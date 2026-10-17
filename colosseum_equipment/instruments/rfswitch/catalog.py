"""Catalog models from the programming-manual spreadsheet.

Each class inherits the generic driver. Inherited commands are sent as
generic SCPI and log one warning per model and command. The class
docstring is the manual link.
"""

from __future__ import annotations

from colosseum_equipment.instruments.registry import instrument_model
from colosseum_equipment.instruments.rfswitch.generic import GenericRfSwitch


@instrument_model("rfswitch", "minicircuits-usb-switch")
class MinicircuitsUsbSwitch(GenericRfSwitch):
    """Manual: https://www.minicircuits.com/softwaredownload/solidstate.html"""


@instrument_model("rfswitch", "minicircuits-u2c")
class MinicircuitsU2c(GenericRfSwitch):
    """Manual: https://www.minicircuits.com/softwaredownload/solidstate.html"""


@instrument_model("rfswitch", "minicircuits-rcs")
class MinicircuitsRcs(GenericRfSwitch):
    """Manual: https://www.minicircuits.com/softwaredownload/solidstate.html"""


@instrument_model("rfswitch", "minicircuits-esb")
class MinicircuitsEsb(GenericRfSwitch):
    """Manual: https://www.minicircuits.com/softwaredownload/solidstate.html"""


@instrument_model("rfswitch", "minicircuits-ztvx")
class MinicircuitsZtvx(GenericRfSwitch):
    """Manual: https://www.minicircuits.com/softwaredownload/ztvx.html"""


@instrument_model("rfswitch", "vaunix-lsw-802pdt")
class VaunixLsw802pdt(GenericRfSwitch):
    """Manual: https://vaunix.com/support/"""


@instrument_model("rfswitch", "vaunix-lsw-203pdt")
class VaunixLsw203pdt(GenericRfSwitch):
    """Manual: https://vaunix.com/support/"""
