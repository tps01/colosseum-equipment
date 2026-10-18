"""Keysight / Agilent U2000-series USB power sensors (U2001A, etc.).

Commands per U2000 Series Programming Guide (U2000-90411): ``SENS:FREQ``,
``SENS:AVER:COUN``, ``FETCh?``, ``CAL:ZERO:AUTO ONCE``.
Operating guide: Keysight U2001A specs/manual PDF in repo docs.
Catalog: https://www.keysight.com/zz/en/assets/9018-01701/programming-guides/9018-01701.pdf
"""

from __future__ import annotations

from colosseum_equipment.exceptions import EquipmentCapabilityError
from colosseum_equipment.instruments.pwrmeter.generic import GenericPwrMeter
from colosseum_equipment.instruments.registry import instrument_model


@instrument_model(
    "pwrmeter",
    "keysight-u2001a",
    "keysight-u2000a",
    "keysight-u2000",
    "keysight-u2002a",
    "keysight-u2004a",
)
class KeysightU2000PwrMeter(GenericPwrMeter):
    def set_frequency(self, frequency_hz: float, *, channel: int = 1) -> None:
        self._require_channel(channel)
        self._scpi.write(f"SENS:FREQ {frequency_hz:.6f}")

    def set_averaging_count(self, count: int, *, channel: int = 1) -> None:
        self._require_channel(channel)
        self._scpi.write(f"SENS:AVER:COUN {int(count)}")

    def measure_power_dbm(self, *, channel: int = 1) -> float:
        self._require_channel(channel)
        return self._scpi.query_float("FETCh?")

    def measure_power_peak_dbm(self, *, channel: int = 1) -> float:
        self._require_channel(channel)
        raise EquipmentCapabilityError("U2000-series sensors measure average power, not envelope peak power")

    def measure_power_avg_dbm(self, *, channel: int = 1) -> float:
        self._require_channel(channel)
        return self._scpi.query_float("FETCh:AVER?")

    def zero_sensor(self, *, channel: int = 1) -> None:
        self._require_channel(channel)
        self._scpi.write("CAL:ZERO:AUTO ONCE")

    def calibrate(self, *, channel: int = 1) -> None:
        self._require_channel(channel)
        self._scpi.write("CAL:AUTO ONCE")
