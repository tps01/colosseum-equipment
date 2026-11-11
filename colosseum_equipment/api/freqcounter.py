"""Frequency counter APIs (``col.equipment.freqcounter``).

Configured IDs select bench TOML rows. Core records command and measurement
outcomes and applies its standard optional-failure handling. Unsupported model
operations raise ``EquipmentCapabilityError``; transport failures raise
``EquipmentConnectionError``.
Operation-specific validation and acquisition constraints are described below.

Commands with an ``EquipmentId`` parameter also accept ``"all"``: targets run
sequentially and failures aggregate. Measurements require numeric IDs.
"""

from __future__ import annotations

from typing import Any

from colosseum.decorators import command, measurement
from colosseum.logging import get_logger

from colosseum_equipment.api._broadcast import EquipmentId, broadcastable, require_int_id
from colosseum_equipment.api._verify import tolerance_verifier
from colosseum_equipment.connections import get_cached_instrument

_logger = get_logger("colosseum.equipment")


def _inst(freqcounter_id: EquipmentId) -> Any:
    return get_cached_instrument("freqcounter", require_int_id(freqcounter_id, kind="freqcounter"))


@command
@broadcastable("freqcounter", "freqcounter_id")
def set_gate_time(*, freqcounter_id: EquipmentId, seconds: float) -> None:
    """Set the measurement gate time.

    :param freqcounter_id: Configured ``equipment.freqcounter`` ID.

    :param seconds: Gate time in seconds.
    """
    _logger.info("Setting gate time on frequency counter %s to %s s", freqcounter_id, seconds)
    _inst(freqcounter_id).set_gate_time(seconds)


@command
@broadcastable("freqcounter", "freqcounter_id")
def set_coupling(*, freqcounter_id: EquipmentId, coupling: str, channel: int = 1) -> None:
    """Set input coupling (``AC`` or ``DC``).

    :param freqcounter_id: Configured ``equipment.freqcounter`` ID.

    :param coupling: Coupling mode.

    :param channel: Input channel index (1-based).
    """
    _logger.info(
        "Setting coupling on frequency counter %s channel %s to %s",
        freqcounter_id,
        channel,
        coupling,
    )
    _inst(freqcounter_id).set_coupling(coupling, channel=channel)


@command
@broadcastable("freqcounter", "freqcounter_id")
def set_impedance(*, freqcounter_id: EquipmentId, ohms: float, channel: int = 1) -> None:
    """Set input termination impedance (``50`` or ``1e6``).

    :param freqcounter_id: Configured ``equipment.freqcounter`` ID.

    :param ohms: Termination in ohms.

    :param channel: Input channel index (1-based).
    """
    _logger.info(
        "Setting impedance on frequency counter %s channel %s to %s ohms",
        freqcounter_id,
        channel,
        ohms,
    )
    _inst(freqcounter_id).set_impedance(ohms, channel=channel)


@command
@broadcastable("freqcounter", "freqcounter_id")
def set_attenuation(*, freqcounter_id: EquipmentId, attenuation_db: float, channel: int = 1) -> None:
    """Set input attenuation in dB.

    :param freqcounter_id: Configured ``equipment.freqcounter`` ID.

    :param attenuation_db: Attenuation in dB.

    :param channel: Input channel index (1-based).
    """
    _logger.info(
        "Setting attenuation on frequency counter %s channel %s to %s dB",
        freqcounter_id,
        channel,
        attenuation_db,
    )
    _inst(freqcounter_id).set_attenuation(attenuation_db, channel=channel)


@command
@broadcastable("freqcounter", "freqcounter_id")
def set_trigger_level_v(*, freqcounter_id: EquipmentId, level_v: float, channel: int = 1) -> None:
    """Set input trigger level in volts.

    :param freqcounter_id: Configured ``equipment.freqcounter`` ID.

    :param level_v: Trigger level in volts.

    :param channel: Input channel index (1-based).
    """
    _logger.info(
        "Setting trigger level on frequency counter %s channel %s to %s V",
        freqcounter_id,
        channel,
        level_v,
    )
    _inst(freqcounter_id).set_trigger_level_v(level_v, channel=channel)


@command
@broadcastable("freqcounter", "freqcounter_id")
def preset(*, freqcounter_id: EquipmentId) -> None:
    """Return the instrument to a default preset.

    :param freqcounter_id: Configured ``equipment.freqcounter`` ID.
    """
    _logger.info("Presetting frequency counter %s", freqcounter_id)
    _inst(freqcounter_id).preset()


@measurement
def measure_frequency(*, freqcounter_id: int, channel: int = 1, key: str) -> float:
    """Measure input frequency.

    :param freqcounter_id: Configured ``equipment.freqcounter`` ID.

    :param channel: Input channel index (1-based).

    :param key: Unique measurement key within domain ``equipment`` and this command name.
        Must not collide with another instrument's measurement using the same command name.

    :returns: Measured frequency in hertz.
    :rtype: float
    """
    _logger.info("Reading frequency from frequency counter %s channel %s", freqcounter_id, channel)
    _ = key
    return float(_inst(freqcounter_id).measure_frequency(channel=channel))


verify_frequency = tolerance_verifier(
    "measure_frequency", module=__name__,
    name="verify_frequency",
    default_tolerance=1.0,
    unit="Hz",
)


@measurement
def measure_period(*, freqcounter_id: int, channel: int = 1, key: str) -> float:
    """Measure input period.

    :param freqcounter_id: Configured ``equipment.freqcounter`` ID.

    :param channel: Input channel index (1-based).

    :param key: Unique measurement key within domain ``equipment`` and this command name.
        Must not collide with another instrument's measurement using the same command name.

    :returns: Measured period in seconds.
    :rtype: float
    """
    _logger.info("Reading period from frequency counter %s channel %s", freqcounter_id, channel)
    _ = key
    return float(_inst(freqcounter_id).measure_period(channel=channel))


@measurement
def measure_time_interval_s(*, freqcounter_id: int, channel: int = 1, key: str) -> float:
    """Measure time interval in seconds.

    :param freqcounter_id: Configured ``equipment.freqcounter`` ID.

    :param channel: Input channel index (1-based).

    :param key: Unique measurement key within domain ``equipment`` and this command name.

    :returns: Time interval in seconds.
    :rtype: float
    """
    _logger.info(
        "Reading time interval from frequency counter %s channel %s",
        freqcounter_id,
        channel,
    )
    _ = key
    return float(_inst(freqcounter_id).measure_time_interval_s(channel=channel))


@measurement
def measure_rise_time_s(*, freqcounter_id: int, channel: int = 1, key: str) -> float:
    """Measure rise time in seconds.

    :param freqcounter_id: Configured ``equipment.freqcounter`` ID.

    :param channel: Input channel index (1-based).

    :param key: Unique measurement key within domain ``equipment`` and this command name.

    :returns: Rise time in seconds.
    :rtype: float
    """
    _logger.info("Reading rise time from frequency counter %s channel %s", freqcounter_id, channel)
    _ = key
    return float(_inst(freqcounter_id).measure_rise_time_s(channel=channel))


@measurement
def measure_duty_cycle_pct(*, freqcounter_id: int, channel: int = 1, key: str) -> float:
    """Measure duty cycle in percent.

    :param freqcounter_id: Configured ``equipment.freqcounter`` ID.

    :param channel: Input channel index (1-based).

    :param key: Unique measurement key within domain ``equipment`` and this command name.

    :returns: Duty cycle in percent.
    :rtype: float
    """
    _logger.info("Reading duty cycle from frequency counter %s channel %s", freqcounter_id, channel)
    _ = key
    return float(_inst(freqcounter_id).measure_duty_cycle_pct(channel=channel))


@measurement
def measure_totalize(*, freqcounter_id: int, channel: int = 1, key: str) -> float:
    """Read totalize count.

    :param freqcounter_id: Configured ``equipment.freqcounter`` ID.

    :param channel: Input channel index (1-based).

    :param key: Unique measurement key within domain ``equipment`` and this command name.

    :returns: Totalize count.
    :rtype: float
    """
    _logger.info(
        "Reading totalize count from frequency counter %s channel %s",
        freqcounter_id,
        channel,
    )
    _ = key
    return float(_inst(freqcounter_id).measure_totalize(channel=channel))


@measurement
def measure_frequency_mean_hz(*, freqcounter_id: int, channel: int = 1, key: str) -> float:
    """Measure mean frequency when statistics are available.

    :param freqcounter_id: Configured ``equipment.freqcounter`` ID.

    :param channel: Input channel index (1-based).

    :param key: Unique measurement key within domain ``equipment`` and this command name.

    :returns: Mean frequency in hertz.
    :rtype: float
    """
    _logger.info(
        "Reading mean frequency from frequency counter %s channel %s",
        freqcounter_id,
        channel,
    )
    _ = key
    return float(_inst(freqcounter_id).measure_frequency_mean_hz(channel=channel))


@measurement
def measure_frequency_stdev_hz(*, freqcounter_id: int, channel: int = 1, key: str) -> float:
    """Measure frequency standard deviation when statistics are available.

    :param freqcounter_id: Configured ``equipment.freqcounter`` ID.

    :param channel: Input channel index (1-based).

    :param key: Unique measurement key within domain ``equipment`` and this command name.

    :returns: Frequency standard deviation in hertz.
    :rtype: float
    """
    _logger.info(
        "Reading frequency stdev from frequency counter %s channel %s",
        freqcounter_id,
        channel,
    )
    _ = key
    return float(_inst(freqcounter_id).measure_frequency_stdev_hz(channel=channel))
