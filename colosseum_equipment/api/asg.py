"""Analog signal generator APIs exposed as ``col.equipment.asg``.

Configure instruments with ``[equipment.asg]`` in bench TOML (``asg_id``, ``resource``,
optional ``model`` and ``driver``; default driver is VISA/SCPI). Pulse generator and modulation
commands use R&S-style SCPI on the ``generic`` model.

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

from colosseum_equipment import calibration as _cal
from colosseum_equipment.api._broadcast import EquipmentId, broadcastable, require_int_id
from colosseum_equipment.connections import get_cached_instrument

_logger = get_logger("colosseum.equipment")


def _inst(asg_id: EquipmentId) -> Any:
    return get_cached_instrument("asg", require_int_id(asg_id, kind="asg"))


@command
@broadcastable("asg", "asg_id")
def set_frequency(
    *,
    asg_id: EquipmentId,
    frequency: float,
    channel: int = 1,
    calibration: str | None = None,
) -> None:
    """Set CW output frequency in hertz.

    When ``calibration`` is set, retunes programmed power so the post-cal
    (desired) output level from the last ``set_power(..., calibration=)`` is
    held at the new frequency.

    :param asg_id: Configured ``equipment.asg`` ID.

    :param frequency: Output frequency in hertz.

    :param channel: Source channel index (1-based).

    :param calibration: Key from :func:`colosseum_equipment.api.calibration.load_calibration`.
    """
    _logger.info("Setting frequency on ASG %s channel %s to %s Hz", asg_id, channel, frequency)
    inst = _inst(asg_id)
    inst.set_frequency(frequency, channel=channel)
    _cal.bind_frequency(inst, frequency, channel=channel)
    if calibration is not None:
        desired = _cal.require_desired_power(inst, channel=channel)
        programmed = _cal.programmed_power_dbm(desired, key=calibration, frequency_hz=frequency)
        inst.set_power(programmed, channel=channel)
        _cal.remember_desired_power(inst, desired, key=calibration, channel=channel)


@command
@broadcastable("asg", "asg_id")
def set_waveform(*, asg_id: EquipmentId, waveform: str, channel: int = 1) -> None:
    """Set output waveform (``sine``, ``square``, ``ramp``, ``pulse``, ``noise``, ``arb``).

    :param asg_id: Configured ``equipment.asg`` ID.

    :param waveform: Waveform name.

    :param channel: Source channel index (1-based).
    """
    _logger.info("Setting waveform on ASG %s channel %s to %s", asg_id, channel, waveform)
    _inst(asg_id).set_waveform(waveform, channel=channel)


@command
@broadcastable("asg", "asg_id")
def set_amplitude_vpp(*, asg_id: EquipmentId, vpp: float, channel: int = 1) -> None:
    """Set output amplitude in volts peak-to-peak.

    :param asg_id: Configured ``equipment.asg`` ID.

    :param vpp: Amplitude in Vpp.

    :param channel: Source channel index (1-based).
    """
    _logger.info("Setting amplitude on ASG %s channel %s to %s Vpp", asg_id, channel, vpp)
    _inst(asg_id).set_amplitude_vpp(vpp, channel=channel)


@command
@broadcastable("asg", "asg_id")
def set_amplitude_vrms(*, asg_id: EquipmentId, vrms: float, channel: int = 1) -> None:
    """Set output amplitude in volts RMS.

    :param asg_id: Configured ``equipment.asg`` ID.

    :param vrms: Amplitude in Vrms.

    :param channel: Source channel index (1-based).
    """
    _logger.info("Setting amplitude on ASG %s channel %s to %s Vrms", asg_id, channel, vrms)
    _inst(asg_id).set_amplitude_vrms(vrms, channel=channel)


@command
@broadcastable("asg", "asg_id")
def set_offset_v(*, asg_id: EquipmentId, offset_v: float, channel: int = 1) -> None:
    """Set DC offset in volts.

    :param asg_id: Configured ``equipment.asg`` ID.

    :param offset_v: Offset voltage.

    :param channel: Source channel index (1-based).
    """
    _logger.info("Setting offset on ASG %s channel %s to %s V", asg_id, channel, offset_v)
    _inst(asg_id).set_offset_v(offset_v, channel=channel)


@command
@broadcastable("asg", "asg_id")
def set_load_ohms(*, asg_id: EquipmentId, ohms: float, channel: int = 1) -> None:
    """Set output load impedance in ohms.

    :param asg_id: Configured ``equipment.asg`` ID.

    :param ohms: Load resistance in ohms.

    :param channel: Source channel index (1-based).
    """
    _logger.info("Setting load on ASG %s channel %s to %s ohms", asg_id, channel, ohms)
    _inst(asg_id).set_load_ohms(ohms, channel=channel)


@measurement
def get_load_ohms(*, asg_id: int, channel: int = 1, key: str) -> float:
    """Read configured output load impedance in ohms.

    :param asg_id: Configured ``equipment.asg`` ID.

    :param channel: Source channel index (1-based).

    :param key: Unique measurement key within domain ``equipment`` and this command name.

    :returns: Load resistance in ohms.
    :rtype: float
    """
    _logger.info("Reading load from ASG %s channel %s", asg_id, channel)
    _ = key
    return float(_inst(asg_id).get_load_ohms(channel=channel))


@command
@broadcastable("asg", "asg_id")
def set_power(
    *,
    asg_id: EquipmentId,
    power_dbm: float,
    channel: int = 1,
    calibration: str | None = None,
) -> None:
    """Set output power in dBm.

    With ``calibration``, ``power_dbm`` is the desired post-path level; the
    instrument is programmed to ``power_dbm - loss_db`` at the last-set frequency.

    :param asg_id: Configured ``equipment.asg`` ID.

    :param power_dbm: Output power in dBm (post-cal desired when ``calibration`` is set).

    :param channel: Source channel index (1-based).

    :param calibration: Key from :func:`colosseum_equipment.api.calibration.load_calibration`.
    """
    _logger.info("Setting output power on ASG %s channel %s to %s dBm", asg_id, channel, power_dbm)
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
@broadcastable("asg", "asg_id")
def set_duty_cycle_pct(*, asg_id: EquipmentId, pct: float, channel: int = 1) -> None:
    """Set square-wave duty cycle in percent.

    :param asg_id: Configured ``equipment.asg`` ID.

    :param pct: Duty cycle 0–100.

    :param channel: Source channel index (1-based).
    """
    _logger.info("Setting duty cycle on ASG %s channel %s to %s %%", asg_id, channel, pct)
    _inst(asg_id).set_duty_cycle_pct(pct, channel=channel)


@command
@broadcastable("asg", "asg_id")
def set_output(*, asg_id: EquipmentId, enabled: bool, channel: int = 1) -> None:
    """Enable or disable RF output.

    :param asg_id: Configured ``equipment.asg`` ID.

    :param enabled: ``True`` to enable RF output, ``False`` to disable.

    :param channel: Source channel index (1-based).
    """
    _logger.info(
        "%s output on ASG %s channel %s",
        "Enabling" if enabled else "Disabling",
        asg_id,
        channel,
    )
    _inst(asg_id).set_output(enabled, channel=channel)


@command
@broadcastable("asg", "asg_id")
def set_modulation_state(*, asg_id: EquipmentId, enabled: bool, channel: int = 1) -> None:
    """Enable or disable AM modulation on a source channel.

    :param asg_id: Configured ``equipment.asg`` ID.

    :param enabled: ``True`` to enable modulation.

    :param channel: Source channel index (1-based).
    """
    _logger.info(
        "%s modulation on ASG %s channel %s",
        "Enabling" if enabled else "Disabling",
        asg_id,
        channel,
    )
    _inst(asg_id).set_modulation_state(enabled, channel=channel)


@command
@broadcastable("asg", "asg_id")
def set_burst_state(*, asg_id: EquipmentId, enabled: bool, channel: int = 1) -> None:
    """Enable or disable burst mode on a source channel.

    :param asg_id: Configured ``equipment.asg`` ID.

    :param enabled: ``True`` to enable burst.

    :param channel: Source channel index (1-based).
    """
    _logger.info(
        "%s burst on ASG %s channel %s",
        "Enabling" if enabled else "Disabling",
        asg_id,
        channel,
    )
    _inst(asg_id).set_burst_state(enabled, channel=channel)


@command
@broadcastable("asg", "asg_id")
def set_pulsegen_output(*, asg_id: EquipmentId, enabled: bool, channel: int = 1) -> None:
    """Enable or disable the pulse generator output (R&S-style).

    :param asg_id: Configured ``equipment.asg`` ID.

    :param enabled: ``True`` to enable pulse generator output, ``False`` to disable.

    :param channel: Source channel index (1-based).
    """
    _logger.info(
        "%s pulse generator on ASG %s channel %s",
        "Enabling" if enabled else "Disabling",
        asg_id,
        channel,
    )
    _inst(asg_id).set_pulsegen_output(enabled, channel=channel)


@command
@broadcastable("asg", "asg_id")
def set_pulsemod_output(*, asg_id: EquipmentId, enabled: bool, channel: int = 1) -> None:
    """Enable or disable pulse modulation.

    :param asg_id: Configured ``equipment.asg`` ID.

    :param enabled: ``True`` to enable pulse modulation, ``False`` to disable.

    :param channel: Source channel index (1-based).
    """
    _logger.info(
        "%s pulse modulation on ASG %s channel %s",
        "Enabling" if enabled else "Disabling",
        asg_id,
        channel,
    )
    _inst(asg_id).set_pulsemod_output(enabled, channel=channel)


@command
@broadcastable("asg", "asg_id")
def set_pulse_period(*, asg_id: EquipmentId, period_s: float, channel: int = 1) -> None:
    """Set pulse period in seconds.

    :param asg_id: Configured ``equipment.asg`` ID.

    :param period_s: Pulse period in seconds.

    :param channel: Source channel index (1-based).
    """
    _logger.info("Setting pulse period on ASG %s channel %s to %s s", asg_id, channel, period_s)
    _inst(asg_id).set_pulse_period(period_s, channel=channel)


@command
@broadcastable("asg", "asg_id")
def set_pulse_width(*, asg_id: EquipmentId, width_s: float, channel: int = 1) -> None:
    """Set pulse width in seconds.

    :param asg_id: Configured ``equipment.asg`` ID.

    :param width_s: Pulse width in seconds.

    :param channel: Source channel index (1-based).
    """
    _logger.info("Setting pulse width on ASG %s channel %s to %s s", asg_id, channel, width_s)
    _inst(asg_id).set_pulse_width(width_s, channel=channel)
