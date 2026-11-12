"""Catalog models from the programming-manual spreadsheet.

Unverified inherited SCPI commands warn and send. The original B&K 8500
uses a binary protocol adapter; the class docstrings link vendor references.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from colosseum_equipment.exceptions import EquipmentCapabilityError
from colosseum_equipment.instruments._channels import resolve_channel_count
from colosseum_equipment.instruments.eload.generic import GenericEload
from colosseum_equipment.instruments.eload.bk8500 import Bk8500Load
from colosseum_equipment.instruments.registry import instrument_model

if TYPE_CHECKING:
    from colosseum_equipment.transports.base import Transport

# TODO: Validate rigol-dl3021 inherited commands against its vendor manual and hardware.

@instrument_model("eload", "rigol-dl3021")
class RigolDl3021(GenericEload):
    """Manual: https://www.rigolna.com/europe/products/dc-load/DL3000.html"""

# TODO: Validate rigol-dl3021a inherited commands against its vendor manual and hardware.

@instrument_model("eload", "rigol-dl3021a")
class RigolDl3021a(GenericEload):
    """Manual: https://www.rigolna.com/europe/products/dc-load/DL3000.html"""

# TODO: Validate rigol-dl3031 inherited commands against its vendor manual and hardware.

@instrument_model("eload", "rigol-dl3031")
class RigolDl3031(GenericEload):
    """Manual: https://www.rigolna.com/europe/products/dc-load/DL3000.html"""

# TODO: Validate rigol-dl3031a inherited commands against its vendor manual and hardware.

@instrument_model("eload", "rigol-dl3031a")
class RigolDl3031a(GenericEload):
    """Manual: https://www.rigolna.com/europe/products/dc-load/DL3000.html"""

# Mode/short verified against SDL1000X -E02B, section 3.3.1. Other inherited commands need review.

@instrument_model("eload", "siglent-sdl1020x")
class SiglentSdl1020x(GenericEload):
    """SDL1000X family static-mode and short controls (-E02B, pp.12?13).

    https://www.batronix.com/files/Siglent/Elektronische-Last/SDL1000X/SDL1000X-Programming_Guide.pdf
    """

    def __init__(self, transport: Transport, config: dict[str, Any]) -> None:
        if resolve_channel_count(config) != 1:
            raise EquipmentCapabilityError("SDL1000X has one input channel")
        super().__init__(transport, config)

    def set_mode(self, mode: str, *, channel: int = 1) -> None:
        self._require_channel(channel)
        modes = {
            "CC": "CURR", "CURR": "CURR", "CURRENT": "CURR",
            "CV": "VOLT", "VOLT": "VOLT", "VOLTAGE": "VOLT",
            "CP": "POW", "POW": "POW", "POWER": "POW",
            "CR": "RES", "RES": "RES", "RESISTANCE": "RES", "LED": "LED",
        }
        token = mode.strip().upper()
        if token not in modes:
            raise EquipmentCapabilityError(f"unsupported SDL1000X static mode {mode!r}")
        self._scpi.write(f"SOUR:FUNC {modes[token]}")

    def toggle_short(self, enabled: bool, *, channel: int = 1) -> None:
        self._require_channel(channel)
        self._scpi.write(f"SOUR:SHOR {'ON' if enabled else 'OFF'}")

# TODO: Validate siglent-sdl1020x-e inherited commands against its vendor manual and hardware.

@instrument_model("eload", "siglent-sdl1020x-e")
class SiglentSdl1020xE(SiglentSdl1020x):
    """Manual: https://www.siglent.com/na/service-support/resource-center/?current=siglent-manual-download"""

# TODO: Validate siglent-sdl1030x inherited commands against its vendor manual and hardware.

@instrument_model("eload", "siglent-sdl1030x")
class SiglentSdl1030x(SiglentSdl1020x):
    """Manual: https://www.siglent.com/na/service-support/resource-center/?current=siglent-manual-download"""

# TODO: Validate siglent-sdl1030x-e inherited commands against its vendor manual and hardware.

@instrument_model("eload", "siglent-sdl1030x-e")
class SiglentSdl1030xE(SiglentSdl1020x):
    """Manual: https://www.siglent.com/na/service-support/resource-center/?current=siglent-manual-download"""

# Native static protocol subset; hardware qualification remains outstanding.

@instrument_model("eload", "bk-8500")
class Bk8500(Bk8500Load):
    """Manual: https://www.bkprecision.com/knowledge/remote-communication/1/rs232-communication-instructions-for-85xx-series"""

# TODO: Validate bk-8600 inherited commands against its vendor manual and hardware.

@instrument_model("eload", "bk-8600")
class Bk8600(GenericEload):
    """Manual: https://www.bkprecision.com/"""
