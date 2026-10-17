"""Minimal NovAtel OEM7 binary framing and BESTPOSB decode.

Reference: OEM7 Commands and Logs Reference Manual (free PDF on docs.novatel.com).
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

OEM7_SYNC = b"\xaa\x44\x12"
MSG_BESTPOS = 42
# Solution status SOL_COMPUTED
SOL_COMPUTED = 0
CRC32_POLYNOMIAL = 0xEDB88320


def _crc32_value(index: int) -> int:
    crc = index & 0xFF
    for _ in range(8):
        if crc & 1:
            crc = (crc >> 1) ^ CRC32_POLYNOMIAL
        else:
            crc >>= 1
    return crc & 0xFFFFFFFF


def oem7_crc32(data: bytes) -> int:
    """OEM7 CRC-32 over header+body (excluding the trailing CRC word)."""
    crc = 0
    for byte in data:
        temp1 = (crc >> 8) & 0x00FFFFFF
        temp2 = _crc32_value((crc ^ byte) & 0xFF)
        crc = temp1 ^ temp2
    return crc & 0xFFFFFFFF


@dataclass(frozen=True)
class BestPos:
    latitude: float
    longitude: float
    altitude_m: float
    fix_quality: int
    satellites: int
    sol_stat: int
    pos_type: int


def parse_bestpos(payload: bytes) -> BestPos | None:
    """Decode BESTPOS body (after 28-byte binary header)."""
    if len(payload) < 72:
        return None
    sol_stat, pos_type = struct.unpack_from("<II", payload, 0)
    lat, lon, hgt = struct.unpack_from("<ddd", payload, 8)
    # #SVs tracked at H+64, #solnSVs at H+65 (relative to body start: 64, 65)
    tracked = payload[64]
    soln_svs = payload[65]
    quality = 0
    if sol_stat == SOL_COMPUTED and pos_type > 0:
        quality = int(pos_type)
    return BestPos(
        latitude=lat,
        longitude=lon,
        altitude_m=hgt,
        fix_quality=quality,
        satellites=soln_svs or tracked,
        sol_stat=sol_stat,
        pos_type=pos_type,
    )


class Oem7StreamParser:
    """Accumulate bytes and yield OEM7 binary payloads or NMEA lines."""

    def __init__(self) -> None:
        self._buf = bytearray()

    def feed(self, data: bytes) -> list[tuple[str, object]]:
        self._buf.extend(data)
        events: list[tuple[str, object]] = []
        while True:
            if not self._buf:
                break
            if self._buf[0] == 0xAA:
                frame = self._take_oem7()
                if frame is None:
                    break
                events.append(("oem7", frame))
                continue
            if self._buf[0] == ord("$") or self._buf[0] == ord("#"):
                # '#' is OEM7 ASCII; treat line-oriented like NMEA for GGA/GSV/$ responses.
                line = self._take_line()
                if line is None:
                    break
                if line.startswith("$"):
                    events.append(("nmea", line))
                else:
                    events.append(("ascii", line))
                continue
            del self._buf[0]
        return events

    def _take_oem7(self) -> tuple[int, bytes] | None:
        if len(self._buf) < 10:
            return None
        if self._buf[0:3] != OEM7_SYNC:
            del self._buf[0]
            return None
        header_len = self._buf[3]
        if header_len < 28 or len(self._buf) < header_len:
            if header_len < 28:
                del self._buf[0]
            return None
        msg_id = self._buf[4] | (self._buf[5] << 8)
        body_len = self._buf[8] | (self._buf[9] << 8)
        total = header_len + body_len + 4
        if len(self._buf) < total:
            return None
        frame = bytes(self._buf[:total])
        del self._buf[:total]
        expected = struct.unpack_from("<I", frame, header_len + body_len)[0]
        if oem7_crc32(frame[: header_len + body_len]) != expected:
            return None
        return msg_id, frame[header_len : header_len + body_len]

    def _take_line(self) -> str | None:
        try:
            end = self._buf.index(0x0A)
        except ValueError:
            return None
        raw = bytes(self._buf[: end + 1])
        del self._buf[: end + 1]
        return raw.decode("ascii", errors="replace").strip()
