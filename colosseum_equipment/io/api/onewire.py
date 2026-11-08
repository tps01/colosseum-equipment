"""1-Wire master APIs (``col.io.onewire``). Measurements use domain ``equipment``."""

from __future__ import annotations

from typing import Any

from colosseum.decorators import command, measurement
from colosseum.logging import get_logger

from colosseum_equipment.io.connections import get_backend

_logger = get_logger("colosseum.equipment")


@command
def configure(*, onewire_id: int, speed: str | None = None) -> dict[str, Any]:
    """Configure 1-Wire bus speed (``standard`` or ``overdrive``).

    :param onewire_id: Configured ``io.onewire`` id from config TOML.
    :param speed: Optional bus speed (``standard`` or ``overdrive``).
    :returns: Applied settings snapshot (port, baudrate, speed, driver).
    """
    _logger.info("Configuring 1-Wire %s speed %s", onewire_id, speed)
    return dict(get_backend("onewire", onewire_id).configure(speed=speed))


@command
def reset(*, onewire_id: int, required: bool = False) -> bool:
    """Issue a 1-Wire reset and return whether a presence pulse was seen.

    :param onewire_id: Configured ``io.onewire`` id from config TOML.
    :param required: When ``True``, raise if no slave presence is detected.
    :returns: ``True`` when a presence pulse was detected.
    """
    _logger.info("Resetting 1-Wire %s", onewire_id)
    return bool(get_backend("onewire", onewire_id).reset(required=required))


@measurement
def search(*, onewire_id: int, key: str) -> list[str]:
    """Search the bus and return ROM ids as uppercase hex strings.

    :param onewire_id: Configured ``io.onewire`` id from config TOML.
    :param key: Unique measurement key within domain ``equipment``.
    :returns: List of 8-byte ROM ids as uppercase hex.
    """
    _logger.info("Searching 1-Wire %s for devices", onewire_id)
    _ = key
    return list(get_backend("onewire", onewire_id).search())


@command
def select(*, onewire_id: int, rom: str | None = None) -> None:
    """Reset then MATCH ROM, or SKIP ROM when ``rom`` is omitted (single-drop).

    :param onewire_id: Configured ``io.onewire`` id from config TOML.
    :param rom: Optional ROM hex string; omit for SKIP ROM on a single-drop bus.
    """
    _logger.info("Selecting 1-Wire %s ROM %s", onewire_id, rom)
    get_backend("onewire", onewire_id).select(rom)


@command
def write(*, onewire_id: int, data: bytes) -> None:
    """Write bytes on the 1-Wire bus (after ``select`` / ``reset`` as needed).

    :param onewire_id: Configured ``io.onewire`` id from config TOML.
    :param data: Bytes to write on the bus.
    """
    _logger.info("Writing %s bytes to 1-Wire %s", len(data), onewire_id)
    get_backend("onewire", onewire_id).write(bytes(data))


@measurement
def read(*, onewire_id: int, nbytes: int, key: str) -> bytes:
    """Read ``nbytes`` from the 1-Wire bus.

    :param onewire_id: Configured ``io.onewire`` id from config TOML.
    :param nbytes: Number of bytes to read.
    :param key: Unique measurement key within domain ``equipment``.
    :returns: Bytes read from the bus.
    """
    _logger.info("Reading %s bytes from 1-Wire %s", nbytes, onewire_id)
    _ = key
    return bytes(get_backend("onewire", onewire_id).read(nbytes))


@measurement
def write_read(*, onewire_id: int, write_data: bytes, read_nbytes: int, key: str) -> bytes:
    """Write then read on the 1-Wire bus.

    :param onewire_id: Configured ``io.onewire`` id from config TOML.
    :param write_data: Bytes to write before reading.
    :param read_nbytes: Number of bytes to read after the write.
    :param key: Unique measurement key within domain ``equipment``.
    :returns: Bytes read from the bus.
    """
    _logger.info(
        "Writing %s bytes and reading %s bytes on 1-Wire %s",
        len(write_data),
        read_nbytes,
        onewire_id,
    )
    _ = key
    return bytes(
        get_backend("onewire", onewire_id).write_read(bytes(write_data), read_nbytes),
    )
