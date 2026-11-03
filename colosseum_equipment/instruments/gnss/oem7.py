"""NovAtel OEM7 binary framing and selected log decoders.

Reference: OEM7 Commands and Logs Reference Manual (free PDF on docs.novatel.com).
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Any

OEM7_SYNC = b"\xaa\x44\x12"
MSG_BESTPOS = 42
MSG_RANGE = 43
MSG_CLOCKMODEL = 16
MSG_TRACKSTAT = 83
MSG_RXSTATUS = 93
MSG_TIME = 101
MSG_PSRDOP = 174
MSG_BESTXYZ = 241
MSG_SATVIS2 = 1043
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
    lat_stdev_m: float | None = None
    lon_stdev_m: float | None = None
    hgt_stdev_m: float | None = None
    tracked_svs: int = 0
    soln_svs: int = 0


def parse_bestpos(payload: bytes) -> BestPos | None:
    """Decode BESTPOS body (after 28-byte binary header)."""
    if len(payload) < 72:
        return None
    sol_stat, pos_type = struct.unpack_from("<II", payload, 0)
    lat, lon, hgt = struct.unpack_from("<ddd", payload, 8)
    lat_std, lon_std, hgt_std = struct.unpack_from("<fff", payload, 40)
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
        lat_stdev_m=float(lat_std),
        lon_stdev_m=float(lon_std),
        hgt_stdev_m=float(hgt_std),
        tracked_svs=int(tracked),
        soln_svs=int(soln_svs),
    )


def bestpos_fields(best: BestPos) -> dict[str, Any]:
    """Normalized PVT evidence fields from BESTPOS."""
    h_acc = None
    if best.lat_stdev_m is not None and best.lon_stdev_m is not None:
        h_acc = (best.lat_stdev_m**2 + best.lon_stdev_m**2) ** 0.5
    return {
        "latitude": best.latitude,
        "longitude": best.longitude,
        "altitude_m": best.altitude_m,
        "fix_quality": best.fix_quality,
        "num_svs": best.satellites,
        "sol_stat": best.sol_stat,
        "pos_type": best.pos_type,
        "h_acc_m": h_acc,
        "v_acc_m": best.hgt_stdev_m,
        "gpsFixOk": 1 if best.fix_quality > 0 else 0,
    }


def parse_psrdop(payload: bytes) -> dict[str, Any] | None:
    """Decode PSRDOP body (gdop/pdop/hdop/…)."""
    if len(payload) < 28:
        return None
    gdop, pdop, hdop, htdop, tdop, cutoff = struct.unpack_from("<ffffff", payload, 0)
    num_sats = payload[24] if len(payload) > 24 else 0
    return {
        "gdop": float(gdop),
        "pdop": float(pdop),
        "hdop": float(hdop),
        "vdop": float(htdop),
        "tdop": float(tdop),
        "cutoff": float(cutoff),
        "num_svs": int(num_sats),
    }


def parse_bestxyz(payload: bytes) -> dict[str, Any] | None:
    """Decode BESTXYZ body (ECEF position)."""
    if len(payload) < 56:
        return None
    sol_stat, pos_type = struct.unpack_from("<II", payload, 0)
    x, y, z = struct.unpack_from("<ddd", payload, 8)
    return {
        "ecefX": float(x),
        "ecefY": float(y),
        "ecefZ": float(z),
        "sol_stat": int(sol_stat),
        "pos_type": int(pos_type),
        "gpsFixOk": 1 if sol_stat == SOL_COMPUTED and pos_type > 0 else 0,
    }


def parse_time(payload: bytes) -> dict[str, Any] | None:
    """Decode TIME body (GPS week / seconds)."""
    if len(payload) < 44:
        return None
    clock_status = struct.unpack_from("<I", payload, 0)[0]
    offset = struct.unpack_from("<d", payload, 4)[0]
    offset_std = struct.unpack_from("<d", payload, 12)[0]
    utc_offset = struct.unpack_from("<d", payload, 20)[0]
    utc_year, utc_month, utc_day, utc_hour = struct.unpack_from("<HHHH", payload, 28)
    utc_min = struct.unpack_from("<I", payload, 36)[0]
    utc_ms = struct.unpack_from("<I", payload, 40)[0]
    return {
        "clockStatus": int(clock_status),
        "offset": float(offset),
        "offsetStd": float(offset_std),
        "utcOffset": float(utc_offset),
        "year": int(utc_year),
        "month": int(utc_month),
        "day": int(utc_day),
        "hour": int(utc_hour),
        "min": int(utc_min),
        "ms": int(utc_ms),
    }


def parse_clockmodel(payload: bytes) -> dict[str, Any] | None:
    """Decode CLOCKMODEL body (clock bias / drift when present)."""
    if len(payload) < 24:
        return None
    status = struct.unpack_from("<I", payload, 0)[0]
    reject = struct.unpack_from("<I", payload, 4)[0]
    # Parameters vary by version; expose leading doubles when available.
    fields: dict[str, Any] = {"status": int(status), "reject": int(reject)}
    if len(payload) >= 32:
        fields["clkBias"] = float(struct.unpack_from("<d", payload, 16)[0])
    if len(payload) >= 40:
        fields["clkDrift"] = float(struct.unpack_from("<d", payload, 24)[0])
    return fields


def parse_rxstatus(payload: bytes) -> dict[str, Any] | None:
    """Decode RXSTATUS body (error / status words)."""
    if len(payload) < 16:
        return None
    error, number_of_stats = struct.unpack_from("<II", payload, 0)
    return {
        "error": int(error),
        "numberOfStats": int(number_of_stats),
        "gpsFixOk": 1 if error == 0 else 0,
        "iTOW": 0,
        "gpsFix": 0 if error else 3,
        "flags": int(error),
    }


def parse_satvis2(payload: bytes) -> dict[str, Any] | None:
    """Decode SATVIS2 header counts (satellite census)."""
    if len(payload) < 12:
        return None
    sat_vis = payload[8] if len(payload) > 8 else 0
    return {"num_svs": int(sat_vis), "svs": []}


def parse_trackstat(payload: bytes) -> dict[str, Any] | None:
    """Decode TRACKSTAT header (channel / obs counts)."""
    if len(payload) < 8:
        return None
    # #obs at start of body for TRACKSTATB
    num_obs = struct.unpack_from("<I", payload, 0)[0] if len(payload) >= 4 else 0
    return {"num_svs": int(num_obs), "svs": []}


def parse_range(payload: bytes) -> dict[str, Any] | None:
    """Decode RANGE header (#obs)."""
    if len(payload) < 4:
        return None
    num_obs = struct.unpack_from("<I", payload, 0)[0]
    return {"num_svs": int(num_obs), "svs": []}


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
            if self._buf[0] == ord("$") or self._buf[0] == ord("#") or self._buf[0] == ord("<"):
                # '#' OEM7 ASCII; '<' command responses; '$' NMEA.
                line = self._take_line()
                if line is None:
                    break
                if line.startswith("$"):
                    events.append(("nmea", line))
                elif line.startswith("<"):
                    events.append(("ack", line))
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
