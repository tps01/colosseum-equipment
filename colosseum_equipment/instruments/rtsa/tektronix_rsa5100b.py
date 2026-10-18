from __future__ import annotations

from typing import TYPE_CHECKING, Any

from colosseum_equipment._paths import resolve_artifact_path
from colosseum_equipment.evidence import record_artifact
from colosseum_equipment.instruments.registry import instrument_model
from colosseum_equipment.instruments.rtsa.generic import GenericRtsa
from colosseum_equipment.instruments.speca.trace_csv import (
    frequency_axis,
    parse_trace_amplitudes,
    write_trace_csv,
)
from colosseum_equipment.instruments.rtsa.iq_export import (
    normalize_iq_format,
    write_iq_bin,
    write_iq_mat,
    write_iq_tar,
)
from colosseum_equipment.protocols.scpi import wait_opc

if TYPE_CHECKING:
    from pathlib import Path

    from colosseum_equipment.transports.base import Transport


@instrument_model("rtsa", "tektronix-rsa5100b")
class TektronixRSA5100BRtsa(GenericRtsa):
    """Tektronix RSA5100B real-time spectrum analyzer (IQ acquisition)."""

    def __init__(self, transport: Transport, config: dict[str, Any]) -> None:
        super().__init__(transport, config)
        self._model = "tektronix-rsa5100b"

    def _ensure_spectrum_view(self) -> None:
        active = self._scpi.query("DISP:WIND:ACT:MEAS?").upper()
        if "SPEC" not in active:
            self._scpi.write("DISP:WIND:ACT:MEAS SPECtrum")

    def preset(self) -> None:
        self._scpi.write("*RST")
        wait_opc(self._scpi)

    def set_center_freq(self, frequency_hz: float) -> None:
        self._ensure_spectrum_view()
        self._scpi.write(f"DISP:SPEC:FREQ:OFFS {frequency_hz:.6f}")

    def set_span(self, span_hz: float) -> None:
        self._ensure_spectrum_view()
        self._scpi.write(f"DISP:SPEC:FREQ:SCAL {span_hz:.6f}")

    def set_bandwidth(self, bandwidth_hz: float) -> None:
        self._ensure_spectrum_view()
        self._scpi.write(f"SENS:SPEC:BAND:RES {bandwidth_hz:.6f}")

    def set_acq_time(self, seconds: float) -> None:
        self._ensure_spectrum_view()
        self._scpi.write(f"SENS:SPEC:ACQ:TIME {seconds:.9f}")

    def set_continuous_run(self, enabled: bool) -> None:
        self._ensure_spectrum_view()
        self._scpi.write(f"INIT:CONT {1 if enabled else 0}")

    def set_num_samples(self, count: int) -> None:
        self._ensure_spectrum_view()
        self._scpi.write(f"SENS:SPEC:ACQ:POIN {int(count)}")

    def get_num_samples(self) -> int:
        self._ensure_spectrum_view()
        return int(self._scpi.query_float("SENS:SPEC:ACQ:POIN?"))

    def set_trigger_source(self, source: str) -> None:
        self._ensure_spectrum_view()
        self._scpi.write(f"TRIG:SOUR {source}")

    def set_trigger_level(self, level_dbm: float) -> None:
        self._ensure_spectrum_view()
        self._scpi.write(f"TRIG:LEV {level_dbm:.3f}")

    def set_trigger_position(self, position_dbm: float) -> None:
        self._ensure_spectrum_view()
        self._scpi.write(f"TRIG:POS {position_dbm:.3f}")

    def run(self) -> None:
        self._ensure_spectrum_view()
        super().run()
        wait_opc(self._scpi)

    def peak_search(self, marker: int = 1) -> None:
        self._ensure_spectrum_view()
        self._scpi.write(f"CALC:MARK{marker}:MAX")

    def save_spectrum_trace_data(self, path: str, *, trace: int = 1) -> Path:
        """Export a non-IQ spectrum trace CSV (last completed acquisition)."""
        self._ensure_spectrum_view()
        center = self._scpi.query_float("DISP:SPEC:FREQ:OFFS?")
        span = self._scpi.query_float("DISP:SPEC:FREQ:SCAL?")
        raw = self._scpi.query(f"FETCH:SPEC:TRAC? TRACE{int(trace)}")
        amplitudes = parse_trace_amplitudes(raw)
        frequencies = frequency_axis(center, span, len(amplitudes))
        artifact_path = resolve_artifact_path(path)
        write_trace_csv(
            artifact_path,
            amplitudes,
            center_hz=center,
            span_hz=span,
            include_frequency=True,
        )
        record_artifact(
            domain="equipment",
            command="save_spectrum_trace_data",
            key=f"rtsa_spec_trace_{trace}",
            path=artifact_path,
            value={
                "trace": trace,
                "center_hz": center,
                "span_hz": span,
                "points": len(amplitudes),
                "run_id": self._run_id,
            },
        )
        return artifact_path

    def save_IQ_data(self, path: str, *, file_format: str = "bin", key: str = "") -> Path:
        from colosseum_equipment.evidence import record_artifact

        self._ensure_spectrum_view()
        payload = self._scpi.read_binary_block("FETCH:SPEC:IQ?")
        export_format = normalize_iq_format(file_format, path)
        artifact_path = resolve_artifact_path(path)
        metadata = {
            "center_freq_hz": self._scpi.query_float("DISP:SPEC:FREQ:OFFS?"),
            "span_hz": self._scpi.query_float("DISP:SPEC:FREQ:SCAL?"),
            "num_samples": self.get_num_samples(),
            "format": export_format,
        }
        if export_format == "mat":
            write_iq_mat(artifact_path, payload, metadata=metadata)
        elif export_format == "iq.tar":
            write_iq_tar(artifact_path, payload, metadata=metadata)
        else:
            write_iq_bin(artifact_path, payload)
        evidence_key = key or f"rtsa_iq_{getattr(self, '_run_id', None) or 'last'}"
        record_artifact(
            domain="equipment",
            command="save_IQ_data",
            key=evidence_key,
            path=artifact_path,
            value=metadata,
        )
        return artifact_path
