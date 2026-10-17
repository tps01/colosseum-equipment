"""Minimal NMEA 0183 GGA / RMC parsing for GNSS position."""

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
    except ValueError:
        return None
    lat = _dm_to_degrees(fields[2], fields[3])
    lon = _dm_to_degrees(fields[4], fields[5])
    if lat is None or lon is None:
        return None
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
    )


def parse_rmc_utc_date(sentence: str) -> str | None:
    """Return ``YYYY-MM-DDTHH:MM:SSZ`` from RMC when date and time are present."""
    line = sentence.strip()
    if not _nmea_checksum_ok(line):
        return None
    fields = line.split("*", 1)[0].split(",")
    if len(fields) < 10 or not fields[0].endswith("RMC"):
        return None
    hhmmss = fields[1]
    ddmmyy = fields[9]
    if len(hhmmss) < 6 or len(ddmmyy) != 6:
        return None
    day = ddmmyy[0:2]
    month = ddmmyy[2:4]
    year = int(ddmmyy[4:6])
    year += 2000 if year < 80 else 1900
    return f"{year:04d}-{month}-{day}T{hhmmss[0:2]}:{hhmmss[2:4]}:{hhmmss[4:6]}Z"


def parse_gsv(sentence: str) -> list[tuple[int, float, float, float]]:
    """Parse one GSV sentence into ``(prn, elevation_deg, azimuth_deg, snr)`` rows."""
    line = sentence.strip()
    if not _nmea_checksum_ok(line):
        return []
    fields = line.split("*", 1)[0].split(",")
    if len(fields) < 4 or not fields[0].endswith("GSV"):
        return []
    sats: list[tuple[int, float, float, float]] = []
    # After talker,numMsg,msgNum,numSV come groups of prn,elev,az,snr.
    idx = 4
    while idx + 3 < len(fields):
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
        sats.append((prn, elev, az, snr))
    return sats
