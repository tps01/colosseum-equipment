"""Catalog models from the programming-manual spreadsheet.

Each class inherits the generic driver. Inherited commands are sent as
generic SCPI and log one warning per model and command. The class
docstring is the manual link.
"""

from __future__ import annotations

from colosseum_equipment.instruments.asg.generic import GenericASG
from colosseum_equipment.instruments.asg.rigol_dg800 import RigolDg800
from colosseum_equipment.instruments.registry import instrument_model


@instrument_model("asg", "rigol-dg1022z")
class RigolDg1022z(GenericASG):
    """Manual: https://www.rigolna.com/support/downloads/"""


@instrument_model("asg", "rigol-dg1032z")
class RigolDg1032z(GenericASG):
    """Manual: https://www.rigolna.com/support/downloads/"""


@instrument_model("asg", "rigol-dg1062z")
class RigolDg1062z(GenericASG):
    """Manual: https://www.rigolna.com/support/downloads/"""


@instrument_model("asg", "rigol-dg4062")
class RigolDg4062(GenericASG):
    """Manual: https://www.rigolna.com/products/waveform-generators/dg4000/"""


@instrument_model("asg", "rigol-dg4102")
class RigolDg4102(GenericASG):
    """Manual: https://www.rigolna.com/products/waveform-generators/dg4000/"""


@instrument_model("asg", "rigol-dg4162")
class RigolDg4162(GenericASG):
    """Manual: https://www.rigolna.com/products/waveform-generators/dg4000/"""


@instrument_model("asg", "rigol-dg4202")
class RigolDg4202(GenericASG):
    """Manual: https://www.rigolna.com/products/waveform-generators/dg4000/"""


@instrument_model("asg", "rigol-dg811")
class RigolDg811(RigolDg800):
    """Manual: https://www.rigolna.com/support/downloads/"""


@instrument_model("asg", "rigol-dg812")
class RigolDg812(RigolDg800):
    """Manual: https://www.rigolna.com/support/downloads/"""


@instrument_model("asg", "rigol-dg821")
class RigolDg821(RigolDg800):
    """Manual: https://www.rigolna.com/support/downloads/"""


@instrument_model("asg", "rigol-dg822")
class RigolDg822(RigolDg800):
    """Manual: https://www.rigolna.com/support/downloads/"""


@instrument_model("asg", "rigol-dg952")
class RigolDg952(GenericASG):
    """Manual: https://www.rigolna.com/support/downloads/"""


@instrument_model("asg", "rigol-dg972")
class RigolDg972(GenericASG):
    """Manual: https://www.rigolna.com/support/downloads/"""


@instrument_model("asg", "rigol-dg2000")
class RigolDg2000(GenericASG):
    """Manual: https://www.rigolna.com/support/downloads/"""


@instrument_model("asg", "rigol-dg5000")
class RigolDg5000(GenericASG):
    """Manual: https://www.rigolna.com/support/downloads/"""


@instrument_model("asg", "rigol-dg6000")
class RigolDg6000(GenericASG):
    """Manual: https://www.rigolna.com/support/downloads/"""


@instrument_model("asg", "rigol-dg70000")
class RigolDg70000(GenericASG):
    """Manual: https://www.rigolna.com/support/downloads/"""


@instrument_model("asg", "siglent-sdg1032x")
class SiglentSdg1032x(GenericASG):
    """Manual: https://siglentna.com/resources/documents/waveform-generators/"""


@instrument_model("asg", "siglent-sdg1062x")
class SiglentSdg1062x(GenericASG):
    """Manual: https://siglentna.com/resources/documents/waveform-generators/"""


@instrument_model("asg", "siglent-sdg2042x")
class SiglentSdg2042x(GenericASG):
    """Manual: https://siglentna.com/resources/documents/waveform-generators/"""


@instrument_model("asg", "siglent-sdg2082x")
class SiglentSdg2082x(GenericASG):
    """Manual: https://siglentna.com/resources/documents/waveform-generators/"""


@instrument_model("asg", "siglent-sdg2122x")
class SiglentSdg2122x(GenericASG):
    """Manual: https://siglentna.com/resources/documents/waveform-generators/"""


@instrument_model("asg", "siglent-sdg6052x")
class SiglentSdg6052x(GenericASG):
    """Manual: https://siglentna.com/resources/documents/waveform-generators/"""


@instrument_model("asg", "siglent-sdg6032x")
class SiglentSdg6032x(GenericASG):
    """Manual: https://siglentna.com/resources/documents/waveform-generators/"""


@instrument_model("asg", "siglent-sdg3000x")
class SiglentSdg3000x(GenericASG):
    """Manual: https://www.siglent.com/na/service-support/resource-center/?current=siglent-manual-download"""


@instrument_model("asg", "siglent-sdg7000a")
class SiglentSdg7000a(GenericASG):
    """Manual: https://www.siglent.com/na/service-support/resource-center/?current=siglent-manual-download"""


@instrument_model("asg", "tektronix-afg31000")
class TektronixAfg31000(GenericASG):
    """Manual: https://www.tek.com/en/support/datasheets-manuals-software-downloads"""
