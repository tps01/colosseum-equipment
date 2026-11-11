"""Relay controller APIs (``col.equipment.relay``).

Configured IDs select bench TOML rows. Core records command and measurement
outcomes and applies its standard optional-failure handling. Unsupported model
operations raise ``EquipmentCapabilityError``; transport failures raise
``EquipmentConnectionError``.
Operation-specific validation and acquisition constraints are described below.

Commands with an ``EquipmentId`` parameter also accept ``"all"``: targets run
sequentially and failures aggregate. Measurements require numeric IDs.
"""

from __future__ import annotations

from colosseum.decorators import command, measurement
from colosseum.logging import get_logger

from colosseum_equipment.api._broadcast import EquipmentId, broadcastable, require_int_id
from colosseum_equipment.connections import get_cached_instrument

_logger = get_logger("colosseum.equipment")


@command
@broadcastable("relay", "relay_id")
def set_relay(*, relay_id: EquipmentId, channel: int, enabled: bool) -> None:
    """Turn a relay channel on or off.

    :param relay_id: Configured ``equipment.relay`` ID.

    :param channel: Relay channel number (1-based for ControlByWeb).

    :param enabled: ``True`` to close/energize, ``False`` to open.
    """
    _logger.info(
        "%s channel %s on relay %s",
        "Enabling" if enabled else "Disabling",
        channel,
        relay_id,
    )
    get_cached_instrument("relay", require_int_id(relay_id, kind="relay")).set_relay(channel, enabled)


@command
@broadcastable("relay", "relay_id")
def set_all(*, relay_id: EquipmentId, bitmask: int) -> None:
    """Set all relay channels from a bitmask (bit 0 = channel 1).

    :param relay_id: Configured ``equipment.relay`` ID.

    :param bitmask: Relay states as a bitmask.
    """
    _logger.info("Setting relay %s channels to bitmask %s", relay_id, bitmask)
    get_cached_instrument("relay", require_int_id(relay_id, kind="relay")).set_all(bitmask)


@command
@broadcastable("relay", "relay_id")
def pulse_relay(*, relay_id: EquipmentId, channel: int, duration_s: float | None = None) -> None:
    """Pulse a relay channel.

    :param relay_id: Configured ``equipment.relay`` ID.

    :param channel: Relay channel number (1-based for ControlByWeb).

    :param duration_s: Optional pulse duration in seconds. When omitted, the
        device preset pulse length is used.
    """
    _logger.info("Pulsing relay %s channel %s", relay_id, channel)
    get_cached_instrument("relay", require_int_id(relay_id, kind="relay")).pulse_relay(channel, duration_s)


@command
@broadcastable("relay", "relay_id")
def set_pulse_width_s(*, relay_id: EquipmentId, channel: int, width_s: float) -> None:
    """Set the preset pulse width for a relay channel (ControlByWeb ``pulseTimeN``).

    :param relay_id: Configured ``equipment.relay`` ID.

    :param channel: Relay channel number (1-based for ControlByWeb).

    :param width_s: Pulse width in seconds.
    """
    _logger.info("Setting pulse width on relay %s channel %s to %s s", relay_id, channel, width_s)
    get_cached_instrument("relay", require_int_id(relay_id, kind="relay")).set_pulse_width_s(channel, width_s)


@measurement
def measure_relay(*, relay_id: int, channel: int, key: str) -> bool:
    """Read whether a relay channel is on.

    :param relay_id: Configured ``equipment.relay`` ID.

    :param channel: Relay channel number (1-based for ControlByWeb).

    :param key: Unique measurement key within domain ``equipment``.

    :returns: ``True`` if the relay is on.
    :rtype: bool
    """
    _logger.info("Reading relay %s channel %s", relay_id, channel)
    _ = key
    return bool(get_cached_instrument("relay", require_int_id(relay_id, kind="relay")).measure_relay(channel))


@measurement
def measure_all(*, relay_id: int, key: str) -> int:
    """Read all relay channels as a bitmask (bit 0 = channel 1).

    :param relay_id: Configured ``equipment.relay`` ID.

    :param key: Unique measurement key within domain ``equipment``.

    :returns: Relay states as a bitmask.
    :rtype: int
    """
    _logger.info("Reading all channels on relay %s", relay_id)
    _ = key
    return int(get_cached_instrument("relay", require_int_id(relay_id, kind="relay")).measure_all())
