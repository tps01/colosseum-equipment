"""VISA INSTR + serial COM scan, probe, classify, and config construction.

Serial ASRL/COM ports are probed with bare ``IDN?`` then ``*IDN?`` across a short
baud list. VISA ASRL sessions enable CR termination (matching bench tools). Fluke
handheld ``QM`` and GNSS vendor probes are opt-in (``qm=True`` / ``gnss=True``)
and run only after IDN fails. Hard serial open errors abort further baud tries.
Optional ``gpib_scan`` sweeps ``GPIB0`` primary addresses when list_resources is
empty for GPIB. Linux ``/dev/usbtmcN`` nodes are probed without VISA. FTDI /
digital IO adapters are not discovered here.
"""

from __future__ import annotations

import contextlib
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, cast

from colosseum.config.loader import ConfigError

from colosseum_equipment.autoconfig.idn_registry import (
    KIND_SECTIONS,
    classify_idn,
    lambda_gen_identity,
)
from colosseum_equipment.autoconfig.logging import (
    AutoconfigProgress,
    log_assignment,
    log_blacklist,
    log_probing,
    log_scan_start,
    log_skip,
    log_summary,
)
from colosseum_equipment.autoconfig.network_filter import (
    BlockedSubnet,
    filter_resources,
    resolve_blacklist,
)
from colosseum_equipment.autoconfig.qm_probe import query_qm_model
from colosseum_equipment.autoconfig.sort import interface_name, sort_resources
from colosseum_equipment.instruments.identify import probe_identity
from colosseum_equipment.transports.usbtmc import UsbtmcTransport, list_usbtmc_devices
from colosseum_equipment.transports.visa import normalize_visa_resource, open_resource_manager

if TYPE_CHECKING:
    from colosseum_equipment.network import IPv4NetworkBinding

_IDN_BAUDS = (9600, 115200, 19200)
_QM_BAUDS = (9600, 115200)
_GPIB_PRIMARY_ADDRESSES = range(31)
_ASRL_NUM = re.compile(r"^ASRL(\d+)", re.IGNORECASE)
_COM_NUM = re.compile(r"^COM(\d+)$", re.IGNORECASE)
_HARD_OPEN_MARKERS = (
    "ASRL_PARITY",
    "ASRL_FRAMING",
    "ASRL_OVERRUN",
    "VI_ERROR_ASRL_PARITY",
    "VI_ERROR_ASRL_FRAMING",
    "VI_ERROR_ASRL_OVERRUN",
    "0xBFFF0060",
    "0xBFFF0061",
    "0xBFFF0062",
    "BFFF0060",
    "BFFF0061",
    "BFFF0062",
)


@dataclass(frozen=True)
class AutoconfigAssignment:
    """One autoconfigured instrument row."""

    section: str
    item_id: int
    kind: str
    resource: str
    model: str
    idn: str
    port: str | None = None
    driver: str | None = None
    baudrate: int | None = None
    device_address: int | None = None


@dataclass(frozen=True)
class AutoconfigSkip:
    """A resource that was not added to generated config."""

    resource: str
    reason: str
    idn: str | None = None


@dataclass
class AutoconfigResult:
    """Outcome of autoconfig discovery."""

    raw: dict[str, Any]
    scanned_count: int
    assignments: list[AutoconfigAssignment] = field(default_factory=list)
    blacklisted: list[tuple[str, BlockedSubnet]] = field(default_factory=list)
    skipped: list[AutoconfigSkip] = field(default_factory=list)
    blacklist_subnets: list[BlockedSubnet] = field(default_factory=list)
    unresolved_blacklist: list[str] = field(default_factory=list)


def _is_hard_serial_open_error(exc: BaseException) -> bool:
    """Return whether ``exc`` is a hard ASRL open failure (skip remaining bauds)."""
    text = f"{type(exc).__name__}: {exc}".upper()
    if "TMO" in text or "TIMEOUT" in text:
        return False
    return (
        any(marker in text for marker in _HARD_OPEN_MARKERS)
        or ("PARITY" in text and "ASRL" in text)
        or ("FRAMING" in text and "ASRL" in text)
        or ("OVERRUN" in text and "ASRL" in text)
    )


def _configure_asrl_cr_termchar(inst: object) -> None:
    """Enable CR termination on a VISA ASRL session (matches working bench tools)."""
    with contextlib.suppress(Exception):
        inst.read_termination = "\r"  # type: ignore[attr-defined]
        inst.write_termination = "\r"  # type: ignore[attr-defined]
        return
    try:
        import pyvisa.constants as visa_constants

        set_attr = getattr(inst, "set_visa_attribute", None)
        if not callable(set_attr):
            return
        set_attr(visa_constants.VI_ATTR_TERMCHAR, ord("\r"))
        set_attr(visa_constants.VI_ATTR_TERMCHAR_EN, visa_constants.VI_TRUE)
    except Exception:
        return


class _VisaResource(Protocol):
    """Minimal pyVISA instrument surface used by discovery open/probe helpers."""

    timeout: float
    baud_rate: int

    def close(self) -> None: ...

    def query(self, command: str) -> object: ...


class _VisaProbeAdapter:
    """Adapt a pyVISA instrument to identify/QM probe helpers."""

    def __init__(self, inst: object, *, cr_termchar: bool = False) -> None:
        self._inst = inst
        self._cr_termchar = cr_termchar

    def close(self) -> None:
        _close_probe(self._inst)

    def query(self, command: str) -> str:
        return str(self._inst.query(command))  # type: ignore[attr-defined]

    def flush(self) -> None:
        flush = getattr(self._inst, "flush", None)
        if callable(flush):
            with contextlib.suppress(Exception):
                flush()
            return
        clear = getattr(self._inst, "clear", None)
        if callable(clear):
            with contextlib.suppress(Exception):
                clear()

    def write_bytes(self, payload: bytes) -> None:
        write_bytes = getattr(self._inst, "write_bytes", None)
        if callable(write_bytes):
            write_bytes(payload)
            return
        write_raw = getattr(self._inst, "write_raw", None)
        if callable(write_raw):
            write_raw(payload)
            return
        write = getattr(self._inst, "write", None)
        if callable(write):
            write(payload.decode("ascii", errors="replace"))
            return
        raise AttributeError("VISA instrument cannot write raw bytes")

    def read_bytes(self, size: int = 512) -> bytes:
        read_bytes = getattr(self._inst, "read_bytes", None)
        if callable(read_bytes):
            return bytes(read_bytes(size))
        read_raw = getattr(self._inst, "read_raw", None)
        if callable(read_raw):
            return bytes(read_raw(size))
        return b""

    def in_waiting(self) -> int:
        waiting = getattr(self._inst, "bytes_in_buffer", None)
        if waiting is not None and not callable(waiting):
            try:
                return int(waiting)
            except Exception:
                return 0
        in_waiting = getattr(self._inst, "in_waiting", None)
        if callable(in_waiting):
            try:
                return int(in_waiting())
            except Exception:
                return 0
        return -1

    def read_until(self, terminator: bytes) -> str:
        # Prefer a single cooked VISA read when CR termchar is enabled (bulk line).
        if self._cr_termchar and terminator in {b"\r", b"\r\n"}:
            read = getattr(self._inst, "read", None)
            if callable(read):
                return str(read())
        read_until = getattr(self._inst, "read_until", None)
        if callable(read_until):
            return str(read_until(terminator))
        read_raw = getattr(self._inst, "read_raw", None)
        if callable(read_raw):
            buf = bytearray()
            while not buf.endswith(terminator):
                chunk = read_raw(1)
                if not chunk:
                    break
                buf.extend(chunk)
            return buf.decode("ascii", errors="replace")
        read = getattr(self._inst, "read", None)
        if callable(read):
            return str(read())
        raise AttributeError("VISA instrument cannot read until terminator")


class _PyserialProbeAdapter:
    """Adapt a pyserial port to identify/QM probe helpers."""

    def __init__(self, port: object) -> None:
        self._port = port

    def close(self) -> None:
        _close_probe(self._port)

    def flush(self) -> None:
        reset = getattr(self._port, "reset_input_buffer", None)
        if callable(reset):
            with contextlib.suppress(Exception):
                reset()

    def write_bytes(self, payload: bytes) -> None:
        self._port.write(payload)  # type: ignore[attr-defined]

    def read_bytes(self, size: int = 512) -> bytes:
        read = getattr(self._port, "read", None)
        if callable(read):
            return bytes(read(size))
        return b""

    def in_waiting(self) -> int:
        waiting = getattr(self._port, "in_waiting", None)
        if waiting is None:
            return -1
        try:
            return int(waiting) if not callable(waiting) else int(waiting())
        except Exception:
            return 0

    def read_until(self, terminator: bytes) -> str:
        raw = self._port.read_until(terminator)  # type: ignore[attr-defined]
        return bytes(raw).decode("ascii", errors="replace")

    def query(self, command: str) -> str:
        self.flush()
        self.write_bytes(f"{command}\n".encode("ascii"))
        return self.read_until(b"\n").strip()


def _port_from_asrl(resource: str) -> str | None:
    match = _ASRL_NUM.match(normalize_visa_resource(resource).split("::", 1)[0])
    if match is None:
        return None
    return f"COM{int(match.group(1))}"


def _asrl_from_port(port: str) -> str | None:
    match = _COM_NUM.match(port.strip())
    if match is None:
        return None
    return f"ASRL{int(match.group(1))}::INSTR"


def _is_asrl_resource(resource: str) -> bool:
    return normalize_visa_resource(resource).upper().startswith("ASRL")


def _build_raw_config(assignments: Sequence[AutoconfigAssignment]) -> dict[str, Any]:
    raw: dict[str, Any] = {"equipment": {}}
    equipment = raw["equipment"]
    for assignment in assignments:
        section_name = assignment.section.split(".", 1)[1]
        id_field = KIND_SECTIONS[assignment.kind][1]
        row: dict[str, Any] = {
            id_field: assignment.item_id,
            "model": assignment.model,
        }
        if assignment.resource:
            row["resource"] = assignment.resource
        if assignment.port:
            row["port"] = assignment.port
        if assignment.driver:
            row["driver"] = assignment.driver
        if assignment.baudrate is not None:
            row["baudrate"] = assignment.baudrate
        if assignment.device_address is not None:
            row["device_address"] = assignment.device_address
        existing = equipment.get(section_name)
        if existing is None:
            equipment[section_name] = [row]
        elif isinstance(existing, list):
            existing.append(row)
        else:
            equipment[section_name] = [existing, row]
    return raw


def _classify_idn_hit(idn: str, *, bare: bool) -> tuple[str, str, str] | None:
    """Return ``(kind, model, idn_label)`` or ``None``."""
    if bare and lambda_gen_identity(idn):
        return "psu", "tdk-genesys-serial", idn
    match = classify_idn(idn)
    if match is None:
        return None
    return match.kind, match.model, idn


def _serial_row_fields(
    *,
    model: str,
    resource: str,
    port: str | None,
    baudrate: int | None,
) -> tuple[str | None, str | None, int | None]:
    if model in {"tdk-genesys-serial", "fluke-189", "fluke-289"}:
        mapped_port = port or _port_from_asrl(resource)
        return mapped_port, "serial", baudrate if baudrate is not None else 9600
    return port, None, baudrate


OpenSerial = Callable[[str, int, float], object]
SerialProbeFn = Callable[[object, int, list[str]], "_SerialHit | None"]

_HARD_ABORT = object()


@dataclass
class _DiscoveryState:
    """Mutable discovery scratch shared across probe helpers."""

    assignments: list[AutoconfigAssignment] = field(default_factory=list)
    skipped: list[AutoconfigSkip] = field(default_factory=list)
    seen_resources: set[str] = field(default_factory=set)
    covered_ports: set[str] = field(default_factory=set)
    next_id: dict[str, int] = field(default_factory=dict)
    logger: AutoconfigProgress | None = None


@dataclass(frozen=True)
class _SerialHit:
    """Successful serial-phase probe ready to assign."""

    kind: str
    model: str
    idn: str
    device_address: int | None = None


def _default_open_serial(port: str, baudrate: int, timeout: float) -> object:
    import serial

    return serial.Serial(port=port, baudrate=baudrate, timeout=timeout)


def _default_gpib_board_present() -> bool:
    """Return whether linux-gpib board 0 looks usable on this host."""
    try:
        import gpib  # noqa: F401
    except ImportError:
        return False
    node = Path("/dev/gpib0")
    try:
        return node.exists()
    except OSError:
        return False


def _listed_gpib_resources(resources: Sequence[str]) -> bool:
    return any(interface_name(resource) == "GPIB" for resource in resources)


def _record_assignment(
    state: _DiscoveryState,
    *,
    kind: str,
    model: str,
    idn: str,
    resource: str,
    port: str | None,
    baudrate: int | None,
    device_address: int | None = None,
) -> None:
    section, _id_field = KIND_SECTIONS[kind]
    item_id = state.next_id.get(kind, 0) + 1
    state.next_id[kind] = item_id
    port_out, driver, baud_out = _serial_row_fields(
        model=model,
        resource=resource,
        port=port,
        baudrate=baudrate,
    )
    if kind == "gnss":
        port_out = port_out or _port_from_asrl(resource)
        driver = "serial"
        if baud_out is None:
            baud_out = 9600
    if port_out:
        state.covered_ports.add(port_out.upper())
    if resource:
        state.seen_resources.add(resource)
        asrl_port = _port_from_asrl(resource)
        if asrl_port:
            state.covered_ports.add(asrl_port.upper())
    assignment = AutoconfigAssignment(
        section=section,
        item_id=item_id,
        kind=kind,
        resource=resource,
        model=model,
        idn=idn,
        port=port_out,
        driver=driver,
        baudrate=baud_out,
        device_address=device_address,
    )
    state.assignments.append(assignment)
    log_assignment(state.logger, assignment)


def _record_skip(
    state: _DiscoveryState,
    resource: str,
    reason: str,
    idn: str | None = None,
) -> None:
    skip = AutoconfigSkip(resource=resource, reason=reason, idn=idn)
    state.skipped.append(skip)
    log_skip(state.logger, skip)


def _assign_classified_idn(
    state: _DiscoveryState,
    *,
    idn: str,
    bare: bool,
    resource: str,
    port: str | None = None,
    baudrate: int | None = None,
    device_address: int | None = None,
) -> bool:
    """Classify ``idn`` and assign, or skip with ``no_kind_match``. Return True if assigned."""
    hit = _classify_idn_hit(idn, bare=bare)
    if hit is None or hit[0] not in KIND_SECTIONS:
        _record_skip(state, resource, "no_kind_match", idn=idn)
        return False
    kind, model, idn_label = hit
    _record_assignment(
        state,
        kind=kind,
        model=model,
        idn=idn_label,
        resource=resource,
        port=port,
        baudrate=baudrate,
        device_address=device_address,
    )
    return True


def _close_probe(probe: object) -> None:
    close = getattr(probe, "close", None)
    if callable(close):
        with contextlib.suppress(Exception):
            close()


def _open_visa_resource(manager: object, resource: str, timeout: float) -> _VisaResource:
    """Open a VISA resource, preferring ``open_timeout`` when the backend supports it."""
    open_timeout_ms = max(1, int(timeout * 1000))
    try:
        return cast(
            "_VisaResource",
            manager.open_resource(  # type: ignore[attr-defined]
                resource,
                open_timeout=open_timeout_ms,
            ),
        )
    except TypeError:
        return cast(
            "_VisaResource",
            manager.open_resource(resource),  # type: ignore[attr-defined]
        )


def _open_visa_asrl_probe(
    manager: object,
    resource: str,
    baud: int,
    seconds: float,
) -> _VisaProbeAdapter:
    open_timeout_ms = max(1, int(seconds * 1000))
    inst = _open_visa_resource(manager, resource, seconds)
    inst.timeout = open_timeout_ms
    with contextlib.suppress(Exception):
        inst.baud_rate = int(baud)
    _configure_asrl_cr_termchar(inst)
    return _VisaProbeAdapter(inst, cr_termchar=True)


def _open_com_probe(
    open_serial_fn: OpenSerial,
    com_port: str,
    baud: int,
    timeout: float,
) -> _PyserialProbeAdapter:
    ser = open_serial_fn(com_port, baud, timeout)
    return _PyserialProbeAdapter(ser)


def _open_serial_baud(
    *,
    baud: int,
    phase: str,
    open_probe: Callable[[int], Any],
    last_errors: list[str],
    state: _DiscoveryState,
    label: str,
) -> object | None:
    """Open at ``baud``. Return probe, ``None`` to try next baud, or ``_HARD_ABORT``."""
    try:
        return cast("object", open_probe(baud))
    except Exception as exc:
        last_errors.append(f"baud={baud} {phase}:{exc}")
        if _is_hard_serial_open_error(exc):
            detail = "; ".join(last_errors)
            _record_skip(state, label, f"probe_failed: hard_open:{exc}; {detail}")
            return _HARD_ABORT
        return None


def _probe_idn_on_serial(
    probe: object,
    baud: int,
    last_errors: list[str],
) -> _SerialHit | None:
    try:
        idn, bare, device_address = probe_identity(
            probe,
            asrl=True,
            log_kind="autoconfig",
        )
    except Exception as exc:
        last_errors.append(f"baud={baud} idn:{exc}")
        return None
    if idn is None:
        return None
    hit = _classify_idn_hit(idn, bare=bare)
    if hit is None:
        last_errors.append(f"baud={baud} no_kind_match idn={idn!r}")
        return None
    kind, model, idn_label = hit
    if kind not in KIND_SECTIONS:
        return None
    return _SerialHit(
        kind=kind,
        model=model,
        idn=idn_label,
        device_address=device_address,
    )


def _probe_qm_on_serial(
    probe: object,
    baud: int,
    last_errors: list[str],
) -> _SerialHit | None:
    try:
        qm_model = query_qm_model(probe)
    except Exception as exc:
        last_errors.append(f"baud={baud} qm:{exc}")
        return None
    if qm_model is None:
        return None
    return _SerialHit(kind="dmm", model=qm_model, idn=f"QM:{qm_model}")


def _probe_gnss_on_serial(
    probe: object,
    baud: int,
    last_errors: list[str],
) -> _SerialHit | None:
    from colosseum_equipment.instruments.gnss.probe import probe_gnss_model

    try:
        gnss_model = probe_gnss_model(probe)
    except Exception as exc:
        last_errors.append(f"baud={baud} gnss:{exc}")
        return None
    if gnss_model is None:
        return None
    return _SerialHit(kind="gnss", model=gnss_model, idn=f"GNSS:{gnss_model}")


def _sweep_serial_bauds(
    *,
    bauds: Sequence[int],
    log_label: str,
    open_phase: str,
    open_probe: Callable[[int], Any],
    last_errors: list[str],
    probe_fn: SerialProbeFn,
    state: _DiscoveryState,
    label: str,
    resource: str,
    port: str | None,
) -> bool | None:
    """Run a baud sweep. True=assigned, False=hard abort, None=no hit."""
    for baud in bauds:
        log_probing(state.logger, log_label, baud=baud)
        probe = _open_serial_baud(
            baud=baud,
            phase=open_phase,
            open_probe=open_probe,
            last_errors=last_errors,
            state=state,
            label=label,
        )
        if probe is _HARD_ABORT:
            return False
        if probe is None:
            continue
        try:
            hit = probe_fn(probe, baud, last_errors)
        finally:
            _close_probe(probe)
        if hit is None:
            continue
        _record_assignment(
            state,
            kind=hit.kind,
            model=hit.model,
            idn=hit.idn,
            resource=resource,
            port=port,
            baudrate=baud,
            device_address=hit.device_address,
        )
        return True
    return None


def _probe_serial_candidate(
    state: _DiscoveryState,
    *,
    label: str,
    resource: str,
    port: str | None,
    open_probe: Callable[[int], Any],
    qm: bool,
    gnss: bool,
) -> None:
    last_errors: list[str] = []
    sweeps: list[tuple[Sequence[int], str, str, SerialProbeFn]] = [
        (_IDN_BAUDS, label, "open", _probe_idn_on_serial),
    ]
    if qm:
        sweeps.append((_QM_BAUDS, f"{label} QM", "qm_open", _probe_qm_on_serial))
    if gnss:
        sweeps.append((_IDN_BAUDS, f"{label} GNSS", "gnss_open", _probe_gnss_on_serial))

    for bauds, log_label, open_phase, probe_fn in sweeps:
        outcome = _sweep_serial_bauds(
            bauds=bauds,
            log_label=log_label,
            open_phase=open_phase,
            open_probe=open_probe,
            last_errors=last_errors,
            probe_fn=probe_fn,
            state=state,
            label=label,
            resource=resource,
            port=port,
        )
        if outcome is not None:
            return

    detail = "; ".join(last_errors) if last_errors else "no response"
    _record_skip(state, label, f"probe_failed: {detail}")


def _identify_visa_instr(
    manager: object,
    resource: str,
    timeout: float,
) -> tuple[str | None, bool] | str:
    """Open → identify a non-ASRL VISA resource.

    Returns ``(idn, bare)`` on success, or an error reason string for ``probe_failed``.
    """
    open_timeout_ms = max(1, int(timeout * 1000))
    try:
        inst = _open_visa_resource(manager, resource, timeout)
    except Exception as exc:
        return str(exc)
    try:
        inst.timeout = open_timeout_ms
        adapter = _VisaProbeAdapter(inst)
        idn, bare, _addr = probe_identity(adapter, asrl=False, log_kind="autoconfig")
    except Exception as exc:
        return str(exc)
    finally:
        with contextlib.suppress(Exception):
            inst.close()
    return idn, bare


def _probe_visa_instr(
    state: _DiscoveryState,
    manager: object,
    resource: str,
    timeout: float,
) -> None:
    """Open → identify → classify/assign for non-ASRL VISA (GPIB, USBTMC, TCPIP, …)."""
    log_probing(state.logger, resource)
    identified = _identify_visa_instr(manager, resource, timeout)
    if isinstance(identified, str):
        _record_skip(state, resource, f"probe_failed: {identified}")
        return
    idn, bare = identified
    if idn is None:
        _record_skip(state, resource, "probe_failed: no identity")
        return
    _assign_classified_idn(state, idn=idn, bare=bare, resource=resource)


def _probe_usbtmc_path(state: _DiscoveryState, path: str, timeout: float) -> None:
    """Identify a Linux ``/dev/usbtmcN`` node without opening it through VISA."""
    if path in state.seen_resources:
        _record_skip(state, path, "duplicate_resource")
        return
    log_probing(state.logger, path)
    try:
        transport = UsbtmcTransport(path, timeout=timeout)
    except Exception as exc:
        _record_skip(state, path, f"probe_failed: {exc}")
        return
    try:
        adapter = _VisaProbeAdapter(transport)
        idn, bare, _addr = probe_identity(adapter, asrl=False, log_kind="autoconfig")
    except Exception as exc:
        _record_skip(state, path, f"probe_failed: {exc}")
        return
    finally:
        with contextlib.suppress(Exception):
            transport.close()
    if idn is None:
        _record_skip(state, path, "probe_failed: no identity")
        return
    _assign_classified_idn(state, idn=idn, bare=bare, resource=path)


def _probe_visa_resource(
    state: _DiscoveryState,
    manager: object,
    resource: str,
    *,
    timeout: float,
    qm: bool,
    gnss: bool,
) -> None:
    if resource in state.seen_resources:
        _record_skip(state, resource, "duplicate_resource")
        return
    if _is_asrl_resource(resource):
        _probe_serial_candidate(
            state,
            label=resource,
            resource=resource,
            port=_port_from_asrl(resource),
            open_probe=lambda baud: _open_visa_asrl_probe(manager, resource, baud, timeout),
            qm=qm,
            gnss=gnss,
        )
        return
    _probe_visa_instr(state, manager, resource, timeout)


def _list_visa_instr(manager: object) -> list[str]:
    try:
        return list(manager.list_resources("?*INSTR"))  # type: ignore[attr-defined]
    except Exception as exc:
        raise ConfigError(f"VISA resource scan failed: {exc}") from exc


def _list_com_ports(list_comports: Callable[[], Sequence[Any]] | None) -> Sequence[Any]:
    if list_comports is not None:
        return list_comports()
    try:
        from serial.tools import list_ports

        return list(list_ports.comports())
    except Exception:
        return []


def _probe_leftover_com_ports(
    state: _DiscoveryState,
    *,
    timeout: float,
    qm: bool,
    gnss: bool,
    open_serial_fn: OpenSerial,
    list_comports: Callable[[], Sequence[Any]] | None,
) -> None:
    for info in _list_com_ports(list_comports):
        port = str(getattr(info, "device", "") or "").strip()
        if not port or port.upper() in state.covered_ports:
            continue
        asrl = _asrl_from_port(port)
        if asrl and asrl in state.seen_resources:
            continue

        def _open_for_port(
            baud: int,
            *,
            p: str = port,
            opener: OpenSerial = open_serial_fn,
        ) -> _PyserialProbeAdapter:
            return _open_com_probe(opener, p, baud, timeout)

        _probe_serial_candidate(
            state,
            label=port,
            resource=asrl or "",
            port=port,
            open_probe=_open_for_port,
            qm=qm,
            gnss=gnss,
        )


def _finalize_discovery(
    state: _DiscoveryState,
    *,
    scanned_count: int,
    blacklisted: list[tuple[str, BlockedSubnet]],
    blocked: list[BlockedSubnet],
    unresolved: Sequence[str],
) -> AutoconfigResult:
    if not state.assignments:
        summary = ", ".join(f"{skip.resource} ({skip.reason})" for skip in state.skipped) or "none"
        raise ConfigError(f"no classifiable instruments found; skipped: {summary}")
    result = AutoconfigResult(
        raw=_build_raw_config(state.assignments),
        scanned_count=scanned_count,
        assignments=state.assignments,
        blacklisted=blacklisted,
        skipped=state.skipped,
        blacklist_subnets=list(blocked),
        unresolved_blacklist=list(unresolved),
    )
    log_summary(state.logger, result)
    return result


def discover_equipment_config(
    *,
    timeout: float = 1.0,
    visa_library: str | None = None,
    blacklist: str | Sequence[str] | None = None,
    network_bindings: Sequence[IPv4NetworkBinding] | None = None,
    resource_manager: object | None = None,
    logger: AutoconfigProgress | None = None,
    list_comports: Callable[[], Sequence[Any]] | None = None,
    open_serial: OpenSerial | None = None,
    qm: bool = False,
    gnss: bool = False,
    gpib_scan: bool = False,
    gpib_board_present: Callable[[], bool] | None = None,
) -> AutoconfigResult:
    """Scan VISA ``?*INSTR`` and local COM ports; build a raw equipment config dict.

    Serial ports use bare ``IDN?`` then ``*IDN?`` across bauds ``9600``, ``115200``,
    ``19200``. With ``qm=True``, Fluke ``QM`` runs after IDN fails (bauds ``9600``,
    ``115200``). With ``gnss=True``, GNSS vendor probes run after IDN (and QM when
    enabled) miss. With ``gpib_scan=True``, primary addresses ``0``–``30`` on
    ``GPIB0`` are probed when ``list_resources`` returned no GPIB names but a
    board appears present. Linux ``/dev/usbtmcN`` nodes are probed without VISA.
    FTDI adapters are not discovered.
    """
    resolution = resolve_blacklist(blacklist, bindings=network_bindings)
    blocked = list(resolution.blocked)
    log_scan_start(logger)
    if resource_manager is None:
        rm: object = open_resource_manager(visa_library)
    else:
        rm = resource_manager
    resources = _list_visa_instr(rm)
    allowed, blacklisted = filter_resources(resources, blocked)
    for resource, subnet in blacklisted:
        log_blacklist(logger, resource, subnet)

    state = _DiscoveryState(logger=logger)
    sorted_resources = sort_resources(allowed)
    for resource in sorted_resources:
        _probe_visa_resource(state, rm, resource, timeout=timeout, qm=qm, gnss=gnss)

    board_present_fn = gpib_board_present or _default_gpib_board_present
    if gpib_scan and not _listed_gpib_resources(sorted_resources) and board_present_fn():
        for pad in _GPIB_PRIMARY_ADDRESSES:
            _probe_visa_resource(
                state,
                rm,
                f"GPIB0::{pad}::INSTR",
                timeout=timeout,
                qm=qm,
                gnss=gnss,
            )

    for path in list_usbtmc_devices():
        _probe_usbtmc_path(state, path, timeout)

    _probe_leftover_com_ports(
        state,
        timeout=timeout,
        qm=qm,
        gnss=gnss,
        open_serial_fn=open_serial or _default_open_serial,
        list_comports=list_comports,
    )
    return _finalize_discovery(
        state,
        scanned_count=len(resources),
        blacklisted=blacklisted,
        blocked=blocked,
        unresolved=resolution.unresolved_entries,
    )
