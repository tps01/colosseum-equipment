"""Rohde & Schwarz SMBV100B vector signal generator.

Manual: R&S SMBV100B User Manual (free PDF on rohde-schwarz.com).
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import TYPE_CHECKING, Any

from colosseum_equipment.instruments._capabilities import supported_commands, unsupported
from colosseum_equipment.instruments.registry import _confirmed_generic_commands, instrument_model
from colosseum_equipment.instruments.vsg.generic import GenericVSG
from colosseum_equipment.instruments.vsg.waveform_upload import _waveform_name
from colosseum_equipment.protocols.scpi import wait_opc

if TYPE_CHECKING:
    from colosseum_equipment.transports.base import Transport


_COMMANDS = (
    "set_frequency", "set_power", "set_output", "measure_frequency", "measure_power", "measure_power_dbm",
    "measure_output_state", "preset", "wait_complete", "select_waveform", "set_arb_state", "play_iq",
    "set_arb_sample_clock", "set_arb_trigger_source", "arm_arb_trigger", "set_multicarrier", "toggle_multitone",
    "upload_waveform", "delete_waveform", "set_ref_source",
)


@instrument_model("vsg", "rohde-smbv100b")
@supported_commands(*_COMMANDS)
@_confirmed_generic_commands(*_COMMANDS)
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
        self._scpi.write(f'SOUR:BB:ARB:WAV:SEL "{_waveform_name(remote_name)}"')

    def set_arb_state(self, enabled: bool) -> None:
        self._scpi.write("SOUR:BB:ARB:STAT ON" if enabled else "SOUR:BB:ARB:STAT OFF")

    def play_iq(
        self,
        filename: str,
        center_freq_hz: float,
        amplitude_dbm: float,
        sample_clock_hz: float,
    ) -> None:
        _waveform_name(filename)
        if not all(math.isfinite(v) for v in (center_freq_hz, amplitude_dbm, sample_clock_hz)) or min(center_freq_hz, sample_clock_hz) <= 0:
            raise ValueError("playback needs finite power and positive frequency/clock")
        self.select_waveform(filename)
        self.set_frequency(center_freq_hz)
        self.set_power(amplitude_dbm)
        self.set_arb_sample_clock(sample_clock_hz)
        self.set_arb_state(True)
        self.set_output(True)
        wait_opc(self._scpi)

    def measure_frequency(self) -> float:
        return self._scpi.query_float("SOUR:FREQ?")

    def measure_power(self) -> float:
        return self._scpi.query_float("SOUR:POW?")

    def measure_power_dbm(self) -> float:
        return self.measure_power()

    def set_arb_sample_clock(self, sample_clock_hz: float) -> None:
        if not math.isfinite(sample_clock_hz) or sample_clock_hz <= 0:
            raise ValueError("ARB clock must be finite and positive")
        self._scpi.write(f"SOUR:BB:ARB:CLOCK {sample_clock_hz:.6f}")

    def set_arb_trigger_source(self, source: str) -> None:
        token = source.strip().upper()
        token = {"INTERNAL": "INT", "EXTERNAL": "EXT"}.get(token, token)
        if token not in {"INT", "EGT1", "EGC1", "EXT", "BBSY"}:
            raise ValueError("SMBV ARB source must be INT, EGT1, EGC1, EXT or BBSY")
        self._scpi.write(f"SOUR:BB:ARB:TRIG:SOUR {token}")

    def arm_arb_trigger(self) -> None:
        self._scpi.write("SOUR:BB:ARB:TRIG:EXEC")

    def set_multicarrier(self, num_tones: int, spacing_hz: float) -> None:
        if isinstance(num_tones, bool) or not isinstance(num_tones, int) or not 1 <= num_tones <= 160001:
            raise ValueError("SMBV MCCW carrier count must be 1..160001")
        if not math.isfinite(spacing_hz) or spacing_hz < 0:
            raise ValueError("MCCW spacing must be finite and nonnegative")
        self._scpi.write(f"SOUR:BB:MCCW:CARR:COUN {num_tones}")
        self._scpi.write(f"SOUR:BB:MCCW:CARR:SPAC {spacing_hz:.6f}")

    def toggle_multitone(self, enabled: bool) -> None:
        self._scpi.write(f"SOUR:BB:MCCW:STAT {'ON' if enabled else 'OFF'}")

    def upload_waveform(self, local_path: str, remote_name: str, *, first_last_blanking: bool = False, method: str = "auto") -> None:
        _waveform_name(remote_name)
        if method not in {"auto", "tcpip"}:
            unsupported(self._model, "upload_waveform", detail="native waveform upload uses SCPI binary transfer")
        if first_last_blanking:
            unsupported(self._model, "upload_waveform", detail="encode marker blanking in the native .wv file")
        path = Path(local_path)
        if path.suffix.lower() != ".wv" or Path(remote_name).suffix.lower() != ".wv":
            raise ValueError("SMBV upload requires a native R&S .wv file and destination")
        payload = path.read_bytes()
        if not payload.startswith(b"{TYPE: SMU-WV,"):
            raise ValueError("invalid native R&S waveform header")
        self._scpi.write_binary_block(f'MMEM:DATA "{remote_name}",', payload)
        wait_opc(self._scpi)

    def delete_waveform(self, remote_name: str) -> None:
        super().delete_waveform(_waveform_name(remote_name))

    def set_ref_source(self, source: str) -> None:
        token = source.strip().upper()
        token = {"INTERNAL": "INT", "EXTERNAL": "EXT"}.get(token, token)
        if token not in {"INT", "EXT"}:
            raise ValueError("reference source must be INT or EXT")
        self._scpi.write(f"ROSC:SOUR {token}")
