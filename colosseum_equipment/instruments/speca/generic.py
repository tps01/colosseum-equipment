from __future__ import annotations

import contextlib
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from colosseum_equipment._paths import resolve_artifact_path
from colosseum_equipment.evidence import record_artifact
from colosseum_equipment.exceptions import EquipmentCapabilityError, EquipmentTimeoutError
from colosseum_equipment.instruments.registry import best_effort_commands, instrument_model
from colosseum_equipment.instruments.speca.bandwidth import measure_bandwidth_hz
from colosseum_equipment.instruments.speca.trace_csv import (
    frequency_axis,
    parse_trace_amplitudes,
    read_trace_power_at_frequency,
    write_trace_csv,
)
from colosseum_equipment.instruments.speca.trace_plot import read_trace_csv, write_trace_plot
from colosseum_equipment.protocols.scpi import SCPIHelper, prepare_fast_sweep, wait_opc

if TYPE_CHECKING:
    from colosseum_equipment.transports.base import Transport


@instrument_model("speca", "generic", extra_optional=("center_freq", "span", "rbw"))
@best_effort_commands
class GenericSpecA:
    """Generic SCPI spectrum analyzer (vendor models extend).

    Acquisition contract (best-effort SCPI dialect):
    - ``arm_sweep`` / ``single_sweep`` arm acquisition; ``single_sweep`` also waits for OPC
    - ``wait_complete`` blocks with a bounded timeout; ``abort`` cancels in progress
    - ``measure_marker_*`` fetch the last completed sweep (do not re-arm)
    - ``save_trace_data`` / ``_fetch_trace`` / ``measure_bw`` without ``trace_path`` take a new sweep
    """

    _model = "generic"

    def __init__(self, transport: Transport, config: dict[str, Any]) -> None:
        self._scpi = SCPIHelper(transport)
        self._config = config
        self._model = str(config.get("model", "generic")).lower()
        self._sweep_id = ""
        if "center_freq" in config:
            self.set_center_frequency(float(config["center_freq"]))
        if "span" in config:
            self.set_span(float(config["span"]))
        if "rbw" in config:
            self.set_rbw(float(config["rbw"]))

    def set_center_frequency(self, frequency: float) -> None:
        self._scpi.write(f"FREQ:CENT {frequency:.6f}")

    def set_start_frequency(self, frequency_hz: float) -> None:
        self._scpi.write(f"FREQ:STAR {frequency_hz:.6f}")

    def set_stop_frequency(self, frequency_hz: float) -> None:
        self._scpi.write(f"FREQ:STOP {frequency_hz:.6f}")

    def set_span(self, span: float) -> None:
        self._scpi.write(f"FREQ:SPAN {span:.6f}")

    def set_rbw(self, rbw: float) -> None:
        self._scpi.write(f"BAND:RES {rbw:.6f}")

    def toggle_marker(self, marker: int, enabled: bool) -> None:
        self._scpi.write(f"CALC:MARK{marker}:STAT {'ON' if enabled else 'OFF'}")

    def peak_search(self, marker: int = 1) -> None:
        self._scpi.write(f"CALC:MARK{marker}:MAX")

    def next_peak_right(self, marker: int = 1) -> None:
        self._scpi.write(f"CALC:MARK{marker}:MAX:NEXT")

    def next_peak_left(self, marker: int = 1) -> None:
        self._scpi.write(f"CALC:MARK{marker}:MAX:PREV")

    def next_highest_peak(self, marker: int = 1) -> None:
        """Move the marker to the next-highest peak (distinct from global ``peak_search``)."""
        self._scpi.write(f"CALC:MARK{marker}:MAX:NH")

    def set_marker_to_center(self, marker: int = 1) -> None:
        """Place a marker at the spectrum center frequency."""
        self._scpi.write(f"CALC:MARK{marker}:X CENT")

    def toggle_delta_marker(self, marker: int, enabled: bool) -> None:
        self._scpi.write(f"CALC:MARK{marker}:DELT:STAT {'ON' if enabled else 'OFF'}")

    def set_marker_delta_reference(self, marker: int, reference_marker: int) -> None:
        self._scpi.write(f"CALC:MARK{marker}:DELT:REF {int(reference_marker)}")

    def measure_marker_delta_frequency(self, marker: int = 1) -> float:
        """Read delta-marker frequency offset in hertz (last sweep; does not re-arm)."""
        return self._scpi.query_float(f"CALC:MARK{marker}:DELT:X?")

    def measure_marker_delta_power(self, marker: int = 1) -> float:
        """Read delta-marker amplitude in dB (last sweep; does not re-arm)."""
        return self._scpi.query_float(f"CALC:MARK{marker}:DELT:Y?")

    def set_attenuation_db(self, attenuation_db: float) -> None:
        self._scpi.write(f"INP:ATT {attenuation_db:.3f}")

    def set_auto_attenuation(self, enabled: bool) -> None:
        self._scpi.write(f"INP:ATT:AUTO {'ON' if enabled else 'OFF'}")

    def toggle_preamp(self, enabled: bool) -> None:
        self._scpi.write(f"INP:GAIN:STAT {'ON' if enabled else 'OFF'}")

    def set_averaging_count(self, count: int) -> None:
        self._scpi.write(f"SWE:COUN {int(count)}")

    def set_average_type(self, average_type: str) -> None:
        self._scpi.write(f"AVER:TYPE {average_type.upper()}")

    def set_sweep_points(self, count: int) -> None:
        self._scpi.write(f"SWE:POIN {int(count)}")

    def toggle_trigger_delay(self, enabled: bool) -> None:
        self._scpi.write(f"TRIG:DEL:STAT {'ON' if enabled else 'OFF'}")

    def set_trigger_delay(self, delay_s: float) -> None:
        self._scpi.write(f"TRIG:DEL {delay_s:.9f}")

    def set_trigger_source(self, source: str) -> None:
        self._scpi.write(f"TRIG:SOUR {source}")

    def user_preset(self) -> None:
        self._scpi.write("*RCL 1")
        wait_opc(self._scpi)

    def set_marker_frequency(self, marker: int, frequency_hz: float) -> None:
        self._scpi.write(f"CALC:MARK{marker}:X {frequency_hz:.6f}")

    def measure_marker_power(self, marker: int = 1) -> float:
        """Read marker amplitude in dBm from the last completed sweep."""
        return self._scpi.query_float(f"CALC:MARK{marker}:Y?")

    def measure_marker_frequency(self, marker: int = 1) -> float:
        """Read marker frequency in hertz from the last completed sweep."""
        return self._scpi.query_float(f"CALC:MARK{marker}:X?")

    def _try_query_float(self, command: str) -> float | None:
        try:
            value = self._scpi.query_float(command)
        except Exception:
            return None
        if value != value:  # NaN
            return None
        return value

    def measure_channel_power_dbm(self, marker: int = 1) -> float:
        """Instrument channel-power result when CALC supports it (fetch; no new sweep)."""
        for command in (
            f"CALC:MARK{marker}:FUNC:POW:RES?",
            "CALC:POW:CHP:POW?",
            "CALC:POW:CHP?",
        ):
            value = self._try_query_float(command)
            if value is not None:
                return value
        raise EquipmentCapabilityError(
            f"speca model `{self._model}` has no supported channel-power CALC query",
        )

    def measure_acpr_db(self, *, side: str = "both") -> float:
        """Adjacent-channel power ratio in dB when limit/ACP CALC exists (fetch)."""
        side_key = side.strip().lower()
        commands = {
            "upper": ("CALC:LIM:ACP:UPP:ACPower?", "CALC:LIM:ACPower:UPP?"),
            "lower": ("CALC:LIM:ACP:LOW:ACPower?", "CALC:LIM:ACPower:LOW?"),
            "both": ("CALC:LIM:ACP:ACPower?", "CALC:LIM:ACPower?"),
        }
        if side_key not in commands:
            raise ValueError(f"unsupported ACPR side: {side}")
        for command in commands[side_key]:
            value = self._try_query_float(command)
            if value is not None:
                return value
        raise EquipmentCapabilityError(
            f"speca model `{self._model}` has no supported ACPR CALC query",
        )

    def measure_obw_hz(
        self,
        start_hz: float,
        stop_hz: float,
        *,
        threshold_db: float = 3.0,
        smoothing_order: int = 0,
        trace: int = 1,
        trace_path: str | Path | None = None,
    ) -> float:
        """Occupied bandwidth in hertz (instrument OBW when available, else host ``measure_bw``)."""
        for command in ("CALC:OBW:BWID?", "CALC:OBW:OBW?", "CALC:OBW:WIDTH?"):
            value = self._try_query_float(command)
            if value is not None and value > 0:
                return value
        return self.measure_bw(
            start_hz,
            stop_hz,
            threshold_db=threshold_db,
            smoothing_order=smoothing_order,
            trace=trace,
            trace_path=trace_path,
        )

    def _fetch_trace(
        self,
        trace: int,
        *,
        include_frequency: bool = True,
    ) -> tuple[list[float], list[float]]:
        prepare_fast_sweep(self._scpi)
        self.single_sweep()
        center = self._scpi.query_float("FREQ:CENT?")
        span = self._scpi.query_float("FREQ:SPAN?")
        raw = self._scpi.query(f"TRAC:DATA? TRACE{trace}")
        amplitudes = parse_trace_amplitudes(raw)
        if include_frequency:
            frequencies = frequency_axis(center, span, len(amplitudes))
        else:
            frequencies = list(range(len(amplitudes)))
        return frequencies, amplitudes

    def save_trace_data(
        self,
        path: str,
        *,
        trace: int = 1,
        include_frequency: bool = True,
        save_plot: bool = False,
        plot_path: str | None = None,
        key: str = "",
        calibration: str | None = None,
    ) -> Path:
        frequencies, amplitudes = self._fetch_trace(trace, include_frequency=include_frequency)
        if calibration is not None:
            from colosseum_equipment import calibration as path_cal

            if not include_frequency:
                raise path_cal.CalibrationError(
                    "save_trace_data with calibration= requires include_frequency=True",
                )
            amplitudes = path_cal.correct_trace_amplitudes(
                frequencies,
                amplitudes,
                key=calibration,
            )
        center = (frequencies[0] + frequencies[-1]) / 2.0 if frequencies else 0.0
        span = frequencies[-1] - frequencies[0] if len(frequencies) > 1 else 0.0
        artifact_path = resolve_artifact_path(path)
        write_trace_csv(
            artifact_path,
            amplitudes,
            center_hz=center if include_frequency else None,
            span_hz=span if include_frequency else None,
            include_frequency=include_frequency,
        )
        self._last_trace_path = artifact_path

        if save_plot or plot_path is not None:
            png_path = resolve_artifact_path(plot_path or str(Path(path).with_suffix(".png")))
            write_trace_plot(artifact_path, png_path)

        evidence_key = key or f"speca_trace_{trace}"
        record_artifact(
            domain="equipment",
            command="save_trace_data",
            key=evidence_key,
            path=artifact_path,
            value={
                "trace": trace,
                "center_hz": center if include_frequency else None,
                "span_hz": span if include_frequency else None,
                "points": len(amplitudes),
                "sweep_id": self._sweep_id,
            },
        )
        return artifact_path

    def measure_bw(
        self,
        start_hz: float,
        stop_hz: float,
        *,
        threshold_db: float = 3.0,
        smoothing_order: int = 0,
        trace: int = 1,
        trace_path: str | Path | None = None,
    ) -> float:
        path = (
            Path(trace_path) if trace_path is not None else getattr(self, "_last_trace_path", None)
        )
        if path is not None:
            frequencies, amplitudes = read_trace_csv(path)
        else:
            frequencies, amplitudes = self._fetch_trace(trace, include_frequency=True)
        return measure_bandwidth_hz(
            frequencies,
            amplitudes,
            start_hz=start_hz,
            stop_hz=stop_hz,
            threshold_db=threshold_db,
            smoothing_order=smoothing_order,
        )

    def measure_trace_power_at_frequency(
        self,
        frequency_hz: float,
        *,
        trace_path: str | Path | None = None,
    ) -> tuple[float, float]:
        path = (
            Path(trace_path) if trace_path is not None else getattr(self, "_last_trace_path", None)
        )
        if path is None:
            raise ValueError("no trace CSV; call save_trace_data first or pass trace_path=")
        return read_trace_power_at_frequency(path, frequency_hz)

    def preset(self) -> None:
        self._scpi.write("*RST")
        wait_opc(self._scpi)

    def set_reference_level(self, level_dbm: float) -> None:
        self._scpi.write(f"DISP:WIND:TRAC:Y:SCAL:RLEV {level_dbm}")

    def set_vbw(self, vbw: float) -> None:
        self._scpi.write(f"BAND:VID {vbw}")

    def set_sweep_time(self, seconds: float) -> None:
        self._scpi.write(f"SWE:TIME {seconds}")

    def set_detector(self, detector: str) -> None:
        self._scpi.write(f"DET {detector}")

    def set_trace_mode(self, trace: int, mode: str) -> None:
        self._scpi.write(f"TRAC{trace}:MODE {mode}")

    def set_continuous_sweep(self, enabled: bool) -> None:
        self._scpi.write(f"INIT:CONT {1 if enabled else 0}")

    def arm_sweep(self) -> None:
        """Arm a single sweep without blocking for completion."""
        self._sweep_id = f"{time.monotonic():.6f}"
        self._scpi.write("INIT:CONT OFF")
        self._scpi.write("INIT:IMM")

    def wait_complete(self, *, timeout_s: float = 60.0) -> None:
        """Block until the current sweep completes or ``timeout_s`` elapses."""
        import contextlib

        deadline = time.monotonic() + timeout_s
        transport = getattr(self._scpi, "_transport", None)
        setter = getattr(transport, "set_timeout_s", None) if transport is not None else None
        prev_timeout = getattr(transport, "_timeout", None) if transport is not None else None
        try:
            while time.monotonic() < deadline:
                remaining = max(0.05, deadline - time.monotonic())
                if callable(setter):
                    with contextlib.suppress(Exception):
                        setter(min(remaining, 1.0))
                try:
                    if self._scpi.query("*OPC?").strip().startswith("1"):
                        return
                except Exception:
                    pass
                time.sleep(0.05)
        finally:
            if callable(setter) and prev_timeout is not None:
                with contextlib.suppress(Exception):
                    setter(float(prev_timeout))
        raise EquipmentTimeoutError(
            f"speca model `{self._model}` sweep did not complete within {timeout_s}s",
        )

    def abort(self) -> None:
        self._scpi.write(":ABOR")

    def single_sweep(self) -> None:
        """Arm a single sweep and wait for completion (OPC)."""
        self.arm_sweep()
        wait_opc(self._scpi)

    def save_screenshot(self, path: str, *, key: str = "") -> Path:
        payload = self._scpi.read_binary_block("HCOP:SDUM:DATA?")
        artifact_path = resolve_artifact_path(path)
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_bytes(payload)
        evidence_key = key or f"speca_screenshot_{self._sweep_id or 'last'}"
        record_artifact(
            domain="equipment",
            command="save_screenshot",
            key=evidence_key,
            path=artifact_path,
            value={"bytes": len(payload), "sweep_id": self._sweep_id},
        )
        return artifact_path

    def close(self) -> None:
        with contextlib.suppress(Exception):
            self._scpi.write("DISP:UPD ON")
        self._scpi._transport.close()
