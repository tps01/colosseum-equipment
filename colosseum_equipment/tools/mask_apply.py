"""Push mask setup metadata to SpecA / oscilloscope instruments."""

from __future__ import annotations

from typing import Any

from colosseum.logging import get_logger

from colosseum_equipment.connections import get_cached_instrument
from colosseum_equipment.tools.mask_schema import load_mask
from colosseum_equipment.tools.mask_verify import resolve_mask_path

_logger = get_logger("colosseum.equipment")

_SPECA_SETUP = {
    "center_hz": ("set_center_frequency", float),
    "span_hz": ("set_span", float),
    "ref_level_dbm": ("set_reference_level", float),
    "rbw_hz": ("set_rbw", float),
    "vbw_hz": ("set_vbw", float),
}


def apply_speca_mask_setup(path: str, *, speca_id: int) -> dict[str, Any]:
    """Apply frequency-domain ``setup`` fields from a mask file to a SpecA."""
    mask = load_mask(resolve_mask_path(path))
    setup = dict(mask.get("setup") or {})
    inst = get_cached_instrument("speca", int(speca_id))
    ignored: list[str] = []
    for key, (method_name, caster) in _SPECA_SETUP.items():
        if key not in setup:
            continue
        method = getattr(inst, method_name, None)
        if not callable(method):
            ignored.append(key)
            continue
        method(caster(setup[key]))
    for key in setup:
        if key not in _SPECA_SETUP:
            ignored.append(key)
    if ignored:
        _logger.warning(
            "mask setup ignored unsupported keys for speca: %s",
            ", ".join(sorted(set(ignored))),
        )
    return setup


def apply_oscope_mask_setup(
    path: str,
    *,
    oscope_id: int,
    channel: int = 1,
) -> dict[str, Any]:
    """Apply time-domain ``setup`` fields from a mask file to an oscilloscope."""
    mask = load_mask(resolve_mask_path(path))
    setup = dict(mask.get("setup") or {})
    inst = get_cached_instrument("oscope", int(oscope_id))
    ignored: list[str] = []
    if "timebase_s" in setup and callable(getattr(inst, "set_timebase_scale", None)):
        inst.set_timebase_scale(float(setup["timebase_s"]))
    elif "timebase_s" in setup:
        ignored.append("timebase_s")
    if "scale_v" in setup and callable(getattr(inst, "set_channel_scale_v", None)):
        inst.set_channel_scale_v(channel, float(setup["scale_v"]))
    elif "scale_v" in setup:
        ignored.append("scale_v")
    if "offset_v" in setup and callable(getattr(inst, "set_channel_offset_v", None)):
        inst.set_channel_offset_v(channel, float(setup["offset_v"]))
    elif "offset_v" in setup:
        ignored.append("offset_v")
    for key in setup:
        if key not in {"timebase_s", "scale_v", "offset_v"}:
            ignored.append(key)
    if ignored:
        _logger.warning(
            "mask setup ignored unsupported keys for oscope: %s",
            ", ".join(sorted(set(ignored))),
        )
    return setup
