from __future__ import annotations

from typing import TYPE_CHECKING, Any

from colosseum_equipment.exceptions import EquipmentCapabilityError
from colosseum_equipment.instruments._base import ScpiInstrumentMixin
from colosseum_equipment.instruments.registry import best_effort_commands, instrument_model
from colosseum_equipment.protocols.scpi import SCPIHelper

if TYPE_CHECKING:
    from colosseum_equipment.transports.base import Transport

_COUPLINGS = {"ac", "dc"}


@instrument_model("freqcounter", "generic", extra_optional=("channels",))
@best_effort_commands
class GenericFreqCounter(ScpiInstrumentMixin):
    """Generic SCPI frequency counter."""

    _model = "generic"

    def __init__(self, transport: Transport, config: dict[str, Any]) -> None:
        self._scpi = SCPIHelper(transport)
        self._config = config
        self._model = str(config.get("model", "generic")).lower()
        self._channel_count = int(
            config.get("channels") or config.get("channel_count") or 2,
        )

    def _require_channel(self, channel: int) -> int:
        ch = int(channel)
        if ch < 1 or ch > self._channel_count:
            raise EquipmentCapabilityError(
                f"freqcounter model `{self._model}` does not support channel {ch} "
                f"(valid 1..{self._channel_count})",
            )
        return ch

    def _select_input(self, channel: int) -> None:
        ch = self._require_channel(channel)
        if ch > 1:
            self._scpi.write(f"ROUT:FEED INP{ch}")

    def set_gate_time(self, seconds: float) -> None:
        self._scpi.write(f"SENS:FREQ:GATE:TIME {seconds}")

    def set_coupling(self, coupling: str, *, channel: int = 1) -> None:
        ch = self._require_channel(channel)
        mode = coupling.strip().lower()
        if mode not in _COUPLINGS:
            raise EquipmentCapabilityError(f"unsupported coupling `{coupling}`")
        self._scpi.write(f"INP{ch}:COUP {mode.upper()}")

    def set_impedance(self, ohms: float, *, channel: int = 1) -> None:
        ch = self._require_channel(channel)
        if ohms == 50:
            value = "50"
        elif ohms >= 1e6:
            value = "1MEG"
        else:
            value = f"{ohms:.1f}"
        self._scpi.write(f"INP{ch}:IMP {value}")

    def set_attenuation(self, attenuation_db: float, *, channel: int = 1) -> None:
        ch = self._require_channel(channel)
        self._scpi.write(f"INP{ch}:ATT {attenuation_db:.3f}")

    def set_trigger_level_v(self, level_v: float, *, channel: int = 1) -> None:
        ch = self._require_channel(channel)
        self._scpi.write(f"INP{ch}:TRIG:LEV {level_v:.6f}")

    def measure_frequency(self, *, channel: int = 1) -> float:
        self._select_input(channel)
        return self._scpi.query_float("MEAS:FREQ?")

    def measure_period(self, *, channel: int = 1) -> float:
        self._select_input(channel)
        return self._scpi.query_float("MEAS:PER?")

    def measure_time_interval_s(self, *, channel: int = 1) -> float:
        self._select_input(channel)
        return self._scpi.query_float("MEAS:TINT?")

    def measure_rise_time_s(self, *, channel: int = 1) -> float:
        self._select_input(channel)
        return self._scpi.query_float("MEAS:RTIM?")

    def measure_duty_cycle_pct(self, *, channel: int = 1) -> float:
        self._select_input(channel)
        return self._scpi.query_float("MEAS:DCYC?")

    def measure_totalize(self, *, channel: int = 1) -> float:
        self._select_input(channel)
        return self._scpi.query_float("MEAS:TOT?")

    def measure_frequency_mean_hz(self, *, channel: int = 1) -> float:
        self._select_input(channel)
        return self._scpi.query_float("CALC:AVER:MEAN?")

    def measure_frequency_stdev_hz(self, *, channel: int = 1) -> float:
        self._select_input(channel)
        return self._scpi.query_float("CALC:AVER:SDEV?")

    def preset(self) -> None:
        self._scpi.write("*RST")
