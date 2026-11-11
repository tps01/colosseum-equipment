"""Sphinx-style docstring fragments for ``col.equipment`` APIs."""

from __future__ import annotations

from colosseum.docstrings import sphinx_param as _sphinx_param


def _key_param(domain: str = "equipment") -> str:
    return _sphinx_param(
        "key",
        "str",
        f"Unique measurement key within domain ``{domain}`` and this command name. "
        "Must not collide with another instrument's measurement using the same command name.",
    )


def tolerance_verify_doc(measure_command: str, *, unit: str = "") -> str:
    unit_note = f" in {unit}" if unit else ""
    expected_desc = "Expected numeric value in the same units as the measurement."
    tolerance_desc = "Maximum allowed absolute deviation from ``expected_val``."
    optional_desc = "When ``True``, FAIL/ERROR does not fail the run at ``col.endex()``."
    return (
        f"Compare a prior ``{measure_command}`` measurement to an expected value{unit_note}.\n\n"
        f"{_key_param('equipment')}\n"
        f"{_sphinx_param('expected_val', 'float', expected_desc)}\n"
        f"{_sphinx_param('tolerance', 'float', tolerance_desc)}\n"
        f"{_sphinx_param('optional', 'bool', optional_desc, optional=True)}\n\n"
        ":returns: VerificationResult with PASS, FAIL, or ERROR status.\n"
        ":rtype: VerificationResult"
    )
