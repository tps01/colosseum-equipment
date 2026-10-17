"""Keithley DMM6500 measure commands.

Command strings from PyMeasure ``keithleyDMM6500`` (``:SENS:FUNC`` / ``:READ?``).
"""

from __future__ import annotations

from colosseum_equipment.instruments.dmm.generic import GenericDMM


class KeithleyDmm6500Family(GenericDMM):
    """DMM6500 overrides; the catalog class keeps the registered slug."""

    def measure_voltage(self, channel: int) -> float:
        _ = channel
        self._scpi.write(':SENS:FUNC "VOLT:DC"')
        return self._scpi.query_float(":READ?")

    def measure_current(self, channel: int) -> float:
        _ = channel
        self._scpi.write(':SENS:FUNC "CURR:DC"')
        return self._scpi.query_float(":READ?")

    def measure_resistance(self, channel: int) -> float:
        _ = channel
        self._scpi.write(':SENS:FUNC "RES"')
        return self._scpi.query_float(":READ?")
