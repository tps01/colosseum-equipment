"""Teledyne LeCroy T3DSO1000/2000 oscilloscope (SCPI).

Manual: T3DSO1000/2000 Programming Guide — ``TDIV``, ``PACU``, ``PAVA?``, ``ARM``.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from colosseum_equipment.exceptions import EquipmentCapabilityError
from colosseum_equipment.instruments.oscope.generic import GenericOscope
from colosseum_equipment.instruments.registry import instrument_model

if TYPE_CHECKING:
    from colosseum_equipment.transports.base import Transport


def _seconds_to_tdiv(seconds_per_div: float) -> str:
    if seconds_per_div >= 1:
        value = seconds_per_div
        suffix = "S"
    elif seconds_per_div >= 1e-3:
        value = seconds_per_div * 1e3
        suffix = "MS"
    elif seconds_per_div >= 1e-6:
        value = seconds_per_div * 1e6
        suffix = "US"
    else:
        value = seconds_per_div * 1e9
        suffix = "NS"
    if value == int(value):
        return f"{int(value)}{suffix}"
    return f"{value:g}{suffix}"


@instrument_model("oscope", "tektronix-t3dso2000")
class TekT3dso2000Oscope(GenericOscope):
    _model = "tektronix-t3dso2000"

    def __init__(self, transport: Transport, config: dict[str, Any]) -> None:
        super().__init__(transport, config)
        self._meas_slot = int(config.get("measurement_slot", 1))

    def set_timebase_scale(self, seconds_per_div: float) -> None:
        self._scpi.write(f"TDIV {_seconds_to_tdiv(seconds_per_div)}")

    def single_acquire(self) -> None:
        self._scpi.write("ARM")

    def configure_vpp(self, channel: int = 1) -> None:
        self._require_channel(channel)
        self._scpi.write(f"PACU PKPK,C{channel}")

    def measure_vpp(self, channel: int = 1) -> float:
        self._require_channel(channel)
        response = self._scpi._setting_value(f"PAVA? CUST{self._meas_slot}")
        match = re.search(rf"CUST{self._meas_slot}:C{channel},PKPK,([0-9.Ee+-]+)", response)
        if not match:
            raise EquipmentCapabilityError(
                f"custom slot is not Vpp on channel {channel}; call configure_vpp(channel=...) first: {response!r}",
            )
        return float(match.group(1))
