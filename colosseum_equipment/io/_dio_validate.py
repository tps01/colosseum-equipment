"""Shared DIO line/value validation (reject instead of silent mask)."""

from __future__ import annotations

from colosseum_equipment.io.exceptions import IoConfigError


def require_line(line: int, port_lines: int) -> None:
    if line < 0 or line >= port_lines:
        raise IoConfigError(f"line {line} out of range for port_lines={port_lines}")


def require_mask_value(value: int, mask: int, *, what: str) -> int:
    """Return value if it only uses bits in mask; otherwise raise."""
    if value < 0:
        raise IoConfigError(f"{what} must be >= 0; got {value}")
    if value & ~mask:
        raise IoConfigError(
            f"{what} 0x{value:X} has bits outside port mask 0x{mask:X}",
        )
    return value


def require_output_value(value: int, *, direction: int, mask: int) -> int:
    """Reject bits outside the port mask or outside configured outputs."""
    require_mask_value(value, mask, what="output value")
    illegal = value & ~direction & mask
    if illegal:
        raise IoConfigError(
            f"output value 0x{value:X} sets input-only bits 0x{illegal:X} " f"(direction=0x{direction:X})",
        )
    return value & direction & mask
