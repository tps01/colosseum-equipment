"""Write configuration dicts as relaxed TOML."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_DEFAULT_HEADER = "# Generated configuration — review before reuse."
_BARE_WORD = re.compile(r"^[\w.:-]+$")
# Match core ``coerce_config_bool`` / TOML number spellings that would change type.
_BOOLISH_STRINGS = frozenset(
    {
        "true",
        "t",
        "yes",
        "y",
        "1",
        "false",
        "f",
        "no",
        "n",
        "0",
        "on",
        "off",
    },
)


class TomlWriteError(OSError):
    """Raised when a config TOML file cannot be written."""


def _string_needs_quotes(text: str) -> bool:
    """Return True when a bare write would not round-trip as this string."""
    if text.lower() in _BOOLISH_STRINGS:
        return True
    if text.startswith(("0x", "0o", "0b")):
        try:
            int(text, 0)
            return True
        except ValueError:
            return False
    if text[:1] in "+-" or text[:1].isdigit():
        try:
            if any(ch in text for ch in (".", "e", "E")):
                float(text)
                return True
            int(text)
            return True
        except ValueError:
            return False
    return False


def _format_toml_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    text = str(value)
    if _string_needs_quotes(text) or not _BARE_WORD.match(text):
        escaped = text.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return text


def _format_row(row: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    keys = sorted(row.keys(), key=lambda key: (0 if key.endswith("_id") else 1, key))
    for key in keys:
        value = row[key]
        if value is None or value == "":
            continue
        lines.append(f"{key} = {_format_toml_value(value)}")
    return lines


def _section_rows(value: object) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [row for row in value if isinstance(row, dict)]
    if isinstance(value, dict):
        return [value]
    return []


def render_config_toml(raw: dict[str, Any], *, header_comment: str | None = _DEFAULT_HEADER) -> str:
    """Render ``raw`` config dict as relaxed config TOML text."""
    lines: list[str] = []
    if header_comment:
        lines.append(header_comment)
        lines.append("")

    for top_key in sorted(raw):
        top_value = raw[top_key]
        if not isinstance(top_value, dict):
            continue
        for section_name in sorted(top_value):
            rows = _section_rows(top_value[section_name])
            if not rows:
                continue
            dotted = f"{top_key}.{section_name}"
            if len(rows) == 1:
                lines.append(f"[{dotted}]")
                lines.extend(_format_row(rows[0]))
                lines.append("")
            else:
                for row in rows:
                    lines.append(f"[[{dotted}]]")
                    lines.extend(_format_row(row))
                    lines.append("")

    text = "\n".join(lines)
    if text and not text.endswith("\n"):
        text += "\n"
    return text


def write_config_toml(
    raw: dict[str, Any],
    path: Path | str,
    *,
    header_comment: str | None = _DEFAULT_HEADER,
) -> Path:
    """Write ``raw`` config to ``path`` as UTF-8 relaxed TOML."""
    destination = Path(path).resolve()
    if destination.exists() and destination.is_dir():
        raise TomlWriteError(f"Config export path is a directory: {destination}")
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            render_config_toml(raw, header_comment=header_comment),
            encoding="utf-8",
        )
    except OSError as exc:
        raise TomlWriteError(f"Failed to write config TOML to {destination}: {exc}") from exc
    return destination
