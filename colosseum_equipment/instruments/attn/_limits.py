"""Attenuator limit metadata from bench config or instrument queries."""

from __future__ import annotations

from typing import Any

from colosseum_equipment.exceptions import EquipmentCapabilityError
from colosseum_equipment.protocols.scpi import SCPIHelper


def float_from_config_or_scpi(
    config: dict[str, Any],
    config_key: str,
    scpi: SCPIHelper,
    *queries: str,
    operation: str,
) -> float:
    if config_key in config and config[config_key] not in (None, ""):
        return float(config[config_key])
    last_error: Exception | None = None
    for query in queries:
        try:
            return scpi.query_float(query)
        except (EquipmentCapabilityError, ValueError, OSError, RuntimeError) as exc:
            last_error = exc
            continue
    detail = f" set `{config_key}` in bench TOML"
    if last_error is not None:
        detail = f"{detail} or fix SCPI queries ({last_error})"
    raise EquipmentCapabilityError(f"{operation} is not available;{detail}")
