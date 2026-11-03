"""Septentrio SBF framing and selected block decoders.

Field layout follows the Septentrio Reference Guide / pysbf2 reading list
(BSD-3) — no runtime dependency.
"""

from __future__ import annotations

import math
import struct
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

SBF_SYNC = b"$@"
BLOCK_DOP = 4001
BLOCK_PVT_CARTESIAN = 4006
BLOCK_PVT_GEODETIC = 4007
BLOCK_SAT_VISIBILITY = 4012
BLOCK_CHANNEL_STATUS = 4013
BLOCK_RECEIVER_STATUS = 4014
BLOCK_MEAS_EPOCH = 4027
BLOCK_RECEIVER_TIME = 5914
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
    undulation_m: float | None = None
    cog_deg: float | None = None
    clock_bias_ms: float | None = None
    clock_drift_ppm: float | None = None


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
    undulation = struct.unpack_from("<f", payload, 32)[0] if len(payload) >= 36 else None
    cog = struct.unpack_from("<f", payload, 48)[0] if len(payload) >= 52 else None
    # ClockBias / ClockDrift sit after NrSV in later revisions; best-effort.
    clock_bias = None
    clock_drift = None
    if len(payload) >= 80:
        clock_bias = struct.unpack_from("<d", payload, 68)[0]
    if len(payload) >= 88:
        clock_drift = struct.unpack_from("<f", payload, 76)[0]
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
        undulation_m=float(undulation) if undulation is not None and math.isfinite(undulation) else None,
        cog_deg=float(cog) if cog is not None and math.isfinite(cog) else None,
        clock_bias_ms=float(clock_bias) if clock_bias is not None and math.isfinite(clock_bias) else None,
        clock_drift_ppm=(
            float(clock_drift) if clock_drift is not None and math.isfinite(clock_drift) else None
        ),
    )


def pvt_geodetic_fields(pvt: PvtGeodetic) -> dict[str, Any]:
    """Normalized PVT evidence fields from PVTGeodetic."""
    fields: dict[str, Any] = {
        "latitude": pvt.latitude,
        "longitude": pvt.longitude,
        "altitude_m": pvt.altitude_m,
        "fix_quality": pvt.fix_quality,
        "num_svs": pvt.satellites,
        "mode_type": pvt.mode_type,
        "error": pvt.error,
        "gpsFixOk": 1 if pvt.fix_quality > 0 else 0,
    }
    if pvt.clock_bias_ms is not None:
        fields["clkBias"] = pvt.clock_bias_ms
    if pvt.clock_drift_ppm is not None:
        fields["clkDrift"] = pvt.clock_drift_ppm
    return fields


def parse_dop(payload: bytes) -> dict[str, Any] | None:
    """Decode DOP body (block 4001)."""
    if len(payload) < 22:
        return None
    # TOW, WNc, NrSV, reserved, PDOP, TDOP, HDOP, VDOP, HPL, VPL
    _tow, _wnc, nr_sv = struct.unpack_from("<IHB", payload, 0)
    pdop, tdop, hdop, vdop = struct.unpack_from("<ffff", payload, 10)
    return {
        "pdop": float(pdop),
        "tdop": float(tdop),
        "hdop": float(hdop),
        "vdop": float(vdop),
        "gdop": float((pdop**2 + tdop**2) ** 0.5) if pdop > 0 else 0.0,
        "num_svs": int(nr_sv),
    }


def parse_pvt_cartesian(payload: bytes) -> dict[str, Any] | None:
    """Decode PVTCartesian body (block 4006)."""
    if len(payload) < 40:
        return None
    _tow, _wnc, mode, error = struct.unpack_from("<IHBB", payload, 0)
    x, y, z = struct.unpack_from("<ddd", payload, 8)
    quality = _mode_to_fix_quality(mode, error)
    return {
        "ecefX": float(x),
        "ecefY": float(y),
        "ecefZ": float(z),
        "fix_quality": quality,
        "gpsFixOk": 1 if quality > 0 else 0,
        "mode_type": mode & 0x0F,
        "error": error,
    }


def parse_receiver_time(payload: bytes) -> dict[str, Any] | None:
    """Decode ReceiverTime body (block 5914)."""
    if len(payload) < 12:
        return None
    tow_ms, wnc = struct.unpack_from("<IH", payload, 0)
    utc_year, utc_month, utc_day = struct.unpack_from("<HBB", payload, 6)
    utc_hour, utc_min, utc_sec = struct.unpack_from("<BBB", payload, 10) if len(payload) >= 13 else (0, 0, 0)
    return {
        "iTOW": int(tow_ms),
        "week": int(wnc),
        "year": int(utc_year),
        "month": int(utc_month),
        "day": int(utc_day),
        "hour": int(utc_hour),
        "min": int(utc_min),
        "sec": int(utc_sec),
        "utc_time": _gps_to_utc_iso(tow_ms, wnc),
    }


def parse_receiver_status(payload: bytes) -> dict[str, Any] | None:
    """Decode ReceiverStatus body (block 4014)."""
    if len(payload) < 12:
        return None
    _tow, _wnc = struct.unpack_from("<IH", payload, 0)
    cpu_load = payload[6] if len(payload) > 6 else 0
    ext_error = payload[7] if len(payload) > 7 else 0
    rx_error = struct.unpack_from("<I", payload, 8)[0] if len(payload) >= 12 else 0
    return {
        "cpuLoad": int(cpu_load),
        "extError": int(ext_error),
        "rxError": int(rx_error),
        "error": int(rx_error),
        "gpsFixOk": 1 if rx_error == 0 else 0,
        "flags": int(rx_error),
    }


def parse_sat_visibility(payload: bytes) -> dict[str, Any] | None:
    """Decode SatVisibility header count."""
    if len(payload) < 8:
        return None
    n = payload[6] if len(payload) > 6 else 0
    return {"num_svs": int(n), "svs": []}


def parse_channel_status(payload: bytes) -> dict[str, Any] | None:
    """Decode ChannelStatus header count."""
    if len(payload) < 8:
        return None
    n = payload[6] if len(payload) > 6 else 0
    return {"num_svs": int(n), "svs": []}


def parse_meas_epoch(payload: bytes) -> dict[str, Any] | None:
    """Decode MeasEpoch header (#observations)."""
    if len(payload) < 12:
        return None
    n1 = payload[6] if len(payload) > 6 else 0
    return {"num_svs": int(n1), "svs": []}


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
