"""I2C master APIs (``col.io.i2c``). Measurements use domain ``equipment`` in SQLite.

Configured IDs select bench TOML rows. Core records command and measurement
outcomes and applies its standard optional-failure handling. Unsupported model
operations raise ``EquipmentCapabilityError``; transport failures raise
``EquipmentConnectionError``.
Operation-specific validation and acquisition constraints are described below.
"""

from __future__ import annotations

from typing import Any

from colosseum.decorators import command, measurement
from colosseum.logging import get_logger

from colosseum_equipment.io.connections import get_backend

_logger = get_logger("colosseum.equipment")


@command
def configure(
    *,
    i2c_id: int,
    address: int | None = None,
    address_bits: int | None = None,
    clock_hz: int | None = None,
) -> dict[str, Any]:
    """Update I2C address, address width, and/or clock rate.

    :param i2c_id: Configured ``io.i2c`` ID.
    :param address: 7-bit or 10-bit slave address.
    :param address_bits: ``7`` or ``10``.
    :param clock_hz: SCL rate in hertz.
    :returns: Applied settings snapshot (clock_hz, address, pullup, …).

    :raises IoConfigError: Invalid address or clock for the configured model.
    """
    _logger.info("Configuring I2C %s address %s clock %s Hz", i2c_id, address, clock_hz)
    return dict(
        get_backend("i2c", i2c_id).configure(
            address=address,
            address_bits=address_bits,
            clock_hz=clock_hz,
        ),
    )


@command
def set_pullup(*, i2c_id: int, enabled: bool) -> None:
    """Enable or disable the adapter I2C pull-ups when supported.

    :param i2c_id: Configured ``io.i2c`` ID.
    :param enabled: ``True`` to enable pull-ups.
    """
    _logger.info("%s pull-ups on I2C %s", "Enabling" if enabled else "Disabling", i2c_id)
    get_backend("i2c", i2c_id).set_pullup(enabled)


@command
def write(*, i2c_id: int, data: bytes) -> None:
    """Write bytes to the configured I2C slave (empty ``data`` probes address ACK).

    :param i2c_id: Configured ``io.i2c`` ID.
    :param data: Bytes to write; ``b\"\"`` is an address-only ACK probe.
    """
    _logger.info("Writing %s bytes to I2C %s", len(data), i2c_id)
    get_backend("i2c", i2c_id).write(bytes(data))


@measurement
def read(*, i2c_id: int, nbytes: int, key: str) -> bytes:
    """Read bytes from the configured I2C slave.

    :param i2c_id: Configured ``io.i2c`` ID.
    :param nbytes: Number of bytes to read.
    :param key: Unique measurement key within domain ``equipment``.

    :returns: Received payload bytes.
    """
    _logger.info("Reading %s bytes from I2C %s", nbytes, i2c_id)
    _ = key
    return bytes(get_backend("i2c", i2c_id).read(nbytes))


@measurement
def write_read(*, i2c_id: int, write_data: bytes, read_nbytes: int, key: str) -> bytes:
    """Write then read (repeated START when the adapter supports it).

    :param i2c_id: Configured ``io.i2c`` ID.
    :param write_data: Bytes to write before the repeated START.
    :param read_nbytes: Number of bytes to read after the write.
    :param key: Unique measurement key within domain ``equipment``.

    :returns: Bytes read from the slave.
    """
    _logger.info(
        "Writing %s bytes and reading %s bytes on I2C %s",
        len(write_data),
        read_nbytes,
        i2c_id,
    )
    _ = key
    return bytes(get_backend("i2c", i2c_id).write_read(bytes(write_data), read_nbytes))
