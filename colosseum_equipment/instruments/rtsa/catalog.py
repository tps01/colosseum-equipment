"""Catalog models from the programming-manual spreadsheet.

Each class inherits the generic driver. Inherited commands are sent as
generic SCPI and log one warning per model and command. The class
docstring is the manual link.
"""

from __future__ import annotations

from colosseum_equipment.instruments.registry import instrument_model
from colosseum_equipment.instruments.rtsa.generic import GenericRtsa


@instrument_model("rtsa", "rigol-rsa3030")
class RigolRsa3030(GenericRtsa):
    """Manual: https://www.rigolna.com/support/downloads/"""


@instrument_model("rtsa", "rigol-rsa3045")
class RigolRsa3045(GenericRtsa):
    """Manual: https://www.rigolna.com/support/downloads/"""


@instrument_model("rtsa", "rigol-rsa3065")
class RigolRsa3065(GenericRtsa):
    """Manual: https://www.rigolna.com/support/downloads/"""


@instrument_model("rtsa", "rigol-rsa5032")
class RigolRsa5032(GenericRtsa):
    """Manual: https://www.rigolna.com/support/downloads/"""


@instrument_model("rtsa", "rigol-rsa5065")
class RigolRsa5065(GenericRtsa):
    """Manual: https://www.rigolna.com/support/downloads/"""


@instrument_model("rtsa", "rigol-rsa800")
class RigolRsa800(GenericRtsa):
    """Manual: https://www.rigolna.com/support/downloads/"""


@instrument_model("rtsa", "rigol-rsa6000")
class RigolRsa6000(GenericRtsa):
    """Manual: https://www.rigolna.com/support/downloads/"""


@instrument_model("rtsa", "siglent-ssa3032x-r")
class SiglentSsa3032xR(GenericRtsa):
    """Manual: https://siglentna.com/resources/documents/spectrum-analyzers/"""


@instrument_model("rtsa", "siglent-ssa3075x-r")
class SiglentSsa3075xR(GenericRtsa):
    """Manual: https://siglentna.com/resources/documents/spectrum-analyzers/"""


@instrument_model("rtsa", "tektronix-rsa306")
class TektronixRsa306(GenericRtsa):
    """Manual: https://www.tek.com/en/manual/spectrum-analyzer/rsa306-rsa306b-and-rsa500a600a-programmer-manual-rsa306"""


@instrument_model("rtsa", "tektronix-rsa306b")
class TektronixRsa306b(GenericRtsa):
    """Manual: https://www.tek.com/en/manual/spectrum-analyzer/rsa306-rsa306b-and-rsa500a600a-programmer-manual-rsa306"""


@instrument_model("rtsa", "tektronix-rsa503a")
class TektronixRsa503a(GenericRtsa):
    """Manual: https://www.tek.com/en/manual/spectrum-analyzer/rsa306-rsa306b-and-rsa500a600a-programmer-manual-rsa306"""


@instrument_model("rtsa", "tektronix-rsa507a")
class TektronixRsa507a(GenericRtsa):
    """Manual: https://www.tek.com/en/manual/spectrum-analyzer/rsa306-rsa306b-and-rsa500a600a-programmer-manual-rsa306"""


@instrument_model("rtsa", "tektronix-rsa603a")
class TektronixRsa603a(GenericRtsa):
    """Manual: https://www.tek.com/en/manual/spectrum-analyzer/rsa306-rsa306b-and-rsa500a600a-programmer-manual-rsa306"""


@instrument_model("rtsa", "tektronix-rsa607a")
class TektronixRsa607a(GenericRtsa):
    """Manual: https://www.tek.com/en/manual/spectrum-analyzer/rsa306-rsa306b-and-rsa500a600a-programmer-manual-rsa306"""
