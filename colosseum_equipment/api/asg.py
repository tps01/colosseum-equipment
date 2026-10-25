"""Analog signal generator APIs exposed as ``col.equipment.asg``.

Configure instruments with ``[equipment.asg]`` in bench TOML (``asg_id``, ``resource``,
optional ``model`` and ``driver``; default driver is VISA/SCPI). Pulse generator and modulation
commands use R&S-style SCPI on the ``generic`` model.
"""

from __future__ import annotations

from typing import Any

from colosseum.decorators import command, measurement

from colosseum_equipment import calibration as _cal
from colosseum_equipment.connections import get_cached_instrument


def _inst(asg_id: int) -> Any:
    return get_cached_instrument("asg", asg_id)


@command
def set_frequency(
    *,
    asg_id: int,
    frequency: float,
    channel: int = 1,
    calibration: str | None = None,
) -> None:
    """Set CW output frequency in hertz.

    When ``calibration`` is set, retunes programmed power so the post-cal
    (desired) output level from the last ``set_power(..., calibration=)`` is
    held at the new frequency.

    :param asg_id: Configured ``equipment.asg`` id from bench TOML.
    :type asg_id: int
    :param frequency: Output frequency in hertz.
    :type frequency: float
    :param channel: Source channel index (1-based).
    :type channel: int
    :param calibration: Key from :func:`colosseum_equipment.api.calibration.load_calibration`.
    :type calibration: str | None, optional

    :returns: None

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    inst = _inst(asg_id)
    inst.set_frequency(frequency, channel=channel)
    _cal.bind_frequency(inst, frequency, channel=channel)
    if calibration is not None:
        desired = _cal.require_desired_power(inst, channel=channel)
        programmed = _cal.programmed_power_dbm(desired, key=calibration, frequency_hz=frequency)
        inst.set_power(programmed, channel=channel)
        _cal.remember_desired_power(inst, desired, key=calibration, channel=channel)


@command
def set_waveform(*, asg_id: int, waveform: str, channel: int = 1) -> None:
    """Set output waveform (``sine``, ``square``, ``ramp``, ``pulse``, ``noise``, ``arb``).

    :param asg_id: Configured ``equipment.asg`` id from bench TOML.
    :type asg_id: int
    :param waveform: Waveform name.
    :type waveform: str
    :param channel: Source channel index (1-based).
    :type channel: int

    :returns: None

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    _inst(asg_id).set_waveform(waveform, channel=channel)


@command
def set_amplitude_vpp(*, asg_id: int, vpp: float, channel: int = 1) -> None:
    """Set output amplitude in volts peak-to-peak.

    :param asg_id: Configured ``equipment.asg`` id from bench TOML.
    :type asg_id: int
    :param vpp: Amplitude in Vpp.
    :type vpp: float
    :param channel: Source channel index (1-based).
    :type channel: int

    :returns: None

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    _inst(asg_id).set_amplitude_vpp(vpp, channel=channel)


@command
def set_amplitude_vrms(*, asg_id: int, vrms: float, channel: int = 1) -> None:
    """Set output amplitude in volts RMS.

    :param asg_id: Configured ``equipment.asg`` id from bench TOML.
    :type asg_id: int
    :param vrms: Amplitude in Vrms.
    :type vrms: float
    :param channel: Source channel index (1-based).
    :type channel: int

    :returns: None

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    _inst(asg_id).set_amplitude_vrms(vrms, channel=channel)


@command
def set_offset_v(*, asg_id: int, offset_v: float, channel: int = 1) -> None:
    """Set DC offset in volts.

    :param asg_id: Configured ``equipment.asg`` id from bench TOML.
    :type asg_id: int
    :param offset_v: Offset voltage.
    :type offset_v: float
    :param channel: Source channel index (1-based).
    :type channel: int

    :returns: None

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    _inst(asg_id).set_offset_v(offset_v, channel=channel)


@command
def set_load_ohms(*, asg_id: int, ohms: float, channel: int = 1) -> None:
    """Set output load impedance in ohms.

    :param asg_id: Configured ``equipment.asg`` id from bench TOML.
    :type asg_id: int
    :param ohms: Load resistance in ohms.
    :type ohms: float
    :param channel: Source channel index (1-based).
    :type channel: int

    :returns: None

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    _inst(asg_id).set_load_ohms(ohms, channel=channel)


@measurement
def get_load_ohms(*, asg_id: int, channel: int = 1, key: str) -> float:
    """Read configured output load impedance in ohms.

    :param asg_id: Configured ``equipment.asg`` id from bench TOML.
    :type asg_id: int
    :param channel: Source channel index (1-based).
    :type channel: int
    :param key: Unique measurement key within domain ``equipment`` and this command name.
    :type key: str

    :returns: Load resistance in ohms.
    :rtype: float

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    _ = key
    return float(_inst(asg_id).get_load_ohms(channel=channel))


@command
def set_power(
    *,
    asg_id: int,
    power_dbm: float,
    channel: int = 1,
    calibration: str | None = None,
) -> None:
    """Set output power in dBm.

    With ``calibration``, ``power_dbm`` is the desired post-path level; the
    instrument is programmed to ``power_dbm - loss_db`` at the last-set frequency.

    :param asg_id: Configured ``equipment.asg`` id from bench TOML.
    :type asg_id: int
    :param power_dbm: Output power in dBm (post-cal desired when ``calibration`` is set).
    :type power_dbm: float
    :param channel: Source channel index (1-based).
    :type channel: int
    :param calibration: Key from :func:`colosseum_equipment.api.calibration.load_calibration`.
    :type calibration: str | None, optional

    :returns: None

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    inst = _inst(asg_id)
    if calibration is None:
        _cal.clear_desired_power(inst, channel=channel)
        inst.set_power(power_dbm, channel=channel)
        return
    frequency = _cal.require_frequency(inst, channel=channel, what="set_power")
    programmed = _cal.programmed_power_dbm(power_dbm, key=calibration, frequency_hz=frequency)
    inst.set_power(programmed, channel=channel)
    _cal.remember_desired_power(inst, power_dbm, key=calibration, channel=channel)


@command
def set_duty_cycle_pct(*, asg_id: int, pct: float, channel: int = 1) -> None:
    """Set square-wave duty cycle in percent.

    :param asg_id: Configured ``equipment.asg`` id from bench TOML.
    :type asg_id: int
    :param pct: Duty cycle 0–100.
    :type pct: float
    :param channel: Source channel index (1-based).
    :type channel: int

    :returns: None

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    _inst(asg_id).set_duty_cycle_pct(pct, channel=channel)


@command
def set_output(*, asg_id: int, enabled: bool, channel: int = 1) -> None:
    """Enable or disable RF output.

    :param asg_id: Configured ``equipment.asg`` id from bench TOML.
    :type asg_id: int
    :param enabled: ``True`` to enable RF output, ``False`` to disable.
    :type enabled: bool
    :param channel: Source channel index (1-based).
    :type channel: int

    :returns: None

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    _inst(asg_id).set_output(enabled, channel=channel)


@command
def set_modulation_state(*, asg_id: int, enabled: bool, channel: int = 1) -> None:
    """Enable or disable AM modulation on a source channel.

    :param asg_id: Configured ``equipment.asg`` id from bench TOML.
    :type asg_id: int
    :param enabled: ``True`` to enable modulation.
    :type enabled: bool
    :param channel: Source channel index (1-based).
    :type channel: int

    :returns: None

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    _inst(asg_id).set_modulation_state(enabled, channel=channel)


@command
def set_burst_state(*, asg_id: int, enabled: bool, channel: int = 1) -> None:
    """Enable or disable burst mode on a source channel.

    :param asg_id: Configured ``equipment.asg`` id from bench TOML.
    :type asg_id: int
    :param enabled: ``True`` to enable burst.
    :type enabled: bool
    :param channel: Source channel index (1-based).
    :type channel: int

    :returns: None

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    _inst(asg_id).set_burst_state(enabled, channel=channel)


@command
def set_pulsegen_output(*, asg_id: int, enabled: bool, channel: int = 1) -> None:
    """Enable or disable the pulse generator output (R&S-style).

    :param asg_id: Configured ``equipment.asg`` id from bench TOML.
    :type asg_id: int
    :param enabled: ``True`` to enable pulse generator output, ``False`` to disable.
    :type enabled: bool
    :param channel: Source channel index (1-based).
    :type channel: int

    :returns: None

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    _inst(asg_id).set_pulsegen_output(enabled, channel=channel)


@command
def set_pulsemod_output(*, asg_id: int, enabled: bool, channel: int = 1) -> None:
    """Enable or disable pulse modulation.

    :param asg_id: Configured ``equipment.asg`` id from bench TOML.
    :type asg_id: int
    :param enabled: ``True`` to enable pulse modulation, ``False`` to disable.
    :type enabled: bool
    :param channel: Source channel index (1-based).
    :type channel: int

    :returns: None

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    _inst(asg_id).set_pulsemod_output(enabled, channel=channel)


@command
def set_pulse_period(*, asg_id: int, period_s: float, channel: int = 1) -> None:
    """Set pulse period in seconds.

    :param asg_id: Configured ``equipment.asg`` id from bench TOML.
    :type asg_id: int
    :param period_s: Pulse period in seconds.
    :type period_s: float
    :param channel: Source channel index (1-based).
    :type channel: int

    :returns: None

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    _inst(asg_id).set_pulse_period(period_s, channel=channel)


@command
def set_pulse_width(*, asg_id: int, width_s: float, channel: int = 1) -> None:
    """Set pulse width in seconds.

    :param asg_id: Configured ``equipment.asg`` id from bench TOML.
    :type asg_id: int
    :param width_s: Pulse width in seconds.
    :type width_s: float
    :param channel: Source channel index (1-based).
    :type channel: int

    :returns: None

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    _inst(asg_id).set_pulse_width(width_s, channel=channel)
