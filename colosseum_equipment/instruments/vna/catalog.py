"""Catalog models from the programming-manual spreadsheet.

Each class inherits the generic driver. Inherited commands are sent as
generic SCPI and log one warning per model and command. The class
docstring is the manual link.
"""

from __future__ import annotations

from colosseum_equipment.instruments.registry import instrument_model
from colosseum_equipment.instruments.vna.generic import GenericVna
from colosseum_equipment.instruments.vna.inventory import EnaVna, PairedTraceVna

# TODO: Validate siglent-sna5000a inherited commands against its vendor manual and hardware.

@instrument_model("vna", "siglent-sna5000a")
class SiglentSna5000a(PairedTraceVna):
    """Manual: https://siglentna.com/wp-content/uploads/dlm_uploads/2022/11/SNA5000A_ProgrammingGuide_PG09050_E03.pdf"""

    # PG09050_E01A: ASCII data arrays, selected-trace pairs, native single trigger.
    _ascii_command = ""
    _smoothing_limits = (0.0, 100.0)
    _trace_limit = 200
    _channel_limit = 200

    def _sweep_once(self) -> None:
        self._scpi.write("TRIG:SOUR INT")
        super()._sweep_once()

# TODO: Validate siglent-sna6000a inherited commands against its vendor manual and hardware.

@instrument_model("vna", "siglent-sna6000a")
class SiglentSna6000a(GenericVna):
    """Manual: https://www.siglent.com/na/service-support/resource-center/?current=siglent-manual-download"""

# TODO: Validate siglent-sva1000x inherited commands against its vendor manual and hardware.

@instrument_model("vna", "siglent-sva1000x")
class SiglentSva1000x(GenericVna):
    """Manual: https://www.siglent.com/na/service-support/resource-center/?current=siglent-manual-download"""

# TODO: Validate keysight-e5071c inherited commands against its vendor manual and hardware.

@instrument_model("vna", "keysight-e5071c")
class KeysightE5071c(EnaVna):
    """Manual: https://helpfiles.keysight.com/csg/e5071c/using_this_help.htm"""

# TODO: Validate rigol-dna6000 inherited commands against its vendor manual and hardware.

@instrument_model("vna", "rigol-dna6000")
class RigolDna6000(GenericVna):
    """Manual: https://www.rigolna.com/support/downloads/"""

# TODO: Validate rigol-dna6000-r inherited commands against its vendor manual and hardware.

@instrument_model("vna", "rigol-dna6000-r")
class RigolDna6000R(GenericVna):
    """Manual: https://www.rigolna.com/support/downloads/"""
