from __future__ import annotations

from typing import TYPE_CHECKING, Any

from colosseum.logging import get_logger

from colosseum_equipment.exceptions import EquipmentConnectionError
from colosseum_equipment.io._dio_validate import (
    require_line,
    require_mask_value,
    require_output_value,
)
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
        initial_output: int = 0,
    ) -> None:
        self._port_lines = port_lines
        self._mask = _line_mask(port_lines)
        self._direction = require_mask_value(direction, self._mask, what="direction")
        self._output = require_output_value(
            initial_output, direction=self._direction, mask=self._mask,
        )
        self._scpi = SCPIHelper(transport)
        # Establish desired level before enabling outputs where the instrument allows.
        self._write_checked(f"SOUR:DIG:DATA {self._output}")
        self._write_checked(f"DIG:DIR {self._direction}")

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
                f"col.io dio id {dio_id} SCPI backend requires port= (serial COM, "
                "preferred for first-contact trials) or resource= (VISA USB/GPIB)",
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
            initial_output=int(config.get("initial_output") or 0),
        )

    def _write_checked(self, command: str) -> None:
        self._scpi.write(command)
        try:
            err = self._scpi.query("SYST:ERR?")
        except Exception as exc:  # noqa: BLE001
            raise IoConnectionError(f"SCPI SYST:ERR? failed after {command!r}: {exc}") from exc
        text = err.strip()
        code = text.split(",", 1)[0].strip()
        if code not in {"0", "+0"}:
            raise IoConnectionError(f"SCPI rejected {command!r}: {text}")

    def configure(self, direction: int, *, initial: int | None = None) -> dict[str, Any]:
        self._direction = require_mask_value(direction, self._mask, what="direction")
        if initial is not None:
            self._output = require_output_value(
                initial, direction=self._direction, mask=self._mask,
            )
            self._write_checked(f"SOUR:DIG:DATA {self._output}")
        else:
            self._output &= self._direction
        self._write_checked(f"DIG:DIR {self._direction}")
        return self.applied_settings()

    def applied_settings(self) -> dict[str, Any]:
        return {
            "driver": "scpi",
            "port_lines": self._port_lines,
            "direction": self._direction,
            "initial_output": self._output,
        }

    def configure_pin(self, line: int, output: bool) -> None:
        require_line(line, self._port_lines)
        bit = 1 << line
        if output:
            self._direction |= bit
        else:
            self._direction &= ~bit
            self._output &= ~bit
        self.configure(self._direction)

    def set_pull(self, line: int, pull: str) -> None:
        require_line(line, self._port_lines)
        mode = pull.strip().lower()
        mapping = {"up": "UP", "down": "DOWN", "float": "NONE"}
        if mode not in mapping:
            raise IoConfigError(f"pull must be up, down, or float; got {pull!r}")
        self._write_checked(f"DIG:PULL {line},{mapping[mode]}")

    def write_port(self, value: int) -> None:
        self._output = require_output_value(value, direction=self._direction, mask=self._mask)
        self._write_checked(f"SOUR:DIG:DATA {self._output}")

    def read_port(self) -> int:
        return int(float(self._scpi.query("SENS:DIG:DATA?"))) & self._mask

    def write_pin(self, line: int, value: bool) -> None:
        require_line(line, self._port_lines)
        bit = 1 << line
        if not (self._direction & bit):
            raise IoConfigError(f"line {line} is not configured as output")
        if value:
            self._output |= bit
        else:
            self._output &= ~bit
        self.write_port(self._output)

    def read_pin(self, line: int) -> bool:
        require_line(line, self._port_lines)
        return bool(self.read_port() & (1 << line))

    def close(self) -> None:
        self._scpi._transport.close()
