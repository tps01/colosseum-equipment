"""Electronic load APIs (``col.equipment.eload``)."""

from __future__ import annotations

from typing import Any

from colosseum.decorators import command, measurement

from colosseum_equipment.api._verify import tolerance_verifier
from colosseum_equipment.connections import get_cached_instrument


def _inst(eload_id: int) -> Any:
    return get_cached_instrument("eload", eload_id)


@command
def set_mode(*, eload_id: int, mode: str, channel: int = 1) -> None:
    """Set operating mode (CC, CV, CP, or CR per model).

    :param eload_id: Integer ID from the configured equipment.eload row. Select an existing ID
        in that section.
    :param mode: Load mode token: CC, CV, CP, or CR, subject to the selected driver's
        capabilities.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _inst(eload_id).set_mode(mode, channel=channel)


@command
def set_current(*, eload_id: int, current: float, channel: int = 1) -> None:
    """Set constant-current level.

    :param eload_id: Integer ID from the configured equipment.eload row. Select an existing ID
        in that section.
    :param current: Current in amperes. Valid settings and protection limits depend on the
        instrument model and range.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _inst(eload_id).set_current(current, channel=channel)


@command
def set_voltage(*, eload_id: int, voltage: float, channel: int = 1) -> None:
    """Set constant-voltage level.

    :param eload_id: Integer ID from the configured equipment.eload row. Select an existing ID
        in that section.
    :param voltage: Voltage in volts. Valid settings and protection limits depend on the
        instrument model and output range.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _inst(eload_id).set_voltage(voltage, channel=channel)


@command
def set_power(*, eload_id: int, power: float, channel: int = 1) -> None:
    """Set constant-power level (use when load is in CP mode).

    :param eload_id: Integer ID from the configured equipment.eload row. Select an existing ID
        in that section.
    :param power: Power in watts. Supported settings depend on the configured load and range.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _inst(eload_id).set_power(power, channel=channel)


@command
def set_resistance(*, eload_id: int, resistance: float, channel: int = 1) -> None:
    """Set constant-resistance level (use when load is in CR mode).

    :param eload_id: Integer ID from the configured equipment.eload row. Select an existing ID
        in that section.
    :param resistance: Resistance in ohms. Supported settings depend on the configured load and
        range.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _inst(eload_id).set_resistance(resistance, channel=channel)


@command
def engage(*, eload_id: int, channel: int = 1) -> None:
    """Connect the load input.

    :param eload_id: Integer ID from the configured equipment.eload row. Select an existing ID
        in that section.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _inst(eload_id).engage(channel=channel)


@command
def disengage(*, eload_id: int, channel: int = 1) -> None:
    """Disconnect the load input.

    :param eload_id: Integer ID from the configured equipment.eload row. Select an existing ID
        in that section.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _inst(eload_id).disengage(channel=channel)


@command
def preset(*, eload_id: int) -> None:
    """Return the instrument to a default preset.

    :param eload_id: Integer ID from the configured equipment.eload row. Select an existing ID
        in that section.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _inst(eload_id).preset()


@command
def set_slew_rate(*, eload_id: int, amps_per_s: float, channel: int = 1) -> None:
    """Set current slew rate.

    :param eload_id: Integer ID from the configured equipment.eload row. Select an existing ID
        in that section.
    :param amps_per_s: Current slew rate in amperes per second; availability and range depend on
        the model.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _inst(eload_id).set_slew_rate(amps_per_s, channel=channel)


@command
def toggle_short(*, eload_id: int, enabled: bool, channel: int = 1) -> None:
    """Enable or disable input short.

    :param eload_id: Integer ID from the configured equipment.eload row. Select an existing ID
        in that section.
    :param enabled: True to enable the named feature; false to disable it.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _inst(eload_id).toggle_short(enabled, channel=channel)


@command
def set_ovp_v(*, eload_id: int, voltage: float, channel: int = 1) -> None:
    """Set over-voltage protection level.

    :param eload_id: Integer ID from the configured equipment.eload row. Select an existing ID
        in that section.
    :param voltage: Voltage in volts. Valid settings and protection limits depend on the
        instrument model and output range.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _inst(eload_id).set_ovp_v(voltage, channel=channel)


@command
def set_ocp_a(*, eload_id: int, current: float, channel: int = 1) -> None:
    """Set over-current protection level.

    :param eload_id: Integer ID from the configured equipment.eload row. Select an existing ID
        in that section.
    :param current: Current in amperes. Valid settings and protection limits depend on the
        instrument model and range.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _inst(eload_id).set_ocp_a(current, channel=channel)


@command
def set_opp_w(*, eload_id: int, power: float, channel: int = 1) -> None:
    """Set over-power protection level.

    :param eload_id: Integer ID from the configured equipment.eload row. Select an existing ID
        in that section.
    :param power: Power in watts. Supported settings depend on the configured load and range.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _inst(eload_id).set_opp_w(power, channel=channel)


@command
def clear_protection(*, eload_id: int, channel: int = 1) -> None:
    """Clear latched protection state.

    :param eload_id: Integer ID from the configured equipment.eload row. Select an existing ID
        in that section.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _inst(eload_id).clear_protection(channel=channel)


@command
def set_transient_mode(*, eload_id: int, mode: str, channel: int = 1) -> None:
    """Set transient generator mode.

    :param eload_id: Integer ID from the configured equipment.eload row. Select an existing ID
        in that section.
    :param mode: Model-specific transient mode token; consult the load's command set before
        enabling transients.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _inst(eload_id).set_transient_mode(mode, channel=channel)


@command
def set_transient_level_a(*, eload_id: int, current: float, channel: int = 1) -> None:
    """Set transient alternate current level.

    :param eload_id: Integer ID from the configured equipment.eload row. Select an existing ID
        in that section.
    :param current: Current in amperes. Valid settings and protection limits depend on the
        instrument model and range.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _inst(eload_id).set_transient_level_a(current, channel=channel)


@command
def set_transient_timer_s(*, eload_id: int, seconds: float, channel: int = 1) -> None:
    """Set transient dwell / timer in seconds.

    :param eload_id: Integer ID from the configured equipment.eload row. Select an existing ID
        in that section.
    :param seconds: Time in seconds. The configured model determines the accepted range.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _inst(eload_id).set_transient_timer_s(seconds, channel=channel)


@command
def toggle_transient(*, eload_id: int, enabled: bool, channel: int = 1) -> None:
    """Enable or disable transient mode.

    :param eload_id: Integer ID from the configured equipment.eload row. Select an existing ID
        in that section.
    :param enabled: True to enable the named feature; false to disable it.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _inst(eload_id).toggle_transient(enabled, channel=channel)


@command
def configure_list_step(
    *,
    eload_id: int,
    step: int,
    current_a: float | None = None,
    dwell_s: float | None = None,
    channel: int = 1,
) -> None:
    """Configure one step of a basic current list.

    :param eload_id: Integer ID from the configured equipment.eload row. Select an existing ID
        in that section.
    :param step: Instrument list-step index; numbering and available steps follow the selected
        load driver.
    :param current_a: Current for this list step in amperes; None leaves the step current
        unchanged.
    :param dwell_s: Dwell time for this list step in seconds; None leaves dwell unchanged.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _inst(eload_id).configure_list_step(
        step,
        current_a=current_a,
        dwell_s=dwell_s,
        channel=channel,
    )


@command
def set_list_count(*, eload_id: int, count: int, channel: int = 1) -> None:
    """Set list sequence step count.

    :param eload_id: Integer ID from the configured equipment.eload row. Select an existing ID
        in that section.
    :param count: List repetition count using the load's supported range.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _inst(eload_id).set_list_count(count, channel=channel)


@command
def toggle_list(*, eload_id: int, enabled: bool, channel: int = 1) -> None:
    """Enable or disable list mode.

    :param eload_id: Integer ID from the configured equipment.eload row. Select an existing ID
        in that section.
    :param enabled: True to enable the named feature; false to disable it.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _inst(eload_id).toggle_list(enabled, channel=channel)


@measurement
def measure_voltage(*, eload_id: int, channel: int = 1, key: str) -> float:
    """Read input voltage.

    :param eload_id: Integer ID from the configured equipment.eload row. Select an existing ID
        in that section.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.
    :param key: Evidence key for this operation. Keep distinct keys for separate facts; see the
        evidence lookup rules in the core guide.

    :returns: Recorded voltage in volts.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _ = key
    return float(_inst(eload_id).measure_voltage(channel=channel))


verify_voltage = tolerance_verifier("measure_voltage", name="verify_voltage", unit="V")


@measurement
def measure_current(*, eload_id: int, channel: int = 1, key: str) -> float:
    """Read input current.

    :param eload_id: Integer ID from the configured equipment.eload row. Select an existing ID
        in that section.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.
    :param key: Evidence key for this operation. Keep distinct keys for separate facts; see the
        evidence lookup rules in the core guide.

    :returns: Recorded current in amperes.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _ = key
    return float(_inst(eload_id).measure_current(channel=channel))


verify_current = tolerance_verifier("measure_current", name="verify_current", unit="A")


@measurement
def measure_power_w(*, eload_id: int, channel: int = 1, key: str) -> float:
    """Read input power in watts.

    :param eload_id: Integer ID from the configured equipment.eload row. Select an existing ID
        in that section.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.
    :param key: Evidence key for this operation. Keep distinct keys for separate facts; see the
        evidence lookup rules in the core guide.

    :returns: Recorded power w in watts.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _ = key
    return float(_inst(eload_id).measure_power_w(channel=channel))


verify_power_w = tolerance_verifier("measure_power_w", name="verify_power_w", unit="W")


@measurement
def measure_resistance_ohm(*, eload_id: int, channel: int = 1, key: str) -> float:
    """Read input resistance in ohms.

    :param eload_id: Integer ID from the configured equipment.eload row. Select an existing ID
        in that section.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.
    :param key: Evidence key for this operation. Keep distinct keys for separate facts; see the
        evidence lookup rules in the core guide.

    :returns: Recorded resistance ohm in ohms.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _ = key
    return float(_inst(eload_id).measure_resistance_ohm(channel=channel))


verify_resistance_ohm = tolerance_verifier(
    "measure_resistance_ohm",
    name="verify_resistance_ohm",
    unit="ohm",
)


@measurement
def measure_input_state(*, eload_id: int, channel: int = 1, key: str) -> float:
    """Read whether load input is engaged (``1.0`` / ``0.0``).

    :param eload_id: Integer ID from the configured equipment.eload row. Select an existing ID
        in that section.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.
    :param key: Evidence key for this operation. Keep distinct keys for separate facts; see the
        evidence lookup rules in the core guide.

    :returns: Recorded input state: 1.0 engaged, 0.0 disengaged.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _ = key
    engaged = _inst(eload_id).measure_input_state(channel=channel)
    return 1.0 if engaged else 0.0


verify_input_state = tolerance_verifier(
    "measure_input_state",
    name="verify_input_state",
    default_tolerance=0.0,
)
