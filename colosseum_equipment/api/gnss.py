"""GNSS receiver APIs (``col.equipment.gnss``)."""

from __future__ import annotations

from typing import Any

from colosseum.context import get_context
from colosseum.decorators import VerificationResult, command, measurement, verification
from colosseum.logging import get_logger

from colosseum_equipment.api._broadcast import EquipmentId, broadcastable, require_int_id
from colosseum_equipment.api._verify import limit_verifier, minimum_verifier, tolerance_verifier
from colosseum_equipment.connections import get_cached_instrument
from colosseum_equipment.instruments.gnss.messages import resolve_logical_message

_logger = get_logger("colosseum.equipment")


@command
def wait_for_fix(*, gnss_id: int, timeout_s: float) -> None:
    """Block until the receiver reports a valid fix or ``timeout_s`` elapses.

    :param gnss_id: Integer ID from the configured equipment.gnss row. Select an existing ID in
        that section.
    :param timeout_s: Maximum wait in seconds. Expiration does not establish that the operation
        completed.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _logger.info("Waiting up to %s s for a fix on GNSS %s", timeout_s, gnss_id)
    get_cached_instrument('gnss', require_int_id(gnss_id, kind='gnss')).wait_for_fix(timeout_s)


@command
@broadcastable("gnss", "gnss_id")
def cold_start(*, gnss_id: EquipmentId) -> None:
    """Clear navigation data and force a cold acquisition (vendor-specific).

    :param gnss_id: Integer ID from the configured equipment.gnss row. Select an existing ID in
        that section.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _logger.info("Cold starting GNSS %s", gnss_id)
    get_cached_instrument('gnss', require_int_id(gnss_id, kind='gnss')).cold_start()


@command
@broadcastable("gnss", "gnss_id")
def mark_acquisition_start(*, gnss_id: EquipmentId) -> None:
    """Mark T0 for TTFF measurement without issuing a cold start.

    :param gnss_id: Integer ID from the configured equipment.gnss row. Select an existing ID in
        that section.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _logger.info("Marking acquisition start on GNSS %s", gnss_id)
    get_cached_instrument('gnss', require_int_id(gnss_id, kind='gnss')).mark_acquisition_start()


@command
@broadcastable("gnss", "gnss_id")
def load_config(*, gnss_id: EquipmentId, path: str) -> None:
    """Apply a vendor configuration file to the receiver.

    u-blox: u-center GNSS Configuration ``.txt`` (legacy CFG and/or CFG-VALGET)
    or binary ``.ubx``. NovAtel/Septentrio: ASCII command scripts.
    Prefer calling while logging is stopped.

    :param gnss_id: Integer ID from the configured equipment.gnss row. Select an existing ID in
        that section.
    :param path: Existing input file path, absolute or relative to the process working
        directory.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _logger.info("Loading GNSS %s config from %s", gnss_id, path)
    get_cached_instrument('gnss', require_int_id(gnss_id, kind='gnss')).load_config(path)


@command
def save_config(*, gnss_id: int, path: str) -> None:
    """Export the configuration subset supported by this receiver driver.

    u-blox polls the supported CFG messages/keys; it is not an exhaustive
    receiver backup. NovAtel and Septentrio export driver-managed log/stream
    state, not arbitrary receiver settings or all previously loaded commands.
    The exported subset can be passed to ``load_config``. Prefer calling
    while logging is stopped. Saves an artifact under the run directory;
    requires artifacts enabled.

    :param gnss_id: Integer ID from the configured equipment.gnss row. Select an existing ID in
        that section.
    :param path: Destination file path, absolute or relative to the active run output directory;
        requires artifacts enabled.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _logger.info("Saving GNSS %s config to %s", gnss_id, path)
    get_cached_instrument('gnss', require_int_id(gnss_id, kind='gnss')).save_config(path)


@command
@broadcastable("gnss", "gnss_id")
def set_message_rate(*, gnss_id: EquipmentId, message: str, rate_hz: float) -> None:
    """Enable/disable or set the rate of a named receiver message.

    ``rate_hz=0`` disables. Examples: ``NAV-SAT``, ``BESTPOSB``, ``PVTGeodetic``.

    :param gnss_id: Integer ID from the configured equipment.gnss row. Select an existing ID in
        that section.
    :param message: Receiver message name, such as NAV-SAT, BESTPOSB, or PVTGeodetic; supported
        names depend on the receiver.
    :param rate_hz: Message frequency in hertz; zero disables the message. Supported rates
        depend on the receiver.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _logger.info("Setting message %s rate on GNSS %s to %s Hz", message, gnss_id, rate_hz)
    get_cached_instrument('gnss', require_int_id(gnss_id, kind='gnss')).set_message_rate(message, rate_hz)


@command
@broadcastable("gnss", "gnss_id")
def set_message_profile(*, gnss_id: EquipmentId, messages: str = "default") -> None:
    """Enable a named message profile (``default`` / ``nmea`` / ``field`` / ``sat`` / ``all``).

    :param gnss_id: Integer ID from the configured equipment.gnss row.
    :param messages: Profile name. Default ``default`` is the light fix/DOP/sky baseline.
    """
    _logger.info("Setting message profile on GNSS %s to %s", gnss_id, messages)
    get_cached_instrument('gnss', require_int_id(gnss_id, kind='gnss')).set_message_profile(messages)


@command
def start_logging(*, gnss_id: int, path: str, key: str = "", messages: str = "default") -> None:
    """Start background logging of raw messages, binary wire capture, track CSV, and DB epochs.

    Writes a decoded text log at ``path``, a binary wire sidecar
    (``{stem}_wire.ubx`` / ``.gps`` / ``.sbf`` / ``.bin``), and ``{stem}_track.csv``.
    ``key`` identifies the logging window for evidence rows.
    ``messages`` selects a vendor message profile (``default`` / ``nmea`` / ``field`` /
    ``sat`` / ``all``).

    :param gnss_id: Integer ID from the configured equipment.gnss row. Select an existing ID in
        that section.
    :param path: Destination file path, absolute or relative to the active run output directory;
        requires artifacts enabled.
    :param key: Evidence key for this operation. Keep distinct keys for separate facts; see the
        evidence lookup rules in the core guide. Default: ``''``.
    :param messages: Message enable profile applied when arming streams. Default: ``default``.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _logger.info("Starting GNSS %s logging to %s (%s)", gnss_id, path, messages)
    get_cached_instrument('gnss', require_int_id(gnss_id, kind='gnss')).start_logging(
        path, key=key, messages=messages,
    )


@command
@broadcastable("gnss", "gnss_id")
def stop_logging(*, gnss_id: EquipmentId) -> None:
    """Stop the listener, emit continuity summaries, and close log files.

    :param gnss_id: Integer ID from the configured equipment.gnss row. Select an existing ID in
        that section.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _logger.info("Stopping logging on GNSS %s", gnss_id)
    get_cached_instrument('gnss', require_int_id(gnss_id, kind='gnss')).stop_logging()


@command
def save_track_plot(*, gnss_id: int, path: str) -> None:
    """Save a lat/lon track PNG from the current logged session.

    :param gnss_id: Integer ID from the configured equipment.gnss row. Select an existing ID in
        that section.
    :param path: Destination file path, absolute or relative to the active run output directory;
        requires artifacts enabled.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _logger.info("Saving track plot from GNSS %s to %s", gnss_id, path)
    get_cached_instrument('gnss', require_int_id(gnss_id, kind='gnss')).save_track_plot(path)


@command
def save_skyplot(*, gnss_id: int, path: str) -> None:
    """Save a polar skyplot PNG (marker size/color from C/N0).

    :param gnss_id: Integer ID from the configured equipment.gnss row. Select an existing ID in
        that section.
    :param path: Destination file path, absolute or relative to the active run output directory;
        requires artifacts enabled.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _logger.info("Saving sky plot from GNSS %s to %s", gnss_id, path)
    get_cached_instrument('gnss', require_int_id(gnss_id, kind='gnss')).save_skyplot(path)


@command
def save_quality_plot(*, gnss_id: int, path: str) -> None:
    """Save DOP / satellite / C/N0 quality PNG.

    :param gnss_id: Integer ID from the configured equipment.gnss row. Select an existing ID in
        that section.
    :param path: Destination file path, absolute or relative to the active run output directory;
        requires artifacts enabled.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _logger.info("Saving quality plot from GNSS %s to %s", gnss_id, path)
    get_cached_instrument('gnss', require_int_id(gnss_id, kind='gnss')).save_quality_plot(path)


@command
def save_signal_levels_plot(*, gnss_id: int, path: str) -> None:
    """Save a per-satellite C/N0 bar chart from the current sky snapshot.

    :param gnss_id: Integer ID from the configured equipment.gnss row.
    :param path: Destination PNG path under the run output directory.
    """
    _logger.info("Saving signal-level plot from GNSS %s to %s", gnss_id, path)
    get_cached_instrument('gnss', require_int_id(gnss_id, kind='gnss')).save_signal_levels_plot(path)


@command
def save_deviation_plot(
    *,
    gnss_id: int,
    path: str,
    ref_lat: float | None = None,
    ref_lon: float | None = None,
) -> None:
    """Save an east/north deviation scatter about mean or a supplied reference.

    :param gnss_id: Integer ID from the configured equipment.gnss row.
    :param path: Destination PNG path under the run output directory.
    :param ref_lat: Optional reference latitude (deg). Default: mean of fix samples.
    :param ref_lon: Optional reference longitude (deg). Default: mean of fix samples.
    """
    _logger.info("Saving deviation plot from GNSS %s to %s", gnss_id, path)
    get_cached_instrument('gnss', require_int_id(gnss_id, kind='gnss')).save_deviation_plot(
        path, ref_lat=ref_lat, ref_lon=ref_lon,
    )


@command
def get_satellite_snapshot(*, gnss_id: int, max_age_s: float = 5.0) -> list[dict[str, Any]]:
    """Return the current sky view (works without a position fix).

    :param gnss_id: Integer ID from the configured equipment.gnss row. Select an existing ID in
        that section.
    :param max_age_s: Maximum age in seconds of cached receiver data; default 5 seconds. Stale
        or unavailable data cannot establish a current fix.

    :returns: List of satellite dictionaries with identity, elevation/azimuth, C/N0, used-in-fix
        flag, and data age.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _logger.info("Reading satellite snapshot from GNSS %s", gnss_id)
    return list(
        get_cached_instrument('gnss', require_int_id(gnss_id, kind='gnss')).get_satellite_snapshot(max_age_s=max_age_s),
    )


@command
def get_fix_type(*, gnss_id: int, max_age_s: float = 5.0) -> str:
    """Return fix type string: ``none`` / ``2d`` / ``3d``.

    :param gnss_id: Integer ID from the configured equipment.gnss row. Select an existing ID in
        that section.
    :param max_age_s: Maximum age in seconds of cached receiver data; default 5 seconds. Stale
        or unavailable data cannot establish a current fix.

    :returns: Fix type string: none, 2d, or 3d.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _logger.info("Reading fix type from GNSS %s", gnss_id)
    return str(get_cached_instrument('gnss', require_int_id(gnss_id, kind='gnss')).get_fix_type(max_age_s=max_age_s))


@command
def get_constellations_present(*, gnss_id: int, max_age_s: float = 5.0) -> list[str]:
    """Return constellation names present in the recent sky view.

    :param gnss_id: Integer ID from the configured equipment.gnss row. Select an existing ID in
        that section.
    :param max_age_s: Maximum age in seconds of cached receiver data; default 5 seconds. Stale
        or unavailable data cannot establish a current fix.

    :returns: Sorted list of constellation names in the recent sky view.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _logger.info("Reading constellations from GNSS %s", gnss_id)
    return list(
        get_cached_instrument('gnss', require_int_id(gnss_id, kind='gnss')).get_constellations_present(max_age_s=max_age_s),
    )


@measurement
def measure_latitude(*, gnss_id: int, key: str, max_age_s: float = 5.0) -> float:
    """Measure latitude in decimal degrees (freshness-gated).

    :param gnss_id: Integer ID from the configured equipment.gnss row. Select an existing ID in
        that section.
    :param key: Evidence key for this operation. Keep distinct keys for separate facts; see the
        evidence lookup rules in the core guide.
    :param max_age_s: Maximum age in seconds of cached receiver data; default 5 seconds. Stale
        or unavailable data cannot establish a current fix.

    :returns: Recorded latitude in degrees north.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _logger.info("Reading latitude from GNSS %s", gnss_id)
    _ = key
    return float(get_cached_instrument('gnss', require_int_id(gnss_id, kind='gnss')).measure_latitude(max_age_s=max_age_s))


@measurement
def measure_longitude(*, gnss_id: int, key: str, max_age_s: float = 5.0) -> float:
    """Measure longitude in decimal degrees (freshness-gated).

    :param gnss_id: Integer ID from the configured equipment.gnss row. Select an existing ID in
        that section.
    :param key: Evidence key for this operation. Keep distinct keys for separate facts; see the
        evidence lookup rules in the core guide.
    :param max_age_s: Maximum age in seconds of cached receiver data; default 5 seconds. Stale
        or unavailable data cannot establish a current fix.

    :returns: Recorded longitude in degrees east.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _logger.info("Reading longitude from GNSS %s", gnss_id)
    _ = key
    return float(get_cached_instrument('gnss', require_int_id(gnss_id, kind='gnss')).measure_longitude(max_age_s=max_age_s))


@measurement
def measure_altitude_m(*, gnss_id: int, key: str, max_age_s: float = 5.0) -> float:
    """Measure altitude in meters MSL when reported.

    :param gnss_id: Integer ID from the configured equipment.gnss row. Select an existing ID in
        that section.
    :param key: Evidence key for this operation. Keep distinct keys for separate facts; see the
        evidence lookup rules in the core guide.
    :param max_age_s: Maximum age in seconds of cached receiver data; default 5 seconds. Stale
        or unavailable data cannot establish a current fix.

    :returns: Recorded altitude m in meters.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _logger.info("Reading altitude from GNSS %s", gnss_id)
    _ = key
    return float(get_cached_instrument('gnss', require_int_id(gnss_id, kind='gnss')).measure_altitude_m(max_age_s=max_age_s))


@measurement
def measure_fix_quality(*, gnss_id: int, key: str, max_age_s: float = 5.0) -> float:
    """Measure NMEA GGA quality / UBX fix type code.

    :param gnss_id: Integer ID from the configured equipment.gnss row. Select an existing ID in
        that section.
    :param key: Evidence key for this operation. Keep distinct keys for separate facts; see the
        evidence lookup rules in the core guide.
    :param max_age_s: Maximum age in seconds of cached receiver data; default 5 seconds. Stale
        or unavailable data cannot establish a current fix.

    :returns: Recorded NMEA quality or UBX fix-type code as a float; interpret it according to
        the receiver protocol.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _logger.info("Reading fix quality from GNSS %s", gnss_id)
    _ = key
    return float(get_cached_instrument('gnss', require_int_id(gnss_id, kind='gnss')).measure_fix_quality(max_age_s=max_age_s))


@measurement
def measure_satellites(*, gnss_id: int, key: str, max_age_s: float = 5.0) -> float:
    """Measure satellites used in the solution.

    :param gnss_id: Integer ID from the configured equipment.gnss row. Select an existing ID in
        that section.
    :param key: Evidence key for this operation. Keep distinct keys for separate facts; see the
        evidence lookup rules in the core guide.
    :param max_age_s: Maximum age in seconds of cached receiver data; default 5 seconds. Stale
        or unavailable data cannot establish a current fix.

    :returns: Recorded number of satellites used in the current solution, as a float.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _logger.info("Reading satellites used from GNSS %s", gnss_id)
    _ = key
    return float(get_cached_instrument('gnss', require_int_id(gnss_id, kind='gnss')).measure_satellites(max_age_s=max_age_s))


verify_satellites = minimum_verifier("measure_satellites", name="verify_satellites")


@measurement
def measure_satellites_visible(*, gnss_id: int, key: str, max_age_s: float = 5.0) -> float:
    """Measure satellites visible in the recent sky view (no fix required).

    :param gnss_id: Integer ID from the configured equipment.gnss row. Select an existing ID in
        that section.
    :param key: Evidence key for this operation. Keep distinct keys for separate facts; see the
        evidence lookup rules in the core guide.
    :param max_age_s: Maximum age in seconds of cached receiver data; default 5 seconds. Stale
        or unavailable data cannot establish a current fix.

    :returns: Recorded number of satellites in the recent sky view, as a float.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _logger.info("Reading visible satellites from GNSS %s", gnss_id)
    _ = key
    return float(
        get_cached_instrument('gnss', require_int_id(gnss_id, kind='gnss')).measure_satellites_visible(max_age_s=max_age_s),
    )


verify_satellites_visible = minimum_verifier(
    "measure_satellites_visible", name="verify_satellites_visible",
)


@measurement
def measure_hdop(*, gnss_id: int, key: str, max_age_s: float = 5.0) -> float:
    """Measure true horizontal dilution of precision (GSA / NAV-DOP / GGA).

    :param gnss_id: Integer ID from the configured equipment.gnss row. Select an existing ID in
        that section.
    :param key: Evidence key for this operation. Keep distinct keys for separate facts; see the
        evidence lookup rules in the core guide.
    :param max_age_s: Maximum age in seconds of cached receiver data; default 5 seconds. Stale
        or unavailable data cannot establish a current fix.

    :returns: Recorded horizontal dilution of precision (dimensionless).

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _logger.info("Reading HDOP from GNSS %s", gnss_id)
    _ = key
    return float(get_cached_instrument('gnss', require_int_id(gnss_id, kind='gnss')).measure_hdop(max_age_s=max_age_s))


verify_hdop = limit_verifier("measure_hdop", name="verify_hdop", upper=True)


@measurement
def measure_pdop(*, gnss_id: int, key: str, max_age_s: float = 5.0) -> float:
    """Measure position dilution of precision.

    :param gnss_id: Integer ID from the configured equipment.gnss row. Select an existing ID in
        that section.
    :param key: Evidence key for this operation. Keep distinct keys for separate facts; see the
        evidence lookup rules in the core guide.
    :param max_age_s: Maximum age in seconds of cached receiver data; default 5 seconds. Stale
        or unavailable data cannot establish a current fix.

    :returns: Recorded position dilution of precision (dimensionless).

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _logger.info("Reading PDOP from GNSS %s", gnss_id)
    _ = key
    return float(get_cached_instrument('gnss', require_int_id(gnss_id, kind='gnss')).measure_pdop(max_age_s=max_age_s))


verify_pdop = limit_verifier("measure_pdop", name="verify_pdop", upper=True)


@measurement
def measure_vdop(*, gnss_id: int, key: str, max_age_s: float = 5.0) -> float:
    """Measure vertical dilution of precision.

    :param gnss_id: Integer ID from the configured equipment.gnss row. Select an existing ID in
        that section.
    :param key: Evidence key for this operation. Keep distinct keys for separate facts; see the
        evidence lookup rules in the core guide.
    :param max_age_s: Maximum age in seconds of cached receiver data; default 5 seconds. Stale
        or unavailable data cannot establish a current fix.

    :returns: Recorded vertical dilution of precision (dimensionless).

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _logger.info("Reading VDOP from GNSS %s", gnss_id)
    _ = key
    return float(get_cached_instrument('gnss', require_int_id(gnss_id, kind='gnss')).measure_vdop(max_age_s=max_age_s))


verify_vdop = limit_verifier("measure_vdop", name="verify_vdop", upper=True)


@measurement
def measure_gdop(*, gnss_id: int, key: str, max_age_s: float = 5.0) -> float:
    """Measure geometric dilution of precision when the model reports it.

    :param gnss_id: Integer ID from the configured equipment.gnss row. Select an existing ID in
        that section.
    :param key: Evidence key for this operation. Keep distinct keys for separate facts; see the
        evidence lookup rules in the core guide.
    :param max_age_s: Maximum age in seconds of cached receiver data; default 5 seconds. Stale
        or unavailable data cannot establish a current fix.

    :returns: Recorded geometric dilution of precision (dimensionless).

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _logger.info("Reading GDOP from GNSS %s", gnss_id)
    _ = key
    return float(get_cached_instrument('gnss', require_int_id(gnss_id, kind='gnss')).measure_gdop(max_age_s=max_age_s))


verify_gdop = limit_verifier("measure_gdop", name="verify_gdop", upper=True)


@measurement
def measure_max_cn0_dbhz(*, gnss_id: int, key: str, max_age_s: float = 5.0) -> float:
    """Measure maximum C/N0 (dB-Hz) across the recent sky view.

    :param gnss_id: Integer ID from the configured equipment.gnss row. Select an existing ID in
        that section.
    :param key: Evidence key for this operation. Keep distinct keys for separate facts; see the
        evidence lookup rules in the core guide.
    :param max_age_s: Maximum age in seconds of cached receiver data; default 5 seconds. Stale
        or unavailable data cannot establish a current fix.

    :returns: Recorded max cn0 dbhz in dB-Hz.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _logger.info("Reading max C/N0 from GNSS %s", gnss_id)
    _ = key
    return float(get_cached_instrument('gnss', require_int_id(gnss_id, kind='gnss')).measure_max_cn0_dbhz(max_age_s=max_age_s))


verify_max_cn0_dbhz = minimum_verifier(
    "measure_max_cn0_dbhz", name="verify_max_cn0_dbhz", unit="dB-Hz",
)


@measurement
def measure_mean_cn0_dbhz(*, gnss_id: int, key: str, max_age_s: float = 5.0) -> float:
    """Measure mean C/N0 (dB-Hz) across satellites with SNR > 0.

    :param gnss_id: Integer ID from the configured equipment.gnss row. Select an existing ID in
        that section.
    :param key: Evidence key for this operation. Keep distinct keys for separate facts; see the
        evidence lookup rules in the core guide.
    :param max_age_s: Maximum age in seconds of cached receiver data; default 5 seconds. Stale
        or unavailable data cannot establish a current fix.

    :returns: Recorded mean cn0 dbhz in dB-Hz.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _logger.info("Reading mean C/N0 from GNSS %s", gnss_id)
    _ = key
    return float(get_cached_instrument('gnss', require_int_id(gnss_id, kind='gnss')).measure_mean_cn0_dbhz(max_age_s=max_age_s))


verify_mean_cn0_dbhz = minimum_verifier(
    "measure_mean_cn0_dbhz", name="verify_mean_cn0_dbhz", unit="dB-Hz",
)


@measurement
def measure_cn0_dbhz(
    *,
    gnss_id: int,
    key: str,
    prn: int,
    constellation: str = "GPS",
    max_age_s: float = 5.0,
) -> float:
    """Measure C/N0 for one PRN within a constellation.

    :param gnss_id: Integer ID from the configured equipment.gnss row. Select an existing ID in
        that section.
    :param key: Evidence key for this operation. Keep distinct keys for separate facts; see the
        evidence lookup rules in the core guide.
    :param prn: Satellite PRN identifier used by the receiver constellation.
    :param constellation: Constellation name used by the receiver; None allows any matching
        constellation. Default: ``'GPS'``.
    :param max_age_s: Maximum age in seconds of cached receiver data; default 5 seconds. Stale
        or unavailable data cannot establish a current fix.

    :returns: Recorded cn0 dbhz in dB-Hz.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _logger.info("Reading C/N0 from GNSS %s %s PRN %s", gnss_id, constellation, prn)
    _ = key
    return float(
        get_cached_instrument('gnss', require_int_id(gnss_id, kind='gnss')).measure_cn0_dbhz(
            prn, constellation=constellation, max_age_s=max_age_s,
        ),
    )


@measurement
def measure_speed_m_s(*, gnss_id: int, key: str, max_age_s: float = 5.0) -> float:
    """Measure ground speed in m/s from RMC/VTG/NAV-PVT.

    :param gnss_id: Integer ID from the configured equipment.gnss row. Select an existing ID in
        that section.
    :param key: Evidence key for this operation. Keep distinct keys for separate facts; see the
        evidence lookup rules in the core guide.
    :param max_age_s: Maximum age in seconds of cached receiver data; default 5 seconds. Stale
        or unavailable data cannot establish a current fix.

    :returns: Recorded speed m s in meters per second.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _logger.info("Reading speed from GNSS %s", gnss_id)
    _ = key
    return float(get_cached_instrument('gnss', require_int_id(gnss_id, kind='gnss')).measure_speed_m_s(max_age_s=max_age_s))


@measurement
def measure_course_deg(*, gnss_id: int, key: str, max_age_s: float = 5.0) -> float:
    """Measure true course in degrees.

    :param gnss_id: Integer ID from the configured equipment.gnss row. Select an existing ID in
        that section.
    :param key: Evidence key for this operation. Keep distinct keys for separate facts; see the
        evidence lookup rules in the core guide.
    :param max_age_s: Maximum age in seconds of cached receiver data; default 5 seconds. Stale
        or unavailable data cannot establish a current fix.

    :returns: Recorded course deg in degrees.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _logger.info("Reading course from GNSS %s", gnss_id)
    _ = key
    return float(get_cached_instrument('gnss', require_int_id(gnss_id, kind='gnss')).measure_course_deg(max_age_s=max_age_s))


@measurement
def measure_h_acc_m(*, gnss_id: int, key: str, max_age_s: float = 5.0) -> float:
    """Measure horizontal accuracy estimate in meters (binary protocols).

    :param gnss_id: Integer ID from the configured equipment.gnss row. Select an existing ID in
        that section.
    :param key: Evidence key for this operation. Keep distinct keys for separate facts; see the
        evidence lookup rules in the core guide.
    :param max_age_s: Maximum age in seconds of cached receiver data; default 5 seconds. Stale
        or unavailable data cannot establish a current fix.

    :returns: Recorded h acc m in meters.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _logger.info("Reading horizontal accuracy from GNSS %s", gnss_id)
    _ = key
    return float(get_cached_instrument('gnss', require_int_id(gnss_id, kind='gnss')).measure_h_acc_m(max_age_s=max_age_s))


verify_h_acc_m = limit_verifier("measure_h_acc_m", name="verify_h_acc_m", upper=True, unit="m")


@measurement
def measure_v_acc_m(*, gnss_id: int, key: str, max_age_s: float = 5.0) -> float:
    """Measure vertical accuracy estimate in meters (binary protocols).

    :param gnss_id: Integer ID from the configured equipment.gnss row. Select an existing ID in
        that section.
    :param key: Evidence key for this operation. Keep distinct keys for separate facts; see the
        evidence lookup rules in the core guide.
    :param max_age_s: Maximum age in seconds of cached receiver data; default 5 seconds. Stale
        or unavailable data cannot establish a current fix.

    :returns: Recorded v acc m in meters.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _logger.info("Reading vertical accuracy from GNSS %s", gnss_id)
    _ = key
    return float(get_cached_instrument('gnss', require_int_id(gnss_id, kind='gnss')).measure_v_acc_m(max_age_s=max_age_s))


verify_v_acc_m = limit_verifier("measure_v_acc_m", name="verify_v_acc_m", upper=True, unit="m")


@measurement
def measure_geoid_separation_m(*, gnss_id: int, key: str, max_age_s: float = 5.0) -> float:
    """Measure geoid separation in meters from GGA when present.

    :param gnss_id: Integer ID from the configured equipment.gnss row. Select an existing ID in
        that section.
    :param key: Evidence key for this operation. Keep distinct keys for separate facts; see the
        evidence lookup rules in the core guide.
    :param max_age_s: Maximum age in seconds of cached receiver data; default 5 seconds. Stale
        or unavailable data cannot establish a current fix.

    :returns: Recorded geoid separation m in meters.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _logger.info("Reading geoid separation from GNSS %s", gnss_id)
    _ = key
    return float(
        get_cached_instrument('gnss', require_int_id(gnss_id, kind='gnss')).measure_geoid_separation_m(max_age_s=max_age_s),
    )


@measurement
def measure_data_age_s(*, gnss_id: int, key: str) -> float:
    """Measure age of the cached fix in seconds.

    :param gnss_id: Integer ID from the configured equipment.gnss row. Select an existing ID in
        that section.
    :param key: Evidence key for this operation. Keep distinct keys for separate facts; see the
        evidence lookup rules in the core guide.

    :returns: Recorded data age s in seconds.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _logger.info("Reading data age from GNSS %s", gnss_id)
    _ = key
    return float(get_cached_instrument('gnss', require_int_id(gnss_id, kind='gnss')).measure_data_age_s())


@measurement
def measure_utc_time(*, gnss_id: int, key: str, max_age_s: float = 5.0) -> str:
    """Measure UTC time as an ISO-8601 string when available.

    :param gnss_id: Integer ID from the configured equipment.gnss row. Select an existing ID in
        that section.
    :param key: Evidence key for this operation. Keep distinct keys for separate facts; see the
        evidence lookup rules in the core guide.
    :param max_age_s: Maximum age in seconds of cached receiver data; default 5 seconds. Stale
        or unavailable data cannot establish a current fix.

    :returns: Recorded UTC time as an ISO-8601 string.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _logger.info("Reading UTC time from GNSS %s", gnss_id)
    _ = key
    return str(get_cached_instrument('gnss', require_int_id(gnss_id, kind='gnss')).measure_utc_time(max_age_s=max_age_s))


@measurement
def measure_ttff_s(*, gnss_id: int, key: str) -> float:
    """Measure time-to-first-fix since cold_start / mark_acquisition_start.

    :param gnss_id: Integer ID from the configured equipment.gnss row. Select an existing ID in
        that section.
    :param key: Evidence key for this operation. Keep distinct keys for separate facts; see the
        evidence lookup rules in the core guide.

    :returns: Recorded ttff s in seconds.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _logger.info("Reading time to first fix from GNSS %s", gnss_id)
    _ = key
    return float(get_cached_instrument('gnss', require_int_id(gnss_id, kind='gnss')).measure_ttff_s())


verify_ttff_s = limit_verifier("measure_ttff_s", name="verify_ttff_s", upper=True, unit="s")


@measurement
def measure_fix_availability(*, gnss_id: int, key: str) -> float:
    """Measure fraction of logging epochs with a valid fix (0..1).

    :param gnss_id: Integer ID from the configured equipment.gnss row. Select an existing ID in
        that section.
    :param key: Evidence key for this operation. Keep distinct keys for separate facts; see the
        evidence lookup rules in the core guide.

    :returns: Recorded fix availability in a fraction from 0 to 1.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _logger.info("Reading fix availability from GNSS %s", gnss_id)
    _ = key
    return float(get_cached_instrument('gnss', require_int_id(gnss_id, kind='gnss')).measure_fix_availability())


verify_fix_availability = minimum_verifier(
    "measure_fix_availability", name="verify_fix_availability",
)


@measurement
def measure_longest_outage_s(*, gnss_id: int, key: str) -> float:
    """Measure longest no-fix outage observed in the logging window.

    :param gnss_id: Integer ID from the configured equipment.gnss row. Select an existing ID in
        that section.
    :param key: Evidence key for this operation. Keep distinct keys for separate facts; see the
        evidence lookup rules in the core guide.

    :returns: Recorded longest outage s in seconds.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _logger.info("Reading longest outage from GNSS %s", gnss_id)
    _ = key
    return float(get_cached_instrument('gnss', require_int_id(gnss_id, kind='gnss')).measure_longest_outage_s())


verify_longest_outage_s = limit_verifier(
    "measure_longest_outage_s", name="verify_longest_outage_s", upper=True, unit="s",
)


@measurement
def measure_reacquisition_s(*, gnss_id: int, key: str) -> float:
    """Measure time from first outage end to reacquisition.

    :param gnss_id: Integer ID from the configured equipment.gnss row. Select an existing ID in
        that section.
    :param key: Evidence key for this operation. Keep distinct keys for separate facts; see the
        evidence lookup rules in the core guide.

    :returns: Recorded reacquisition s in seconds.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _logger.info("Reading reacquisition time from GNSS %s", gnss_id)
    _ = key
    return float(get_cached_instrument('gnss', require_int_id(gnss_id, kind='gnss')).measure_reacquisition_s())


verify_reacquisition_s = limit_verifier(
    "measure_reacquisition_s", name="verify_reacquisition_s", upper=True, unit="s",
)


verify_latitude = tolerance_verifier("measure_latitude", name="verify_latitude", unit="deg")
verify_longitude = tolerance_verifier("measure_longitude", name="verify_longitude", unit="deg")
verify_altitude_m = tolerance_verifier("measure_altitude_m", name="verify_altitude_m", unit="m")


def _field_rows(*, key: str, message: str) -> list[dict[str, Any]]:
    logical = resolve_logical_message(message)
    rows = get_context().db.list_measurements("equipment", logical, key)
    out: list[dict[str, Any]] = []
    for row in rows:
        value = row.value
        if isinstance(value, dict):
            out.append(value)
        elif value is not None:
            out.append({"value": value})
    return out


def _field_values(rows: list[dict[str, Any]], field: str) -> list[float]:
    values: list[float] = []
    for row in rows:
        if field not in row:
            continue
        try:
            values.append(float(row[field]))
        except (TypeError, ValueError):
            continue
    return values


def _sat_counts(
    rows: list[dict[str, Any]],
    *,
    gnss_id: int | None,
) -> list[float]:
    counts: list[float] = []
    for row in rows:
        if gnss_id is None:
            raw = row.get("num_svs", row.get("numSvs", row.get("numMeas", row.get("numSV"))))
            try:
                counts.append(float(raw))  # type: ignore[arg-type]
            except (TypeError, ValueError):
                continue
            continue
        svs = row.get("svs")
        if not isinstance(svs, list):
            continue
        counts.append(float(sum(1 for sv in svs if isinstance(sv, dict) and int(sv.get("gnssId", -1)) == gnss_id)))
    return counts


def _check_bound(
    actual: float,
    *,
    expected_val: float | None,
    tolerance: float | None,
    minimum: float | None,
    maximum: float | None,
    limit: float | None,
    optional: bool,
) -> VerificationResult:
    if expected_val is not None:
        tol = 0.0 if tolerance is None else tolerance
        if abs(actual - expected_val) <= tol:
            return VerificationResult(status="PASS", message="", optional=optional, actual=actual)
        return VerificationResult(
            status="FAIL",
            message=f"expected {expected_val} +/- {tol}, got {actual}",
            optional=optional,
            actual=actual,
        )
    lo = minimum
    hi = maximum if maximum is not None else limit
    if lo is not None and actual < lo:
        return VerificationResult(
            status="FAIL",
            message=f"expected {actual} >= {lo}",
            optional=optional,
            actual=actual,
        )
    if hi is not None and actual > hi:
        return VerificationResult(
            status="FAIL",
            message=f"expected {actual} <= {hi}",
            optional=optional,
            actual=actual,
        )
    if lo is None and hi is None:
        return VerificationResult(
            status="ERROR",
            message="provide expected_val/tolerance and/or minimum/maximum/limit",
            optional=optional,
            actual=actual,
        )
    return VerificationResult(status="PASS", message="", optional=optional, actual=actual)


@verification
def verify_field_avg(
    *,
    key: str,
    message: str,
    field: str,
    expected_val: float | None = None,
    tolerance: float | None = None,
    minimum: float | None = None,
    maximum: float | None = None,
    limit: float | None = None,
    optional: bool = False,
) -> VerificationResult:
    """Verify the mean of ``field`` over multi-row logging evidence for ``message``.

    :param key: Logging measurement key that owns the multi-row evidence.
    :param message: Logical message alias (for example ``pvt`` or ``sat``).
    :param field: Numeric field name within each evidence row.
    :param expected_val: Optional expected mean; used with ``tolerance``.
    :param tolerance: Absolute tolerance around ``expected_val``.
    :param minimum: Optional inclusive lower bound on the mean.
    :param maximum: Optional inclusive upper bound on the mean.
    :param limit: Optional inclusive upper bound alias (same as ``maximum``).
    :param optional: When ``True``, failures do not fail the overall run.
    :returns: Pass/fail verification result for the computed mean.
    """
    try:
        rows = _field_rows(key=key, message=message)
    except KeyError:
        return VerificationResult(
            status="ERROR",
            message=f"unknown message alias {message!r}",
            optional=optional,
        )
    values = _field_values(rows, field)
    if not values:
        return VerificationResult(
            status="ERROR",
            message=f"no rows for message {message!r} field {field!r} under key {key!r}",
            optional=optional,
        )
    actual = sum(values) / len(values)
    return _check_bound(
        actual,
        expected_val=expected_val,
        tolerance=tolerance,
        minimum=minimum,
        maximum=maximum,
        limit=limit,
        optional=optional,
    )


@verification
def verify_field_avg_delta(
    *,
    key_a: str,
    key_b: str,
    message: str,
    field: str,
    expected_val: float | None = None,
    tolerance: float | None = None,
    minimum: float | None = None,
    maximum: float | None = None,
    limit: float | None = None,
    optional: bool = False,
) -> VerificationResult:
    """Verify ``avg(key_b) - avg(key_a)`` for ``field`` (B minus A).

    :param key_a: Logging key for the baseline (A) capture.
    :param key_b: Logging key for the comparison (B) capture.
    :param message: Logical message alias (for example ``pvt`` or ``sat``).
    :param field: Numeric field name within each evidence row.
    :param expected_val: Optional expected delta; used with ``tolerance``.
    :param tolerance: Absolute tolerance around ``expected_val``.
    :param minimum: Optional inclusive lower bound on the delta.
    :param maximum: Optional inclusive upper bound on the delta.
    :param limit: Optional inclusive upper bound alias (same as ``maximum``).
    :param optional: When ``True``, failures do not fail the overall run.
    :returns: Pass/fail verification result for ``avg(B) - avg(A)``.
    """
    try:
        rows_a = _field_rows(key=key_a, message=message)
        rows_b = _field_rows(key=key_b, message=message)
    except KeyError:
        return VerificationResult(
            status="ERROR",
            message=f"unknown message alias {message!r}",
            optional=optional,
        )
    vals_a = _field_values(rows_a, field)
    vals_b = _field_values(rows_b, field)
    if not vals_a or not vals_b:
        return VerificationResult(
            status="ERROR",
            message=f"missing field rows for {message!r}/{field!r} under {key_a!r} or {key_b!r}",
            optional=optional,
        )
    actual = (sum(vals_b) / len(vals_b)) - (sum(vals_a) / len(vals_a))
    return _check_bound(
        actual,
        expected_val=expected_val,
        tolerance=tolerance,
        minimum=minimum,
        maximum=maximum,
        limit=limit,
        optional=optional,
    )


@verification
def verify_field_equal_percent(
    *,
    key: str,
    message: str,
    field: str,
    expected_val: float,
    tolerance: float = 0.0,
    minimum: float | None = None,
    maximum: float | None = None,
    limit: float | None = None,
    optional: bool = False,
) -> VerificationResult:
    """Verify the percentage of rows where ``field`` equals ``expected_val``.

    :param key: Logging measurement key that owns the multi-row evidence.
    :param message: Logical message alias (for example ``pvt`` or ``status``).
    :param field: Numeric field name within each evidence row.
    :param expected_val: Target field value counted as a match.
    :param tolerance: Absolute tolerance when matching ``expected_val``.
    :param minimum: Optional inclusive lower bound on the match percentage.
    :param maximum: Optional inclusive upper bound on the match percentage.
    :param limit: Optional inclusive upper bound alias (same as ``maximum``).
    :param optional: When ``True``, failures do not fail the overall run.
    :returns: Pass/fail verification result for the match percentage.
    """
    try:
        rows = _field_rows(key=key, message=message)
    except KeyError:
        return VerificationResult(
            status="ERROR",
            message=f"unknown message alias {message!r}",
            optional=optional,
        )
    values = _field_values(rows, field)
    if not values:
        return VerificationResult(
            status="ERROR",
            message=f"no rows for message {message!r} field {field!r} under key {key!r}",
            optional=optional,
        )
    matches = sum(1 for value in values if abs(value - expected_val) <= tolerance)
    actual = 100.0 * matches / len(values)
    return _check_bound(
        actual,
        expected_val=None,
        tolerance=None,
        minimum=minimum,
        maximum=maximum,
        limit=limit,
        optional=optional,
    )


@verification
def verify_sat_avg_delta(
    *,
    key_a: str,
    key_b: str,
    message: str,
    gnss_id: int | None = None,
    as_percent: bool = False,
    expected_val: float | None = None,
    tolerance: float | None = None,
    minimum: float | None = None,
    maximum: float | None = None,
    limit: float | None = None,
    optional: bool = False,
) -> VerificationResult:
    """Verify absolute (or percent) difference of average satellite counts between keys.

    :param key_a: Logging key for the baseline (A) capture.
    :param key_b: Logging key for the comparison (B) capture.
    :param message: Logical message alias that carries satellite lists.
    :param gnss_id: Optional constellation filter; ``None`` counts all SVs.
    :param as_percent: When ``True``, express the delta as a percent of avg(A).
    :param expected_val: Optional expected delta; used with ``tolerance``.
    :param tolerance: Absolute tolerance around ``expected_val``.
    :param minimum: Optional inclusive lower bound on the delta.
    :param maximum: Optional inclusive upper bound on the delta.
    :param limit: Optional inclusive upper bound alias (same as ``maximum``).
    :param optional: When ``True``, failures do not fail the overall run.
    :returns: Pass/fail verification result for the sat-count delta.
    """
    try:
        rows_a = _field_rows(key=key_a, message=message)
        rows_b = _field_rows(key=key_b, message=message)
    except KeyError:
        return VerificationResult(
            status="ERROR",
            message=f"unknown message alias {message!r}",
            optional=optional,
        )
    counts_a = _sat_counts(rows_a, gnss_id=gnss_id)
    counts_b = _sat_counts(rows_b, gnss_id=gnss_id)
    if not counts_a or not counts_b:
        return VerificationResult(
            status="ERROR",
            message=f"missing sat-count rows for {message!r} under {key_a!r} or {key_b!r}",
            optional=optional,
        )
    avg_a = sum(counts_a) / len(counts_a)
    avg_b = sum(counts_b) / len(counts_b)
    delta = abs(avg_b - avg_a)
    if as_percent:
        if avg_a == 0:
            return VerificationResult(
                status="ERROR",
                message="cannot compute percent sat delta vs zero baseline",
                optional=optional,
            )
        delta = 100.0 * delta / abs(avg_a)
    return _check_bound(
        delta,
        expected_val=expected_val,
        tolerance=tolerance,
        minimum=minimum,
        maximum=maximum,
        limit=limit,
        optional=optional,
    )


@verification
def verify_sat_diff(
    *,
    key_a: str,
    key_b: str,
    message: str,
    gnss_id: int | None = None,
    as_percent: bool = False,
    expected_val: float | None = None,
    tolerance: float | None = None,
    minimum: float | None = None,
    maximum: float | None = None,
    limit: float | None = None,
    optional: bool = False,
) -> VerificationResult:
    """Verify the largest epoch-aligned absolute sat-count delta between two keys.

    :param key_a: Logging key for the baseline (A) capture.
    :param key_b: Logging key for the comparison (B) capture.
    :param message: Logical message alias that carries satellite lists.
    :param gnss_id: Optional constellation filter; ``None`` counts all SVs.
    :param as_percent: When ``True``, express the max delta as a percent of A.
    :param expected_val: Optional expected delta; used with ``tolerance``.
    :param tolerance: Absolute tolerance around ``expected_val``.
    :param minimum: Optional inclusive lower bound on the delta.
    :param maximum: Optional inclusive upper bound on the delta.
    :param limit: Optional inclusive upper bound alias (same as ``maximum``).
    :param optional: When ``True``, failures do not fail the overall run.
    :returns: Pass/fail verification result for the max epoch sat-count delta.
    """
    try:
        rows_a = _field_rows(key=key_a, message=message)
        rows_b = _field_rows(key=key_b, message=message)
    except KeyError:
        return VerificationResult(
            status="ERROR",
            message=f"unknown message alias {message!r}",
            optional=optional,
        )
    counts_a = _sat_counts(rows_a, gnss_id=gnss_id)
    counts_b = _sat_counts(rows_b, gnss_id=gnss_id)
    if not counts_a or not counts_b:
        return VerificationResult(
            status="ERROR",
            message=f"missing sat-count rows for {message!r} under {key_a!r} or {key_b!r}",
            optional=optional,
        )
    n = min(len(counts_a), len(counts_b))
    diffs = [abs(counts_a[i] - counts_b[i]) for i in range(n)]
    if not diffs:
        actual = 0.0
        baseline = 0.0
    else:
        max_i = max(range(n), key=lambda i: diffs[i])
        actual = diffs[max_i]
        baseline = abs(counts_a[max_i])
    if as_percent:
        if baseline == 0:
            return VerificationResult(
                status="ERROR",
                message="cannot compute percent sat diff vs zero baseline",
                optional=optional,
            )
        actual = 100.0 * actual / baseline
    return _check_bound(
        actual,
        expected_val=expected_val,
        tolerance=tolerance,
        minimum=minimum,
        maximum=maximum,
        limit=limit,
        optional=optional,
    )
