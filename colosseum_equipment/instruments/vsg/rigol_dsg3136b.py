"""Rigol DSG3136B signal generator commands.

Command strings from the MIT QCoDeS contrib file ``Rigol_DSG3136B``.
"""

from __future__ import annotations

from colosseum_equipment.instruments.vsg.generic import GenericVSG


class RigolDsg3136bFamily(GenericVSG):
    """DSG3136B overrides; the catalog class keeps the registered slug."""

    def set_frequency(self, frequency: float) -> None:
        self._scpi.write(f"FREQ {frequency:.2f}")

    def set_power(self, power_dbm: float) -> None:
        self._scpi.write(f"LEV {power_dbm:.2f}")

    def set_output(self, enabled: bool) -> None:
        self._scpi.write(":OUTPut:STATe ON" if enabled else ":OUTPut:STATe OFF")
