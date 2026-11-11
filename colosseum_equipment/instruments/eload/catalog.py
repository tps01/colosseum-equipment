"""Catalog models from the programming-manual spreadsheet.

Each class inherits the generic driver. Inherited commands are sent as
generic SCPI and log one warning per model and command. The class
docstring is the manual link.
"""

from __future__ import annotations

from colosseum_equipment.instruments.eload.generic import GenericEload
from colosseum_equipment.instruments.registry import instrument_model

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

# TODO: Validate siglent-sdl1020x inherited commands against its vendor manual and hardware.

@instrument_model("eload", "siglent-sdl1020x")
class SiglentSdl1020x(GenericEload):
    """Manual: https://www.siglent.com/na/service-support/resource-center/?current=siglent-manual-download"""

# TODO: Validate siglent-sdl1020x-e inherited commands against its vendor manual and hardware.

@instrument_model("eload", "siglent-sdl1020x-e")
class SiglentSdl1020xE(GenericEload):
    """Manual: https://www.siglent.com/na/service-support/resource-center/?current=siglent-manual-download"""

# TODO: Validate siglent-sdl1030x inherited commands against its vendor manual and hardware.

@instrument_model("eload", "siglent-sdl1030x")
class SiglentSdl1030x(GenericEload):
    """Manual: https://www.siglent.com/na/service-support/resource-center/?current=siglent-manual-download"""

# TODO: Validate siglent-sdl1030x-e inherited commands against its vendor manual and hardware.

@instrument_model("eload", "siglent-sdl1030x-e")
class SiglentSdl1030xE(GenericEload):
    """Manual: https://www.siglent.com/na/service-support/resource-center/?current=siglent-manual-download"""

# TODO: Validate bk-8500 inherited commands against its vendor manual and hardware.

@instrument_model("eload", "bk-8500")
class Bk8500(GenericEload):
    """Manual: https://www.bkprecision.com/"""

# TODO: Validate bk-8600 inherited commands against its vendor manual and hardware.

@instrument_model("eload", "bk-8600")
class Bk8600(GenericEload):
    """Manual: https://www.bkprecision.com/"""
