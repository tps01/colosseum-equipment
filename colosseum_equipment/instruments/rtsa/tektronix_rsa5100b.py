from __future__ import annotations

import contextlib
import time
from typing import TYPE_CHECKING, Any

import numpy as np
import numpy.typing as npt
from colosseum.logging import get_logger

from colosseum_equipment._paths import resolve_artifact_path
from colosseum_equipment.evidence import record_artifact
from colosseum_equipment.exceptions import EquipmentResponseError, EquipmentTimeoutError
from colosseum_equipment.instruments.registry import instrument_model
from colosseum_equipment.instruments.rtsa.generic import GenericRtsa
from colosseum_equipment.instruments.rtsa.iq_export import (
    normalize_iq_format,
    write_capture_iq,
    write_iq_bin,
    write_iq_mat,
    write_iq_tar,
)
from colosseum_equipment.instruments.speca.trace_csv import (
    frequency_axis,
    parse_trace_amplitudes,
    write_trace_csv,
)
from colosseum_equipment.protocols.scpi import wait_opc

if TYPE_CHECKING:
    from pathlib import Path

    from colosseum_equipment.transports.base import Transport

_logger = get_logger("colosseum.equipment")

# Firmware is unreliable on a single large FETCh:RFIN:IQ?; match the MATLAB
# chunking strategy (~250k complex samples per request).
_IQ_CHUNK_SAMPLES = 250_000
_RECORD_ID_RETRIES = 9
_HEADER_RETRIES = 9


@instrument_model(
    "rtsa",
    "tektronix-rsa5100b",
    "tektronix-rsa5103b",
    "tektronix-rsa6000",
)
class TektronixRSA5100BRtsa(GenericRtsa):
    """Tektronix RSA5100B / RSA6000 real-time spectrum analyzer (IQ acquisition)."""

    def __init__(self, transport: Transport, config: dict[str, Any]) -> None:
        super().__init__(transport, config)
        self._model = str(config.get("model", "tektronix-rsa5100b")).lower()

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

    def _setup_iqvtime(
        self,
        *,
        center_hz: float,
        span_hz: float,
        bandwidth_hz: float,
        seconds: float,
    ) -> None:
        self._scpi.write("ABORt")
        self._scpi.write("TRIGger:SEQuence:STATus 0")
        self._scpi.write("INIT:CONT OFF")
        self._scpi.write("DISPlay:GENeral:MEASview:NEW IQVTime")
        self._scpi.write("DISPlay:GENeral:MEASview:SELect IQVTime")
        self._scpi.write("SENSe:IQVTime:CLEar:RESults")
        self._scpi.write("DISPlay:IQVTime:X:SCALe:AUTO")
        self._scpi.write("DISPlay:IQVTime:Y:SCALe:AUTO")
        self._scpi.write("SENSe:ACQuisition:MODE LENGTH")
        self._scpi.write(f"SENSe:ACQuisition:SEConds {seconds:.9f}")
        self._scpi.write(f"SENSe:ACQuisition:BANDwidth {bandwidth_hz:.6f}")
        self._scpi.write("SENSe:IQVTime:MAXTracepoints NEVerdecimate")
        self._scpi.write(f"SENSe:IQVTime:FREQuency:SPAN {span_hz:.6f}")
        self._scpi.write(f"SENSe:IQVTime:FREQuency:CENTer {center_hz:.6f}")

    def _wait_opc(self, *, timeout_s: float) -> None:
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
            f"rtsa model `{self._model}` IQ acquisition did not complete within {timeout_s}s",
        )

    def _fetch_record_id(self) -> int:
        details = ""
        for _ in range(_RECORD_ID_RETRIES):
            details = self._scpi.query("FETCh:RFIN:RECord:IDS?")
            fields = [part.strip() for part in details.split(",") if part.strip()]
            if len(fields) >= 2:
                first = int(float(fields[0]))
                last = int(float(fields[1]))
                if first != last:
                    _logger.warning(
                        "Unexpected RFIN record ID range %s; using first ID %s",
                        details,
                        first,
                    )
                return first
        raise EquipmentResponseError(
            f"Unable to obtain RFIN record IDs after {_RECORD_ID_RETRIES} tries "
            f"(last reply {details!r})",
        )

    def _fetch_iq_header(self, record_id: int) -> tuple[float, int]:
        header = ""
        for _ in range(_HEADER_RETRIES):
            header = self._scpi.query(f"FETCh:RFIN:IQ:HEADer? {record_id}")
            fields = [part.strip() for part in header.split(",") if part.strip()]
            if len(fields) >= 3:
                sample_rate_hz = float(fields[1])
                num_samples = int(float(fields[2]))
                return sample_rate_hz, num_samples
        raise EquipmentResponseError(
            f"Unable to obtain RFIN IQ header after {_HEADER_RETRIES} tries "
            f"(last reply {header!r})",
        )

    def _fetch_iq_float32(self, record_id: int, num_samples: int) -> npt.NDArray[np.complex64]:
        if num_samples <= 0:
            return np.array([], dtype=np.complex64)
        parts: list[npt.NDArray[np.complex64]] = []
        start = 0
        while start < num_samples:
            end = min(start + _IQ_CHUNK_SAMPLES, num_samples) - 1
            cmd = f"FETCh:RFIN:IQ? {record_id},{start},{end}"
            payload = self._scpi.read_binary_block(cmd)
            expected = (end - start + 1) * 8
            if len(payload) < expected:
                raise EquipmentResponseError(
                    f"Short RFIN IQ block: got {len(payload)} bytes, expected {expected}",
                )
            raw = np.frombuffer(payload[:expected], dtype="<f4")
            chunk = raw[0::2].astype(np.float32) + 1j * raw[1::2].astype(np.float32)
            parts.append(chunk.astype(np.complex64, copy=False))
            start = end + 1
        return np.concatenate(parts) if len(parts) > 1 else parts[0]

    def capture_iq(
        self,
        *,
        center_hz: float,
        span_hz: float,
        bandwidth_hz: float,
        seconds: float,
        path: str,
        file_format: str = "mat",
        sample_format: str = "f32",
        timeout_s: float = 120.0,
        key: str = "",
    ) -> dict[str, Any]:
        """Acquire one IQ vs Time record (RSA6000 / RSA5100B length mode)."""
        self._run_id = f"{time.monotonic():.6f}"
        self._setup_iqvtime(
            center_hz=center_hz,
            span_hz=span_hz,
            bandwidth_hz=bandwidth_hz,
            seconds=seconds,
        )
        self._scpi.write("INITIATE:IMMEDIATE")
        self._wait_opc(timeout_s=timeout_s)

        transport = getattr(self._scpi, "_transport", None)
        setter = getattr(transport, "set_timeout_s", None) if transport is not None else None
        prev_timeout = getattr(transport, "_timeout", None) if transport is not None else None
        try:
            if callable(setter):
                with contextlib.suppress(Exception):
                    setter(max(float(timeout_s), 1.0))
            record_id = self._fetch_record_id()
            sample_rate_hz, num_samples = self._fetch_iq_header(record_id)
            iq = self._fetch_iq_float32(record_id, num_samples)
        finally:
            if callable(setter) and prev_timeout is not None:
                with contextlib.suppress(Exception):
                    setter(float(prev_timeout))

        artifact_path = resolve_artifact_path(path)
        base_meta = {
            "center_hz": float(center_hz),
            "span_hz": float(span_hz),
            "bandwidth_hz": float(bandwidth_hz),
            "seconds": float(seconds),
            "sample_rate_hz": float(sample_rate_hz),
            "record_id": int(record_id),
            "run_id": self._run_id,
        }
        out_meta = write_capture_iq(
            artifact_path,
            iq,
            file_format=file_format,
            sample_format=sample_format,
            metadata=base_meta,
        )
        out_meta["path"] = str(artifact_path)
        evidence_key = key or f"rtsa_capture_iq_{self._run_id}"
        record_artifact(
            domain="equipment",
            command="capture_iq",
            key=evidence_key,
            path=artifact_path,
            value=out_meta,
        )
        return out_meta
