from __future__ import annotations

from typing import Any

from colosseum_equipment.io.backends.scpi.dio import ScpiDioBackend
from colosseum_equipment.io.backends.sim.dio import SimDioBackend
from colosseum_equipment.io.exceptions import IoConfigError

_GENERIC_DIO_DRIVERS = frozenset({"", "generic", "visa", "serial", "scpi"})


def _driver_name(config: dict[str, Any]) -> str:
    driver = config.get("driver")
    if driver in (None, ""):
        return ""
    return str(driver).lower()


def _port_lines(config: dict[str, Any]) -> int:
    raw = config.get("port_lines", 8)
    return int(raw)


def _direction(config: dict[str, Any]) -> int:
    raw = config.get("direction", 0)
    if raw in (None, ""):
        return 0
    return int(raw)


def open_dio_backend(dio_id: int, config: dict[str, Any]) -> Any:  # noqa: ANN401
    driver = _driver_name(config)
    if driver == "sim":
        return SimDioBackend.from_cache(
            dio_id=dio_id,
            port_lines=_port_lines(config),
            direction=_direction(config),
        )
    if driver == "ftdi-ft232h":
        from colosseum_equipment.io.backends.ftdi.dio import FtdiFt232hDioBackend

        return FtdiFt232hDioBackend(
            resource=str(config.get("resource") or ""),
            port_lines=_port_lines(config),
            direction=_direction(config),
        )
    if driver in _GENERIC_DIO_DRIVERS:
        return ScpiDioBackend.from_config(dio_id, config)
    raise IoConfigError(f"col.io dio: unsupported driver `{driver}`")


def open_backend(kind: str, resource_id: int, config: dict[str, Any]) -> Any:  # noqa: ANN401
    if kind == "dio":
        return open_dio_backend(resource_id, config)
    raise IoConfigError(f"unsupported io kind `{kind}`")
