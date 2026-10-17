"""GNSS receiver APIs (``col.equipment.gnss``)."""

from __future__ import annotations

from colosseum.decorators import command, measurement

from colosseum_equipment.connections import get_cached_instrument


@command
def wait_for_fix(*, gnss_id: int, timeout_s: float) -> None:
    """Block until the receiver reports a valid fix or ``timeout_s`` elapses.

    :param gnss_id: Configured ``equipment.gnss`` id from config TOML.
    :type gnss_id: int
    :param timeout_s: Maximum seconds to wait for a fix.
    :type timeout_s: float

    :returns: None

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentTimeoutError: No fix within ``timeout_s``.
    """
    get_cached_instrument("gnss", gnss_id).wait_for_fix(timeout_s)


@command
def cold_start(*, gnss_id: int) -> None:
    """Clear navigation data and force a cold acquisition (vendor-specific).

    :param gnss_id: Configured ``equipment.gnss`` id from config TOML.
    :type gnss_id: int

    :returns: None

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Model does not support cold start.
    """
    get_cached_instrument("gnss", gnss_id).cold_start()


@command
def start_logging(*, gnss_id: int, path: str) -> None:
    """Start a background listen thread that logs raw messages and track CSV.

    While logging, only the listener reads the transport; ``wait_for_fix`` and
    measurements use the shared in-memory fix. Writes ``path`` (raw text log) and
    a sibling ``*_track.csv`` under the run output directory.

    :param gnss_id: Configured ``equipment.gnss`` id from config TOML.
    :type gnss_id: int
    :param path: Relative artifact path (for example ``gnss/session.nmea``).
    :type path: str

    :returns: None

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    """
    get_cached_instrument("gnss", gnss_id).start_logging(path)


@command
def stop_logging(*, gnss_id: int) -> None:
    """Stop the background listener and flush log files.

    :param gnss_id: Configured ``equipment.gnss`` id from config TOML.
    :type gnss_id: int

    :returns: None
    """
    get_cached_instrument("gnss", gnss_id).stop_logging()


@command
def save_track_plot(*, gnss_id: int, path: str) -> None:
    """Save a lat/lon track PNG from the current logged session.

    :param gnss_id: Configured ``equipment.gnss`` id from config TOML.
    :type gnss_id: int
    :param path: Relative PNG path under the run directory.
    :type path: str

    :returns: None
    """
    get_cached_instrument("gnss", gnss_id).save_track_plot(path)


@command
def save_skyplot(*, gnss_id: int, path: str) -> None:
    """Save a polar skyplot PNG from the latest GSV snapshot.

    :param gnss_id: Configured ``equipment.gnss`` id from config TOML.
    :type gnss_id: int
    :param path: Relative PNG path under the run directory.
    :type path: str

    :returns: None
    """
    get_cached_instrument("gnss", gnss_id).save_skyplot(path)


@command
def save_quality_plot(*, gnss_id: int, path: str) -> None:
    """Save an HDOP and satellite-count vs sample-index PNG.

    :param gnss_id: Configured ``equipment.gnss`` id from config TOML.
    :type gnss_id: int
    :param path: Relative PNG path under the run directory.
    :type path: str

    :returns: None
    """
    get_cached_instrument("gnss", gnss_id).save_quality_plot(path)


@measurement
def measure_latitude(*, gnss_id: int, key: str) -> float:
    """Measure latitude in decimal degrees.

    :param gnss_id: Configured ``equipment.gnss`` id from config TOML.
    :type gnss_id: int
    :param key: Unique measurement key within domain ``equipment``.
    :type key: str

    :returns: Latitude in degrees.
    :rtype: float
    """
    _ = key
    return float(get_cached_instrument("gnss", gnss_id).measure_latitude())


@measurement
def measure_longitude(*, gnss_id: int, key: str) -> float:
    """Measure longitude in decimal degrees.

    :param gnss_id: Configured ``equipment.gnss`` id from config TOML.
    :type gnss_id: int
    :param key: Unique measurement key within domain ``equipment``.
    :type key: str

    :returns: Longitude in degrees.
    :rtype: float
    """
    _ = key
    return float(get_cached_instrument("gnss", gnss_id).measure_longitude())


@measurement
def measure_altitude_m(*, gnss_id: int, key: str) -> float:
    """Measure altitude in meters (MSL when the model reports it).

    :param gnss_id: Configured ``equipment.gnss`` id from config TOML.
    :type gnss_id: int
    :param key: Unique measurement key within domain ``equipment``.
    :type key: str

    :returns: Altitude in meters.
    :rtype: float
    """
    _ = key
    return float(get_cached_instrument("gnss", gnss_id).measure_altitude_m())


@measurement
def measure_fix_quality(*, gnss_id: int, key: str) -> float:
    """Measure fix quality (NMEA GGA quality or UBX fix type when available).

    :param gnss_id: Configured ``equipment.gnss`` id from config TOML.
    :type gnss_id: int
    :param key: Unique measurement key within domain ``equipment``.
    :type key: str

    :returns: Fix quality code as float.
    :rtype: float
    """
    _ = key
    return float(get_cached_instrument("gnss", gnss_id).measure_fix_quality())


@measurement
def measure_satellites(*, gnss_id: int, key: str) -> float:
    """Measure the number of satellites used in the solution.

    :param gnss_id: Configured ``equipment.gnss`` id from config TOML.
    :type gnss_id: int
    :param key: Unique measurement key within domain ``equipment``.
    :type key: str

    :returns: Satellite count.
    :rtype: float
    """
    _ = key
    return float(get_cached_instrument("gnss", gnss_id).measure_satellites())


@measurement
def measure_hdop(*, gnss_id: int, key: str) -> float:
    """Measure horizontal dilution of precision.

    :param gnss_id: Configured ``equipment.gnss`` id from config TOML.
    :type gnss_id: int
    :param key: Unique measurement key within domain ``equipment``.
    :type key: str

    :returns: HDOP (or PDOP/100 from UBX NAV-PVT when that is the source).
    :rtype: float
    """
    _ = key
    return float(get_cached_instrument("gnss", gnss_id).measure_hdop())


@measurement
def measure_utc_time(*, gnss_id: int, key: str) -> str:
    """Measure UTC time as an ISO-8601 string when available.

    :param gnss_id: Configured ``equipment.gnss`` id from config TOML.
    :type gnss_id: int
    :param key: Unique measurement key within domain ``equipment``.
    :type key: str

    :returns: UTC timestamp string.
    :rtype: str
    """
    _ = key
    return str(get_cached_instrument("gnss", gnss_id).measure_utc_time())
