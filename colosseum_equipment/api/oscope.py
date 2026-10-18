"""Oscilloscope APIs (``col.equipment.oscope``).

Documented workflow (Tek MDO4000 family):
preset → set_channel_* → set_timebase_* → set_trigger_* → set_acquire_*
→ acquire / single_acquire → measure_* / save_waveform / save_screenshot

``measure_*`` and ``save_*`` fetch the last completed capture; they do not re-arm.
"""

from __future__ import annotations

from colosseum.decorators import VerificationResult, command, measurement, verification

from colosseum_equipment.api._verify import tolerance_verifier
from colosseum_equipment.connections import get_cached_instrument
from colosseum_equipment.tools.mask_apply import apply_oscope_mask_setup
from colosseum_equipment.tools.mask_verify import verification_from_mask


def _inst(oscope_id: int):
    return get_cached_instrument("oscope", oscope_id)


@command
def preset(*, oscope_id: int) -> None:
    """Return the scope to a default preset."""
    _inst(oscope_id).preset()


@command
def set_channel_display(*, oscope_id: int, channel: int, enabled: bool) -> None:
    """Enable or disable a channel display."""
    _inst(oscope_id).set_channel_display(channel, enabled)


@command
def set_channel_scale_v(*, oscope_id: int, channel: int, volts_per_div: float) -> None:
    """Set vertical scale in volts per division."""
    _inst(oscope_id).set_channel_scale_v(channel, volts_per_div)


@command
def set_channel_offset_v(*, oscope_id: int, channel: int, offset_v: float) -> None:
    """Set vertical offset in volts."""
    _inst(oscope_id).set_channel_offset_v(channel, offset_v)


@command
def set_channel_coupling(*, oscope_id: int, channel: int, coupling: str) -> None:
    """Set channel coupling (``AC`` / ``DC`` / ``GND``)."""
    _inst(oscope_id).set_channel_coupling(channel, coupling)


@command
def set_channel_probe_attenuation(*, oscope_id: int, channel: int, attenuation: float) -> None:
    """Set probe attenuation factor (e.g. ``10`` for 10x)."""
    _inst(oscope_id).set_channel_probe_attenuation(channel, attenuation)


@command
def set_channel_bandwidth_limit(*, oscope_id: int, channel: int, enabled: bool) -> None:
    """Enable or disable channel bandwidth limit."""
    _inst(oscope_id).set_channel_bandwidth_limit(channel, enabled)


@command
def set_channel_impedance(*, oscope_id: int, channel: int, ohms: float) -> None:
    """Set channel termination impedance (``50`` or ``1e6``)."""
    _inst(oscope_id).set_channel_impedance(channel, ohms)


@measurement
def get_channel_scale_v(*, oscope_id: int, channel: int, key: str) -> float:
    """Read configured vertical scale (V/div)."""
    _ = key
    return float(_inst(oscope_id).get_channel_scale_v(channel))


@measurement
def get_channel_offset_v(*, oscope_id: int, channel: int, key: str) -> float:
    """Read configured vertical offset (V)."""
    _ = key
    return float(_inst(oscope_id).get_channel_offset_v(channel))


@command
def set_timebase_scale(*, oscope_id: int, seconds_per_div: float) -> None:
    """Set horizontal timebase scale."""
    _inst(oscope_id).set_timebase_scale(seconds_per_div)


@command
def set_timebase_position_s(*, oscope_id: int, position_s: float) -> None:
    """Set horizontal position / delay."""
    _inst(oscope_id).set_timebase_position_s(position_s)


@command
def set_record_length(*, oscope_id: int, points: int) -> None:
    """Set acquisition record length in points."""
    _inst(oscope_id).set_record_length(points)


@measurement
def get_record_length(*, oscope_id: int, key: str) -> float:
    """Read configured record length."""
    _ = key
    return float(_inst(oscope_id).get_record_length())


@command
def set_trigger_mode(*, oscope_id: int, mode: str) -> None:
    """Set trigger mode (``auto`` / ``normal`` / ``single``)."""
    _inst(oscope_id).set_trigger_mode(mode)


@command
def set_trigger_source(*, oscope_id: int, source: str) -> None:
    """Set edge trigger source (e.g. ``CH1``)."""
    _inst(oscope_id).set_trigger_source(source)


@command
def set_trigger_level_v(*, oscope_id: int, level_v: float) -> None:
    """Set edge trigger level in volts."""
    _inst(oscope_id).set_trigger_level_v(level_v)


@command
def set_trigger_slope(*, oscope_id: int, slope: str) -> None:
    """Set edge trigger slope (``rising`` / ``falling``)."""
    _inst(oscope_id).set_trigger_slope(slope)


@command
def set_trigger_holdoff_s(*, oscope_id: int, holdoff_s: float) -> None:
    """Set trigger holdoff time in seconds."""
    _inst(oscope_id).set_trigger_holdoff_s(holdoff_s)


@command
def force_trigger(*, oscope_id: int) -> None:
    """Force a trigger event."""
    _inst(oscope_id).force_trigger()


@command
def wait_for_trigger(*, oscope_id: int, timeout_s: float) -> None:
    """Wait until the scope reports a triggered / complete state."""
    _inst(oscope_id).wait_for_trigger(timeout_s=timeout_s)


@command
def set_acquire_mode(*, oscope_id: int, mode: str) -> None:
    """Set acquire mode (``sample`` / ``peak`` / ``average`` / ``hres``)."""
    _inst(oscope_id).set_acquire_mode(mode)


@command
def set_acquire_averages(*, oscope_id: int, count: int) -> None:
    """Set number of averages when acquire mode is average."""
    _inst(oscope_id).set_acquire_averages(count)


@command
def run(*, oscope_id: int) -> None:
    """Start continuous acquisition (arm)."""
    _inst(oscope_id).run()


@command
def stop(*, oscope_id: int) -> None:
    """Stop acquisition."""
    _inst(oscope_id).stop()


@command
def single_acquire(*, oscope_id: int) -> None:
    """Arm a single acquisition and wait for OPC completion."""
    _inst(oscope_id).single_acquire()


@command
def abort(*, oscope_id: int) -> None:
    """Abort / stop an in-progress acquisition."""
    _inst(oscope_id).abort()


@command
def wait_complete(*, oscope_id: int, timeout_s: float) -> None:
    """Wait for the current acquisition to complete."""
    _inst(oscope_id).wait_complete(timeout_s=timeout_s)


@command
def acquire(*, oscope_id: int, timeout_s: float = 10.0) -> str:
    """Arm single acquisition, wait, return capture id."""
    return str(_inst(oscope_id).acquire(timeout_s=timeout_s))


@measurement
def get_acquire_state(*, oscope_id: int, key: str) -> str:
    """Read acquisition / trigger state string."""
    _ = key
    return str(_inst(oscope_id).get_acquire_state())


@measurement
def measure_vpp(*, oscope_id: int, channel: int = 1, key: str) -> float:
    """Measure peak-to-peak voltage from the last capture."""
    _ = key
    return float(_inst(oscope_id).measure_vpp(channel))


verify_vpp = tolerance_verifier("measure_vpp", name="verify_vpp", unit="V")


@measurement
def measure_vmax(*, oscope_id: int, channel: int = 1, key: str) -> float:
    """Measure maximum voltage from the last capture."""
    _ = key
    return float(_inst(oscope_id).measure_vmax(channel))


@measurement
def measure_vmin(*, oscope_id: int, channel: int = 1, key: str) -> float:
    """Measure minimum voltage from the last capture."""
    _ = key
    return float(_inst(oscope_id).measure_vmin(channel))


@measurement
def measure_vrms(*, oscope_id: int, channel: int = 1, key: str) -> float:
    """Measure RMS voltage from the last capture."""
    _ = key
    return float(_inst(oscope_id).measure_vrms(channel))


@measurement
def measure_frequency_hz(*, oscope_id: int, channel: int = 1, key: str) -> float:
    """Measure frequency from the last capture."""
    _ = key
    return float(_inst(oscope_id).measure_frequency_hz(channel))


@measurement
def measure_period_s(*, oscope_id: int, channel: int = 1, key: str) -> float:
    """Measure period from the last capture."""
    _ = key
    return float(_inst(oscope_id).measure_period_s(channel))


@measurement
def measure_rise_time_s(*, oscope_id: int, channel: int = 1, key: str) -> float:
    """Measure rise time from the last capture."""
    _ = key
    return float(_inst(oscope_id).measure_rise_time_s(channel))


@measurement
def measure_fall_time_s(*, oscope_id: int, channel: int = 1, key: str) -> float:
    """Measure fall time from the last capture."""
    _ = key
    return float(_inst(oscope_id).measure_fall_time_s(channel))


@command
def save_waveform(*, oscope_id: int, channel: int, path: str, key: str = "") -> None:
    """Download waveform with preamble metadata and register an artifact."""
    _inst(oscope_id).save_waveform(channel=channel, path=path, key=key)


@command
def save_screenshot(*, oscope_id: int, path: str, key: str = "") -> None:
    """Save a screen capture under the run directory."""
    _inst(oscope_id).save_screenshot(path, key=key)


@command
def apply_mask_setup(
    *,
    oscope_id: int,
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
    apply_oscope_mask_setup(mask, oscope_id=oscope_id, channel=channel)


@verification
def verify_mask(
    *,
    key: str,
    mask: str = "",
    optional: bool = False,
) -> VerificationResult:
    """Verify a prior ``save_waveform`` CSV against a mask JSON file.

    ``mask`` may come from ``parameters.toml`` for ``key``.
    """
    return verification_from_mask(
        key=key,
        mask=mask,
        prefer_commands=("save_waveform",),
        optional=optional,
    )
