"""Catalog models from the programming-manual spreadsheet.

Each class inherits the generic driver. Inherited commands are sent as
generic SCPI and log one warning per model and command. The class
docstring is the manual link.
"""

from __future__ import annotations

from colosseum_equipment.instruments.registry import instrument_model
from colosseum_equipment.instruments.vna.generic import GenericVna


@instrument_model("vna", "siglent-sna5000a")
class SiglentSna5000a(GenericVna):
    """Manual: https://siglentna.com/wp-content/uploads/dlm_uploads/2022/11/SNA5000A_ProgrammingGuide_PG09050_E03.pdf"""


@instrument_model("vna", "siglent-sna6000a")
class SiglentSna6000a(GenericVna):
    """Manual: https://www.siglent.com/na/service-support/resource-center/?current=siglent-manual-download"""


@instrument_model("vna", "siglent-sva1000x")
class SiglentSva1000x(GenericVna):
    """Manual: https://www.siglent.com/na/service-support/resource-center/?current=siglent-manual-download"""


@instrument_model("vna", "keysight-e5071c")
class KeysightE5071c(GenericVna):
    """Manual: https://helpfiles.keysight.com/csg/e5071c/using_this_help.htm"""


@instrument_model("vna", "rigol-dna6000")
class RigolDna6000(GenericVna):
    """Manual: https://www.rigolna.com/support/downloads/"""


@instrument_model("vna", "rigol-dna6000-r")
class RigolDna6000R(GenericVna):
    """Manual: https://www.rigolna.com/support/downloads/"""
