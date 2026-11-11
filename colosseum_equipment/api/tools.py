"""Mask JSON helpers (``col.equipment.tools``).

Create masks with colosseum-library/tools/mask_editor.py. Apply and verify
masks through ``col.equipment.speca`` and ``col.equipment.oscope``.
"""

from __future__ import annotations

from typing import Any

from colosseum.logging import get_logger

from colosseum_equipment.tools.mask_schema import (
    list_mask_templates as _list_mask_templates,
)
from colosseum_equipment.tools.mask_schema import load_mask as _load_mask
from colosseum_equipment.tools.mask_schema import save_mask as _save_mask

_logger = get_logger("colosseum.equipment")

__all__ = [
    "list_mask_templates",
    "load_mask",
    "save_mask",
]


def load_mask(*, path: str) -> dict[str, Any]:
    """Parse and validate a mask JSON file (no GUI).

    :param path: Existing input file path, absolute or relative to the process working
        directory.

    :returns: Validated, normalized mask dictionary. This helper does not record evidence.
    """
    _logger.info("Loading mask from %s", path)
    return _load_mask(path)


def save_mask(*, path: str, mask: dict[str, Any]) -> str:
    """Validate and write a mask JSON file.

    :param path: Destination file path, absolute or relative to the process working directory.
        This offline helper does not require an active run.
    :param mask: Mask definition used by this operation; see the mask workflow for supported
        structure and units.

    :returns: Saved path as a string, preserving relative or absolute form. This helper does not
        record evidence.
    """
    _logger.info("Saving mask to %s", path)
    return str(_save_mask(path, mask))


def list_mask_templates() -> list[str]:
    """Return built-in mask template ids."""
    _logger.info("Listing built-in mask templates")
    return _list_mask_templates()
