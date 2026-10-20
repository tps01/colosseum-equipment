"""Swept spectrum-mode operation on Keysight X-Series and PSA analyzers.

Manual: Keysight X-Series Spectrum Analyzer Measurement Application SCPI
reference (N9060); E4440A PSA programming reference. No licensed apps assumed.
"""
from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from colosseum_equipment.exceptions import EquipmentResponseError
from colosseum_equipment.instruments._capabilities import supported_commands
from colosseum_equipment.instruments.registry import instrument_model
from colosseum_equipment.instruments.speca.generic import GenericSpecA
from colosseum_equipment.instruments.speca.trace_csv import frequency_axis, parse_trace_amplitudes

if TYPE_CHECKING:
    from colosseum_equipment.transports.base import Transport


@instrument_model(
    "speca", "keysight-n9000a", "keysight-n9010a", "keysight-n9010b", "keysight-n9020a",
    "keysight-n9020b", "keysight-n9030a", "keysight-e4440a",
)
@supported_commands(
    "set_center_frequency", "set_start_frequency", "set_stop_frequency", "set_span", "set_rbw",
    "set_vbw", "set_sweep_time", "set_sweep_points", "set_detector", "set_attenuation_db",
    "set_auto_attenuation", "set_reference_level", "toggle_marker", "peak_search",
    "set_marker_frequency", "measure_marker_frequency", "measure_marker_power", "preset",
    "set_continuous_sweep", "arm_sweep", "wait_complete", "abort", "single_sweep",
    "save_trace_data", "measure_bw", "measure_trace_power_at_frequency",
)
class KeysightSpectrumAnalyzer(GenericSpecA):
    """Spectrum mode only; scalar markers and linear-frequency trace CSV."""

    def __init__(self, transport: Transport, config: dict[str, Any]) -> None:
        # Select application before applying configuration from the TOML row.
        transport.write("INST:SEL SA")
        super().__init__(transport, config)
        self._scpi.write("UNIT:POW DBM")

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

    def _fetch_trace(
        self, trace: int, *, include_frequency: bool = True,
    ) -> tuple[list[float], list[float]]:
        maximum = 3 if self._model == "keysight-e4440a" else 6
        if not 1 <= trace <= maximum:
            raise ValueError(f"trace must be between 1 and {maximum}")
        self._scpi.write("FORM:DATA ASC")
        self._scpi.write("UNIT:POW DBM")
        # MODE WRIT is documented on PSA and is the compatibility spelling on
        # X-Series; it selects clear/write AND enables updates/display. TYPE
        # alone would leave a previously held trace frozen on X-Series.
        self._scpi.write(f"TRAC{trace}:MODE WRIT")
        self.single_sweep()
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
        axis = frequency_axis(center, span, len(values)) if include_frequency else [float(index) for index in range(count)]
        return axis, values

    def close(self) -> None:
        self._scpi._transport.close()
