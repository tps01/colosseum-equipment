"""Rohde & Schwarz SMBV100B vector signal generator.

Manual: R&S SMBV100B User Manual (free PDF on rohde-schwarz.com).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from colosseum_equipment.instruments.registry import instrument_model
from colosseum_equipment.instruments.vsg.generic import GenericVSG
from colosseum_equipment.protocols.scpi import wait_opc

if TYPE_CHECKING:
    from colosseum_equipment.transports.base import Transport


@instrument_model("vsg", "rohde-smbv100b")
class RohdeSmbv100bVsg(GenericVSG):
    """SMBV100B overrides for RF and baseband ARB playback."""

    def __init__(self, transport: Transport, config: dict[str, Any]) -> None:
        super().__init__(transport, config)
        self._model = "rohde-smbv100b"

    def set_frequency(self, frequency: float) -> None:
        self._scpi.write(f"SOUR:FREQ {frequency:.6f}")

    def set_power(self, power_dbm: float) -> None:
        self._scpi.write(f"SOUR:POW {power_dbm:.3f}")

    def set_output(self, enabled: bool) -> None:
        self._scpi.write("OUTP ON" if enabled else "OUTP OFF")

    def select_waveform(self, remote_name: str) -> None:
        self._scpi.write(f'SOUR:BB:ARB:WAV:SEL "{remote_name}"')

    def set_arb_state(self, enabled: bool) -> None:
        self._scpi.write("SOUR:BB:ARB:STAT ON" if enabled else "SOUR:BB:ARB:STAT OFF")
        self._scpi.write("SOUR:BB:STAT ON" if enabled else "SOUR:BB:STAT OFF")

    def play_iq(
        self,
        filename: str,
        center_freq_hz: float,
        amplitude_dbm: float,
        sample_clock_hz: float,
    ) -> None:
        self.select_waveform(filename)
        self.set_frequency(center_freq_hz)
        self.set_power(amplitude_dbm)
        self._scpi.write(f"SOUR:BB:ARB:CLOCK {sample_clock_hz:.6f}")
        self.set_arb_state(True)
        self.set_output(True)
        wait_opc(self._scpi)

    def measure_frequency(self) -> float:
        return self._scpi.query_float("SOUR:FREQ?")

    def measure_power(self) -> float:
        return self._scpi.query_float("SOUR:POW?")
