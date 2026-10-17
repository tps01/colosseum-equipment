"""Minimal Septentrio SBF framing and PVTGeodetic decode.

Field layout follows the Septentrio Reference Guide / pysbf2 reading list
(BSD-3) — no runtime dependency.
"""

from __future__ import annotations

import math
import struct
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

SBF_SYNC = b"$@"
BLOCK_PVT_GEODETIC = 4007
_GPS_EPOCH = datetime(1980, 1, 6, tzinfo=timezone.utc)
# Approximate GPS→UTC leap-second offset; fine for bench timestamps.
_GPS_UTC_LEAP_S = 18


def sbf_crc(data: bytes) -> int:
    """CRC-CCITT (poly 0x1021) over ID through end of block."""
    crc = 0
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ 0x1021
            else:
                crc <<= 1
            crc &= 0xFFFF
    return crc


def build_sbf(block_number: int, payload: bytes, *, revision: int = 0) -> bytes:
    """Build a padded SBF block (header + payload + CRC)."""
    body = payload
    pad = (4 - ((8 + len(body)) % 4)) % 4
    if pad:
        body = body + b"\x00" * pad
    length = 8 + len(body)
    block_id = ((revision & 0x7) << 13) | (block_number & 0x1FFF)
    mid = struct.pack("<HH", block_id, length) + body
    return SBF_SYNC + struct.pack("<H", sbf_crc(mid)) + mid


@dataclass(frozen=True)
class PvtGeodetic:
    latitude: float
    longitude: float
    altitude_m: float
    fix_quality: int
    satellites: int
    utc_time: str
    mode_type: int
    error: int


def _mode_to_fix_quality(mode: int, error: int) -> int:
    """Map SBF Mode/Error to a GGA-like quality code."""
    if error != 0:
        return 0
    mode_type = mode & 0x0F
    if mode_type == 0:
        return 0
    return mode_type


def _gps_to_utc_iso(tow_ms: int, wnc: int) -> str:
    try:
        dt = _GPS_EPOCH + timedelta(weeks=wnc, milliseconds=tow_ms)
        dt = dt - timedelta(seconds=_GPS_UTC_LEAP_S)
    except OverflowError:
        return ""
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_pvt_geodetic(payload: bytes) -> PvtGeodetic | None:
    """Decode PVTGeodetic body (block 4007), excluding the 8-byte header."""
    if len(payload) < 67:
        return None
    tow_ms, wnc, mode, error = struct.unpack_from("<IHBB", payload, 0)
    lat_rad, lon_rad, height = struct.unpack_from("<ddd", payload, 8)
    nr_sv = payload[66]
    if not math.isfinite(lat_rad) or not math.isfinite(lon_rad):
        return None
    quality = _mode_to_fix_quality(mode, error)
    return PvtGeodetic(
        latitude=math.degrees(lat_rad),
        longitude=math.degrees(lon_rad),
        altitude_m=height if math.isfinite(height) else 0.0,
        fix_quality=quality,
        satellites=nr_sv,
        utc_time=_gps_to_utc_iso(tow_ms, wnc),
        mode_type=mode & 0x0F,
        error=error,
    )


class SbfStreamParser:
    """Accumulate bytes and yield SBF payloads or NMEA lines."""

    def __init__(self) -> None:
        self._buf = bytearray()

    def feed(self, data: bytes) -> list[tuple[str, object]]:
        self._buf.extend(data)
        events: list[tuple[str, object]] = []
        while True:
            if not self._buf:
                break
            if self._buf[0] == ord("$"):
                if len(self._buf) < 2:
                    break
                if self._buf[1] == ord("@"):
                    frame = self._take_sbf()
                    if frame is None:
                        break
                    events.append(("sbf", frame))
                    continue
                line = self._take_nmea()
                if line is None:
                    break
                events.append(("nmea", line))
                continue
            del self._buf[0]
        return events

    def _take_sbf(self) -> tuple[int, bytes] | None:
        if len(self._buf) < 8:
            return None
        if self._buf[0:2] != SBF_SYNC:
            del self._buf[0]
            return None
        length = self._buf[6] | (self._buf[7] << 8)
        if length < 8 or length % 4:
            del self._buf[0]
            return None
        if len(self._buf) < length:
            return None
        frame = bytes(self._buf[:length])
        del self._buf[:length]
        crc_expected = frame[2] | (frame[3] << 8)
        if sbf_crc(frame[4:]) != crc_expected:
            return None
        block_id = frame[4] | (frame[5] << 8)
        block_number = block_id & 0x1FFF
        return block_number, frame[8:]

    def _take_nmea(self) -> str | None:
        try:
            end = self._buf.index(0x0A)
        except ValueError:
            return None
        raw = bytes(self._buf[: end + 1])
        del self._buf[: end + 1]
        return raw.decode("ascii", errors="replace").strip()
