"""GNSS receiver APIs (``col.equipment.gnss``)."""

from __future__ import annotations

from typing import Any

from colosseum.decorators import command, measurement

from colosseum_equipment.api._verify import limit_verifier, minimum_verifier, tolerance_verifier
from colosseum_equipment.connections import get_cached_instrument


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
    get_cached_instrument("gnss", gnss_id).wait_for_fix(timeout_s)


@command
def cold_start(*, gnss_id: int) -> None:
    """Clear navigation data and force a cold acquisition (vendor-specific).

    :param gnss_id: Integer ID from the configured equipment.gnss row. Select an existing ID in
        that section.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    get_cached_instrument("gnss", gnss_id).cold_start()


@command
def mark_acquisition_start(*, gnss_id: int) -> None:
    """Mark T0 for TTFF measurement without issuing a cold start.

    :param gnss_id: Integer ID from the configured equipment.gnss row. Select an existing ID in
        that section.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    get_cached_instrument("gnss", gnss_id).mark_acquisition_start()


@command
def load_config(*, gnss_id: int, path: str) -> None:
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
    get_cached_instrument("gnss", gnss_id).load_config(path)


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
    get_cached_instrument("gnss", gnss_id).save_config(path)


@command
def set_message_rate(*, gnss_id: int, message: str, rate_hz: float) -> None:
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
    get_cached_instrument("gnss", gnss_id).set_message_rate(message, rate_hz)


@command
def start_logging(*, gnss_id: int, path: str, key: str = "") -> None:
    """Start background logging of raw messages, binary wire capture, track CSV, and DB epochs.

    Writes a decoded text log at ``path``, a binary wire sidecar
    (``{stem}_wire.ubx`` / ``.gps`` / ``.sbf`` / ``.bin``), and ``{stem}_track.csv``.
    ``key`` identifies the logging window for evidence rows.

    :param gnss_id: Integer ID from the configured equipment.gnss row. Select an existing ID in
        that section.
    :param path: Destination file path, absolute or relative to the active run output directory;
        requires artifacts enabled.
    :param key: Evidence key for this operation. Keep distinct keys for separate facts; see the
        evidence lookup rules in the core guide. Default: ``''``.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    get_cached_instrument("gnss", gnss_id).start_logging(path, key=key)


@command
def stop_logging(*, gnss_id: int) -> None:
    """Stop the listener, emit continuity summaries, and close log files.

    :param gnss_id: Integer ID from the configured equipment.gnss row. Select an existing ID in
        that section.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    get_cached_instrument("gnss", gnss_id).stop_logging()


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
    get_cached_instrument("gnss", gnss_id).save_track_plot(path)


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
    get_cached_instrument("gnss", gnss_id).save_skyplot(path)


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
    get_cached_instrument("gnss", gnss_id).save_quality_plot(path)


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
    return list(
        get_cached_instrument("gnss", gnss_id).get_satellite_snapshot(max_age_s=max_age_s),
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
    return str(get_cached_instrument("gnss", gnss_id).get_fix_type(max_age_s=max_age_s))


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
    return list(
        get_cached_instrument("gnss", gnss_id).get_constellations_present(max_age_s=max_age_s),
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
    _ = key
    return float(get_cached_instrument("gnss", gnss_id).measure_latitude(max_age_s=max_age_s))


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
    _ = key
    return float(get_cached_instrument("gnss", gnss_id).measure_longitude(max_age_s=max_age_s))


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
    _ = key
    return float(get_cached_instrument("gnss", gnss_id).measure_altitude_m(max_age_s=max_age_s))


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
    _ = key
    return float(get_cached_instrument("gnss", gnss_id).measure_fix_quality(max_age_s=max_age_s))


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
    _ = key
    return float(get_cached_instrument("gnss", gnss_id).measure_satellites(max_age_s=max_age_s))


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
    _ = key
    return float(
        get_cached_instrument("gnss", gnss_id).measure_satellites_visible(max_age_s=max_age_s),
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
    _ = key
    return float(get_cached_instrument("gnss", gnss_id).measure_hdop(max_age_s=max_age_s))


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
    _ = key
    return float(get_cached_instrument("gnss", gnss_id).measure_pdop(max_age_s=max_age_s))


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
    _ = key
    return float(get_cached_instrument("gnss", gnss_id).measure_vdop(max_age_s=max_age_s))


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
    _ = key
    return float(get_cached_instrument("gnss", gnss_id).measure_gdop(max_age_s=max_age_s))


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
    _ = key
    return float(get_cached_instrument("gnss", gnss_id).measure_max_cn0_dbhz(max_age_s=max_age_s))


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
    _ = key
    return float(get_cached_instrument("gnss", gnss_id).measure_mean_cn0_dbhz(max_age_s=max_age_s))


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
    _ = key
    return float(
        get_cached_instrument("gnss", gnss_id).measure_cn0_dbhz(
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
    _ = key
    return float(get_cached_instrument("gnss", gnss_id).measure_speed_m_s(max_age_s=max_age_s))


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
    _ = key
    return float(get_cached_instrument("gnss", gnss_id).measure_course_deg(max_age_s=max_age_s))


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
    _ = key
    return float(get_cached_instrument("gnss", gnss_id).measure_h_acc_m(max_age_s=max_age_s))


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
    _ = key
    return float(get_cached_instrument("gnss", gnss_id).measure_v_acc_m(max_age_s=max_age_s))


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
    _ = key
    return float(
        get_cached_instrument("gnss", gnss_id).measure_geoid_separation_m(max_age_s=max_age_s),
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
    _ = key
    return float(get_cached_instrument("gnss", gnss_id).measure_data_age_s())


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
    _ = key
    return str(get_cached_instrument("gnss", gnss_id).measure_utc_time(max_age_s=max_age_s))


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
    _ = key
    return float(get_cached_instrument("gnss", gnss_id).measure_ttff_s())


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
    _ = key
    return float(get_cached_instrument("gnss", gnss_id).measure_fix_availability())


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
    _ = key
    return float(get_cached_instrument("gnss", gnss_id).measure_longest_outage_s())


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
    _ = key
    return float(get_cached_instrument("gnss", gnss_id).measure_reacquisition_s())


verify_latitude = tolerance_verifier("measure_latitude", name="verify_latitude", unit="deg")
verify_longitude = tolerance_verifier("measure_longitude", name="verify_longitude", unit="deg")
verify_altitude_m = tolerance_verifier("measure_altitude_m", name="verify_altitude_m", unit="m")
