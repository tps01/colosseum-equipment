"""Digital I/O APIs (``col.io.dio``). Measurements use domain ``equipment`` in SQLite."""

from __future__ import annotations

from typing import Literal

from colosseum.decorators import command, measurement

from colosseum_equipment.io._pins import resolve_pin_line
from colosseum_equipment.io.connections import get_backend, get_config

PullMode = Literal["up", "down", "float"]


@command
def configure(*, dio_id: int, direction: int) -> None:
    """Configure port direction bitmask.

    :param dio_id: Configured ``io.dio`` id from config TOML.
    :type dio_id: int
    :param direction: Bitmask of input (0) vs output (1) per line.
    :type direction: int

    :returns: None

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    get_backend("dio", dio_id).configure(direction)


@command
def configure_pin(*, dio_id: int, line: int, output: bool) -> None:
    """Configure one GPIO line as input or output.

    :param dio_id: Configured ``io.dio`` id from config TOML.
    :type dio_id: int
    :param line: Line index.
    :type line: int
    :param output: ``True`` for output, ``False`` for input.
    :type output: bool

    :returns: None

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    get_backend("dio", dio_id).configure_pin(line, output)


@command
def set_pull(*, dio_id: int, line: int, pull: PullMode) -> None:
    """Configure pull-up, pull-down, or floating on an input line when supported.

    :param dio_id: Configured ``io.dio`` id from config TOML.
    :type dio_id: int
    :param line: Line index.
    :type line: int
    :param pull: ``up``, ``down``, or ``float``.
    :type pull: str

    :returns: None

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    get_backend("dio", dio_id).set_pull(line, pull)


@command
def write_port(*, dio_id: int, value: int) -> None:
    """Write a port value.

    :param dio_id: Configured ``io.dio`` id from config TOML.
    :type dio_id: int
    :param value: Port output bitmask.
    :type value: int

    :returns: None

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    get_backend("dio", dio_id).write_port(value)


@measurement
def read_port(*, dio_id: int, key: str) -> int:
    """Read a full port value.

    :param dio_id: Configured ``io.dio`` id from config TOML.
    :type dio_id: int
    :param key: Unique measurement key within domain ``equipment`` and this command name.
        Must not collide with another instrument's measurement using the same command name.
    :type key: str

    :returns: Measured port bitmask as integer.
    :rtype: int

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
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

    :param dio_id: Configured ``io.dio`` id from config TOML.
    :type dio_id: int
    :param value: Line level.
    :type value: bool
    :param line: Line index (mutually exclusive with ``name``).
    :type line: int | None, optional
    :param name: Named pin from bench ``pins`` map (mutually exclusive with ``line``).
    :type name: str | None, optional

    :returns: None

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
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

    :param dio_id: Configured ``io.dio`` id from config TOML.
    :type dio_id: int
    :param key: Unique measurement key within domain ``equipment`` and this command name.
        Must not collide with another instrument's measurement using the same command name.
    :type key: str
    :param line: Line index (mutually exclusive with ``name``).
    :type line: int | None, optional
    :param name: Named pin from bench ``pins`` map (mutually exclusive with ``line``).
    :type name: str | None, optional

    :returns: Measured line level as bool.
    :rtype: bool

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    _ = key
    resolved = resolve_pin_line(get_config("dio", dio_id), line=line, name=name)
    return bool(get_backend("dio", dio_id).read_pin(resolved))
