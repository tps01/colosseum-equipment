"""Relay controller APIs (``col.equipment.relay``)."""

from __future__ import annotations

from colosseum.decorators import command, measurement

from colosseum_equipment.connections import get_cached_instrument


@command
def set_relay(*, relay_id: int, channel: int, enabled: bool) -> None:
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
    get_cached_instrument("relay", relay_id).set_relay(channel, enabled)


@command
def pulse_relay(*, relay_id: int, channel: int, duration_s: float | None = None) -> None:
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
    get_cached_instrument("relay", relay_id).pulse_relay(channel, duration_s)


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
    return bool(get_cached_instrument("relay", relay_id).measure_relay(channel))
