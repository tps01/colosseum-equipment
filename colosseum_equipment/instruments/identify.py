"""Choose an instrument model when a config row omits ``model``."""

from __future__ import annotations

import contextlib
from typing import Any

from colosseum.logging import get_logger

from colosseum_equipment.autoconfig.idn_registry import classify_idn, lambda_gen_identity
from colosseum_equipment.instruments.registry import registered_models
from colosseum_equipment.transports.factory import resolve_connection
from colosseum_equipment.transports.visa import normalize_visa_resource

_logger = get_logger("colosseum.equipment")

_NO_PROBE_KINDS = frozenset({"serial", "gnss", "relay"})


def instrument_config(kind: str, config: dict[str, Any], model: str) -> dict[str, Any]:
    """Return a row copy whose ``model`` is the resolved slug."""
    resolved = dict(config)
    resolved["model"] = model
    if model == "tdk-genesys-serial" and kind == "psu":
        resolved["driver"] = "serial"
        if "baudrate" not in resolved:
            resolved["baudrate"] = 9600
    return resolved


def resolve_instrument_model(kind: str, config: dict[str, Any], transport: object) -> str:
    """Return the model slug for ``config``.

    A non-empty ``model`` wins and does not query. Otherwise a pyVISA instrument
    is classified from ``*IDN?`` within ``kind``, falling back to ``generic``.
    A COM or ASRL resource is probed with ``IDN?`` first. A Lambda GEN reply
    selects ``tdk-genesys-serial``.
    """
    explicit = str(config.get("model") or "").strip().lower()
    if explicit:
        return explicit
    if kind in _NO_PROBE_KINDS:
        return "generic"
    driver, _address = resolve_connection(kind, config)
    if driver in {"sim", "http"}:
        return "generic"

    idn, bare = probe_identity(transport, asrl=_uses_asrl(kind, config), log_kind=kind)
    if idn is None:
        return "generic"
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


def _uses_asrl(kind: str, config: dict[str, Any]) -> bool:
    driver, address = resolve_connection(kind, config)
    if driver == "serial":
        return True
    resource = normalize_visa_resource(str(config.get("resource") or address or ""))
    return resource.upper().startswith("ASRL")


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


def probe_identity(
    transport: object,
    *,
    asrl: bool,
    log_kind: str = "instrument",
) -> tuple[str | None, bool]:
    """Return ``(idn, bare)`` using bare ``IDN?`` on ASRL/COM then ``*IDN?``.

    When ``bare`` is true the reply matched a Lambda GEN rating via bare ``IDN?``.
    """
    if asrl:
        try:
            bare = query_bare_idn(transport).strip()
        except Exception as bare_exc:
            _logger.warning("equipment.%s IDN? failed: %s", log_kind, bare_exc)
            bare = ""
        if bare and lambda_gen_identity(bare):
            return bare, True
        flush_transport(transport)
    try:
        idn = str(transport.query("*IDN?")).strip()  # type: ignore[attr-defined]
    except Exception as exc:
        _logger.warning("equipment.%s *IDN? failed: %s", log_kind, exc)
        return None, False
    return idn, False
