"""Rigol DHO-series oscilloscope commands.

Command strings from PyMeasure ``rigol_dho_base.DHOBase``.
"""

from __future__ import annotations

from colosseum_equipment.instruments.oscope.generic import GenericOscope
from colosseum_equipment.protocols.scpi import wait_opc


class RigolDho(GenericOscope):
    """Shared DHO overrides; catalog classes keep their own slugs."""

    def set_timebase_scale(self, seconds_per_div: float) -> None:
        self._scpi.write(f":TIM:MAIN:SCAL {seconds_per_div:g}")

    def single_acquire(self) -> None:
        self._scpi.write(":SING")
        wait_opc(self._scpi)

    def measure_vpp(self, channel: int = 1) -> float:
        return self._scpi.query_float(f":MEAS:ITEM? VPP,CHAN{channel}")
