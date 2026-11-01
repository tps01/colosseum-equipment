"""Serial/COM port APIs (``col.equipment.serial``)."""

from __future__ import annotations

from colosseum.decorators import command, measurement

from colosseum_equipment.api._broadcast import EquipmentId, broadcastable, require_int_id
from colosseum_equipment.connections import get_transport
from colosseum_equipment.protocols.serial import SerialChannel
from colosseum_equipment.protocols.serial import strip_ansi as strip_ansi_text


def _channel(serial_id: EquipmentId) -> SerialChannel:
    return SerialChannel(get_transport('serial', require_int_id(serial_id, kind='serial')))


@command
@broadcastable("serial", "serial_id")
def write(*, serial_id: EquipmentId, data: str, append_newline: str = "") -> None:
    """Write raw text to a configured serial port.

    :param serial_id: Configured ``equipment.serial`` id from config TOML.
    :type serial_id: int
    :param data: Payload to send (no line ending added unless ``append_newline`` is set).
    :type data: str
    :param append_newline: Optional suffix (for example ``"\\r\\n"``).
    :type append_newline: str, optional

    :returns: None

    :raises EquipmentConnectionError: Port open or write failed.
    """
    _channel(serial_id).write(data, append_newline=append_newline)


@command
@broadcastable("serial", "serial_id")
def write_bytes(*, serial_id: EquipmentId, data: bytes) -> None:
    """Write raw bytes to a configured serial port.

    :param serial_id: Configured ``equipment.serial`` id from config TOML.
    :type serial_id: int
    :param data: Payload to send.
    :type data: bytes

    :returns: None

    :raises EquipmentConnectionError: Port open or write failed.
    """
    _channel(serial_id).write_bytes(data)


@measurement
def read(*, serial_id: int, key: str, strip_ansi: bool = False) -> str:
    """Read one line from a configured serial port.

    :param serial_id: Configured ``equipment.serial`` id from config TOML.
    :type serial_id: int
    :param key: Unique measurement key within domain ``equipment``.
    :type key: str
    :param strip_ansi: When ``True``, strip CSI ANSI escape sequences from the line.
    :type strip_ansi: bool, optional

    :returns: Received line text.
    :rtype: str

    :raises EquipmentConnectionError: Port read failed or timed out.
    """
    _ = key
    text = _channel(serial_id).read_line()
    return strip_ansi_text(text) if strip_ansi else text


@measurement
def read_bytes(*, serial_id: int, size: int, key: str) -> bytes:
    """Read up to ``size`` bytes from a configured serial port.

    :param serial_id: Configured ``equipment.serial`` id from config TOML.
    :type serial_id: int
    :param size: Maximum number of bytes to read.
    :type size: int
    :param key: Unique measurement key within domain ``equipment``.
    :type key: str

    :returns: Received bytes (may be shorter than ``size`` on timeout).
    :rtype: bytes

    :raises EquipmentConnectionError: Port read failed or timed out.
    """
    _ = key
    return _channel(serial_id).read_bytes(size)


@measurement
def read_until(
    *,
    serial_id: int,
    terminator: str,
    key: str,
    strip_ansi: bool = False,
) -> str:
    """Read from a serial port until ``terminator`` appears in the response.

    :param serial_id: Configured ``equipment.serial`` id from config TOML.
    :type serial_id: int
    :param terminator: Stop reading when this substring is received.
    :type terminator: str
    :param key: Unique measurement key within domain ``equipment``.
    :type key: str
    :param strip_ansi: When ``True``, strip CSI ANSI escape sequences from the result.
    :type strip_ansi: bool, optional

    :returns: Received text including the terminator when present.
    :rtype: str

    :raises EquipmentConnectionError: Port read failed or timed out.
    """
    _ = key
    text = _channel(serial_id).read_until(terminator)
    return strip_ansi_text(text) if strip_ansi else text


@command
@broadcastable("serial", "serial_id")
def flush(*, serial_id: EquipmentId) -> None:
    """Discard pending RX/TX buffers on the serial port when supported.

    :param serial_id: Configured ``equipment.serial`` id from config TOML.
    :type serial_id: int

    :returns: None

    :raises EquipmentConnectionError: Port flush failed.
    :raises EquipmentCapabilityError: Transport does not support flush.
    """
    _channel(serial_id).flush()


@measurement
def measure_in_waiting(*, serial_id: int, key: str) -> int:
    """Read the number of bytes waiting in the RX buffer.

    :param serial_id: Configured ``equipment.serial`` id from config TOML.
    :type serial_id: int
    :param key: Unique measurement key within domain ``equipment``.
    :type key: str

    :returns: Byte count available to read.
    :rtype: int

    :raises EquipmentConnectionError: Port access failed.
    :raises EquipmentCapabilityError: Transport does not expose buffer depth.
    """
    _ = key
    return int(_channel(serial_id).measure_in_waiting())


@command
@broadcastable("serial", "serial_id")
def set_timeout_s(*, serial_id: EquipmentId, timeout_s: float) -> None:
    """Set the serial port read timeout in seconds.

    :param serial_id: Configured ``equipment.serial`` id from config TOML.
    :type serial_id: int
    :param timeout_s: Read timeout in seconds.
    :type timeout_s: float

    :returns: None

    :raises EquipmentConnectionError: Port access failed.
    :raises EquipmentCapabilityError: Transport does not support changing timeout.
    """
    _channel(serial_id).set_timeout_s(timeout_s)
