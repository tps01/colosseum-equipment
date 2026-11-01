from __future__ import annotations

from typing import TYPE_CHECKING, Any

from colosseum_equipment.exceptions import EquipmentCapabilityError
from colosseum_equipment.instruments._base import ScpiInstrumentMixin
from colosseum_equipment.instruments.registry import best_effort_commands, instrument_model
from colosseum_equipment.protocols.scpi import SCPIHelper

if TYPE_CHECKING:
    from colosseum_equipment.transports.base import Transport


@instrument_model("eload", "generic", extra_optional=("channels", "channel_count"))
@best_effort_commands
class GenericEload(ScpiInstrumentMixin):
    """Generic SCPI electronic load."""

    def __init__(self, transport: Transport, config: dict[str, Any]) -> None:
        self._scpi = SCPIHelper(transport)
        self._config = config
        self._model = str(config.get("model", "generic")).lower()
        from colosseum_equipment.instruments._channels import resolve_channel_count

        self._channel_count = resolve_channel_count(config)

    def _require_channel(self, channel: int) -> int:
        ch = int(channel)
        if ch < 1 or ch > self._channel_count:
            raise EquipmentCapabilityError(
                f"eload model `{self._model}` does not support channel {ch} "
                f"(valid 1..{self._channel_count})",
            )
        return ch

    def _apply_channel(self, channel: int) -> int:
        ch = self._require_channel(channel)
        if self._channel_count > 1:
            self._scpi.write(f"INST:NSEL {ch}")
        return ch

    def set_mode(self, mode: str, *, channel: int = 1) -> None:
        self._apply_channel(channel)
        self._scpi.write(f"MODE {mode.upper()}")

    def set_current(self, current: float, *, channel: int = 1) -> None:
        self._apply_channel(channel)
        self._scpi.write(f"CURR {current}")

    def set_voltage(self, voltage: float, *, channel: int = 1) -> None:
        self._apply_channel(channel)
        self._scpi.write(f"VOLT {voltage}")

    def set_power(self, power: float, *, channel: int = 1) -> None:
        self._apply_channel(channel)
        self._scpi.write(f"POW {power}")

    def set_resistance(self, resistance: float, *, channel: int = 1) -> None:
        self._apply_channel(channel)
        self._scpi.write(f"RES {resistance}")

    def engage(self, *, channel: int = 1) -> None:
        self._apply_channel(channel)
        self._scpi.write("INP ON")

    def disengage(self, *, channel: int = 1) -> None:
        self._apply_channel(channel)
        self._scpi.write("INP OFF")

    def measure_voltage(self, *, channel: int = 1) -> float:
        self._apply_channel(channel)
        return self._scpi.query_float("MEAS:VOLT?")

    def measure_current(self, *, channel: int = 1) -> float:
        self._apply_channel(channel)
        return self._scpi.query_float("MEAS:CURR?")

    def measure_power_w(self, *, channel: int = 1) -> float:
        self._apply_channel(channel)
        try:
            return self._scpi.query_float("MEAS:POW?")
        except Exception:
            return self.measure_voltage(channel=channel) * self.measure_current(channel=channel)

    def measure_resistance_ohm(self, *, channel: int = 1) -> float:
        self._apply_channel(channel)
        try:
            return self._scpi.query_float("MEAS:RES?")
        except Exception:
            current = self.measure_current(channel=channel)
            if abs(current) < 1e-12:
                return float("inf")
            return self.measure_voltage(channel=channel) / current

    def measure_input_state(self, *, channel: int = 1) -> bool:
        self._apply_channel(channel)
        return bool(int(float(self._scpi.query("INP?"))))

    def set_slew_rate(self, amps_per_s: float, *, channel: int = 1) -> None:
        self._apply_channel(channel)
        self._scpi.write(f"CURR:SLEW:POS {amps_per_s}")

    def toggle_short(self, enabled: bool, *, channel: int = 1) -> None:
        self._apply_channel(channel)
        self._scpi.write(f"INP:SHOR {'ON' if enabled else 'OFF'}")

    def set_ovp_v(self, voltage: float, *, channel: int = 1) -> None:
        self._apply_channel(channel)
        self._scpi.write(f"VOLT:PROT {voltage}")

    def set_ocp_a(self, current: float, *, channel: int = 1) -> None:
        self._apply_channel(channel)
        self._scpi.write(f"CURR:PROT {current}")

    def set_opp_w(self, power: float, *, channel: int = 1) -> None:
        self._apply_channel(channel)
        self._scpi.write(f"POW:PROT {power}")

    def clear_protection(self, *, channel: int = 1) -> None:
        self._apply_channel(channel)
        self._scpi.write("OUTP:PROT:CLE")

    def set_transient_mode(self, mode: str, *, channel: int = 1) -> None:
        self._apply_channel(channel)
        self._scpi.write(f"TRAN:MODE {mode.upper()}")

    def set_transient_level_a(self, current: float, *, channel: int = 1) -> None:
        self._apply_channel(channel)
        self._scpi.write(f"TRAN:ALEV {current}")

    def set_transient_timer_s(self, seconds: float, *, channel: int = 1) -> None:
        self._apply_channel(channel)
        # Keysight/Agilent load family: TRANsient:TWIDth <time> (no channel node).
        self._scpi.write(f"TRAN:TWID {seconds}")

    def toggle_transient(self, enabled: bool, *, channel: int = 1) -> None:
        self._apply_channel(channel)
        self._scpi.write(f"TRAN:STAT {'ON' if enabled else 'OFF'}")

    def configure_list_step(
        self,
        step: int,
        *,
        current_a: float | None = None,
        dwell_s: float | None = None,
        channel: int = 1,
    ) -> None:
        self._apply_channel(channel)
        if current_a is not None:
            self._scpi.write(f"LIST:STEP {step}:CURR {current_a}")
        if dwell_s is not None:
            self._scpi.write(f"LIST:STEP {step}:DWEL {dwell_s}")

    def set_list_count(self, count: int, *, channel: int = 1) -> None:
        self._apply_channel(channel)
        self._scpi.write(f"LIST:COUN {count}")

    def toggle_list(self, enabled: bool, *, channel: int = 1) -> None:
        self._apply_channel(channel)
        self._scpi.write(f"LIST:STAT {'ON' if enabled else 'OFF'}")

    def preset(self) -> None:
        self._scpi.write("*RST")
