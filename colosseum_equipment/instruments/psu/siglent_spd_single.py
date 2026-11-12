"""Siglent SPD1168X / SPD1305X and SPD3303X/X-E supply commands.

Command strings from PyMeasure ``siglent_spdbase.SPDChannel``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from colosseum_equipment.instruments.psu.generic import GenericPSU
from colosseum_equipment.instruments._channels import resolve_channel_count
from colosseum_equipment.exceptions import EquipmentCapabilityError, EquipmentResponseError

if TYPE_CHECKING:
    from colosseum_equipment.transports.base import Transport


class SiglentSpdSingle(GenericPSU):
    """Shared SPD1168X / SPD1305X overrides; catalog classes keep their own slugs."""

    def __init__(self, transport: Transport, config: dict[str, Any]) -> None:
        super().__init__(transport, config)
        self._channel_count = 1

    def _ch(self, channel: int) -> str:
        ch = self._require_channel(channel)
        return f"CH{ch}"

    def set_voltage(self, voltage: float, *, channel: int = 1) -> None:
        tag = self._ch(channel)
        self._scpi.write(f"{tag}:VOLT {voltage:g}")

    def set_current_limit(self, current: float, *, channel: int = 1) -> None:
        tag = self._ch(channel)
        self._scpi.write(f"{tag}:CURR {current:g}")

    def set_output(self, enabled: bool, *, channel: int = 1) -> None:
        tag = self._ch(channel)
        self._scpi.write(f"OUTP {tag},ON" if enabled else f"OUTP {tag},OFF")

    def get_voltage(self, *, channel: int = 1) -> float:
        tag = self._ch(channel)
        return self._scpi.query_float(f"{tag}:VOLT?")

    def get_current_limit(self, *, channel: int = 1) -> float:
        tag = self._ch(channel)
        return self._scpi.query_float(f"{tag}:CURR?")

    def get_output(self, *, channel: int = 1) -> bool:
        tag = self._ch(channel)
        return bool(int(float(self._scpi.query(f"OUTP? {tag}"))))

    def measure_voltage(self, *, channel: int = 1) -> float:
        tag = self._ch(channel)
        return self._scpi.query_float(f"MEAS:VOLT? {tag}")

    def measure_current(self, *, channel: int = 1) -> float:
        tag = self._ch(channel)
        return self._scpi.query_float(f"MEAS:CURR? {tag}")


class SiglentSpd3303(SiglentSpdSingle):
    """SPD3000X Quick Start, pp.29?34: explicit channels and status bitmap.

    https://siglentna.com/wp-content/uploads/dlm_uploads/2017/10/SPD3303X_QuickStart_QS0503X-E01B-1.pdf
    CH3 permits output switching only; it is not an adjustable CH1/CH2.
    """

    def __init__(self, transport: Transport, config: dict[str, Any]) -> None:
        count = resolve_channel_count(config, default=3)
        if count not in (1, 2, 3):
            raise EquipmentCapabilityError("SPD3303X/X-E has three outputs")
        GenericPSU.__init__(self, transport, {**config, "channels": count})

    def _ch(self, channel: int) -> str:
        ch = self._require_channel(channel)
        if ch == 3:
            raise EquipmentCapabilityError("SPD3303 CH3 supports output switching only")
        return f"CH{ch}"

    def _apply_channel(self, channel: int) -> int:
        tag = self._ch(channel)
        self._scpi.write(f"INST {tag}")
        return channel

    def set_output(self, enabled: bool, *, channel: int = 1) -> None:
        ch = self._require_channel(channel)
        self._scpi.write(f"OUTP CH{ch},{'ON' if enabled else 'OFF'}")

    def _status(self, channel: int) -> int:
        self._ch(channel)
        raw = self._scpi.query("SYST:STAT?").strip()
        try:
            value = int(raw, 16)
            if not 0 <= value <= 0x3FF:
                raise ValueError("out of range")
        except ValueError as exc:
            raise EquipmentResponseError(f"invalid SPD3303 status: {raw!r}") from exc
        return value

    def get_output(self, *, channel: int = 1) -> bool:
        # Output flags occupy bits 4 and 5 for CH1 and CH2.
        return bool(self._status(channel) & (1 << (channel + 3)))

    def get_regulation_mode(self, *, channel: int = 1) -> str:
        # Regulation flags occupy bits 0 and 1 (0=CV, 1=CC).
        return "cc" if self._status(channel) & (1 << (channel - 1)) else "cv"

    def measure_power_w(self, *, channel: int = 1) -> float:
        return self._scpi.query_float(f"MEAS:POW? {self._ch(channel)}")

    def set_tracking_mode(self, mode: str, *, channel: int = 1) -> None:
        self._ch(channel)
        modes = {"independent": 0, "series": 1, "parallel": 2, "0": 0, "1": 1, "2": 2}
        token = mode.strip().lower()
        if token not in modes:
            raise EquipmentCapabilityError(f"unsupported SPD3303 tracking mode {mode!r}")
        self._scpi.write(f"OUTP:TRACK {modes[token]}")
