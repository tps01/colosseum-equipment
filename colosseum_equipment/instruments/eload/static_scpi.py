"""Static input control for the Rigol DL3000 and Siglent SDL1000X."""

from __future__ import annotations

from math import isfinite
from typing import TYPE_CHECKING, Any

from colosseum_equipment.exceptions import EquipmentCapabilityError, EquipmentResponseError
from colosseum_equipment.instruments._channels import resolve_channel_count
from colosseum_equipment.instruments.eload.generic import GenericEload

if TYPE_CHECKING:
    from colosseum_equipment.transports.base import Transport


class _StaticScpiLoad(GenericEload):
    """Single-input static commands shared by DL3000 and SDL1000X."""

    _extra_static_modes: tuple[str, ...] = ()

    def __init__(self, transport: Transport, config: dict[str, Any]) -> None:
        if resolve_channel_count(config) != 1:
            raise EquipmentCapabilityError("this electronic load has one input channel")
        super().__init__(transport, config)

    def set_mode(self, mode: str, *, channel: int = 1) -> None:
        self._require_channel(channel)
        modes = {
            "CC": "CURR", "CURR": "CURR", "CURRENT": "CURR",
            "CV": "VOLT", "VOLT": "VOLT", "VOLTAGE": "VOLT",
            "CP": "POW", "POW": "POW", "POWER": "POW",
            "CR": "RES", "RES": "RES", "RESISTANCE": "RES",
        }
        token = mode.strip().upper()
        if token not in modes and token not in self._extra_static_modes:
            raise EquipmentCapabilityError(f"unsupported static load mode {mode!r}")
        self._scpi.write(f"SOUR:FUNC {modes.get(token, token)}")

    def _set_static_level(self, command: str, value: float, channel: int) -> None:
        self._require_channel(channel)
        if not isfinite(value):
            raise EquipmentCapabilityError(f"{command} requires a finite setpoint")
        self._scpi.write(f"SOUR:{command} {value}")

    def set_current(self, current: float, *, channel: int = 1) -> None:
        self._set_static_level("CURR", current, channel)

    def set_voltage(self, voltage: float, *, channel: int = 1) -> None:
        self._set_static_level("VOLT", voltage, channel)

    def set_power(self, power: float, *, channel: int = 1) -> None:
        self._set_static_level("POW", power, channel)

    def set_resistance(self, resistance: float, *, channel: int = 1) -> None:
        self._set_static_level("RES", resistance, channel)

    def engage(self, *, channel: int = 1) -> None:
        self._require_channel(channel)
        self._scpi.write("SOUR:INP:STAT ON")

    def disengage(self, *, channel: int = 1) -> None:
        self._require_channel(channel)
        self._scpi.write("SOUR:INP:STAT OFF")

    def measure_input_state(self, *, channel: int = 1) -> bool:
        self._require_channel(channel)
        raw = self._scpi.query("SOUR:INP:STAT?").upper()
        if raw in {"0", "OFF"}:
            return False
        if raw in {"1", "ON"}:
            return True
        raise EquipmentResponseError(f"invalid load input state: {raw!r}")

    def _read_static_measurement(self, command: str, channel: int) -> float:
        self._require_channel(channel)
        raw = self._scpi.query(command)
        try:
            value = float(raw)
        except ValueError as exc:
            raise EquipmentResponseError(f"{command} returned an invalid measurement: {raw!r}") from exc
        if not isfinite(value):
            raise EquipmentResponseError(f"{command} returned a nonfinite measurement: {raw!r}")
        return value

    def measure_voltage(self, *, channel: int = 1) -> float:
        return self._read_static_measurement("MEAS:VOLT?", channel)

    def measure_current(self, *, channel: int = 1) -> float:
        return self._read_static_measurement("MEAS:CURR?", channel)

    def measure_power_w(self, *, channel: int = 1) -> float:
        return self._read_static_measurement("MEAS:POW?", channel)


class RigolDl3000(_StaticScpiLoad):
    """RIGOL DL3000 Programming Guide, chapter 2. Select FIX mode for static control."""


class SiglentSdl1000x(_StaticScpiLoad):
    """SIGLENT SDL1000X Programming Guide E02B, sections 3.2 and 3.3."""

    _extra_static_modes = ("LED",)

    def toggle_short(self, enabled: bool, *, channel: int = 1) -> None:
        self._require_channel(channel)
        self._scpi.write(f"SOUR:SHOR {'ON' if enabled else 'OFF'}")
