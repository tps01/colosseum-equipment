"""Resolve instrument channel-count config keys."""

from __future__ import annotations

from typing import Any


def resolve_channel_count(config: dict[str, Any], *, default: int = 1) -> int:
    """Return channel count from ``channels`` (preferred) or ``channel_count``.

    When both keys are present they must agree; otherwise raise ``ValueError``.
    """
    channels = config.get("channels")
    channel_count = config.get("channel_count")
    if channels is not None and channel_count is not None:
        left = int(channels)
        right = int(channel_count)
        if left != right:
            raise ValueError(
                f"channels ({left}) and channel_count ({right}) disagree; "
                "prefer channels and omit channel_count",
            )
        return left
    if channels is not None:
        return int(channels)
    if channel_count is not None:
        return int(channel_count)
    return int(default)
