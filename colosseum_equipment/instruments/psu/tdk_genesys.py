from __future__ import annotations

from typing import TYPE_CHECKING, Any

from colosseum_equipment.instruments.psu.generic import GenericPSU
from colosseum_equipment.instruments.registry import instrument_model

if TYPE_CHECKING:
    from colosseum_equipment.transports.base import Transport


@instrument_model("psu", "tdk-genesys")
class TdkGenesysPSU(GenericPSU):
    """Reference driver for TDK-Lambda Genesys."""

    def __init__(self, transport: Transport, config: dict[str, Any]) -> None:
        super().__init__(transport, config)
        if "ovp" in config:
            self.set_ovp_v(float(config["ovp"]))
        if "ocp" in config:
            self.set_ocp_a(float(config["ocp"]))
