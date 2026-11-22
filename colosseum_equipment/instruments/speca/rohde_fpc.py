"""FPC1500 spectrum mode; 1178.4130.02 v13, remote control ch.20.

https://www.batronix.com/files/Rohde-%26-Schwarz/Spectrum-Analyser/FPC1500/FPC_UserManual_en.pdf
"""

from __future__ import annotations

import math

from colosseum_equipment.exceptions import EquipmentResponseError
from colosseum_equipment.instruments._capabilities import supported_commands
from colosseum_equipment.instruments.registry import _confirmed_generic_commands, instrument_model
from colosseum_equipment.instruments.speca.generic import GenericSpecA
from colosseum_equipment.instruments.speca.trace_csv import parse_trace_amplitudes



_FPC_COMMANDS = (
    "set_center_frequency",
    "set_start_frequency",
    "set_stop_frequency",
    "set_span",
    "set_rbw",
    "set_vbw",
    "set_sweep_time",
    "set_reference_level",
    "set_continuous_sweep",
    "arm_sweep",
    "single_sweep",
    "wait_complete",
    "save_trace_data",
    "measure_bw",
    "measure_center_frequency_hz",
    "measure_trace_power_at_frequency",
    "toggle_marker",
    "peak_search",
    "set_marker_frequency",
    "measure_marker_frequency",
    "measure_marker_power",
    "next_highest_peak",
    "set_marker_to_center",
    "toggle_delta_marker",
    "measure_marker_delta_frequency",
    "measure_marker_delta_power",
    "set_trace_mode",
    "set_detector",
    "set_averaging_count",
    "set_attenuation_db",
    "set_auto_attenuation",
    "abort",
)


@instrument_model("speca", "rohde-fpc1500")
@supported_commands(*_FPC_COMMANDS)
@_confirmed_generic_commands(*_FPC_COMMANDS)
class RohdeFpc1500(GenericSpecA):
    """Spectrum only; no VNA, receiver, tracking generator or licensed measurements."""


    def set_reference_level(self, level_dbm: float) -> None:
        self._scpi.write(f"DISP:TRAC:Y:RLEV {level_dbm}DBM")

    def single_sweep(self) -> None:
        self.arm_sweep()
        self.wait_complete(timeout_s=float(self._config.get("timeout", 60.0)))

    def _marker_command(self, marker: int, *, delta: bool = False) -> str:
        minimum = 2 if delta else 1
        if isinstance(marker, bool) or not isinstance(marker, int) or not minimum <= marker <= 6:
            raise ValueError(f"FPC marker number must be {minimum}..6")
        return f"CALC:{'DELT' if delta else 'MARK'}{marker}"

    def set_marker_frequency(self, marker: int, frequency_hz: float) -> None:
        command = self._marker_command(marker)
        if not math.isfinite(frequency_hz) or frequency_hz < 0:
            raise ValueError("marker frequency must be finite and nonnegative")
        self._scpi.write(f"{command}:X {frequency_hz:.6f}")

    def measure_marker_power(self, marker: int = 1) -> float:
        command = self._marker_command(marker)
        self._scpi.require_setting("UNIT:POW?", "DBM")
        return self._scpi.query_float(f"{command}:Y?")

    def next_highest_peak(self, marker: int = 1) -> None:
        self._scpi.write(f"{self._marker_command(marker)}:MAX:NEXT")

    def set_marker_to_center(self, marker: int = 1) -> None:
        command = self._marker_command(marker)
        center = self._scpi.query_float("FREQ:CENT?")
        self._scpi.write(f"{command}:X {center:.6f}")

    def toggle_delta_marker(self, marker: int, enabled: bool) -> None:
        command = self._marker_command(marker, delta=True)
        # A normal marker command converts a delta marker back to normal.
        if not enabled:
            command = self._marker_command(marker)
        self._scpi.write(f"{command}:STAT ON")

    def measure_marker_delta_frequency(self, marker: int = 1) -> float:
        return self._scpi.query_float(f"{self._marker_command(marker, delta=True)}:X:REL?")

    def measure_marker_delta_power(self, marker: int = 1) -> float:
        command = self._marker_command(marker, delta=True)
        self._scpi.require_setting("UNIT:POW?", "DBM")
        return self._scpi.query_float(f"{command}:Y?")

    def set_trace_mode(self, trace: int, mode: str) -> None:
        if isinstance(trace, bool) or not isinstance(trace, int) or trace not in (1, 2):
            raise ValueError("FPC spectrum traces are 1 or 2")
        token = mode.strip().upper()
        token = {"WRITE": "WRIT", "MAXHOLD": "MAXH", "MINHOLD": "MINH", "AVERAGE": "AVER", "BLANK": "BLAN"}.get(token, token)
        if token not in {"WRIT", "VIEW", "MAXH", "MINH", "AVER", "BLAN"}:
            raise ValueError("invalid FPC trace mode")
        self._scpi.write(f"DISP:TRAC{trace}:MODE {token}")

    def set_detector(self, detector: str) -> None:
        token = detector.strip().upper()
        if token not in {"POS", "NEG", "SAMP", "RMS", "AVER", "APE"}:
            raise ValueError("invalid FPC spectrum detector")
        self._scpi.write("DET1:AUTO OFF")
        self._scpi.write(f"DET1 {token}")

    def set_averaging_count(self, count: int) -> None:
        if isinstance(count, bool) or not isinstance(count, int) or not 0 <= count <= 999:
            raise ValueError("FPC average count must be 0..999")
        self._scpi.write(f"SWE:COUN {count}")

    def set_attenuation_db(self, attenuation_db: float) -> None:
        if not math.isfinite(attenuation_db) or not 0 <= attenuation_db <= 40 or attenuation_db % 5:
            raise ValueError("FPC attenuation must be 0..40 dB in 5 dB steps")
        self._scpi.write(f"INP:ATT {attenuation_db:.3f}")

    def abort(self) -> None:
        # FPC manual requires synchronization before subsequent commands.
        self._scpi.write("ABOR;*WAI")

    def _fetch_trace(
        self,
        trace: int,
        *,
        include_frequency: bool = True,
    ) -> tuple[list[float], list[float]]:
        if trace not in (1, 2):
            raise ValueError("FPC spectrum traces are 1 or 2")
        self._scpi.require_setting("UNIT:POW?", "DBM")
        with self._scpi.temporary_settings(('FORM', 'ASC')):
            values = parse_trace_amplitudes(self._scpi.query(f"TRAC:DATA? TRACE{trace}"))
            start = self._scpi.query_float("FREQ:STAR?")
            stop = self._scpi.query_float("FREQ:STOP?")
            if len(values) < 2 or any(not math.isfinite(v) for v in values):
                raise EquipmentResponseError("empty or invalid spectrum data")
            if not math.isfinite(start) or not math.isfinite(stop) or stop <= start:
                raise EquipmentResponseError("frequency CSV requires a positive linear sweep span")
            # Firmware revisions have different fixed trace lengths (631 / 1183).
            axis = [start + i * (stop - start) / (len(values) - 1) for i in range(len(values))]
            return (axis if include_frequency else [float(i) for i in range(len(values))]), values

    def close(self) -> None:
        self._scpi._transport.close()
