"""Oscilloscope APIs (``col.equipment.oscope``).

Documented workflow (Tek MDO4000 family):
preset → set_channel_* → set_timebase_* → set_trigger_* → set_acquire_*
→ acquire / single_acquire → measure_* / save_waveform / save_screenshot

``measure_*`` and ``save_*`` fetch the last completed capture; they do not re-arm.
"""

from __future__ import annotations

from typing import Any

from colosseum.decorators import VerificationResult, command, measurement, verification

from colosseum_equipment.api._broadcast import EquipmentId, broadcastable, require_int_id
from colosseum_equipment.api._verify import tolerance_verifier
from colosseum_equipment.connections import get_cached_instrument
from colosseum_equipment.tools.mask_apply import apply_oscope_mask_setup
from colosseum_equipment.tools.mask_verify import verification_from_mask


def _inst(oscope_id: EquipmentId) -> Any:
    return get_cached_instrument('oscope', require_int_id(oscope_id, kind='oscope'))


@command
@broadcastable("oscope", "oscope_id")
def preset(*, oscope_id: EquipmentId) -> None:
    """Return the scope to a default preset.

    :param oscope_id: Integer ID from the configured equipment.oscope row. Select an existing ID
        in that section.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _inst(oscope_id).preset()


@command
@broadcastable("oscope", "oscope_id")
def set_channel_display(*, oscope_id: EquipmentId, channel: int, enabled: bool) -> None:
    """Enable or disable a channel display.

    :param oscope_id: Integer ID from the configured equipment.oscope row. Select an existing ID
        in that section.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.
    :param enabled: True to enable the named feature; false to disable it.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _inst(oscope_id).set_channel_display(channel, enabled)


@command
@broadcastable("oscope", "oscope_id")
def set_channel_scale_v(*, oscope_id: EquipmentId, channel: int, volts_per_div: float) -> None:
    """Set vertical scale in volts per division.

    :param oscope_id: Integer ID from the configured equipment.oscope row. Select an existing ID
        in that section.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.
    :param volts_per_div: Vertical scale in volts per display division; range depends on the
        scope/channel.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _inst(oscope_id).set_channel_scale_v(channel, volts_per_div)


@command
@broadcastable("oscope", "oscope_id")
def set_channel_offset_v(*, oscope_id: EquipmentId, channel: int, offset_v: float) -> None:
    """Set vertical offset in volts.

    :param oscope_id: Integer ID from the configured equipment.oscope row. Select an existing ID
        in that section.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.
    :param offset_v: Vertical offset in volts; range depends on the scope/channel.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _inst(oscope_id).set_channel_offset_v(channel, offset_v)


@command
@broadcastable("oscope", "oscope_id")
def set_channel_coupling(*, oscope_id: EquipmentId, channel: int, coupling: str) -> None:
    """Set channel coupling (``AC`` / ``DC`` / ``GND``).

    :param oscope_id: Integer ID from the configured equipment.oscope row. Select an existing ID
        in that section.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.
    :param coupling: Channel coupling token, typically AC, DC, or GND; only use modes supported
        by the scope.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _inst(oscope_id).set_channel_coupling(channel, coupling)


@command
@broadcastable("oscope", "oscope_id")
def set_channel_probe_attenuation(*, oscope_id: EquipmentId, channel: int, attenuation: float) -> None:
    """Set probe attenuation factor (e.g. ``10`` for 10x).

    :param oscope_id: Integer ID from the configured equipment.oscope row. Select an existing ID
        in that section.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.
    :param attenuation: Probe attenuation factor (for example 10 for a 10:1 probe), not a value
        in decibels.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _inst(oscope_id).set_channel_probe_attenuation(channel, attenuation)


@command
@broadcastable("oscope", "oscope_id")
def set_channel_bandwidth_limit(*, oscope_id: EquipmentId, channel: int, enabled: bool) -> None:
    """Enable or disable channel bandwidth limit.

    :param oscope_id: Integer ID from the configured equipment.oscope row. Select an existing ID
        in that section.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.
    :param enabled: True to enable the named feature; false to disable it.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _inst(oscope_id).set_channel_bandwidth_limit(channel, enabled)


@command
@broadcastable("oscope", "oscope_id")
def set_channel_impedance(*, oscope_id: EquipmentId, channel: int, ohms: float) -> None:
    """Set channel termination impedance (``50`` or ``1e6``).

    :param oscope_id: Integer ID from the configured equipment.oscope row. Select an existing ID
        in that section.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.
    :param ohms: Impedance in ohms. The configured model determines the accepted values.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _inst(oscope_id).set_channel_impedance(channel, ohms)


@measurement
def get_channel_scale_v(*, oscope_id: int, channel: int, key: str) -> float:
    """Read configured vertical scale (V/div).

    :param oscope_id: Integer ID from the configured equipment.oscope row. Select an existing ID
        in that section.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.
    :param key: Evidence key for this operation. Keep distinct keys for separate facts; see the
        evidence lookup rules in the core guide.

    :returns: Recorded channel scale v in volts per division.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _ = key
    return float(_inst(oscope_id).get_channel_scale_v(channel))


@measurement
def get_channel_offset_v(*, oscope_id: int, channel: int, key: str) -> float:
    """Read configured vertical offset (V).

    :param oscope_id: Integer ID from the configured equipment.oscope row. Select an existing ID
        in that section.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.
    :param key: Evidence key for this operation. Keep distinct keys for separate facts; see the
        evidence lookup rules in the core guide.

    :returns: Recorded channel offset v in volts.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _ = key
    return float(_inst(oscope_id).get_channel_offset_v(channel))


@command
@broadcastable("oscope", "oscope_id")
def set_timebase_scale(*, oscope_id: EquipmentId, seconds_per_div: float) -> None:
    """Set horizontal timebase scale.

    :param oscope_id: Integer ID from the configured equipment.oscope row. Select an existing ID
        in that section.
    :param seconds_per_div: Horizontal scale in seconds per display division; range depends on
        the scope.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _inst(oscope_id).set_timebase_scale(seconds_per_div)


@command
@broadcastable("oscope", "oscope_id")
def set_timebase_position_s(*, oscope_id: EquipmentId, position_s: float) -> None:
    """Set horizontal position / delay.

    :param oscope_id: Integer ID from the configured equipment.oscope row. Select an existing ID
        in that section.
    :param position_s: Horizontal trigger position in seconds using the selected scope's
        reference convention.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _inst(oscope_id).set_timebase_position_s(position_s)


@command
@broadcastable("oscope", "oscope_id")
def set_record_length(*, oscope_id: EquipmentId, points: int) -> None:
    """Set acquisition record length in points.

    :param oscope_id: Integer ID from the configured equipment.oscope row. Select an existing ID
        in that section.
    :param points: Requested record length in sample points; supported lengths depend on the
        scope and mode.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _inst(oscope_id).set_record_length(points)


@measurement
def get_record_length(*, oscope_id: int, key: str) -> float:
    """Read configured record length.

    :param oscope_id: Integer ID from the configured equipment.oscope row. Select an existing ID
        in that section.
    :param key: Evidence key for this operation. Keep distinct keys for separate facts; see the
        evidence lookup rules in the core guide.

    :returns: Recorded sample count as a float.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _ = key
    return float(_inst(oscope_id).get_record_length())


@command
@broadcastable("oscope", "oscope_id")
def set_trigger_mode(*, oscope_id: EquipmentId, mode: str) -> None:
    """Set trigger mode (``auto`` / ``normal`` / ``single``).

    :param oscope_id: Integer ID from the configured equipment.oscope row. Select an existing ID
        in that section.
    :param mode: Model-specific acquisition or trigger mode token. Use the configured scope's
        supported command vocabulary.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _inst(oscope_id).set_trigger_mode(mode)


@command
@broadcastable("oscope", "oscope_id")
def set_trigger_source(*, oscope_id: EquipmentId, source: str) -> None:
    """Set edge trigger source (e.g. ``CH1``).

    :param oscope_id: Integer ID from the configured equipment.oscope row. Select an existing ID
        in that section.
    :param source: Trigger source token accepted by the configured scope, such as CHAN1 or EXT.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _inst(oscope_id).set_trigger_source(source)


@command
@broadcastable("oscope", "oscope_id")
def set_trigger_level_v(*, oscope_id: EquipmentId, level_v: float) -> None:
    """Set edge trigger level in volts.

    :param oscope_id: Integer ID from the configured equipment.oscope row. Select an existing ID
        in that section.
    :param level_v: Trigger threshold in volts using the selected trigger source.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _inst(oscope_id).set_trigger_level_v(level_v)


@command
@broadcastable("oscope", "oscope_id")
def set_trigger_slope(*, oscope_id: EquipmentId, slope: str) -> None:
    """Set edge trigger slope (``rising`` / ``falling``).

    :param oscope_id: Integer ID from the configured equipment.oscope row. Select an existing ID
        in that section.
    :param slope: Trigger edge token, such as POS or NEG; supported tokens depend on the
        selected driver.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _inst(oscope_id).set_trigger_slope(slope)


@command
@broadcastable("oscope", "oscope_id")
def set_trigger_holdoff_s(*, oscope_id: EquipmentId, holdoff_s: float) -> None:
    """Set trigger holdoff time in seconds.

    :param oscope_id: Integer ID from the configured equipment.oscope row. Select an existing ID
        in that section.
    :param holdoff_s: Trigger holdoff in seconds; accepted range depends on the scope.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _inst(oscope_id).set_trigger_holdoff_s(holdoff_s)


@command
@broadcastable("oscope", "oscope_id")
def force_trigger(*, oscope_id: EquipmentId) -> None:
    """Force a trigger event.

    :param oscope_id: Integer ID from the configured equipment.oscope row. Select an existing ID
        in that section.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _inst(oscope_id).force_trigger()


@command
def wait_for_trigger(*, oscope_id: int, timeout_s: float) -> None:
    """Wait until the scope reports a triggered / complete state.

    :param oscope_id: Integer ID from the configured equipment.oscope row. Select an existing ID
        in that section.
    :param timeout_s: Maximum wait in seconds. Expiration does not establish that the operation
        completed.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _inst(oscope_id).wait_for_trigger(timeout_s=timeout_s)


@command
@broadcastable("oscope", "oscope_id")
def set_acquire_mode(*, oscope_id: EquipmentId, mode: str) -> None:
    """Set acquire mode (``sample`` / ``peak`` / ``average`` / ``hres``).

    :param oscope_id: Integer ID from the configured equipment.oscope row. Select an existing ID
        in that section.
    :param mode: Model-specific acquisition or trigger mode token. Use the configured scope's
        supported command vocabulary.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _inst(oscope_id).set_acquire_mode(mode)


@command
@broadcastable("oscope", "oscope_id")
def set_acquire_averages(*, oscope_id: EquipmentId, count: int) -> None:
    """Set number of averages when acquire mode is average.

    :param oscope_id: Integer ID from the configured equipment.oscope row. Select an existing ID
        in that section.
    :param count: Number of acquisition averages.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _inst(oscope_id).set_acquire_averages(count)


@command
@broadcastable("oscope", "oscope_id")
def run(*, oscope_id: EquipmentId) -> None:
    """Start continuous acquisition (arm).

    :param oscope_id: Integer ID from the configured equipment.oscope row. Select an existing ID
        in that section.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _inst(oscope_id).run()


@command
@broadcastable("oscope", "oscope_id")
def stop(*, oscope_id: EquipmentId) -> None:
    """Stop acquisition.

    :param oscope_id: Integer ID from the configured equipment.oscope row. Select an existing ID
        in that section.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _inst(oscope_id).stop()


@command
@broadcastable("oscope", "oscope_id")
def arm_single(*, oscope_id: EquipmentId) -> None:
    """Arm one capture without waiting; generate the external event next.

    Call :func:`wait_complete` before reading measurements or waveforms.
    Unlike :func:`acquire`, this call does not wait for a trigger.

    :param oscope_id: Integer ID from the configured equipment.oscope row. Select an existing ID
        in that section.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.


    Generate the stimulus after this call, then call wait_complete before
    fetching. See the instrument acquisition workflow and driver support matrix.
    """
    _inst(oscope_id).arm_single()


@command
def single_acquire(*, oscope_id: int) -> None:
    """Arm a single acquisition and wait for OPC completion.

    :param oscope_id: Integer ID from the configured equipment.oscope row. Select an existing ID
        in that section.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _inst(oscope_id).single_acquire()


@command
@broadcastable("oscope", "oscope_id")
def abort(*, oscope_id: EquipmentId) -> None:
    """Abort / stop an in-progress acquisition.

    :param oscope_id: Integer ID from the configured equipment.oscope row. Select an existing ID
        in that section.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _inst(oscope_id).abort()


@command
def wait_complete(*, oscope_id: int, timeout_s: float) -> None:
    """Wait for the current acquisition to complete.

    :param oscope_id: Integer ID from the configured equipment.oscope row. Select an existing ID
        in that section.
    :param timeout_s: Maximum wait in seconds. Expiration does not establish that the operation
        completed.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _inst(oscope_id).wait_complete(timeout_s=timeout_s)


@command
def acquire(*, oscope_id: int, timeout_s: float = 10.0) -> str:
    """Arm single acquisition, wait, return capture id.

    :param oscope_id: Integer ID from the configured equipment.oscope row. Select an existing ID
        in that section.
    :param timeout_s: Maximum wait in seconds. Expiration does not establish that the operation
        completed. Default: ``10.0``.

    :returns: Capture identifier string after single acquisition completes.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    return str(_inst(oscope_id).acquire(timeout_s=timeout_s))


@measurement
def get_acquire_state(*, oscope_id: int, key: str) -> str:
    """Read acquisition / trigger state string.

    :param oscope_id: Integer ID from the configured equipment.oscope row. Select an existing ID
        in that section.
    :param key: Evidence key for this operation. Keep distinct keys for separate facts; see the
        evidence lookup rules in the core guide.

    :returns: Acquisition/trigger state text; vocabulary depends on the selected scope.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _ = key
    return str(_inst(oscope_id).get_acquire_state())


@measurement
def measure_vpp(*, oscope_id: int, channel: int = 1, key: str) -> float:
    """Measure peak-to-peak voltage from the last capture.

    :param oscope_id: Integer ID from the configured equipment.oscope row. Select an existing ID
        in that section.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.
    :param key: Evidence key for this operation. Keep distinct keys for separate facts; see the
        evidence lookup rules in the core guide.

    :returns: Recorded vpp in volts.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _ = key
    return float(_inst(oscope_id).measure_vpp(channel))


verify_vpp = tolerance_verifier("measure_vpp", name="verify_vpp", unit="V")


@measurement
def measure_vmax(*, oscope_id: int, channel: int = 1, key: str) -> float:
    """Measure maximum voltage from the last capture.

    :param oscope_id: Integer ID from the configured equipment.oscope row. Select an existing ID
        in that section.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.
    :param key: Evidence key for this operation. Keep distinct keys for separate facts; see the
        evidence lookup rules in the core guide.

    :returns: Recorded vmax in volts.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _ = key
    return float(_inst(oscope_id).measure_vmax(channel))


@measurement
def measure_vmin(*, oscope_id: int, channel: int = 1, key: str) -> float:
    """Measure minimum voltage from the last capture.

    :param oscope_id: Integer ID from the configured equipment.oscope row. Select an existing ID
        in that section.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.
    :param key: Evidence key for this operation. Keep distinct keys for separate facts; see the
        evidence lookup rules in the core guide.

    :returns: Recorded vmin in volts.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _ = key
    return float(_inst(oscope_id).measure_vmin(channel))


@measurement
def measure_vrms(*, oscope_id: int, channel: int = 1, key: str) -> float:
    """Measure RMS voltage from the last capture.

    :param oscope_id: Integer ID from the configured equipment.oscope row. Select an existing ID
        in that section.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.
    :param key: Evidence key for this operation. Keep distinct keys for separate facts; see the
        evidence lookup rules in the core guide.

    :returns: Recorded vrms in volts.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _ = key
    return float(_inst(oscope_id).measure_vrms(channel))


@measurement
def measure_frequency_hz(*, oscope_id: int, channel: int = 1, key: str) -> float:
    """Measure frequency from the last capture.

    :param oscope_id: Integer ID from the configured equipment.oscope row. Select an existing ID
        in that section.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.
    :param key: Evidence key for this operation. Keep distinct keys for separate facts; see the
        evidence lookup rules in the core guide.

    :returns: Recorded frequency hz in hertz.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _ = key
    return float(_inst(oscope_id).measure_frequency_hz(channel))


@measurement
def measure_period_s(*, oscope_id: int, channel: int = 1, key: str) -> float:
    """Measure period from the last capture.

    :param oscope_id: Integer ID from the configured equipment.oscope row. Select an existing ID
        in that section.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.
    :param key: Evidence key for this operation. Keep distinct keys for separate facts; see the
        evidence lookup rules in the core guide.

    :returns: Recorded period s in seconds.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _ = key
    return float(_inst(oscope_id).measure_period_s(channel))


@measurement
def measure_rise_time_s(*, oscope_id: int, channel: int = 1, key: str) -> float:
    """Measure rise time from the last capture.

    :param oscope_id: Integer ID from the configured equipment.oscope row. Select an existing ID
        in that section.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.
    :param key: Evidence key for this operation. Keep distinct keys for separate facts; see the
        evidence lookup rules in the core guide.

    :returns: Recorded rise time s in seconds.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _ = key
    return float(_inst(oscope_id).measure_rise_time_s(channel))


@measurement
def measure_fall_time_s(*, oscope_id: int, channel: int = 1, key: str) -> float:
    """Measure fall time from the last capture.

    :param oscope_id: Integer ID from the configured equipment.oscope row. Select an existing ID
        in that section.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.
    :param key: Evidence key for this operation. Keep distinct keys for separate facts; see the
        evidence lookup rules in the core guide.

    :returns: Recorded fall time s in seconds.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _ = key
    return float(_inst(oscope_id).measure_fall_time_s(channel))


@command
def save_waveform(*, oscope_id: int, channel: int, path: str, key: str = "") -> None:
    """Download waveform with preamble metadata and register an artifact.

    :param oscope_id: Integer ID from the configured equipment.oscope row. Select an existing ID
        in that section.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.
    :param path: Destination file path, absolute or relative to the active run output directory;
        requires artifacts enabled.
    :param key: Evidence key for this operation. Keep distinct keys for separate facts; see the
        evidence lookup rules in the core guide. Default: ``''``.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _inst(oscope_id).save_waveform(channel=channel, path=path, key=key)


@command
def save_screenshot(*, oscope_id: int, path: str, key: str = "") -> None:
    """Save a screen capture under the run directory.

    :param oscope_id: Integer ID from the configured equipment.oscope row. Select an existing ID
        in that section.
    :param path: Destination file path, absolute or relative to the active run output directory;
        requires artifacts enabled.
    :param key: Evidence key for this operation. Keep distinct keys for separate facts; see the
        evidence lookup rules in the core guide. Default: ``''``.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _inst(oscope_id).save_screenshot(path, key=key)


@command
@broadcastable("oscope", "oscope_id")
def apply_mask_setup(
    *,
    oscope_id: EquipmentId,
    mask: str,
    channel: int = 1,
    key: str = "",
) -> None:
    """Apply mask JSON ``setup`` fields (timebase/scale/offset) to this oscilloscope.

    :param oscope_id: Configured ``equipment.oscope`` id from config TOML.
    :param mask: Path to mask JSON (or from ``parameters.toml`` via ``key=``).
    :param channel: Channel for vertical scale/offset (default 1).
    :param key: Optional parameters / evidence key for this step.
    """
    _ = key
    apply_oscope_mask_setup(mask, oscope_id=require_int_id(oscope_id, kind='oscope'), channel=channel)


@verification
def verify_mask(
    *,
    key: str,
    mask: str = "",
    optional: bool = False,
) -> VerificationResult:
    """Verify a prior ``save_waveform`` CSV against a mask JSON file.

    ``mask`` may come from ``parameters.toml`` for ``key``.

    :param key: Evidence key for this operation. Keep distinct keys for separate facts; see the
        evidence lookup rules in the core guide.
    :param mask: Mask definition used by this operation; see the mask workflow for supported
        structure and units. Default: ``''``.
    :param optional: When true, retain an unsuccessful outcome without failing the aggregate
        result. Commands and measurements also suppress their operation exception; a failed
        measurement returns None. Defaults to false.

    :returns: Recorded verification outcome (PASS, FAIL, ERROR, or BLOCKED), including the
        actual value when available.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    return verification_from_mask(
        key=key,
        mask=mask,
        prefer_commands=("save_waveform",),
        optional=optional,
    )
