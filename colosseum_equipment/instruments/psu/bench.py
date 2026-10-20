"""Inventory bench supplies: explicit output selection and channel-list dialects.

Manuals: E364xA 9018-01165; HMP Series 1178.6833.02;
N6705A User's Guide N6705-90001 (SCPI channel lists).
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from colosseum_equipment.exceptions import EquipmentCapabilityError
from colosseum_equipment.instruments._capabilities import supported_commands
from colosseum_equipment.instruments.psu.generic import GenericPSU
from colosseum_equipment.instruments.registry import instrument_model

if TYPE_CHECKING:
    from colosseum_equipment.transports.base import Transport

_BASIC = (
    "set_voltage", "set_current_limit", "set_output", "get_voltage", "get_current_limit",
    "get_output", "measure_voltage", "measure_current", "measure_power_w", "measure_output_state",
    "wait_for_voltage", "wait_for_current",
)


@instrument_model("psu", "keysight-e3644a")
@supported_commands(*_BASIC, "set_ovp_v", "get_ovp_v", "clear_protection")
class KeysightE3644A(GenericPSU):
    """Manual: https://www.keysight.com/us/en/assets/9018-01165/user-manuals/9018-01165.pdf

    Select the desired output range on the instrument before use; this driver
    does not change ranges or enable the output when connecting.
    """

    def __init__(self, transport: Transport, config: dict[str, Any]) -> None:
        if int(config.get("channels") or config.get("channel_count") or 1) != 1:
            raise EquipmentCapabilityError("E3644A has one output")
        super().__init__(transport, config)

    def clear_protection(self, *, channel: int = 1) -> None:
        self._require_channel(channel)
        self._scpi.write("VOLT:PROT:CLE")

    def measure_power_w(self, *, channel: int = 1) -> float:
        return self.measure_voltage(channel=channel) * self.measure_current(channel=channel)


@instrument_model("psu", "rohde-hmp4040")
@supported_commands(*_BASIC, "set_ovp_v", "get_ovp_v")
class RohdeHmp4040(GenericPSU):
    """Manual: https://www.rohde-schwarz.com/manual/hmp

    OUTP addresses the selected channel. OUTP:GEN would enable every previously
    selected channel and is deliberately not used for channel-specific output.
    """

    def __init__(self, transport: Transport, config: dict[str, Any]) -> None:
        count = int(config.get("channels") or config.get("channel_count") or 4)
        if count < 1 or count > 4:
            raise EquipmentCapabilityError("HMP4040 has four outputs")
        super().__init__(transport, {**config, "channels": count})

    def _apply_channel(self, channel: int) -> int:
        ch = self._require_channel(channel)
        self._scpi.write(f"INST OUT{ch}")
        return ch

    def measure_power_w(self, *, channel: int = 1) -> float:
        return self.measure_voltage(channel=channel) * self.measure_current(channel=channel)


@instrument_model("psu", "keysight-n6705a")
@supported_commands(
    *_BASIC, "set_ovp_v", "get_ovp_v", "toggle_ocp", "get_ocp_enabled", "clear_protection",
    "set_slew_voltage",
)
class KeysightN6705A(GenericPSU):
    """Basic sourcing only. Installed modules determine output ranges/capabilities.

    Manual: https://www.keysight.com/us/en/support/N6705A/dc-power-analyzer-modular-600-w-4-slots.html
    """

    def __init__(self, transport: Transport, config: dict[str, Any]) -> None:
        count = int(config.get("channels") or config.get("channel_count") or 4)
        if count < 1 or count > 4:
            raise EquipmentCapabilityError("N6705A has at most four module slots")
        super().__init__(transport, {**config, "channels": count})

    def _write_channel(self, command: str, value: str, channel: int) -> None:
        ch = self._require_channel(channel)
        self._scpi.write(f"{command} {value},(@{ch})")

    def _query_channel(self, command: str, channel: int) -> float:
        ch = self._require_channel(channel)
        return self._scpi.query_float(f"{command}? (@{ch})")

    def set_voltage(self, voltage: float, *, channel: int = 1) -> None:
        self._write_channel("VOLT", f"{voltage:.6f}", channel)

    def set_current_limit(self, current: float, *, channel: int = 1) -> None:
        self._write_channel("CURR", f"{current:.6f}", channel)

    def set_output(self, enabled: bool, *, channel: int = 1) -> None:
        self._write_channel("OUTP", str(int(enabled)), channel)

    def get_voltage(self, *, channel: int = 1) -> float:
        return self._query_channel("VOLT", channel)

    def get_current_limit(self, *, channel: int = 1) -> float:
        return self._query_channel("CURR", channel)

    def get_output(self, *, channel: int = 1) -> bool:
        return bool(int(self._query_channel("OUTP", channel)))

    def measure_voltage(self, *, channel: int = 1) -> float:
        return self._query_channel("MEAS:VOLT", channel)

    def measure_current(self, *, channel: int = 1) -> float:
        return self._query_channel("MEAS:CURR", channel)

    def measure_power_w(self, *, channel: int = 1) -> float:
        # Works also on modules without simultaneous V/I power acquisition.
        return self.measure_voltage(channel=channel) * self.measure_current(channel=channel)

    def set_ovp_v(self, voltage: float, *, channel: int = 1) -> None:
        self._write_channel("VOLT:PROT", f"{voltage:.6f}", channel)

    def get_ovp_v(self, *, channel: int = 1) -> float:
        return self._query_channel("VOLT:PROT", channel)

    def toggle_ocp(self, enabled: bool, *, channel: int = 1) -> None:
        self._write_channel("CURR:PROT:STAT", str(int(enabled)), channel)

    def get_ocp_enabled(self, *, channel: int = 1) -> bool:
        return bool(int(self._query_channel("CURR:PROT:STAT", channel)))

    def clear_protection(self, *, channel: int = 1) -> None:
        ch = self._require_channel(channel)
        self._scpi.write(f"OUTP:PROT:CLE (@{ch})")

    def set_slew_voltage(self, volts_per_s: float, *, channel: int = 1) -> None:
        self._write_channel("VOLT:SLEW", str(volts_per_s), channel)
