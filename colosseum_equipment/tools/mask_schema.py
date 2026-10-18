"""JSON mask schema: load, validate, save, and built-in templates."""

from __future__ import annotations

import json
from copy import deepcopy
from importlib import resources
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from importlib.resources.abc import Traversable

REGION_KINDS = frozenset({"keep_below", "keep_above", "keep_inside", "keep_outside"})
DOMAINS = frozenset({"frequency", "time"})


class MaskSchemaError(ValueError):
    """Mask JSON failed validation."""


def _as_float(value: object, field: str) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise MaskSchemaError(f"{field} must be a number") from exc


def validate_mask(mask: dict[str, Any]) -> dict[str, Any]:
    """Return a normalized deep copy of ``mask`` or raise ``MaskSchemaError``."""
    if not isinstance(mask, dict):
        raise MaskSchemaError("mask must be a JSON object")
    version = mask.get("version", 1)
    if int(version) != 1:
        raise MaskSchemaError(f"unsupported mask version {version!r} (expected 1)")
    domain = str(mask.get("domain", "")).strip().lower()
    if domain not in DOMAINS:
        raise MaskSchemaError(f"domain must be one of {sorted(DOMAINS)}, got {domain!r}")

    x_unit = str(mask.get("x_unit") or ("Hz" if domain == "frequency" else "s"))
    y_unit = str(mask.get("y_unit") or ("dBm" if domain == "frequency" else "V"))
    setup_raw = mask.get("setup") or {}
    if not isinstance(setup_raw, dict):
        raise MaskSchemaError("setup must be an object")
    setup = {str(k): _as_float(v, f"setup.{k}") for k, v in setup_raw.items()}

    regions_raw = mask.get("regions")
    if not isinstance(regions_raw, list):
        raise MaskSchemaError("regions must be a list")
    regions: list[dict[str, Any]] = []
    for index, region in enumerate(regions_raw):
        if not isinstance(region, dict):
            raise MaskSchemaError(f"regions[{index}] must be an object")
        kind = str(region.get("kind", "")).strip().lower()
        if kind not in REGION_KINDS:
            raise MaskSchemaError(
                f"regions[{index}].kind must be one of {sorted(REGION_KINDS)}, got {kind!r}",
            )
        x0 = _as_float(region.get("x0"), f"regions[{index}].x0")
        x1 = _as_float(region.get("x1"), f"regions[{index}].x1")
        y0 = _as_float(region.get("y0"), f"regions[{index}].y0")
        y1 = _as_float(region.get("y1"), f"regions[{index}].y1")
        if x1 < x0:
            x0, x1 = x1, x0
        if y1 < y0:
            y0, y1 = y1, y0
        region_id = str(region.get("id") or f"region_{index}")
        regions.append(
            {
                "id": region_id,
                "kind": kind,
                "x0": x0,
                "x1": x1,
                "y0": y0,
                "y1": y1,
            },
        )

    return {
        "version": 1,
        "domain": domain,
        "x_unit": x_unit,
        "y_unit": y_unit,
        "setup": setup,
        "regions": regions,
    }


def load_mask(path: str | Path) -> dict[str, Any]:
    """Load and validate a mask JSON file."""
    resolved = Path(path)
    if not resolved.is_file():
        raise FileNotFoundError(f"mask not found: {resolved}")
    try:
        raw = json.loads(resolved.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise MaskSchemaError(f"invalid mask JSON in {resolved}: {exc}") from exc
    return validate_mask(raw)


def save_mask(path: str | Path, mask: dict[str, Any]) -> Path:
    """Validate and write mask JSON."""
    normalized = validate_mask(mask)
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(normalized, indent=2) + "\n", encoding="utf-8")
    return out


def _template_files() -> Traversable | None:
    """Return an importlib.resources Traversable for built-in templates."""
    try:
        return resources.files("colosseum_equipment.tools.mask_templates")
    except (TypeError, FileNotFoundError, ModuleNotFoundError):
        return None


def list_mask_templates() -> list[str]:
    root = _template_files()
    if root is not None:
        try:
            return sorted(
                p.name[:-5]
                for p in root.iterdir()
                if getattr(p, "name", "").endswith(".json")
            )
        except (OSError, FileNotFoundError, AttributeError):
            pass
    fallback = Path(__file__).resolve().parent / "mask_templates"
    if not fallback.is_dir():
        return []
    return sorted(p.stem for p in fallback.glob("*.json"))


def load_mask_template(template_id: str) -> dict[str, Any]:
    """Load a built-in template by id (filename stem)."""
    name = template_id.strip()
    if not name:
        raise MaskSchemaError("template id is empty")
    root = _template_files()
    if root is not None:
        candidate = root / f"{name}.json"
        try:
            if candidate.is_file():
                raw = json.loads(candidate.read_text(encoding="utf-8"))
                return deepcopy(validate_mask(raw))
        except (OSError, FileNotFoundError, AttributeError, MaskSchemaError):
            pass
        except json.JSONDecodeError as exc:
            raise MaskSchemaError(f"invalid mask template {name!r}: {exc}") from exc
    path = Path(__file__).resolve().parent / "mask_templates" / f"{name}.json"
    if not path.is_file():
        known = ", ".join(list_mask_templates()) or "(none)"
        raise MaskSchemaError(f"unknown mask template {name!r}; known: {known}")
    return deepcopy(load_mask(path))
