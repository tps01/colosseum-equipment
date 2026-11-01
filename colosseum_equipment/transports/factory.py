from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from colosseum.exceptions import ProceduralFault
from colosseum.logging import get_logger

from colosseum_equipment.exceptions import EquipmentConnectionError
from colosseum_equipment.transports.http import HttpTransport
from colosseum_equipment.transports.sim import SimTransport

if TYPE_CHECKING:
    from colosseum_equipment.transports.base import Transport
    from colosseum_equipment.transports.visa import VISATransport

_logger = get_logger("colosseum.equipment")
_COM_PORT = re.compile(r"COM(\d+):?", re.IGNORECASE)


def _open_failed(message: str) -> ProceduralFault:
    return ProceduralFault(message)


def _kind_address(kind: str) -> str | None:
    from colosseum_equipment.instruments.registry import kind_address_mode

    return kind_address_mode(kind)


def resolve_connection(kind: str, config: dict[str, Any]) -> tuple[str, str]:
    """Return ``(driver, address)`` for a config row.

    An explicit ``driver`` wins. Serial kinds (or ``kind`` address mode
    ``serial``) use the serial/ASRL path. An ``http`` kind (or an
    ``http(s)://`` resource) uses HTTP. Otherwise VISA — a lone ``port`` does
    **not** flip a VISA kind to serial. ``driver=serial`` still opens through
    pyVISA. ``resource`` and ``port`` both remain valid address fields; open
    uses the resolved address.
    """
    resource = str(config.get("resource") or "").strip()
    port = str(config.get("port") or "").strip()
    explicit = config.get("driver")
    kind_address = _kind_address(kind)
    if explicit not in (None, ""):
        driver = str(explicit).lower()
    elif kind == "serial" or kind_address == "serial":
        driver = "serial"
    elif kind_address == "http" or resource.startswith(("http://", "https://")):
        driver = "http"
    else:
        driver = "visa"
        if port and resource:
            _logger.warning(
                "equipment.%s has port and resource with no driver; using VISA resource "
                "and ignoring port",
                kind,
            )
    address = port or resource if driver == "serial" else resource or port
    return driver, address


def _line_baud(kind: str, config: dict[str, Any], *, line_mode: bool, resource: str) -> int | None:
    asrl = resource.upper().startswith("ASRL")
    if not line_mode and not (asrl and "baudrate" in config):
        return None
    default_baud = 9600 if kind == "gnss" else 115200
    if line_mode:
        return int(config.get("baudrate", default_baud))
    return int(config["baudrate"])


def _open_visa(
    kind: str,
    equipment_id: int,
    config: dict[str, Any],
    *,
    raw_address: str,
    line_mode: bool,
    timeout: float,
    missing_field: str,
) -> VISATransport:
    from colosseum_equipment.transports.visa import VISATransport, normalize_visa_resource

    if not raw_address:
        raise _open_failed(f"equipment.{kind} id {equipment_id} missing `{missing_field}`")
    resource = normalize_visa_resource(raw_address)
    serial_line = line_mode or _COM_PORT.fullmatch(raw_address) is not None
    visa_backend = config.get("visa_backend")
    sim_definition = config.get("sim_definition")
    visa_library = config.get("visa_library")
    return VISATransport(
        resource,
        timeout=timeout,
        visa_backend=str(visa_backend) if visa_backend is not None else None,
        sim_definition=str(sim_definition) if sim_definition is not None else None,
        visa_library=str(visa_library) if visa_library is not None else None,
        baudrate=_line_baud(kind, config, line_mode=serial_line, resource=resource),
        line_mode=serial_line,
    )


def open_transport(kind: str, equipment_id: int, config: dict[str, Any]) -> Transport:
    driver, address = resolve_connection(kind, config)
    timeout = float(config.get("timeout", 5.0))
    _logger.debug(
        "open_transport kind=%s id=%s driver=%s timeout=%ss",
        kind,
        equipment_id,
        driver,
        timeout,
    )

    try:
        if driver == "sim":
            return SimTransport(kind, equipment_id, config)
        if driver == "visa":
            return _open_visa(
                kind,
                equipment_id,
                config,
                raw_address=address,
                line_mode=False,
                timeout=timeout,
                missing_field="resource",
            )
        if driver == "serial":
            return _open_visa(
                kind,
                equipment_id,
                config,
                raw_address=address,
                line_mode=True,
                timeout=timeout,
                missing_field="port",
            )
        if driver == "http":
            if not address:
                raise _open_failed(
                    f"equipment.{kind} id {equipment_id} missing `resource`",
                )
            return HttpTransport(
                address,
                timeout=timeout,
                username=str(config.get("username") or ""),
                password=str(config.get("password") or ""),
            )
        raise _open_failed(
            f"Unsupported driver `{driver}` for equipment.{kind} id {equipment_id}",
        )
    except ProceduralFault:
        raise
    except EquipmentConnectionError as exc:
        raise _open_failed(str(exc)) from exc
    except Exception as exc:
        raise _open_failed(
            f"Failed to open equipment.{kind} id {equipment_id}: {exc}",
        ) from exc
