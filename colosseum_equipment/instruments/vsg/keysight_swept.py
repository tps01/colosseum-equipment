"""PSG/MXG sourcing, step/list sweeps and MXG vector playback.

References: E8251-90256 (PSG C), E8251-90356 (PSG D), N5180-90004
(MXG A), N5180-90057 (MXG B).
"""
from __future__ import annotations

import math

from colosseum_equipment.instruments._capabilities import supported_commands, unsupported
from colosseum_equipment.instruments.registry import _confirmed_generic_commands, instrument_model
from colosseum_equipment.instruments.vsg.generic import GenericVSG
from colosseum_equipment.instruments.vsg.waveform_upload import _waveform_name
from colosseum_equipment.protocols.scpi import wait_opc

_COMMANDS = (
    "set_frequency", "set_power", "set_output", "measure_frequency", "measure_power_dbm",
    "measure_output_state", "preset", "wait_complete", "set_ref_source", "set_alc",
    "set_attenuation", "set_phase", "set_output_blanking", "freq_sweep", "amplitude_sweep",
    "step_power", "configure_list", "set_modulation", "set_pulsemod_output",
    "pulse_source", "set_pulse_period", "set_pulse_width", "select_waveform", "set_arb_state",
    "set_arb_sample_clock", "set_arb_trigger_source", "arm_arb_trigger", "play_iq",
    "upload_waveform", "delete_waveform", "delete_all_waveforms",
)
_MAX_LIST_POINTS = 3201
_MAX_STEP_POINTS = 65535


@instrument_model("vsg", "keysight-e8257c", "keysight-e8257d", "keysight-n5183a", "keysight-n5183b")
@supported_commands(*_COMMANDS)
@_confirmed_generic_commands(*_COMMANDS)
class KeysightSweptGenerator(GenericVSG):
    """Analog PSG/MXG controls; ARB requires N5182B with a baseband option.

    Sweep methods start continuous sweeps, but never enable RF. configure_list
    loads points without starting acquisition. AM/FM/PM and pulse controls use
    the existing panel source/depth settings; they do not invent modulation defaults.
    """

    def _require_option(self, operation: str, options: set[str]) -> None:
        installed = {item.strip().strip('"').upper() for item in self._scpi.query("*OPT?").split(",")}
        if not installed & options:
            unsupported(self._model, operation, detail=f"requires installed option {'/'.join(sorted(options))}")

    def _require_arb(self, operation: str) -> None:
        if self._model != "keysight-n5182b":
            unsupported(self._model, operation, detail="requires vector N5182B")
        self._require_option(operation, {"656", "657"})

    def set_frequency(self, frequency: float) -> None:
        if not math.isfinite(frequency) or frequency <= 0:
            raise ValueError("frequency must be finite and positive")
        self._scpi.write("FREQ:MODE CW")
        self._scpi.write(f"FREQ:CW {frequency:.6f}")

    def set_power(self, power_dbm: float) -> None:
        if not math.isfinite(power_dbm):
            raise ValueError("power must be finite")
        self._scpi.write("UNIT:POW DBM")
        self._scpi.write("POW:MODE FIX")
        self._scpi.write(f"POW:AMPL {power_dbm:.3f}DBM")

    def measure_power_dbm(self) -> float:
        self._scpi.require_setting("UNIT:POW?", "DBM")
        return self._scpi.query_float("POW:AMPL?")

    def set_phase(self, phase_deg: float) -> None:
        if not math.isfinite(phase_deg):
            raise ValueError("phase must be finite")
        self._scpi.write(f"PHAS {phase_deg:.3f}DEG")

    def set_attenuation(self, attenuation_db: float) -> None:
        if not math.isfinite(attenuation_db) or attenuation_db < 0:
            raise ValueError("attenuation must be finite and nonnegative")
        self._scpi.write("POW:ATT:AUTO OFF")
        self._scpi.write(f"POW:ATT {attenuation_db:.3f}")

    def set_output_blanking(self, enabled: bool) -> None:
        self._scpi.write(f"OUTP:BLAN:STAT {'ON' if enabled else 'OFF'}")

    def set_ref_source(self, source: str) -> None:
        token = source.strip().upper()
        token = {"INTERNAL": "INT", "EXTERNAL": "EXT"}.get(token, token)
        if token not in {"INT", "EXT"}:
            raise ValueError("reference source must be INT or EXT")
        self._scpi.write(f"ROSC:SOUR {token}")

    def _step_sweep(self, start: float, stop: float, points: int, dwell_s: float, *, frequency: bool) -> None:
        if not all(math.isfinite(v) for v in (start, stop, dwell_s)):
            raise ValueError("sweep values must be finite")
        if isinstance(points, bool) or not isinstance(points, int) or not 2 <= points <= _MAX_STEP_POINTS:
            raise ValueError(f"step sweep points must be 2..{_MAX_STEP_POINTS}")
        # PSG dwell resolution/minimum differ from MXG; do not rely on coercion.
        psg = self._model.startswith("keysight-e8257")
        minimum_dwell = 0.001 if psg else 0.0001
        maximum_dwell = 60 if psg else 100
        if not minimum_dwell <= dwell_s <= maximum_dwell:
            raise ValueError(f"step dwell must be {minimum_dwell}..{maximum_dwell} seconds")
        if psg and not math.isclose(dwell_s * 1000, round(dwell_s * 1000), abs_tol=1e-9):
            raise ValueError("PSG step dwell must use whole milliseconds")
        if frequency and min(start, stop) <= 0:
            raise ValueError("sweep frequencies must be positive")
        axis = "FREQ" if frequency else "POW"
        other = "POW" if frequency else "FREQ"
        self._scpi.write("INIT:CONT OFF")
        self._scpi.write("LIST:TYPE STEP")
        self._scpi.write("LIST:MODE AUTO")
        if not psg:
            self._scpi.write("SWE:SPAC LIN")
        if not frequency:
            self._scpi.write("UNIT:POW DBM")
        self._scpi.write(f"{axis}:STAR {min(start, stop):.6f}")
        self._scpi.write(f"{axis}:STOP {max(start, stop):.6f}")
        self._scpi.write(f"LIST:DIR {'UP' if stop >= start else 'DOWN'}")
        self._scpi.write(f"SWE:POIN {points}")
        self._scpi.write(f"SWE:DWEL {dwell_s:.9f}")
        self._scpi.write(f"{other}:MODE {'FIX' if frequency else 'CW'}")
        self._scpi.write(f"{axis}:MODE LIST")
        self._scpi.write("LIST:TRIG:SOUR IMM")
        self._scpi.write("TRIG:SOUR IMM")
        self._scpi.write("INIT:CONT ON")

    def freq_sweep(self, start_hz: float, stop_hz: float, points: int, dwell_s: float) -> None:
        self._step_sweep(start_hz, stop_hz, points, dwell_s, frequency=True)

    def amplitude_sweep(self, start_dbm: float, stop_dbm: float, points: int, dwell_s: float) -> None:
        self._step_sweep(start_dbm, stop_dbm, points, dwell_s, frequency=False)

    def step_power(self, start_dbm: float, stop_dbm: float, step_db: float, interval_s: float) -> None:
        if not all(math.isfinite(v) for v in (start_dbm, stop_dbm, step_db, interval_s)) or step_db <= 0:
            raise ValueError("power steps must be finite with a positive step")
        steps = abs(stop_dbm - start_dbm) / step_db
        points = round(steps) + 1
        if not math.isclose(steps, round(steps), abs_tol=1e-9):
            raise ValueError("power span must be a whole number of step_db increments")
        self.amplitude_sweep(start_dbm, stop_dbm, points, interval_s)

    def configure_list(self, frequencies: list[float], powers: list[float] | None = None) -> None:
        if not 1 <= len(frequencies) <= _MAX_LIST_POINTS or any(not math.isfinite(v) or v <= 0 for v in frequencies):
            raise ValueError(f"frequency list must contain 1..{_MAX_LIST_POINTS} finite positive values")
        if powers is not None and (len(powers) != len(frequencies) or any(not math.isfinite(v) for v in powers)):
            raise ValueError("power list must be finite and match frequency list length")
        self._scpi.write("INIT:CONT OFF")
        self._scpi.write("LIST:TYPE LIST")
        self._scpi.write("LIST:MODE AUTO")
        self._scpi.write("LIST:DIR UP")
        if powers is not None:
            self._scpi.write("UNIT:POW DBM")
        self._scpi.write("LIST:FREQ " + ",".join(f"{value:.6f}" for value in frequencies))
        if powers is not None:
            self._scpi.write("LIST:POW " + ",".join(f"{value:.3f}" for value in powers))
        self._scpi.write("FREQ:MODE LIST")
        self._scpi.write(f"POW:MODE {'LIST' if powers is not None else 'FIX'}")

    def set_modulation(self, enabled: bool, modulation_type: str = "none") -> None:
        token = modulation_type.strip().upper()
        token = {"PHASE": "PM", "PHAS": "PM", "DIGITAL": "DM"}.get(token, token)
        if token not in {"NONE", "OFF", "AM", "FM", "PM", "DM"}:
            raise ValueError("modulation type must be none, AM, FM, PM or DM")
        if token == "DM":
            self._require_arb("set_modulation")
        elif token in {"AM", "FM", "PM"}:
            self._require_option("set_modulation", {"UNT"})
        if token not in {"NONE", "OFF"}:
            self._scpi.write(f"{token}:STAT {'ON' if enabled else 'OFF'}")
        self._scpi.write(f"OUTP:MOD {'ON' if enabled else 'OFF'}")

    def _require_pulse(self, operation: str) -> None:
        if self._model == "keysight-e8257c":
            return  # Model capability in E8251-90256, rather than an option.
        options = {"UNU", "UNW"} if self._model == "keysight-e8257d" else {"UNW"}
        self._require_option(operation, options)

    def set_pulsemod_output(self, enabled: bool) -> None:
        self._require_pulse("set_pulsemod_output")
        self._scpi.write(f"PULM:STAT {'ON' if enabled else 'OFF'}")

    def pulse_source(self, source: str) -> None:
        token = source.strip().upper()
        if token not in {"PULSE", "SQUARE", "EXT1"}:
            raise ValueError("pulse source must be PULSE, SQUARE or EXT1")
        self._require_pulse("pulse_source")
        if token == "EXT1":
            self._scpi.write("PULM:SOUR EXT")
        else:
            self._scpi.write("PULM:SOUR INT")
            self._scpi.write(f"PULM:SOUR:INT {'SQU' if token == 'SQUARE' else 'FRUN'}")

    def set_pulse_period(self, period_s: float) -> None:
        if not math.isfinite(period_s) or period_s <= 0:
            raise ValueError("pulse period must be finite and positive")
        self._require_pulse("set_pulse_period")
        self._scpi.write(f"PULM:INT:PER {period_s:.9f}")

    def set_pulse_width(self, width_s: float) -> None:
        if not math.isfinite(width_s) or width_s <= 0:
            raise ValueError("pulse width must be finite and positive")
        self._require_pulse("set_pulse_width")
        self._scpi.write(f"PULM:INT:PWID {width_s:.9f}")

    def select_waveform(self, remote_name: str) -> None:
        self._require_arb("select_waveform")
        super().select_waveform(_waveform_name(remote_name))

    def set_arb_state(self, enabled: bool) -> None:
        self._require_arb("set_arb_state")
        super().set_arb_state(enabled)

    def set_arb_sample_clock(self, sample_clock_hz: float) -> None:
        if not math.isfinite(sample_clock_hz) or sample_clock_hz <= 0:
            raise ValueError("ARB clock must be finite and positive")
        self._require_arb("set_arb_sample_clock")
        super().set_arb_sample_clock(sample_clock_hz)

    def set_arb_trigger_source(self, source: str) -> None:
        token = source.strip().upper()
        if token not in {"BUS", "EXT", "KEY"}:
            raise ValueError("ARB trigger source must be BUS, EXT or KEY")
        self._require_arb("set_arb_trigger_source")
        self._scpi.write(f"RAD:ARB:TRIG:SOUR {token}")

    def arm_arb_trigger(self) -> None:
        self._require_arb("arm_arb_trigger")
        self._scpi.write("*TRG")

    def play_iq(self, filename: str, center_freq_hz: float, amplitude_dbm: float, sample_clock_hz: float) -> None:
        _waveform_name(filename)
        if not all(math.isfinite(v) for v in (center_freq_hz, amplitude_dbm, sample_clock_hz)) or min(center_freq_hz, sample_clock_hz) <= 0:
            raise ValueError("playback needs finite power and positive frequency/clock")
        self._require_arb("play_iq")
        super().select_waveform(filename)
        self.set_frequency(center_freq_hz)
        self.set_power(amplitude_dbm)
        super().set_arb_sample_clock(sample_clock_hz)
        super().set_arb_state(True)
        self._scpi.write("OUTP:MOD ON")

    def upload_waveform(self, local_path: str, remote_name: str, *, first_last_blanking: bool = False, method: str = "auto") -> None:
        self._require_arb("upload_waveform")
        _waveform_name(remote_name)
        super().upload_waveform(local_path, remote_name, first_last_blanking=first_last_blanking, method=method)

    def delete_waveform(self, remote_name: str) -> None:
        self._require_arb("delete_waveform")
        super().delete_waveform(_waveform_name(remote_name))

    def delete_all_waveforms(self) -> None:
        self._require_arb("delete_all_waveforms")
        self._scpi.write("MMEM:DEL:WFM")
        wait_opc(self._scpi)
