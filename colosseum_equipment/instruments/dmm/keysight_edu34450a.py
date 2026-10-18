from __future__ import annotations

from colosseum_equipment.instruments.dmm.generic import GenericDMM
from colosseum_equipment.instruments.registry import instrument_model


@instrument_model("dmm", "keysight-edu34450a")
class KeysightEDU34450A(GenericDMM):
    """Reference driver for Keysight EDU34450A (Keysight EDU34450A Programming Guide)."""

    def measure_voltage_dc(self, channel: int = 1) -> float:
        self._require_channel(channel)
        self._scpi.write(f"CONF:VOLT:DC CH{channel}")
        return self._scpi.query_float("READ?")

    def measure_voltage(self, channel: int = 1) -> float:
        return self.measure_voltage_dc(channel)

    def measure_current_dc(self, channel: int = 1) -> float:
        self._require_channel(channel)
        self._scpi.write(f"CONF:CURR:DC CH{channel}")
        return self._scpi.query_float("READ?")

    def measure_current(self, channel: int = 1) -> float:
        return self.measure_current_dc(channel)

    def measure_resistance(self, channel: int = 1) -> float:
        self._require_channel(channel)
        self._scpi.write(f"CONF:RES CH{channel}")
        return self._scpi.query_float("READ?")
