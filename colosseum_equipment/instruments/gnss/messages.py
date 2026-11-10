"""Vendor-neutral GNSS message profiles and logical evidence ids.

Profiles (``default`` / ``nmea`` / ``field`` / ``sat`` / ``all``) are the same
names for every receiver; each driver maps them to vendor enable specs
(name + rate + trigger). Multi-row logging uses logical ids (``gnss_pvt``, …);
aliases such as ``UbloxNavPVT`` / ``BESTPOSB`` / ``PVTGeodetic`` resolve to
those ids for verifies.

Normalized evidence payloads (via ``_record_message_epoch``) include
``vendor_message``, ``model``, ``logging_key``, ``gnss_id`` plus shared numeric
fields where available (``latitude``, ``longitude``, ``altitude_m``,
``h_acc_m``, ``v_acc_m``, DOP scalars, ``num_svs``, status ints). Sat lists use
``{gnssId, svId, cno, elev, azim, flags?}`` with u-blox constellation ids
(GPS=0, SBAS=1, GAL=2, BDS=3, QZSS=5, GLO=6).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

MESSAGE_PROFILES: Final[tuple[str, ...]] = ("default", "nmea", "field", "sat", "all")

# Logical evidence command ids (DB measurement.command)
LOGICAL_PVT = "gnss_pvt"
LOGICAL_DOP = "gnss_dop"
LOGICAL_STATUS = "gnss_status"
LOGICAL_POSECEF = "gnss_posecef"
LOGICAL_TIME = "gnss_time"
LOGICAL_CLOCK = "gnss_clock"
LOGICAL_SAT = "gnss_sat"
LOGICAL_MEASX = "gnss_measx"
LOGICAL_RAWX = "gnss_rawx"

# Constellation name → u-blox-style gnssId (project standard for verify_sat_*).
CONSTELLATION_GNSS_ID: Final[dict[str, int]] = {
    "GPS": 0,
    "SBAS": 1,
    "GALILEO": 2,
    "GAL": 2,
    "BEIDOU": 3,
    "BDS": 3,
    "QZSS": 5,
    "GLONASS": 6,
    "GLO": 6,
}


@dataclass(frozen=True)
class MessageEnableSpec:
    """One vendor message to enable for a profile."""

    name: str
    rate_hz: float = 1.0
    trigger: str = "ontime"  # ontime | onchanged


def _spec(name: str, rate_hz: float = 1.0, trigger: str = "ontime") -> MessageEnableSpec:
    return MessageEnableSpec(name=name, rate_hz=rate_hz, trigger=trigger)


# alias (upper, normalized) -> logical id
_MESSAGE_ALIASES: dict[str, str] = {
    "GNSS_PVT": LOGICAL_PVT,
    "GNSS-PVT": LOGICAL_PVT,
    "NAV-PVT": LOGICAL_PVT,
    "UBLOXNAVPVT": LOGICAL_PVT,
    "UBLOX-NAV-PVT": LOGICAL_PVT,
    "BESTPOS": LOGICAL_PVT,
    "BESTPOSB": LOGICAL_PVT,
    "BESTPOSA": LOGICAL_PVT,
    "NOVATELBESTPOS": LOGICAL_PVT,
    "PVTGEODETIC": LOGICAL_PVT,
    "SEPTENTRIOPVTGEODETIC": LOGICAL_PVT,
    "GNSS_DOP": LOGICAL_DOP,
    "GNSS-DOP": LOGICAL_DOP,
    "NAV-DOP": LOGICAL_DOP,
    "UBLOXNAVDOP": LOGICAL_DOP,
    "UBLOX-NAV-DOP": LOGICAL_DOP,
    "PSRDOP": LOGICAL_DOP,
    "PSRDOPB": LOGICAL_DOP,
    "PSRDOPA": LOGICAL_DOP,
    "DOP": LOGICAL_DOP,
    "SEPTENTRIODOP": LOGICAL_DOP,
    "GNSS_STATUS": LOGICAL_STATUS,
    "GNSS-STATUS": LOGICAL_STATUS,
    "NAV-STATUS": LOGICAL_STATUS,
    "UBLOXNAVSTATUS": LOGICAL_STATUS,
    "UBLOX-NAV-STATUS": LOGICAL_STATUS,
    "RXSTATUS": LOGICAL_STATUS,
    "RXSTATUSB": LOGICAL_STATUS,
    "RXSTATUSA": LOGICAL_STATUS,
    "RECEIVERSTATUS": LOGICAL_STATUS,
    "GNSS_POSECEF": LOGICAL_POSECEF,
    "GNSS-POSECEF": LOGICAL_POSECEF,
    "NAV-POSECEF": LOGICAL_POSECEF,
    "UBLOXNAVPOSECEF": LOGICAL_POSECEF,
    "UBLOX-NAV-POSECEF": LOGICAL_POSECEF,
    "BESTXYZ": LOGICAL_POSECEF,
    "BESTXYZB": LOGICAL_POSECEF,
    "BESTXYZA": LOGICAL_POSECEF,
    "PVTCARTESIAN": LOGICAL_POSECEF,
    "GNSS_TIME": LOGICAL_TIME,
    "GNSS-TIME": LOGICAL_TIME,
    "NAV-TIMEGPS": LOGICAL_TIME,
    "UBLOXNAVTIMEGPS": LOGICAL_TIME,
    "UBLOX-NAV-TIMEGPS": LOGICAL_TIME,
    "TIME": LOGICAL_TIME,
    "TIMEB": LOGICAL_TIME,
    "TIMEA": LOGICAL_TIME,
    "RECEIVERTIME": LOGICAL_TIME,
    "GNSS_CLOCK": LOGICAL_CLOCK,
    "GNSS-CLOCK": LOGICAL_CLOCK,
    "NAV-CLOCK": LOGICAL_CLOCK,
    "UBLOXNAVCLOCK": LOGICAL_CLOCK,
    "UBLOX-NAV-CLOCK": LOGICAL_CLOCK,
    "CLOCKMODEL": LOGICAL_CLOCK,
    "CLOCKMODELB": LOGICAL_CLOCK,
    "CLOCKMODELA": LOGICAL_CLOCK,
    "GNSS_SAT": LOGICAL_SAT,
    "GNSS-SAT": LOGICAL_SAT,
    "NAV-SAT": LOGICAL_SAT,
    "UBLOXNAVSAT": LOGICAL_SAT,
    "UBLOX-NAV-SAT": LOGICAL_SAT,
    "GSV": LOGICAL_SAT,
    "GPGSV": LOGICAL_SAT,
    "GLGSV": LOGICAL_SAT,
    "GAGSV": LOGICAL_SAT,
    "GBGSV": LOGICAL_SAT,
    "SATVIS2": LOGICAL_SAT,
    "SATVIS2B": LOGICAL_SAT,
    "SATVIS2A": LOGICAL_SAT,
    "SATVISIBILITY": LOGICAL_SAT,
    "TRACKSTAT": LOGICAL_SAT,
    "TRACKSTATB": LOGICAL_SAT,
    "CHANNELSTATUS": LOGICAL_SAT,
    "GNSS_MEASX": LOGICAL_MEASX,
    "GNSS-MEASX": LOGICAL_MEASX,
    "RXM-MEASX": LOGICAL_MEASX,
    "UBLOXRXMMEASX": LOGICAL_MEASX,
    "UBLOX-RXM-MEASX": LOGICAL_MEASX,
    "MEASEPOCH": LOGICAL_MEASX,
    "GNSS_RAWX": LOGICAL_RAWX,
    "GNSS-RAWX": LOGICAL_RAWX,
    "RXM-RAWX": LOGICAL_RAWX,
    "UBLOXRXMRAWX": LOGICAL_RAWX,
    "UBLOX-RXM-RAWX": LOGICAL_RAWX,
    "RANGE": LOGICAL_RAWX,
    "RANGEB": LOGICAL_RAWX,
    "RANGEA": LOGICAL_RAWX,
}

VENDOR_PROFILE_SPECS: dict[str, dict[str, tuple[MessageEnableSpec, ...]]] = {
    "ublox": {
        "default": (
            _spec("NAV-PVT"),
            _spec("NAV-DOP"),
            _spec("NMEA-GSV"),
        ),
        "nmea": (
            _spec("NAV-PVT"),
            _spec("NAV-DOP"),
            _spec("NMEA-GGA"),
            _spec("NMEA-RMC"),
            _spec("NMEA-GSA"),
            _spec("NMEA-GSV"),
            _spec("NMEA-VTG"),
        ),
        "field": (
            _spec("NAV-PVT"),
            _spec("NAV-DOP"),
            _spec("NMEA-GSV"),
            _spec("NAV-POSECEF"),
            _spec("NAV-TIMEGPS"),
            _spec("NAV-CLOCK"),
            _spec("NAV-STATUS"),
        ),
        "sat": (
            _spec("NAV-PVT"),
            _spec("NAV-DOP"),
            _spec("NMEA-GSV"),
            _spec("NAV-SAT"),
            _spec("RXM-MEASX"),
            _spec("RXM-RAWX"),
        ),
        "all": (
            _spec("NAV-PVT"),
            _spec("NAV-DOP"),
            _spec("NMEA-GGA"),
            _spec("NMEA-RMC"),
            _spec("NMEA-GSA"),
            _spec("NMEA-GSV"),
            _spec("NMEA-VTG"),
            _spec("NAV-POSECEF"),
            _spec("NAV-TIMEGPS"),
            _spec("NAV-CLOCK"),
            _spec("NAV-STATUS"),
            _spec("NAV-SAT"),
            _spec("RXM-MEASX"),
            _spec("RXM-RAWX"),
        ),
    },
    "novatel": {
        "default": (
            _spec("BESTPOSB"),
            _spec("PSRDOPB", trigger="onchanged"),
            _spec("GPGGA"),
            _spec("GPRMC"),
            _spec("GPGSV"),
        ),
        "nmea": (
            _spec("BESTPOSB"),
            _spec("PSRDOPB", trigger="onchanged"),
            _spec("GPGGA"),
            _spec("GPRMC"),
            _spec("GPGSA"),
            _spec("GPGSV"),
            _spec("GPVTG"),
        ),
        "field": (
            _spec("BESTPOSB"),
            _spec("PSRDOPB", trigger="onchanged"),
            _spec("GPGGA"),
            _spec("GPRMC"),
            _spec("GPGSV"),
            _spec("BESTXYZB"),
            _spec("TIMEB"),
            _spec("CLOCKMODELB"),
            _spec("RXSTATUSB", trigger="onchanged"),
        ),
        "sat": (
            _spec("BESTPOSB"),
            _spec("PSRDOPB", trigger="onchanged"),
            _spec("GPGGA"),
            _spec("GPRMC"),
            _spec("GPGSV"),
            _spec("SATVIS2B", rate_hz=1.0 / 30.0),
            _spec("TRACKSTATB"),
            _spec("RANGEB"),
        ),
        "all": (
            _spec("BESTPOSB"),
            _spec("PSRDOPB", trigger="onchanged"),
            _spec("GPGGA"),
            _spec("GPRMC"),
            _spec("GPGSA"),
            _spec("GPGSV"),
            _spec("GPVTG"),
            _spec("BESTXYZB"),
            _spec("TIMEB"),
            _spec("CLOCKMODELB"),
            _spec("RXSTATUSB", trigger="onchanged"),
            _spec("SATVIS2B", rate_hz=1.0 / 30.0),
            _spec("TRACKSTATB"),
            _spec("RANGEB"),
        ),
    },
    "septentrio": {
        "default": (
            _spec("GGA"),
            _spec("RMC"),
            _spec("GSV"),
            _spec("PVTGeodetic"),
            _spec("DOP"),
        ),
        "nmea": (
            _spec("GGA"),
            _spec("RMC"),
            _spec("GSA"),
            _spec("GSV"),
            _spec("VTG"),
            _spec("PVTGeodetic"),
            _spec("DOP"),
        ),
        "field": (
            _spec("GGA"),
            _spec("RMC"),
            _spec("GSV"),
            _spec("PVTGeodetic"),
            _spec("DOP"),
            _spec("PVTCartesian"),
            _spec("ReceiverTime"),
            _spec("ReceiverStatus"),
        ),
        "sat": (
            _spec("GGA"),
            _spec("RMC"),
            _spec("GSV"),
            _spec("PVTGeodetic"),
            _spec("DOP"),
            _spec("SatVisibility"),
            _spec("ChannelStatus"),
            _spec("MeasEpoch"),
        ),
        "all": (
            _spec("GGA"),
            _spec("RMC"),
            _spec("GSA"),
            _spec("GSV"),
            _spec("VTG"),
            _spec("PVTGeodetic"),
            _spec("DOP"),
            _spec("PVTCartesian"),
            _spec("ReceiverTime"),
            _spec("ReceiverStatus"),
            _spec("SatVisibility"),
            _spec("ChannelStatus"),
            _spec("MeasEpoch"),
        ),
    },
}

# Backward-compatible name-only sketch (derived from specs).
VENDOR_PROFILE_SKETCH: dict[str, dict[str, tuple[str, ...]]] = {
    vendor: {profile: tuple(spec.name for spec in specs) for profile, specs in profiles.items()}
    for vendor, profiles in VENDOR_PROFILE_SPECS.items()
}


def normalize_message_alias(message: str) -> str:
    """Uppercase alias key without spaces; keep hyphens for NAV-* lookup."""
    raw = message.strip().upper().replace(" ", "")
    compact = raw.replace("_", "").replace("-", "")
    if raw in _MESSAGE_ALIASES:
        return raw
    if compact in _MESSAGE_ALIASES:
        return compact
    return message.strip().upper().replace("_", "-")


def resolve_logical_message(message: str) -> str:
    """Resolve a user/vendor message name to a logical evidence id.

    :raises KeyError: Unknown message alias.
    """
    raw = message.strip().upper().replace(" ", "")
    hyphen = message.strip().upper().replace("_", "-")
    compact = raw.replace("_", "").replace("-", "")
    for key in (hyphen, raw, compact, hyphen.replace("-", "")):
        hit = _MESSAGE_ALIASES.get(key)
        if hit is not None:
            return hit
        hit = _MESSAGE_ALIASES.get(key.replace("-", ""))
        if hit is not None:
            return hit
    raise KeyError(message)


def expand_profile_specs(profile: str, vendor: str = "ublox") -> tuple[MessageEnableSpec, ...]:
    """Return vendor enable specs for a profile (deduped by name, stable order)."""
    name = profile.strip().lower()
    if name not in MESSAGE_PROFILES:
        raise ValueError(f"unknown message profile {profile!r}; expected one of {MESSAGE_PROFILES}")
    maps = VENDOR_PROFILE_SPECS.get(vendor.lower()) or VENDOR_PROFILE_SPECS["ublox"]
    return maps[name]


def expand_profile(profile: str, vendor: str = "ublox") -> tuple[str, ...]:
    """Return vendor message names for a profile (deduped, stable order)."""
    return tuple(spec.name for spec in expand_profile_specs(profile, vendor=vendor))


def constellation_to_gnss_id(constellation: str) -> int:
    """Map a constellation name to the project-standard gnssId."""
    return CONSTELLATION_GNSS_ID.get(constellation.strip().upper(), 0)
