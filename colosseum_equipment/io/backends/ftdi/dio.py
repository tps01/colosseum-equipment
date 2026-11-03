from __future__ import annotations

from typing import Any

from pyftdi.gpio import GpioMpsseController

from colosseum_equipment.exceptions import EquipmentCapabilityError
from colosseum_equipment.io._dio_validate import (
    require_line,
    require_mask_value,
    require_output_value,
)
from colosseum_equipment.io.exceptions import IoConfigError, IoConnectionError


def _line_mask(port_lines: int) -> int:
    if port_lines not in (8, 16):
        raise IoConfigError("ftdi-ft232h port_lines must be 8 (ADBUS) or 16 (ADBUS+ACBUS)")
    return (1 << port_lines) - 1


class FtdiFt232hDioBackend:
    """FT232H GPIO via pyftdi ``GpioMpsseController`` (MPSSE mode)."""

    def __init__(
        self,
        *,
        resource: str,
        port_lines: int,
        direction: int,
        initial_output: int = 0,
    ) -> None:
        if not resource:
            raise IoConfigError(
                "ftdi-ft232h requires resource= (pyftdi URL, e.g. ftdi://ftdi:232h/1)",
            )
        self._port_lines = port_lines
        self._mask = _line_mask(port_lines)
        self._direction = require_mask_value(direction, self._mask, what="direction")
        self._output = require_output_value(
            initial_output, direction=self._direction, mask=self._mask,
        )
        self._gpio: Any = GpioMpsseController()
        try:
            # Direction map is applied after the desired output level is staged.
            self._gpio.configure(resource, direction=0)
            self._gpio.write(self._output)
            self._gpio.set_direction(self._mask, self._direction)
        except Exception as exc:
            raise IoConnectionError(f"failed to open FTDI GPIO at {resource!r}: {exc}") from exc

    def configure(self, direction: int, *, initial: int | None = None) -> dict[str, Any]:
        self._direction = require_mask_value(direction, self._mask, what="direction")
        if initial is not None:
            self._output = require_output_value(
                initial, direction=self._direction, mask=self._mask,
            )
        else:
            self._output &= self._direction
        self._gpio.write(self._output)
        self._gpio.set_direction(self._mask, self._direction)
        return self.applied_settings()

    def configure_pin(self, line: int, output: bool) -> None:
        require_line(line, self._port_lines)
        bit = 1 << line
        if output:
            self._direction |= bit
        else:
            self._direction &= ~bit
            self._output &= ~bit
        self._gpio.write(self._output)
        self._gpio.set_direction(self._mask, self._direction)

    def set_pull(self, line: int, pull: str) -> None:
        _ = line, pull
        raise EquipmentCapabilityError(
            "set_pull is not supported on ftdi-ft232h (no per-line pull control in pyftdi GPIO)",
        )

    def write_port(self, value: int) -> None:
        self._output = require_output_value(value, direction=self._direction, mask=self._mask)
        self._gpio.write(self._output)

    def read_port(self) -> int:
        return int(self._gpio.read()) & self._mask

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

    def applied_settings(self) -> dict[str, Any]:
        return {
            "driver": "ftdi-ft232h",
            "port_lines": self._port_lines,
            "direction": self._direction,
            "initial_output": self._output,
        }

    def close(self) -> None:
        close = getattr(self._gpio, "close", None)
        if callable(close):
            close()
