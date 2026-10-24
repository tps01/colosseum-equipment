"""Vaunix Lab Brick LDA attenuators — vendor SDK/DLL only, not SCPI.

Manual / SDK: https://vaunix.com/digital-attenuators/
Same disposition as LadyBug / NRP-Z: do not invent SCPI for DLL devices.
"""

from __future__ import annotations

from colosseum_equipment.instruments._capabilities import supported_commands
from colosseum_equipment.instruments.attn.generic import GenericAttn
from colosseum_equipment.instruments.registry import instrument_model


@instrument_model(
    "attn",
    "vaunix-lda",
    "vaunix-lda-302p-1",
    "vaunix-lda-302p-h",
    extra_optional=(
        "attenuation_db",
        "channel",
        "path",
        "port",
        "min_attenuation_db",
        "max_attenuation_db",
        "step_db",
        "settle_s",
    ),
    address="either",
)
@supported_commands()
class VaunixLdaAttn(GenericAttn):
    """Registered for inventory identity; remote ops refuse (SDK/DLL required)."""
