"""Normalize RF switch path readback strings."""

from __future__ import annotations

import re


def normalize_switch_path(raw: str) -> str:
    """Convert vendor path readback to ``A=1;B=0`` style when possible."""
    text = raw.strip()
    if not text:
        return text
    if "=" in text or ";" in text:
        return text
    if text.upper().startswith("SETP="):
        return text
    digits = re.sub(r"[^01]", "", text)
    if not digits:
        return text
    parts = [f"{chr(ord('A') + index)}={digits[index]}" for index in range(len(digits))]
    return ";".join(parts)
