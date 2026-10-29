"""Offline mask authoring helpers (``col.equipment.tools``).

Procedure-time apply/verify live on ``col.equipment.speca`` /
``col.equipment.oscope``. This module is for creating and managing mask JSON
ahead of a run.
"""

from __future__ import annotations

from typing import Any

from colosseum_equipment.tools.mask_editor import MaskEditorCancelled, run_mask_editor
from colosseum_equipment.tools.mask_schema import (
    list_mask_templates as _list_mask_templates,
)
from colosseum_equipment.tools.mask_schema import load_mask as _load_mask
from colosseum_equipment.tools.mask_schema import save_mask as _save_mask

__all__ = [
    "MaskEditorCancelled",
    "create_mask",
    "list_mask_templates",
    "load_mask",
    "save_mask",
]


def create_mask(
    *,
    domain: str,
    path: str = "",
    template: str = "",
    import_path: str = "",
) -> str:
    """Open the interactive mask editor; block until Save or Cancel.

    Intended for offline authoring, not for standard test procedures. Procedure
    scripts should call ``speca.apply_mask_setup`` / ``oscope.apply_mask_setup``
    and ``verify_mask`` instead.

    :param domain: ``frequency`` (Hz vs dBm) or ``time`` (s vs V).
    :param path: Optional destination for Save (relative to CWD or run artifacts).
    :param template: Built-in template id to seed the editor.
    :param import_path: Existing mask JSON to open for editing.
    :returns: Absolute path of the saved mask file.
    :raises RuntimeError: If the user cancels (message ``mask editor cancelled``).
    """
    saved = run_mask_editor(
        domain=domain,
        path=path,
        template=template,
        import_path=import_path,
    )
    return str(saved)


def load_mask(*, path: str) -> dict[str, Any]:
    """Parse and validate a mask JSON file (no GUI).

    :param path: Existing input file path, absolute or relative to the process working
        directory.

    :returns: Validated, normalized mask dictionary. This helper does not record evidence.
    """
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
    return str(_save_mask(path, mask))


def list_mask_templates() -> list[str]:
    """Return built-in mask template ids."""
    return _list_mask_templates()
