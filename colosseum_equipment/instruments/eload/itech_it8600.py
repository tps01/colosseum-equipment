"""Itech IT8600 series electronic load (SCPI).

Manual: IT8600 Programming Guide — ``CURRent:LEVel``, ``FUNCtion``, ``INPut:STATe``.
"""

from __future__ import annotations

from colosseum_equipment.instruments.eload.generic import GenericEload
from colosseum_equipment.instruments.registry import instrument_model


@instrument_model("eload", "itech-it8600")
class ItechIT8600Eload(GenericEload):
    _MODE_MAP = {
        "cc": "CURRent",
        "cv": "VOLTage",
        "cr": "RESistance",
        "cp": "POWer",
    }

    def set_mode(self, mode: str, *, channel: int = 1) -> None:
        self._apply_channel(channel)
        func = self._MODE_MAP.get(mode.lower(), mode)
        self._scpi.write(f"FUNCtion {func}")

    def set_current(self, current: float, *, channel: int = 1) -> None:
        self._apply_channel(channel)
        self._scpi.write(f"CURRent:LEVel {current}")

    def set_voltage(self, voltage: float, *, channel: int = 1) -> None:
        self._apply_channel(channel)
        self._scpi.write(f"VOLTage:LEVel {voltage}")

    def set_power(self, power: float, *, channel: int = 1) -> None:
        self._apply_channel(channel)
        self._scpi.write(f"POWer:LEVel {power}")

    def set_resistance(self, resistance: float, *, channel: int = 1) -> None:
        self._apply_channel(channel)
        self._scpi.write(f"RESistance:LEVel {resistance}")

    def engage(self, *, channel: int = 1) -> None:
        self._apply_channel(channel)
        self._scpi.write("INPut:STATe ON")

    def disengage(self, *, channel: int = 1) -> None:
        self._apply_channel(channel)
        self._scpi.write("INPut:STATe OFF")

    def measure_voltage(self, *, channel: int = 1) -> float:
        self._apply_channel(channel)
        return self._scpi.query_float("MEASure:VOLTage?")

    def measure_current(self, *, channel: int = 1) -> float:
        self._apply_channel(channel)
        return self._scpi.query_float("MEASure:CURRent?")
