"""Catalog models from the programming-manual spreadsheet.

Each class inherits the generic driver. Inherited commands are sent as
generic SCPI and log one warning per model and command. The class
docstring is the manual link.
"""

from __future__ import annotations

from colosseum_equipment.instruments.dmm.generic import GenericDMM
from colosseum_equipment.instruments.dmm.keithley_dmm6500 import KeithleyDmm6500Family
from colosseum_equipment.instruments.dmm.keysight_34401a import Keysight34401A
from colosseum_equipment.instruments.registry import instrument_model


@instrument_model("dmm", "rigol-dm3058")
class RigolDm3058(GenericDMM):
    """Manual: https://www.rigolna.com/support/downloads/"""


@instrument_model("dmm", "rigol-dm3068")
class RigolDm3068(GenericDMM):
    """Manual: https://www.rigolna.com/support/downloads/"""


@instrument_model("dmm", "rigol-dm858")
class RigolDm858(GenericDMM):
    """Manual: https://www.rigolna.com/support/downloads/"""


@instrument_model("dmm", "siglent-sdm3045x")
class SiglentSdm3045x(GenericDMM):
    """Manual: https://www.siglent.com/na/service-support/resource-center/?current=siglent-manual-download"""


@instrument_model("dmm", "siglent-sdm3055")
class SiglentSdm3055(GenericDMM):
    """Manual: https://www.siglent.com/na/service-support/resource-center/?current=siglent-manual-download"""


@instrument_model("dmm", "siglent-sdm3065x")
class SiglentSdm3065x(GenericDMM):
    """Manual: https://www.siglent.com/na/service-support/resource-center/?current=siglent-manual-download"""


@instrument_model("dmm", "keysight-34401a")
class Keysight34401a(Keysight34401A):
    """Manual: https://www.keysight.com/us/en/assets/9018-01063/user-manuals/9018-01063.pdf"""


@instrument_model("dmm", "keysight-34460a")
class Keysight34460a(GenericDMM):
    """Manual: https://www.keysight.com/ie/en/support/34465A/digital-multimeter-6-5-digit-truevolt-dmm.html"""


@instrument_model("dmm", "keysight-34461a")
class Keysight34461a(GenericDMM):
    """Manual: https://www.keysight.com/ie/en/support/34465A/digital-multimeter-6-5-digit-truevolt-dmm.html"""


@instrument_model("dmm", "keysight-34465a")
class Keysight34465a(GenericDMM):
    """Manual: https://www.keysight.com/ie/en/support/34465A/digital-multimeter-6-5-digit-truevolt-dmm.html"""


@instrument_model("dmm", "keysight-34470a")
class Keysight34470a(GenericDMM):
    """Manual: https://www.keysight.com/ie/en/support/34465A/digital-multimeter-6-5-digit-truevolt-dmm.html"""


@instrument_model("dmm", "keithley-dmm6500")
class KeithleyDmm6500(KeithleyDmm6500Family):
    """Manual: https://www.tek.com/en/support/datasheets-manuals-software-downloads"""


@instrument_model("dmm", "keithley-dmm7510")
class KeithleyDmm7510(GenericDMM):
    """Manual: https://www.tek.com/en/support/datasheets-manuals-software-downloads"""
