from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from colosseum_equipment.exceptions import EquipmentCapabilityError, EquipmentResponseError
from colosseum_equipment.instruments._capabilities import supported_commands
from colosseum_equipment.instruments.psu.generic import GenericPSU
from colosseum_equipment.instruments.registry import instrument_model

if TYPE_CHECKING:
    from colosseum_equipment.transports.base import Transport


@instrument_model("psu", "tdk-genesys")
class TdkGenesysPSU(GenericPSU):
    """Reference driver for TDK-Lambda Genesys."""

    def __init__(self, transport: Transport, config: dict[str, Any]) -> None:
        super().__init__(transport, config)
        if "ovp" in config:
            self.set_ovp_v(float(config["ovp"]))
        if "ocp" in config:
            self.set_ocp_a(float(config["ocp"]))


@instrument_model("psu", "tdk-gen300-5-serial")
@supported_commands(
    "set_voltage", "set_current_limit", "set_output", "get_voltage", "get_current_limit", "get_output",
    "measure_voltage", "measure_current", "measure_power_w", "measure_output_state",
    "set_ovp_v", "get_ovp_v", "wait_for_voltage", "wait_for_current",
)
class TdkGen3005Serial(GenericPSU):
    """Genesys 750/1500W user manual ch.7: addressed CR-terminated native protocol.

    https://www.atecorp.com/getmedia/13512e00-f13e-448e-9adc-d54daa8115e8/gen600-2-6-manual.pdf
    Explicit serial model; never infer this personality from a SCPI family IDN.
    """

    def __init__(self, transport: Transport, config: dict[str, Any]) -> None:
        if config.get("driver") != "serial" or "baudrate" not in config or "device_address" not in config:
            raise EquipmentCapabilityError("use driver=serial with explicit matching baudrate and device_address")
        if int(config.get("channels") or config.get("channel_count") or 1) != 1:
            raise EquipmentCapabilityError("native serial session addresses one power supply")
        address_token = str(config["device_address"]).strip()
        if not address_token.isdecimal():
            raise ValueError("Genesys device address must be an integer in 0..30")
        address = int(address_token)
        if not 0 <= address <= 30:
            raise ValueError("Genesys device address must be 0..30")
        self._native_transport = transport
        self._write_native(f"ADR {address}")
        super().__init__(transport, config)

    def _exchange(self, command: str) -> str:
        write = getattr(self._native_transport, "write_bytes", None)
        read = getattr(self._native_transport, "read_until", None)
        if not callable(write) or not callable(read):
            raise EquipmentCapabilityError("native Genesys requires a raw serial transport")
        write(command.encode("ascii") + b"\r")
        raw = str(read(b"\r"))
        if not raw.endswith("\r"):
            raise EquipmentResponseError("incomplete Genesys CR-terminated response")
        return raw.strip()

    def _write_native(self, command: str) -> None:
        response = self._exchange(command)
        if response != "OK":
            raise EquipmentResponseError(f"Genesys rejected {command!r}: {response!r}")

    def _value(self, command: str, channel: int) -> float:
        self._require_channel(channel)
        raw = self._exchange(command)
        try:
            value = float(raw)
        except ValueError as exc:
            raise EquipmentResponseError(f"invalid Genesys response {raw!r}") from exc
        if not math.isfinite(value):
            raise EquipmentResponseError(f"invalid Genesys response {raw!r}")
        return value

    def set_voltage(self, voltage: float, *, channel: int = 1) -> None:
        self._require_channel(channel)
        self._write_native(f"PV {voltage:.6f}")

    def set_current_limit(self, current: float, *, channel: int = 1) -> None:
        self._require_channel(channel)
        self._write_native(f"PC {current:.6f}")

    def set_output(self, enabled: bool, *, channel: int = 1) -> None:
        self._require_channel(channel)
        self._write_native(f"OUT {int(enabled)}")

    def get_voltage(self, *, channel: int = 1) -> float:
        return self._value("PV?", channel)

    def get_current_limit(self, *, channel: int = 1) -> float:
        return self._value("PC?", channel)

    def get_output(self, *, channel: int = 1) -> bool:
        self._require_channel(channel)
        value = self._exchange("OUT?").upper()
        if value not in {"ON", "OFF"}:
            raise EquipmentResponseError("invalid Genesys output state")
        return value == "ON"

    def measure_voltage(self, *, channel: int = 1) -> float:
        return self._value("MV?", channel)

    def measure_current(self, *, channel: int = 1) -> float:
        return self._value("MC?", channel)

    def measure_power_w(self, *, channel: int = 1) -> float:
        return self.measure_voltage(channel=channel) * self.measure_current(channel=channel)

    def set_ovp_v(self, voltage: float, *, channel: int = 1) -> None:
        self._require_channel(channel)
        self._write_native(f"OVP {voltage:.6f}")

    def get_ovp_v(self, *, channel: int = 1) -> float:
        return self._value("OVP?", channel)
