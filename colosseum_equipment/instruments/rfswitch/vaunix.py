"""Vaunix Lab Brick LSW switches — vendor SDK/DLL only, not SCPI.

Manual / SDK: https://vaunix.com/support/
"""

from __future__ import annotations

from colosseum_equipment.instruments._capabilities import supported_commands
from colosseum_equipment.instruments.registry import instrument_model
from colosseum_equipment.instruments.rfswitch.generic import GenericRfSwitch


@instrument_model(
    "rfswitch",
    "vaunix-lsw-802pdt",
    "vaunix-lsw-203pdt",
    extra_optional=("path", "port", "settle_s", "wait_settle_s"),
    address="either",
)
@supported_commands()
class VaunixLswSwitch(GenericRfSwitch):
    """Registered for inventory identity; remote ops refuse (SDK/DLL required)."""
