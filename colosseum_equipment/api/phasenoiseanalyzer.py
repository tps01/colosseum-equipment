"""Phase noise analyzer APIs (``col.equipment.phasenoiseanalyzer``).

Configured IDs select bench TOML rows. Core records command and measurement
outcomes and applies its standard optional-failure handling. Unsupported model
operations raise ``EquipmentCapabilityError``; transport failures raise
``EquipmentConnectionError``.
Operation-specific validation and acquisition constraints are described below.

Commands with an ``EquipmentId`` parameter also accept ``"all"``: targets run
sequentially and failures aggregate. Measurements require numeric IDs.
"""

from __future__ import annotations

from colosseum.decorators import command, measurement
from colosseum.logging import get_logger

from colosseum_equipment.api._broadcast import EquipmentId, broadcastable, require_int_id
from colosseum_equipment.connections import get_cached_instrument

_logger = get_logger("colosseum.equipment")


@command
@broadcastable("phasenoiseanalyzer", "phasenoiseanalyzer_id")
def preset(*, phasenoiseanalyzer_id: EquipmentId) -> None:
    """Return the instrument to a default preset.

    :param phasenoiseanalyzer_id: Configured ``equipment.phasenoiseanalyzer`` id.
    """
    _logger.info("Presetting phase noise analyzer %s", phasenoiseanalyzer_id)
    get_cached_instrument(
        "phasenoiseanalyzer", require_int_id(phasenoiseanalyzer_id, kind="phasenoiseanalyzer"),
    ).preset()


@command
@broadcastable("phasenoiseanalyzer", "phasenoiseanalyzer_id")
def set_carrier_frequency_hz(*, phasenoiseanalyzer_id: EquipmentId, frequency_hz: float) -> None:
    """Set the carrier / DUT frequency in hertz.

    :param phasenoiseanalyzer_id: Configured ``equipment.phasenoiseanalyzer`` id.

    :param frequency_hz: Carrier frequency in hertz.
    """
    _logger.info(
        "Setting carrier on phase noise analyzer %s to %s Hz",
        phasenoiseanalyzer_id,
        frequency_hz,
    )
    get_cached_instrument(
        "phasenoiseanalyzer", require_int_id(phasenoiseanalyzer_id, kind="phasenoiseanalyzer"),
    ).set_carrier_frequency_hz(
        frequency_hz,
    )


@command
@broadcastable("phasenoiseanalyzer", "phasenoiseanalyzer_id")
def set_offset_start_hz(*, phasenoiseanalyzer_id: EquipmentId, offset_hz: float) -> None:
    """Set the phase-noise offset start frequency in hertz.

    :param phasenoiseanalyzer_id: Configured ``equipment.phasenoiseanalyzer`` id.

    :param offset_hz: Start offset in hertz.
    """
    _logger.info(
        "Setting start offset on phase noise analyzer %s to %s Hz",
        phasenoiseanalyzer_id,
        offset_hz,
    )
    get_cached_instrument(
        "phasenoiseanalyzer", require_int_id(phasenoiseanalyzer_id, kind="phasenoiseanalyzer"),
    ).set_offset_start_hz(
        offset_hz,
    )


@command
@broadcastable("phasenoiseanalyzer", "phasenoiseanalyzer_id")
def set_offset_stop_hz(*, phasenoiseanalyzer_id: EquipmentId, offset_hz: float) -> None:
    """Set the phase-noise offset stop frequency in hertz.

    :param phasenoiseanalyzer_id: Configured ``equipment.phasenoiseanalyzer`` id.

    :param offset_hz: Stop offset in hertz.
    """
    _logger.info(
        "Setting stop offset on phase noise analyzer %s to %s Hz",
        phasenoiseanalyzer_id,
        offset_hz,
    )
    get_cached_instrument(
        "phasenoiseanalyzer", require_int_id(phasenoiseanalyzer_id, kind="phasenoiseanalyzer"),
    ).set_offset_stop_hz(
        offset_hz,
    )


@command
@broadcastable("phasenoiseanalyzer", "phasenoiseanalyzer_id")
def initiate(*, phasenoiseanalyzer_id: EquipmentId) -> None:
    """Start a phase-noise measurement sweep.

    :param phasenoiseanalyzer_id: Configured ``equipment.phasenoiseanalyzer`` id.
    """
    _logger.info("Initiating measurement on phase noise analyzer %s", phasenoiseanalyzer_id)
    get_cached_instrument(
        "phasenoiseanalyzer", require_int_id(phasenoiseanalyzer_id, kind="phasenoiseanalyzer"),
    ).initiate()


@command
def wait_complete(*, phasenoiseanalyzer_id: int, timeout_s: float = 120.0) -> None:
    """Wait for the current sweep with a bounded timeout.

    :param phasenoiseanalyzer_id: Configured ``equipment.phasenoiseanalyzer`` id.

    :param timeout_s: Maximum wait time in seconds.
    """
    _logger.info("Waiting for phase noise analyzer %s to complete", phasenoiseanalyzer_id)
    get_cached_instrument(
        "phasenoiseanalyzer", require_int_id(phasenoiseanalyzer_id, kind="phasenoiseanalyzer"),
    ).wait_complete(
        timeout_s=timeout_s,
    )


@command
@broadcastable("phasenoiseanalyzer", "phasenoiseanalyzer_id")
def abort(*, phasenoiseanalyzer_id: EquipmentId) -> None:
    """Cancel an in-progress phase-noise sweep.

    :param phasenoiseanalyzer_id: Configured ``equipment.phasenoiseanalyzer`` id.
    """
    _logger.info("Aborting phase noise analyzer %s", phasenoiseanalyzer_id)
    get_cached_instrument(
        "phasenoiseanalyzer", require_int_id(phasenoiseanalyzer_id, kind="phasenoiseanalyzer"),
    ).abort()


@command
@broadcastable("phasenoiseanalyzer", "phasenoiseanalyzer_id")
def set_averaging_count(*, phasenoiseanalyzer_id: EquipmentId, count: int) -> None:
    """Set sweep averaging count.

    :param phasenoiseanalyzer_id: Configured ``equipment.phasenoiseanalyzer`` id.

    :param count: Number of sweeps to average.
    """
    _logger.info(
        "Setting averaging count on phase noise analyzer %s to %s",
        phasenoiseanalyzer_id,
        count,
    )
    get_cached_instrument(
        "phasenoiseanalyzer", require_int_id(phasenoiseanalyzer_id, kind="phasenoiseanalyzer"),
    ).set_averaging_count(
        count,
    )


@command
@broadcastable("phasenoiseanalyzer", "phasenoiseanalyzer_id")
def set_xcorr_count(*, phasenoiseanalyzer_id: EquipmentId, count: int) -> None:
    """Set cross-correlation count (R&S FSWP and similar).

    :param phasenoiseanalyzer_id: Configured ``equipment.phasenoiseanalyzer`` id.

    :param count: Cross-correlation count.
    """
    _logger.info(
        "Setting cross-correlation count on phase noise analyzer %s to %s",
        phasenoiseanalyzer_id,
        count,
    )
    get_cached_instrument(
        "phasenoiseanalyzer", require_int_id(phasenoiseanalyzer_id, kind="phasenoiseanalyzer"),
    ).set_xcorr_count(count)


@command
def save_trace_data(*, phasenoiseanalyzer_id: int, path: str, trace: int = 1) -> None:
    """Export phase-noise trace CSV and register an artifact.

    :param phasenoiseanalyzer_id: Configured ``equipment.phasenoiseanalyzer`` id.

    :param path: Relative path under the run output directory.

    :param trace: Trace number (1-based).
    """
    _logger.info(
        "Saving trace data from phase noise analyzer %s to %s",
        phasenoiseanalyzer_id,
        path,
    )
    get_cached_instrument(
        "phasenoiseanalyzer", require_int_id(phasenoiseanalyzer_id, kind="phasenoiseanalyzer"),
    ).save_trace_data(
        path,
        trace=trace,
    )


@command
def wait_opc(*, phasenoiseanalyzer_id: int) -> None:
    """Wait for the instrument operation-complete bit.

    :param phasenoiseanalyzer_id: Configured ``equipment.phasenoiseanalyzer`` id.
    """
    _logger.info("Waiting for operation complete on phase noise analyzer %s", phasenoiseanalyzer_id)
    get_cached_instrument(
        "phasenoiseanalyzer", require_int_id(phasenoiseanalyzer_id, kind="phasenoiseanalyzer"),
    ).wait_opc()


@measurement
def measure_spot_noise_dbc_hz(
    *,
    phasenoiseanalyzer_id: int,
    offset_hz: float,
    key: str,
) -> float:
    """Measure spot phase noise at ``offset_hz`` in dBc/Hz.

    :param phasenoiseanalyzer_id: Configured ``equipment.phasenoiseanalyzer`` id.

    :param offset_hz: Spot offset frequency in hertz.

    :param key: Unique measurement key within domain ``equipment``.

    :returns: Spot noise in dBc/Hz.
    :rtype: float
    """
    _logger.info(
        "Reading spot noise from phase noise analyzer %s at %s Hz",
        phasenoiseanalyzer_id,
        offset_hz,
    )
    _ = key
    instrument = get_cached_instrument(
        "phasenoiseanalyzer", require_int_id(phasenoiseanalyzer_id, kind="phasenoiseanalyzer"),
    )
    return float(instrument.measure_spot_noise_dbc_hz(offset_hz))


@measurement
def measure_integrated_jitter_s(
    *,
    phasenoiseanalyzer_id: int,
    key: str,
    start_hz: float | None = None,
    stop_hz: float | None = None,
) -> float:
    """Measure integrated phase jitter in seconds when CALC supports it.

    :param phasenoiseanalyzer_id: Configured ``equipment.phasenoiseanalyzer`` id.

    :param key: Unique measurement key within domain ``equipment``.

    :param start_hz: Optional integration start offset in hertz.

    :param stop_hz: Optional integration stop offset in hertz.

    :returns: Integrated jitter in seconds (RMS).
    :rtype: float
    """
    _logger.info("Reading integrated jitter from phase noise analyzer %s", phasenoiseanalyzer_id)
    _ = key
    return float(
        get_cached_instrument(
            "phasenoiseanalyzer", require_int_id(phasenoiseanalyzer_id, kind="phasenoiseanalyzer"),
        ).measure_integrated_jitter_s(
            start_hz=start_hz,
            stop_hz=stop_hz,
        ),
    )


@measurement
def measure_carrier_frequency_hz(*, phasenoiseanalyzer_id: int, key: str) -> float:
    """Measure the configured carrier frequency in hertz.

    :param phasenoiseanalyzer_id: Configured ``equipment.phasenoiseanalyzer`` id.

    :param key: Unique measurement key within domain ``equipment``.

    :returns: Carrier frequency in hertz.
    :rtype: float
    """
    _logger.info("Reading carrier frequency from phase noise analyzer %s", phasenoiseanalyzer_id)
    _ = key
    return float(
        get_cached_instrument(
            "phasenoiseanalyzer",
            phasenoiseanalyzer_id,
        ).measure_carrier_frequency_hz(),
    )
