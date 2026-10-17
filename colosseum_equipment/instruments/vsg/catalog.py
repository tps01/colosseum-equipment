"""Catalog models from the programming-manual spreadsheet.

Each class inherits the generic driver. Inherited commands are sent as
generic SCPI and log one warning per model and command. The class
docstring is the manual link.
"""

from __future__ import annotations

from colosseum_equipment.instruments.registry import instrument_model
from colosseum_equipment.instruments.vsg.generic import GenericVSG
from colosseum_equipment.instruments.vsg.rigol_dsg3136b import RigolDsg3136bFamily


@instrument_model("vsg", "rigol-dsg3030")
class RigolDsg3030(GenericVSG):
    """Manual: https://www.rigolna.com/support/downloads/"""


@instrument_model("vsg", "rigol-dsg3060")
class RigolDsg3060(GenericVSG):
    """Manual: https://www.rigolna.com/support/downloads/"""


@instrument_model("vsg", "rigol-dsg3060b")
class RigolDsg3060b(GenericVSG):
    """Manual: https://www.rigolna.com/support/downloads/"""


@instrument_model("vsg", "rigol-dsg3136b")
class RigolDsg3136b(RigolDsg3136bFamily):
    """Manual: https://www.rigolna.com/support/downloads/"""


@instrument_model("vsg", "rigol-dsg800")
class RigolDsg800(GenericVSG):
    """Manual: https://www.rigolna.com/support/downloads/"""


@instrument_model("vsg", "rigol-dsg5000")
class RigolDsg5000(GenericVSG):
    """Manual: https://www.rigolna.com/support/downloads/"""


@instrument_model("vsg", "siglent-ssg3000x")
class SiglentSsg3000x(GenericVSG):
    """Manual: https://www.siglent.com/na/service-support/resource-center/?current=siglent-manual-download"""


@instrument_model("vsg", "siglent-ssg5000x")
class SiglentSsg5000x(GenericVSG):
    """Manual: https://www.siglent.com/na/service-support/resource-center/?current=siglent-manual-download"""


@instrument_model("vsg", "siglent-ssg6000a")
class SiglentSsg6000a(GenericVSG):
    """Manual: https://www.siglent.com/na/service-support/resource-center/?current=siglent-manual-download"""


@instrument_model("vsg", "keysight-n5166b")
class KeysightN5166b(GenericVSG):
    """Manual: https://www.keysight.com/vn/en/support/N5182B/mxg-x-series-rf-vector-signal-generator-9-khz-6-ghz.html"""


@instrument_model("vsg", "keysight-n5171b")
class KeysightN5171b(GenericVSG):
    """Manual: https://www.keysight.com/vn/en/support/N5182B/mxg-x-series-rf-vector-signal-generator-9-khz-6-ghz.html"""


@instrument_model("vsg", "keysight-n5172b")
class KeysightN5172b(GenericVSG):
    """Manual: https://www.keysight.com/vn/en/support/N5182B/mxg-x-series-rf-vector-signal-generator-9-khz-6-ghz.html"""


@instrument_model("vsg", "keysight-n5181b")
class KeysightN5181b(GenericVSG):
    """Manual: https://www.keysight.com/vn/en/support/N5182B/mxg-x-series-rf-vector-signal-generator-9-khz-6-ghz.html"""


@instrument_model("vsg", "keysight-n5182b")
class KeysightN5182b(GenericVSG):
    """Manual: https://www.keysight.com/vn/en/support/N5182B/mxg-x-series-rf-vector-signal-generator-9-khz-6-ghz.html"""
