"""Keysight / HP 34401A measure commands.

Command strings from PyMeasure ``hp.hp34401A``.
"""

from __future__ import annotations

from colosseum_equipment.instruments.dmm.generic import GenericDMM
from colosseum_equipment.instruments.registry import _confirmed_generic_commands


@_confirmed_generic_commands("get_function", "fetch")
class Keysight34401A(GenericDMM):
    """34401A overrides; the catalog class keeps the registered slug."""

    def measure_voltage(self, channel: int = 1) -> float:
        return self._measure("VOLT:DC", channel)

    def measure_current(self, channel: int = 1) -> float:
        return self._measure("CURR:DC", channel)

    def measure_resistance(self, channel: int = 1) -> float:
        return self._measure("RES", channel)
