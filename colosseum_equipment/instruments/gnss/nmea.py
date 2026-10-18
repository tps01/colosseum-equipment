"""NMEA 0183 parsers for GNSS position, DOP, velocity, and sky view."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NmeaFix:
    latitude: float
    longitude: float
    altitude_m: float
    fix_quality: int
    satellites: int
    hdop: float
    utc_time: str
    geoid_separation_m: float = 0.0


@dataclass(frozen=True)
class NmeaDop:
    fix_type: str  # none / 2d / 3d
    pdop: float
    hdop: float
    vdop: float
    prns: tuple[int, ...]


@dataclass(frozen=True)
class NmeaVelocity:
    speed_m_s: float
    course_deg: float


@dataclass(frozen=True)
class NmeaSat:
    prn: int
    elevation_deg: float
    azimuth_deg: float
    snr: float
    constellation: str
    signal_id: int | None = None


_TALKER_CONSTELLATION = {
    "GP": "GPS",
    "GL": "GLONASS",
    "GA": "Galileo",
    "GB": "BeiDou",
    "BD": "BeiDou",
    "GQ": "QZSS",
    "GI": "NavIC",
    "GN": "GNSS",
}


def _nmea_checksum_ok(sentence: str) -> bool:
    body = sentence.strip()
    if not body.startswith("$") or "*" not in body:
        return False
    payload, _, checksum = body[1:].partition("*")
    if len(checksum) < 2:
        return False
    value = 0
    for char in payload:
        value ^= ord(char)
    try:
        return value == int(checksum[:2], 16)
    except ValueError:
        return False


def _talker(fields0: str) -> str:
    # $GPGGA -> GP
    if fields0.startswith("$"):
        fields0 = fields0[1:]
    return fields0[:2] if len(fields0) >= 2 else ""


def constellation_from_talker(talker: str) -> str:
    return _TALKER_CONSTELLATION.get(talker.upper(), talker.upper() or "UNK")


def _dm_to_degrees(raw: str, hemisphere: str) -> float | None:
    if not raw or not hemisphere:
        return None
    try:
        value = float(raw)
    except ValueError:
        return None
    degrees = int(value // 100)
    minutes = value - degrees * 100
    result = degrees + minutes / 60.0
    if hemisphere in ("S", "W"):
        result = -result
    return result


def parse_gga(sentence: str) -> NmeaFix | None:
    """Parse a GGA sentence into a fix, or ``None`` if incomplete."""
    line = sentence.strip()
    if not _nmea_checksum_ok(line):
        return None
    fields = line.split("*", 1)[0].split(",")
    if len(fields) < 10 or not fields[0].endswith("GGA"):
        return None
    try:
        quality = int(fields[6] or "0")
        satellites = int(fields[7] or "0")
        hdop = float(fields[8] or "0")
        altitude = float(fields[9] or "0")
        geoid = float(fields[11] or "0") if len(fields) > 11 and fields[11] else 0.0
    except ValueError:
        return None
    lat = _dm_to_degrees(fields[2], fields[3])
    lon = _dm_to_degrees(fields[4], fields[5])
    # Allow no-fix sentences without lat/lon for dropout logging.
    if quality > 0 and (lat is None or lon is None):
        return None
    if lat is None:
        lat = 0.0
    if lon is None:
        lon = 0.0
    hhmmss = fields[1]
    utc = ""
    if len(hhmmss) >= 6:
        utc = f"{hhmmss[0:2]}:{hhmmss[2:4]}:{hhmmss[4:6]}Z"
    return NmeaFix(
        latitude=lat,
        longitude=lon,
        altitude_m=altitude,
        fix_quality=quality,
        satellites=satellites,
        hdop=hdop,
        utc_time=utc,
        geoid_separation_m=geoid,
    )


def parse_gsa(sentence: str) -> NmeaDop | None:
    """Parse GSA into fix type and PDOP/HDOP/VDOP."""
    line = sentence.strip()
    if not _nmea_checksum_ok(line):
        return None
    fields = line.split("*", 1)[0].split(",")
    if len(fields) < 18 or not fields[0].endswith("GSA"):
        return None
    try:
        fix_code = int(fields[2] or "1")
        pdop = float(fields[15] or "0")
        hdop = float(fields[16] or "0")
        vdop = float(fields[17] or "0")
    except ValueError:
        return None
    fix_type = {1: "none", 2: "2d", 3: "3d"}.get(fix_code, "none")
    prns: list[int] = []
    for raw in fields[3:15]:
        if not raw:
            continue
        try:
            prns.append(int(raw))
        except ValueError:
            continue
    return NmeaDop(
        fix_type=fix_type,
        pdop=pdop,
        hdop=hdop,
        vdop=vdop,
        prns=tuple(prns),
    )


def parse_vtg(sentence: str) -> NmeaVelocity | None:
    """Parse VTG into ground speed (m/s) and true course."""
    line = sentence.strip()
    if not _nmea_checksum_ok(line):
        return None
    fields = line.split("*", 1)[0].split(",")
    if len(fields) < 8 or not fields[0].endswith("VTG"):
        return None
    try:
        course = float(fields[1] or "0")
        # Prefer km/h (field 7) then knots (field 5).
        if fields[7]:
            speed_m_s = float(fields[7]) * (1000.0 / 3600.0)
        elif fields[5]:
            speed_m_s = float(fields[5]) * 0.514444
        else:
            return None
    except ValueError:
        return None
    return NmeaVelocity(speed_m_s=speed_m_s, course_deg=course)


def parse_rmc(sentence: str) -> tuple[str | None, NmeaVelocity | None, bool]:
    """Return ``(utc_iso, velocity, status_ok)`` from RMC."""
    line = sentence.strip()
    if not _nmea_checksum_ok(line):
        return None, None, False
    fields = line.split("*", 1)[0].split(",")
    if len(fields) < 10 or not fields[0].endswith("RMC"):
        return None, None, False
    status_ok = (fields[2] or "").upper() == "A"
    hhmmss = fields[1]
    ddmmyy = fields[9]
    utc_iso: str | None = None
    if len(hhmmss) >= 6 and len(ddmmyy) == 6:
        day = ddmmyy[0:2]
        month = ddmmyy[2:4]
        year = int(ddmmyy[4:6])
        year += 2000 if year < 80 else 1900
        utc_iso = (
            f"{year:04d}-{month}-{day}T{hhmmss[0:2]}:{hhmmss[2:4]}:{hhmmss[4:6]}Z"
        )
    velocity: NmeaVelocity | None = None
    try:
        if fields[7]:
            speed_m_s = float(fields[7]) * 0.514444
            course = float(fields[8] or "0")
            velocity = NmeaVelocity(speed_m_s=speed_m_s, course_deg=course)
    except ValueError:
        velocity = None
    return utc_iso, velocity, status_ok


def parse_rmc_utc_date(sentence: str) -> str | None:
    """Return ``YYYY-MM-DDTHH:MM:SSZ`` from RMC when date and time are present."""
    utc_iso, _, _ = parse_rmc(sentence)
    return utc_iso


def parse_gsv(sentence: str) -> list[tuple[int, float, float, float]]:
    """Parse one GSV sentence into ``(prn, elevation_deg, azimuth_deg, snr)`` rows."""
    return [
        (sat.prn, sat.elevation_deg, sat.azimuth_deg, sat.snr)
        for sat in parse_gsv_sats(sentence)
    ]


def parse_gsv_sats(sentence: str) -> list[NmeaSat]:
    """Parse one GSV sentence into satellite rows with constellation."""
    line = sentence.strip()
    if not _nmea_checksum_ok(line):
        return []
    fields = line.split("*", 1)[0].split(",")
    if len(fields) < 4 or not fields[0].endswith("GSV"):
        return []
    constellation = constellation_from_talker(_talker(fields[0]))
    signal_id: int | None = None
    # NMEA 4.11+ may append signal ID as last field after sat groups.
    sats: list[NmeaSat] = []
    idx = 4
    while idx + 3 < len(fields):
        # Stop if remaining looks like a lone signal-id field.
        if idx + 4 >= len(fields) and len(fields) - idx == 1:
            try:
                signal_id = int(fields[idx])
            except ValueError:
                pass
            break
        prn_raw, elev_raw, az_raw, snr_raw = fields[idx : idx + 4]
        idx += 4
        if not prn_raw:
            continue
        try:
            prn = int(prn_raw)
            elev = float(elev_raw or "0")
            az = float(az_raw or "0")
            snr = float(snr_raw or "0")
        except ValueError:
            continue
        sats.append(
            NmeaSat(
                prn=prn,
                elevation_deg=elev,
                azimuth_deg=az,
                snr=snr,
                constellation=constellation,
                signal_id=signal_id,
            ),
        )
    return sats
