"""Tektronix FCA3000/FCA3100/MCA3000 timer/counter (SCPI).

Manual: 077-0494-00 Programmer Manual — frequency measurement subsystem.
Catalog: https://www.tek.com/en/frequency-counter/mca3000-manual/fca3000-and-fca3100-series-mca3000-series
"""

from __future__ import annotations

from colosseum_equipment.instruments.freqcounter.generic import GenericFreqCounter
from colosseum_equipment.instruments.registry import instrument_model


@instrument_model(
    "freqcounter",
    "tektronix-fca3000",
    "tektronix-fca3100",
    "tektronix-mca3000",
    "tektronix-fca3003",
    "tektronix-fca3020",
    "tektronix-fca3103",
    "tektronix-fca3120",
    "tektronix-mca3027",
    "tektronix-mca3040",
)
class TekFca3000FreqCounter(GenericFreqCounter):
    def set_gate_time(self, seconds: float) -> None:
        self._scpi.write(f"SENSe:FREQuency:GATE:TIME {seconds}")

    def measure_frequency(self, *, channel: int = 1) -> float:
        self._select_input(channel)
        self._scpi.write(":FUNC 'FREQ'")
        return self._scpi.query_float("MEASure:FREQuency?")

    def measure_period(self, *, channel: int = 1) -> float:
        self._select_input(channel)
        self._scpi.write(":FUNC 'PER'")
        return self._scpi.query_float("MEASure:PERiod?")
