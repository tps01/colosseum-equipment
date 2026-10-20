"""PLA/PLW programming guide, MODE / INPUT / CURRENT / MEASURE subsystems.

https://www.manualsdir.com/manuals/754240/ametek-pla-plw-programming-manual.html
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from colosseum_equipment.exceptions import EquipmentCapabilityError
from colosseum_equipment.instruments._capabilities import supported_commands
from colosseum_equipment.instruments.eload.generic import GenericEload
from colosseum_equipment.instruments.registry import instrument_model

if TYPE_CHECKING:
    from colosseum_equipment.transports.base import Transport


@instrument_model("eload", "ametek-pla4k-600-240")
@supported_commands(
    "set_mode", "set_current", "set_voltage", "set_power", "set_resistance", "engage", "disengage",
    "measure_voltage", "measure_current", "measure_input_state", "preset",
)
class AmetekPla(GenericEload):
    """Single-input static modes. Select SCPI syntax on the instrument first.

    Legacy AMREL personality, slew-time semantics, stepping and protection
    clearing that can restore an input are excluded from this subset.
    """

    def __init__(self, transport: Transport, config: dict[str, Any]) -> None:
        if int(config.get("channels") or config.get("channel_count") or 1) != 1:
            raise EquipmentCapabilityError("PLA4K has one load input")
        super().__init__(transport, config)

    def set_mode(self, mode: str, *, channel: int = 1) -> None:
        self._require_channel(channel)
        token = mode.upper()
        if token not in {"CC", "CV", "CP", "CR"}:
            raise EquipmentCapabilityError("PLA static modes are CC, CV, CP and CR")
        self._scpi.write(f"MODE {token}")
