from __future__ import annotations

from typing import Any

from colosseum.logging import get_logger

from colosseum_equipment.io.backends.scpi.dio import ScpiDioBackend
from colosseum_equipment.io.backends.sim.dio import SimDioBackend
from colosseum_equipment.io.exceptions import IoConfigError

_logger = get_logger("colosseum.io")
_SCPI_ALIASES = frozenset({"", "generic", "visa", "serial"})
_alias_warned: set[str] = set()


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


def _optional_str(config: dict[str, Any], key: str) -> str | None:
    raw = config.get(key)
    if raw in (None, ""):
        return None
    return str(raw)


def _optional_float(config: dict[str, Any], key: str) -> float | None:
    raw = config.get(key)
    if raw is None or raw == "":
        return None
    return float(raw)


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
    if driver == "ni-6501":
        from colosseum_equipment.io.backends.ni.dio_6501 import Ni6501DioBackend

        port_lines = _port_lines(config) if config.get("port_lines") not in (None, "") else 24
        if port_lines != 24:
            raise IoConfigError("ni-6501 port_lines must be 24")
        return Ni6501DioBackend(
            resource=str(config.get("resource") or ""),
            direction=_direction(config),
            drive=str(config.get("drive") or "open-drain"),
            library=_optional_str(config, "library"),
        )
    if driver == "ni-845x":
        from colosseum_equipment.io.backends.ni.dio_845x import Ni845xDioBackend

        port_lines = _port_lines(config) if config.get("port_lines") not in (None, "") else 8
        if port_lines != 8:
            raise IoConfigError("ni-845x port_lines must be 8")
        return Ni845xDioBackend(
            resource=str(config.get("resource") or ""),
            model=str(config.get("model") or ""),
            direction=_direction(config),
            drive=str(config.get("drive") or "push-pull"),
            voltage=_optional_float(config, "voltage"),
            library=_optional_str(config, "library"),
        )
    if driver == "scpi" or driver in _SCPI_ALIASES:
        if driver in _SCPI_ALIASES and driver not in _alias_warned:
            _alias_warned.add(driver)
            shown = driver or "omitted"
            _logger.warning("col.io dio driver `%s` is accepted; prefer driver = \"scpi\"", shown)
        return ScpiDioBackend.from_config(dio_id, config)
    raise IoConfigError(f"col.io dio: unsupported driver `{driver}`")


def open_i2c_backend(i2c_id: int, config: dict[str, Any]) -> Any:  # noqa: ANN401
    driver = _driver_name(config)
    if driver == "totalphase-aardvark":
        from colosseum_equipment.io.backends.totalphase import AardvarkI2cBackend

        return AardvarkI2cBackend(config)
    if driver == "ti-usb2any":
        from colosseum_equipment.io.backends.usb2any import Usb2AnyI2cBackend

        return Usb2AnyI2cBackend(config)
    if driver == "sim":
        from colosseum_equipment.io.backends.sim.i2c import SimI2cBackend

        return SimI2cBackend.from_cache(i2c_id=i2c_id, config=config)
    if driver == "ni-845x":
        from colosseum_equipment.io.backends.ni.i2c import Ni845xI2cBackend

        return Ni845xI2cBackend(
            resource=str(config.get("resource") or ""),
            model=str(config.get("model") or ""),
            voltage=_optional_float(config, "voltage"),
            clock_hz=int(config.get("clock_hz", 100_000)),
            address=int(config.get("address", 0x50)),
            address_bits=int(config.get("address_bits", 7)),
            pullup=bool(config.get("pullup", True)),
            library=_optional_str(config, "library"),
        )
    raise IoConfigError(f"col.io i2c: unsupported driver `{driver}`")


def open_spi_backend(spi_id: int, config: dict[str, Any]) -> Any:  # noqa: ANN401
    driver = _driver_name(config)
    if driver in ("totalphase-aardvark", "totalphase-cheetah"):
        from colosseum_equipment.io.backends.totalphase import TotalPhaseSpiBackend

        return TotalPhaseSpiBackend(config, cheetah=driver == "totalphase-cheetah")
    if driver == "ti-usb2any":
        from colosseum_equipment.io.backends.usb2any import Usb2AnySpiBackend

        return Usb2AnySpiBackend(config)
    if driver == "sim":
        from colosseum_equipment.io.backends.sim.spi import SimSpiBackend

        return SimSpiBackend.from_cache(spi_id=spi_id, config=config)
    if driver == "ni-845x":
        from colosseum_equipment.io.backends.ni.spi import Ni845xSpiBackend

        return Ni845xSpiBackend(
            resource=str(config.get("resource") or ""),
            model=str(config.get("model") or ""),
            voltage=_optional_float(config, "voltage"),
            clock_hz=int(config.get("clock_hz", 1_000_000)),
            mode=int(config.get("mode", 0)),
            chip_select=int(config.get("chip_select", 0)),
            bits_per_word=int(config.get("bits_per_word", 8)),
            library=_optional_str(config, "library"),
        )
    raise IoConfigError(f"col.io spi: unsupported driver `{driver}`")


def open_backend(kind: str, resource_id: int, config: dict[str, Any]) -> Any:  # noqa: ANN401
    if kind == "dio":
        return open_dio_backend(resource_id, config)
    if kind == "i2c":
        return open_i2c_backend(resource_id, config)
    if kind == "spi":
        return open_spi_backend(resource_id, config)
    if kind == "analyzer":
        if _driver_name(config) not in ("sim", "totalphase-beagle"):
            raise IoConfigError("analyzer driver must be sim or totalphase-beagle")
        from colosseum_equipment.io.backends.analyzer import AnalyzerBackend

        return AnalyzerBackend(config)
    raise IoConfigError(f"unsupported io kind `{kind}`")
