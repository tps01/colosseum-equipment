"""NI USB-8451 / USB-8452 DIO (one 8-line port) via NI-845x."""

from __future__ import annotations

from ctypes import byref, c_int32, c_uint8
from typing import Any

from colosseum_equipment.exceptions import EquipmentCapabilityError
from colosseum_equipment.io._dio_validate import (
    require_line,
    require_mask_value,
    require_output_value,
)
from colosseum_equipment.io.backends.ni import ni845x as api
from colosseum_equipment.io.backends.ni import session845x
from colosseum_equipment.io.backends.ni.models import resolve_voltage
from colosseum_equipment.io.exceptions import IoConfigError

_PORT = 0
_PORT_LINES = 8
_MASK = (1 << _PORT_LINES) - 1


class Ni845xDioBackend:
    """USB-845x general-purpose DIO port 0 (8 lines)."""

    def __init__(
        self,
        *,
        resource: str,
        model: str,
        direction: int = 0,
        drive: str = "push-pull",
        voltage: float | None = 3.3,
        library: str | None = None,
        initial_output: int = 0,
        timeout_ms: int | None = None,
    ) -> None:
        drive_key = drive.strip().lower().replace("_", "-")
        if drive_key in ("open-drain", "open-collector", "opendrain"):
            self._driver_type = api.kNi845xOpenDrain
            self._drive_name = "open-drain"
        elif drive_key in ("push-pull", "active-drive", "pushpull"):
            self._driver_type = api.kNi845xPushPull
            self._drive_name = "push-pull"
        else:
            raise IoConfigError(
                f"ni-845x drive must be open-drain or push-pull; got {drive!r}",
            )
        self._resource = resource
        self._model = model
        self._timeout_ms = timeout_ms
        self._voltage = resolve_voltage(model, voltage)
        self._session = session845x.acquire_session(
            resource=resource,
            voltage=self._voltage,
            library=library,
            timeout_ms=timeout_ms,
        )
        self._mask = _MASK
        self._direction = require_mask_value(direction, self._mask, what="direction")
        self._output = require_output_value(
            initial_output,
            direction=self._direction,
            mask=self._mask,
        )
        try:
            # Drive intended levels before enabling outputs.
            self._apply_output()
            self._apply_direction()
            self._apply_driver()
        except Exception:
            session845x.release_session(self._session)
            raise

    def _apply_direction(self) -> None:
        with session845x.locked(self._session) as session:
            api.check_status(
                session.lib,
                session.lib.ni845xDioSetPortLineDirectionMap(
                    session.handle,
                    _PORT,
                    self._direction,
                ),
                action="DioSetPortLineDirectionMap",
            )

    def _apply_driver(self) -> None:
        with session845x.locked(self._session) as session:
            api.check_status(
                session.lib,
                session.lib.ni845xDioSetDriverType(
                    session.handle,
                    _PORT,
                    self._driver_type,
                ),
                action="DioSetDriverType",
            )

    def _apply_output(self) -> None:
        with session845x.locked(self._session) as session:
            api.check_status(
                session.lib,
                session.lib.ni845xDioWritePort(session.handle, _PORT, self._output),
                action="DioWritePort",
            )

    def configure(self, direction: int, *, initial: int | None = None) -> dict[str, Any]:
        self._direction = require_mask_value(direction, self._mask, what="direction")
        if initial is not None:
            self._output = require_output_value(
                initial,
                direction=self._direction,
                mask=self._mask,
            )
        else:
            self._output &= self._direction
        self._apply_output()
        self._apply_direction()
        return self.applied_settings()

    def applied_settings(self) -> dict[str, Any]:
        return {
            "driver": "ni-845x",
            "resource": self._resource,
            "model": self._model,
            "port_lines": _PORT_LINES,
            "direction": self._direction,
            "initial_output": self._output,
            "drive": self._drive_name,
            "voltage": self._voltage,
            "timeout_ms": self._timeout_ms,
        }

    def configure_pin(self, line: int, output: bool) -> None:
        require_line(line, _PORT_LINES)
        bit = 1 << line
        if output:
            self._direction |= bit
        else:
            self._direction &= ~bit
            self._output &= ~bit
        self._apply_output()
        self._apply_direction()

    def set_pull(self, line: int, pull: str) -> None:
        _ = line, pull
        raise EquipmentCapabilityError(
            "set_pull is not supported on ni-845x DIO; " "use col.io.i2c.set_pullup for I2C bus pull-ups",
        )

    def write_port(self, value: int) -> None:
        self._output = require_output_value(value, direction=self._direction, mask=self._mask)
        self._apply_output()

    def read_port(self) -> int:
        value = c_uint8(0)
        with session845x.locked(self._session) as session:
            api.check_status(
                session.lib,
                session.lib.ni845xDioReadPort(session.handle, _PORT, byref(value)),
                action="DioReadPort",
            )
        return int(value.value) & self._mask

    def write_pin(self, line: int, value: bool) -> None:
        require_line(line, _PORT_LINES)
        bit = 1 << line
        if not (self._direction & bit):
            raise IoConfigError(f"line {line} is not configured as output")
        with session845x.locked(self._session) as session:
            api.check_status(
                session.lib,
                session.lib.ni845xDioWriteLine(
                    session.handle,
                    _PORT,
                    line,
                    1 if value else 0,
                ),
                action="DioWriteLine",
            )
        if value:
            self._output |= bit
        else:
            self._output &= ~bit

    def read_pin(self, line: int) -> bool:
        require_line(line, _PORT_LINES)
        value = c_int32(0)
        with session845x.locked(self._session) as session:
            api.check_status(
                session.lib,
                session.lib.ni845xDioReadLine(session.handle, _PORT, line, byref(value)),
                action="DioReadLine",
            )
        return bool(value.value)

    def close(self) -> None:
        try:
            self._direction = 0
            self._apply_direction()
        finally:
            session845x.release_session(self._session)
