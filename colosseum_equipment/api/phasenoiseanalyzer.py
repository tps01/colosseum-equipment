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
