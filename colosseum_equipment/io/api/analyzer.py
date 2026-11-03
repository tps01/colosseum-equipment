"""Passive protocol captures (``col.io.analyzer``)."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from colosseum.decorators import command

from colosseum_equipment._paths import resolve_artifact_path
from colosseum_equipment.evidence import record_artifact
from colosseum_equipment.io.connections import get_backend


def _export_failed(summary: dict[str, Any]) -> bool:
    if summary.get("loss_detected"):
        return True
    if int(summary.get("records") or 0) <= 0:
        return True
    reason = str(summary.get("stop_reason") or "")
    if reason in {"drain_timeout", "error", "byte_limit", "record_limit"}:
        return True
    return reason == "duration_limit" and int(summary.get("records") or 0) <= 0


@command
def configure(
    *, analyzer_id: int, protocol: str | None = None, mode: int | None = None,
    sample_rate_hz: int | None = None,
) -> dict[str, Any]:
    """Configure an idle analyzer. SPI modes use active-low CS and MSB first.

    :returns: Applied analyzer settings snapshot.
    """
    return dict(
        get_backend("analyzer", analyzer_id).configure(
            protocol=protocol, mode=mode, sample_rate_hz=sample_rate_hz,
        ),
    )


@command
def start(*, analyzer_id: int, path: str | None = None) -> str:
    """Enable capture before returning, then stream packets to JSON Lines.

    :param path: New capture file relative to run output. Defaults to a unique name.
    :returns: Relative capture path used for this session.
    """
    relative = path or f"captures/analyzer_{analyzer_id}_{uuid4().hex}.jsonl"
    get_backend("analyzer", analyzer_id).start(
        resolve_artifact_path(relative),
        relative_path=relative,
    )
    return relative


@command
def stop(*, analyzer_id: int, timeout_s: float = 2.0) -> dict[str, Any]:
    """Drain until idle or deadline and stop; raise on a capture/SDK failure.

    :returns: Summary including limits, detected loss, path, and stop-boundary uncertainty.
    """
    return dict(get_backend("analyzer", analyzer_id).stop(timeout_s))


@command
def export(*, analyzer_id: int, path: str, key: str) -> dict[str, Any]:
    """Export a stopped capture and record its summary and artifact in evidence.

    Failed / empty captures export as ``FAIL`` evidence. Inspect ``stop_reason``,
    ``records``, and ``loss_detected`` before accepting the result.

    Prefer calling ``export`` in an inner ``finally`` so a ``stop`` worker error
    still leaves the capture artifact in evidence.
    """
    artifact = resolve_artifact_path(path)
    summary = dict(get_backend("analyzer", analyzer_id).export(artifact))
    record_artifact(
        domain="equipment",
        command="io.analyzer.export",
        key=key,
        path=artifact,
        value=summary,
        status="FAIL" if _export_failed(summary) else "PASS",
    )
    return summary


def is_running(*, analyzer_id: int) -> bool:
    """Return whether a capture worker is currently running."""
    return bool(get_backend("analyzer", analyzer_id).is_running())


def status(*, analyzer_id: int) -> dict[str, Any]:
    """Return a mid-soak snapshot (running flag, records, stop_reason, path, …)."""
    return dict(get_backend("analyzer", analyzer_id).status())
