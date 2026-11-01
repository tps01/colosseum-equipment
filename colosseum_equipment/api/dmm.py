"""Digital multimeter APIs (``col.equipment.dmm``).

One-shot measurements (``measure_voltage``, ``measure_voltage_dc``, etc.) configure
the function then issue ``READ?``. Use ``set_function`` → ``initiate`` → ``fetch``
when you need a fixed configuration across multiple samples.
"""

from __future__ import annotations

from typing import Any

from colosseum.decorators import command, measurement

from colosseum_equipment.api._broadcast import EquipmentId, broadcastable, require_int_id
from colosseum_equipment.api._verify import tolerance_verifier
from colosseum_equipment.connections import get_cached_instrument


def _inst(dmm_id: EquipmentId) -> Any:
    return get_cached_instrument('dmm', require_int_id(dmm_id, kind='dmm'))


@command
@broadcastable("dmm", "dmm_id")
def set_function(*, dmm_id: EquipmentId, function: str, channel: int = 1) -> None:
    """Set measurement function (e.g. ``VOLT:DC``, ``CURR:AC``, ``RES``).

    :param dmm_id: Integer ID from the configured equipment.dmm row. Select an existing ID in
        that section.
    :param function: Measurement function token, such as VOLT:DC, CURR:AC, or RES. Supported
        functions depend on the meter.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _inst(dmm_id).set_function(function, channel=channel)


@command
@broadcastable("dmm", "dmm_id")
def set_range(*, dmm_id: EquipmentId, value: float, channel: int = 1) -> None:
    """Set manual measurement range for the active function.

    :param dmm_id: Integer ID from the configured equipment.dmm row. Select an existing ID in
        that section.
    :param value: Manual range in the active measurement function's units (volts, amperes, ohms,
        or hertz).
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _inst(dmm_id).set_range(value, channel=channel)


@command
@broadcastable("dmm", "dmm_id")
def set_auto_range(*, dmm_id: EquipmentId, enabled: bool, channel: int = 1) -> None:
    """Enable or disable autorange.

    :param dmm_id: Integer ID from the configured equipment.dmm row. Select an existing ID in
        that section.
    :param enabled: True to enable the named feature; false to disable it.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _inst(dmm_id).set_auto_range(enabled, channel=channel)


@command
@broadcastable("dmm", "dmm_id")
def set_nplc(*, dmm_id: EquipmentId, nplc: float, channel: int = 1) -> None:
    """Set integration time in power-line cycles (NPLC).

    :param dmm_id: Integer ID from the configured equipment.dmm row. Select an existing ID in
        that section.
    :param nplc: Integration interval in power-line cycles. Supported values depend on the meter
        and active function.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _inst(dmm_id).set_nplc(nplc, channel=channel)


@command
@broadcastable("dmm", "dmm_id")
def set_aperture_s(*, dmm_id: EquipmentId, seconds: float, channel: int = 1) -> None:
    """Set aperture time in seconds (when supported).

    :param dmm_id: Integer ID from the configured equipment.dmm row. Select an existing ID in
        that section.
    :param seconds: Time in seconds. The configured model determines the accepted range.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _inst(dmm_id).set_aperture_s(seconds, channel=channel)


@command
@broadcastable("dmm", "dmm_id")
def set_auto_zero(*, dmm_id: EquipmentId, enabled: bool, channel: int = 1) -> None:
    """Enable or disable auto-zero.

    :param dmm_id: Integer ID from the configured equipment.dmm row. Select an existing ID in
        that section.
    :param enabled: True to enable the named feature; false to disable it.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _inst(dmm_id).set_auto_zero(enabled, channel=channel)


@command
@broadcastable("dmm", "dmm_id")
def set_input_z(*, dmm_id: EquipmentId, ohms: float, channel: int = 1) -> None:
    """Set input impedance in ohms.

    :param dmm_id: Integer ID from the configured equipment.dmm row. Select an existing ID in
        that section.
    :param ohms: Impedance in ohms. The configured model determines the accepted values.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _inst(dmm_id).set_input_z(ohms, channel=channel)


@command
@broadcastable("dmm", "dmm_id")
def set_trigger_source(*, dmm_id: EquipmentId, source: str, channel: int = 1) -> None:
    """Set trigger source (e.g. ``IMM``, ``EXT``, ``BUS``).

    :param dmm_id: Integer ID from the configured equipment.dmm row. Select an existing ID in
        that section.
    :param source: DMM trigger token, such as IMM, EXT, or BUS; support depends on the meter.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _inst(dmm_id).set_trigger_source(source, channel=channel)


@command
@broadcastable("dmm", "dmm_id")
def initiate(*, dmm_id: EquipmentId, channel: int = 1) -> None:
    """Arm a measurement (``INIT``); read with :func:`fetch`.

    :param dmm_id: Integer ID from the configured equipment.dmm row. Select an existing ID in
        that section.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.

    :returns: None; the command outcome is recorded.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _inst(dmm_id).initiate(channel=channel)


@measurement
def get_function(*, dmm_id: int, channel: int = 1, key: str) -> str:
    """Read active measurement function.

    :param dmm_id: Integer ID from the configured equipment.dmm row. Select an existing ID in
        that section.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.
    :param key: Evidence key for this operation. Keep distinct keys for separate facts; see the
        evidence lookup rules in the core guide.

    :returns: Active measurement function token as reported by the meter.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _ = key
    return str(_inst(dmm_id).get_function(channel=channel))


@measurement
def get_range(*, dmm_id: int, channel: int = 1, key: str) -> float:
    """Read manual range setting.

    :param dmm_id: Integer ID from the configured equipment.dmm row. Select an existing ID in
        that section.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.
    :param key: Evidence key for this operation. Keep distinct keys for separate facts; see the
        evidence lookup rules in the core guide.

    :returns: Recorded range in the active function units.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _ = key
    return float(_inst(dmm_id).get_range(channel=channel))


@measurement
def get_auto_range(*, dmm_id: int, channel: int = 1, key: str) -> float:
    """Read autorange state (``1.0`` / ``0.0``).

    :param dmm_id: Integer ID from the configured equipment.dmm row. Select an existing ID in
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
    return 1.0 if _inst(dmm_id).get_auto_range(channel=channel) else 0.0


@measurement
def get_nplc(*, dmm_id: int, channel: int = 1, key: str) -> float:
    """Read NPLC setting.

    :param dmm_id: Integer ID from the configured equipment.dmm row. Select an existing ID in
        that section.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.
    :param key: Evidence key for this operation. Keep distinct keys for separate facts; see the
        evidence lookup rules in the core guide.

    :returns: Recorded nplc in power-line cycles.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _ = key
    return float(_inst(dmm_id).get_nplc(channel=channel))


@measurement
def get_aperture_s(*, dmm_id: int, channel: int = 1, key: str) -> float:
    """Read aperture time in seconds.

    :param dmm_id: Integer ID from the configured equipment.dmm row. Select an existing ID in
        that section.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.
    :param key: Evidence key for this operation. Keep distinct keys for separate facts; see the
        evidence lookup rules in the core guide.

    :returns: Recorded aperture s in seconds.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _ = key
    return float(_inst(dmm_id).get_aperture_s(channel=channel))


@measurement
def get_auto_zero(*, dmm_id: int, channel: int = 1, key: str) -> float:
    """Read auto-zero state (``1.0`` / ``0.0``).

    :param dmm_id: Integer ID from the configured equipment.dmm row. Select an existing ID in
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
    return 1.0 if _inst(dmm_id).get_auto_zero(channel=channel) else 0.0


@measurement
def get_input_z(*, dmm_id: int, channel: int = 1, key: str) -> float:
    """Read input impedance in ohms.

    :param dmm_id: Integer ID from the configured equipment.dmm row. Select an existing ID in
        that section.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.
    :param key: Evidence key for this operation. Keep distinct keys for separate facts; see the
        evidence lookup rules in the core guide.

    :returns: Recorded input z in ohms.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _ = key
    return float(_inst(dmm_id).get_input_z(channel=channel))


@measurement
def get_trigger_source(*, dmm_id: int, channel: int = 1, key: str) -> str:
    """Read trigger source.

    :param dmm_id: Integer ID from the configured equipment.dmm row. Select an existing ID in
        that section.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.
    :param key: Evidence key for this operation. Keep distinct keys for separate facts; see the
        evidence lookup rules in the core guide.

    :returns: Trigger-source token as reported by the meter.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _ = key
    return str(_inst(dmm_id).get_trigger_source(channel=channel))


@measurement
def fetch(*, dmm_id: int, channel: int = 1, key: str) -> float:
    """Fetch result after :func:`initiate`.

    :param dmm_id: Integer ID from the configured equipment.dmm row. Select an existing ID in
        that section.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.
    :param key: Evidence key for this operation. Keep distinct keys for separate facts; see the
        evidence lookup rules in the core guide.

    :returns: Recorded scalar in the active function units (V, A, ohms, or Hz); fetch does not
        configure a new function.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _ = key
    return float(_inst(dmm_id).fetch(channel=channel))


verify_fetch = tolerance_verifier("fetch", name="verify_fetch")


def measure_voltage(*, dmm_id: int, channel: int = 1, key: str) -> float:
    """Measure DC voltage (alias for :func:`measure_voltage_dc`).

    Records evidence under command ``measure_voltage_dc``. Pair with
    :data:`verify_voltage` or :data:`verify_voltage_dc` using the same ``key``.

    :param dmm_id: Integer ID from the configured equipment.dmm row. Select an existing ID in
        that section.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.
    :param key: Evidence key for this operation. Keep distinct keys for separate facts; see the
        evidence lookup rules in the core guide.

    :returns: Recorded voltage in volts.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.


    Pair with verify_voltage using the same key. Configure equipment.dmm first;
    see the PSU/DMM acquisition recipe in the instrument workflow guide.
    """
    return measure_voltage_dc(dmm_id=dmm_id, channel=channel, key=key)


verify_voltage = tolerance_verifier("measure_voltage_dc", name="verify_voltage", unit="V")


@measurement
def measure_voltage_dc(*, dmm_id: int, channel: int = 1, key: str) -> float:
    """One-shot DC voltage (``CONF:VOLT:DC`` then ``READ?``).

    :param dmm_id: Integer ID from the configured equipment.dmm row. Select an existing ID in
        that section.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.
    :param key: Evidence key for this operation. Keep distinct keys for separate facts; see the
        evidence lookup rules in the core guide.

    :returns: Recorded DC voltage in volts.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _ = key
    return float(_inst(dmm_id).measure_voltage_dc(channel))


verify_voltage_dc = tolerance_verifier("measure_voltage_dc", name="verify_voltage_dc", unit="V")


@measurement
def measure_voltage_ac(*, dmm_id: int, channel: int = 1, key: str) -> float:
    """One-shot AC voltage.

    :param dmm_id: Integer ID from the configured equipment.dmm row. Select an existing ID in
        that section.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.
    :param key: Evidence key for this operation. Keep distinct keys for separate facts; see the
        evidence lookup rules in the core guide.

    :returns: Recorded AC voltage in volts.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _ = key
    return float(_inst(dmm_id).measure_voltage_ac(channel))


verify_voltage_ac = tolerance_verifier("measure_voltage_ac", name="verify_voltage_ac", unit="V")


def measure_current(*, dmm_id: int, channel: int = 1, key: str) -> float:
    """Measure DC current (alias for :func:`measure_current_dc`).

    Records evidence under command ``measure_current_dc``. Pair with
    :data:`verify_current` or :data:`verify_current_dc` using the same ``key``.

    :param dmm_id: Integer ID from the configured equipment.dmm row. Select an existing ID in
        that section.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.
    :param key: Evidence key for this operation. Keep distinct keys for separate facts; see the
        evidence lookup rules in the core guide.

    :returns: Recorded current in amperes.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    return measure_current_dc(dmm_id=dmm_id, channel=channel, key=key)


verify_current = tolerance_verifier("measure_current_dc", name="verify_current", unit="A")


@measurement
def measure_current_dc(*, dmm_id: int, channel: int = 1, key: str) -> float:
    """One-shot DC current.

    :param dmm_id: Integer ID from the configured equipment.dmm row. Select an existing ID in
        that section.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.
    :param key: Evidence key for this operation. Keep distinct keys for separate facts; see the
        evidence lookup rules in the core guide.

    :returns: Recorded DC current in amperes.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _ = key
    return float(_inst(dmm_id).measure_current_dc(channel))


verify_current_dc = tolerance_verifier("measure_current_dc", name="verify_current_dc", unit="A")


@measurement
def measure_current_ac(*, dmm_id: int, channel: int = 1, key: str) -> float:
    """One-shot AC current.

    :param dmm_id: Integer ID from the configured equipment.dmm row. Select an existing ID in
        that section.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.
    :param key: Evidence key for this operation. Keep distinct keys for separate facts; see the
        evidence lookup rules in the core guide.

    :returns: Recorded AC current in amperes.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _ = key
    return float(_inst(dmm_id).measure_current_ac(channel))


verify_current_ac = tolerance_verifier("measure_current_ac", name="verify_current_ac", unit="A")


@measurement
def measure_resistance(*, dmm_id: int, channel: int = 1, key: str) -> float:
    """Measure 2-wire resistance.

    :param dmm_id: Integer ID from the configured equipment.dmm row. Select an existing ID in
        that section.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.
    :param key: Evidence key for this operation. Keep distinct keys for separate facts; see the
        evidence lookup rules in the core guide.

    :returns: Recorded resistance in ohms.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _ = key
    return float(_inst(dmm_id).measure_resistance(channel))


verify_resistance = tolerance_verifier("measure_resistance", name="verify_resistance", unit="ohm")


@measurement
def measure_resistance_4w(*, dmm_id: int, channel: int = 1, key: str) -> float:
    """Measure 4-wire resistance.

    :param dmm_id: Integer ID from the configured equipment.dmm row. Select an existing ID in
        that section.
    :param channel: Physical channel, numbered from 1. Defaults to 1; valid channels depend on
        the configured model and fitted modules.
    :param key: Evidence key for this operation. Keep distinct keys for separate facts; see the
        evidence lookup rules in the core guide.

    :returns: Recorded resistance 4w in ohms.

    :raises EquipmentCapabilityError: The configured model does not implement this operation or
        channel.
    :raises EquipmentConnectionError: The instrument transport could not complete the operation.
    """
    _ = key
    return float(_inst(dmm_id).measure_resistance_4w(channel))


verify_resistance_4w = tolerance_verifier(
    "measure_resistance_4w",
    name="verify_resistance_4w",
    unit="ohm",
)


@measurement
def measure_frequency_hz(*, dmm_id: int, channel: int = 1, key: str) -> float:
    """Measure frequency in hertz.

    :param dmm_id: Integer ID from the configured equipment.dmm row. Select an existing ID in
        that section.
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
    return float(_inst(dmm_id).measure_frequency_hz(channel))


verify_frequency_hz = tolerance_verifier(
    "measure_frequency_hz",
    name="verify_frequency_hz",
    unit="Hz",
)
