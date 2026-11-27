"""Static GPIO on the 16 AD3 DIO pins."""

from __future__ import annotations

import ctypes as ct
from contextlib import suppress
from typing import Any

from colosseum_equipment.exceptions import EquipmentCapabilityError, EquipmentConnectionError
from colosseum_equipment.io._dio_validate import require_line, require_mask_value, require_output_value
from colosseum_equipment.io.exceptions import IoConfigError, IoConnectionError
from colosseum_equipment.transports.digilent import DRIVER, DigilentConnection

_PORT_LINES = 16
_MASK = (1 << _PORT_LINES) - 1


class DigilentDio:
    def __init__(self, config: dict[str, Any]) -> None:
        if str(config.get("driver") or "").lower() != DRIVER:
            raise IoConfigError(f"Analog Discovery 3 DIO requires driver={DRIVER!r}")
        if config.get("port_lines", _PORT_LINES) != _PORT_LINES:
            raise IoConfigError("Analog Discovery 3 uses a 16-line DIO port")
        direction = require_mask_value(int(config.get("direction", 0)), _MASK, what="direction")
        initial = require_output_value(int(config.get("initial_output", 0)), direction=direction, mask=_MASK)
        try:
            self._device = DigilentConnection("dio", config)
        except EquipmentConnectionError as exc:
            raise IoConnectionError(str(exc)) from exc
        self._direction: int | None = None
        self._output = 0
        try:
            self.configure(direction, initial=initial)
        except IoConnectionError:
            with suppress(EquipmentConnectionError):
                self.close()
            raise

    def _call(self, function: str, *args: object) -> None:
        try:
            self._device.call("DigitalIO" + function, *args)
        except EquipmentConnectionError as exc:
            raise IoConnectionError(str(exc)) from exc

    def _apply(self, direction: int, output: int) -> None:
        old_direction = self._direction
        self._direction = None
        if old_direction is None:
            self._call("Reset")
            self._call("Configure")
        self._call("OutputSet", ct.c_uint(output))
        self._call("OutputEnableSet", ct.c_uint(direction))
        self._call("Configure")
        self._direction, self._output = direction, output

    def configure(self, direction: int, *, initial: int | None = None) -> dict[str, int | str]:
        require_mask_value(direction, _MASK, what="direction")
        with self._device.lock:
            output = (self._output & direction) if initial is None and self._direction is not None else (initial or 0)
            require_output_value(output, direction=direction, mask=_MASK)
            self._apply(direction, output)
            return {"driver": DRIVER, "port_lines": _PORT_LINES, "direction": direction, "initial_output": output}

    def _configured_direction(self) -> int:
        if self._direction is None:
            raise IoConfigError("Reconfigure the AD3 DIO direction before using this port")
        return self._direction

    def configure_pin(self, line: int, output: bool) -> None:
        require_line(line, _PORT_LINES)
        with self._device.lock:
            direction = self._configured_direction()
            bit = 1 << line
            self.configure(direction | bit if output else direction & ~bit)

    def write_port(self, value: int) -> None:
        with self._device.lock:
            direction = self._configured_direction()
            self._apply(direction, require_output_value(value, direction=direction, mask=_MASK))

    def write_pin(self, line: int, value: bool) -> None:
        require_line(line, _PORT_LINES)
        with self._device.lock:
            bit = 1 << line
            if not self._configured_direction() & bit:
                raise IoConfigError(f"line {line} is not configured as output")
            self.write_port(self._output | bit if value else self._output & ~bit)

    def read_port(self) -> int:
        with self._device.lock:
            value = ct.c_uint()
            self._call("Status")
            self._call("InputStatus", ct.byref(value))
            return value.value & _MASK

    def read_pin(self, line: int) -> bool:
        require_line(line, _PORT_LINES)
        return bool(self.read_port() & (1 << line))

    def set_pull(self, line: int, pull: str) -> None:
        require_line(line, _PORT_LINES)
        raise EquipmentCapabilityError(f"AD3 DIO does not support per-pin pull configuration ({pull!r})")

    def close(self) -> None:
        self._device.close()
