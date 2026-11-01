"""Relay controller APIs (``col.equipment.relay``)."""

from __future__ import annotations

from colosseum.decorators import command, measurement

from colosseum_equipment.api._broadcast import EquipmentId, broadcastable, require_int_id
from colosseum_equipment.connections import get_cached_instrument


@command
@broadcastable("relay", "relay_id")
def set_relay(*, relay_id: EquipmentId, channel: int, enabled: bool) -> None:
    """Turn a relay channel on or off.

    :param relay_id: Configured ``equipment.relay`` id from config TOML.
    :type relay_id: int
    :param channel: Relay channel number (1-based for ControlByWeb).
    :type channel: int
    :param enabled: ``True`` to close/energize, ``False`` to open.
    :type enabled: bool

    :returns: None

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    get_cached_instrument('relay', require_int_id(relay_id, kind='relay')).set_relay(channel, enabled)


@command
@broadcastable("relay", "relay_id")
def set_all(*, relay_id: EquipmentId, bitmask: int) -> None:
    """Set all relay channels from a bitmask (bit 0 = channel 1).

    :param relay_id: Configured ``equipment.relay`` id from config TOML.
    :type relay_id: int
    :param bitmask: Relay states as a bitmask.
    :type bitmask: int

    :returns: None

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    get_cached_instrument('relay', require_int_id(relay_id, kind='relay')).set_all(bitmask)


@command
@broadcastable("relay", "relay_id")
def pulse_relay(*, relay_id: EquipmentId, channel: int, duration_s: float | None = None) -> None:
    """Pulse a relay channel.

    :param relay_id: Configured ``equipment.relay`` id from config TOML.
    :type relay_id: int
    :param channel: Relay channel number (1-based for ControlByWeb).
    :type channel: int
    :param duration_s: Optional pulse duration in seconds. When omitted, the
        device preset pulse length is used.
    :type duration_s: float | None

    :returns: None

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    get_cached_instrument('relay', require_int_id(relay_id, kind='relay')).pulse_relay(channel, duration_s)


@command
@broadcastable("relay", "relay_id")
def set_pulse_width_s(*, relay_id: EquipmentId, channel: int, width_s: float) -> None:
    """Set the preset pulse width for a relay channel (ControlByWeb ``pulseTimeN``).

    :param relay_id: Configured ``equipment.relay`` id from config TOML.
    :type relay_id: int
    :param channel: Relay channel number (1-based for ControlByWeb).
    :type channel: int
    :param width_s: Pulse width in seconds.
    :type width_s: float

    :returns: None

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    get_cached_instrument('relay', require_int_id(relay_id, kind='relay')).set_pulse_width_s(channel, width_s)


@measurement
def measure_relay(*, relay_id: int, channel: int, key: str) -> bool:
    """Read whether a relay channel is on.

    :param relay_id: Configured ``equipment.relay`` id from config TOML.
    :type relay_id: int
    :param channel: Relay channel number (1-based for ControlByWeb).
    :type channel: int
    :param key: Unique measurement key within domain ``equipment``.
    :type key: str

    :returns: ``True`` if the relay is on.
    :rtype: bool

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    _ = key
    return bool(get_cached_instrument('relay', require_int_id(relay_id, kind='relay')).measure_relay(channel))


@measurement
def measure_all(*, relay_id: int, key: str) -> int:
    """Read all relay channels as a bitmask (bit 0 = channel 1).

    :param relay_id: Configured ``equipment.relay`` id from config TOML.
    :type relay_id: int
    :param key: Unique measurement key within domain ``equipment``.
    :type key: str

    :returns: Relay states as a bitmask.
    :rtype: int

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    _ = key
    return int(get_cached_instrument('relay', require_int_id(relay_id, kind='relay')).measure_all())
