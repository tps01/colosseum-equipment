"""Phase noise analyzer APIs (``col.equipment.phasenoiseanalyzer``)."""

from __future__ import annotations

from colosseum.decorators import command, measurement

from colosseum_equipment.connections import get_cached_instrument


@command
def preset(*, phasenoiseanalyzer_id: int) -> None:
    """Return the instrument to a default preset.

    :param phasenoiseanalyzer_id: Configured ``equipment.phasenoiseanalyzer`` id.
    :type phasenoiseanalyzer_id: int

    :returns: None
    """
    get_cached_instrument("phasenoiseanalyzer", phasenoiseanalyzer_id).preset()


@command
def set_carrier_frequency_hz(*, phasenoiseanalyzer_id: int, frequency_hz: float) -> None:
    """Set the carrier / DUT frequency in hertz.

    :param phasenoiseanalyzer_id: Configured ``equipment.phasenoiseanalyzer`` id.
    :type phasenoiseanalyzer_id: int
    :param frequency_hz: Carrier frequency in hertz.
    :type frequency_hz: float

    :returns: None
    """
    get_cached_instrument("phasenoiseanalyzer", phasenoiseanalyzer_id).set_carrier_frequency_hz(
        frequency_hz,
    )


@command
def set_offset_start_hz(*, phasenoiseanalyzer_id: int, offset_hz: float) -> None:
    """Set the phase-noise offset start frequency in hertz.

    :param phasenoiseanalyzer_id: Configured ``equipment.phasenoiseanalyzer`` id.
    :type phasenoiseanalyzer_id: int
    :param offset_hz: Start offset in hertz.
    :type offset_hz: float

    :returns: None
    """
    get_cached_instrument("phasenoiseanalyzer", phasenoiseanalyzer_id).set_offset_start_hz(
        offset_hz,
    )


@command
def set_offset_stop_hz(*, phasenoiseanalyzer_id: int, offset_hz: float) -> None:
    """Set the phase-noise offset stop frequency in hertz.

    :param phasenoiseanalyzer_id: Configured ``equipment.phasenoiseanalyzer`` id.
    :type phasenoiseanalyzer_id: int
    :param offset_hz: Stop offset in hertz.
    :type offset_hz: float

    :returns: None
    """
    get_cached_instrument("phasenoiseanalyzer", phasenoiseanalyzer_id).set_offset_stop_hz(
        offset_hz,
    )


@command
def initiate(*, phasenoiseanalyzer_id: int) -> None:
    """Start a phase-noise measurement sweep.

    :param phasenoiseanalyzer_id: Configured ``equipment.phasenoiseanalyzer`` id.
    :type phasenoiseanalyzer_id: int

    :returns: None
    """
    get_cached_instrument("phasenoiseanalyzer", phasenoiseanalyzer_id).initiate()


@command
def wait_complete(*, phasenoiseanalyzer_id: int, timeout_s: float = 120.0) -> None:
    """Wait for the current sweep with a bounded timeout.

    :param phasenoiseanalyzer_id: Configured ``equipment.phasenoiseanalyzer`` id.
    :type phasenoiseanalyzer_id: int
    :param timeout_s: Maximum wait time in seconds.
    :type timeout_s: float, optional

    :returns: None
    """
    get_cached_instrument("phasenoiseanalyzer", phasenoiseanalyzer_id).wait_complete(
        timeout_s=timeout_s,
    )


@command
def abort(*, phasenoiseanalyzer_id: int) -> None:
    """Cancel an in-progress phase-noise sweep.

    :param phasenoiseanalyzer_id: Configured ``equipment.phasenoiseanalyzer`` id.
    :type phasenoiseanalyzer_id: int

    :returns: None
    """
    get_cached_instrument("phasenoiseanalyzer", phasenoiseanalyzer_id).abort()


@command
def set_averaging_count(*, phasenoiseanalyzer_id: int, count: int) -> None:
    """Set sweep averaging count.

    :param phasenoiseanalyzer_id: Configured ``equipment.phasenoiseanalyzer`` id.
    :type phasenoiseanalyzer_id: int
    :param count: Number of sweeps to average.
    :type count: int

    :returns: None
    """
    get_cached_instrument("phasenoiseanalyzer", phasenoiseanalyzer_id).set_averaging_count(
        count,
    )


@command
def set_xcorr_count(*, phasenoiseanalyzer_id: int, count: int) -> None:
    """Set cross-correlation count (R&S FSWP and similar).

    :param phasenoiseanalyzer_id: Configured ``equipment.phasenoiseanalyzer`` id.
    :type phasenoiseanalyzer_id: int
    :param count: Cross-correlation count.
    :type count: int

    :returns: None
    """
    get_cached_instrument("phasenoiseanalyzer", phasenoiseanalyzer_id).set_xcorr_count(count)


@command
def save_trace_data(*, phasenoiseanalyzer_id: int, path: str, trace: int = 1) -> None:
    """Export phase-noise trace CSV and register an artifact.

    :param phasenoiseanalyzer_id: Configured ``equipment.phasenoiseanalyzer`` id.
    :type phasenoiseanalyzer_id: int
    :param path: Relative path under the run output directory.
    :type path: str
    :param trace: Trace number (1-based).
    :type trace: int, optional

    :returns: None
    """
    get_cached_instrument("phasenoiseanalyzer", phasenoiseanalyzer_id).save_trace_data(
        path,
        trace=trace,
    )


@command
def wait_opc(*, phasenoiseanalyzer_id: int) -> None:
    """Wait for the instrument operation-complete bit.

    :param phasenoiseanalyzer_id: Configured ``equipment.phasenoiseanalyzer`` id.
    :type phasenoiseanalyzer_id: int

    :returns: None
    """
    get_cached_instrument("phasenoiseanalyzer", phasenoiseanalyzer_id).wait_opc()


@measurement
def measure_spot_noise_dbc_hz(
    *,
    phasenoiseanalyzer_id: int,
    offset_hz: float,
    key: str,
) -> float:
    """Measure spot phase noise at ``offset_hz`` in dBc/Hz.

    :param phasenoiseanalyzer_id: Configured ``equipment.phasenoiseanalyzer`` id.
    :type phasenoiseanalyzer_id: int
    :param offset_hz: Spot offset frequency in hertz.
    :type offset_hz: float
    :param key: Unique measurement key within domain ``equipment``.
    :type key: str

    :returns: Spot noise in dBc/Hz.
    :rtype: float
    """
    _ = key
    instrument = get_cached_instrument("phasenoiseanalyzer", phasenoiseanalyzer_id)
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
    :type phasenoiseanalyzer_id: int
    :param key: Unique measurement key within domain ``equipment``.
    :type key: str
    :param start_hz: Optional integration start offset in hertz.
    :type start_hz: float | None, optional
    :param stop_hz: Optional integration stop offset in hertz.
    :type stop_hz: float | None, optional

    :returns: Integrated jitter in seconds (RMS).
    :rtype: float
    """
    _ = key
    return float(
        get_cached_instrument("phasenoiseanalyzer", phasenoiseanalyzer_id).measure_integrated_jitter_s(
            start_hz=start_hz,
            stop_hz=stop_hz,
        ),
    )


@measurement
def measure_carrier_frequency_hz(*, phasenoiseanalyzer_id: int, key: str) -> float:
    """Measure the configured carrier frequency in hertz.

    :param phasenoiseanalyzer_id: Configured ``equipment.phasenoiseanalyzer`` id.
    :type phasenoiseanalyzer_id: int
    :param key: Unique measurement key within domain ``equipment``.
    :type key: str

    :returns: Carrier frequency in hertz.
    :rtype: float
    """
    _ = key
    return float(
        get_cached_instrument(
            "phasenoiseanalyzer",
            phasenoiseanalyzer_id,
        ).measure_carrier_frequency_hz(),
    )
