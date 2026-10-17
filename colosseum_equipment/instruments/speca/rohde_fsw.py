"""Rohde & Schwarz FSW signal and spectrum analyzer.

Manual: R&S FSW User Manual (free PDF on rohde-schwarz.com).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from colosseum_equipment.instruments.registry import instrument_model
from colosseum_equipment.instruments.speca.generic import GenericSpecA

if TYPE_CHECKING:
    from colosseum_equipment.transports.base import Transport


@instrument_model("speca", "rohde-fsw")
class RohdeFswSpecA(GenericSpecA):
    """FSW SCPI overrides (BAND / DISP:TRAC:Y:RLEV / marker)."""

    def __init__(self, transport: Transport, config: dict[str, Any]) -> None:
        super().__init__(transport, config)
        self._model = "rohde-fsw"

    def set_rbw(self, rbw: float) -> None:
        self._scpi.write(f"BAND {rbw:.6f}")

    def set_vbw(self, vbw: float) -> None:
        self._scpi.write(f"BAND:VID {vbw:.6f}")

    def set_reference_level(self, level_dbm: float) -> None:
        self._scpi.write(f"DISP:TRAC:Y:RLEV {level_dbm:.3f}")

    def toggle_marker(self, marker: int, enabled: bool) -> None:
        self._scpi.write(f"CALC:MARK{marker}:STAT {'ON' if enabled else 'OFF'}")

    def peak_search(self, marker: int = 1) -> None:
        self._scpi.write(f"CALC:MARK{marker}:MAX")

    def set_marker_frequency(self, marker: int, frequency_hz: float) -> None:
        self._scpi.write(f"CALC:MARK{marker}:X {frequency_hz:.6f}")

    def measure_marker_power(self, marker: int = 1) -> float:
        return self._scpi.query_float(f"CALC:MARK{marker}:Y?")

    def measure_marker_frequency(self, marker: int = 1) -> float:
        return self._scpi.query_float(f"CALC:MARK{marker}:X?")
