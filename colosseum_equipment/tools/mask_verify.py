"""Evaluate a saved trace CSV against a mask."""

from __future__ import annotations

import contextlib
import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from colosseum.context import get_context
from colosseum.decorators import VerificationResult, missing_measurement_result

from colosseum_equipment.tools.mask_schema import load_mask


@dataclass(frozen=True)
class MaskViolation:
    region_id: str
    kind: str
    x: float
    y: float
    limit: str


@dataclass(frozen=True)
class MaskEvalResult:
    ok: bool
    message: str
    violations: tuple[MaskViolation, ...] = ()


def read_trace_xy(path: Path) -> tuple[list[float], list[float], str]:
    """Return (x, y, domain) from SpecA or oscope CSV.

    Domain is ``frequency`` (``frequency_hz`` + ``amplitude_dbm``) or ``time``
    (``time_s`` + ``voltage_v``). Index-only SpecA exports are rejected for
    mask verification — absolute frequency is required.
    """
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"trace CSV has no header: {path}")
        fields = {name.strip().lower(): name for name in reader.fieldnames}
        if "frequency_hz" in fields and "amplitude_dbm" in fields:
            x_key, y_key, domain = fields["frequency_hz"], fields["amplitude_dbm"], "frequency"
        elif "time_s" in fields and "voltage_v" in fields:
            x_key, y_key, domain = fields["time_s"], fields["voltage_v"], "time"
        elif "index" in fields and "amplitude_dbm" in fields:
            raise ValueError(
                f"trace CSV has index-only frequency axis; re-save with "
                f"include_frequency=True for mask verification: {path}",
            )
        else:
            raise ValueError(
                f"unsupported trace CSV columns {reader.fieldnames!r} in {path}",
            )
        xs: list[float] = []
        ys: list[float] = []
        for row in reader:
            xs.append(float(row[x_key]))
            ys.append(float(row[y_key]))
    if not xs:
        raise ValueError(f"trace CSV is empty: {path}")
    return xs, ys, domain


def _point_ok(kind: str, y: float, y0: float, y1: float) -> tuple[bool, str]:
    if kind == "keep_below":
        return y <= y1, f"y<={y1}"
    if kind == "keep_above":
        return y >= y0, f"y>={y0}"
    if kind == "keep_inside":
        return y0 <= y <= y1, f"{y0}<=y<={y1}"
    if kind == "keep_outside":
        return y < y0 or y > y1, f"y<{y0} or y>{y1}"
    return False, "unknown kind"


def evaluate_mask(
    xs: list[float],
    ys: list[float],
    mask: dict[str, Any],
    *,
    max_violations: int = 20,
) -> MaskEvalResult:
    """Check trace samples against mask regions.

    Every region must contain at least one sample (coverage). Missing coverage
    is a FAIL, not a silent PASS.
    """
    regions = list(mask.get("regions") or [])
    if not regions:
        return MaskEvalResult(ok=False, message="mask has no regions to evaluate", violations=())

    violations: list[MaskViolation] = []
    uncovered: list[str] = []
    for region in regions:
        kind = str(region["kind"])
        x0 = float(region["x0"])
        x1 = float(region["x1"])
        y0 = float(region["y0"])
        y1 = float(region["y1"])
        region_id = str(region.get("id", "region"))
        samples_in_band = 0
        for x, y in zip(xs, ys, strict=True):
            if x < x0 or x > x1:
                continue
            samples_in_band += 1
            ok, limit = _point_ok(kind, y, y0, y1)
            if ok:
                continue
            if len(violations) < max_violations:
                violations.append(
                    MaskViolation(
                        region_id=region_id,
                        kind=kind,
                        x=x,
                        y=y,
                        limit=limit,
                    ),
                )
        if samples_in_band == 0:
            uncovered.append(region_id)

    if uncovered:
        ids = ", ".join(uncovered)
        return MaskEvalResult(
            ok=False,
            message=f"mask region(s) have no overlapping samples: {ids}",
            violations=tuple(violations),
        )
    if not violations:
        return MaskEvalResult(ok=True, message="", violations=())
    first = violations[0]
    extra = f" (+{len(violations) - 1} more)" if len(violations) > 1 else ""
    message = (
        f"mask region `{first.region_id}` ({first.kind}) failed at "
        f"x={first.x:g} y={first.y:g} (need {first.limit}){extra}"
    )
    return MaskEvalResult(ok=False, message=message, violations=tuple(violations))


def evaluate_mask_file(trace_csv: Path, mask: dict[str, Any]) -> MaskEvalResult:
    xs, ys, domain_hint = read_trace_xy(trace_csv)
    mask_domain = str(mask.get("domain", "")).strip().lower()
    if mask_domain and domain_hint != mask_domain:
        raise ValueError(
            f"mask domain {mask_domain!r} does not match trace domain {domain_hint!r} "
            f"in {trace_csv}",
        )
    return evaluate_mask(xs, ys, mask)


def resolve_mask_path(mask: str) -> Path:
    """Resolve a mask path relative to CWD, parameters file, or run output dir."""
    candidate = Path(mask)
    if candidate.is_file():
        return candidate
    try:
        ctx = get_context()
        params_path = getattr(ctx, "parameters_path", None)
        if params_path is not None:
            beside = Path(params_path).parent / mask
            if beside.is_file():
                return beside
        from colosseum.runner.paths import ensure_output_dir

        out = ensure_output_dir(ctx, logical_name=ctx.test_case_name) / mask
        if out.is_file():
            return out
    except RuntimeError:
        pass
    cwd = Path.cwd() / mask
    if cwd.is_file():
        return cwd
    raise FileNotFoundError(f"mask not found: {mask}")


def _resolve_csv(ctx: Any, stored: str) -> Path | None:
    resolver = getattr(ctx.db, "resolve_artifact_path", None)
    if callable(resolver):
        resolved = resolver(stored)
        if resolved is not None and Path(resolved).is_file():
            return Path(resolved)
    output_dir = getattr(ctx, "output_dir", None)
    if output_dir is not None and not Path(stored).is_absolute():
        joined = Path(output_dir) / stored
        if joined.is_file():
            return joined
    direct = Path(stored)
    if direct.is_file():
        return direct
    return None


def find_trace_csv(key: str, *, prefer_commands: tuple[str, ...]) -> Path | None:
    """Locate a CSV artifact for ``key``, preferring the given command names."""
    ctx = get_context()
    if not ctx.db.is_initialized():
        return None
    drain = getattr(ctx.db, "drain", None)
    if callable(drain):
        with contextlib.suppress(Exception):
            drain(timeout=5.0)
    for command in prefer_commands:
        row = ctx.db.get_measurement("equipment", command, key, row_index=0)
        if row is not None and row.artifact_path:
            path = _resolve_csv(ctx, str(row.artifact_path))
            if path is not None:
                return path
    matches: list[tuple[int, Path]] = []
    for record in ctx.db.fetch_all_measurements():
        if record.domain != "equipment" or record.key != key:
            continue
        if not record.artifact_path:
            continue
        path = _resolve_csv(ctx, str(record.artifact_path))
        if path is None or path.suffix.lower() != ".csv":
            continue
        row_id = 0 if record.id is None else int(record.id)
        matches.append((row_id, path))
    if not matches:
        return None
    matches.sort(key=lambda item: item[0])
    return matches[-1][1]


def verification_from_mask(
    *,
    key: str,
    mask: str,
    prefer_commands: tuple[str, ...],
    optional: bool = False,
) -> VerificationResult:
    """Shared PASS/FAIL path for SpecA/oscope ``verify_mask`` APIs."""
    if not mask:
        return VerificationResult(
            status="ERROR",
            message="verify_mask requires mask= (path to mask JSON)",
            optional=optional,
        )
    csv_path = find_trace_csv(key, prefer_commands=prefer_commands)
    if csv_path is None:
        return missing_measurement_result(key=key, optional=optional)
    try:
        mask_data = load_mask(resolve_mask_path(mask))
        result = evaluate_mask_file(csv_path, mask_data)
    except (OSError, ValueError) as exc:
        return VerificationResult(
            status="ERROR",
            message=str(exc),
            optional=optional,
        )
    if result.ok:
        return VerificationResult(status="PASS", message="", optional=optional)
    return VerificationResult(
        status="FAIL",
        message=result.message,
        optional=optional,
    )
