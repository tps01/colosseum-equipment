"""Digital I/O APIs (``col.io.dio``). Measurements use domain ``equipment`` in SQLite.

Configured IDs select bench TOML rows. Core records command and measurement
outcomes and applies its standard optional-failure handling. Unsupported model
operations raise ``EquipmentCapabilityError``; transport failures raise
``EquipmentConnectionError``.
Operation-specific validation and acquisition constraints are described below.
"""

from __future__ import annotations

from typing import Any, Literal

from colosseum.decorators import command, measurement
from colosseum.logging import get_logger

from colosseum_equipment.io._pins import resolve_pin_line
from colosseum_equipment.io.connections import get_backend, get_config

_logger = get_logger("colosseum.equipment")

PullMode = Literal["up", "down", "float"]


@command
def configure(*, dio_id: int, direction: int, initial: int | None = None) -> dict[str, Any]:
    """Configure port direction bitmask.

    :param dio_id: Configured ``io.dio`` ID.
    :param direction: Bitmask of input (0) vs output (1) per line.
    :param initial: Optional output level applied before enabling outputs.

    :returns: Applied settings snapshot (direction, port_lines, initial_output, …).

    :raises IoConfigError: Invalid direction/value for the configured port.
    """
    _logger.info("Configuring DIO %s direction %s", dio_id, direction)
    return dict(get_backend("dio", dio_id).configure(direction, initial=initial))


@command
def configure_pin(*, dio_id: int, line: int, output: bool) -> None:
    """Configure one GPIO line as input or output.

    :param dio_id: Configured ``io.dio`` ID.
    :param line: Zero-based line index.
    :param output: ``True`` for output, ``False`` for input.

    :raises IoConfigError: Line out of range or invalid for this backend.
    """
    _logger.info("Configuring DIO %s line %s as %s", dio_id, line, "output" if output else "input")
    get_backend("dio", dio_id).configure_pin(line, output)


@command
def set_pull(*, dio_id: int, line: int, pull: PullMode) -> None:
    """Configure pull-up, pull-down, or floating on an input line when supported.

    :param dio_id: Configured ``io.dio`` ID.
    :param line: Zero-based line index.
    :param pull: ``up``, ``down``, or ``float``.
    """
    _logger.info("Setting pull on DIO %s line %s to %s", dio_id, line, pull)
    get_backend("dio", dio_id).set_pull(line, pull)


@command
def write_port(*, dio_id: int, value: int) -> None:
    """Write a port value.

    Bits outside ``port_lines`` or configured outputs are rejected (not masked).

    :param dio_id: Configured ``io.dio`` ID.
    :param value: Port output bitmask.

    :raises IoConfigError: Value has illegal bits for the current direction.
    """
    _logger.info("Writing %s to DIO %s port", value, dio_id)
    get_backend("dio", dio_id).write_port(value)


@measurement
def read_port(*, dio_id: int, key: str) -> int:
    """Read a full port value.

    :param dio_id: Configured ``io.dio`` ID.
    :param key: Unique measurement key within domain ``equipment``.

    :returns: Measured port bitmask as integer.
    """
    _logger.info("Reading DIO %s port", dio_id)
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

    :param dio_id: Configured ``io.dio`` ID.
    :param value: Line level.
    :param line: Line index (mutually exclusive with ``name``).
    :param name: Named pin from bench ``pins`` map (mutually exclusive with ``line``).

    :raises IoConfigError: Line is not an output or is out of range.
    """
    _logger.info(
        "Writing %s to DIO %s line %s",
        "high" if value else "low",
        dio_id,
        name if name is not None else line,
    )
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

    :param dio_id: Configured ``io.dio`` ID.
    :param key: Unique measurement key within domain ``equipment``.
    :param line: Line index (mutually exclusive with ``name``).
    :param name: Named pin from bench ``pins`` map (mutually exclusive with ``line``).

    :returns: Measured line level as bool.
    """
    _logger.info("Reading DIO %s line %s", dio_id, name if name is not None else line)
    _ = key
    resolved = resolve_pin_line(get_config("dio", dio_id), line=line, name=name)
    return bool(get_backend("dio", dio_id).read_pin(resolved))
