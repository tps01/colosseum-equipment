"""Build a cached instrument from its registered model."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from colosseum_equipment.instruments.registry import build_registered

if TYPE_CHECKING:
    from colosseum_equipment.transports.base import Transport


def build_instrument(
    kind: str, equipment_id: int, config: dict[str, Any], transport: Transport,
) -> object:
    model = str(config.get("model", "generic")).lower()
    try:
        return build_registered(kind, model, transport, config)
    except RuntimeError as exc:
        if "Unsupported equipment model" in str(exc):
            raise RuntimeError(
                f"Unsupported equipment model `{model}` for {kind} id {equipment_id}",
            ) from exc
        raise
