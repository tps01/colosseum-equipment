from __future__ import annotations

from typing import TYPE_CHECKING, Any

from colosseum.exceptions import ProceduralFault
from colosseum.logging import get_logger

from colosseum_equipment.exceptions import EquipmentConnectionError
from colosseum_equipment.transports.http import HttpTransport
from colosseum_equipment.transports.serial_transport import SerialTransport
from colosseum_equipment.transports.sim import SimTransport
from colosseum_equipment.transports.visa import VISATransport

if TYPE_CHECKING:
    from colosseum_equipment.transports.base import Transport

_logger = get_logger("colosseum.equipment")


def _open_failed(message: str) -> ProceduralFault:
    return ProceduralFault(message)


def _kind_address(kind: str) -> str | None:
    from colosseum_equipment.instruments.registry import kind_specs

    for spec in kind_specs():
        if spec.kind == kind:
            return spec.address
    return None


def resolve_connection(kind: str, config: dict[str, Any]) -> tuple[str, str]:
    """Return ``(driver, address)`` for a config row.

    An explicit ``driver`` wins. Otherwise a serial kind, or a ``port`` with no
    ``resource``, uses serial. An ``http`` kind (or an ``http(s)://`` resource)
    uses HTTP. Otherwise VISA. ``resource`` and ``port`` both remain valid
    address fields.
    """
    resource = str(config.get("resource") or "").strip()
    port = str(config.get("port") or "").strip()
    explicit = config.get("driver")
    kind_address = _kind_address(kind)
    if explicit not in (None, ""):
        driver = str(explicit).lower()
    elif kind == "serial" or kind_address == "serial" or (port and not resource):
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
            resource = str(config.get("resource") or "").strip()
            if not resource:
                raise _open_failed(f"equipment.{kind} id {equipment_id} missing `resource`")
            visa_backend = config.get("visa_backend")
            sim_definition = config.get("sim_definition")
            visa_library = config.get("visa_library")
            return VISATransport(
                resource,
                timeout=timeout,
                visa_backend=str(visa_backend) if visa_backend is not None else None,
                sim_definition=str(sim_definition) if sim_definition is not None else None,
                visa_library=str(visa_library) if visa_library is not None else None,
            )
        if driver == "serial":
            if not address:
                raise _open_failed(f"equipment.{kind} id {equipment_id} missing `port`")
            default_baud = 9600 if kind == "gnss" else 115200
            baudrate = int(config.get("baudrate", default_baud))
            return SerialTransport(address, baudrate=baudrate, timeout=timeout)
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
