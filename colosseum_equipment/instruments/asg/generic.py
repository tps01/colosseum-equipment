from __future__ import annotations

from typing import TYPE_CHECKING, Any

from colosseum_equipment.exceptions import EquipmentCapabilityError
from colosseum_equipment.instruments._base import ScpiInstrumentMixin
from colosseum_equipment.instruments.registry import best_effort_commands, instrument_model
from colosseum_equipment.protocols.scpi import SCPIHelper

if TYPE_CHECKING:
    from colosseum_equipment.transports.base import Transport

_WAVEFORMS = {
    "sine": "SIN",
    "square": "SQU",
    "ramp": "RAMP",
    "pulse": "PULS",
    "noise": "NOIS",
    "arb": "ARB",
}


@instrument_model(
    "asg",
    "generic",
    extra_optional=("frequency", "power_dbm", "output", "channels"),
)
@best_effort_commands
class GenericASG(ScpiInstrumentMixin):
    """Generic analog signal generator using R&S-oriented SCPI mnemonics."""

    _model = "generic"

    def __init__(self, transport: Transport, config: dict[str, Any]) -> None:
        self._scpi = SCPIHelper(transport)
        self._config = config
        self._model = str(config.get("model", "generic")).lower()
        self._channel_count = int(
            config.get("channels") or config.get("channel_count") or 1,
        )
        if "frequency" in config:
            self.set_frequency(float(config["frequency"]))
        if "power_dbm" in config:
            self.set_power(float(config["power_dbm"]))
        if config.get("output"):
            self.set_output(True)

    def _require_channel(self, channel: int) -> int:
        ch = int(channel)
        if ch < 1 or ch > self._channel_count:
            raise EquipmentCapabilityError(
                f"asg model `{self._model}` does not support channel {ch} "
                f"(valid 1..{self._channel_count})",
            )
        return ch

    def _source(self, channel: int) -> str:
        ch = self._require_channel(channel)
        return f"SOUR{ch}:"

    def set_frequency(self, frequency: float, *, channel: int = 1) -> None:
        ch = self._require_channel(channel)
        if ch == 1:
            self._scpi.write(f"FREQ:CW {frequency:.6f}")
            return
        self._scpi.write(f"SOUR{ch}:FREQ {frequency:.6f}")

    def set_waveform(self, waveform: str, *, channel: int = 1) -> None:
        name = waveform.strip().lower()
        if name not in _WAVEFORMS:
            raise EquipmentCapabilityError(f"unsupported waveform `{waveform}`")
        self._scpi.write(f"{self._source(channel)}FUNC {_WAVEFORMS[name]}")

    def set_amplitude_vpp(self, vpp: float, *, channel: int = 1) -> None:
        prefix = self._source(channel)
        self._scpi.write(f"{prefix}VOLT:UNIT VPP")
        self._scpi.write(f"{prefix}VOLT {vpp:.6f}")

    def set_amplitude_vrms(self, vrms: float, *, channel: int = 1) -> None:
        prefix = self._source(channel)
        self._scpi.write(f"{prefix}VOLT:UNIT VRMS")
        self._scpi.write(f"{prefix}VOLT {vrms:.6f}")

    def set_offset_v(self, offset_v: float, *, channel: int = 1) -> None:
        self._scpi.write(f"{self._source(channel)}VOLT:OFFS {offset_v:.6f}")

    def set_load_ohms(self, ohms: float, *, channel: int = 1) -> None:
        ch = self._require_channel(channel)
        self._scpi.write(f"OUTP{ch}:LOAD {ohms:.1f}")

    def get_load_ohms(self, *, channel: int = 1) -> float:
        ch = self._require_channel(channel)
        return self._scpi.query_float(f"OUTP{ch}:LOAD?")

    def set_power(self, power_dbm: float, *, channel: int = 1) -> None:
        ch = self._require_channel(channel)
        if ch == 1:
            self._scpi.write(f"POW:AMPL {power_dbm:.3f}")
            return
        self._scpi.write(f"SOUR{ch}:POW:AMPL {power_dbm:.3f}")

    def set_duty_cycle_pct(self, pct: float, *, channel: int = 1) -> None:
        self._scpi.write(f"{self._source(channel)}FUNC:SQU:DCYC {pct:.3f}")

    def set_output(self, enabled: bool, *, channel: int = 1) -> None:
        ch = self._require_channel(channel)
        if ch == 1:
            self._scpi.write("OUTP ON" if enabled else "OUTP OFF")
            return
        self._scpi.write(f"OUTP{ch} {'ON' if enabled else 'OFF'}")

    def set_modulation_state(self, enabled: bool, *, channel: int = 1) -> None:
        self._scpi.write(
            f"{self._source(channel)}AM:STAT {'ON' if enabled else 'OFF'}",
        )

    def set_burst_state(self, enabled: bool, *, channel: int = 1) -> None:
        self._scpi.write(
            f"{self._source(channel)}BURS:STAT {'ON' if enabled else 'OFF'}",
        )

    def set_pulsegen_output(self, enabled: bool, *, channel: int = 1) -> None:
        _ = self._require_channel(channel)
        self._scpi.write(":PULGen:STAT ON" if enabled else ":PULGen:STAT OFF")

    def set_pulsemod_output(self, enabled: bool, *, channel: int = 1) -> None:
        _ = self._require_channel(channel)
        self._scpi.write(":PULM:STAT ON" if enabled else ":PULM:STAT OFF")

    def set_pulse_period(self, period_s: float, *, channel: int = 1) -> None:
        _ = self._require_channel(channel)
        self._scpi.write(f":PULM:PER {period_s:.9f}")

    def set_pulse_width(self, width_s: float, *, channel: int = 1) -> None:
        _ = self._require_channel(channel)
        self._scpi.write(f":PULM:WIDt {width_s:.9f}")
