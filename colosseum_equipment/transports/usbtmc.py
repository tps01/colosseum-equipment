"""Linux kernel USBTMC character-device transport."""

from __future__ import annotations

import os
import re
import select
import time
from pathlib import Path

from colosseum_equipment.exceptions import EquipmentConnectionError, EquipmentTimeoutError
from colosseum_equipment.transports.base import Transport

_USBTMC_DEV = re.compile(r"^/dev/usbtmc\d+$")


def usbtmc_device_path(address: str) -> str | None:
    """Return a ``/dev/usbtmcN`` path when ``address`` names one, else ``None``."""
    text = address.strip()
    if _USBTMC_DEV.fullmatch(text):
        return text
    if "::" not in text:
        return None
    head = text.split("::", 1)[0]
    if not head.upper().startswith("ASRL"):
        return None
    path = head[4:]
    if _USBTMC_DEV.fullmatch(path):
        return path
    return None


def list_usbtmc_devices() -> list[str]:
    """Return sorted existing ``/dev/usbtmc*`` character devices."""
    root = Path("/dev")
    if not root.is_dir():
        return []
    devices: list[str] = []
    for path in sorted(root.glob("usbtmc*")):
        text = str(path)
        if not _USBTMC_DEV.fullmatch(text):
            continue
        try:
            if path.is_char_device():
                devices.append(text)
        except OSError:
            continue
    return devices


class UsbtmcTransport(Transport):
    """SCPI over a kernel ``usbtmc`` character device."""

    def __init__(self, path: str, *, timeout: float = 5.0) -> None:
        device = usbtmc_device_path(path) or path.strip()
        if not _USBTMC_DEV.fullmatch(device):
            raise EquipmentConnectionError(f"not a USBTMC device path: {path!r}")
        self._path = device
        self._timeout = float(timeout)
        self._fd: int | None
        flags = os.O_RDWR
        nonblock = getattr(os, "O_NONBLOCK", 0)
        if nonblock:
            flags |= nonblock
        try:
            self._fd = os.open(device, flags)
        except OSError as exc:
            raise EquipmentConnectionError(f"Failed to open `{device}`: {exc}") from exc

    def _require_fd(self) -> int:
        if self._fd is None:
            raise EquipmentConnectionError(f"USBTMC device `{self._path}` is closed")
        return self._fd

    def write(self, data: str) -> None:
        payload = data if data.endswith("\n") else f"{data}\n"
        raw = payload.encode("ascii", errors="replace")
        try:
            os.write(self._require_fd(), raw)
        except OSError as exc:
            raise EquipmentConnectionError(f"USBTMC write failed on `{self._path}`: {exc}") from exc

    def read(self) -> str:
        fd = self._require_fd()
        deadline = time.monotonic() + self._timeout
        buffer = bytearray()
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise EquipmentTimeoutError(f"USBTMC read timed out on `{self._path}`")
            ready, _, _ = select.select([fd], [], [], remaining)
            if not ready:
                raise EquipmentTimeoutError(f"USBTMC read timed out on `{self._path}`")
            try:
                chunk = os.read(fd, 4096)
            except BlockingIOError:
                continue
            except OSError as exc:
                raise EquipmentConnectionError(
                    f"USBTMC read failed on `{self._path}`: {exc}",
                ) from exc
            if not chunk:
                break
            buffer.extend(chunk)
            if b"\n" in chunk or b"\r" in chunk:
                break
        return bytes(buffer).decode("ascii", errors="replace")

    def query(self, data: str) -> str:
        self.write(data)
        return self.read().strip()

    def close(self) -> None:
        fd = self._fd
        if fd is None:
            return
        self._fd = None
        try:
            os.close(fd)
        except OSError:
            return
