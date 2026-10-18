"""Helpers to record equipment evidence into the run measurements DB."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from colosseum.context import get_context
from colosseum.database import MeasurementRow
from colosseum.database.artifact_paths import stored_artifact_path


def _runtime_db() -> Any | None:
    try:
        ctx = get_context()
    except RuntimeError:
        return None
    if not ctx.db.is_initialized():
        return None
    return ctx.db


def _output_dir() -> Path | None:
    try:
        ctx = get_context()
    except RuntimeError:
        return None
    output_dir = getattr(ctx, "output_dir", None)
    return output_dir if isinstance(output_dir, Path) else None


def _store_path(path: Path | str) -> str:
    return stored_artifact_path(path, _output_dir())


def enqueue_measurement(
    *,
    domain: str,
    command: str,
    key: str,
    value: Any,
    row_index: int = 0,
    units: str | None = None,
    artifact_path: str | None = None,
    status: str = "PASS",
    timestamp: str = "",
) -> None:
    """Enqueue a measurement row (safe from listener threads).

    Durability is the core write queue: ``drain`` / ``flush`` / database
    ``close`` (finalize does this). The row is visible to later verifiers only
    after that barrier. Identity is ``(domain, command, key, row_index)``.
    """
    db = _runtime_db()
    if db is None:
        return
    stored = _store_path(artifact_path) if artifact_path else None
    db.enqueue_measurement(
        MeasurementRow(
            domain=domain,
            command=command,
            key=key,
            row_index=row_index,
            value=value,
            units=units,
            artifact_path=stored,
            status=status,
            timestamp=timestamp,
        ),
    )


def record_artifact(
    *,
    domain: str,
    command: str,
    key: str,
    path: Path | str,
    value: Any = None,
    units: str | None = None,
) -> None:
    """Record a saved file as a measurement with ``artifact_path``.

    Uses a synchronous insert so a following ``verify_*`` on the script thread
    can see the row without racing the write queue.
    """
    db = _runtime_db()
    if db is None:
        return
    stored = _store_path(path)
    row = MeasurementRow(
        domain=domain,
        command=command,
        key=key,
        value=value if value is not None else {"path": stored},
        artifact_path=stored,
        units=units,
    )
    insert = getattr(db, "insert_measurement", None)
    if callable(insert):
        insert(row)
        return
    db.enqueue_measurement(row)
