"""Choose an instrument model when a config row omits ``model``."""

from __future__ import annotations

import contextlib
from collections.abc import Callable, Sequence
from typing import Any

from colosseum.logging import get_logger

from colosseum_equipment.instruments.registry import registered_models
from colosseum_equipment.transports.factory import resolve_connection
from colosseum_equipment.transports.visa import normalize_visa_resource

_logger = get_logger("colosseum.equipment")

_NO_PROBE_KINDS = frozenset({"serial", "relay"})
# Genesys default bus address is 6 (bench tools often send ``ADR 06``).
_GENESYS_ADR_CANDIDATES = (6,)


def instrument_config(kind: str, config: dict[str, Any], model: str) -> dict[str, Any]:
    """Return a row copy whose ``model`` is the resolved slug."""
    resolved = dict(config)
    resolved["model"] = model
    if model == "tdk-genesys-serial" and kind == "psu":
        resolved["driver"] = "serial"
        if "baudrate" not in resolved:
            resolved["baudrate"] = 9600
    return resolved


def _resolve_gnss_model(transport: object) -> str:
    from colosseum_equipment.instruments.gnss.probe import probe_gnss_model

    hit = probe_gnss_model(transport)
    if hit and hit in registered_models("gnss"):
        return hit
    if hit:
        _logger.warning(
            "equipment.gnss probe selected unregistered model `%s`; using generic",
            hit,
        )
    return "generic"


def _model_from_idn(kind: str, idn: str, *, bare: bool) -> str:
    from colosseum_equipment.autoconfig.idn_registry import classify_idn, lambda_gen_identity

    if bare and lambda_gen_identity(idn):
        model = "tdk-genesys-serial"
    else:
        match = classify_idn(idn)
        if match is None or match.kind != kind:
            _logger.warning(
                "equipment.%s identity %r did not match a %s model; using generic",
                kind,
                idn,
                kind,
            )
            return "generic"
        model = match.model
    if model not in registered_models(kind):
        _logger.warning(
            "equipment.%s identity %r selected unregistered model `%s`; using generic",
            kind,
            idn,
            model,
        )
        return "generic"
    return model


def resolve_instrument_model(kind: str, config: dict[str, Any], transport: object) -> str:
    """Return the model slug for ``config``.

    A non-empty ``model`` wins and does not query. GNSS (no ``*IDN?``) uses a
    vendor stream probe when ``model`` is omitted. Otherwise a pyVISA instrument
    is classified from ``*IDN?`` within ``kind``, falling back to ``generic``.
    A COM or ASRL resource is probed with ``IDN?`` first (Genesys may need
    ``ADR n`` first). A Lambda GEN reply selects ``tdk-genesys-serial``.
    """
    explicit = str(config.get("model") or "").strip().lower()
    if explicit:
        return explicit

    # Ordered kind/driver rules; first match returns without *IDN?.
    early_rules: list[tuple[bool, Callable[[], str]]] = [
        (kind == "gnss", lambda: _resolve_gnss_model(transport)),
        (kind in _NO_PROBE_KINDS, lambda: "generic"),
    ]
    for matches, resolve in early_rules:
        if matches:
            return resolve()
    driver, _address = resolve_connection(kind, config)
    if driver in {"sim", "http"}:
        return "generic"

    asrl = _uses_asrl(kind, config)
    configured_addr = _configured_device_address(config)
    idn, bare, discovered_addr = probe_identity(
        transport,
        asrl=asrl,
        log_kind=kind,
        device_address=configured_addr,
    )
    if discovered_addr is not None and "device_address" not in config:
        config["device_address"] = discovered_addr
    if idn is None:
        return "generic"
    return _model_from_idn(kind, idn, bare=bare)


def _uses_asrl(kind: str, config: dict[str, Any]) -> bool:
    from colosseum_equipment.transports.usbtmc import usbtmc_device_path

    driver, address = resolve_connection(kind, config)
    if driver == "serial":
        raw = str(config.get("port") or address or "")
        return usbtmc_device_path(raw) is None
    raw = str(config.get("resource") or address or "")
    if usbtmc_device_path(raw) is not None:
        return False
    resource = normalize_visa_resource(raw)
    return resource.upper().startswith("ASRL")


def _configured_device_address(config: dict[str, Any]) -> int | None:
    if "device_address" not in config:
        return None
    token = str(config["device_address"]).strip()
    if token == "" or not token.isdecimal():
        return None
    address = int(token)
    if not 0 <= address <= 30:
        return None
    return address


def flush_transport(transport: object) -> None:
    """Best-effort flush of a transport input buffer."""
    flush = getattr(transport, "flush", None)
    if callable(flush):
        with contextlib.suppress(Exception):
            flush()


def query_bare_idn(transport: object) -> str:
    """Send CR-terminated bare ``IDN?`` (Genesys native serial)."""
    flush_transport(transport)
    write_bytes = getattr(transport, "write_bytes", None)
    read_until = getattr(transport, "read_until", None)
    if callable(write_bytes) and callable(read_until):
        write_bytes(b"IDN?\r")
        return str(read_until(b"\r"))
    return str(transport.query("IDN?"))  # type: ignore[attr-defined]


def probe_genesys_serial_identity(
    transport: object,
    *,
    addresses: Sequence[int] | None = None,
    log_kind: str = "instrument",
) -> tuple[str, int] | None:
    """``ADR n`` then ``IDN?``; return ``(idn, address)`` for a Lambda GEN hit."""
    from colosseum_equipment.autoconfig.idn_registry import lambda_gen_identity

    write_bytes = getattr(transport, "write_bytes", None)
    read_until = getattr(transport, "read_until", None)
    if not callable(write_bytes) or not callable(read_until):
        return None
    candidates = tuple(addresses) if addresses is not None else _GENESYS_ADR_CANDIDATES
    for address in candidates:
        if not 0 <= int(address) <= 30:
            continue
        try:
            flush_transport(transport)
            write_bytes(f"ADR {int(address)}\r".encode("ascii"))
            ack = str(read_until(b"\r")).strip().upper()
            if ack != "OK":
                continue
            write_bytes(b"IDN?\r")
            idn = str(read_until(b"\r")).strip()
        except Exception as exc:
            _logger.warning(
                "equipment.%s Genesys ADR %s probe failed: %s",
                log_kind,
                address,
                exc,
            )
            continue
        if idn and lambda_gen_identity(idn):
            return idn, int(address)
    return None


def probe_identity(
    transport: object,
    *,
    asrl: bool,
    log_kind: str = "instrument",
    device_address: int | None = None,
) -> tuple[str | None, bool, int | None]:
    """Return ``(idn, bare, device_address)`` for ASRL/COM then ``*IDN?``.

    On ASRL/COM, tries bare ``IDN?`` first. When that is not a Lambda GEN rating,
    tries ``ADR n`` (configured address, else default candidates) then ``IDN?``.
    ``bare`` is true when the reply matched a Lambda GEN rating via native serial.
    """
    if asrl:
        from colosseum_equipment.autoconfig.idn_registry import lambda_gen_identity

        try:
            bare = query_bare_idn(transport).strip()
        except Exception as bare_exc:
            _logger.warning("equipment.%s IDN? failed: %s", log_kind, bare_exc)
            bare = ""
        if bare and lambda_gen_identity(bare):
            return bare, True, None
        addresses = (device_address,) if device_address is not None else None
        genesys = probe_genesys_serial_identity(
            transport,
            addresses=addresses,
            log_kind=log_kind,
        )
        if genesys is not None:
            idn, addr = genesys
            return idn, True, addr
        flush_transport(transport)
    try:
        idn = str(transport.query("*IDN?")).strip()  # type: ignore[attr-defined]
    except Exception as exc:
        _logger.warning("equipment.%s *IDN? failed: %s", log_kind, exc)
        return None, False, None
    return idn, False, None
