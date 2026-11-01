"""VISA INSTR + serial COM scan, probe, classify, and config construction.

Serial ASRL/COM ports are probed with bare ``IDN?`` then ``*IDN?`` across a short
baud list. Fluke handheld ``QM`` is tried only after IDN fails. FTDI / digital IO
adapters are not discovered here.
"""

from __future__ import annotations

import contextlib
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

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
from colosseum_equipment.autoconfig.sort import sort_resources
from colosseum_equipment.instruments.identify import probe_identity
from colosseum_equipment.transports.visa import normalize_visa_resource

if TYPE_CHECKING:
    from colosseum_equipment.network import IPv4NetworkBinding

_IDN_BAUDS = (9600, 115200, 19200)
_QM_BAUDS = (9600, 115200)
_ASRL_NUM = re.compile(r"^ASRL(\d+)", re.IGNORECASE)
_COM_NUM = re.compile(r"^COM(\d+)$", re.IGNORECASE)


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


class _VisaProbeAdapter:
    """Adapt a pyVISA instrument to identify/QM probe helpers."""

    def __init__(self, inst: object) -> None:
        self._inst = inst

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

    def read_until(self, terminator: bytes) -> str:
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

    def flush(self) -> None:
        reset = getattr(self._port, "reset_input_buffer", None)
        if callable(reset):
            with contextlib.suppress(Exception):
                reset()

    def write_bytes(self, payload: bytes) -> None:
        self._port.write(payload)  # type: ignore[attr-defined]

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


def _default_open_serial(port: str, baudrate: int, timeout: float) -> object:
    import serial

    return serial.Serial(port=port, baudrate=baudrate, timeout=timeout)


def discover_equipment_config(
    *,
    timeout: float = 5.0,
    visa_library: str | None = None,
    blacklist: str | Sequence[str] | None = None,
    network_bindings: Sequence[IPv4NetworkBinding] | None = None,
    resource_manager: object | None = None,
    logger: AutoconfigProgress | None = None,
    list_comports: Callable[[], Sequence[Any]] | None = None,
    open_serial: OpenSerial | None = None,
) -> AutoconfigResult:
    """Scan VISA ``?*INSTR`` and local COM ports; build a raw equipment config dict.

    Serial ports use bare ``IDN?`` then ``*IDN?`` across bauds ``9600``, ``115200``,
    ``19200``. Fluke ``QM`` is tried only after IDN fails (bauds ``9600``, ``115200``).
    FTDI adapters are not discovered.
    """
    import pyvisa

    blacklist_resolution = resolve_blacklist(blacklist, bindings=network_bindings)
    blocked = list(blacklist_resolution.blocked)
    log_scan_start(logger)

    if resource_manager is None:
        rm: object = (
            pyvisa.ResourceManager(visa_library) if visa_library else pyvisa.ResourceManager()
        )
    else:
        rm = resource_manager

    try:
        resources = list(rm.list_resources("?*INSTR"))  # type: ignore[attr-defined]
    except Exception as exc:
        raise ConfigError(f"VISA resource scan failed: {exc}") from exc

    scanned_count = len(resources)
    allowed, blacklisted = filter_resources(resources, blocked)
    for resource, subnet in blacklisted:
        log_blacklist(logger, resource, subnet)

    sorted_resources = sort_resources(allowed)
    assignments: list[AutoconfigAssignment] = []
    skipped: list[AutoconfigSkip] = []
    seen_resources: set[str] = set()
    covered_ports: set[str] = set()
    next_id: dict[str, int] = {}
    open_serial_fn = open_serial or _default_open_serial

    def _assign(
        *,
        kind: str,
        model: str,
        idn: str,
        resource: str,
        port: str | None,
        baudrate: int | None,
    ) -> None:
        section, _id_field = KIND_SECTIONS[kind]
        item_id = next_id.get(kind, 0) + 1
        next_id[kind] = item_id
        port_out, driver, baud_out = _serial_row_fields(
            model=model, resource=resource, port=port, baudrate=baudrate,
        )
        if port_out:
            covered_ports.add(port_out.upper())
        if resource:
            seen_resources.add(resource)
            asrl_port = _port_from_asrl(resource)
            if asrl_port:
                covered_ports.add(asrl_port.upper())
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
        )
        assignments.append(assignment)
        log_assignment(logger, assignment)

    def _skip(resource: str, reason: str, idn: str | None = None) -> None:
        skip = AutoconfigSkip(resource=resource, reason=reason, idn=idn)
        skipped.append(skip)
        log_skip(logger, skip)

    def _probe_visa(resource: str) -> None:
        if resource in seen_resources:
            _skip(resource, "duplicate_resource")
            return
        asrl = _is_asrl_resource(resource)
        if asrl:
            _probe_serial_candidate(
                label=resource,
                resource=resource,
                port=_port_from_asrl(resource),
                open_probe=lambda baud: _open_visa_probe(rm, resource, baud, timeout),
            )
            return
        log_probing(logger, resource)
        try:
            inst = rm.open_resource(resource)  # type: ignore[attr-defined]
        except Exception as exc:
            _skip(resource, f"probe_failed: {exc}")
            return
        try:
            inst.timeout = int(timeout * 1000)
            adapter = _VisaProbeAdapter(inst)
            idn, bare = probe_identity(adapter, asrl=False, log_kind="autoconfig")
        except Exception as exc:
            _skip(resource, f"probe_failed: {exc}")
            return
        finally:
            with contextlib.suppress(Exception):
                inst.close()
        if idn is None:
            _skip(resource, "probe_failed: no identity")
            return
        hit = _classify_idn_hit(idn, bare=bare)
        if hit is None:
            _skip(resource, "no_kind_match", idn=idn)
            return
        kind, model, idn_label = hit
        if kind not in KIND_SECTIONS:
            _skip(resource, "no_kind_match", idn=idn)
            return
        _assign(kind=kind, model=model, idn=idn_label, resource=resource, port=None, baudrate=None)

    def _probe_serial_candidate(
        *,
        label: str,
        resource: str,
        port: str | None,
        open_probe: Callable[[int], Any],
    ) -> None:
        last_errors: list[str] = []
        for baud in _IDN_BAUDS:
            log_probing(logger, label, baud=baud)
            try:
                probe = open_probe(baud)
            except Exception as exc:
                last_errors.append(f"baud={baud} open:{exc}")
                continue
            try:
                idn, bare = probe_identity(probe, asrl=True, log_kind="autoconfig")
            except Exception as exc:
                last_errors.append(f"baud={baud} idn:{exc}")
                idn, bare = None, False
            finally:
                close = getattr(probe, "close", None)
                if callable(close):
                    with contextlib.suppress(Exception):
                        close()
            if idn is None:
                continue
            hit = _classify_idn_hit(idn, bare=bare)
            if hit is None:
                last_errors.append(f"baud={baud} no_kind_match idn={idn!r}")
                continue
            kind, model, idn_label = hit
            if kind not in KIND_SECTIONS:
                continue
            _assign(
                kind=kind,
                model=model,
                idn=idn_label,
                resource=resource,
                port=port,
                baudrate=baud,
            )
            return

        for baud in _QM_BAUDS:
            log_probing(logger, f"{label} QM", baud=baud)
            try:
                probe = open_probe(baud)
            except Exception as exc:
                last_errors.append(f"baud={baud} qm_open:{exc}")
                continue
            try:
                qm_model = query_qm_model(probe)
            except Exception as exc:
                last_errors.append(f"baud={baud} qm:{exc}")
                qm_model = None
            finally:
                close = getattr(probe, "close", None)
                if callable(close):
                    with contextlib.suppress(Exception):
                        close()
            if qm_model is None:
                continue
            _assign(
                kind="dmm",
                model=qm_model,
                idn=f"QM:{qm_model}",
                resource=resource,
                port=port,
                baudrate=baud,
            )
            return

        detail = "; ".join(last_errors) if last_errors else "no response"
        _skip(label, f"probe_failed: {detail}")

    def _open_visa_probe(
        manager: object, resource: str, baud: int, seconds: float,
    ) -> _VisaProbeAdapter:
        inst = manager.open_resource(resource)  # type: ignore[attr-defined]
        inst.timeout = int(seconds * 1000)
        with contextlib.suppress(Exception):
            inst.baud_rate = int(baud)
        adapter = _VisaProbeAdapter(inst)

        def _close() -> None:
            with contextlib.suppress(Exception):
                inst.close()

        adapter.close = _close  # type: ignore[attr-defined]
        return adapter

    def _open_com_probe(com_port: str, baud: int) -> _PyserialProbeAdapter:
        ser = open_serial_fn(com_port, baud, timeout)
        adapter = _PyserialProbeAdapter(ser)

        def _close() -> None:
            close = getattr(ser, "close", None)
            if callable(close):
                with contextlib.suppress(Exception):
                    close()

        adapter.close = _close  # type: ignore[attr-defined]
        return adapter

    for resource in sorted_resources:
        _probe_visa(resource)

    comport_list: Sequence[Any]
    if list_comports is not None:
        comport_list = list_comports()
    else:
        try:
            from serial.tools import list_ports

            comport_list = list(list_ports.comports())
        except Exception:
            comport_list = []

    for info in comport_list:
        port = str(getattr(info, "device", "") or "").strip()
        if not port:
            continue
        if port.upper() in covered_ports:
            continue
        asrl = _asrl_from_port(port)
        if asrl and asrl in seen_resources:
            continue

        def _open_for_port(baud: int, *, p: str = port) -> _PyserialProbeAdapter:
            return _open_com_probe(p, baud)

        _probe_serial_candidate(
            label=port,
            resource=asrl or "",
            port=port,
            open_probe=_open_for_port,
        )

    if not assignments:
        summary = ", ".join(f"{skip.resource} ({skip.reason})" for skip in skipped) or "none"
        raise ConfigError(f"no classifiable instruments found; skipped: {summary}")

    raw = _build_raw_config(assignments)
    result = AutoconfigResult(
        raw=raw,
        scanned_count=scanned_count,
        assignments=assignments,
        blacklisted=blacklisted,
        skipped=skipped,
        blacklist_subnets=list(blocked),
        unresolved_blacklist=list(blacklist_resolution.unresolved_entries),
    )
    log_summary(logger, result)
    return result
