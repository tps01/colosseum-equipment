"""Bench power supply APIs (``col.equipment.psu``)."""

from __future__ import annotations

from typing import Any

from colosseum.decorators import command, measurement

from colosseum_equipment.api._verify import tolerance_verifier
from colosseum_equipment.connections import get_cached_instrument


def _inst(psu_id: int) -> Any:
    return get_cached_instrument("psu", psu_id)


@command
def set_voltage(*, psu_id: int, voltage: float, channel: int = 1) -> None:
    """Set the programmed output voltage.

    :param psu_id: Configured ``equipment.psu`` id from bench TOML.
    :type psu_id: int
    :param voltage: Target voltage in volts.
    :type voltage: float
    :param channel: Output channel (1-based; default single-channel supply).
    :type channel: int, optional

    :returns: None

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    _inst(psu_id).set_voltage(voltage, channel=channel)


@command
def set_current_limit(*, psu_id: int, current: float, channel: int = 1) -> None:
    """Set the current limit.

    :param psu_id: Configured ``equipment.psu`` id from bench TOML.
    :type psu_id: int
    :param current: Current limit in amperes.
    :type current: float
    :param channel: Output channel (1-based).
    :type channel: int, optional

    :returns: None

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    _inst(psu_id).set_current_limit(current, channel=channel)


@command
def set_output(*, psu_id: int, enabled: bool, channel: int = 1) -> None:
    """Enable or disable the output.

    :param psu_id: Configured ``equipment.psu`` id from bench TOML.
    :type psu_id: int
    :param enabled: ``True`` to enable output, ``False`` to disable.
    :type enabled: bool
    :param channel: Output channel (1-based).
    :type channel: int, optional

    :returns: None

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    _inst(psu_id).set_output(enabled, channel=channel)


@command
def set_ovp_v(*, psu_id: int, voltage: float, channel: int = 1) -> None:
    """Set over-voltage protection level.

    :param psu_id: Integer ID from the configured equipment.psu row. Select an existing ID in
        that section.
    :param voltage: Voltage in volts. Valid settings and protection limits depend on the
        instrument model and output range.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _inst(psu_id).set_ovp_v(voltage, channel=channel)


@command
def set_ocp_a(*, psu_id: int, current: float, channel: int = 1) -> None:
    """Set over-current protection level.

    :param psu_id: Integer ID from the configured equipment.psu row. Select an existing ID in
        that section.
    :param current: Current in amperes. Valid settings and protection limits depend on the
        instrument model and range.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _inst(psu_id).set_ocp_a(current, channel=channel)


@command
def toggle_ovp(*, psu_id: int, enabled: bool, channel: int = 1) -> None:
    """Enable or disable over-voltage protection.

    :param psu_id: Integer ID from the configured equipment.psu row. Select an existing ID in
        that section.
    :param enabled: True to enable the named feature; false to disable it.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _inst(psu_id).toggle_ovp(enabled, channel=channel)


@command
def toggle_ocp(*, psu_id: int, enabled: bool, channel: int = 1) -> None:
    """Enable or disable over-current protection.

    :param psu_id: Integer ID from the configured equipment.psu row. Select an existing ID in
        that section.
    :param enabled: True to enable the named feature; false to disable it.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _inst(psu_id).toggle_ocp(enabled, channel=channel)


@command
def clear_protection(*, psu_id: int, channel: int = 1) -> None:
    """Clear latched protection / fault state.

    :param psu_id: Integer ID from the configured equipment.psu row. Select an existing ID in
        that section.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _inst(psu_id).clear_protection(channel=channel)


@command
def set_remote_sense(*, psu_id: int, enabled: bool, channel: int = 1) -> None:
    """Enable or disable remote (4-wire) sense.

    :param psu_id: Integer ID from the configured equipment.psu row. Select an existing ID in
        that section.
    :param enabled: True to enable the named feature; false to disable it.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _inst(psu_id).set_remote_sense(enabled, channel=channel)


@command
def set_slew_voltage(*, psu_id: int, volts_per_s: float, channel: int = 1) -> None:
    """Set voltage slew rate (best-effort SCPI).

    :param psu_id: Integer ID from the configured equipment.psu row. Select an existing ID in
        that section.
    :param volts_per_s: Voltage slew rate in volts per second; availability and range depend on
        the model.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _inst(psu_id).set_slew_voltage(volts_per_s, channel=channel)


@command
def set_slew_current(*, psu_id: int, amps_per_s: float, channel: int = 1) -> None:
    """Set current slew rate (best-effort SCPI).

    :param psu_id: Integer ID from the configured equipment.psu row. Select an existing ID in
        that section.
    :param amps_per_s: Current slew rate in amperes per second; availability and range depend on
        the model.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _inst(psu_id).set_slew_current(amps_per_s, channel=channel)


@command
def set_tracking_mode(*, psu_id: int, mode: str, channel: int = 1) -> None:
    """Set series/parallel tracking mode (best-effort SCPI).

    :param psu_id: Integer ID from the configured equipment.psu row. Select an existing ID in
        that section.
    :param mode: Tracking token. Generic SCPI accepts ON, OFF, TRACK, or IND; vendor semantics
        and support depend on the supply.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _inst(psu_id).set_tracking_mode(mode, channel=channel)


@command
def wait_for_current(
    *,
    psu_id: int,
    current: float,
    timeout_s: float,
    tolerance: float = 0.01,
    channel: int = 1,
) -> None:
    """Block until measured output current reaches the target within tolerance.

    :param psu_id: Configured ``equipment.psu`` id from bench TOML.
    :type psu_id: int
    :param current: Target current in amperes.
    :type current: float
    :param timeout_s: Maximum wait time in seconds.
    :type timeout_s: float
    :param tolerance: Allowed absolute deviation in amperes.
    :type tolerance: float, optional
    :param channel: Output channel (1-based).
    :type channel: int, optional

    :returns: None

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    _inst(psu_id).wait_for_current(
        current,
        timeout_s=timeout_s,
        tolerance=tolerance,
        channel=channel,
    )


@command
def wait_for_voltage(
    *,
    psu_id: int,
    voltage: float,
    timeout_s: float,
    tolerance: float = 0.01,
    channel: int = 1,
) -> None:
    """Block until measured output voltage reaches the target within tolerance.

    :param psu_id: Integer ID from the configured equipment.psu row. Select an existing ID in
        that section.
    :param voltage: Voltage in volts. Valid settings and protection limits depend on the
        instrument model and output range.
    :param timeout_s: Maximum wait in seconds. Expiration does not establish that the operation
        completed.
    :param tolerance: Maximum absolute difference from the target in the same units as that
        target. Default: ``0.01``.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _inst(psu_id).wait_for_voltage(
        voltage,
        timeout_s=timeout_s,
        tolerance=tolerance,
        channel=channel,
    )


@measurement
def get_voltage(*, psu_id: int, channel: int = 1, key: str) -> float:
    """Read programmed output voltage setpoint.

    :param psu_id: Integer ID from the configured equipment.psu row. Select an existing ID in
        that section.
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
    return float(_inst(psu_id).get_voltage(channel=channel))


verify_get_voltage = tolerance_verifier("get_voltage", name="verify_get_voltage", unit="V")


@measurement
def get_current_limit(*, psu_id: int, channel: int = 1, key: str) -> float:
    """Read programmed current limit setpoint.

    :param psu_id: Integer ID from the configured equipment.psu row. Select an existing ID in
        that section.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.
    :param key: Evidence key for this operation. Keep distinct keys for separate facts; see the
        evidence lookup rules in the core guide.

    :returns: Recorded current limit in amperes.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _ = key
    return float(_inst(psu_id).get_current_limit(channel=channel))


verify_get_current_limit = tolerance_verifier(
    "get_current_limit",
    name="verify_get_current_limit",
    unit="A",
)


@measurement
def get_output(*, psu_id: int, channel: int = 1, key: str) -> float:
    """Read programmed output enable state (``1.0`` on, ``0.0`` off).

    :param psu_id: Integer ID from the configured equipment.psu row. Select an existing ID in
        that section.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.
    :param key: Evidence key for this operation. Keep distinct keys for separate facts; see the
        evidence lookup rules in the core guide.

    :returns: Recorded state (1.0 enabled, 0.0 disabled).

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _ = key
    enabled = _inst(psu_id).get_output(channel=channel)
    return 1.0 if enabled else 0.0


verify_get_output = tolerance_verifier(
    "get_output",
    name="verify_get_output",
    default_tolerance=0.0,
)


@measurement
def get_ovp_v(*, psu_id: int, channel: int = 1, key: str) -> float:
    """Read over-voltage protection level.

    :param psu_id: Integer ID from the configured equipment.psu row. Select an existing ID in
        that section.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.
    :param key: Evidence key for this operation. Keep distinct keys for separate facts; see the
        evidence lookup rules in the core guide.

    :returns: Recorded ovp v in volts.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _ = key
    return float(_inst(psu_id).get_ovp_v(channel=channel))


@measurement
def get_ocp_a(*, psu_id: int, channel: int = 1, key: str) -> float:
    """Read over-current protection level.

    :param psu_id: Integer ID from the configured equipment.psu row. Select an existing ID in
        that section.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.
    :param key: Evidence key for this operation. Keep distinct keys for separate facts; see the
        evidence lookup rules in the core guide.

    :returns: Recorded ocp a in amperes.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _ = key
    return float(_inst(psu_id).get_ocp_a(channel=channel))


@measurement
def get_ovp_enabled(*, psu_id: int, channel: int = 1, key: str) -> float:
    """Read whether OVP is enabled (``1.0`` / ``0.0``).

    :param psu_id: Integer ID from the configured equipment.psu row. Select an existing ID in
        that section.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.
    :param key: Evidence key for this operation. Keep distinct keys for separate facts; see the
        evidence lookup rules in the core guide.

    :returns: Recorded state (1.0 enabled, 0.0 disabled).

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _ = key
    return 1.0 if _inst(psu_id).get_ovp_enabled(channel=channel) else 0.0


@measurement
def get_ocp_enabled(*, psu_id: int, channel: int = 1, key: str) -> float:
    """Read whether OCP is enabled (``1.0`` / ``0.0``).

    :param psu_id: Integer ID from the configured equipment.psu row. Select an existing ID in
        that section.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.
    :param key: Evidence key for this operation. Keep distinct keys for separate facts; see the
        evidence lookup rules in the core guide.

    :returns: Recorded state (1.0 enabled, 0.0 disabled).

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _ = key
    return 1.0 if _inst(psu_id).get_ocp_enabled(channel=channel) else 0.0


@measurement
def get_regulation_mode(*, psu_id: int, channel: int = 1, key: str) -> str:
    """Read CV/CC/UR regulation mode (best-effort SCPI).

    :param psu_id: Integer ID from the configured equipment.psu row. Select an existing ID in
        that section.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.
    :param key: Evidence key for this operation. Keep distinct keys for separate facts; see the
        evidence lookup rules in the core guide.

    :returns: Regulation state text, typically cv, cc, ur, or unknown; vendor replies can differ.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _ = key
    return str(_inst(psu_id).get_regulation_mode(channel=channel))


@measurement
def get_fault_status(*, psu_id: int, channel: int = 1, key: str) -> str:
    """Read instrument fault / questionable status register.

    :param psu_id: Integer ID from the configured equipment.psu row. Select an existing ID in
        that section.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.
    :param key: Evidence key for this operation. Keep distinct keys for separate facts; see the
        evidence lookup rules in the core guide.

    :returns: Raw fault/status register response; interpretation depends on the supply.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _ = key
    return str(_inst(psu_id).get_fault_status(channel=channel))


@measurement
def measure_voltage(*, psu_id: int, channel: int = 1, key: str) -> float:
    """Read output voltage.

    :param psu_id: Configured ``equipment.psu`` id from bench TOML.
    :type psu_id: int
    :param channel: Output channel (1-based).
    :type channel: int, optional
    :param key: Unique measurement key within domain ``equipment`` and this command name.
        Must not collide with another instrument's measurement using the same command name.
    :type key: str

    :returns: Measured voltage in volts.
    :rtype: float

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    _ = key
    return float(_inst(psu_id).measure_voltage(channel=channel))


verify_voltage = tolerance_verifier("measure_voltage", name="verify_voltage", unit="V")


@measurement
def measure_current(*, psu_id: int, channel: int = 1, key: str) -> float:
    """Read output current.

    :param psu_id: Configured ``equipment.psu`` id from bench TOML.
    :type psu_id: int
    :param channel: Output channel (1-based).
    :type channel: int, optional
    :param key: Unique measurement key within domain ``equipment`` and this command name.
        Must not collide with another instrument's measurement using the same command name.
    :type key: str

    :returns: Measured current in amperes.
    :rtype: float

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    _ = key
    return float(_inst(psu_id).measure_current(channel=channel))


verify_current = tolerance_verifier("measure_current", name="verify_current", unit="A")


@measurement
def measure_power_w(*, psu_id: int, channel: int = 1, key: str) -> float:
    """Read output power in watts.

    :param psu_id: Integer ID from the configured equipment.psu row. Select an existing ID in
        that section.
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
    return float(_inst(psu_id).measure_power_w(channel=channel))


verify_power_w = tolerance_verifier("measure_power_w", name="verify_power_w", unit="W")


@measurement
def measure_output_state(*, psu_id: int, channel: int = 1, key: str) -> float:
    """Read whether output is enabled.

    :param psu_id: Configured ``equipment.psu`` id from bench TOML.
    :type psu_id: int
    :param channel: Output channel (1-based).
    :type channel: int, optional
    :param key: Unique measurement key within domain ``equipment`` and this command name.
        Must not collide with another instrument's measurement using the same command name.
    :type key: str

    :returns: Measured state as ``1.0`` (on) or ``0.0`` (off).
    :rtype: float

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    _ = key
    enabled = _inst(psu_id).measure_output_state(channel=channel)
    return 1.0 if enabled else 0.0


verify_output_state = tolerance_verifier(
    "measure_output_state",
    name="verify_output_state",
    default_tolerance=0.0,
)
