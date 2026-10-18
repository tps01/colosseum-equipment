"""RF power meter APIs (``col.equipment.pwrmeter``)."""

from __future__ import annotations

from colosseum.decorators import command, measurement

from colosseum_equipment.api._verify import tolerance_verifier
from colosseum_equipment.connections import get_cached_instrument


def _inst(pwrmeter_id: int):
    return get_cached_instrument("pwrmeter", pwrmeter_id)


@command
def set_frequency(*, pwrmeter_id: int, frequency_hz: float, channel: int = 1) -> None:
    """Set the calibration frequency.

    :param pwrmeter_id: Configured ``equipment.pwrmeter`` id from bench TOML.
    :type pwrmeter_id: int
    :param frequency_hz: Frequency in hertz.
    :type frequency_hz: float
    :param channel: Sensor channel index (1-based).
    :type channel: int

    :returns: None

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    _inst(pwrmeter_id).set_frequency(frequency_hz, channel=channel)


@command
def set_averaging_count(*, pwrmeter_id: int, count: int, channel: int = 1) -> None:
    """Set the measurement averaging count.

    :param pwrmeter_id: Configured ``equipment.pwrmeter`` id from bench TOML.
    :type pwrmeter_id: int
    :param count: Number of averages.
    :type count: int
    :param channel: Sensor channel index (1-based).
    :type channel: int

    :returns: None

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    _inst(pwrmeter_id).set_averaging_count(count, channel=channel)


@command
def set_offset_db(*, pwrmeter_id: int, offset_db: float, channel: int = 1) -> None:
    """Set power offset correction in dB.

    :param pwrmeter_id: Configured ``equipment.pwrmeter`` id from bench TOML.
    :type pwrmeter_id: int
    :param offset_db: Offset in dB.
    :type offset_db: float
    :param channel: Sensor channel index (1-based).
    :type channel: int

    :returns: None

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    _inst(pwrmeter_id).set_offset_db(offset_db, channel=channel)


@command
def zero_sensor(*, pwrmeter_id: int, channel: int = 1) -> None:
    """Zero the sensor.

    :param pwrmeter_id: Configured ``equipment.pwrmeter`` id from bench TOML.
    :type pwrmeter_id: int
    :param channel: Sensor channel index (1-based).
    :type channel: int

    :returns: None

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    _inst(pwrmeter_id).zero_sensor(channel=channel)


@command
def calibrate(*, pwrmeter_id: int, channel: int = 1) -> None:
    """Run sensor calibration.

    :param pwrmeter_id: Configured ``equipment.pwrmeter`` id from bench TOML.
    :type pwrmeter_id: int
    :param channel: Sensor channel index (1-based).
    :type channel: int

    :returns: None

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    _inst(pwrmeter_id).calibrate(channel=channel)


@command
def preset(*, pwrmeter_id: int) -> None:
    """Return the instrument to a default preset.

    :param pwrmeter_id: Configured ``equipment.pwrmeter`` id from bench TOML.
    :type pwrmeter_id: int

    :returns: None

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    _inst(pwrmeter_id).preset()


@measurement
def measure_power_dbm(*, pwrmeter_id: int, channel: int = 1, key: str) -> float:
    """Measure RF power in dBm.

    :param pwrmeter_id: Configured ``equipment.pwrmeter`` id from bench TOML.
    :type pwrmeter_id: int
    :param channel: Sensor channel index (1-based).
    :type channel: int
    :param key: Unique measurement key within domain ``equipment`` and this command name.
        Must not collide with another instrument's measurement using the same command name.
    :type key: str

    :returns: Measured power in dBm.
    :rtype: float

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    _ = key
    return float(_inst(pwrmeter_id).measure_power_dbm(channel=channel))


verify_power_dbm = tolerance_verifier(
    "measure_power_dbm",
    name="verify_power_dbm",
    default_tolerance=0.5,
    unit="dBm",
)


@measurement
def measure_power(*, pwrmeter_id: int, channel: int = 1, key: str) -> float:
    """Measure RF power in dBm (alias of :func:`measure_power_dbm`).

    :param pwrmeter_id: Configured ``equipment.pwrmeter`` id from bench TOML.
    :type pwrmeter_id: int
    :param channel: Sensor channel index (1-based).
    :type channel: int
    :param key: Unique measurement key within domain ``equipment`` and this command name.
        Must not collide with another instrument's measurement using the same command name.
    :type key: str

    :returns: Measured power in dBm.
    :rtype: float

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    _ = key
    return float(_inst(pwrmeter_id).measure_power(channel=channel))


verify_power = tolerance_verifier(
    "measure_power", name="verify_power", default_tolerance=0.5, unit="dBm",
)


@measurement
def measure_power_w(*, pwrmeter_id: int, channel: int = 1, key: str) -> float:
    """Measure RF power in watts.

    :param pwrmeter_id: Configured ``equipment.pwrmeter`` id from bench TOML.
    :type pwrmeter_id: int
    :param channel: Sensor channel index (1-based).
    :type channel: int
    :param key: Unique measurement key within domain ``equipment`` and this command name.
    :type key: str

    :returns: Measured power in watts.
    :rtype: float

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    _ = key
    return float(_inst(pwrmeter_id).measure_power_w(channel=channel))


@measurement
def measure_power_peak_dbm(*, pwrmeter_id: int, channel: int = 1, key: str) -> float:
    """Measure peak RF power in dBm.

    :param pwrmeter_id: Configured ``equipment.pwrmeter`` id from bench TOML.
    :type pwrmeter_id: int
    :param channel: Sensor channel index (1-based).
    :type channel: int
    :param key: Unique measurement key within domain ``equipment`` and this command name.
    :type key: str

    :returns: Peak power in dBm.
    :rtype: float

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    _ = key
    return float(_inst(pwrmeter_id).measure_power_peak_dbm(channel=channel))


@measurement
def measure_power_avg_dbm(*, pwrmeter_id: int, channel: int = 1, key: str) -> float:
    """Measure averaged RF power in dBm.

    :param pwrmeter_id: Configured ``equipment.pwrmeter`` id from bench TOML.
    :type pwrmeter_id: int
    :param channel: Sensor channel index (1-based).
    :type channel: int
    :param key: Unique measurement key within domain ``equipment`` and this command name.
    :type key: str

    :returns: Averaged power in dBm.
    :rtype: float

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    _ = key
    return float(_inst(pwrmeter_id).measure_power_avg_dbm(channel=channel))
