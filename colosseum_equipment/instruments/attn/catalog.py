"""Catalog models from the programming-manual spreadsheet.

Mini-Circuits Prog_Manual-6 identities are registered in ``minicircuits.py``.
Vaunix LDA identities are registered in ``vaunix.py`` (SDK-only refuse).
"""

from __future__ import annotations

from colosseum_equipment.instruments.attn.generic import GenericAttn
from colosseum_equipment.instruments.registry import instrument_model


@instrument_model("attn", "minicircuits-rcm-ztm")
class MinicircuitsRcmZtm(GenericAttn):
    """Manual: https://www.minicircuits.com/softwaredownload/Prog_Manual-Modular_ZTM_RCM.pdf"""
