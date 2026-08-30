from __future__ import annotations

from typing import TYPE_CHECKING, Any

from colosseum.logging import get_logger

from colosseum_equipment.exceptions import EquipmentConnectionError
from colosseum_equipment.io.exceptions import IoConfigError, IoConnectionError
from colosseum_equipment.protocols.scpi import SCPIHelper
from colosseum_equipment.transports.factory import open_transport

if TYPE_CHECKING:
    from colosseum_equipment.transports.base import Transport

_logger = get_logger("colosseum.io")


def _line_mask(port_lines: int) -> int:
    if port_lines <= 0 or port_lines > 16:
        raise IoConfigError(f"port_lines must be 1..16, got {port_lines}")
    return (1 << port_lines) - 1


class ScpiDioBackend:
    """Digital I/O over an existing VISA/serial transport using SCPI-99 DIG commands."""

    def __init__(
        self,
        *,
        transport: Transport,
        port_lines: int,
        direction: int,
    ) -> None:
        self._mask = _line_mask(port_lines)
        self._direction = direction & self._mask
        self._output = 0
        self._scpi = SCPIHelper(transport)
        self.configure(self._direction)

    @classmethod
    def from_config(cls, dio_id: int, config: dict[str, Any]) -> ScpiDioBackend:
        resource = str(config.get("resource") or "").strip()
        port = str(config.get("port") or "").strip()
        driver = str(config.get("driver") or "visa").lower()
        if driver in ("generic", "scpi", ""):
            driver = "serial" if port and not resource else "visa"
        if driver == "serial":
            if not port and not resource:
                raise IoConfigError(
                    f"col.io dio id {dio_id} generic SCPI backend requires port= (serial) "
                    "or resource= (VISA)",
                )
            transport_config = {**config, "driver": "serial"}
            if not transport_config.get("port"):
                transport_config["port"] = resource
        elif driver == "visa":
            if not resource:
                raise IoConfigError(
                    f"col.io dio id {dio_id} generic SCPI backend requires resource= (VISA)",
                )
            transport_config = {**config, "driver": "visa"}
        else:
            raise IoConfigError(f"col.io dio id {dio_id}: unsupported SCPI transport `{driver}`")

        try:
            transport = open_transport("dio", dio_id, transport_config)
        except EquipmentConnectionError as exc:
            raise IoConnectionError(str(exc)) from exc
        _logger.debug("Opened SCPI DIO backend id=%s driver=%s", dio_id, driver)
        return cls(
            transport=transport,
            port_lines=int(config.get("port_lines", 8)),
            direction=int(config.get("direction") or 0),
        )

    def configure(self, direction: int) -> None:
        self._direction = direction & self._mask
        self._scpi.write(f"DIG:DIR {self._direction}")

    def write_port(self, value: int) -> None:
        self._output = value & self._direction & self._mask
        self._scpi.write(f"SOUR:DIG:DATA {self._output}")

    def read_port(self) -> int:
        return int(float(self._scpi.query("SENS:DIG:DATA?"))) & self._mask

    def write_pin(self, line: int, value: bool) -> None:
        bit = 1 << line
        if line < 0 or line >= self._mask.bit_length():
            raise IoConfigError(
                f"line {line} out of range for port_lines={self._mask.bit_length()}",
            )
        if not (self._direction & bit):
            raise IoConfigError(f"line {line} is not configured as output")
        if value:
            self._output |= bit
        else:
            self._output &= ~bit
        self._output &= self._mask
        self.write_port(self._output)

    def read_pin(self, line: int) -> bool:
        bit = 1 << line
        if line < 0 or line >= self._mask.bit_length():
            raise IoConfigError(
                f"line {line} out of range for port_lines={self._mask.bit_length()}",
            )
        return bool(self.read_port() & bit)

    def close(self) -> None:
        self._scpi._transport.close()
