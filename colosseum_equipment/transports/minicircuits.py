"""RCM/ZTM transports: C2 programming guide §§5.2/5.4/7.1–7.2.

https://minicircuits.com/softwaredownload/Prog_Manual-Multi_Attenuators.pdf
The instrument driver owns block/channel commands; transports own framing.
"""

from __future__ import annotations

import math
import socket
import threading
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, NoReturn
from urllib.parse import quote, urlsplit

from colosseum_equipment.exceptions import (
    EquipmentCapabilityError,
    EquipmentConnectionError,
    EquipmentResponseError,
    EquipmentTimeoutError,
)
from colosseum_equipment.transports.http import HttpTransport

if TYPE_CHECKING:
    from colosseum_equipment.transports.base import Transport

_VENDOR_ID, _PRODUCT_ID = 0x20CE, 0x22
_REPORT_BYTES = 64
_SCPI_CODE = 42  # C2 accepts interrupt command 1 or 42 for SCPI.
_MAX_LINE_BYTES = 4096
_IAC, _WILL, _WONT, _DO, _DONT, _SB, _SE = 255, 251, 252, 253, 254, 250, 240


def _command(data: str) -> bytes:
    if not data or not data.isascii() or any(ord(c) < 32 or ord(c) == 127 or c == ";" for c in data):
        raise ValueError("RCM/ZTM requires one printable ASCII command without terminators or semicolons")
    return data.encode("ascii")


def _password(config: dict[str, Any]) -> str:
    if config.get("username"):
        raise ValueError("RCM/ZTM uses its rack password; HTTP Basic usernames are not supported")
    password = str(config.get("password") or "")
    if len(password) > 20 or not password.isascii() or any(ord(c) < 32 or ord(c) == 127 or c == ";" for c in password):
        raise ValueError("RCM/ZTM password must be at most 20 printable ASCII characters without semicolons")
    return password


class MiniCircuitsHttpTransport(HttpTransport):
    """Native PWD=...; URL prefix, rather than HTTP Basic authentication."""

    def __init__(self, resource: str, *, password: str, timeout: float) -> None:
        target = urlsplit(resource)
        if target.username or target.password or target.path not in {"", "/"} or target.query or target.fragment:
            raise ValueError("RCM/ZTM HTTP resource must be a rack origin URL, without credentials or command paths")
        super().__init__(resource, timeout=timeout)
        self._prefix = f"/PWD={quote(password, safe='')};" if password else "/"

    def query(self, data: str) -> str:
        _command(data)
        try:
            return super().query(self._prefix + data)
        except EquipmentTimeoutError:
            raise EquipmentTimeoutError("RCM/ZTM HTTP request timed out") from None
        except EquipmentConnectionError:
            # The base HTTP exception includes the URL, which may contain PWD.
            raise EquipmentConnectionError("RCM/ZTM HTTP request failed") from None

    def write(self, data: str) -> None:
        self.query(data)


class MiniCircuitsTelnetTransport:
    """One bounded, serialized CRLF transaction at a time; never auto-retry sets."""

    def __init__(self, resource: str, *, password: str, timeout: float) -> None:
        target = urlsplit(resource)
        if target.scheme != "telnet" or not target.hostname or target.username or target.password:
            raise ValueError("RCM/ZTM Telnet resource must be telnet://host[:port], without credentials")
        if target.path not in {"", "/"} or target.query or target.fragment:
            raise ValueError("RCM/ZTM Telnet resource cannot include a path or query")
        self._timeout = timeout
        self._lock = threading.RLock()
        self._closed = False
        try:
            self._socket = socket.create_connection((target.hostname, target.port or 23), timeout=timeout)
        except OSError:
            raise EquipmentConnectionError("cannot connect to RCM/ZTM Telnet endpoint") from None
        try:
            deadline = time.monotonic() + timeout
            if self._line(deadline, greeting=True):
                raise EquipmentResponseError("invalid RCM/ZTM Telnet greeting")
            if password:
                self._send(f"PWD={password};\r\n".encode("ascii"), deadline)
                if self._line(deadline) != "1 - Success":
                    raise EquipmentConnectionError("RCM/ZTM Telnet authentication failed")
        except TimeoutError:
            self.close()
            raise EquipmentTimeoutError("RCM/ZTM Telnet handshake timed out") from None
        except Exception:
            self.close()
            raise

    def _remaining(self, deadline: float) -> None:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("RCM/ZTM transaction deadline expired")
        self._socket.settimeout(remaining)

    def _send(self, data: bytes, deadline: float) -> None:
        self._remaining(deadline)
        self._socket.sendall(data)

    def _byte(self, deadline: float) -> int:
        self._remaining(deadline)
        data = self._socket.recv(1)
        if not data:
            raise EquipmentConnectionError("RCM/ZTM Telnet connection closed before a complete reply")
        return data[0]

    def _data_byte(self, deadline: float) -> int:
        while True:
            value = self._byte(deadline)
            if value != _IAC:
                return value
            verb = self._byte(deadline)
            if verb in {_WILL, _WONT, _DO, _DONT}:
                option = self._byte(deadline)
                if verb in {_WILL, _DO}:
                    self._send(bytes([_IAC, _DONT if verb == _WILL else _WONT, option]), deadline)
            elif verb == _SB:
                self._subnegotiation(deadline)
            elif verb not in {_SE, 241, 249}:  # End subnegotiation / NOP / Go Ahead.
                raise EquipmentResponseError("unsupported Telnet control in RCM/ZTM reply")

    def _subnegotiation(self, deadline: float) -> None:
        previous = 0
        for _ in range(_MAX_LINE_BYTES):
            value = self._byte(deadline)
            if previous == _IAC and value == _SE:
                return
            previous = value
        raise EquipmentResponseError("oversized Telnet subnegotiation")

    def _line(self, deadline: float, *, greeting: bool = False) -> str:
        data = bytearray()
        while len(data) < _MAX_LINE_BYTES:
            data.append(self._data_byte(deadline))
            if data[-1] == 10:
                if not greeting and not data.endswith(b"\r\n"):
                    raise EquipmentResponseError("RCM/ZTM Telnet reply lacks CRLF termination")
                try:
                    return data.rstrip(b"\r\n").decode("ascii")
                except UnicodeDecodeError:
                    raise EquipmentResponseError("non-ASCII RCM/ZTM Telnet reply") from None
        raise EquipmentResponseError("oversized RCM/ZTM Telnet reply")

    def query(self, data: str) -> str:
        command = _command(data)
        with self._lock:
            if self._closed:
                raise EquipmentConnectionError("RCM/ZTM Telnet session is closed")
            try:
                deadline = time.monotonic() + self._timeout
                self._send(command + b"\r\n", deadline)
                return self._line(deadline)
            except TimeoutError:
                self.close()
                raise EquipmentTimeoutError("RCM/ZTM Telnet transaction timed out; session closed") from None
            except OSError:
                self.close()
                raise EquipmentConnectionError("RCM/ZTM Telnet transaction failed; session closed") from None
            except (EquipmentConnectionError, EquipmentResponseError):
                self.close()
                raise

    def write(self, data: str) -> None:
        self.query(data)

    def read(self) -> NoReturn:
        raise EquipmentCapabilityError("RCM/ZTM Telnet uses complete query transactions")

    def close(self) -> None:
        with self._lock:
            if not self._closed:
                self._closed = True
                self._socket.close()


@dataclass
class _UsbSession:
    device: Any
    serial: str = ""
    references: int = 0
    closed: bool = False
    lock: Any = field(default_factory=threading.RLock)

    def close(self) -> None:
        if not self.closed:
            self.closed = True
            self.device.close()

    def query(self, command: bytes, timeout_ms: int) -> str:
        with self.lock:
            if self.closed:
                raise EquipmentConnectionError("RCM/ZTM USB session is closed; reopen all rows for this rack")
            try:
                # HIDAPI requires an initial report ID (0 for unnumbered reports).
                report = b"\0" + bytes([_SCPI_CODE]) + command.ljust(_REPORT_BYTES - 1, b"\0")
                if self.device.write(report) != len(report):
                    raise EquipmentConnectionError("short RCM/ZTM USB report write")
                reply = bytes(self.device.read(_REPORT_BYTES, timeout_ms))
                if not reply:
                    raise EquipmentTimeoutError("RCM/ZTM USB response timed out")
                if len(reply) != _REPORT_BYTES or reply[0] not in {1, _SCPI_CODE} or b"\0" not in reply[1:]:
                    raise EquipmentResponseError("invalid RCM/ZTM USB report size, code or terminator")
                try:
                    return reply[1:].split(b"\0", 1)[0].decode("ascii")
                except UnicodeDecodeError:
                    raise EquipmentResponseError("non-ASCII RCM/ZTM USB reply") from None
            except OSError:
                self.close()
                raise EquipmentConnectionError("RCM/ZTM USB report exchange failed") from None
            except (EquipmentConnectionError, EquipmentResponseError, EquipmentTimeoutError):
                self.close()
                raise


_usb_sessions: dict[bytes, _UsbSession] = {}
_usb_registry_lock = threading.Lock()


def _acquire_usb(resource: str, timeout_ms: int) -> tuple[bytes, _UsbSession]:
    import hid

    if not resource:
        raise ValueError("RCM/ZTM USB resource must be the rack serial number or 'auto'")
    paths = list(dict.fromkeys(item["path"] for item in hid.enumerate(_VENDOR_ID, _PRODUCT_ID)))
    if not paths or (resource == "auto" and len(paths) != 1):
        raise EquipmentConnectionError("RCM/ZTM USB auto requires exactly one rack; otherwise configure its serial")
    with _usb_registry_lock:
        for path in paths:
            session = _usb_sessions.get(path)
            if session is not None:
                if resource in {"auto", session.serial}:
                    if session.closed:
                        raise EquipmentConnectionError(
                            "RCM/ZTM USB session failed; close all rack rows before reopening",
                        )
                    session.references += 1
                    return path, session
                continue
            session = _UsbSession(hid.device())
            try:
                session.device.open_path(path)
                session.serial = session.query(b":SN?", timeout_ms).strip()
                if not session.serial or ":" in session.serial:
                    raise EquipmentResponseError("RCM/ZTM returned an invalid controller serial number")
                if resource in {"auto", session.serial}:
                    session.references = 1
                    _usb_sessions[path] = session
                    return path, session
            except Exception:
                session.close()
                raise
            session.close()
    raise EquipmentConnectionError("the configured RCM/ZTM USB serial number was not found")


class MiniCircuitsUsbTransport:
    """Native 64-byte reports; block rows share a locked, reference-counted handle."""

    def __init__(self, resource: str, *, timeout: float) -> None:
        self._timeout_ms = max(1, math.ceil(timeout * 1000))
        self._path, self._session = _acquire_usb(resource, self._timeout_ms)
        self._closed = False

    def query(self, data: str) -> str:
        command = _command(data)
        if len(command) > _REPORT_BYTES - 1:
            raise ValueError("RCM/ZTM USB command exceeds the 63-byte report capacity")
        if self._closed:
            raise EquipmentConnectionError("RCM/ZTM USB transport is closed")
        return self._session.query(command, self._timeout_ms)

    def write(self, data: str) -> None:
        self.query(data)

    def read(self) -> NoReturn:
        raise EquipmentCapabilityError("RCM/ZTM USB uses complete report transactions")

    def close(self) -> None:
        with _usb_registry_lock:
            if self._closed:
                return
            self._closed = True
            self._session.references -= 1
            if self._session.references == 0:
                del _usb_sessions[self._path]
                with self._session.lock:
                    self._session.close()


def open_rcm_transport(driver: str, config: dict[str, Any]) -> Transport:
    resource = str(config.get("resource") or "").strip()
    timeout = float(config.get("timeout", 5.0))
    if not math.isfinite(timeout) or not 0 < timeout <= 3600:
        raise ValueError("RCM/ZTM timeout must be finite and within (0, 3600] seconds")
    password = _password(config)
    if driver == "http":
        return MiniCircuitsHttpTransport(resource, password=password, timeout=timeout)
    if driver == "minicircuits-telnet":
        return MiniCircuitsTelnetTransport(resource, password=password, timeout=timeout)
    if driver == "minicircuits-usb":
        return MiniCircuitsUsbTransport(resource, timeout=timeout)
    raise EquipmentCapabilityError(
        "RCM/ZTM requires http, minicircuits-telnet or minicircuits-usb; USB HID is not a VISA endpoint",
    )
