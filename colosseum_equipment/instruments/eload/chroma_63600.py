"""Chroma 63600 mainframe static load control, not the unrelated 8600 dialect.

Manual: Chroma 63600 Series Operation & Programming Manual v2.2,
chapter 5 (CHAN, MODE, LOAD and static level/slew commands).
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from colosseum_equipment.exceptions import EquipmentCapabilityError, EquipmentResponseError
from colosseum_equipment.instruments._capabilities import supported_commands
from colosseum_equipment.instruments.eload.generic import GenericEload
from colosseum_equipment.instruments.registry import instrument_model

if TYPE_CHECKING:
    from colosseum_equipment.transports.base import Transport


@instrument_model("eload", "chroma-63600-5")
@supported_commands(
    "set_mode", "set_current", "set_voltage", "set_power", "set_resistance", "engage", "disengage",
    "measure_voltage", "measure_current", "measure_power_w", "measure_input_state", "set_slew_rate",
)
class Chroma63600(GenericEload):
    """Address logical load channels through one mainframe session.

    Configure channels to match installed modules. 63630-80-60 is a module;
    63630-80-20 from the inventory needs identity confirmation. Static mode uses
    the high range and L1. Parallel and synchronized multi-frame modes excluded.
    """

    def __init__(self, transport: Transport, config: dict[str, Any]) -> None:
        count = int(config.get("channels") or config.get("channel_count") or 1)
        if not 1 <= count <= 10:
            raise EquipmentCapabilityError("63600-5 supports up to ten logical channels")
        super().__init__(transport, {**config, "channels": count})

    def _apply_channel(self, channel: int) -> int:
        ch = self._require_channel(channel)
        self._scpi.write(f"CHAN {ch}")
        return ch

    def set_mode(self, mode: str, *, channel: int = 1) -> None:
        token = mode.upper()
        if token not in {"CC", "CV", "CP", "CR"}:
            raise EquipmentCapabilityError(f"unsupported static load mode {mode!r}")
        self._apply_channel(channel)
        self._scpi.write(f"MODE {token}H")

    def set_current(self, current: float, *, channel: int = 1) -> None:
        self._apply_channel(channel)
        self._scpi.write(f"CURR:STAT:L1 {current}")

    def set_voltage(self, voltage: float, *, channel: int = 1) -> None:
        self._apply_channel(channel)
        self._scpi.write(f"VOLT:STAT:L1 {voltage}")

    def set_power(self, power: float, *, channel: int = 1) -> None:
        self._apply_channel(channel)
        self._scpi.write(f"POW:STAT:L1 {power}")

    def set_resistance(self, resistance: float, *, channel: int = 1) -> None:
        self._apply_channel(channel)
        self._scpi.write(f"RES:STAT:L1 {resistance}")

    def engage(self, *, channel: int = 1) -> None:
        self._apply_channel(channel)
        self._scpi.write("LOAD ON")

    def disengage(self, *, channel: int = 1) -> None:
        self._apply_channel(channel)
        self._scpi.write("LOAD OFF")

    def measure_input_state(self, *, channel: int = 1) -> bool:
        self._apply_channel(channel)
        state = self._scpi.query("LOAD?").upper()
        if state not in {"ON", "OFF", "1", "0"}:
            raise EquipmentResponseError(f"invalid load state {state!r}")
        return state in {"ON", "1"}

    def measure_power_w(self, *, channel: int = 1) -> float:
        self._apply_channel(channel)
        return self._scpi.query_float("MEAS:POW?")

    def set_slew_rate(self, amps_per_s: float, *, channel: int = 1) -> None:
        if amps_per_s <= 0:
            raise ValueError("slew rate must be positive")
        self._apply_channel(channel)
        # Instrument uses A/us; public API uses A/s.
        value = amps_per_s / 1e6
        self._scpi.write(f"CURR:STAT:RISE {value}")
        self._scpi.write(f"CURR:STAT:FALL {value}")
