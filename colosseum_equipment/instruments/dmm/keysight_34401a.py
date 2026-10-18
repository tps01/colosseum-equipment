"""Keysight / HP 34401A measure commands.

Command strings from PyMeasure ``hp.hp34401A``.
"""

from __future__ import annotations

from colosseum_equipment.instruments.dmm.generic import GenericDMM


class Keysight34401A(GenericDMM):
    """34401A overrides; the catalog class keeps the registered slug."""

    def measure_voltage(self, channel: int = 1) -> float:
        _ = channel
        return self._scpi.query_float("MEAS:VOLT:DC? DEF,DEF")

    def measure_current(self, channel: int = 1) -> float:
        _ = channel
        return self._scpi.query_float("MEAS:CURR:DC? DEF,DEF")

    def measure_resistance(self, channel: int = 1) -> float:
        _ = channel
        return self._scpi.query_float("MEAS:RES? DEF,DEF")
