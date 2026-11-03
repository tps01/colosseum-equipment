"""Minimal UBX framing and NAV-PVT decode (u-blox interface description).

Reference: u-blox M10 / F10 interface descriptions (UBX-20053845, UBX-23003447)
and the pyubx2 reading list for message IDs — no runtime dependency.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Any

UBX_SYNC = b"\xb5\x62"
CLS_NAV = 0x01
ID_NAV_POSECEF = 0x01
ID_NAV_STATUS = 0x03
ID_NAV_DOP = 0x04
ID_NAV_PVT = 0x07
ID_NAV_TIMEGPS = 0x20
ID_NAV_CLOCK = 0x22
ID_NAV_SAT = 0x35
CLS_RXM = 0x02
ID_RXM_MEASX = 0x14
ID_RXM_RAWX = 0x15
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
    "NAV-POSECEF": (CLS_NAV, ID_NAV_POSECEF),
    "NAV-STATUS": (CLS_NAV, ID_NAV_STATUS),
    "NAV-TIMEGPS": (CLS_NAV, ID_NAV_TIMEGPS),
    "NAV-CLOCK": (CLS_NAV, ID_NAV_CLOCK),
    "RXM-MEASX": (CLS_RXM, ID_RXM_MEASX),
    "RXM-RAWX": (CLS_RXM, ID_RXM_RAWX),
    "NMEA-GGA": (CLS_NMEA, ID_NMEA_GGA),
    "NMEA-GLL": (CLS_NMEA, ID_NMEA_GLL),
    "NMEA-GSA": (CLS_NMEA, ID_NMEA_GSA),
    "NMEA-GSV": (CLS_NMEA, ID_NMEA_GSV),
    "NMEA-RMC": (CLS_NMEA, ID_NMEA_RMC),
    "NMEA-VTG": (CLS_NMEA, ID_NMEA_VTG),
    # Common aliases
    "GGA": (CLS_NMEA, ID_NMEA_GGA),
    "GSA": (CLS_NMEA, ID_NMEA_GSA),
    "GSV": (CLS_NMEA, ID_NMEA_GSV),
    "RMC": (CLS_NMEA, ID_NMEA_RMC),
    "VTG": (CLS_NMEA, ID_NMEA_VTG),
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


def parse_mon_ver_series(body: bytes) -> str | None:
    """Return a series token (m8/m9/m10/f9/f10) from a MON-VER payload, if any."""
    if len(body) < 40:
        return None
    parts: list[str] = []
    for start, end in ((0, 30), (30, 40)):
        raw = body[start:end].split(b"\x00", 1)[0]
        if raw:
            parts.append(raw.decode("ascii", errors="replace"))
    for offset in range(40, len(body), 30):
        raw = body[offset : offset + 30].split(b"\x00", 1)[0]
        if raw:
            parts.append(raw.decode("ascii", errors="replace"))
    blob = " ".join(parts).upper()
    for token in ("M10", "F10", "F9", "M9", "M8"):
        if token in blob:
            return token.lower()
    return None


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


def parse_nav_posecef(payload: bytes) -> dict[str, Any] | None:
    """Decode UBX-NAV-POSECEF (20 bytes) to a field dict."""
    if len(payload) < 20:
        return None
    itow, ecef_x, ecef_y, ecef_z, p_acc = struct.unpack_from("<IiiiI", payload, 0)
    return {
        "iTOW": itow,
        "ecefX": ecef_x,
        "ecefY": ecef_y,
        "ecefZ": ecef_z,
        "pAcc": p_acc,
        "ecefX_m": ecef_x / 100.0,
        "ecefY_m": ecef_y / 100.0,
        "ecefZ_m": ecef_z / 100.0,
        "pAcc_m": p_acc / 100.0,
    }


def parse_nav_status(payload: bytes) -> dict[str, Any] | None:
    """Decode UBX-NAV-STATUS (16 bytes)."""
    if len(payload) < 16:
        return None
    itow = struct.unpack_from("<I", payload, 0)[0]
    gps_fix = payload[4]
    flags = payload[5]
    fix_stat = payload[6]
    flags2 = payload[7]
    ttff, msss = struct.unpack_from("<II", payload, 8)
    return {
        "iTOW": itow,
        "gpsFix": gps_fix,
        "flags": flags,
        "fixStat": fix_stat,
        "flags2": flags2,
        "ttff": ttff,
        "msss": msss,
        "gpsFixOk": 1 if (flags & 0x01) else 0,
    }


def parse_nav_timegps(payload: bytes) -> dict[str, Any] | None:
    """Decode UBX-NAV-TIMEGPS (16 bytes)."""
    if len(payload) < 16:
        return None
    itow, ftow, week = struct.unpack_from("<IiH", payload, 0)
    leap_s = struct.unpack_from("<b", payload, 10)[0]
    valid = payload[11]
    t_acc = struct.unpack_from("<I", payload, 12)[0]
    return {
        "iTOW": itow,
        "fTOW": ftow,
        "week": week,
        "leapS": leap_s,
        "valid": valid,
        "tAcc": t_acc,
    }


def parse_nav_clock(payload: bytes) -> dict[str, Any] | None:
    """Decode UBX-NAV-CLOCK (20 bytes)."""
    if len(payload) < 20:
        return None
    itow, clk_b, clk_d, t_acc, f_acc = struct.unpack_from("<IiiII", payload, 0)
    return {
        "iTOW": itow,
        "clkB": clk_b,
        "clkD": clk_d,
        "tAcc": t_acc,
        "fAcc": f_acc,
    }


def parse_nav_sat(payload: bytes) -> dict[str, Any] | None:
    """Decode UBX-NAV-SAT header + per-SV rows; include ``num_svs`` and ``svs``."""
    if len(payload) < 8:
        return None
    itow = struct.unpack_from("<I", payload, 0)[0]
    version = payload[4]
    num_svs = payload[5]
    svs: list[dict[str, float | int]] = []
    offset = 8
    for _ in range(num_svs):
        if offset + 12 > len(payload):
            break
        gnss_id, sv_id, cno, elev = payload[offset : offset + 4]
        azim, pr_res = struct.unpack_from("<hh", payload, offset + 4)
        flags = struct.unpack_from("<I", payload, offset + 8)[0]
        elev_s = elev if elev < 128 else elev - 256
        svs.append(
            {
                "gnssId": gnss_id,
                "svId": sv_id,
                "cno": cno,
                "elev": elev_s,
                "azim": azim,
                "prRes": pr_res,
                "flags": flags,
            },
        )
        offset += 12
    return {
        "iTOW": itow,
        "version": version,
        "numSvs": num_svs,
        "num_svs": float(len(svs)),
        "svs": svs,
    }


def parse_rxm_rawx(payload: bytes) -> dict[str, Any] | None:
    """Decode UBX-RXM-RAWX header; ``num_svs`` is measurement count."""
    if len(payload) < 16:
        return None
    rcv_tow = struct.unpack_from("<d", payload, 0)[0]
    week = struct.unpack_from("<H", payload, 8)[0]
    leap_s = struct.unpack_from("<b", payload, 10)[0]
    num_meas = payload[11]
    return {
        "rcvTow": rcv_tow,
        "week": week,
        "leapS": leap_s,
        "numMeas": num_meas,
        "num_svs": float(num_meas),
        "recStat": payload[12],
        "version": payload[13],
    }


def parse_rxm_measx(payload: bytes) -> dict[str, Any] | None:
    """Decode UBX-RXM-MEASX header; ``num_svs`` from numSV field."""
    if len(payload) < 44:
        return None
    version = payload[0]
    num_sv = payload[34]
    flags = payload[35]
    return {
        "version": version,
        "numSV": num_sv,
        "num_svs": float(num_sv),
        "flags": flags,
    }


def nav_pvt_fields(nav: NavPvt) -> dict[str, float | int | str | bool]:
    """Flatten NavPvt for multi-row evidence."""
    return {
        "latitude": nav.latitude,
        "longitude": nav.longitude,
        "altitude_m": nav.altitude_m,
        "fix_quality": nav.fix_quality,
        "satellites": nav.satellites,
        "num_svs": float(nav.satellites),
        "pdop": nav.pdop,
        "utc_time": nav.utc_time,
        "fix_ok": nav.fix_ok,
        "gpsFixOk": 1 if nav.fix_ok else 0,
        "hAcc": nav.h_acc_m * 1000.0,  # mm, UBX native scale alias
        "vAcc": nav.v_acc_m * 1000.0,
        "h_acc_m": nav.h_acc_m,
        "v_acc_m": nav.v_acc_m,
        "speed_m_s": nav.speed_m_s,
        "course_deg": nav.course_deg,
    }


def nav_dop_fields(dop: NavDop) -> dict[str, float]:
    return {
        "gDOP": dop.gdop,
        "pDOP": dop.pdop,
        "tDOP": dop.tdop,
        "vDOP": dop.vdop,
        "hDOP": dop.hdop,
        "nDOP": dop.ndop,
        "eDOP": dop.edop,
        "gdop": dop.gdop,
        "pdop": dop.pdop,
        "vdop": dop.vdop,
        "hdop": dop.hdop,
    }


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
