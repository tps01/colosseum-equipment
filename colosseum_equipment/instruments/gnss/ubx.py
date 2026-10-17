"""Minimal UBX framing and NAV-PVT decode (u-blox interface description).

Reference: u-blox M10 / F10 interface descriptions (UBX-20053845, UBX-23003447)
and the pyubx2 reading list for message IDs — no runtime dependency.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

UBX_SYNC = b"\xb5\x62"
CLS_NAV = 0x01
ID_NAV_PVT = 0x07
CLS_CFG = 0x06
ID_CFG_MSG = 0x01
ID_CFG_RST = 0x04
CLS_NMEA = 0xF0
ID_NMEA_GSV = 0x03
CLS_ACK = 0x05
ID_ACK_ACK = 0x01


def ubx_checksum(payload: bytes) -> bytes:
    ck_a = 0
    ck_b = 0
    for byte in payload:
        ck_a = (ck_a + byte) & 0xFF
        ck_b = (ck_b + ck_a) & 0xFF
    return bytes((ck_a, ck_b))


def build_ubx(msg_class: int, msg_id: int, payload: bytes = b"") -> bytes:
    header = bytes((msg_class, msg_id)) + struct.pack("<H", len(payload))
    body = header + payload
    return UBX_SYNC + body + ubx_checksum(body)


def cfg_msg_rate(msg_class: int, msg_id: int, rate: int) -> bytes:
    """Enable or disable a message on the current I/O port (CFG-MSG)."""
    return build_ubx(CLS_CFG, ID_CFG_MSG, bytes((msg_class, msg_id, rate & 0xFF)))


def cfg_rst_cold() -> bytes:
    """UBX-CFG-RST cold start: clear BBR navigation data, controlled software reset."""
    # navBbrMask=0xFFFF (cold), resetMode=0x01 (controlled software reset), reserved=0
    return build_ubx(CLS_CFG, ID_CFG_RST, struct.pack("<HBB", 0xFFFF, 0x01, 0x00))


@dataclass(frozen=True)
class NavPvt:
    latitude: float
    longitude: float
    altitude_m: float
    fix_quality: int
    satellites: int
    hdop: float
    utc_time: str
    fix_ok: bool


def parse_nav_pvt(payload: bytes) -> NavPvt | None:
    """Decode UBX-NAV-PVT payload (92+ bytes)."""
    if len(payload) < 92:
        return None
    year, month, day, hour, minute, second = struct.unpack_from("<HBBBBB", payload, 4)
    fix_type = payload[20]
    flags = payload[21]
    num_sv = payload[23]
    lon_i, lat_i, _height, h_msl = struct.unpack_from("<iiii", payload, 24)
    p_dop = struct.unpack_from("<H", payload, 76)[0]
    fix_ok = bool(flags & 0x01)
    quality = fix_type if fix_ok else 0
    return NavPvt(
        latitude=lat_i * 1e-7,
        longitude=lon_i * 1e-7,
        altitude_m=h_msl / 1000.0,
        fix_quality=quality,
        satellites=num_sv,
        hdop=p_dop / 100.0,
        utc_time=f"{year:04d}-{month:02d}-{day:02d}T{hour:02d}:{minute:02d}:{second:02d}Z",
        fix_ok=fix_ok and fix_type >= 2,
    )


class UbxStreamParser:
    """Accumulate serial bytes and yield complete UBX payloads or NMEA lines."""

    def __init__(self) -> None:
        self._buf = bytearray()

    def feed(self, data: bytes) -> list[tuple[str, object]]:
        self._buf.extend(data)
        events: list[tuple[str, object]] = []
        while True:
            if not self._buf:
                break
            if self._buf[0] == 0xB5:
                frame = self._take_ubx()
                if frame is None:
                    break
                events.append(("ubx", frame))
                continue
            if self._buf[0] == ord("$"):
                line = self._take_nmea()
                if line is None:
                    break
                events.append(("nmea", line))
                continue
            del self._buf[0]
        return events

    def _take_ubx(self) -> tuple[int, int, bytes] | None:
        if len(self._buf) < 6:
            return None
        if self._buf[0] != 0xB5 or self._buf[1] != 0x62:
            del self._buf[0]
            return None
        length = self._buf[4] | (self._buf[5] << 8)
        total = 8 + length
        if len(self._buf) < total:
            return None
        frame = bytes(self._buf[:total])
        del self._buf[:total]
        body = frame[2:6 + length]
        if ubx_checksum(body) != frame[6 + length : total]:
            return None
        return frame[2], frame[3], frame[6 : 6 + length]

    def _take_nmea(self) -> str | None:
        try:
            end = self._buf.index(0x0A)
        except ValueError:
            return None
        raw = bytes(self._buf[: end + 1])
        del self._buf[: end + 1]
        return raw.decode("ascii", errors="replace").strip()
