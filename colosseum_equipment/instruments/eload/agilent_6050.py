"""Agilent 6050/6060 electronic load family (SCPI).

Manual: Agilent 06060-90005 Programming Manual — ``CURR``, ``VOLT``, ``INPUT``, ``MEAS:CURR?``.
"""

from __future__ import annotations

from colosseum_equipment.instruments._capabilities import unsupported
from colosseum_equipment.instruments.eload.generic import GenericEload
from colosseum_equipment.instruments.registry import instrument_model


@instrument_model("eload", "agilent-6050")
class Agilent6050Eload(GenericEload):
    def set_mode(self, mode: str, *, channel: int = 1) -> None:
        self._apply_channel(channel)
        self._scpi.write(f"MODE:{mode.upper()}")

    def set_current(self, current: float, *, channel: int = 1) -> None:
        self._apply_channel(channel)
        self._scpi.write(f"CURR {current}")

    def set_voltage(self, voltage: float, *, channel: int = 1) -> None:
        self._apply_channel(channel)
        self._scpi.write(f"VOLT {voltage}")

    def set_power(self, power: float, *, channel: int = 1) -> None:
        _ = power
        unsupported(self._model, "set_power", detail="6060 family supports CC/CV only")

    def set_resistance(self, resistance: float, *, channel: int = 1) -> None:
        _ = resistance
        unsupported(self._model, "set_resistance", detail="6060 family supports CC/CV only")

    def engage(self, *, channel: int = 1) -> None:
        self._apply_channel(channel)
        self._scpi.write("INPUT ON")

    def disengage(self, *, channel: int = 1) -> None:
        self._apply_channel(channel)
        self._scpi.write("INPUT OFF")

    def measure_voltage(self, *, channel: int = 1) -> float:
        self._apply_channel(channel)
        return self._scpi.query_float("MEAS:VOLT?")

    def measure_current(self, *, channel: int = 1) -> float:
        self._apply_channel(channel)
        return self._scpi.query_float("MEAS:CURR?")
