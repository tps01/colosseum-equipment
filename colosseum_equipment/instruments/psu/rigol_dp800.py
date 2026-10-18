"""Rigol DP800-series supply commands.

Command strings from python-ivi ``ivi.scpi.dcpwr`` / ``ivi.rigol.rigolDP800``.
"""

from __future__ import annotations

from colosseum_equipment.instruments.psu.generic import GenericPSU


class RigolDp800(GenericPSU):
    """Shared DP800 overrides; catalog classes keep their own slugs."""

    def _apply_channel(self, channel: int) -> int:
        ch = self._require_channel(channel)
        self._scpi.write(f"instrument:nselect {ch}")
        return ch

    def set_voltage(self, voltage: float, *, channel: int = 1) -> None:
        self._apply_channel(channel)
        self._scpi.write(f"source:voltage:level {voltage:.6f}")

    def set_current_limit(self, current: float, *, channel: int = 1) -> None:
        self._apply_channel(channel)
        self._scpi.write(f"source:current:level {current:.6f}")

    def set_output(self, enabled: bool, *, channel: int = 1) -> None:
        self._apply_channel(channel)
        self._scpi.write("output on" if enabled else "output off")

    def get_voltage(self, *, channel: int = 1) -> float:
        self._apply_channel(channel)
        return self._scpi.query_float("source:voltage:level?")

    def get_current_limit(self, *, channel: int = 1) -> float:
        self._apply_channel(channel)
        return self._scpi.query_float("source:current:level?")

    def get_output(self, *, channel: int = 1) -> bool:
        self._apply_channel(channel)
        return bool(int(float(self._scpi.query("output?"))))

    def measure_voltage(self, *, channel: int = 1) -> float:
        self._apply_channel(channel)
        return self._scpi.query_float("measure:voltage?")

    def measure_current(self, *, channel: int = 1) -> float:
        self._apply_channel(channel)
        return self._scpi.query_float("measure:current?")

    def set_ovp_v(self, voltage: float, *, channel: int = 1) -> None:
        self._apply_channel(channel)
        self._scpi.write(f"source:voltage:protection:level {voltage:.6f}")

    def set_ocp_a(self, current: float, *, channel: int = 1) -> None:
        self._apply_channel(channel)
        self._scpi.write(f"source:current:protection:level {current:.6f}")

    def toggle_ovp(self, enabled: bool, *, channel: int = 1) -> None:
        self._apply_channel(channel)
        self._scpi.write(
            "source:voltage:protection:state on"
            if enabled
            else "source:voltage:protection:state off",
        )

    def toggle_ocp(self, enabled: bool, *, channel: int = 1) -> None:
        self._apply_channel(channel)
        self._scpi.write(
            "source:current:protection:state on"
            if enabled
            else "source:current:protection:state off",
        )

    def get_ovp_v(self, *, channel: int = 1) -> float:
        self._apply_channel(channel)
        return self._scpi.query_float("source:voltage:protection:level?")

    def get_ocp_a(self, *, channel: int = 1) -> float:
        self._apply_channel(channel)
        return self._scpi.query_float("source:current:protection:level?")

    def clear_protection(self, *, channel: int = 1) -> None:
        self._apply_channel(channel)
        self._scpi.write("output:protection:clear")
