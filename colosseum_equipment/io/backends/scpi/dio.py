from __future__ import annotations

from typing import TYPE_CHECKING, Any

from colosseum.logging import get_logger

from colosseum_equipment.exceptions import EquipmentConnectionError
from colosseum_equipment.io.exceptions import IoConfigError, IoConnectionError
from colosseum_equipment.protocols.scpi import SCPIHelper
from colosseum_equipment.transports.factory import open_transport, resolve_connection

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
        transport_config = dict(config)
        raw_driver = str(transport_config.get("driver") or "").strip().lower()
        if raw_driver in ("", "generic", "scpi"):
            transport_config.pop("driver", None)
        resolved_driver, address = resolve_connection("dio", transport_config)
        if resolved_driver not in ("visa", "serial"):
            raise IoConfigError(
                f"col.io dio id {dio_id}: unsupported SCPI transport `{resolved_driver}`",
            )
        if not address:
            raise IoConfigError(
                f"col.io dio id {dio_id} generic SCPI backend requires resource= (VISA) "
                "or port= (serial)",
            )
        transport_config["driver"] = resolved_driver
        if resolved_driver == "serial":
            transport_config["port"] = address
        else:
            transport_config["resource"] = address
        try:
            transport = open_transport("dio", dio_id, transport_config)
        except EquipmentConnectionError as exc:
            raise IoConnectionError(str(exc)) from exc
        _logger.debug("Opened SCPI DIO backend id=%s driver=%s", dio_id, resolved_driver)
        return cls(
            transport=transport,
            port_lines=int(config.get("port_lines", 8)),
            direction=int(config.get("direction") or 0),
        )

    def configure(self, direction: int) -> None:
        self._direction = direction & self._mask
        self._scpi.write(f"DIG:DIR {self._direction}")

    def configure_pin(self, line: int, output: bool) -> None:
        bit = 1 << line
        if line < 0 or line >= self._mask.bit_length():
            raise IoConfigError(
                f"line {line} out of range for port_lines={self._mask.bit_length()}",
            )
        if output:
            self._direction |= bit
        else:
            self._direction &= ~bit
        self._direction &= self._mask
        self.configure(self._direction)

    def set_pull(self, line: int, pull: str) -> None:
        if line < 0 or line >= self._mask.bit_length():
            raise IoConfigError(
                f"line {line} out of range for port_lines={self._mask.bit_length()}",
            )
        mode = pull.strip().lower()
        mapping = {"up": "UP", "down": "DOWN", "float": "NONE"}
        if mode not in mapping:
            raise IoConfigError(f"pull must be up, down, or float; got {pull!r}")
        self._scpi.write(f"DIG:PULL {line},{mapping[mode]}")

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
