from __future__ import annotations

from colosseum.context import get_context

from colosseum_equipment.io._dio_validate import (
    require_line,
    require_mask_value,
    require_output_value,
)
from colosseum_equipment.io.exceptions import IoConfigError

_SIM_STATE_KEY = "io:sim:state"


def _line_mask(port_lines: int) -> int:
    if port_lines <= 0 or port_lines > 16:
        raise IoConfigError(f"port_lines must be 1..16, got {port_lines}")
    return (1 << port_lines) - 1


def _state_key(dio_id: int) -> str:
    return f"dio:{dio_id}"


class SimDioBackend:
    """In-memory GPIO for offline runs and unit tests."""

    def __init__(
        self,
        *,
        dio_id: int,
        port_lines: int,
        direction: int,
        initial_output: int = 0,
    ) -> None:
        mask = _line_mask(port_lines)
        self._dio_id = dio_id
        self._port_lines = port_lines
        self._mask = mask
        self._direction = require_mask_value(direction, mask, what="direction")
        self._output = require_output_value(initial_output, direction=self._direction, mask=mask)
        self._input = 0
        self._pulls: dict[int, str] = {}

    def _persist(self) -> None:
        ctx = get_context()
        state = ctx.resource_cache.setdefault(_SIM_STATE_KEY, {})
        state[_state_key(self._dio_id)] = {
            "direction": self._direction,
            "output": self._output,
            "input": self._input,
            "mask": self._mask,
            "port_lines": self._port_lines,
            "pulls": dict(self._pulls),
        }

    @classmethod
    def from_cache(
        cls,
        *,
        dio_id: int,
        port_lines: int,
        direction: int,
        initial_output: int = 0,
    ) -> SimDioBackend:
        ctx = get_context()
        state = ctx.resource_cache.setdefault(_SIM_STATE_KEY, {})
        key = _state_key(dio_id)
        mask = _line_mask(port_lines)
        if key not in state:
            backend = cls(
                dio_id=dio_id,
                port_lines=port_lines,
                direction=direction,
                initial_output=initial_output,
            )
            backend._persist()
            return backend
        entry = state[key]
        backend = cls(
            dio_id=dio_id,
            port_lines=port_lines,
            direction=entry["direction"],
            initial_output=entry["output"],
        )
        backend._output = entry["output"] & mask
        backend._input = entry["input"] & mask
        backend._direction = entry["direction"] & mask
        backend._pulls = dict(entry.get("pulls", {}))
        return backend

    def configure(self, direction: int, *, initial: int | None = None) -> dict[str, int | str]:
        self._direction = require_mask_value(direction, self._mask, what="direction")
        if initial is not None:
            self._output = require_output_value(initial, direction=self._direction, mask=self._mask)
        else:
            self._output &= self._direction
        self._persist()
        return self.applied_settings()

    def applied_settings(self) -> dict[str, int | str]:
        return {
            "driver": "sim",
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
        self._persist()

    def set_pull(self, line: int, pull: str) -> None:
        require_line(line, self._port_lines)
        bit = 1 << line
        mode = pull.strip().lower()
        if mode not in ("up", "down", "float"):
            raise IoConfigError(f"pull must be up, down, or float; got {pull!r}")
        if self._direction & bit:
            raise IoConfigError(f"line {line} is configured as output")
        self._pulls[line] = mode
        self._persist()

    def write_port(self, value: int) -> None:
        self._output = require_output_value(value, direction=self._direction, mask=self._mask)
        self._persist()

    def read_port(self) -> int:
        return ((self._output & self._direction) | (self._input & ~self._direction)) & self._mask

    def write_pin(self, line: int, value: bool) -> None:
        require_line(line, self._port_lines)
        bit = 1 << line
        if not (self._direction & bit):
            raise IoConfigError(f"line {line} is not configured as output")
        if value:
            self._output |= bit
        else:
            self._output &= ~bit
        self._persist()

    def read_pin(self, line: int) -> bool:
        require_line(line, self._port_lines)
        return bool(self.read_port() & (1 << line))

    def close(self) -> None:
        return None
