"""Agilent 6050/6060 electronic load family (SCPI).

Manual: Agilent 06060-90005 Programming Manual — ``CURR``, ``VOLT``, ``INPUT``, ``MEAS:CURR?``.
"""

from __future__ import annotations

from colosseum_equipment.instruments._capabilities import unsupported
from colosseum_equipment.instruments.eload.generic import GenericEload
from colosseum_equipment.instruments.registry import _confirmed_generic_commands, instrument_model


@instrument_model("eload", "agilent-6050")
@_confirmed_generic_commands(
    "set_current",
    "set_voltage",
    "measure_voltage",
    "measure_current",
)
class Agilent6050Eload(GenericEload):
    def set_mode(self, mode: str, *, channel: int = 1) -> None:
        self._apply_channel(channel)
        self._scpi.write(f"MODE:{mode.upper()}")

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
