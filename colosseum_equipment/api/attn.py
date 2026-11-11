"""Programmable attenuator APIs (``col.equipment.attn``).

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
from colosseum_equipment.api._verify import tolerance_verifier
from colosseum_equipment.connections import get_cached_instrument

_logger = get_logger("colosseum.equipment")


@command
@broadcastable("attn", "attn_id")
def set_attenuation_db(
    *,
    attn_id: EquipmentId,
    attenuation_db: float,
    channel: int | None = None,
    settle_s: float | None = None,
) -> None:
    """Set attenuation.

    :param attn_id: Configured ``equipment.attn`` ID.

    :param attenuation_db: Attenuation in dB.

    :param channel: Optional RF channel (overrides bench ``channel`` / ``path``).

    :param settle_s: Optional post-command wait in seconds (defaults to bench ``settle_s``).
    """
    _logger.info(
        "Setting attenuation on attenuator %s channel %s to %s dB",
        attn_id,
        channel,
        attenuation_db,
    )
    get_cached_instrument("attn", require_int_id(attn_id, kind="attn")).set_attenuation_db(
        attenuation_db,
        channel=channel,
        settle_s=settle_s,
    )


@command
def wait_settle(*, attn_id: int, settle_s: float | None = None) -> None:
    """Wait for the attenuator to finish settling after a step.

    :param attn_id: Configured ``equipment.attn`` ID.

    :param settle_s: Wait time in seconds (defaults to bench ``settle_s`` when set).
    """
    _logger.info("Waiting for attenuator %s to settle", attn_id)
    get_cached_instrument("attn", require_int_id(attn_id, kind="attn")).wait_settle(settle_s=settle_s)


@command
@broadcastable("attn", "attn_id")
def preset(*, attn_id: EquipmentId) -> None:
    """Return the instrument to a default preset.

    :param attn_id: Configured ``equipment.attn`` ID.
    """
    _logger.info("Presetting attenuator %s", attn_id)
    get_cached_instrument("attn", require_int_id(attn_id, kind="attn")).preset()


@measurement
def measure_attenuation_db(*, attn_id: int, key: str, channel: int | None = None) -> float:
    """Read programmed or measured attenuation.

    :param attn_id: Configured ``equipment.attn`` ID.

    :param key: Unique measurement key within domain ``equipment`` and this command name.
        Must not collide with another instrument's measurement using the same command name.

    :param channel: Optional RF channel (overrides bench ``channel`` / ``path``).

    :returns: Measured attenuation in dB.
    :rtype: float
    """
    _logger.info("Reading attenuation from attenuator %s channel %s", attn_id, channel)
    _ = key
    return float(
        get_cached_instrument("attn", require_int_id(attn_id, kind="attn")).measure_attenuation_db(channel=channel),
    )


verify_attenuation_db = tolerance_verifier(
    "measure_attenuation_db", module=__name__,
    name="verify_attenuation_db",
    unit="dB",
)


@measurement
def measure_min_attenuation_db(*, attn_id: int, key: str) -> float:
    """Read minimum attenuation (instrument query or bench metadata).

    :param attn_id: Configured ``equipment.attn`` ID.

    :param key: Unique measurement key within domain ``equipment``.

    :returns: Minimum attenuation in dB.
    :rtype: float
    """
    _logger.info("Reading minimum attenuation from attenuator %s", attn_id)
    _ = key
    return float(get_cached_instrument("attn", require_int_id(attn_id, kind="attn")).measure_min_attenuation_db())


@measurement
def measure_max_attenuation_db(*, attn_id: int, key: str) -> float:
    """Read maximum attenuation (instrument query or bench metadata).

    :param attn_id: Configured ``equipment.attn`` ID.

    :param key: Unique measurement key within domain ``equipment``.

    :returns: Maximum attenuation in dB.
    :rtype: float
    """
    _logger.info("Reading maximum attenuation from attenuator %s", attn_id)
    _ = key
    return float(get_cached_instrument("attn", require_int_id(attn_id, kind="attn")).measure_max_attenuation_db())


@measurement
def measure_step_db(*, attn_id: int, key: str) -> float:
    """Read attenuator step size in dB (instrument query or bench metadata).

    :param attn_id: Configured ``equipment.attn`` ID.

    :param key: Unique measurement key within domain ``equipment``.

    :returns: Step size in dB.
    :rtype: float
    """
    _logger.info("Reading attenuation step from attenuator %s", attn_id)
    _ = key
    return float(get_cached_instrument("attn", require_int_id(attn_id, kind="attn")).measure_step_db())
