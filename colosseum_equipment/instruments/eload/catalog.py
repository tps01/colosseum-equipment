"""Catalog models from the programming-manual spreadsheet.

Unverified inherited SCPI commands warn and send. The original B&K 8500
uses a binary protocol adapter; the class docstrings link vendor references.
"""

from __future__ import annotations

from colosseum_equipment.instruments.eload.bk8500 import Bk8500Load
from colosseum_equipment.instruments.eload.generic import GenericEload
from colosseum_equipment.instruments.eload.static_scpi import RigolDl3000, SiglentSdl1000x
from colosseum_equipment.instruments.registry import instrument_model


@instrument_model("eload", "rigol-dl3021")
class RigolDl3021(RigolDl3000):
    """RIGOL DL3000 Programming Guide, chapter 2."""


@instrument_model("eload", "rigol-dl3021a")
class RigolDl3021a(RigolDl3000):
    """RIGOL DL3000 Programming Guide, chapter 2."""


@instrument_model("eload", "rigol-dl3031")
class RigolDl3031(RigolDl3000):
    """RIGOL DL3000 Programming Guide, chapter 2."""


@instrument_model("eload", "rigol-dl3031a")
class RigolDl3031a(RigolDl3000):
    """RIGOL DL3000 Programming Guide, chapter 2."""


@instrument_model("eload", "siglent-sdl1020x")
class SiglentSdl1020x(SiglentSdl1000x):
    """SIGLENT SDL1000X Programming Guide E02B, sections 3.2 and 3.3."""


@instrument_model("eload", "siglent-sdl1020x-e")
class SiglentSdl1020xE(SiglentSdl1000x):
    """SIGLENT SDL1000X Programming Guide E02B, sections 3.2 and 3.3."""


@instrument_model("eload", "siglent-sdl1030x")
class SiglentSdl1030x(SiglentSdl1000x):
    """SIGLENT SDL1000X Programming Guide E02B, sections 3.2 and 3.3."""


@instrument_model("eload", "siglent-sdl1030x-e")
class SiglentSdl1030xE(SiglentSdl1000x):
    """SIGLENT SDL1000X Programming Guide E02B, sections 3.2 and 3.3."""


# Native static protocol subset; hardware qualification remains outstanding.

@instrument_model("eload", "bk-8500")
class Bk8500(Bk8500Load):
    """Manual: https://www.bkprecision.com/knowledge/remote-communication/1/rs232-communication-instructions-for-85xx-series"""

# TODO: Validate bk-8600 inherited commands against its vendor manual and hardware.

@instrument_model("eload", "bk-8600")
class Bk8600(GenericEload):
    """Manual: https://www.bkprecision.com/"""
