"""Rigol DG800-series waveform generator commands.

Command strings from PyMeasure ``rigol_dg800.VoltageChannel``.
``set_power`` is unsupported: the DG800 source programs volts, not dBm.
"""

from __future__ import annotations

from colosseum_equipment.instruments._capabilities import unsupported
from colosseum_equipment.instruments.asg.generic import GenericASG


class RigolDg800(GenericASG):
    """Shared DG800 overrides; catalog classes keep their own slugs."""

    def set_power(self, power_dbm: float, *, channel: int = 1) -> None:
        unsupported(
            self._model,
            "set_power",
            detail="DG800 programs amplitude in volts",
        )

    def set_frequency(self, frequency: float, *, channel: int = 1) -> None:
        ch = self._require_channel(channel)
        self._scpi.write(f":SOUR{ch}:FREQ {frequency:f}")

    def set_output(self, enabled: bool, *, channel: int = 1) -> None:
        ch = self._require_channel(channel)
        self._scpi.write(f":OUTP{ch} ON" if enabled else f":OUTP{ch} OFF")
