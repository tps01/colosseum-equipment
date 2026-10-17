"""Catalog models from the programming-manual spreadsheet.

Each class inherits the generic driver. Inherited commands are sent as
generic SCPI and log one warning per model and command. The class
docstring is the manual link.
"""

from __future__ import annotations

from colosseum_equipment.instruments.attn.generic import GenericAttn
from colosseum_equipment.instruments.registry import instrument_model


@instrument_model("attn", "minicircuits-rudat")
class MinicircuitsRudat(GenericAttn):
    """Manual: https://www.minicircuits.com/softwaredownload/Prog_Manual-6-Programmable_Attenuator.pdf"""


@instrument_model("attn", "minicircuits-rcdat")
class MinicircuitsRcdat(GenericAttn):
    """Manual: https://www.minicircuits.com/softwaredownload/Prog_Manual-6-Programmable_Attenuator.pdf"""


@instrument_model("attn", "minicircuits-rc4dat")
class MinicircuitsRc4dat(GenericAttn):
    """Manual: https://www.minicircuits.com/softwaredownload/Prog_Manual-6-Programmable_Attenuator.pdf"""


@instrument_model("attn", "minicircuits-rc8dat")
class MinicircuitsRc8dat(GenericAttn):
    """Manual: https://www.minicircuits.com/softwaredownload/Prog_Manual-6-Programmable_Attenuator.pdf"""


@instrument_model("attn", "minicircuits-zvva")
class MinicircuitsZvva(GenericAttn):
    """Manual: https://www.minicircuits.com/softwaredownload/Prog_Manual-6-Programmable_Attenuator.pdf"""


@instrument_model("attn", "minicircuits-rcm-ztm")
class MinicircuitsRcmZtm(GenericAttn):
    """Manual: https://www.minicircuits.com/softwaredownload/Prog_Manual-Modular_ZTM_RCM.pdf"""


@instrument_model("attn", "vaunix-lda-302p-1")
class VaunixLda302p1(GenericAttn):
    """Manual: https://vaunix.com/digital-attenuators/"""


@instrument_model("attn", "vaunix-lda-302p-h")
class VaunixLda302pH(GenericAttn):
    """Manual: https://vaunix.com/digital-attenuators/"""


@instrument_model("attn", "vaunix-lda")
class VaunixLda(GenericAttn):
    """Manual: https://vaunix.com/digital-attenuators/"""
