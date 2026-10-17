"""Rohde & Schwarz FSWP phase noise analyzer.

Manual: R&S FSWP User Manual (free PDF on rohde-schwarz.com).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from colosseum_equipment.instruments.phasenoiseanalyzer.generic import GenericPhaseNoiseAnalyzer
from colosseum_equipment.instruments.registry import instrument_model
from colosseum_equipment.protocols.scpi import wait_opc

if TYPE_CHECKING:
    from colosseum_equipment.transports.base import Transport


@instrument_model("phasenoiseanalyzer", "rohde-fswp")
class RohdeFswpPhaseNoiseAnalyzer(GenericPhaseNoiseAnalyzer):
    """FSWP phase-noise measurement overrides."""

    def __init__(self, transport: Transport, config: dict[str, Any]) -> None:
        super().__init__(transport, config)
        self._model = "rohde-fswp"

    def set_carrier_frequency_hz(self, frequency_hz: float) -> None:
        self._scpi.write(f"FREQ:CENT {frequency_hz:.6f}")

    def set_offset_start_hz(self, offset_hz: float) -> None:
        self._scpi.write(f"FREQ:STAR {offset_hz:.6f}")

    def set_offset_stop_hz(self, offset_hz: float) -> None:
        self._scpi.write(f"FREQ:STOP {offset_hz:.6f}")

    def initiate(self) -> None:
        self._scpi.write("INIT:CONT OFF")
        self._scpi.write("INIT:IMM")

    def measure_spot_noise_dbc_hz(self, offset_hz: float) -> float:
        self.initiate()
        wait_opc(self._scpi)
        self._scpi.write(f"CALC:SNO:X {offset_hz:.6f}")
        return self._scpi.query_float("CALC:SNO:Y?")

    def measure_carrier_frequency_hz(self) -> float:
        return self._scpi.query_float("FREQ:CENT?")
