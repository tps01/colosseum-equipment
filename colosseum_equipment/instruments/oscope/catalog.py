"""Catalog models from the programming-manual spreadsheet.

Each class inherits the generic driver. Inherited commands are sent as
generic SCPI and log one warning per model and command. The class
docstring is the manual link.
"""

from __future__ import annotations

from colosseum_equipment.instruments.oscope.generic import GenericOscope
from colosseum_equipment.instruments.oscope.rigol_dho import RigolDho
from colosseum_equipment.instruments.oscope.siglent_sds1000x_e import SiglentSds1000xE
from colosseum_equipment.instruments.registry import instrument_model


@instrument_model("oscope", "rigol-ds1054z")
class RigolDs1054z(GenericOscope):
    """Manual: https://www.rigolna.com/support/downloads/"""


@instrument_model("oscope", "rigol-ds1074z")
class RigolDs1074z(GenericOscope):
    """Manual: https://www.rigolna.com/support/downloads/"""


@instrument_model("oscope", "rigol-ds1104z")
class RigolDs1104z(GenericOscope):
    """Manual: https://www.rigolna.com/support/downloads/"""


@instrument_model("oscope", "rigol-mso1074z")
class RigolMso1074z(GenericOscope):
    """Manual: https://www.rigolna.com/support/downloads/"""


@instrument_model("oscope", "rigol-mso1104z")
class RigolMso1104z(GenericOscope):
    """Manual: https://www.rigolna.com/support/downloads/"""


@instrument_model("oscope", "rigol-dho802")
class RigolDho802(RigolDho):
    """Manual: https://www.rigolna.com/support/downloads/"""


@instrument_model("oscope", "rigol-dho804")
class RigolDho804(RigolDho):
    """Manual: https://www.rigolna.com/support/downloads/"""


@instrument_model("oscope", "rigol-dho914")
class RigolDho914(RigolDho):
    """Manual: https://www.rigolna.com/support/downloads/"""


@instrument_model("oscope", "rigol-dho924")
class RigolDho924(RigolDho):
    """Manual: https://www.rigolna.com/support/downloads/"""


@instrument_model("oscope", "rigol-dho1074")
class RigolDho1074(RigolDho):
    """Manual: https://www.rigolna.com/support/downloads/"""


@instrument_model("oscope", "rigol-dho1104")
class RigolDho1104(RigolDho):
    """Manual: https://www.rigolna.com/support/downloads/"""


@instrument_model("oscope", "rigol-ds2000a")
class RigolDs2000a(GenericOscope):
    """Manual: https://www.rigolna.com/support/downloads/"""


@instrument_model("oscope", "rigol-ds4000")
class RigolDs4000(GenericOscope):
    """Manual: https://www.rigolna.com/support/downloads/"""


@instrument_model("oscope", "rigol-mso5000")
class RigolMso5000(GenericOscope):
    """Manual: https://www.rigolna.com/support/downloads/"""


@instrument_model("oscope", "rigol-mso8000")
class RigolMso8000(GenericOscope):
    """Manual: https://www.rigolna.com/support/downloads/"""


@instrument_model("oscope", "rigol-ds70000")
class RigolDs70000(GenericOscope):
    """Manual: https://www.rigolna.com/support/downloads/"""


@instrument_model("oscope", "siglent-sds1102x-e")
class SiglentSds1102xE(SiglentSds1000xE):
    """Manual: https://siglentna.com/resources/documents/digital-oscilloscopes/"""


@instrument_model("oscope", "siglent-sds1104x-e")
class SiglentSds1104xE(SiglentSds1000xE):
    """Manual: https://siglentna.com/resources/documents/digital-oscilloscopes/"""


@instrument_model("oscope", "siglent-sds1202x-e")
class SiglentSds1202xE(SiglentSds1000xE):
    """Manual: https://siglentna.com/resources/documents/digital-oscilloscopes/"""


@instrument_model("oscope", "siglent-sds1204x-e")
class SiglentSds1204xE(SiglentSds1000xE):
    """Manual: https://siglentna.com/resources/documents/digital-oscilloscopes/"""


@instrument_model("oscope", "siglent-sds2000x-plus")
class SiglentSds2000xPlus(GenericOscope):
    """Manual: https://www.siglent.com/na/service-support/resource-center/?current=siglent-manual-download"""


@instrument_model("oscope", "siglent-sds5000x")
class SiglentSds5000x(GenericOscope):
    """Manual: https://www.siglent.com/na/service-support/resource-center/?current=siglent-manual-download"""


@instrument_model("oscope", "siglent-sds6000a")
class SiglentSds6000a(GenericOscope):
    """Manual: https://www.siglent.com/na/service-support/resource-center/?current=siglent-manual-download"""


@instrument_model("oscope", "siglent-sds7000a")
class SiglentSds7000a(GenericOscope):
    """Manual: https://www.siglent.com/na/service-support/resource-center/?current=siglent-manual-download"""


@instrument_model("oscope", "siglent-sds800x-hd")
class SiglentSds800xHd(GenericOscope):
    """Manual: https://www.siglent.com/na/service-support/resource-center/?current=siglent-manual-download"""
