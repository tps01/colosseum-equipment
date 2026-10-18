"""Shared settle/wait helpers for mechanical and RF routing devices."""

from __future__ import annotations

import time
from typing import Any


def resolve_settle_s(
    config: dict[str, Any],
    *,
    settle_s: float | None = None,
    config_keys: tuple[str, ...] = ("settle_s", "wait_settle_s"),
) -> float | None:
    """Return an explicit settle time, else the first configured default."""
    if settle_s is not None:
        return float(settle_s)
    for key in config_keys:
        if key in config and config[key] not in (None, ""):
            return float(config[key])
    return None


def wait_settle_s(config: dict[str, Any], *, settle_s: float | None = None) -> None:
    """Block for the resolved settle interval when one is defined."""
    delay = resolve_settle_s(config, settle_s=settle_s)
    if delay is not None and delay > 0:
        time.sleep(delay)
