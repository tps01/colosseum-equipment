"""Rigol DG800-series waveform generator commands.

Command strings from PyMeasure ``rigol_dg800.VoltageChannel``.
``set_power`` stays on generic SCPI: the DG800 source programs volts, not dBm.
"""

from __future__ import annotations

from colosseum_equipment.instruments.asg.generic import GenericASG


class RigolDg800(GenericASG):
    """Shared DG800 overrides; catalog classes keep their own slugs."""

    def set_frequency(self, frequency: float) -> None:
        self._scpi.write(f":SOUR1:FREQ {frequency:f}")

    def set_output(self, enabled: bool) -> None:
        self._scpi.write(":OUTP1 ON" if enabled else ":OUTP1 OFF")
