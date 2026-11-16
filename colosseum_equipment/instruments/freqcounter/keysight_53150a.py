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
@supported_commands("measure_frequency", "preset", "initiate")
class Keysight53150A(GenericFreqCounter):
    """One-shot frequency in Hz; channel 1 is LF, channel 2 is microwave."""

    _last_frequency: tuple[int, float] | None = None

    def preset(self) -> None:
        self._last_frequency = None
        super().preset()

    def initiate(self, *, channel: int = 1) -> None:
        if channel not in (1, 2):
            raise EquipmentCapabilityError("53150A frequency inputs are channels 1 and 2")
        self._last_frequency = None
        raw = self._scpi.query(f"MEAS:FREQ? (@{channel})")
        try:
            value = float(raw)
        except ValueError as exc:
            raise EquipmentResponseError(f"invalid frequency reading {raw!r}") from exc
        if not math.isfinite(value) or not 0 < value < 9e37:
            raise EquipmentResponseError(f"invalid frequency reading {raw!r}")
        self._last_frequency = (channel, value)

    def measure_frequency(self, *, channel: int = 1) -> float:
        result = self._last_frequency
        if result is None or result[0] != channel:
            raise EquipmentCapabilityError("call initiate(channel=...) before fetching a 53150A result")
        return float(result[1])
