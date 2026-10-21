"""Average RF power on EPM-P/P-Series bodies, USB thermal and NRP sensors.

Attached E/N-series sensors are configured through a meter body, not registered
as separately addressable instruments. Envelope peak/gating is not implemented.
Manuals: E4416/E4417 programming guide; N1911A/12A 9018-05085;
U8480 Series programming guide; R&S NRPxxS(N) operating manual.
"""
from __future__ import annotations

import math
import re
from typing import TYPE_CHECKING, Any

from colosseum_equipment.exceptions import EquipmentCapabilityError, EquipmentResponseError
from colosseum_equipment.instruments._capabilities import supported_commands
from colosseum_equipment.instruments.pwrmeter.generic import GenericPwrMeter
from colosseum_equipment.instruments.registry import instrument_model

if TYPE_CHECKING:
    from colosseum_equipment.transports.base import Transport

_AVERAGE = (
    "set_frequency", "set_averaging_count", "acquire", "measure_power", "measure_power_dbm",
    "measure_power_w", "measure_power_avg_dbm",
)


class AveragePowerMeter(GenericPwrMeter):
    """Scalar result validation; immediate power read is fresh, average fetch is not."""

    def _result(self, query: str) -> float:
        raw = self._scpi.query(query)
        try:
            value = float(raw)
        except ValueError as exc:
            raise EquipmentResponseError(f"expected one power reading, received {raw!r}") from exc
        if not math.isfinite(value) or abs(value) >= 9e37:
            raise EquipmentResponseError(f"overload/invalid power reading {raw!r}")
        return value

    def _wait(self) -> None:
        if self._scpi.query("*OPC?") != "1":
            raise EquipmentResponseError("power acquisition did not complete")

    def measure_power_dbm(self, *, channel: int = 1) -> float:
        self.acquire(channel=channel)
        return self.measure_power_avg_dbm(channel=channel)


@instrument_model("pwrmeter", "keysight-e4417a", "keysight-n1912a")
@supported_commands(*_AVERAGE, "zero_sensor", "calibrate")
class KeysightDualPowerMeter(AveragePowerMeter):
    """Physical input 1/2 maps explicitly to calculation 1/2, average feed only."""

    def __init__(self, transport: Transport, config: dict[str, Any]) -> None:
        count = int(config.get("channels") or 2)
        if count not in (1, 2):
            raise EquipmentCapabilityError("meter body has two physical sensor inputs")
        super().__init__(transport, {**config, "channels": count})
        for ch in range(1, count + 1):
            self._scpi.write(f'CALC{ch}:MATH:EXPR "(SENS{ch})"')
            self._scpi.write(f'CALC{ch}:FEED1 "POW:AVER"')
            self._scpi.write(f"CALC{ch}:REL:STAT OFF")
            self._scpi.write(f"CALC{ch}:GAIN:STAT OFF")
            self._scpi.write(f"UNIT{ch}:POW DBM")

    def set_frequency(self, frequency_hz: float, *, channel: int = 1) -> None:
        ch = self._require_channel(channel)
        self._scpi.write(f"SENS{ch}:FREQ {frequency_hz:.6f}")

    def set_averaging_count(self, count: int, *, channel: int = 1) -> None:
        ch = self._require_channel(channel)
        if count < 1:
            raise ValueError("averaging count must be positive")
        self._scpi.write(f"SENS{ch}:AVER:COUN:AUTO OFF")
        self._scpi.write(f"SENS{ch}:AVER:COUN {count}")
        self._scpi.write(f"SENS{ch}:AVER:STAT ON")

    def acquire(self, *, channel: int = 1) -> None:
        ch = self._require_channel(channel)
        self._scpi.write(f"INIT{ch}:CONT OFF")
        self._scpi.write(f"TRIG{ch}:SOUR IMM")
        self._scpi.write(f"INIT{ch}:IMM")
        self._wait()

    def measure_power_avg_dbm(self, *, channel: int = 1) -> float:
        ch = self._require_channel(channel)
        return self._result(f"FETC{ch}?")

    def zero_sensor(self, *, channel: int = 1) -> None:
        ch = self._require_channel(channel)
        self._scpi.write(f"CAL{ch}:ZERO:AUTO ONCE")
        self._wait()

    def calibrate(self, *, channel: int = 1) -> None:
        ch = self._require_channel(channel)
        self._scpi.write(f"CAL{ch}:AUTO ONCE")
        self._wait()


@instrument_model("pwrmeter", "keysight-u8487a", "keysight-u8488a")
@supported_commands(*_AVERAGE)
class KeysightU848x(AveragePowerMeter):
    """USB thermal sensor; use VISA USBTMC, one sensor per configuration row."""

    def __init__(self, transport: Transport, config: dict[str, Any]) -> None:
        if int(config.get("channels") or 1) != 1:
            raise EquipmentCapabilityError("USB sensor has one input")
        super().__init__(transport, config)
        self._scpi.write("UNIT:POW DBM")

    def set_frequency(self, frequency_hz: float, *, channel: int = 1) -> None:
        self._require_channel(channel)
        self._scpi.write(f"SENS:FREQ {frequency_hz:.6f}")

    def set_averaging_count(self, count: int, *, channel: int = 1) -> None:
        self._require_channel(channel)
        if count < 1:
            raise ValueError("averaging count must be positive")
        self._scpi.write("SENS:AVER:COUN:AUTO OFF")
        self._scpi.write(f"SENS:AVER:COUN {count}")
        self._scpi.write("SENS:AVER:STAT ON")

    def acquire(self, *, channel: int = 1) -> None:
        self._require_channel(channel)
        self._scpi.write("INIT:CONT OFF")
        self._scpi.write("TRIG:SOUR IMM")
        self._scpi.write("INIT:IMM")
        self._wait()

    def measure_power_avg_dbm(self, *, channel: int = 1) -> float:
        self._require_channel(channel)
        return self._result("FETC?")


@instrument_model("pwrmeter", "rohde-nrp18s", "rohde-nrp33sn")
@supported_commands(*_AVERAGE)
class RohdeNrpAverage(KeysightU848x):
    """Direct SCPI NRP sensor session; NRP results are watts, converted on host.

    Requires a working vendor/VISA sensor interface or the SN network interface.
    Does not provide a vendor DLL loader for older NRP-Z sensors.
    """

    def __init__(self, transport: Transport, config: dict[str, Any]) -> None:
        if int(config.get("channels") or 1) != 1:
            raise EquipmentCapabilityError("direct NRP session has one input")
        AveragePowerMeter.__init__(self, transport, config)
        self._scpi.write("SENS:FUNC 'POW:AVG'")

    def set_averaging_count(self, count: int, *, channel: int = 1) -> None:
        self._require_channel(channel)
        if count < 1:
            raise ValueError("averaging count must be positive")
        self._scpi.write("SENS:AVER:COUN:AUTO OFF")
        self._scpi.write(f"SENS:AVER:COUN {count}")
        self._scpi.write("SENS:AVER:STAT ON")

    def acquire(self, *, channel: int = 1) -> None:
        self._require_channel(channel)
        self._scpi.write("INIT:CONT OFF")
        self._scpi.write("TRIG:SOUR IMM")
        self._scpi.write("TRIG:COUN 1")
        self._scpi.write("INIT:IMM")
        self._wait()

    def measure_power_avg_dbm(self, *, channel: int = 1) -> float:
        self._require_channel(channel)
        watts = self._result("FETC?")
        if watts <= 0:
            raise EquipmentResponseError("nonpositive watt reading has no finite dBm value")
        return 10 * math.log10(watts) + 30


@instrument_model("pwrmeter", "anritsu-ml2495a")
@supported_commands(
    "set_frequency", "set_averaging_count", "measure_power", "measure_power_dbm",
    "measure_power_w", "measure_power_avg_dbm",
)
class AnritsuMl2495a(GenericPwrMeter):
    """13000-00239J, ch.6/11: CW readout from physical input A.

    https://dl.cdn-anritsu.com/en-us/test-measurement/files/Manuals/Programming-Manual/13000-00239J.pdf
    CWO reads current CW result; no promise of a newly triggered conversion.
    Pulsed mode, profile, peak and trigger acquisition are outside this subset.
    """

    def __init__(self, transport: Transport, config: dict[str, Any]) -> None:
        if int(config.get("channels") or 1) != 1:
            raise EquipmentCapabilityError("ML2495A subset exposes physical input A as channel 1")
        super().__init__(transport, config)
        for command in ("CHCFG 1,A", "CHMODE 1,CW", "CWREL 1,OFF", "CHUNIT 1,DBM"):
            self._scpi.write(command)

    def set_frequency(self, frequency_hz: float, *, channel: int = 1) -> None:
        self._require_channel(channel)
        self._scpi.write("SNCFSRC A,FREQ")
        self._scpi.write(f"SNCFRQ A,{frequency_hz:.6f}HZ")

    def set_averaging_count(self, count: int, *, channel: int = 1) -> None:
        self._require_channel(channel)
        if not 1 <= count <= 512:
            raise ValueError("CW average count is 1..512")
        self._scpi.write(f"CWAVG 1,MOV,{count}")

    def measure_power_dbm(self, *, channel: int = 1) -> float:
        self._require_channel(channel)
        raw = self._scpi.query("CWO 1")
        match = re.fullmatch(r"CWO\s*1,\s*([-+0-9.eE]+)", raw, re.IGNORECASE)
        if match is None:
            raise EquipmentResponseError(f"expected CW channel 1 result, got {raw!r}")
        try:
            value = float(match[1])
        except ValueError as exc:
            raise EquipmentResponseError("invalid CW power reading") from exc
        if not math.isfinite(value) or abs(value) >= 9e37:
            raise EquipmentResponseError("invalid CW power reading")
        return value

    def measure_power_avg_dbm(self, *, channel: int = 1) -> float:
        return self.measure_power_dbm(channel=channel)


@instrument_model("pwrmeter", "rohde-nrx")
@supported_commands(*_AVERAGE)
class RohdeNrx(AveragePowerMeter):
    """1178.5566.02 v09, sections 13.4, 13.6.1/4/6; native NRX SCPI.

    https://assets.testequity.com/te1/Documents/pdf/rs/RS_NRX_UserManual_en_09.pdf
    Channel n owns measurement pane n and fixed sensor port n (A..D).
    Configure only fitted/connected ports; USB/LAN sensor indices are excluded.
    """

    def __init__(self, transport: Transport, config: dict[str, Any]) -> None:
        count = int(config.get("channels") or 1)
        if not 1 <= count <= 4:
            raise EquipmentCapabilityError("NRX subset addresses fixed sensor ports A..D")
        super().__init__(transport, {**config, "channels": count})
        for ch in range(1, count + 1):
            self._scpi.write(f"CALC{ch}:TYPE CONTAV")
            self._scpi.write(f'CALC{ch}:MATH:EXPR "(SENS{ch})"')
            self._scpi.write(f"CALC{ch}:SENS:IND {ch}")
            self._scpi.write(f'CALC{ch}:FEED1 "POW:AVER"')
            self._scpi.write(f"CALC{ch}:REL1:STAT OFF")
            self._scpi.write(f"UNIT{ch}:POW DBM")

    def set_frequency(self, frequency_hz: float, *, channel: int = 1) -> None:
        ch = self._require_channel(channel)
        self._scpi.write(f"SENS{ch}:FREQ {frequency_hz:.6f}")

    def set_averaging_count(self, count: int, *, channel: int = 1) -> None:
        ch = self._require_channel(channel)
        if count < 1:
            raise ValueError("average count must be positive")
        self._scpi.write(f"SENS{ch}:AVER:COUN:AUTO OFF")
        self._scpi.write(f"SENS{ch}:AVER:COUN {count}")

    def acquire(self, *, channel: int = 1) -> None:
        ch = self._require_channel(channel)
        self._scpi.write(f"INIT{ch}:CONT OFF")
        self._scpi.write(f"TRIG{ch}:SOUR BUS")
        self._scpi.write(f"INIT{ch}:IMM")
        self._scpi.write(f"TRIG{ch}:IMM")
        self._wait()

    def measure_power_avg_dbm(self, *, channel: int = 1) -> float:
        ch = self._require_channel(channel)
        return self._result(f"FETC{ch}?")
