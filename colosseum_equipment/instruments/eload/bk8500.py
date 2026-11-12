"""Original 8500: 26-byte RS232 protocol, user manual 032218 pp.46–69.

https://www.bkprecision.com/knowledge/remote-communication/1/rs232-communication-instructions-for-85xx-series
"""

from __future__ import annotations

import math
import struct
import threading
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from colosseum_equipment.exceptions import EquipmentCapabilityError, EquipmentResponseError
from colosseum_equipment.instruments._capabilities import supported_commands
from colosseum_equipment.instruments._channels import resolve_channel_count
from colosseum_equipment.instruments.eload.generic import GenericEload

if TYPE_CHECKING:
    from colosseum_equipment.transports.base import Transport

_PACKET_SIZE = 26
_ACK = 0x12
_SUCCESS = 0x80
_MEASURE = 0x5F


@supported_commands(
    "set_mode", "set_current", "set_voltage", "set_power", "set_resistance",
    "engage", "disengage", "measure_voltage", "measure_current", "measure_power_w",
    "measure_resistance_ohm", "measure_input_state", "toggle_short",
)
class Bk8500Load(GenericEload):
    """Static load control; no ASCII fallback for this non-SCPI protocol."""

    def __init__(self, transport: Transport, config: dict[str, Any]) -> None:
        if resolve_channel_count(config) != 1:
            raise EquipmentCapabilityError("original B&K 8500 has one load input")
        self._address = int(config.get("device_address", 0))
        if not 0 <= self._address <= 0xFE:
            raise ValueError("device_address must be within 0..254")
        writer = getattr(transport, "write_bytes", None)
        reader = getattr(transport, "read_bytes", None)
        if not callable(writer) or not callable(reader):
            raise EquipmentCapabilityError("B&K 8500 requires raw byte write/read transport")
        self._write: Callable[[bytes], None] = writer
        self._read: Callable[[int], bytes] = reader
        self._exchange_lock = threading.Lock()
        super().__init__(transport, config)
        self._exchange(0x20, b"\x01")  # Remote control, without enabling the input.

    def _exchange(self, command: int, data: bytes = b"", *, query: bool = False) -> bytes:
        frame = bytes([0xAA, self._address, command]) + data.ljust(22, b"\0")
        frame += bytes([sum(frame) & 0xFF])
        with self._exchange_lock:
            self._write(frame)
            reply = bytearray()
            while len(reply) < _PACKET_SIZE:
                chunk = self._read(_PACKET_SIZE - len(reply))
                if not chunk:
                    raise EquipmentResponseError("truncated B&K 8500 reply")
                reply.extend(chunk)
        if (
            len(reply) != _PACKET_SIZE or reply[:2] != frame[:2]
            or sum(reply[:-1]) & 0xFF != reply[-1]
        ):
            raise EquipmentResponseError("invalid B&K 8500 packet length/header/address/checksum")
        if reply[2] == _ACK:
            if reply[3] != _SUCCESS:
                raise EquipmentResponseError(f"B&K 8500 command {command:#x} failed: status {reply[3]:#x}")
            if query:
                raise EquipmentResponseError("B&K 8500 returned status instead of measurement data")
        elif not query or reply[2] != command:
            raise EquipmentResponseError("unexpected B&K 8500 response command")
        return bytes(reply)

    def _set_value(self, command: int, value: float, scale: int, channel: int) -> None:
        self._require_channel(channel)
        if not math.isfinite(value) or not 0 <= value * scale <= 0xFFFFFFFF:
            raise ValueError("load setting must be finite, nonnegative and fit the protocol range")
        self._exchange(command, struct.pack("<I", round(value * scale)))

    def set_mode(self, mode: str, *, channel: int = 1) -> None:
        self._require_channel(channel)
        modes = {"CC": 0, "CV": 1, "CW": 2, "CP": 2, "CR": 3}
        token = mode.strip().upper()
        if token not in modes:
            raise EquipmentCapabilityError(f"unsupported B&K 8500 mode {mode!r}")
        self._exchange(0x5D, b"\0")  # Fixed rather than transient/list/battery function.
        self._exchange(0x28, bytes([modes[token]]))

    def set_current(self, current: float, *, channel: int = 1) -> None:
        self._set_value(0x2A, current, 10000, channel)  # 0.1 mA units.

    def set_voltage(self, voltage: float, *, channel: int = 1) -> None:
        self._set_value(0x2C, voltage, 1000, channel)  # mV units.

    def set_power(self, power: float, *, channel: int = 1) -> None:
        self._set_value(0x2E, power, 1000, channel)  # mW units.

    def set_resistance(self, resistance: float, *, channel: int = 1) -> None:
        self._set_value(0x30, resistance, 1000, channel)  # milliohm units.

    def engage(self, *, channel: int = 1) -> None:
        self._require_channel(channel)
        self._exchange(0x21, b"\x01")

    def disengage(self, *, channel: int = 1) -> None:
        self._require_channel(channel)
        self._exchange(0x21, b"\0")

    def _measurement(self, channel: int) -> bytes:
        self._require_channel(channel)
        return self._exchange(_MEASURE, query=True)

    def measure_voltage(self, *, channel: int = 1) -> float:
        return float(struct.unpack_from("<I", self._measurement(channel), 3)[0]) / 1000.0

    def measure_current(self, *, channel: int = 1) -> float:
        return float(struct.unpack_from("<I", self._measurement(channel), 7)[0]) / 10000.0

    def measure_power_w(self, *, channel: int = 1) -> float:
        return float(struct.unpack_from("<I", self._measurement(channel), 11)[0]) / 1000.0

    def measure_resistance_ohm(self, *, channel: int = 1) -> float:
        voltage, current = struct.unpack_from("<II", self._measurement(channel), 3)
        return voltage * 10.0 / current if current else float("inf")

    def measure_input_state(self, *, channel: int = 1) -> bool:
        return bool(self._measurement(channel)[15] & (1 << 3))

    def toggle_short(self, enabled: bool, *, channel: int = 1) -> None:
        self._require_channel(channel)
        self._exchange(0x5D, bytes([int(bool(enabled))]))  # SHORT / FIXED function.
