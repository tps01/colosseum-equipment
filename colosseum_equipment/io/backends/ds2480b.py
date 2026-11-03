"""Maxim DS9481R / DS2480B serial 1-Wire master (pyserial, no TMEX/OWFS).

Protocol reference: DS2480B datasheet + Application Note 192.
"""

from __future__ import annotations

import contextlib
import time
from typing import Any

import serial

from colosseum_equipment.io.exceptions import IoConfigError, IoConnectionError

# DS2480B mode / command bytes
_CMD_MODE = 0xE3
_DATA_MODE = 0xE1
_PULSE_TERM = 0xF1
# Single-bit communication commands (command mode)
_RESET_PULSE = 0xC1  # reset pulse at current speed, normal pullup
# Configuration: speed via PARAM codes
_CFG_SPEED_FLEX = 0x29  # flex/normal (standard) 1-Wire speed parameter write form
_CFG_SPEED_OD = 0x69  # overdrive


def _crc8(data: bytes) -> int:
    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0x8C
            else:
                crc >>= 1
            crc &= 0xFF
    return crc


def rom_to_hex(rom: bytes) -> str:
    if len(rom) != 8:
        raise IoConfigError(f"1-Wire ROM must be 8 bytes, got {len(rom)}")
    return rom.hex().upper()


def hex_to_rom(rom: str | bytes | None) -> bytes | None:
    if rom is None:
        return None
    if isinstance(rom, bytes):
        if len(rom) != 8:
            raise IoConfigError(f"1-Wire ROM must be 8 bytes, got {len(rom)}")
        return rom
    text = rom.strip().replace(" ", "").replace(":", "").replace("-", "")
    raw = bytes.fromhex(text)
    if len(raw) != 8:
        raise IoConfigError(f"1-Wire ROM must be 8 bytes, got {len(raw)}")
    return raw


class Ds2480bOneWireBackend:
    """DS9481R (and other DS2480B-emulating) serial 1-Wire adapter."""

    def __init__(
        self,
        *,
        port: str,
        baudrate: int = 9600,
        timeout_s: float = 1.0,
        speed: str = "standard",
        serial_factory: Any = None,  # noqa: ANN401
    ) -> None:
        if not port:
            raise IoConfigError(
                "maxim-ds9481r requires port= (serial COM from Device Manager, e.g. COM5)",
            )
        self._port = port
        self._baudrate = int(baudrate)
        self._timeout_s = float(timeout_s)
        self._speed = "standard"
        self._mode: str | None = None
        factory = serial_factory or serial.Serial
        try:
            self._ser = factory(
                port=port,
                baudrate=self._baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=self._timeout_s,
                write_timeout=self._timeout_s,
            )
        except Exception as exc:  # noqa: BLE001
            raise IoConnectionError(f"failed to open 1-Wire serial port {port!r}: {exc}") from exc
        try:
            self._detect()
            self.configure(speed=speed)
        except Exception:
            self.close()
            raise

    @classmethod
    def from_config(
        cls,
        config: dict[str, Any],
        *,
        serial_factory: Any = None,  # noqa: ANN401
    ) -> Ds2480bOneWireBackend:
        return cls(
            port=str(config.get("port") or ""),
            baudrate=int(config.get("baudrate", 9600)),
            timeout_s=float(config.get("timeout_s", 1.0)),
            speed=str(config.get("speed") or "standard"),
            serial_factory=serial_factory,
        )

    def close(self) -> None:
        ser = getattr(self, "_ser", None)
        if ser is not None:
            with contextlib.suppress(Exception):
                ser.close()
            self._ser = None

    def _write(self, data: bytes) -> None:
        assert self._ser is not None
        self._ser.write(data)
        self._ser.flush()

    def _read(self, n: int) -> bytes:
        assert self._ser is not None
        data = bytes(self._ser.read(n))
        if len(data) < n:
            raise IoConnectionError(
                f"1-Wire serial short read: expected {n} bytes, got {len(data)}",
            )
        return data

    def _drain(self) -> None:
        assert self._ser is not None
        time.sleep(0.01)
        try:
            waiting = self._ser.in_waiting
        except Exception:  # noqa: BLE001
            waiting = 0
        if waiting:
            self._ser.read(waiting)

    def _command_mode(self) -> None:
        if self._mode == "command":
            return
        self._write(bytes((_CMD_MODE,)))
        self._mode = "command"

    def _data_mode(self) -> None:
        if self._mode == "data":
            return
        self._write(bytes((_DATA_MODE,)))
        self._mode = "data"

    def _detect(self) -> None:
        """Synchronize with the DS2480B (AN192 detect sequence)."""
        self._drain()
        # Send a break-like sync: command-mode reset pulse after a short pause.
        self._mode = None
        self._write(bytes((_CMD_MODE, _RESET_PULSE)))
        self._mode = "command"
        try:
            reply = self._read(1)
        except IoConnectionError as exc:
            raise IoConnectionError(
                f"DS2480B detect failed on {self._port!r}; check Prolific COM driver "
                "and DS9481R connection",
            ) from exc
        # Presence coding: bit 0/1 of reply encode presence; accept any reply byte.
        _ = reply

    def configure(self, *, speed: str | None = None) -> dict[str, Any]:
        if speed is not None:
            name = speed.strip().lower()
            if name not in ("standard", "overdrive"):
                raise IoConfigError("onewire speed must be 'standard' or 'overdrive'")
            self._speed = name
        self._command_mode()
        cfg = _CFG_SPEED_OD if self._speed == "overdrive" else _CFG_SPEED_FLEX
        self._write(bytes((cfg,)))
        # Configuration commands echo the parameter byte.
        # Some firmwares omit the echo on first config after detect.
        with contextlib.suppress(IoConnectionError):
            self._read(1)
        return {
            "port": self._port,
            "baudrate": self._baudrate,
            "timeout_s": self._timeout_s,
            "speed": self._speed,
            "driver": "maxim-ds9481r",
        }

    def reset(self, *, required: bool = False) -> bool:
        self._command_mode()
        self._write(bytes((_RESET_PULSE,)))
        reply = self._read(1)[0]
        # Per DS2480B: bits encode presence / alarm / short. Presence when bit0==0 typically.
        presence = (reply & 0x03) != 0x03 and (reply & 0x01) == 0
        # Also accept common "presence seen" encodings used by emulators.
        if reply in (0xCD, 0xED, 0xC9, 0xE9):
            presence = True
        if (reply & 0xC0) == 0xC0 and (reply & 0x03) in (0x01, 0x00):
            presence = True
        if required and not presence:
            raise IoConnectionError("no 1-Wire presence pulse detected")
        return presence

    def _write_byte(self, value: int) -> int:
        self._data_mode()
        byte = value & 0xFF
        # Reserved command codes must be duplicated when sent as data.
        if byte in (_CMD_MODE, _DATA_MODE, _PULSE_TERM):
            self._write(bytes((byte, byte)))
        else:
            self._write(bytes((byte,)))
        return self._read(1)[0]

    def _read_byte(self) -> int:
        return self._write_byte(0xFF)

    def write(self, data: bytes) -> None:
        for byte in data:
            self._write_byte(byte)

    def read(self, nbytes: int) -> bytes:
        if nbytes < 0:
            raise IoConfigError("nbytes must be >= 0")
        return bytes(self._read_byte() for _ in range(nbytes))

    def write_read(self, write_data: bytes, read_nbytes: int) -> bytes:
        self.write(write_data)
        return self.read(read_nbytes)

    def select(self, rom: str | bytes | None = None) -> None:
        if not self.reset(required=True):
            raise IoConnectionError("no 1-Wire presence pulse detected")
        raw = hex_to_rom(rom)
        if raw is None:
            self.write(b"\xCC")  # SKIP ROM
            return
        self.write(b"\x55")  # MATCH ROM
        self.write(raw)

    def _touch_bit(self, bit: int) -> int:
        """Write one 1-Wire bit and return the sampled bus value."""
        self._command_mode()
        cmd = 0x91 if bit else 0x81
        self._write(bytes((cmd,)))
        reply = self._read(1)[0]
        return 1 if (reply & 0x01) else 0

    def search(self) -> list[str]:
        """Classic ROM search via single-bit slots (no accelerator dependency)."""
        found: list[str] = []
        last_discrepancy = 0
        done = False
        rom = bytearray(8)
        while not done:
            if not self.reset():
                break
            self.write(b"\xF0")  # SEARCH ROM
            last_zero = 0
            for bit_index in range(1, 65):
                id_bit = self._touch_bit(1)
                cmp_bit = self._touch_bit(1)
                if id_bit and cmp_bit:
                    done = True
                    rom = bytearray(8)
                    break
                if id_bit != cmp_bit:
                    direction = id_bit
                elif bit_index == last_discrepancy:
                    direction = 1
                elif bit_index > last_discrepancy:
                    direction = 0
                else:
                    direction = (rom[(bit_index - 1) // 8] >> ((bit_index - 1) % 8)) & 1
                if direction == 0:
                    last_zero = bit_index
                byte_index = (bit_index - 1) // 8
                bit_mask = 1 << ((bit_index - 1) % 8)
                if direction:
                    rom[byte_index] |= bit_mask
                else:
                    rom[byte_index] &= (~bit_mask) & 0xFF
                self._touch_bit(direction)
            else:
                if _crc8(bytes(rom[:7])) != rom[7]:
                    raise IoConnectionError(f"1-Wire ROM CRC mismatch: {bytes(rom).hex()}")
                hex_rom = rom_to_hex(bytes(rom))
                if hex_rom not in found:
                    found.append(hex_rom)
                last_discrepancy = last_zero
                if last_discrepancy == 0:
                    done = True
                continue
            break
        return found
