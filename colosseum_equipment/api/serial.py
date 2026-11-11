"""Serial/COM port APIs (``col.equipment.serial``).

Configured IDs select bench TOML rows. Core records command and measurement
outcomes and applies its standard optional-failure handling. Unsupported model
operations raise ``EquipmentCapabilityError``; transport failures raise
``EquipmentConnectionError``.
Operation-specific validation and acquisition constraints are described below.

Commands with an ``EquipmentId`` parameter also accept ``"all"``: targets run
sequentially and failures aggregate. Measurements require numeric IDs.
"""

from __future__ import annotations

from colosseum.decorators import command, measurement
from colosseum.logging import get_logger

from colosseum_equipment.api._broadcast import EquipmentId, broadcastable, require_int_id
from colosseum_equipment.connections import get_transport
from colosseum_equipment.protocols.serial import SerialChannel
from colosseum_equipment.protocols.serial import strip_ansi as strip_ansi_text

_logger = get_logger("colosseum.equipment")


def _channel(serial_id: EquipmentId) -> SerialChannel:
    return SerialChannel(get_transport("serial", require_int_id(serial_id, kind="serial")))


@command
@broadcastable("serial", "serial_id")
def write(*, serial_id: EquipmentId, data: str, append_newline: str = "") -> None:
    """Write raw text to a configured serial port.

    :param serial_id: Configured ``equipment.serial`` ID.

    :param data: Payload to send (no line ending added unless ``append_newline`` is set).

    :param append_newline: Optional suffix (for example ``"\\r\\n"``).

    :raises EquipmentConnectionError: Port open or write failed.
    """
    _logger.info("Writing %s characters to serial %s", len(data), serial_id)
    _channel(serial_id).write(data, append_newline=append_newline)


@command
@broadcastable("serial", "serial_id")
def write_bytes(*, serial_id: EquipmentId, data: bytes) -> None:
    """Write raw bytes to a configured serial port.

    :param serial_id: Configured ``equipment.serial`` ID.

    :param data: Payload to send.

    :raises EquipmentConnectionError: Port open or write failed.
    """
    _logger.info("Writing %s bytes to serial %s", len(data), serial_id)
    _channel(serial_id).write_bytes(data)


@measurement
def read(*, serial_id: int, key: str, strip_ansi: bool = False) -> str:
    """Read one line from a configured serial port.

    :param serial_id: Configured ``equipment.serial`` ID.

    :param key: Unique measurement key within domain ``equipment``.

    :param strip_ansi: When ``True``, strip CSI ANSI escape sequences from the line.

    :returns: Received line text.
    :rtype: str

    :raises EquipmentConnectionError: Port read failed or timed out.
    """
    _logger.info("Reading a line from serial %s", serial_id)
    _ = key
    text = _channel(serial_id).read_line()
    return strip_ansi_text(text) if strip_ansi else text


@measurement
def read_bytes(*, serial_id: int, size: int, key: str) -> bytes:
    """Read up to ``size`` bytes from a configured serial port.

    :param serial_id: Configured ``equipment.serial`` ID.

    :param size: Maximum number of bytes to read.

    :param key: Unique measurement key within domain ``equipment``.

    :returns: Received bytes (may be shorter than ``size`` on timeout).
    :rtype: bytes

    :raises EquipmentConnectionError: Port read failed or timed out.
    """
    _logger.info("Reading up to %s bytes from serial %s", size, serial_id)
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

    :param serial_id: Configured ``equipment.serial`` ID.

    :param terminator: Stop reading when this substring is received.

    :param key: Unique measurement key within domain ``equipment``.

    :param strip_ansi: When ``True``, strip CSI ANSI escape sequences from the result.

    :returns: Received text including the terminator when present.
    :rtype: str

    :raises EquipmentConnectionError: Port read failed or timed out.
    """
    _logger.info("Reading serial %s until %s", serial_id, terminator)
    _ = key
    text = _channel(serial_id).read_until(terminator)
    return strip_ansi_text(text) if strip_ansi else text


@command
@broadcastable("serial", "serial_id")
def flush(*, serial_id: EquipmentId) -> None:
    """Discard pending RX/TX buffers on the serial port when supported.

    :param serial_id: Configured ``equipment.serial`` ID.

    :raises EquipmentConnectionError: Port flush failed.
    :raises EquipmentCapabilityError: Transport does not support flush.
    """
    _logger.info("Flushing serial %s", serial_id)
    _channel(serial_id).flush()


@measurement
def measure_in_waiting(*, serial_id: int, key: str) -> int:
    """Read the number of bytes waiting in the RX buffer.

    :param serial_id: Configured ``equipment.serial`` ID.

    :param key: Unique measurement key within domain ``equipment``.

    :returns: Byte count available to read.
    :rtype: int

    :raises EquipmentConnectionError: Port access failed.
    :raises EquipmentCapabilityError: Transport does not expose buffer depth.
    """
    _logger.info("Reading bytes waiting on serial %s", serial_id)
    _ = key
    return int(_channel(serial_id).measure_in_waiting())


@command
@broadcastable("serial", "serial_id")
def set_timeout_s(*, serial_id: EquipmentId, timeout_s: float) -> None:
    """Set the serial port read timeout in seconds.

    :param serial_id: Configured ``equipment.serial`` ID.

    :param timeout_s: Read timeout in seconds.

    :raises EquipmentConnectionError: Port access failed.
    :raises EquipmentCapabilityError: Transport does not support changing timeout.
    """
    _logger.info("Setting timeout on serial %s to %s s", serial_id, timeout_s)
    _channel(serial_id).set_timeout_s(timeout_s)
