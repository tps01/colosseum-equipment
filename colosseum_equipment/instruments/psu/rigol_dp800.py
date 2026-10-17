"""Rigol DP800-series supply commands.

Command strings from python-ivi ``ivi.scpi.dcpwr`` / ``ivi.rigol.rigolDP800``.
"""

from __future__ import annotations

from colosseum_equipment.instruments.psu.generic import GenericPSU


class RigolDp800(GenericPSU):
    """Shared DP800 overrides; catalog classes keep their own slugs."""

    def set_voltage(self, voltage: float) -> None:
        self._scpi.write("instrument:nselect 1")
        self._scpi.write(f"source:voltage:level {voltage:.6f}")

    def set_current_limit(self, current: float) -> None:
        self._scpi.write("instrument:nselect 1")
        self._scpi.write(f"source:current:level {current:.6f}")

    def set_output(self, enabled: bool) -> None:
        self._scpi.write("instrument:nselect 1")
        self._scpi.write("output on" if enabled else "output off")

    def measure_voltage(self) -> float:
        self._scpi.write("instrument:nselect 1")
        return self._scpi.query_float("measure:voltage?")

    def measure_current(self) -> float:
        self._scpi.write("instrument:nselect 1")
        return self._scpi.query_float("measure:current?")
