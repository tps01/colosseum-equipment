"""Frequency counter APIs (``col.equipment.freqcounter``)."""

from __future__ import annotations

from typing import Any

from colosseum.decorators import command, measurement

from colosseum_equipment.api._broadcast import EquipmentId, broadcastable, require_int_id
from colosseum_equipment.api._verify import tolerance_verifier
from colosseum_equipment.connections import get_cached_instrument


def _inst(freqcounter_id: EquipmentId) -> Any:
    return get_cached_instrument('freqcounter', require_int_id(freqcounter_id, kind='freqcounter'))


@command
@broadcastable("freqcounter", "freqcounter_id")
def set_gate_time(*, freqcounter_id: EquipmentId, seconds: float) -> None:
    """Set the measurement gate time.

    :param freqcounter_id: Configured ``equipment.freqcounter`` id from bench TOML.
    :type freqcounter_id: int
    :param seconds: Gate time in seconds.
    :type seconds: float

    :returns: None

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    _inst(freqcounter_id).set_gate_time(seconds)


@command
@broadcastable("freqcounter", "freqcounter_id")
def set_coupling(*, freqcounter_id: EquipmentId, coupling: str, channel: int = 1) -> None:
    """Set input coupling (``AC`` or ``DC``).

    :param freqcounter_id: Configured ``equipment.freqcounter`` id from bench TOML.
    :type freqcounter_id: int
    :param coupling: Coupling mode.
    :type coupling: str
    :param channel: Input channel index (1-based).
    :type channel: int

    :returns: None

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    _inst(freqcounter_id).set_coupling(coupling, channel=channel)


@command
@broadcastable("freqcounter", "freqcounter_id")
def set_impedance(*, freqcounter_id: EquipmentId, ohms: float, channel: int = 1) -> None:
    """Set input termination impedance (``50`` or ``1e6``).

    :param freqcounter_id: Configured ``equipment.freqcounter`` id from bench TOML.
    :type freqcounter_id: int
    :param ohms: Termination in ohms.
    :type ohms: float
    :param channel: Input channel index (1-based).
    :type channel: int

    :returns: None

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    _inst(freqcounter_id).set_impedance(ohms, channel=channel)


@command
@broadcastable("freqcounter", "freqcounter_id")
def set_attenuation(*, freqcounter_id: EquipmentId, attenuation_db: float, channel: int = 1) -> None:
    """Set input attenuation in dB.

    :param freqcounter_id: Configured ``equipment.freqcounter`` id from bench TOML.
    :type freqcounter_id: int
    :param attenuation_db: Attenuation in dB.
    :type attenuation_db: float
    :param channel: Input channel index (1-based).
    :type channel: int

    :returns: None

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    _inst(freqcounter_id).set_attenuation(attenuation_db, channel=channel)


@command
@broadcastable("freqcounter", "freqcounter_id")
def set_trigger_level_v(*, freqcounter_id: EquipmentId, level_v: float, channel: int = 1) -> None:
    """Set input trigger level in volts.

    :param freqcounter_id: Configured ``equipment.freqcounter`` id from bench TOML.
    :type freqcounter_id: int
    :param level_v: Trigger level in volts.
    :type level_v: float
    :param channel: Input channel index (1-based).
    :type channel: int

    :returns: None

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    _inst(freqcounter_id).set_trigger_level_v(level_v, channel=channel)


@command
@broadcastable("freqcounter", "freqcounter_id")
def preset(*, freqcounter_id: EquipmentId) -> None:
    """Return the instrument to a default preset.

    :param freqcounter_id: Configured ``equipment.freqcounter`` id from bench TOML.
    :type freqcounter_id: int

    :returns: None

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    _inst(freqcounter_id).preset()


@measurement
def measure_frequency(*, freqcounter_id: int, channel: int = 1, key: str) -> float:
    """Measure input frequency.

    :param freqcounter_id: Configured ``equipment.freqcounter`` id from bench TOML.
    :type freqcounter_id: int
    :param channel: Input channel index (1-based).
    :type channel: int
    :param key: Unique measurement key within domain ``equipment`` and this command name.
        Must not collide with another instrument's measurement using the same command name.
    :type key: str

    :returns: Measured frequency in hertz.
    :rtype: float

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    _ = key
    return float(_inst(freqcounter_id).measure_frequency(channel=channel))


verify_frequency = tolerance_verifier(
    "measure_frequency",
    name="verify_frequency",
    default_tolerance=1.0,
    unit="Hz",
)


@measurement
def measure_period(*, freqcounter_id: int, channel: int = 1, key: str) -> float:
    """Measure input period.

    :param freqcounter_id: Configured ``equipment.freqcounter`` id from bench TOML.
    :type freqcounter_id: int
    :param channel: Input channel index (1-based).
    :type channel: int
    :param key: Unique measurement key within domain ``equipment`` and this command name.
        Must not collide with another instrument's measurement using the same command name.
    :type key: str

    :returns: Measured period in seconds.
    :rtype: float

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    _ = key
    return float(_inst(freqcounter_id).measure_period(channel=channel))


@measurement
def measure_time_interval_s(*, freqcounter_id: int, channel: int = 1, key: str) -> float:
    """Measure time interval in seconds.

    :param freqcounter_id: Configured ``equipment.freqcounter`` id from bench TOML.
    :type freqcounter_id: int
    :param channel: Input channel index (1-based).
    :type channel: int
    :param key: Unique measurement key within domain ``equipment`` and this command name.
    :type key: str

    :returns: Time interval in seconds.
    :rtype: float

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    _ = key
    return float(_inst(freqcounter_id).measure_time_interval_s(channel=channel))


@measurement
def measure_rise_time_s(*, freqcounter_id: int, channel: int = 1, key: str) -> float:
    """Measure rise time in seconds.

    :param freqcounter_id: Configured ``equipment.freqcounter`` id from bench TOML.
    :type freqcounter_id: int
    :param channel: Input channel index (1-based).
    :type channel: int
    :param key: Unique measurement key within domain ``equipment`` and this command name.
    :type key: str

    :returns: Rise time in seconds.
    :rtype: float

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    _ = key
    return float(_inst(freqcounter_id).measure_rise_time_s(channel=channel))


@measurement
def measure_duty_cycle_pct(*, freqcounter_id: int, channel: int = 1, key: str) -> float:
    """Measure duty cycle in percent.

    :param freqcounter_id: Configured ``equipment.freqcounter`` id from bench TOML.
    :type freqcounter_id: int
    :param channel: Input channel index (1-based).
    :type channel: int
    :param key: Unique measurement key within domain ``equipment`` and this command name.
    :type key: str

    :returns: Duty cycle in percent.
    :rtype: float

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    _ = key
    return float(_inst(freqcounter_id).measure_duty_cycle_pct(channel=channel))


@measurement
def measure_totalize(*, freqcounter_id: int, channel: int = 1, key: str) -> float:
    """Read totalize count.

    :param freqcounter_id: Configured ``equipment.freqcounter`` id from bench TOML.
    :type freqcounter_id: int
    :param channel: Input channel index (1-based).
    :type channel: int
    :param key: Unique measurement key within domain ``equipment`` and this command name.
    :type key: str

    :returns: Totalize count.
    :rtype: float

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    _ = key
    return float(_inst(freqcounter_id).measure_totalize(channel=channel))


@measurement
def measure_frequency_mean_hz(*, freqcounter_id: int, channel: int = 1, key: str) -> float:
    """Measure mean frequency when statistics are available.

    :param freqcounter_id: Configured ``equipment.freqcounter`` id from bench TOML.
    :type freqcounter_id: int
    :param channel: Input channel index (1-based).
    :type channel: int
    :param key: Unique measurement key within domain ``equipment`` and this command name.
    :type key: str

    :returns: Mean frequency in hertz.
    :rtype: float

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    _ = key
    return float(_inst(freqcounter_id).measure_frequency_mean_hz(channel=channel))


@measurement
def measure_frequency_stdev_hz(*, freqcounter_id: int, channel: int = 1, key: str) -> float:
    """Measure frequency standard deviation when statistics are available.

    :param freqcounter_id: Configured ``equipment.freqcounter`` id from bench TOML.
    :type freqcounter_id: int
    :param channel: Input channel index (1-based).
    :type channel: int
    :param key: Unique measurement key within domain ``equipment`` and this command name.
    :type key: str

    :returns: Frequency standard deviation in hertz.
    :rtype: float

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    _ = key
    return float(_inst(freqcounter_id).measure_frequency_stdev_hz(channel=channel))
