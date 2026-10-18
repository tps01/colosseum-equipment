"""Named GPIO line resolution from bench config."""

from __future__ import annotations

from typing import Any

from colosseum_equipment.io.exceptions import IoConfigError


def resolve_pin_line(
    config: dict[str, Any],
    *,
    line: int | None,
    name: str | None,
) -> int:
    if name is not None:
        if line is not None:
            raise IoConfigError("specify line or name, not both")
        pins = config.get("pins") or config.get("pin_names")
        if not isinstance(pins, dict):
            raise IoConfigError("named pins require a `pins` map in io.dio config")
        if name not in pins:
            raise IoConfigError(f"unknown pin name {name!r}")
        return int(pins[name])
    if line is None:
        raise IoConfigError("line or name is required")
    return int(line)
