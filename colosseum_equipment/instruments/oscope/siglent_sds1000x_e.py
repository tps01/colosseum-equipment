"""Siglent SDS1000X-E oscilloscope commands.

Command strings from SCPI-Instrument-Control legacy dialect
(``TDIV``, ``TRIG_MODE``, ``C{{ch}}:PAVA?``).
"""

from __future__ import annotations

from colosseum_equipment.instruments.oscope.generic import GenericOscope
from colosseum_equipment.protocols.scpi import wait_opc


class SiglentSds1000xE(GenericOscope):
    """Shared SDS1000X-E overrides; catalog classes keep their own slugs."""

    def set_timebase_scale(self, seconds_per_div: float) -> None:
        self._scpi.write(f"TDIV {seconds_per_div}")

    def single_acquire(self) -> None:
        self._scpi.write("TRIG_MODE SINGLE")
        wait_opc(self._scpi)

    def measure_vpp(self, channel: int = 1) -> float:
        raw = self._scpi.query(f"C{channel}:PAVA? PKPK")
        value = raw.split(",")[-1].strip()
        for unit in ("V", "S", "HZ", "%", "A"):
            value = value.replace(unit, "").replace(unit.lower(), "")
        return float(value)
