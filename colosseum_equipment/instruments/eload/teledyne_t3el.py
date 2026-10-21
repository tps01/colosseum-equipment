"""T3EL150303P static operation; Teledyne T3EL programming manual, SCPI section."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from colosseum_equipment.exceptions import EquipmentCapabilityError
from colosseum_equipment.instruments._capabilities import supported_commands
from colosseum_equipment.instruments.eload.generic import GenericEload
from colosseum_equipment.instruments.registry import instrument_model

if TYPE_CHECKING:
    from colosseum_equipment.transports.base import Transport


@instrument_model("eload", "teledyne-t3el150303p")
@supported_commands(
    "set_mode", "set_current", "set_voltage", "set_power", "set_resistance", "engage",
    "disengage", "measure_voltage", "measure_current", "measure_power_w", "measure_input_state",
    "toggle_short", "preset",
)
class TeledyneT3el(GenericEload):
    """Single input, static CC/CV/CP/CR. Dynamic/list operation is excluded."""

    def __init__(self, transport: Transport, config: dict[str, Any]) -> None:
        if int(config.get("channels") or config.get("channel_count") or 1) != 1:
            raise EquipmentCapabilityError("T3EL150303P has one load input")
        super().__init__(transport, config)

    def set_mode(self, mode: str, *, channel: int = 1) -> None:
        self._require_channel(channel)
        token = {"CC": "CURR", "CV": "VOLT", "CP": "POW", "CR": "RES"}.get(mode.upper())
        if token is None:
            raise EquipmentCapabilityError("supported static modes are CC, CV, CP and CR")
        self._scpi.write(f"FUNC {token}")

    def measure_power_w(self, *, channel: int = 1) -> float:
        self._require_channel(channel)
        return self._scpi.query_float("MEAS:POW?")

    def toggle_short(self, enabled: bool, *, channel: int = 1) -> None:
        self._require_channel(channel)
        self._scpi.write(f"SHOR {'ON' if enabled else 'OFF'}")
