"""Swept spectrum-mode operation on Keysight X-Series and PSA analyzers.

Manual: Keysight X-Series Spectrum Analyzer Measurement Application SCPI
reference (N9060); E4440A PSA programming reference. No licensed apps assumed.
"""

from __future__ import annotations

import math

from colosseum_equipment.exceptions import EquipmentResponseError
from colosseum_equipment.instruments._capabilities import supported_commands, unsupported
from colosseum_equipment.instruments.registry import _confirmed_generic_commands, instrument_model
from colosseum_equipment.instruments.speca.generic import GenericSpecA
from colosseum_equipment.instruments.speca.trace_csv import frequency_axis, parse_trace_amplitudes



_SPECTRUM_COMMANDS = (
    "align_all",
    "set_center_frequency",
    "set_start_frequency",
    "set_stop_frequency",
    "set_span",
    "set_rbw",
    "set_vbw",
    "set_sweep_time",
    "set_sweep_points",
    "set_detector",
    "set_attenuation_db",
    "set_auto_attenuation",
    "set_reference_level",
    "toggle_marker",
    "peak_search",
    "set_marker_frequency",
    "measure_marker_frequency",
    "measure_marker_power",
    "preset",
    "set_continuous_sweep",
    "arm_sweep",
    "wait_complete",
    "abort",
    "single_sweep",
    "save_trace_data",
    "measure_bw",
    "measure_center_frequency_hz",
    "measure_trace_power_at_frequency",
    "next_peak_right",
    "next_peak_left",
    "next_highest_peak",
    "set_marker_to_center",
    "toggle_delta_marker",
    "measure_marker_delta_frequency",
    "measure_marker_delta_power",
    "set_trace_mode",
    "set_averaging_count",
    "set_average_type",
)


@instrument_model(
    "speca",
    "keysight-n9000a",
    "keysight-n9010a",
    "keysight-n9010b",
    "keysight-n9020a",
    "keysight-n9020b",
    "keysight-n9030a",
    "keysight-e4440a",
)
@supported_commands(*_SPECTRUM_COMMANDS)
@_confirmed_generic_commands(*_SPECTRUM_COMMANDS)
class KeysightSpectrumAnalyzer(GenericSpecA):
    """Spectrum mode only; scalar markers and linear-frequency trace CSV."""

    def align_all(self) -> None:
        if self._model == "keysight-e4440a":
            unsupported(self._model, "align_all")
        self._scpi.align_all("CAL:ALL?", success_code=0)

    def preset(self) -> None:
        self._scpi.write("INST:SEL SA")
        super().preset()
        self._scpi.write("UNIT:POW DBM")

    def set_detector(self, detector: str) -> None:
        command = "DET" if self._model == "keysight-e4440a" else "DET:TRAC1"
        self._scpi.write(f"{command} {detector}")

    def arm_sweep(self) -> None:
        self._scpi.write("TRIG:SOUR IMM")
        super().arm_sweep()

    def single_sweep(self) -> None:
        self.arm_sweep()
        self.wait_complete(timeout_s=float(self._config.get("timeout", 60.0)))

    def _expanded(self, operation: str) -> None:
        # PSA shares only the original audited subset, not X-Series extensions.
        if self._model == "keysight-e4440a":
            unsupported(self._model, operation, detail="X-Series extension; PSA dialect unverified")

    def _marker(self, marker: int) -> str:
        self._expanded("extended_marker_control")
        if isinstance(marker, bool) or not isinstance(marker, int) or not 1 <= marker <= 12:
            raise ValueError("X-Series marker number must be 1..12")
        return f"CALC:MARK{marker}"

    def next_peak_right(self, marker: int = 1) -> None:
        self._scpi.write(f"{self._marker(marker)}:MAX:RIGH")

    def next_peak_left(self, marker: int = 1) -> None:
        self._scpi.write(f"{self._marker(marker)}:MAX:LEFT")

    def next_highest_peak(self, marker: int = 1) -> None:
        self._scpi.write(f"{self._marker(marker)}:MAX:NEXT")

    def set_marker_to_center(self, marker: int = 1) -> None:
        command = self._marker(marker)
        center = self._scpi.query_float("FREQ:CENT?")
        self._scpi.write(f"{command}:X {center:.6f}")

    def toggle_delta_marker(self, marker: int, enabled: bool) -> None:
        self._scpi.write(f"{self._marker(marker)}:MODE {'DELT' if enabled else 'POS'}")

    def measure_marker_delta_frequency(self, marker: int = 1) -> float:
        command = self._marker(marker)
        self._scpi.require_setting(f"{command}:MODE?", "DELT")
        return self._scpi.query_float(f"{command}:X?")

    def measure_marker_delta_power(self, marker: int = 1) -> float:
        command = self._marker(marker)
        self._scpi.require_setting("UNIT:POW?", "DBM")
        self._scpi.require_setting(f"{command}:MODE?", "DELT")
        return self._scpi.query_float(f"{command}:Y?")

    def set_trace_mode(self, trace: int, mode: str) -> None:
        self._expanded("set_trace_mode")
        if isinstance(trace, bool) or not isinstance(trace, int) or not 1 <= trace <= 6:
            raise ValueError("X-Series trace number must be 1..6")
        token = mode.strip().upper()
        aliases = {"WRITE": "WRIT", "MAXHOLD": "MAXH", "MINHOLD": "MINH", "AVERAGE": "AVER", "BLANK": "BLAN"}
        token = aliases.get(token, token)
        if token not in {"WRIT", "VIEW", "MAXH", "MINH", "AVER", "BLAN"}:
            raise ValueError("invalid X-Series trace mode")
        self._scpi.write(f"TRAC{trace}:MODE {token}")

    def set_averaging_count(self, count: int) -> None:
        self._expanded("set_averaging_count")
        if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= 10000:
            raise ValueError("X-Series average count must be 1..10000")
        self._scpi.write(f"AVER:COUN {count}")

    def set_average_type(self, average_type: str) -> None:
        self._expanded("set_average_type")
        token = average_type.strip().upper()
        if token not in {"LOG", "RMS", "SCAL"}:
            raise ValueError("X-Series average type must be LOG, RMS or SCAL")
        self._scpi.write(f"AVER:TYPE {token}")

    def _fetch_trace(
        self,
        trace: int,
        *,
        include_frequency: bool = True,
    ) -> tuple[list[float], list[float]]:
        maximum = 3 if self._model == "keysight-e4440a" else 6
        if not 1 <= trace <= maximum:
            raise ValueError(f"trace must be between 1 and {maximum}")
        with self._scpi.temporary_settings(('FORM:DATA', 'ASC')):
            self._scpi.require_setting("UNIT:POW?", "DBM")
            # Fetch held/averaged data without changing its trace mode.
            center = self._scpi.query_float("FREQ:CENT?")
            span = self._scpi.query_float("FREQ:SPAN?")
            values = parse_trace_amplitudes(self._scpi.query(f"TRAC:DATA? TRACE{trace}"))
            count = int(self._scpi.query_float("SWE:POIN?"))
            if not values or len(values) != count or any(not math.isfinite(v) for v in values):
                raise EquipmentResponseError("trace length differs from configured sweep points")
            if not math.isfinite(center) or not math.isfinite(span):
                raise EquipmentResponseError("invalid spectrum frequency axis")
            if span <= 0 and include_frequency:
                raise EquipmentResponseError("zero-span trace has a time axis; frequency CSV unavailable")
            axis = (
                frequency_axis(center, span, len(values)) if include_frequency else [float(index) for index in range(count)]
            )
            return axis, values

    def close(self) -> None:
        self._scpi._transport.close()
