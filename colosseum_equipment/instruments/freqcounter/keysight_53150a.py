"""53150A frequency measurements with explicit front-panel input selection.

Manual: Keysight 53150-90014 Programming Guide, Measure subsystem table 4-2.
Gate time, period and timing operations from universal counters do not apply.
"""
from __future__ import annotations

import math

from colosseum_equipment.exceptions import EquipmentCapabilityError, EquipmentResponseError
from colosseum_equipment.instruments._capabilities import supported_commands
from colosseum_equipment.instruments.freqcounter.generic import GenericFreqCounter
from colosseum_equipment.instruments.registry import instrument_model


@instrument_model("freqcounter", "keysight-53150a")
@supported_commands("measure_frequency", "preset")
class Keysight53150A(GenericFreqCounter):
    """One-shot frequency in Hz; channel 1 is LF, channel 2 is microwave."""

    def measure_frequency(self, *, channel: int = 1) -> float:
        if channel not in (1, 2):
            raise EquipmentCapabilityError("53150A frequency inputs are channels 1 and 2")
        raw = self._scpi.query(f"MEAS:FREQ? (@{channel})")
        try:
            value = float(raw)
        except ValueError as exc:
            raise EquipmentResponseError(f"invalid frequency reading {raw!r}") from exc
        if not math.isfinite(value) or value <= 0 or value >= 9e37:
            raise EquipmentResponseError(f"invalid frequency reading {raw!r}")
        return value
