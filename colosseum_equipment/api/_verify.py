"""Shared verification helpers for equipment measurement APIs."""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, cast

from colosseum.context import get_context
from colosseum.decorators import (
    VerificationResult,
    missing_measurement_result,
    verification,
)
from colosseum.decorators._common import command_id_for_module

from colosseum_equipment.api._docstrings import tolerance_verify_doc

if TYPE_CHECKING:
    from collections.abc import Callable


def verify_tolerance(
    *,
    domain: str,
    command: str,
    key: str,
    expected_val: float,
    tolerance: float,
    optional: bool = False,
    unit: str = "",
) -> VerificationResult:
    row = get_context().db.get_measurement(domain, command, key, row_index=0)
    if row is None or row.value is None:
        return missing_measurement_result(key=key, optional=optional)
    actual = float(str(row.value))
    if abs(actual - expected_val) <= tolerance:
        return VerificationResult(status="PASS", message="", optional=optional, actual=actual)
    unit_suffix = f" {unit}" if unit else ""
    return VerificationResult(
        status="FAIL",
        message=f"expected {expected_val} +/- {tolerance}{unit_suffix}, got {actual}",
        optional=optional,
        actual=actual,
    )


def _caller_module() -> str:
    frame = inspect.currentframe()
    caller_frame = frame.f_back.f_back if frame is not None and frame.f_back is not None else None
    if caller_frame is None:
        return __name__
    return str(caller_frame.f_globals.get("__name__", __name__))


def _source_command(command: str, caller_module: str) -> str:
    return command if "." in command else command_id_for_module(caller_module, command)


def tolerance_verifier(
    command: str,
    *,
    name: str,
    default_tolerance: float = 0.1,
    unit: str = "",
    domain: str = "equipment",
) -> Callable[..., VerificationResult]:
    """Build a @verification function that compares a prior measurement with tolerance."""
    caller_module = _caller_module()
    source_command = _source_command(command, caller_module)

    def verify(
        *,
        key: str,
        expected_val: float,
        tolerance: float = default_tolerance,
        optional: bool = False,
    ) -> VerificationResult:
        return verify_tolerance(
            domain=domain,
            command=source_command,
            key=key,
            expected_val=expected_val,
            tolerance=tolerance,
            optional=optional,
            unit=unit,
        )

    verify.__name__ = name
    verify.__qualname__ = name
    verify.__module__ = caller_module
    verify.__doc__ = tolerance_verify_doc(source_command, unit=unit)
    return cast(
        "Callable[..., VerificationResult]",
        verification(verify),
    )


def limit_verifier(
    command: str,
    *,
    name: str,
    upper: bool = True,
    unit: str = "",
    domain: str = "equipment",
) -> Callable[..., VerificationResult]:
    """Build a verifier that checks a measurement is below (or above) a limit."""
    caller_module = _caller_module()
    source_command = _source_command(command, caller_module)

    def verify(
        *,
        key: str,
        limit: float,
        optional: bool = False,
    ) -> VerificationResult:
        row = get_context().db.get_measurement(domain, source_command, key, row_index=0)
        if row is None or row.value is None:
            return missing_measurement_result(key=key, optional=optional)
        actual = float(str(row.value))
        ok = actual <= limit if upper else actual >= limit
        if ok:
            return VerificationResult(status="PASS", message="", optional=optional, actual=actual)
        cmp = "<=" if upper else ">="
        unit_suffix = f" {unit}" if unit else ""
        return VerificationResult(
            status="FAIL",
            message=f"expected {actual}{unit_suffix} {cmp} {limit}{unit_suffix}",
            optional=optional,
            actual=actual,
        )

    verify.__name__ = name
    verify.__qualname__ = name
    verify.__module__ = caller_module
    verify.__doc__ = f"Verify ``{source_command}`` against a {'upper' if upper else 'lower'} limit."
    return cast("Callable[..., VerificationResult]", verification(verify))


def minimum_verifier(
    command: str,
    *,
    name: str,
    unit: str = "",
    domain: str = "equipment",
) -> Callable[..., VerificationResult]:
    """Build a verifier that checks a measurement is at least ``minimum``.

    Resolves the source command from *this* caller's module (not via
    ``limit_verifier``, which would mis-attribute the module).
    """
    caller_module = _caller_module()
    source_command = _source_command(command, caller_module)

    def verify(
        *,
        key: str,
        limit: float,
        optional: bool = False,
    ) -> VerificationResult:
        row = get_context().db.get_measurement(domain, source_command, key, row_index=0)
        if row is None or row.value is None:
            return missing_measurement_result(key=key, optional=optional)
        actual = float(str(row.value))
        if actual >= limit:
            return VerificationResult(status="PASS", message="", optional=optional, actual=actual)
        unit_suffix = f" {unit}" if unit else ""
        return VerificationResult(
            status="FAIL",
            message=f"expected {actual}{unit_suffix} >= {limit}{unit_suffix}",
            optional=optional,
            actual=actual,
        )

    verify.__name__ = name
    verify.__qualname__ = name
    verify.__module__ = caller_module
    verify.__doc__ = f"Verify ``{source_command}`` is at least ``limit``."
    return cast("Callable[..., VerificationResult]", verification(verify))
