"""TI USB2ANY SDK 2.7 Windows x86 ABI, loaded from a bench installation."""

from __future__ import annotations

import ctypes
import sys
from functools import lru_cache
from threading import RLock
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Sequence

from colosseum.logging import get_logger

from colosseum_equipment.io.backends._usb import (
    Session,
    UsbBackend,
    acquire,
    address,
    checked,
    count,
    size,
    spi_settings,
)
from colosseum_equipment.io.exceptions import IoConfigError, IoConnectionError

_logger = get_logger("colosseum.io")
# Receive timeout is DLL-global, so all devices using this SDK must serialize.
_runtime_lock = RLock()
_I2C_SPEEDS = {100_000: 0, 400_000: 1, 10_000: 2}
_SPI_SOURCE_HZ = 24_000_000


@lru_cache(maxsize=8)
def load_api(library: str) -> Any:  # noqa: ANN401
    if sys.platform != "win32" or ctypes.sizeof(ctypes.c_void_p) != 4:
        raise IoConnectionError(
            "USB2ANY SDK 2.7 requires Windows and 32-bit Python. "
            "Use a matching bench runtime; the x64 ABI is not qualified.",
        )
    try:
        lib = ctypes.WinDLL(library)
        integer, byte = ctypes.c_int32, ctypes.c_uint8
        buffer = ctypes.POINTER(byte)
        signatures: dict[str, Sequence[object]] = {
            "u2aOpen": [ctypes.c_char_p],
            "u2aClose": [integer],
            "u2aSuppressSplash": [integer],
            "u2aSetReceiveTimeout": [integer],
            "u2aPower_Enable": [integer] * 4,
            "u2aI2C_Control": [integer] * 4,
            "u2aI2C_RawWrite": [integer, ctypes.c_uint16, byte, buffer],
            "u2aI2C_RawRead": [integer, ctypes.c_uint16, byte, buffer],
            "u2aI2C_BlockWriteBlockRead": [
                integer, ctypes.c_uint16, byte, buffer, byte, buffer,
            ],
            "u2aSPI_Control": [integer] * 7 + [byte, byte],
            "u2aSPI_WriteAndRead": [integer, byte, buffer],
        }
        for name, args in signatures.items():
            # x86 stdcall uses four stack bytes even for Byte/UInt16 arguments.
            exported = f"_{name}@{4 * len(args)}"
            function = getattr(lib, exported, None)
            if function is None:
                function = getattr(lib, name)
            function.argtypes, function.restype = args, integer
            setattr(lib, name, function)
    except (OSError, AttributeError) as exc:
        raise IoConnectionError(
            f"Cannot load USB2ANY SDK 2.7 at {library!r}: {exc}",
        ) from exc
    return lib


def open_session(config: dict[str, Any]) -> Session:
    resource = str(config.get("resource") or "")
    if not resource or not resource.isascii():
        raise IoConfigError("USB2ANY resource must be its ASCII serial number")
    library = str(config.get("library") or "USB2ANY.dll")
    timeout = int(config.get("timeout_ms", 25))
    if not 2 <= timeout <= 200:
        raise IoConfigError("USB2ANY timeout_ms must be 2..200")
    if config.get("voltage") is not None and float(config["voltage"]) != 3.3:
        raise IoConfigError("USB2ANY backend supports fixed 3.3 V logic")
    power = bool(config.get("target_power", False))

    def _open() -> tuple[Any, int]:
        with _runtime_lock:
            api = load_api(library)
            checked(api.u2aSuppressSplash(1), "u2aSuppressSplash")
            handle = checked(api.u2aOpen(resource.encode("ascii")), "u2aOpen")
            if handle == 0:
                raise IoConnectionError("u2aOpen returned an invalid handle")
            try:
                checked(api.u2aPower_Enable(handle, int(power), 0, 0), "u2aPower_Enable")
            except Exception:
                api.u2aClose(handle)
                raise
            return api, handle

    def _close(api: Any, handle: int) -> None:  # noqa: ANN401
        try:
            checked(api.u2aPower_Enable(handle, 0, 0, 0), "u2aPower_Enable")
        finally:
            checked(api.u2aClose(handle), "u2aClose")

    session = acquire("ti-usb2any", resource, (library, power, timeout), _open, _close)
    session.lock = _runtime_lock
    return session


class Usb2AnyI2cBackend(UsbBackend):
    def __init__(self, config: dict[str, Any]) -> None:
        self._address = int(config.get("address", 0x50))
        self._bits = int(config.get("address_bits", 7))
        self._clock = int(config.get("clock_hz", 100_000))
        self._pullup = bool(config.get("pullup", True))
        self._validate(self._address, self._bits, self._clock)
        self._timeout = int(config.get("timeout_ms", 25))
        self._session = open_session(config)
        try:
            with self._session.lock:
                self._apply()
        except Exception:
            self.close()
            raise

    @staticmethod
    def _validate(addr: int, bits: int, clock: int) -> None:
        address(addr, bits)
        if clock not in _I2C_SPEEDS:
            raise IoConfigError("USB2ANY I2C clock_hz must be 10000, 100000, or 400000")

    def _apply(self) -> None:
        s = self.session()
        checked(s.api.u2aSetReceiveTimeout(self._timeout), "u2aSetReceiveTimeout")
        checked(s.api.u2aI2C_Control(
            s.handle, _I2C_SPEEDS[self._clock], int(self._bits == 10), int(self._pullup),
        ), "u2aI2C_Control")
        self.actual_clock_hz = self._clock

    def configure(
        self, *, address: int | None = None, address_bits: int | None = None,
        clock_hz: int | None = None,
    ) -> None:
        addr = self._address if address is None else address
        bits = self._bits if address_bits is None else address_bits
        clock = self._clock if clock_hz is None else clock_hz
        self._validate(addr, bits, clock)
        with self.session().lock:
            self._address, self._bits, self._clock = addr, bits, clock
            self._apply()

    def set_pullup(self, enabled: bool) -> None:
        with self.session().lock:
            self._pullup = enabled
            self._apply()

    def write(self, data: bytes) -> None:
        size(len(data), 255)
        buf = (ctypes.c_uint8 * max(1, len(data)))(*data)
        with self.session().lock:
            self._apply()
            s = self.session()
            checked(s.api.u2aI2C_RawWrite(s.handle, self._address, len(data), buf),
                    "u2aI2C_RawWrite")

    def read(self, nbytes: int) -> bytes:
        size(nbytes, 255)
        buf = (ctypes.c_uint8 * max(1, nbytes))()
        with self.session().lock:
            self._apply()
            s = self.session()
            count(s.api.u2aI2C_RawRead(s.handle, self._address, nbytes, buf),
                  nbytes, "u2aI2C_RawRead")
        return bytes(buf[:nbytes])

    def write_read(self, write_data: bytes, read_nbytes: int) -> bytes:
        size(len(write_data), 255)
        size(read_nbytes, 255)
        wbuf = (ctypes.c_uint8 * max(1, len(write_data)))(*write_data)
        rbuf = (ctypes.c_uint8 * max(1, read_nbytes))()
        with self.session().lock:
            self._apply()
            s = self.session()
            # SDK returns status zero, not a byte count, for this atomic operation.
            checked(s.api.u2aI2C_BlockWriteBlockRead(
                s.handle, self._address, len(write_data), wbuf, read_nbytes, rbuf,
            ), "u2aI2C_BlockWriteBlockRead")
        return bytes(rbuf[:read_nbytes])


class Usb2AnySpiBackend(UsbBackend):
    def __init__(self, config: dict[str, Any]) -> None:
        self._clock = int(config.get("clock_hz", 1_000_000))
        self._mode = int(config.get("mode", 0))
        self._validate(self._clock, self._mode, int(config.get("chip_select", 0)),
                       int(config.get("bits_per_word", 8)))
        self._timeout = int(config.get("timeout_ms", 25))
        self._session = open_session(config)
        try:
            with self._session.lock:
                self._apply()
        except Exception:
            self.close()
            raise

    @staticmethod
    def _validate(clock: int, mode: int, cs: int, bits: int) -> None:
        spi_settings(clock, mode, cs, bits, 0)
        if not 367 <= clock <= 8_000_000:
            raise IoConfigError("USB2ANY SPI clock_hz must be 367..8000000")

    def _apply(self) -> None:
        s = self.session()
        divider = (_SPI_SOURCE_HZ + self._clock - 1) // self._clock
        checked(s.api.u2aSetReceiveTimeout(self._timeout), "u2aSetReceiveTimeout")
        # TI's phase enum is inverted relative to conventional CPHA. Packet CS,
        # active low, MSB first, 8-bit words; only the dedicated CS is exposed.
        checked(s.api.u2aSPI_Control(
            s.handle, 1 - (self._mode & 1), self._mode >> 1, 1, 0, 1, 1,
            divider >> 8, divider & 0xFF,
        ), "u2aSPI_Control")
        self.actual_clock_hz = _SPI_SOURCE_HZ / divider
        _logger.debug("USB2ANY SPI actual clock %s Hz", self.actual_clock_hz)

    def configure(
        self, *, clock_hz: int | None = None, mode: int | None = None,
        chip_select: int | None = None, bits_per_word: int | None = None,
    ) -> None:
        clock = self._clock if clock_hz is None else clock_hz
        selected_mode = self._mode if mode is None else mode
        self._validate(clock, selected_mode, 0 if chip_select is None else chip_select,
                       8 if bits_per_word is None else bits_per_word)
        with self.session().lock:
            self._clock, self._mode = clock, selected_mode
            self._apply()

    def transfer(self, data: bytes) -> bytes:
        size(len(data), 255)
        buf = (ctypes.c_uint8 * max(1, len(data)))(*data)
        with self.session().lock:
            self._apply()
            s = self.session()
            if data:
                count(s.api.u2aSPI_WriteAndRead(s.handle, len(data), buf),
                      len(data), "u2aSPI_WriteAndRead")
        return bytes(buf[:len(data)])
