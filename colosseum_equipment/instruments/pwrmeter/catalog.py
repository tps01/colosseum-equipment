"""Catalog models from the programming-manual spreadsheet.

Unverified inherited commands retain generic warning-and-send behavior.
E4418B/E4419B use native average-power commands in the SCPI personality.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from colosseum_equipment.exceptions import EquipmentCapabilityError
from colosseum_equipment.instruments._channels import resolve_channel_count
from colosseum_equipment.instruments.pwrmeter.generic import GenericPwrMeter
from colosseum_equipment.instruments.pwrmeter.inventory import AveragePowerMeter
from colosseum_equipment.instruments.registry import instrument_model

if TYPE_CHECKING:
    from colosseum_equipment.transports.base import Transport

# Manual-backed subset; hardware qualification remains outstanding.

@instrument_model("pwrmeter", "keysight-e4418b")
class KeysightE4418b(AveragePowerMeter):
    """Manual: https://www.keysight.com/us/en/assets/9018-01176/programming-guides/9018-01176.pdf"""

    _physical_channels = 1

    def __init__(self, transport: Transport, config: dict[str, Any]) -> None:
        count = resolve_channel_count(config, default=self._physical_channels)
        if not 1 <= count <= self._physical_channels:
            raise EquipmentCapabilityError(
                f"meter body has {self._physical_channels} physical sensor input(s)",
            )
        super().__init__(transport, {**config, "channels": count})

    def set_frequency(self, frequency_hz: float, *, channel: int = 1) -> None:
        ch = self._require_channel(channel)
        # E4418-90029, 9-37: command range, not the attached sensor's RF range.
        if not 1e3 <= frequency_hz <= 999.999e9:
            raise ValueError("frequency must be within 1 kHz..999.999 GHz")
        self._scpi.write(f"SENS{ch}:FREQ {frequency_hz:.6f}")

    def set_averaging_count(self, count: int, *, channel: int = 1) -> None:
        ch = self._require_channel(channel)
        if not 1 <= count <= 1024 or int(count) != count:
            raise ValueError("averaging count must be an integer within 1..1024")
        # Averaging and channel offsets are unavailable at 200 readings/s (9-54).
        self._scpi.write(f"SENS{ch}:SPE 20")
        # Setting COUN disables automatic selection and enables the filter (9-5).
        self._scpi.write(f"SENS{ch}:AVER:COUN {int(count)}")

    def set_offset_db(self, offset_db: float, *, channel: int = 1) -> None:
        ch = self._require_channel(channel)
        if not -100 <= offset_db <= 100:
            raise ValueError("offset must be within -100..100 dB")
        self._scpi.write(f"SENS{ch}:SPE 20")
        # LOSS2 compensates cable loss: a positive offset increases reported power.
        self._scpi.write(f"SENS{ch}:CORR:LOSS2 {offset_db:.3f}DB")

    def measure_power_dbm(self, *, channel: int = 1) -> float:
        ch = self._require_channel(channel)
        self._scpi.write(f"INIT{ch}:CONT OFF")
        self._scpi.write(f"TRIG{ch}:SOUR IMM")
        self._scpi.write(f"TRIG{ch}:DEL:AUTO ON")
        self._scpi.write(f"UNIT{ch}:POW DBM")
        self._scpi.write("FORM ASC")
        # READ aborts/initiates the explicit input, returns a fresh absolute result,
        # and preserves averaging. DEF placeholders preserve range/resolution.
        return self._result(f"READ{ch}:POW:AC? DEF,DEF,(@{ch})")

    def acquire(self, *, channel: int = 1) -> None:
        self.measure_power_dbm(channel=channel)

    def measure_power_avg_dbm(self, *, channel: int = 1) -> float:
        ch = self._require_channel(channel)
        self._scpi.write(f"UNIT{ch}:POW DBM")
        self._scpi.write("FORM ASC")
        return self._result(f"FETC{ch}:POW:AC? DEF,DEF,(@{ch})")

    def measure_power_peak_dbm(self, *, channel: int = 1) -> float:
        self._require_channel(channel)
        raise EquipmentCapabilityError("E4418B/E4419B do not measure envelope peak power")

    def zero_sensor(self, *, channel: int = 1) -> None:
        ch = self._require_channel(channel)
        self._scpi.write(f"CAL{ch}:ZERO:AUTO ONCE")
        self._wait()

    def calibrate(self, *, channel: int = 1) -> None:
        ch = self._require_channel(channel)
        self._scpi.write(f"CAL{ch}:AUTO ONCE")
        self._wait()


@instrument_model("pwrmeter", "keysight-e4419b")
class KeysightE4419b(KeysightE4418b):
    """Manual: https://www.keysight.com/us/en/assets/9018-01176/programming-guides/9018-01176.pdf"""

    _physical_channels = 2

# TODO: Validate keysight-n1913a inherited commands against its vendor manual and hardware.

@instrument_model("pwrmeter", "keysight-n1913a")
class KeysightN1913a(GenericPwrMeter):
    """Manual: https://www.keysight.com/be/en/support/N1913A/epm-series-single-channel-power-meter.html"""

# TODO: Validate keysight-n1914a inherited commands against its vendor manual and hardware.

@instrument_model("pwrmeter", "keysight-n1914a")
class KeysightN1914a(GenericPwrMeter):
    """Manual: https://www.keysight.com/be/en/support/N1913A/epm-series-single-channel-power-meter.html"""
