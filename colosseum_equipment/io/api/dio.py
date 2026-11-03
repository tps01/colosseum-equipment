"""Digital I/O APIs (``col.io.dio``). Measurements use domain ``equipment`` in SQLite."""

from __future__ import annotations

from typing import Any, Literal

from colosseum.decorators import command, measurement

from colosseum_equipment.io._pins import resolve_pin_line
from colosseum_equipment.io.connections import get_backend, get_config

PullMode = Literal["up", "down", "float"]


@command
def configure(*, dio_id: int, direction: int, initial: int | None = None) -> dict[str, Any]:
    """Configure port direction bitmask.

    :param dio_id: Configured ``io.dio`` id from config TOML.
    :param direction: Bitmask of input (0) vs output (1) per line.
    :param initial: Optional output level applied before enabling outputs.

    :returns: Applied settings snapshot (direction, port_lines, initial_output, …).

    :raises IoConnectionError: Transport or instrument connection failed.
    :raises IoConfigError: Invalid direction/value for the configured port.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    return dict(get_backend("dio", dio_id).configure(direction, initial=initial))


@command
def configure_pin(*, dio_id: int, line: int, output: bool) -> None:
    """Configure one GPIO line as input or output.

    :raises IoConnectionError: Transport or instrument connection failed.
    :raises IoConfigError: Line out of range or invalid for this backend.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    get_backend("dio", dio_id).configure_pin(line, output)


@command
def set_pull(*, dio_id: int, line: int, pull: PullMode) -> None:
    """Configure pull-up, pull-down, or floating on an input line when supported.

    :raises IoConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    get_backend("dio", dio_id).set_pull(line, pull)


@command
def write_port(*, dio_id: int, value: int) -> None:
    """Write a port value.

    Bits outside ``port_lines`` or configured outputs are rejected (not masked).

    :raises IoConnectionError: Transport or instrument connection failed.
    :raises IoConfigError: Value has illegal bits for the current direction.
    """
    get_backend("dio", dio_id).write_port(value)


@measurement
def read_port(*, dio_id: int, key: str) -> int:
    """Read a full port value.

    :raises IoConnectionError: Transport or instrument connection failed.
    """
    _ = key
    return int(get_backend("dio", dio_id).read_port())


@command
def write_pin(
    *,
    dio_id: int,
    value: bool,
    line: int | None = None,
    name: str | None = None,
) -> None:
    """Write one GPIO line.

    :raises IoConnectionError: Transport or instrument connection failed.
    :raises IoConfigError: Line is not an output or is out of range.
    """
    resolved = resolve_pin_line(get_config("dio", dio_id), line=line, name=name)
    get_backend("dio", dio_id).write_pin(resolved, value)


@measurement
def read_pin(
    *,
    dio_id: int,
    key: str,
    line: int | None = None,
    name: str | None = None,
) -> bool:
    """Read one GPIO line.

    :raises IoConnectionError: Transport or instrument connection failed.
    """
    _ = key
    resolved = resolve_pin_line(get_config("dio", dio_id), line=line, name=name)
    return bool(get_backend("dio", dio_id).read_pin(resolved))
