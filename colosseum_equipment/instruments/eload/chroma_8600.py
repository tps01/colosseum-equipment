"""Chroma / programmable DC load 8600 series (SCPI).

Manual: 8600 Series Programming Manual — ``FUNCtion``, ``CURRent:LEVel``, ``INPut:STATe``.
"""

from __future__ import annotations

from colosseum_equipment.instruments.eload.generic import GenericEload
from colosseum_equipment.instruments.registry import instrument_model


@instrument_model("eload", "chroma-8600", "chroma-8601")
class Chroma8600Eload(GenericEload):
    _MODE_MAP = {
        "cc": "CURRent",
        "cv": "VOLTage",
        "cr": "RESistance",
        "cp": "POWer",
    }

    def set_mode(self, mode: str, *, channel: int = 1) -> None:
        self._apply_channel(channel)
        func = self._MODE_MAP.get(mode.lower(), mode)
        self._scpi.write(f"FUNC {func}")

    def set_current(self, current: float, *, channel: int = 1) -> None:
        self._apply_channel(channel)
        self._scpi.write(f"CURR:LEV {current}")

    def set_voltage(self, voltage: float, *, channel: int = 1) -> None:
        self._apply_channel(channel)
        self._scpi.write(f"VOLT {voltage}")

    def set_power(self, power: float, *, channel: int = 1) -> None:
        self._apply_channel(channel)
        self._scpi.write(f"POW:LEV {power}")

    def set_resistance(self, resistance: float, *, channel: int = 1) -> None:
        self._apply_channel(channel)
        self._scpi.write(f"RES:LEV {resistance}")

    def engage(self, *, channel: int = 1) -> None:
        self._apply_channel(channel)
        self._scpi.write("INP 1")

    def disengage(self, *, channel: int = 1) -> None:
        self._apply_channel(channel)
        self._scpi.write("INP 0")

    def measure_voltage(self, *, channel: int = 1) -> float:
        self._apply_channel(channel)
        return self._scpi.query_float("MEAS:VOLT?")

    def measure_current(self, *, channel: int = 1) -> float:
        self._apply_channel(channel)
        return self._scpi.query_float("MEAS:CURR?")
