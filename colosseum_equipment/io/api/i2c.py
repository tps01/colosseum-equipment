"""I2C master APIs (``col.io.i2c``). Measurements use domain ``equipment`` in SQLite."""

from __future__ import annotations

from typing import Any

from colosseum.decorators import command, measurement

from colosseum_equipment.io.connections import get_backend


@command
def configure(
    *,
    i2c_id: int,
    address: int | None = None,
    address_bits: int | None = None,
    clock_hz: int | None = None,
) -> dict[str, Any]:
    """Update I2C address, address width, and/or clock rate.

    :returns: Applied settings snapshot (clock_hz, address, pullup, …).

    :raises IoConnectionError: Transport or instrument connection failed.
    :raises IoConfigError: Invalid address or clock for the configured model.
    """
    return dict(
        get_backend("i2c", i2c_id).configure(
            address=address, address_bits=address_bits, clock_hz=clock_hz,
        ),
    )


@command
def set_pullup(*, i2c_id: int, enabled: bool) -> None:
    """Enable or disable the adapter I2C pull-ups when supported.

    :raises IoConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    get_backend("i2c", i2c_id).set_pullup(enabled)


@command
def write(*, i2c_id: int, data: bytes) -> None:
    """Write bytes to the configured I2C slave (empty ``data`` probes address ACK).

    :raises IoConnectionError: Transport or instrument connection failed.
    """
    get_backend("i2c", i2c_id).write(bytes(data))


@measurement
def read(*, i2c_id: int, nbytes: int, key: str) -> bytes:
    """Read bytes from the configured I2C slave.

    :raises IoConnectionError: Transport or instrument connection failed.
    """
    _ = key
    return bytes(get_backend("i2c", i2c_id).read(nbytes))


@measurement
def write_read(*, i2c_id: int, write_data: bytes, read_nbytes: int, key: str) -> bytes:
    """Write then read (repeated START when the adapter supports it).

    :raises IoConnectionError: Transport or instrument connection failed.
    """
    _ = key
    return bytes(get_backend("i2c", i2c_id).write_read(bytes(write_data), read_nbytes))
