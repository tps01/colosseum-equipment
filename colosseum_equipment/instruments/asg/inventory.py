"""33250A voltage waveforms and CG635 clock control using native commands.

Manuals: Keysight 33250A User's Guide 9018-03925;
https://www.thinksrs.com/downloads/pdfs/manuals/CG635m.pdf (remote programming).
"""
from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from colosseum_equipment.exceptions import EquipmentCapabilityError
from colosseum_equipment.instruments._capabilities import supported_commands
from colosseum_equipment.instruments.asg.generic import GenericASG
from colosseum_equipment.instruments.registry import instrument_model

if TYPE_CHECKING:
    from colosseum_equipment.transports.base import Transport


@instrument_model("asg", "keysight-33250a")
@supported_commands(
    "set_frequency", "set_waveform", "set_amplitude_vpp", "set_amplitude_vrms", "set_offset_v",
    "set_load_ohms", "get_load_ohms", "set_duty_cycle_pct", "set_output",
    "set_modulation_state", "set_burst_state",
)
class Keysight33250A(GenericASG):
    """One output, standard waveforms; arbitrary-memory upload is a separate task."""

    def __init__(self, transport: Transport, config: dict[str, Any]) -> None:
        if int(config.get("channels") or 1) != 1:
            raise EquipmentCapabilityError("33250A has one output")
        super().__init__(transport, config)

    def _source(self, channel: int) -> str:
        self._require_channel(channel)
        return ""

    def set_frequency(self, frequency: float, *, channel: int = 1) -> None:
        self._require_channel(channel)
        self._scpi.write(f"FREQ {frequency:.9f}")

    def set_waveform(self, waveform: str, *, channel: int = 1) -> None:
        self._require_channel(channel)
        token = {"sine": "SIN", "square": "SQU", "ramp": "RAMP", "pulse": "PULS",
                 "noise": "NOIS", "dc": "DC"}.get(waveform.lower())
        if token is None:
            raise EquipmentCapabilityError(f"unsupported standard waveform {waveform!r}")
        self._scpi.write(f"FUNC {token}")

    def set_load_ohms(self, ohms: float, *, channel: int = 1) -> None:
        self._require_channel(channel)
        if not (1 <= ohms <= 10000 or ohms == math.inf):
            raise ValueError("33250A load is 1..10000 ohms or positive infinity")
        self._scpi.write(f"OUTP:LOAD {'INF' if math.isinf(ohms) else str(ohms)}")

    def get_load_ohms(self, *, channel: int = 1) -> float:
        self._require_channel(channel)
        value = self._scpi.query_float("OUTP:LOAD?")
        return math.inf if value >= 9e37 else value


@instrument_model("asg", "srs-cg635")
@supported_commands("set_frequency", "set_output")
class SrsCg635(GenericASG):
    """Global clock frequency and run/stop; RUNS affects all clock outputs.

    Stopping holds clock outputs low; it does not disconnect/tri-state them.
    No generic amplitude or arbitrary-waveform semantics are implied.
    """

    def __init__(self, transport: Transport, config: dict[str, Any]) -> None:
        if int(config.get("channels") or 1) != 1:
            raise EquipmentCapabilityError("CG635 exposes one global clock control")
        super().__init__(transport, config)

    def set_frequency(self, frequency: float, *, channel: int = 1) -> None:
        self._require_channel(channel)
        if not math.isfinite(frequency) or not 0 <= frequency <= 2.05e9:
            raise ValueError("CG635 clock frequency is 0..2.05 GHz")
        self._scpi.write(f"FREQ {frequency:.12f}")

    def set_output(self, enabled: bool, *, channel: int = 1) -> None:
        self._require_channel(channel)
        self._scpi.write(f"RUNS {int(enabled)}")


@instrument_model("asg", "gwinstek-afg3032")
@supported_commands(
    "set_frequency", "set_amplitude_vpp", "set_amplitude_vrms", "set_output",
    "set_modulation_state", "set_burst_state",
)
class GwInstekAfg3032(GenericASG):
    """AFG-3021/3022/3031/3032 User Manual, remote interface pp.300-308.

    Native AMPLitude is not the generic VOLT command. Set waveform/offset/load
    on the panel: APPLy also enables output and is not used as a shape setter.
    https://manuals.plus/m/a280818d4836eb6fd43db9736ecd68ba3366153452db7a74237f12aa1000aca7
    """

    def __init__(self, transport: Transport, config: dict[str, Any]) -> None:
        channels = int(config.get("channels") or 2)
        if not 1 <= channels <= 2:
            raise EquipmentCapabilityError("AFG-3032 has two outputs")
        super().__init__(transport, {**config, "channels": channels})

    def set_frequency(self, frequency: float, *, channel: int = 1) -> None:
        self._scpi.write(f"{self._source(channel)}FREQ {frequency:.9f}")

    def set_amplitude_vpp(self, vpp: float, *, channel: int = 1) -> None:
        self._scpi.write(f"{self._source(channel)}AMPL {vpp:.6f}VPP")

    def set_amplitude_vrms(self, vrms: float, *, channel: int = 1) -> None:
        self._scpi.write(f"{self._source(channel)}AMPL {vrms:.6f}VRMS")

    def set_output(self, enabled: bool, *, channel: int = 1) -> None:
        ch = self._require_channel(channel)
        self._scpi.write(f"OUTP{ch} {'ON' if enabled else 'OFF'}")
