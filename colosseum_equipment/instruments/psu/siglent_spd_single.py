"""Siglent single-channel SPD1168X / SPD1305X supply commands.

Command strings from PyMeasure ``siglent_spdbase.SPDChannel``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from colosseum_equipment.instruments.psu.generic import GenericPSU

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
