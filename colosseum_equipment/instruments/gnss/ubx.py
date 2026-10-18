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
ID_NAV_DOP = 0x04
ID_NAV_SAT = 0x35
CLS_CFG = 0x06
ID_CFG_PRT = 0x00
ID_CFG_MSG = 0x01
ID_CFG_RST = 0x04
ID_CFG_RATE = 0x08
ID_CFG_NAV5 = 0x24
ID_CFG_GNSS = 0x3E
ID_CFG_VALSET = 0x8A
ID_CFG_VALGET = 0x8B
CLS_NMEA = 0xF0
ID_NMEA_GGA = 0x00
ID_NMEA_GLL = 0x01
ID_NMEA_GSA = 0x02
ID_NMEA_GSV = 0x03
ID_NMEA_RMC = 0x04
ID_NMEA_VTG = 0x05
CLS_ACK = 0x05
ID_ACK_NAK = 0x00
ID_ACK_ACK = 0x01
CLS_MON = 0x0A
ID_MON_VER = 0x04

# SET layer bitfield for CFG-VALSET
SET_LAYER_RAM = 0x01
SET_LAYER_BBR = 0x02
SET_LAYER_FLASH = 0x04

# Named messages for set_message_rate (CFG-MSG on current port)
MESSAGE_IDS: dict[str, tuple[int, int]] = {
    "NAV-PVT": (CLS_NAV, ID_NAV_PVT),
    "NAV-DOP": (CLS_NAV, ID_NAV_DOP),
    "NAV-SAT": (CLS_NAV, ID_NAV_SAT),
    "NMEA-GGA": (CLS_NMEA, ID_NMEA_GGA),
    "NMEA-GLL": (CLS_NMEA, ID_NMEA_GLL),
    "NMEA-GSA": (CLS_NMEA, ID_NMEA_GSA),
    "NMEA-GSV": (CLS_NMEA, ID_NMEA_GSV),
    "NMEA-RMC": (CLS_NMEA, ID_NMEA_RMC),
    "NMEA-VTG": (CLS_NMEA, ID_NMEA_VTG),
    # Common aliases
    "GGA": (CLS_NMEA, ID_NMEA_GGA),
    "GSV": (CLS_NMEA, ID_NMEA_GSV),
    "RMC": (CLS_NMEA, ID_NMEA_RMC),
}

# Legacy CFG polls for M8 save_config
LEGACY_CFG_POLLS: tuple[tuple[str, int, int, bytes], ...] = (
    ("CFG-PRT", CLS_CFG, ID_CFG_PRT, b""),
    ("CFG-RATE", CLS_CFG, ID_CFG_RATE, b""),
    ("CFG-NAV5", CLS_CFG, ID_CFG_NAV5, b""),
    ("CFG-GNSS", CLS_CFG, ID_CFG_GNSS, b""),
    ("CFG-MSG", CLS_CFG, ID_CFG_MSG, bytes((CLS_NAV, ID_NAV_PVT))),
    ("CFG-MSG", CLS_CFG, ID_CFG_MSG, bytes((CLS_NAV, ID_NAV_DOP))),
    ("CFG-MSG", CLS_CFG, ID_CFG_MSG, bytes((CLS_NMEA, ID_NMEA_GSV))),
    ("CFG-MSG", CLS_CFG, ID_CFG_MSG, bytes((CLS_NMEA, ID_NMEA_GGA))),
    ("CFG-MSG", CLS_CFG, ID_CFG_MSG, bytes((CLS_NMEA, ID_NMEA_RMC))),
)


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


def cfg_valget_poll(*, layer: int = 0, position: int = 0) -> bytes:
    """Poll CFG-VALGET (version 0) for configuration items at ``position``."""
    payload = bytes((0, layer & 0xFF)) + struct.pack("<H", position & 0xFFFF)
    return build_ubx(CLS_CFG, ID_CFG_VALGET, payload)


def mon_ver_poll() -> bytes:
    return build_ubx(CLS_MON, ID_MON_VER, b"")


def resolve_message_id(message: str) -> tuple[int, int]:
    key = message.strip().upper().replace("_", "-")
    if key not in MESSAGE_IDS:
        raise KeyError(message)
    return MESSAGE_IDS[key]


def ucenter_hex_line(name: str, msg_class: int, msg_id: int, payload: bytes) -> str:
    """Format one u-center GNSS Configuration text line (no sync/checksum)."""
    body = bytes((msg_class, msg_id)) + struct.pack("<H", len(payload)) + payload
    return f"{name} - {body.hex(' ').upper()}"


@dataclass(frozen=True)
class NavPvt:
    latitude: float
    longitude: float
    altitude_m: float
    altitude_ellipsoid_m: float
    fix_quality: int
    satellites: int
    pdop: float
    utc_time: str
    fix_ok: bool
    h_acc_m: float
    v_acc_m: float
    speed_m_s: float
    course_deg: float


@dataclass(frozen=True)
class NavDop:
    gdop: float
    pdop: float
    tdop: float
    vdop: float
    hdop: float
    ndop: float
    edop: float


def parse_nav_pvt(payload: bytes) -> NavPvt | None:
    """Decode UBX-NAV-PVT payload (92+ bytes)."""
    if len(payload) < 92:
        return None
    year, month, day, hour, minute, second = struct.unpack_from("<HBBBBB", payload, 4)
    fix_type = payload[20]
    flags = payload[21]
    num_sv = payload[23]
    lon_i, lat_i, height, h_msl = struct.unpack_from("<iiii", payload, 24)
    h_acc, v_acc = struct.unpack_from("<II", payload, 40)
    vel_n, vel_e, vel_d = struct.unpack_from("<iii", payload, 48)
    g_speed, head_mot = struct.unpack_from("<ii", payload, 60)
    p_dop = struct.unpack_from("<H", payload, 76)[0]
    fix_ok = bool(flags & 0x01)
    quality = fix_type if fix_ok else 0
    speed = (g_speed / 1000.0) if g_speed else (
        (vel_n ** 2 + vel_e ** 2 + vel_d ** 2) ** 0.5 / 1000.0
    )
    return NavPvt(
        latitude=lat_i * 1e-7,
        longitude=lon_i * 1e-7,
        altitude_m=h_msl / 1000.0,
        altitude_ellipsoid_m=height / 1000.0,
        fix_quality=quality,
        satellites=num_sv,
        pdop=p_dop / 100.0,
        utc_time=f"{year:04d}-{month:02d}-{day:02d}T{hour:02d}:{minute:02d}:{second:02d}Z",
        fix_ok=fix_ok and fix_type >= 2,
        h_acc_m=h_acc / 1000.0,
        v_acc_m=v_acc / 1000.0,
        speed_m_s=speed,
        course_deg=head_mot / 1e5,
    )


def parse_nav_dop(payload: bytes) -> NavDop | None:
    """Decode UBX-NAV-DOP payload (18 bytes)."""
    if len(payload) < 18:
        return None
    # iTOW + gDOP pDOP tDOP vDOP hDOP nDOP eDOP (each u2, scale 0.01)
    values = struct.unpack_from("<HHHHHHH", payload, 4)
    return NavDop(*(v / 100.0 for v in values))


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
