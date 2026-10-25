"""Catalog models from the programming-manual spreadsheet.

Mini-Circuits RC-family ASCII switches reuse ``MiniCircuitsRcSwitch``.
ZTVX uses a PATH dialect not covered by SETA/SWPORT — refuse until implemented.
Vaunix LSW identities are registered in ``vaunix.py`` (SDK-only refuse).
"""

from __future__ import annotations

from colosseum_equipment.instruments._capabilities import supported_commands
from colosseum_equipment.instruments.registry import instrument_model
from colosseum_equipment.instruments.rfswitch.generic import GenericRfSwitch
from colosseum_equipment.instruments.rfswitch.minicircuits_rc import MiniCircuitsRcSwitch


@instrument_model(
    "rfswitch",
    "minicircuits-usb-switch",
    extra_optional=("path", "settle_s", "wait_settle_s"),
)
class MinicircuitsUsbSwitch(MiniCircuitsRcSwitch):
    """Manual: https://www.minicircuits.com/softwaredownload/Prog_Manual-2-Switch.pdf"""


@instrument_model(
    "rfswitch",
    "minicircuits-u2c",
    extra_optional=("path", "settle_s", "wait_settle_s"),
)
class MinicircuitsU2c(MiniCircuitsRcSwitch):
    """Manual: https://www.minicircuits.com/softwaredownload/Prog_Manual-2-Switch.pdf"""


@instrument_model(
    "rfswitch",
    "minicircuits-rcs",
    extra_optional=("path", "settle_s", "wait_settle_s"),
)
class MinicircuitsRcs(MiniCircuitsRcSwitch):
    """Manual: https://www.minicircuits.com/softwaredownload/Prog_Manual-2-Switch.pdf"""


@instrument_model(
    "rfswitch",
    "minicircuits-esb",
    extra_optional=("path", "settle_s", "wait_settle_s"),
)
class MinicircuitsEsb(MiniCircuitsRcSwitch):
    """Manual: https://www.minicircuits.com/softwaredownload/Prog_Manual-2-Switch.pdf"""


@instrument_model(
    "rfswitch",
    "minicircuits-ztvx",
    extra_optional=("path", "port", "settle_s", "wait_settle_s"),
    address="either",
)
@supported_commands()
class MinicircuitsZtvx(GenericRfSwitch):
    """ZT PATH dialect (:PATH:start:end); refuse ROUT:* inheritance until implemented.

    Manual: https://www.minicircuits.com/softwaredownload/Prog_Manual-ZT-Custom.pdf
    """
