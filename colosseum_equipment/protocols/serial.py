"""Raw serial/COM port helpers for ``col.equipment.serial``."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

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
        write_bytes = getattr(self._transport, "write_bytes", None)
        if callable(write_bytes):
            write_bytes(payload)
            return
        self._transport.write(data if append_newline else data)

    def read_line(self) -> str:
        read_line = getattr(self._transport, "read_line", None)
        if callable(read_line):
            return str(read_line())
        return self._transport.read()

    def read_until(self, terminator: str) -> str:
        read_until = getattr(self._transport, "read_until", None)
        if callable(read_until):
            return str(read_until(terminator))
        buffer = self.read_line()
        if terminator in buffer:
            return buffer
        return buffer
