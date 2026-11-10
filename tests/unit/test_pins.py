"""Named GPIO pin resolution."""

from __future__ import annotations

import pytest
from colosseum_equipment.io._pins import resolve_pin_line
from colosseum_equipment.io.exceptions import IoConfigError


def test_named_integral_float_line_is_accepted() -> None:
    assert resolve_pin_line({"pins": {"reset": 1.0}}, line=None, name="reset") == 1


def test_named_fractional_line_is_rejected() -> None:
    with pytest.raises(IoConfigError, match="integral"):
        resolve_pin_line({"pins": {"reset": 1.9}}, line=None, name="reset")


def test_explicit_fractional_line_is_rejected() -> None:
    with pytest.raises(IoConfigError, match="integral"):
        resolve_pin_line({}, line=1.9, name=None)  # type: ignore[arg-type]


def test_bool_line_is_rejected() -> None:
    with pytest.raises(IoConfigError, match="integral"):
        resolve_pin_line({"pins": {"reset": True}}, line=None, name="reset")
