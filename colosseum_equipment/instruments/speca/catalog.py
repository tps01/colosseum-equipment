"""Catalog models from the programming-manual spreadsheet.

Each class inherits the generic driver. Inherited commands are sent as
generic SCPI and log one warning per model and command. The class
docstring is the manual link.
"""

from __future__ import annotations

from colosseum_equipment.instruments.registry import instrument_model
from colosseum_equipment.instruments.speca.generic import GenericSpecA
from colosseum_equipment.instruments.speca.rigol_dsa800 import RigolDsa800


@instrument_model("speca", "rigol-dsa815")
class RigolDsa815(RigolDsa800):
    """Manual: https://www.rigolna.com/support/downloads/"""


@instrument_model("speca", "rigol-dsa815-tg")
class RigolDsa815Tg(RigolDsa800):
    """Manual: https://www.rigolna.com/support/downloads/"""


@instrument_model("speca", "rigol-dsa832")
class RigolDsa832(RigolDsa800):
    """Manual: https://www.rigolna.com/support/downloads/"""


@instrument_model("speca", "rigol-dsa875")
class RigolDsa875(RigolDsa800):
    """Manual: https://www.rigolna.com/support/downloads/"""


@instrument_model("speca", "rigol-dsa800e")
class RigolDsa800e(RigolDsa800):
    """Manual: https://www.rigolna.com/support/downloads/"""


@instrument_model("speca", "rigol-dsa1000")
class RigolDsa1000(GenericSpecA):
    """Manual: https://www.rigolna.com/support/downloads/"""


@instrument_model("speca", "rigol-rsa3030")
class RigolRsa3030(GenericSpecA):
    """Manual: https://www.rigolna.com/support/downloads/"""


@instrument_model("speca", "rigol-rsa3045")
class RigolRsa3045(GenericSpecA):
    """Manual: https://www.rigolna.com/support/downloads/"""


@instrument_model("speca", "rigol-rsa5065")
class RigolRsa5065(GenericSpecA):
    """Manual: https://www.rigolna.com/support/downloads/"""


@instrument_model("speca", "siglent-ssa3021x")
class SiglentSsa3021x(GenericSpecA):
    """Manual: https://siglentna.com/resources/documents/spectrum-analyzers/"""


@instrument_model("speca", "siglent-ssa3032x")
class SiglentSsa3032x(GenericSpecA):
    """Manual: https://siglentna.com/resources/documents/spectrum-analyzers/"""


@instrument_model("speca", "siglent-ssa3021x-plus")
class SiglentSsa3021xPlus(GenericSpecA):
    """Manual: https://siglentna.com/resources/documents/spectrum-analyzers/"""


@instrument_model("speca", "siglent-ssa3032x-plus")
class SiglentSsa3032xPlus(GenericSpecA):
    """Manual: https://siglentna.com/resources/documents/spectrum-analyzers/"""


@instrument_model("speca", "siglent-ssa3075x-plus")
class SiglentSsa3075xPlus(GenericSpecA):
    """Manual: https://siglentna.com/resources/documents/spectrum-analyzers/"""


@instrument_model("speca", "siglent-ssa5000a")
class SiglentSsa5000a(GenericSpecA):
    """Manual: https://siglentna.com/resources/documents/spectrum-analyzers/"""
