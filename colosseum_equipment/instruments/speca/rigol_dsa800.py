"""Rigol DSA800-series spectrum analyzer commands.

Command strings from the MIT QCoDeS contrib file ``Rigol_DSA800``.
"""

from __future__ import annotations

from colosseum_equipment.instruments.speca.generic import GenericSpecA


class RigolDsa800(GenericSpecA):
    """Shared DSA800 overrides; catalog classes keep their own slugs."""

    def set_center_frequency(self, frequency: float) -> None:
        self._scpi.write(f":SENSe:FREQuency:CENTer {frequency}")

    def set_span(self, span: float) -> None:
        self._scpi.write(f":SENSe:FREQuency:SPAN {span}")

    def set_rbw(self, rbw: float) -> None:
        self._scpi.write(f":SENSe:BANDwidth:RESolution {rbw}")

    def set_reference_level(self, level_dbm: float) -> None:
        self._scpi.write(f":DISPlay:WINdow:TRACe:Y:SCALe:RLEVel {level_dbm}")

    def set_marker_frequency(self, marker: int, frequency_hz: float) -> None:
        self._scpi.write(f":CALCulate:MARKer{marker}:X {frequency_hz}")

    def measure_marker_power(self, marker: int = 1) -> float:
        return self._scpi.query_float(f":CALCulate:MARKer{marker}:Y?")
