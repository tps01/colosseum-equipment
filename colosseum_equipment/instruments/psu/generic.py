from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from colosseum_equipment.exceptions import EquipmentCapabilityError, EquipmentTimeoutError
from colosseum_equipment.instruments._base import ScpiInstrumentMixin
from colosseum_equipment.instruments.registry import best_effort_commands, instrument_model
from colosseum_equipment.protocols.scpi import SCPIHelper

if TYPE_CHECKING:
    from colosseum_equipment.transports.base import Transport


@instrument_model(
    "psu",
    "generic",
    extra_optional=("voltage", "ovp", "ocp", "channels", "channel_count"),
)
@best_effort_commands
class GenericPSU(ScpiInstrumentMixin):
    def __init__(self, transport: Transport, config: dict[str, Any]) -> None:
        self._scpi = SCPIHelper(transport)
        self._config = config
        self._model = str(config.get("model", "generic")).lower()
        self._channel_count = int(config.get("channels") or config.get("channel_count") or 1)
        if "voltage" in config:
            self.set_voltage(float(config["voltage"]))
        if "ocp" in config:
            self.set_current_limit(float(config["ocp"]))
        if "ovp" in config:
            self.set_ovp_v(float(config["ovp"]))

    def _require_channel(self, channel: int) -> int:
        ch = int(channel)
        if ch < 1 or ch > self._channel_count:
            raise EquipmentCapabilityError(
                f"psu model `{self._model}` does not support channel {ch} "
                f"(valid 1..{self._channel_count})",
            )
        return ch

    def _apply_channel(self, channel: int) -> int:
        ch = self._require_channel(channel)
        if self._channel_count > 1:
            self._scpi.write(f"INST:NSEL {ch}")
        return ch

    def set_voltage(self, voltage: float, *, channel: int = 1) -> None:
        self._apply_channel(channel)
        self._scpi.write(f"VOLT {float(voltage):.6f}")

    def set_current_limit(self, current: float, *, channel: int = 1) -> None:
        self._apply_channel(channel)
        self._scpi.write(f"CURR {float(current):.6f}")

    def set_output(self, enabled: bool, *, channel: int = 1) -> None:
        self._apply_channel(channel)
        self._scpi.write("OUTP ON" if enabled else "OUTP OFF")

    def get_voltage(self, *, channel: int = 1) -> float:
        self._apply_channel(channel)
        return self._scpi.query_float("VOLT?")

    def get_current_limit(self, *, channel: int = 1) -> float:
        self._apply_channel(channel)
        return self._scpi.query_float("CURR?")

    def get_output(self, *, channel: int = 1) -> bool:
        self._apply_channel(channel)
        return bool(int(float(self._scpi.query("OUTP?"))))

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

    def measure_output_state(self, *, channel: int = 1) -> bool:
        return self.get_output(channel=channel)

    def get_regulation_mode(self, *, channel: int = 1) -> str:
        self._apply_channel(channel)
        raw = self._scpi.query("OUTP:MODE?").strip().upper()
        for token, label in (("CV", "cv"), ("CC", "cc"), ("UR", "ur"), ("UNR", "ur")):
            if token in raw:
                return label
        if raw in ("0", "1", "2"):
            return ("cv", "cc", "ur")[int(raw)]
        return raw.lower() or "unknown"

    def set_ovp_v(self, voltage: float, *, channel: int = 1) -> None:
        self._apply_channel(channel)
        self._scpi.write(f"VOLT:PROT {float(voltage):.6f}")

    def set_ocp_a(self, current: float, *, channel: int = 1) -> None:
        self._apply_channel(channel)
        self._scpi.write(f"CURR:PROT {float(current):.6f}")

    def toggle_ovp(self, enabled: bool, *, channel: int = 1) -> None:
        self._apply_channel(channel)
        self._scpi.write(f"VOLT:PROT:STAT {'ON' if enabled else 'OFF'}")

    def toggle_ocp(self, enabled: bool, *, channel: int = 1) -> None:
        self._apply_channel(channel)
        self._scpi.write(f"CURR:PROT:STAT {'ON' if enabled else 'OFF'}")

    def get_ovp_v(self, *, channel: int = 1) -> float:
        self._apply_channel(channel)
        return self._scpi.query_float("VOLT:PROT?")

    def get_ocp_a(self, *, channel: int = 1) -> float:
        self._apply_channel(channel)
        return self._scpi.query_float("CURR:PROT?")

    def get_ovp_enabled(self, *, channel: int = 1) -> bool:
        self._apply_channel(channel)
        return bool(int(float(self._scpi.query("VOLT:PROT:STAT?"))))

    def get_ocp_enabled(self, *, channel: int = 1) -> bool:
        self._apply_channel(channel)
        return bool(int(float(self._scpi.query("CURR:PROT:STAT?"))))

    def clear_protection(self, *, channel: int = 1) -> None:
        self._apply_channel(channel)
        self._scpi.write("OUTP:PROT:CLE")

    def get_fault_status(self, *, channel: int = 1) -> str:
        self._apply_channel(channel)
        return self._scpi.query("STAT:QUES:INST?").strip()

    def set_remote_sense(self, enabled: bool, *, channel: int = 1) -> None:
        self._apply_channel(channel)
        self._scpi.write(f"SENS {'ON' if enabled else 'OFF'}")

    def set_slew_voltage(self, volts_per_s: float, *, channel: int = 1) -> None:
        self._apply_channel(channel)
        self._scpi.write(f"VOLT:SLEW:POS {volts_per_s}")

    def set_slew_current(self, amps_per_s: float, *, channel: int = 1) -> None:
        self._apply_channel(channel)
        self._scpi.write(f"CURR:SLEW:POS {amps_per_s}")

    def set_tracking_mode(self, mode: str, *, channel: int = 1) -> None:
        self._apply_channel(channel)
        token = mode.strip().upper()
        if token in ("ON", "OFF", "TRACK", "IND"):
            self._scpi.write(f"OUTP:TRAC {token}")
        else:
            self._scpi.write(f"OUTP:TRAC {'ON' if token in ('1', 'TRUE', 'YES') else 'OFF'}")

    def wait_for_voltage(
        self,
        voltage: float,
        *,
        timeout_s: float,
        tolerance: float = 0.01,
        channel: int = 1,
    ) -> None:
        deadline = time.monotonic() + timeout_s
        measured = self.measure_voltage(channel=channel)
        while time.monotonic() < deadline:
            measured = self.measure_voltage(channel=channel)
            if abs(measured - voltage) <= tolerance:
                return
            time.sleep(0.05)
        raise EquipmentTimeoutError(
            f"PSU did not reach {voltage} V within {timeout_s}s (last reading {measured} V)",
        )

    def wait_for_current(
        self,
        current: float,
        *,
        timeout_s: float,
        tolerance: float = 0.01,
        channel: int = 1,
    ) -> None:
        deadline = time.monotonic() + timeout_s
        measured = self.measure_current(channel=channel)
        while time.monotonic() < deadline:
            measured = self.measure_current(channel=channel)
            if abs(measured - current) <= tolerance:
                return
            time.sleep(0.05)
        raise EquipmentTimeoutError(
            f"PSU did not reach {current} A within {timeout_s}s (last reading {measured} A)",
        )
