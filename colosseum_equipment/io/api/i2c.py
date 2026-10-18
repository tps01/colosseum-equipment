"""I2C master APIs (``col.io.i2c``). Measurements use domain ``equipment`` in SQLite."""

from __future__ import annotations

from colosseum.decorators import command, measurement

from colosseum_equipment.io.connections import get_backend


@command
def configure(
    *,
    i2c_id: int,
    address: int | None = None,
    address_bits: int | None = None,
    clock_hz: int | None = None,
) -> None:
    """Update I2C address, address width, and/or clock rate.

    :param i2c_id: Configured ``io.i2c`` id from config TOML.
    :type i2c_id: int
    :param address: 7-bit or 10-bit slave address.
    :type address: int | None, optional
    :param address_bits: ``7`` or ``10``.
    :type address_bits: int | None, optional
    :param clock_hz: SCL rate in hertz.
    :type clock_hz: int | None, optional

    :returns: None

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    get_backend("i2c", i2c_id).configure(
        address=address, address_bits=address_bits, clock_hz=clock_hz,
    )


@command
def set_pullup(*, i2c_id: int, enabled: bool) -> None:
    """Enable or disable the adapter I2C pull-ups when supported.

    :param i2c_id: Configured ``io.i2c`` id from config TOML.
    :type i2c_id: int
    :param enabled: ``True`` to enable pull-ups.
    :type enabled: bool

    :returns: None
    """
    get_backend("i2c", i2c_id).set_pullup(enabled)


@command
def write(*, i2c_id: int, data: bytes) -> None:
    """Write bytes to the configured I2C slave (empty ``data`` probes address ACK).

    :param i2c_id: Configured ``io.i2c`` id from config TOML.
    :type i2c_id: int
    :param data: Bytes to write; ``b\"\"`` is an address-only ACK probe.
    :type data: bytes

    :returns: None
    """
    get_backend("i2c", i2c_id).write(bytes(data))


@measurement
def read(*, i2c_id: int, nbytes: int, key: str) -> bytes:
    """Read bytes from the configured I2C slave.

    :param i2c_id: Configured ``io.i2c`` id from config TOML.
    :type i2c_id: int
    :param nbytes: Number of bytes to read.
    :type nbytes: int
    :param key: Unique measurement key within domain ``equipment``.
    :type key: str

    :returns: Received payload bytes.
    :rtype: bytes
    """
    _ = key
    return bytes(get_backend("i2c", i2c_id).read(nbytes))


@measurement
def write_read(*, i2c_id: int, write_data: bytes, read_nbytes: int, key: str) -> bytes:
    """Write then read with a repeated START (combined transaction).

    :param i2c_id: Configured ``io.i2c`` id from config TOML.
    :type i2c_id: int
    :param write_data: Bytes written before the repeated START.
    :type write_data: bytes
    :param read_nbytes: Number of bytes to read after the repeated START.
    :type read_nbytes: int
    :param key: Unique measurement key within domain ``equipment``.
    :type key: str

    :returns: Received payload bytes.
    :rtype: bytes
    """
    _ = key
    return bytes(get_backend("i2c", i2c_id).write_read(bytes(write_data), read_nbytes))
