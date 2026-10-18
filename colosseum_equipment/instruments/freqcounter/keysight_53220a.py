"""Keysight 53220A/53230A frequency counter (SCPI).

Manual: Keysight 53220A/53230A User's Guide — ``MEASure:FREQuency?``, gate time.
"""

from __future__ import annotations

from colosseum_equipment.instruments.freqcounter.generic import GenericFreqCounter
from colosseum_equipment.instruments.registry import instrument_model


@instrument_model("freqcounter", "keysight-53220a", "keysight-53230a")
class Keysight53220AFreqCounter(GenericFreqCounter):
    def set_gate_time(self, seconds: float) -> None:
        self._scpi.write(f"SENSe:FREQuency:GATE:TIME {seconds}")

    def measure_frequency(self, *, channel: int = 1) -> float:
        self._select_input(channel)
        return self._scpi.query_float("MEASure:FREQuency?")

    def measure_period(self, *, channel: int = 1) -> float:
        self._select_input(channel)
        return self._scpi.query_float("MEASure:PERiod?")

    def measure_frequency_mean_hz(self, *, channel: int = 1) -> float:
        self._select_input(channel)
        self._scpi.write("CALCulate:AVERage:STATe ON")
        return self._scpi.query_float("CALCulate:AVERage:MEAN?")

    def measure_frequency_stdev_hz(self, *, channel: int = 1) -> float:
        self._select_input(channel)
        self._scpi.write("CALCulate:AVERage:STATe ON")
        return self._scpi.query_float("CALCulate:AVERage:SDEViation?")
