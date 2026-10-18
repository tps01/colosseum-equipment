"""Programmable attenuator APIs (``col.equipment.attn``)."""

from __future__ import annotations

from colosseum.decorators import command, measurement

from colosseum_equipment.api._verify import tolerance_verifier
from colosseum_equipment.connections import get_cached_instrument


@command
def set_attenuation_db(
    *,
    attn_id: int,
    attenuation_db: float,
    channel: int | None = None,
    settle_s: float | None = None,
) -> None:
    """Set attenuation.

    :param attn_id: Configured ``equipment.attn`` id from bench TOML.
    :type attn_id: int
    :param attenuation_db: Attenuation in dB.
    :type attenuation_db: float
    :param channel: Optional RF channel (overrides bench ``channel`` / ``path``).
    :type channel: int | None, optional
    :param settle_s: Optional post-command wait in seconds (defaults to bench ``settle_s``).
    :type settle_s: float | None, optional

    :returns: None

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    get_cached_instrument("attn", attn_id).set_attenuation_db(
        attenuation_db,
        channel=channel,
        settle_s=settle_s,
    )


@command
def wait_settle(*, attn_id: int, settle_s: float | None = None) -> None:
    """Wait for the attenuator to finish settling after a step.

    :param attn_id: Configured ``equipment.attn`` id from bench TOML.
    :type attn_id: int
    :param settle_s: Wait time in seconds (defaults to bench ``settle_s`` when set).
    :type settle_s: float | None, optional

    :returns: None

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    get_cached_instrument("attn", attn_id).wait_settle(settle_s=settle_s)


@command
def preset(*, attn_id: int) -> None:
    """Return the instrument to a default preset.

    :param attn_id: Configured ``equipment.attn`` id from bench TOML.
    :type attn_id: int

    :returns: None

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    get_cached_instrument("attn", attn_id).preset()


@measurement
def measure_attenuation_db(*, attn_id: int, key: str, channel: int | None = None) -> float:
    """Read programmed or measured attenuation.

    :param attn_id: Configured ``equipment.attn`` id from bench TOML.
    :type attn_id: int
    :param key: Unique measurement key within domain ``equipment`` and this command name.
        Must not collide with another instrument's measurement using the same command name.
    :type key: str
    :param channel: Optional RF channel (overrides bench ``channel`` / ``path``).
    :type channel: int | None, optional

    :returns: Measured attenuation in dB.
    :rtype: float

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    _ = key
    return float(
        get_cached_instrument("attn", attn_id).measure_attenuation_db(channel=channel),
    )


verify_attenuation_db = tolerance_verifier(
    "measure_attenuation_db", name="verify_attenuation_db", unit="dB",
)


@measurement
def measure_min_attenuation_db(*, attn_id: int, key: str) -> float:
    """Read minimum attenuation (instrument query or bench metadata).

    :param attn_id: Configured ``equipment.attn`` id from bench TOML.
    :type attn_id: int
    :param key: Unique measurement key within domain ``equipment``.
    :type key: str

    :returns: Minimum attenuation in dB.
    :rtype: float

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    _ = key
    return float(get_cached_instrument("attn", attn_id).measure_min_attenuation_db())


@measurement
def measure_max_attenuation_db(*, attn_id: int, key: str) -> float:
    """Read maximum attenuation (instrument query or bench metadata).

    :param attn_id: Configured ``equipment.attn`` id from bench TOML.
    :type attn_id: int
    :param key: Unique measurement key within domain ``equipment``.
    :type key: str

    :returns: Maximum attenuation in dB.
    :rtype: float

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    _ = key
    return float(get_cached_instrument("attn", attn_id).measure_max_attenuation_db())


@measurement
def measure_step_db(*, attn_id: int, key: str) -> float:
    """Read attenuator step size in dB (instrument query or bench metadata).

    :param attn_id: Configured ``equipment.attn`` id from bench TOML.
    :type attn_id: int
    :param key: Unique measurement key within domain ``equipment``.
    :type key: str

    :returns: Step size in dB.
    :rtype: float

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    _ = key
    return float(get_cached_instrument("attn", attn_id).measure_step_db())
