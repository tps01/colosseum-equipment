"""E5052B phase-noise traces on the instrument's actual offset grid.

Manual: https://helpfiles.keysight.com/csg/e5052b/welcome.htm
Uses PN1 measurement; PDAT is phase-noise data independent of display math.
"""
from __future__ import annotations

import bisect
import math
import time
from typing import TYPE_CHECKING

from colosseum_equipment._paths import resolve_artifact_path
from colosseum_equipment.evidence import record_artifact
from colosseum_equipment.exceptions import EquipmentCapabilityError, EquipmentResponseError
from colosseum_equipment.instruments._capabilities import supported_commands
from colosseum_equipment.instruments.phasenoiseanalyzer.generic import GenericPhaseNoiseAnalyzer
from colosseum_equipment.instruments.phasenoiseanalyzer.trace_export import write_phase_noise_trace_csv
from colosseum_equipment.instruments.registry import instrument_model

if TYPE_CHECKING:
    from pathlib import Path


@instrument_model("phasenoiseanalyzer", "keysight-e5052b")
@supported_commands(
    "preset", "set_offset_start_hz", "set_offset_stop_hz", "set_averaging_count", "set_xcorr_count",
    "initiate", "wait_opc", "wait_complete", "abort", "save_trace_data", "measure_spot_noise_dbc_hz",
)
class KeysightE5052B(GenericPhaseNoiseAnalyzer):
    """Carrier detection is instrument-managed; spot interpolation is linear in log(offset)."""

    def set_offset_start_hz(self, offset_hz: float) -> None:
        if offset_hz <= 0:
            raise ValueError("offset frequency must be positive")
        self._scpi.write(f"SENS:PN1:FREQ:STAR {offset_hz:.6f}")

    def set_offset_stop_hz(self, offset_hz: float) -> None:
        if offset_hz <= 0:
            raise ValueError("offset frequency must be positive")
        self._scpi.write(f"SENS:PN1:FREQ:STOP {offset_hz:.6f}")

    def set_averaging_count(self, count: int) -> None:
        if count < 1:
            raise ValueError("averaging count must be positive")
        self._scpi.write(f"SENS:PN1:AVER:COUN {count}")
        self._scpi.write("SENS:PN1:AVER:STAT ON")

    def set_xcorr_count(self, count: int) -> None:
        if count < 1:
            raise ValueError("correlation count must be positive")
        self._scpi.write(f"SENS:PN1:CORR:COUN {count}")

    def initiate(self) -> None:
        self._sweep_id = f"{time.monotonic():.6f}"
        self._scpi.write("INIT:PN1:CONT OFF")
        self._scpi.write("SENS:PN1:AVER:CLE")
        self._scpi.write("INIT:PN1:IMM")

    def abort(self) -> None:
        self._scpi.write("ABOR")

    def _trace(self) -> tuple[list[float], list[float]]:
        self._scpi.write("FORM:DATA ASC")
        try:
            axis = [float(v) for v in self._scpi.query("CALC:PN1:DATA:XDAT?").split(",")]
            values = [float(v) for v in self._scpi.query("CALC:PN1:TRAC1:DATA:PDAT?").split(",")]
        except ValueError as exc:
            raise EquipmentResponseError("malformed phase-noise array") from exc
        if not axis or len(axis) != len(values):
            raise EquipmentResponseError("phase-noise axis/data length mismatch")
        if any(not math.isfinite(v) or v <= 0 for v in axis):
            raise EquipmentResponseError("invalid offset-frequency axis")
        if any(b <= a for a, b in zip(axis, axis[1:], strict=False)):
            raise EquipmentResponseError("offset frequencies must increase strictly")
        if any(not math.isfinite(v) or abs(v) >= 9e37 for v in values):
            raise EquipmentResponseError("invalid phase-noise reading")
        return axis, values

    def measure_spot_noise_dbc_hz(self, offset_hz: float) -> float:
        axis, values = self._trace()
        if not axis[0] <= offset_hz <= axis[-1]:
            raise EquipmentCapabilityError("requested offset is outside the captured trace")
        right = bisect.bisect_left(axis, offset_hz)
        if axis[right] == offset_hz:
            return values[right]
        left = right - 1
        fraction = math.log(offset_hz / axis[left]) / math.log(axis[right] / axis[left])
        return values[left] + fraction * (values[right] - values[left])

    def save_trace_data(self, path: str, *, trace: int = 1) -> Path:
        if trace != 1:
            raise EquipmentCapabilityError("E5052B PN measurement has trace 1")
        axis, values = self._trace()
        artifact = resolve_artifact_path(path)
        write_phase_noise_trace_csv(artifact, axis, values)
        record_artifact(
            domain="equipment", command="save_trace_data", key="phasenoise_trace_1", path=artifact,
            value={"trace": 1, "points": len(values), "sweep_id": self._sweep_id,
                   "offset_start_hz": axis[0], "offset_stop_hz": axis[-1]},
        )
        return artifact
