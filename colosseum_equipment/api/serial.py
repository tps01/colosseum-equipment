"""Serial/COM port APIs (``col.equipment.serial``)."""

from __future__ import annotations

from colosseum.decorators import command, measurement

from colosseum_equipment.connections import get_transport
from colosseum_equipment.protocols.serial import SerialChannel
from colosseum_equipment.protocols.serial import strip_ansi as strip_ansi_text


def _channel(serial_id: int) -> SerialChannel:
    return SerialChannel(get_transport("serial", serial_id))


@command
def write(*, serial_id: int, data: str, append_newline: str = "") -> None:
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
