"""Function-qualified SCPI for the inventory's bench multimeters.

Manuals: Keysight 34410A/11A command reference 9018-61141;
Keithley 2100-900-01 and 2001-900-01 operator manuals.
"""
from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from colosseum_equipment.exceptions import EquipmentCapabilityError, EquipmentResponseError
from colosseum_equipment.instruments._capabilities import supported_commands
from colosseum_equipment.instruments.dmm.generic import GenericDMM
from colosseum_equipment.instruments.registry import instrument_model

if TYPE_CHECKING:
    from colosseum_equipment.transports.base import Transport

_FUNCTIONS = {
    "VOLT": "VOLT:DC", "VOLTAGE": "VOLT:DC", "DC": "VOLT:DC", "AC": "VOLT:AC",
    "CURR": "CURR:DC", "CURRENT": "CURR:DC", "RESISTANCE": "RES", "FRESISTANCE": "FRES",
    "FREQUENCY": "FREQ", "VOLTAGE:DC": "VOLT:DC", "VOLTAGE:AC": "VOLT:AC",
    "CURRENT:DC": "CURR:DC", "CURRENT:AC": "CURR:AC",
}
_BASIC = (
    "set_function", "get_function", "set_range", "get_range", "set_auto_range", "get_auto_range",
    "set_nplc", "get_nplc", "set_auto_zero", "get_auto_zero", "set_trigger_source",
    "get_trigger_source", "initiate", "fetch", "measure_voltage", "measure_voltage_dc",
    "measure_voltage_ac", "measure_current", "measure_current_dc", "measure_current_ac",
    "measure_resistance", "measure_resistance_4w", "measure_frequency_hz",
)


class BenchDmm(GenericDMM):
    """Single-input scalar measurements; no implicit buffered-array truncation."""

    _zero_command = "ZERO:AUTO"

    def __init__(self, transport: Transport, config: dict[str, Any]) -> None:
        if int(config.get("channels") or config.get("channel_count") or 1) != 1:
            raise EquipmentCapabilityError("bench DMM supports one input, not scanner channels")
        super().__init__(transport, config)

    def _function(self, function: str) -> str:
        token = function.strip().strip('\"').upper()
        token = _FUNCTIONS.get(token, token)
        if token not in {"VOLT:DC", "VOLT:AC", "CURR:DC", "CURR:AC", "RES", "FRES", "FREQ"}:
            raise EquipmentCapabilityError(f"unsupported DMM function {function!r}")
        return token

    def set_function(self, function: str, *, channel: int = 1) -> None:
        self._require_channel(channel)
        self._scpi.write(f'CONF:{self._function(function)}')

    def get_function(self, *, channel: int = 1) -> str:
        self._require_channel(channel)
        return self._function(self._scpi.query("SENS:FUNC?"))

    def _sense(self, channel: int, suffix: str, *, integrating: bool = False) -> str:
        function = self.get_function(channel=channel)
        if integrating and function not in {"VOLT:DC", "CURR:DC", "RES", "FRES"}:
            raise EquipmentCapabilityError(f"{suffix} is unavailable for {function}")
        return f"SENS:{function}:{suffix}"

    def set_range(self, value: float, *, channel: int = 1) -> None:
        self._scpi.write(f"{self._sense(channel, 'RANG')} {value}")

    def get_range(self, *, channel: int = 1) -> float:
        return self._scpi.query_float(f"{self._sense(channel, 'RANG')}?")

    def set_auto_range(self, enabled: bool, *, channel: int = 1) -> None:
        self._scpi.write(f"{self._sense(channel, 'RANG:AUTO')} {int(enabled)}")

    def get_auto_range(self, *, channel: int = 1) -> bool:
        return bool(int(self._scpi.query(f"{self._sense(channel, 'RANG:AUTO')}?")))

    def set_nplc(self, nplc: float, *, channel: int = 1) -> None:
        self._scpi.write(f"{self._sense(channel, 'NPLC', integrating=True)} {nplc}")

    def get_nplc(self, *, channel: int = 1) -> float:
        return self._scpi.query_float(f"{self._sense(channel, 'NPLC', integrating=True)}?")

    def set_auto_zero(self, enabled: bool, *, channel: int = 1) -> None:
        self._require_channel(channel)
        self._scpi.write(f"{self._zero_command} {int(enabled)}")

    def get_auto_zero(self, *, channel: int = 1) -> bool:
        self._require_channel(channel)
        return bool(int(self._scpi.query(f"{self._zero_command}?")))

    def set_trigger_source(self, source: str, *, channel: int = 1) -> None:
        self._require_channel(channel)
        token = source.strip().upper()
        if token not in {"IMM", "IMMEDIATE", "EXT", "EXTERNAL", "BUS"}:
            raise EquipmentCapabilityError(f"unsupported trigger source {source!r}")
        self._scpi.write(f"TRIG:SOUR {token}")

    def _reading(self, query: str) -> float:
        raw = self._scpi.query(query)
        try:
            value = float(raw)
        except ValueError as exc:
            raise EquipmentResponseError(f"expected one numeric reading, received {raw!r}") from exc
        if not math.isfinite(value) or abs(value) >= 9e37:
            raise EquipmentResponseError(f"overload or invalid DMM reading: {raw!r}")
        return value

    def fetch(self, *, channel: int = 1) -> float:
        self._require_channel(channel)
        return self._reading("FETC?")

    def _measure(self, function: str, channel: int) -> float:
        self.set_function(function, channel=channel)
        # A one-shot must not inherit EXT/BUS triggering or a multi-sample setup.
        self._scpi.write("TRIG:SOUR IMM")
        self._scpi.write("TRIG:COUN 1")
        self._scpi.write("SAMP:COUN 1")
        return self._reading("READ?")

    def measure_voltage_dc(self, channel: int = 1) -> float:
        return self._measure("VOLT:DC", channel)

    def measure_voltage_ac(self, channel: int = 1) -> float:
        return self._measure("VOLT:AC", channel)

    def measure_current_dc(self, channel: int = 1) -> float:
        return self._measure("CURR:DC", channel)

    def measure_current_ac(self, channel: int = 1) -> float:
        return self._measure("CURR:AC", channel)

    def measure_resistance(self, channel: int = 1) -> float:
        return self._measure("RES", channel)

    def measure_resistance_4w(self, channel: int = 1) -> float:
        return self._measure("FRES", channel)

    def measure_frequency_hz(self, channel: int = 1) -> float:
        return self._measure("FREQ", channel)


@instrument_model("dmm", "keysight-34410a", "keysight-34411a")
@supported_commands(*_BASIC, "set_aperture_s", "get_aperture_s", "set_input_z")
class Keysight3441x(BenchDmm):
    """Manual: https://www.keysight.com/us/en/assets/9018-61141/programming-guides/9018-61141.pdf"""

    def get_function(self, *, channel: int = 1) -> str:
        self._require_channel(channel)
        # CONF? includes range/resolution after the function name.
        return self._function(self._scpi.query("CONF?").strip('\"').split()[0])

    def set_auto_zero(self, enabled: bool, *, channel: int = 1) -> None:
        self._scpi.write(f"{self._sense(channel, 'ZERO:AUTO', integrating=True)} {int(enabled)}")

    def get_auto_zero(self, *, channel: int = 1) -> bool:
        command = self._sense(channel, "ZERO:AUTO", integrating=True)
        return bool(int(self._scpi.query(f"{command}?")))

    def set_aperture_s(self, seconds: float, *, channel: int = 1) -> None:
        self._scpi.write(f"{self._sense(channel, 'APER', integrating=True)} {seconds}")

    def get_aperture_s(self, *, channel: int = 1) -> float:
        return self._scpi.query_float(f"{self._sense(channel, 'APER', integrating=True)}?")

    def set_input_z(self, ohms: float, *, channel: int = 1) -> None:
        self._require_channel(channel)
        if math.isnan(ohms) or (ohms != 1e7 and ohms < 1e10):
            raise EquipmentCapabilityError("input impedance is 10 Mohm or automatic high impedance")
        self._scpi.write(f"VOLT:DC:IMP:AUTO {int(ohms >= 1e10)}")

@instrument_model("dmm", "keithley-2100")
@supported_commands(*_BASIC)
class Keithley2100(BenchDmm):
    """Manual: https://download.tek.com/manual/2100-900-01%28E-Mar2012%29%28User%29.pdf"""


@instrument_model("dmm", "keithley-2001")
@supported_commands(*_BASIC)
class Keithley2001(BenchDmm):
    """Manual: https://download.tek.com/manual/2001-900-01(K-Aug2010)(Operator).pdf

    Select SCPI fetch semantics explicitly: the power-on FRESH format otherwise
    starts another conversion on FETCh?, violating initiate/fetch semantics.
    """

    _zero_command = "SYST:AZER:STAT"

    def __init__(self, transport: Transport, config: dict[str, Any]) -> None:
        super().__init__(transport, config)
        self._scpi.write("SYST:FETC:FORM SCPI")
        self._scpi.write("FORM:DATA ASC")
        self._scpi.write("FORM:ELEM READ")

    def set_function(self, function: str, *, channel: int = 1) -> None:
        self._require_channel(channel)
        self._scpi.write(f'SENS:FUNC "{self._function(function)}"')

    def _measure(self, function: str, channel: int) -> float:
        self.set_function(function, channel=channel)
        self._scpi.write("INIT:CONT OFF")
        self._scpi.write("ABOR")
        self._scpi.write("ARM:LAY1:SOUR IMM")
        self._scpi.write("ARM:LAY1:COUN 1")
        self._scpi.write("ARM:LAY2:SOUR IMM")
        self._scpi.write("ARM:LAY2:COUN 1")
        self._scpi.write("TRIG:SOUR IMM")
        self._scpi.write("TRIG:COUN 1")
        return self._reading("READ?")
