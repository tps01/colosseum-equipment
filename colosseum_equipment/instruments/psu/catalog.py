"""Catalog models from the programming-manual spreadsheet.

Each class inherits the generic driver. Inherited commands are sent as
generic SCPI and log one warning per model and command. The class
docstring is the manual link.
"""

from __future__ import annotations

from colosseum_equipment.instruments.psu.generic import GenericPSU
from colosseum_equipment.instruments.psu.rigol_dp800 import RigolDp800
from colosseum_equipment.instruments.psu.siglent_spd_single import SiglentSpdSingle
from colosseum_equipment.instruments.registry import instrument_model


@instrument_model("psu", "rigol-dp811")
class RigolDp811(RigolDp800):
    """Manual: https://www.rigolna.com/products/dc-power-loads/dp800/"""


@instrument_model("psu", "rigol-dp813")
class RigolDp813(RigolDp800):
    """Manual: https://www.rigolna.com/products/dc-power-loads/dp800/"""


@instrument_model("psu", "rigol-dp821")
class RigolDp821(RigolDp800):
    """Manual: https://www.rigolna.com/products/dc-power-loads/dp800/"""


@instrument_model("psu", "rigol-dp821a")
class RigolDp821a(RigolDp800):
    """Manual: https://www.rigolna.com/products/dc-power-loads/dp800/"""


@instrument_model("psu", "rigol-dp822")
class RigolDp822(RigolDp800):
    """Manual: https://www.rigolna.com/products/dc-power-loads/dp800/"""


@instrument_model("psu", "rigol-dp831")
class RigolDp831(RigolDp800):
    """Manual: https://www.rigolna.com/products/dc-power-loads/dp800/"""


@instrument_model("psu", "rigol-dp832")
class RigolDp832(RigolDp800):
    """Manual: https://www.rigolna.com/products/dc-power-loads/dp800/"""


@instrument_model("psu", "rigol-dp832a")
class RigolDp832a(RigolDp800):
    """Manual: https://www.rigolna.com/products/dc-power-loads/dp800/"""


@instrument_model("psu", "rigol-dp711")
class RigolDp711(GenericPSU):
    """Manual: https://www.rigolna.com/support/downloads/"""


@instrument_model("psu", "rigol-dp712")
class RigolDp712(GenericPSU):
    """Manual: https://www.rigolna.com/support/downloads/"""


@instrument_model("psu", "rigol-dp932u")
class RigolDp932u(GenericPSU):
    """Manual: https://www.rigolna.com/support/downloads/"""


@instrument_model("psu", "rigol-dp932a")
class RigolDp932a(GenericPSU):
    """Manual: https://www.rigolna.com/support/downloads/"""


@instrument_model("psu", "rigol-dp2000")
class RigolDp2000(GenericPSU):
    """Manual: https://www.rigolna.com/support/downloads/"""


@instrument_model("psu", "rigol-dp1116a")
class RigolDp1116a(GenericPSU):
    """Manual: https://www.rigolna.com/support/downloads/"""


@instrument_model("psu", "siglent-spd3303x")
class SiglentSpd3303x(GenericPSU):
    """Manual: https://www.siglent.com/na/service-support/resource-center/?current=siglent-manual-download"""


@instrument_model("psu", "siglent-spd3303x-e")
class SiglentSpd3303xE(GenericPSU):
    """Manual: https://www.siglent.com/na/service-support/resource-center/?current=siglent-manual-download"""


@instrument_model("psu", "siglent-spd3303c")
class SiglentSpd3303c(GenericPSU):
    """Manual: https://www.siglent.com/na/service-support/resource-center/?current=siglent-manual-download"""


@instrument_model("psu", "siglent-spd1168x")
class SiglentSpd1168x(SiglentSpdSingle):
    """Manual: https://www.siglent.com/na/service-support/resource-center/?current=siglent-manual-download"""


@instrument_model("psu", "siglent-spd1305x")
class SiglentSpd1305x(SiglentSpdSingle):
    """Manual: https://www.siglent.com/na/service-support/resource-center/?current=siglent-manual-download"""


@instrument_model("psu", "keysight-n6705c")
class KeysightN6705c(GenericPSU):
    """Manual: https://www.keysight.com/us/en/assets/9018-04227/service-manuals/9018-04227.pdf"""
