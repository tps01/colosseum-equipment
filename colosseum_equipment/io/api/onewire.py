"""1-Wire master APIs (``col.io.onewire``). Measurements use domain ``equipment``."""

from __future__ import annotations

from colosseum.decorators import command, measurement

from colosseum_equipment.io.connections import get_backend


@command
def configure(*, onewire_id: int, speed: str | None = None) -> dict:
    """Configure 1-Wire bus speed (``standard`` or ``overdrive``).

    :returns: Applied settings snapshot (port, baudrate, speed, driver).
    """
    return dict(get_backend("onewire", onewire_id).configure(speed=speed))


@command
def reset(*, onewire_id: int, required: bool = False) -> bool:
    """Issue a 1-Wire reset and return whether a presence pulse was seen.

    :param required: When ``True``, raise if no slave presence is detected.
    """
    return bool(get_backend("onewire", onewire_id).reset(required=required))


@measurement
def search(*, onewire_id: int, key: str) -> list[str]:
    """Search the bus and return ROM ids as uppercase hex strings."""
    _ = key
    return list(get_backend("onewire", onewire_id).search())


@command
def select(*, onewire_id: int, rom: str | None = None) -> None:
    """Reset then MATCH ROM, or SKIP ROM when ``rom`` is omitted (single-drop)."""
    get_backend("onewire", onewire_id).select(rom)


@command
def write(*, onewire_id: int, data: bytes) -> None:
    """Write bytes on the 1-Wire bus (after ``select`` / ``reset`` as needed)."""
    get_backend("onewire", onewire_id).write(bytes(data))


@measurement
def read(*, onewire_id: int, nbytes: int, key: str) -> bytes:
    """Read ``nbytes`` from the 1-Wire bus."""
    _ = key
    return bytes(get_backend("onewire", onewire_id).read(nbytes))


@measurement
def write_read(*, onewire_id: int, write_data: bytes, read_nbytes: int, key: str) -> bytes:
    """Write then read on the 1-Wire bus."""
    _ = key
    return bytes(
        get_backend("onewire", onewire_id).write_read(bytes(write_data), read_nbytes),
    )
