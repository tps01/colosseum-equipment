"""Siglent single-channel SPD1168X / SPD1305X supply commands.

Command strings from PyMeasure ``siglent_spdbase.SPDChannel``.
"""

from __future__ import annotations

from colosseum_equipment.instruments.psu.generic import GenericPSU


class SiglentSpdSingle(GenericPSU):
    """Shared SPD1168X / SPD1305X overrides; catalog classes keep their own slugs."""

    def set_voltage(self, voltage: float) -> None:
        self._scpi.write(f"CH1:VOLT {voltage:g}")

    def set_current_limit(self, current: float) -> None:
        self._scpi.write(f"CH1:CURR {current:g}")

    def set_output(self, enabled: bool) -> None:
        self._scpi.write("OUTP CH1,ON" if enabled else "OUTP CH1,OFF")

    def measure_voltage(self) -> float:
        return self._scpi.query_float("MEAS:VOLT? CH1")

    def measure_current(self) -> float:
        return self._scpi.query_float("MEAS:CURR? CH1")
