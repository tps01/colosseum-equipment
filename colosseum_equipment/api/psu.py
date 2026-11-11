"""Bench power supply APIs (``col.equipment.psu``).

Configured IDs select ``equipment.psu`` rows. Commands decorated with
``@broadcastable`` also accept ``"all"``: targets run sequentially and failures
are aggregated. Measurements require a numeric ID and distinct evidence keys.
Unsupported model operations raise ``EquipmentCapabilityError``; connection
failures raise ``EquipmentConnectionError``. Core records outcomes and applies
its standard ``optional`` handling. Channel availability depends on the model.
"""

from __future__ import annotations

from typing import Any

from colosseum.decorators import command, measurement
from colosseum.logging import get_logger

from colosseum_equipment.api._broadcast import EquipmentId, broadcastable, require_int_id
from colosseum_equipment.api._verify import tolerance_verifier
from colosseum_equipment.connections import get_cached_instrument

_logger = get_logger("colosseum.equipment")


def _inst(psu_id: EquipmentId) -> Any:
    return get_cached_instrument("psu", require_int_id(psu_id, kind="psu"))


@command
@broadcastable("psu", "psu_id")
def set_voltage(*, psu_id: EquipmentId, voltage: float, channel: int = 1) -> None:
    """Set the programmed output voltage.

    :param psu_id: Configured ``equipment.psu`` ID.
    :param voltage: Target voltage in volts.
    :param channel: Output channel (1-based; default single-channel supply).
    """
    _logger.info("Setting voltage on PSU %s channel %s to %s V", psu_id, channel, voltage)
    _inst(psu_id).set_voltage(voltage, channel=channel)


@command
@broadcastable("psu", "psu_id")
def set_current_limit(*, psu_id: EquipmentId, current: float, channel: int = 1) -> None:
    """Set the current limit.

    :param psu_id: Configured ``equipment.psu`` ID.
    :param current: Current limit in amperes.
    :param channel: Output channel (1-based).
    """
    _logger.info("Setting current limit on PSU %s channel %s to %s A", psu_id, channel, current)
    _inst(psu_id).set_current_limit(current, channel=channel)


@command
@broadcastable("psu", "psu_id")
def set_output(*, psu_id: EquipmentId, enabled: bool, channel: int = 1) -> None:
    """Enable or disable the output.

    :param psu_id: Configured ``equipment.psu`` ID.
    :param enabled: ``True`` to enable output, ``False`` to disable.
    :param channel: Output channel (1-based).
    """
    _logger.info("%s output on PSU %s channel %s", "Enabling" if enabled else "Disabling", psu_id, channel)
    _inst(psu_id).set_output(enabled, channel=channel)


@command
@broadcastable("psu", "psu_id")
def set_ovp_v(*, psu_id: EquipmentId, voltage: float, channel: int = 1) -> None:
    """Set over-voltage protection level.

    :param psu_id: Configured ``equipment.psu`` ID.
    :param voltage: Voltage in volts. Valid settings and protection limits depend on the
        instrument model and output range.
    :param channel: Physical channel (1-based); availability depends on the model.
    """
    _logger.info("Setting OVP on PSU %s channel %s to %s V", psu_id, channel, voltage)
    _inst(psu_id).set_ovp_v(voltage, channel=channel)


@command
@broadcastable("psu", "psu_id")
def set_ocp_a(*, psu_id: EquipmentId, current: float, channel: int = 1) -> None:
    """Set over-current protection level.

    :param psu_id: Configured ``equipment.psu`` ID.
    :param current: Current in amperes. Valid settings and protection limits depend on the
        instrument model and range.
    :param channel: Physical channel (1-based); availability depends on the model.
    """
    _logger.info("Setting OCP on PSU %s channel %s to %s A", psu_id, channel, current)
    _inst(psu_id).set_ocp_a(current, channel=channel)


@command
@broadcastable("psu", "psu_id")
def toggle_ovp(*, psu_id: EquipmentId, enabled: bool, channel: int = 1) -> None:
    """Enable or disable over-voltage protection.

    :param psu_id: Configured ``equipment.psu`` ID.
    :param enabled: True to enable the named feature; false to disable it.
    :param channel: Physical channel (1-based); availability depends on the model.
    """
    _logger.info("%s OVP on PSU %s channel %s", "Enabling" if enabled else "Disabling", psu_id, channel)
    _inst(psu_id).toggle_ovp(enabled, channel=channel)


@command
@broadcastable("psu", "psu_id")
def toggle_ocp(*, psu_id: EquipmentId, enabled: bool, channel: int = 1) -> None:
    """Enable or disable over-current protection.

    :param psu_id: Configured ``equipment.psu`` ID.
    :param enabled: True to enable the named feature; false to disable it.
    :param channel: Physical channel (1-based); availability depends on the model.
    """
    _logger.info("%s OCP on PSU %s channel %s", "Enabling" if enabled else "Disabling", psu_id, channel)
    _inst(psu_id).toggle_ocp(enabled, channel=channel)


@command
@broadcastable("psu", "psu_id")
def clear_protection(*, psu_id: EquipmentId, channel: int = 1) -> None:
    """Clear latched protection / fault state.

    :param psu_id: Configured ``equipment.psu`` ID.
    :param channel: Physical channel (1-based); availability depends on the model.
    """
    _logger.info("Clearing protection on PSU %s channel %s", psu_id, channel)
    _inst(psu_id).clear_protection(channel=channel)


@command
@broadcastable("psu", "psu_id")
def set_remote_sense(*, psu_id: EquipmentId, enabled: bool, channel: int = 1) -> None:
    """Enable or disable remote (4-wire) sense.

    :param psu_id: Configured ``equipment.psu`` ID.
    :param enabled: True to enable the named feature; false to disable it.
    :param channel: Physical channel (1-based); availability depends on the model.
    """
    _logger.info("%s remote sense on PSU %s channel %s", "Enabling" if enabled else "Disabling", psu_id, channel)
    _inst(psu_id).set_remote_sense(enabled, channel=channel)


@command
@broadcastable("psu", "psu_id")
def set_slew_voltage(*, psu_id: EquipmentId, volts_per_s: float, channel: int = 1) -> None:
    """Set voltage slew rate (best-effort SCPI).

    :param psu_id: Configured ``equipment.psu`` ID.
    :param volts_per_s: Voltage slew rate in volts per second; availability and range depend on
        the model.
    :param channel: Physical channel (1-based); availability depends on the model.
    """
    _logger.info("Setting voltage slew on PSU %s channel %s to %s V/s", psu_id, channel, volts_per_s)
    _inst(psu_id).set_slew_voltage(volts_per_s, channel=channel)


@command
@broadcastable("psu", "psu_id")
def set_slew_current(*, psu_id: EquipmentId, amps_per_s: float, channel: int = 1) -> None:
    """Set current slew rate (best-effort SCPI).

    :param psu_id: Configured ``equipment.psu`` ID.
    :param amps_per_s: Current slew rate in amperes per second; availability and range depend on
        the model.
    :param channel: Physical channel (1-based); availability depends on the model.
    """
    _logger.info("Setting current slew on PSU %s channel %s to %s A/s", psu_id, channel, amps_per_s)
    _inst(psu_id).set_slew_current(amps_per_s, channel=channel)


@command
@broadcastable("psu", "psu_id")
def set_tracking_mode(*, psu_id: EquipmentId, mode: str, channel: int = 1) -> None:
    """Set series/parallel tracking mode (best-effort SCPI).

    :param psu_id: Configured ``equipment.psu`` ID.
    :param mode: Tracking token. Generic SCPI accepts ON, OFF, TRACK, or IND; vendor semantics
        and support depend on the supply.
    :param channel: Physical channel (1-based); availability depends on the model.
    """
    _logger.info("Setting tracking mode on PSU %s channel %s to %s", psu_id, channel, mode)
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

    :param psu_id: Configured ``equipment.psu`` ID.
    :param current: Target current in amperes.
    :param timeout_s: Maximum wait time in seconds.
    :param tolerance: Allowed absolute deviation in amperes.
    :param channel: Output channel (1-based).
    """
    _logger.info("Waiting for current on PSU %s channel %s to reach %s A", psu_id, channel, current)
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

    :param psu_id: Configured ``equipment.psu`` ID.
    :param voltage: Voltage in volts. Valid settings and protection limits depend on the
        instrument model and output range.
    :param timeout_s: Maximum wait in seconds. Expiration does not establish that the operation
        completed.
    :param tolerance: Maximum absolute difference from the target in the same units as that
        target. Default: ``0.01``.
    :param channel: Physical channel (1-based); availability depends on the model.
    """
    _logger.info("Waiting for voltage on PSU %s channel %s to reach %s V", psu_id, channel, voltage)
    _inst(psu_id).wait_for_voltage(
        voltage,
        timeout_s=timeout_s,
        tolerance=tolerance,
        channel=channel,
    )


@measurement
def get_voltage(*, psu_id: int, channel: int = 1, key: str) -> float:
    """Read programmed output voltage setpoint.

    :param psu_id: Configured ``equipment.psu`` ID.
    :param channel: Physical channel (1-based); availability depends on the model.
    :param key: Unique evidence key for this measurement.

    :returns: Recorded voltage in volts.
    """
    _logger.info("Reading voltage setpoint from PSU %s channel %s", psu_id, channel)
    _ = key
    return float(_inst(psu_id).get_voltage(channel=channel))


verify_get_voltage = tolerance_verifier("get_voltage", module=__name__, name="verify_get_voltage", unit="V")


@measurement
def get_current_limit(*, psu_id: int, channel: int = 1, key: str) -> float:
    """Read programmed current limit setpoint.

    :param psu_id: Configured ``equipment.psu`` ID.
    :param channel: Physical channel (1-based); availability depends on the model.
    :param key: Unique evidence key for this measurement.

    :returns: Recorded current limit in amperes.
    """
    _logger.info("Reading current limit from PSU %s channel %s", psu_id, channel)
    _ = key
    return float(_inst(psu_id).get_current_limit(channel=channel))


verify_get_current_limit = tolerance_verifier(
    "get_current_limit", module=__name__,
    name="verify_get_current_limit",
    unit="A",
)


@measurement
def get_output(*, psu_id: int, channel: int = 1, key: str) -> float:
    """Read programmed output enable state (``1.0`` on, ``0.0`` off).

    :param psu_id: Configured ``equipment.psu`` ID.
    :param channel: Physical channel (1-based); availability depends on the model.
    :param key: Unique evidence key for this measurement.

    :returns: Recorded state (1.0 enabled, 0.0 disabled).
    """
    _logger.info("Reading output state from PSU %s channel %s", psu_id, channel)
    _ = key
    enabled = _inst(psu_id).get_output(channel=channel)
    return 1.0 if enabled else 0.0


verify_get_output = tolerance_verifier(
    "get_output", module=__name__,
    name="verify_get_output",
    default_tolerance=0.0,
)


@measurement
def get_ovp_v(*, psu_id: int, channel: int = 1, key: str) -> float:
    """Read over-voltage protection level.

    :param psu_id: Configured ``equipment.psu`` ID.
    :param channel: Physical channel (1-based); availability depends on the model.
    :param key: Unique evidence key for this measurement.

    :returns: Recorded ovp v in volts.
    """
    _logger.info("Reading OVP from PSU %s channel %s", psu_id, channel)
    _ = key
    return float(_inst(psu_id).get_ovp_v(channel=channel))


@measurement
def get_ocp_a(*, psu_id: int, channel: int = 1, key: str) -> float:
    """Read over-current protection level.

    :param psu_id: Configured ``equipment.psu`` ID.
    :param channel: Physical channel (1-based); availability depends on the model.
    :param key: Unique evidence key for this measurement.

    :returns: Recorded ocp a in amperes.
    """
    _logger.info("Reading OCP from PSU %s channel %s", psu_id, channel)
    _ = key
    return float(_inst(psu_id).get_ocp_a(channel=channel))


@measurement
def get_ovp_enabled(*, psu_id: int, channel: int = 1, key: str) -> float:
    """Read whether OVP is enabled (``1.0`` / ``0.0``).

    :param psu_id: Configured ``equipment.psu`` ID.
    :param channel: Physical channel (1-based); availability depends on the model.
    :param key: Unique evidence key for this measurement.

    :returns: Recorded state (1.0 enabled, 0.0 disabled).
    """
    _logger.info("Reading OVP enable from PSU %s channel %s", psu_id, channel)
    _ = key
    return 1.0 if _inst(psu_id).get_ovp_enabled(channel=channel) else 0.0


@measurement
def get_ocp_enabled(*, psu_id: int, channel: int = 1, key: str) -> float:
    """Read whether OCP is enabled (``1.0`` / ``0.0``).

    :param psu_id: Configured ``equipment.psu`` ID.
    :param channel: Physical channel (1-based); availability depends on the model.
    :param key: Unique evidence key for this measurement.

    :returns: Recorded state (1.0 enabled, 0.0 disabled).
    """
    _logger.info("Reading OCP enable from PSU %s channel %s", psu_id, channel)
    _ = key
    return 1.0 if _inst(psu_id).get_ocp_enabled(channel=channel) else 0.0


@measurement
def get_regulation_mode(*, psu_id: int, channel: int = 1, key: str) -> str:
    """Read CV/CC/UR regulation mode (best-effort SCPI).

    :param psu_id: Configured ``equipment.psu`` ID.
    :param channel: Physical channel (1-based); availability depends on the model.
    :param key: Unique evidence key for this measurement.

    :returns: Regulation state text, typically cv, cc, ur, or unknown; vendor replies can differ.
    """
    _logger.info("Reading regulation mode from PSU %s channel %s", psu_id, channel)
    _ = key
    return str(_inst(psu_id).get_regulation_mode(channel=channel))


@measurement
def get_fault_status(*, psu_id: int, channel: int = 1, key: str) -> str:
    """Read instrument fault / questionable status register.

    :param psu_id: Configured ``equipment.psu`` ID.
    :param channel: Physical channel (1-based); availability depends on the model.
    :param key: Unique evidence key for this measurement.

    :returns: Raw fault/status register response; interpretation depends on the supply.
    """
    _logger.info("Reading fault status from PSU %s channel %s", psu_id, channel)
    _ = key
    return str(_inst(psu_id).get_fault_status(channel=channel))


@measurement
def measure_voltage(*, psu_id: int, channel: int = 1, key: str) -> float:
    """Read output voltage.

    :param psu_id: Configured ``equipment.psu`` ID.
    :param channel: Physical channel (1-based); availability depends on the model.
    :param key: Unique evidence key for this measurement.
    :returns: Measured voltage in volts.
    :rtype: float
    """
    _logger.info("Reading voltage from PSU %s channel %s", psu_id, channel)
    _ = key
    return float(_inst(psu_id).measure_voltage(channel=channel))


verify_voltage = tolerance_verifier("measure_voltage", module=__name__, name="verify_voltage", unit="V")


@measurement
def measure_current(*, psu_id: int, channel: int = 1, key: str) -> float:
    """Read output current.

    :param psu_id: Configured ``equipment.psu`` ID.
    :param channel: Physical channel (1-based); availability depends on the model.
    :param key: Unique evidence key for this measurement.
    :returns: Measured current in amperes.
    :rtype: float
    """
    _logger.info("Reading current from PSU %s channel %s", psu_id, channel)
    _ = key
    return float(_inst(psu_id).measure_current(channel=channel))


verify_current = tolerance_verifier("measure_current", module=__name__, name="verify_current", unit="A")


@measurement
def measure_power_w(*, psu_id: int, channel: int = 1, key: str) -> float:
    """Read output power in watts.

    :param psu_id: Configured ``equipment.psu`` ID.
    :param channel: Physical channel (1-based); availability depends on the model.
    :param key: Unique evidence key for this measurement.

    :returns: Recorded power w in watts.
    """
    _logger.info("Reading power from PSU %s channel %s", psu_id, channel)
    _ = key
    return float(_inst(psu_id).measure_power_w(channel=channel))


verify_power_w = tolerance_verifier("measure_power_w", module=__name__, name="verify_power_w", unit="W")


@measurement
def measure_output_state(*, psu_id: int, channel: int = 1, key: str) -> float:
    """Read whether output is enabled.

    :param psu_id: Configured ``equipment.psu`` ID.
    :param channel: Physical channel (1-based); availability depends on the model.
    :param key: Unique evidence key for this measurement.
    :returns: Measured state as ``1.0`` (on) or ``0.0`` (off).
    :rtype: float
    """
    _logger.info("Reading output state from PSU %s channel %s", psu_id, channel)
    _ = key
    enabled = _inst(psu_id).measure_output_state(channel=channel)
    return 1.0 if enabled else 0.0


verify_output_state = tolerance_verifier(
    "measure_output_state", module=__name__,
    name="verify_output_state",
    default_tolerance=0.0,
)
