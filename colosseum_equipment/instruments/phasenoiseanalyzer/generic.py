"""Generic SCPI phase noise analyzer."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from colosseum_equipment._paths import resolve_artifact_path
from colosseum_equipment.evidence import record_artifact
from colosseum_equipment.exceptions import EquipmentCapabilityError, EquipmentTimeoutError
from colosseum_equipment.instruments._base import ScpiInstrumentMixin
from colosseum_equipment.instruments.phasenoiseanalyzer.trace_export import (
    parse_trace_values,
    write_phase_noise_trace_csv,
)
from colosseum_equipment.instruments.registry import best_effort_commands, instrument_model
from colosseum_equipment.protocols.scpi import SCPIHelper, wait_opc

if TYPE_CHECKING:
    from pathlib import Path

    from colosseum_equipment.transports.base import Transport


@instrument_model("phasenoiseanalyzer", "generic")
@best_effort_commands
class GenericPhaseNoiseAnalyzer(ScpiInstrumentMixin):
    """Generic SCPI phase-noise analyzer (IEEE 488.2 + common mnemonics).

    ``initiate`` arms a sweep; ``wait_opc`` / ``wait_complete`` block; ``abort`` cancels.
    ``measure_spot_noise_dbc_hz`` and ``save_trace_data`` fetch the last completed sweep.
    """

    _model = "generic"

    def __init__(self, transport: Transport, config: dict[str, Any]) -> None:
        self._scpi = SCPIHelper(transport)
        self._config = config
        self._model = str(config.get("model", "generic")).lower()
        self._sweep_id = ""

    def preset(self) -> None:
        self._scpi.write("*RST")
        wait_opc(self._scpi)

    def set_carrier_frequency_hz(self, frequency_hz: float) -> None:
        self._scpi.write(f"FREQ:CENT {frequency_hz:.6f}")

    def set_offset_start_hz(self, offset_hz: float) -> None:
        self._scpi.write(f"FREQ:STAR {offset_hz:.6f}")

    def set_offset_stop_hz(self, offset_hz: float) -> None:
        self._scpi.write(f"FREQ:STOP {offset_hz:.6f}")

    def initiate(self) -> None:
        self._sweep_id = f"{time.monotonic():.6f}"
        self._scpi.write("INIT:CONT OFF")
        self._scpi.write("INIT:IMM")

    def wait_opc(self) -> None:
        wait_opc(self._scpi)

    def wait_complete(self, *, timeout_s: float = 120.0) -> None:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            try:
                if self._scpi.query("*OPC?").strip().startswith("1"):
                    return
            except Exception:
                pass
            time.sleep(0.05)
        raise EquipmentTimeoutError(
            f"phasenoiseanalyzer model `{self._model}` sweep did not complete within {timeout_s}s",
        )

    def abort(self) -> None:
        self._scpi.write(":ABOR")

    def set_averaging_count(self, count: int) -> None:
        self._scpi.write(f"SWE:COUN {int(count)}")

    def set_xcorr_count(self, count: int) -> None:
        raise EquipmentCapabilityError(
            f"phasenoiseanalyzer model `{self._model}` does not support set_xcorr_count",
        )

    def measure_spot_noise_dbc_hz(self, offset_hz: float) -> float:
        """Read spot noise at ``offset_hz`` from the last sweep (does not re-arm)."""
        self._scpi.write(f"CALC:SNO:X {offset_hz:.6f}")
        return self._scpi.query_float("CALC:SNO:Y?")

    def measure_integrated_jitter_s(
        self,
        *,
        start_hz: float | None = None,
        stop_hz: float | None = None,
    ) -> float:
        if start_hz is not None:
            self._scpi.write(f"CALC:LINT:STAR {start_hz:.6f}")
        if stop_hz is not None:
            self._scpi.write(f"CALC:LINT:STOP {stop_hz:.6f}")
        for command in ("CALC:LINT:RMS?", "CALC:JIT:RMS?", "CALC:JITTer:RMS?"):
            try:
                return self._scpi.query_float(command)
            except Exception:
                continue
        raise EquipmentCapabilityError(
            f"phasenoiseanalyzer model `{self._model}` has no integrated jitter CALC query",
        )

    def save_trace_data(self, path: str, *, trace: int = 1) -> Path:
        """Export phase-noise trace CSV from the last completed sweep."""
        raw = self._scpi.query(f"TRAC:DATA? TRACE{int(trace)}")
        values = parse_trace_values(raw)
        start = self._scpi.query_float("FREQ:STAR?")
        stop = self._scpi.query_float("FREQ:STOP?")
        if len(values) > 1:
            step = (stop - start) / (len(values) - 1)
            offsets = [start + index * step for index in range(len(values))]
        elif len(values) == 1:
            offsets = [start]
        else:
            offsets = []
        artifact_path = resolve_artifact_path(path)
        write_phase_noise_trace_csv(artifact_path, offsets, values)
        record_artifact(
            domain="equipment",
            command="save_trace_data",
            key=f"phasenoise_trace_{trace}",
            path=artifact_path,
            value={
                "trace": trace,
                "offset_start_hz": start,
                "offset_stop_hz": stop,
                "points": len(values),
                "sweep_id": self._sweep_id,
            },
        )
        return artifact_path

    def measure_carrier_frequency_hz(self) -> float:
        return self._scpi.query_float("FREQ:CENT?")
