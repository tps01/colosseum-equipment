from __future__ import annotations

import contextlib
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from colosseum.logging import get_logger

from colosseum_equipment._cache import cached_resource
from colosseum_equipment.exceptions import EquipmentConnectionError
from colosseum_equipment.transports.base import Transport
from colosseum_equipment.transports.visa_errors import map_visa_exception, raise_mapped_visa_error

if TYPE_CHECKING:
    from collections.abc import Iterator

_logger = get_logger("colosseum.equipment")

_COM_PORT = re.compile(r"COM(\d+):?", re.IGNORECASE)


def _find_checkout_root() -> Path | None:
    # visa.py -> transports -> colosseum_equipment -> repository root
    package_root = Path(__file__).resolve().parents[2]
    if (package_root / "pyproject.toml").is_file():
        return package_root
    current = Path.cwd().resolve()
    for directory in (current, *current.parents):
        if (directory / "pyproject.toml").is_file() and (
            directory / "colosseum_equipment"
        ).is_dir():
            return directory
    return None


def resolve_sim_definition(path: str) -> Path:
    """Resolve a bench ``sim_definition`` path to an existing YAML file."""
    candidate = Path(path)
    if candidate.is_file():
        return candidate.resolve()
    for base in (Path.cwd(), _find_checkout_root() or Path()):
        if base == Path():
            continue
        resolved = (base / candidate).resolve()
        if resolved.is_file():
            return resolved
    raise EquipmentConnectionError(f"PyVISA-sim definition file not found: {path}")


def normalize_visa_resource(address: str) -> str:
    """Return a pyVISA resource string for ``address``.

    ``COM5`` becomes ``ASRL5::INSTR``. Strings that already contain ``::`` are
    returned unchanged. Device paths are wrapped as ``ASRL<path>::INSTR``.
    """
    text = address.strip()
    match = _COM_PORT.fullmatch(text)
    if match:
        return f"ASRL{int(match.group(1))}::INSTR"
    if "::" in text:
        return text
    if text.startswith("/") or text.startswith("\\\\.\\"):
        return f"ASRL{text}::INSTR"
    return text


def _context_cache() -> dict[str, object] | None:
    try:
        from colosseum.context import get_context

        return get_context().resource_cache
    except RuntimeError:
        return None


def _new_resource_manager(visa_library: str | None, sim_path: str | None) -> Any:  # noqa: ANN401
    import pyvisa

    if sim_path is not None:
        return pyvisa.ResourceManager(f"{sim_path}@sim")
    if visa_library:
        return pyvisa.ResourceManager(visa_library)
    return pyvisa.ResourceManager()


def _enable_tcp_nodelay(session: Any) -> tuple[object | None, object | None]:  # noqa: ANN401
    """Return ``(attribute, previous)`` after enabling TCP no-delay, or ``(None, None)``."""
    try:
        import pyvisa

        attribute = pyvisa.constants.VI_ATTR_TCPIP_NODELAY
        previous = session.get_visa_attribute(attribute)
        session.set_visa_attribute(attribute, pyvisa.constants.VI_TRUE)
    except Exception:
        return None, None
    return attribute, previous


def _release_failed_open(session: object, manager: object, *, shared: bool) -> None:
    close_session = getattr(session, "close", None)
    if callable(close_session):
        with contextlib.suppress(Exception):
            close_session()
    if shared:
        return
    close_manager = getattr(manager, "close", None)
    if callable(close_manager):
        with contextlib.suppress(Exception):
            close_manager()


def _acquire_resource_manager(
    visa_library: str | None,
    sim_path: str | None,
) -> tuple[Any, bool]:
    """Return ``(manager, shared)``. A shared manager is closed by ``close_all``."""
    cache = _context_cache()
    if cache is None:
        return _new_resource_manager(visa_library, sim_path), False
    if sim_path is not None:
        key = f"visa:manager:sim:{sim_path}"
    else:
        key = f"visa:manager:lib:{visa_library or ''}"

    def _open() -> Any:  # noqa: ANN401
        return _new_resource_manager(visa_library, sim_path)

    return cached_resource(cache, key, _open), True


class VISATransport(Transport):
    _inst: Any

    def __init__(
        self,
        resource: str,
        timeout: float = 5.0,
        *,
        visa_backend: str | None = None,
        sim_definition: str | None = None,
        visa_library: str | None = None,
        baudrate: int | None = None,
        line_mode: bool = False,
    ) -> None:
        self._resource = resource
        self._timeout = timeout
        self._shared_manager = False
        backend = (visa_backend or "").lower()
        sim_path: str | None = None
        manager: Any = None
        session: Any = None
        try:
            if backend == "sim":
                if not sim_definition:
                    raise EquipmentConnectionError(
                        "visa_backend=sim requires `sim_definition` in bench config",
                    )
                sim_path = str(resolve_sim_definition(sim_definition))
            manager, self._shared_manager = _acquire_resource_manager(
                str(visa_library) if visa_library else None,
                sim_path,
            )
            self._rm = manager
            if backend == "sim" or line_mode:
                session = self._rm.open_resource(
                    resource,
                    read_termination="\n",
                    write_termination="\n",
                )
            else:
                session = self._rm.open_resource(resource)
            self._inst = session
            self._inst.timeout = int(timeout * 1000)
            if baudrate is not None:
                self._inst.baud_rate = int(baudrate)
        except EquipmentConnectionError:
            _release_failed_open(session, manager, shared=self._shared_manager)
            raise
        except Exception as exc:
            _release_failed_open(session, manager, shared=self._shared_manager)
            mapped = map_visa_exception(exc, resource=resource)
            raise EquipmentConnectionError(
                f"Failed to open VISA resource `{resource}`: {mapped}",
            ) from exc
        _logger.debug(
            "VISA resource open: %s backend=%s timeout=%ss line_mode=%s",
            resource,
            backend or "default",
            timeout,
            line_mode,
        )

    def write(self, data: str) -> None:
        try:
            self._inst.write(data)
        except Exception as exc:
            raise_mapped_visa_error(exc, resource=self._resource)

    def read(self) -> str:
        try:
            return str(self._inst.read())
        except Exception as exc:
            raise_mapped_visa_error(exc, resource=self._resource)

    def query(self, data: str) -> str:
        try:
            return str(self._inst.query(data))
        except Exception as exc:
            raise_mapped_visa_error(exc, resource=self._resource)

    def write_raw(self, data: bytes) -> None:
        try:
            self._inst.write_raw(data)
        except Exception as exc:
            raise_mapped_visa_error(exc, resource=self._resource)

    def write_bytes(self, payload: bytes) -> None:
        self.write_raw(payload)

    def read_raw(self, size: int = 655360) -> bytes:
        try:
            return bytes(self._inst.read_raw(size))
        except Exception as exc:
            raise_mapped_visa_error(exc, resource=self._resource)

    def read_bytes(self, size: int) -> bytes:
        try:
            return bytes(self._inst.read_bytes(size))
        except Exception as exc:
            raise_mapped_visa_error(exc, resource=self._resource)

    def read_until(self, terminator: str | bytes) -> str:
        term = terminator.encode("ascii") if isinstance(terminator, str) else terminator
        buffer = bytearray()
        while not bytes(buffer).endswith(term):
            chunk = self.read_bytes(1)
            if not chunk:
                break
            buffer.extend(chunk)
        return bytes(buffer).decode("ascii", errors="replace")

    def flush(self) -> None:
        import pyvisa

        mask = pyvisa.constants.VI_READ_BUF_DISCARD | pyvisa.constants.VI_WRITE_BUF_DISCARD
        try:
            self._inst.flush(mask)
        except Exception as exc:
            raise_mapped_visa_error(exc, resource=self._resource)

    def in_waiting(self) -> int:
        try:
            return int(self._inst.bytes_in_buffer)
        except Exception as exc:
            raise_mapped_visa_error(exc, resource=self._resource)

    def set_timeout_s(self, timeout_s: float) -> None:
        self._timeout = float(timeout_s)
        if getattr(self, "_inst", None) is not None:
            self._inst.timeout = int(float(timeout_s) * 1000)

    @contextlib.contextmanager
    def large_binary_write(self, nbytes: int) -> Iterator[None]:
        """Send one SCPI block without the default 20 KiB VISA chunks.

        ``chunk_size`` becomes the full message so ``write_raw`` is a single
        ``viWrite``. TCP no-delay is enabled for that write, and the timeout
        covers a slow ingest instead of the 5 s session default.
        """
        session = self._inst
        previous_chunk = int(session.chunk_size)
        previous_timeout = self._timeout
        nodelay_attr: object | None = None
        previous_nodelay: object | None = None
        try:
            session.chunk_size = max(previous_chunk, int(nbytes))
            needed_s = max(previous_timeout, (int(nbytes) * 8) / 50_000 + 30.0)
            self.set_timeout_s(needed_s)
            nodelay_attr, previous_nodelay = _enable_tcp_nodelay(session)
            yield
        finally:
            with contextlib.suppress(Exception):
                session.chunk_size = previous_chunk
            with contextlib.suppress(Exception):
                self.set_timeout_s(previous_timeout)
            if nodelay_attr is not None and previous_nodelay is not None:
                with contextlib.suppress(Exception):
                    session.set_visa_attribute(nodelay_attr, previous_nodelay)

    def close(self) -> None:
        with contextlib.suppress(Exception):
            self._inst.close()
        if not self._shared_manager:
            with contextlib.suppress(Exception):
                self._rm.close()
