"""RF switch matrix APIs (``col.equipment.rfswitch``)."""

from __future__ import annotations

from colosseum.decorators import command, measurement

from colosseum_equipment.api._broadcast import EquipmentId, broadcastable, require_int_id
from colosseum_equipment.connections import get_cached_instrument


@command
@broadcastable("rfswitch", "rfswitch_id")
def set_path(*, rfswitch_id: EquipmentId, path: str, wait_settle_s: float | None = None) -> None:
    """Set routing path (model-specific string, e.g. ``A=1;B=0`` or ``SETP=0011``).

    :param rfswitch_id: Configured ``equipment.rfswitch`` id from bench TOML.
    :type rfswitch_id: int
    :param path: Path command string for the configured model.
    :type path: str
    :param wait_settle_s: Optional post-command wait in seconds (defaults to bench ``settle_s``).
    :type wait_settle_s: float | None, optional

    :returns: None

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    get_cached_instrument('rfswitch', require_int_id(rfswitch_id, kind='rfswitch')).set_path(path, wait_settle_s=wait_settle_s)


@command
@broadcastable("rfswitch", "rfswitch_id")
def set_switch(
    *,
    rfswitch_id: EquipmentId,
    switch: str,
    state: int,
    wait_settle_s: float | None = None,
) -> None:
    """Set one switch letter (Mini-Circuits ``SETA=1`` style).

    :param rfswitch_id: Configured ``equipment.rfswitch`` id from bench TOML.
    :type rfswitch_id: int
    :param switch: Switch identifier (e.g. ``A``).
    :type switch: str
    :param state: ``1`` on, ``0`` off.
    :type state: int
    :param wait_settle_s: Optional post-command wait in seconds (defaults to bench ``settle_s``).
    :type wait_settle_s: float | None, optional

    :returns: None

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    get_cached_instrument('rfswitch', require_int_id(rfswitch_id, kind='rfswitch')).set_switch(
        switch,
        state,
        wait_settle_s=wait_settle_s,
    )


@command
def wait_settle(*, rfswitch_id: int, settle_s: float | None = None) -> None:
    """Wait for mechanical switches to finish settling.

    :param rfswitch_id: Configured ``equipment.rfswitch`` id from bench TOML.
    :type rfswitch_id: int
    :param settle_s: Wait time in seconds (defaults to bench ``settle_s`` when set).
    :type settle_s: float | None, optional

    :returns: None

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    get_cached_instrument('rfswitch', require_int_id(rfswitch_id, kind='rfswitch')).wait_settle(settle_s=settle_s)


@command
@broadcastable("rfswitch", "rfswitch_id")
def preset(*, rfswitch_id: EquipmentId) -> None:
    """Return the switch to a default preset.

    :param rfswitch_id: Configured ``equipment.rfswitch`` id from bench TOML.
    :type rfswitch_id: int

    :returns: None

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    get_cached_instrument('rfswitch', require_int_id(rfswitch_id, kind='rfswitch')).preset()


@measurement
def measure_path(*, rfswitch_id: int, key: str) -> str:
    """Read the active routing path string.

    :param rfswitch_id: Configured ``equipment.rfswitch`` id from bench TOML.
    :type rfswitch_id: int
    :param key: Unique measurement key within domain ``equipment`` and this command name.
        Must not collide with another instrument's measurement using the same command name.
    :type key: str

    :returns: Measured path string.
    :rtype: str

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    _ = key
    return str(get_cached_instrument('rfswitch', require_int_id(rfswitch_id, kind='rfswitch')).measure_path())
