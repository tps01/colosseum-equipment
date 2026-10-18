"""Raw serial/COM port helpers for ``col.equipment.serial``."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from colosseum_equipment.exceptions import EquipmentCapabilityError

if TYPE_CHECKING:
    from colosseum_equipment.transports.base import Transport

_ANSI_CSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def strip_ansi(text: str) -> str:
    """Remove CSI ANSI escape sequences from ``text``."""
    return _ANSI_CSI.sub("", text)


class SerialChannel:
    """Adapter over a cached transport for raw serial read/write."""

    def __init__(self, transport: Transport) -> None:
        self._transport = transport

    def write(self, data: str, *, append_newline: str = "") -> None:
        payload = f"{data}{append_newline}".encode("ascii")
        self.write_bytes(payload)

    def write_bytes(self, payload: bytes) -> None:
        write_bytes = getattr(self._transport, "write_bytes", None)
        if callable(write_bytes):
            write_bytes(payload)
            return
        self._transport.write(payload.decode("ascii", errors="replace"))

    def read_line(self) -> str:
        read_line = getattr(self._transport, "read_line", None)
        if callable(read_line):
            return str(read_line())
        return self._transport.read()

    def read_bytes(self, size: int) -> bytes:
        read_bytes = getattr(self._transport, "read_bytes", None)
        if callable(read_bytes):
            return bytes(read_bytes(size))
        text = self.read_line()
        encoded = text.encode("ascii", errors="replace")
        return encoded[:size]

    def read_until(self, terminator: str) -> str:
        read_until = getattr(self._transport, "read_until", None)
        if callable(read_until):
            return str(read_until(terminator))
        buffer = self.read_line()
        if terminator in buffer:
            return buffer
        return buffer

    def flush(self) -> None:
        flush = getattr(self._transport, "flush", None)
        if callable(flush):
            flush()
            return
        raise EquipmentCapabilityError("flush is not supported by this serial transport")

    def measure_in_waiting(self) -> int:
        in_waiting = getattr(self._transport, "in_waiting", None)
        if callable(in_waiting):
            return int(in_waiting())
        raise EquipmentCapabilityError(
            "measure_in_waiting is not supported by this serial transport",
        )

    def set_timeout_s(self, timeout_s: float) -> None:
        setter = getattr(self._transport, "set_timeout_s", None)
        if callable(setter):
            setter(timeout_s)
            return
        raise EquipmentCapabilityError(
            "set_timeout_s is not supported by this serial transport",
        )
