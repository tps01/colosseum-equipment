"""Native RSA spectrum and recorded IQ commands, not display-axis offsets.

077-0901-03/05 RSA5100B programmer manual, FETCh/SENSe/INITiate groups.
RSA6100A/5100A programmer manual: shared spectrum subset only for RSA6114A.
https://device.report/m/768f72f644270bfba95235a6ebec01ffc4c9b48f1a5d831974c45f533cdae63b
"""
from __future__ import annotations

import csv
import math
import struct
from typing import TYPE_CHECKING, Any

from colosseum_equipment._paths import resolve_artifact_path
from colosseum_equipment.evidence import record_artifact
from colosseum_equipment.exceptions import EquipmentCapabilityError, EquipmentResponseError
from colosseum_equipment.instruments._capabilities import supported_commands
from colosseum_equipment.instruments.registry import instrument_model
from colosseum_equipment.instruments.rtsa.generic import GenericRtsa
from colosseum_equipment.instruments.rtsa.iq_export import normalize_iq_format, write_iq_bin, write_iq_mat, write_iq_tar
from colosseum_equipment.instruments.rtsa.tektronix_rsa5100b import TektronixRSA5100BRtsa
from colosseum_equipment.instruments.speca.trace_csv import write_trace_csv

if TYPE_CHECKING:
    from pathlib import Path

    from colosseum_equipment.transports.base import Transport

_SPECTRUM = (
    "set_center_freq", "set_span", "set_bandwidth", "set_continuous_run", "run", "wait_complete",
    "abort", "acquire", "save_spectrum_trace_data",
)


class TekNativeRtsa(GenericRtsa):
    """Manual-controlled trigger/capture length; finite acquisitions, no streaming."""

    # Same IQ vs Time length-mode sequence as the family driver. Spectrum methods
    # below stay on native SENSe commands rather than display-axis offsets.
    _setup_iqvtime = TektronixRSA5100BRtsa._setup_iqvtime
    _wait_opc = TektronixRSA5100BRtsa._wait_opc
    _fetch_record_id = TektronixRSA5100BRtsa._fetch_record_id
    _fetch_iq_header = TektronixRSA5100BRtsa._fetch_iq_header
    _fetch_iq_float32 = TektronixRSA5100BRtsa._fetch_iq_float32
    capture_iq = TektronixRSA5100BRtsa.capture_iq

    def __init__(self, transport: Transport, config: dict[str, Any]) -> None:
        transport.write("DISP:GEN:MEAS:NEW SPEC")
        super().__init__(transport, config)

    def set_center_freq(self, frequency_hz: float) -> None:
        self._scpi.write(f"SENS:SPEC:FREQ:CENT {frequency_hz:.6f}")

    def set_span(self, span_hz: float) -> None:
        self._scpi.write(f"SENS:SPEC:FREQ:SPAN {span_hz:.6f}")

    def set_bandwidth(self, bandwidth_hz: float) -> None:
        self._scpi.write("SENS:SPEC:BAND:RES:AUTO OFF")
        self._scpi.write(f"SENS:SPEC:BAND:RES {bandwidth_hz:.6f}")

    def save_spectrum_trace_data(self, path: str, *, trace: int = 1) -> Path:
        if not 1 <= trace <= 3:
            raise EquipmentCapabilityError("only normal spectrum traces 1..3 are implemented")
        if self._scpi.query("SENS:POW:UNIT?").upper() != "DBM":
            raise EquipmentCapabilityError("select dBm power units before exporting")
        # Spectrum traces may use a logarithmic x-axis. Never assume a linear
        # axis when the instrument is configured that way.
        if int(self._scpi.query("DISP:SPEC:SCAL:LOG:STAT?")):
            raise EquipmentCapabilityError("select a linear spectrum frequency axis")
        raw = self._scpi.read_binary_block(f"FETC:SPEC:TRAC{trace}?")
        if len(raw) < 8 or len(raw) % 4:
            raise EquipmentResponseError("invalid spectrum float32 byte count")
        values = list(struct.unpack(f"<{len(raw) // 4}f", raw))
        start = self._scpi.query_float("SENS:SPEC:FREQ:STAR?")
        stop = self._scpi.query_float("SENS:SPEC:FREQ:STOP?")
        if any(not math.isfinite(v) for v in values) or not math.isfinite(start) or not math.isfinite(stop) or stop <= start:
            raise EquipmentResponseError("invalid spectrum values or frequency axis")
        artifact = resolve_artifact_path(path)
        write_trace_csv(artifact, values, center_hz=(start + stop) / 2, span_hz=stop - start,
                        include_frequency=True)
        record_artifact(domain="equipment", command="save_spectrum_trace_data", key=f"rtsa_spec_trace_{trace}",
                        path=artifact, value={"points": len(values), "units": "dBm", "run_id": self._run_id})
        return artifact

    def _iq_header(self) -> tuple[int, list[str]]:
        ids = self._scpi.query("FETC:RFIN:REC:IDS?").split(",")
        if len(ids) != 2:
            raise EquipmentResponseError("expected first/last acquisition record IDs")
        try:
            first, last = (int(v) for v in ids)
            if first < 0 or last < first:
                raise ValueError("no recorded acquisition")
            fields = next(csv.reader([self._scpi.query(f"FETC:RFIN:IQ:HEAD? {last}")]))
            if len(fields) != 9:
                raise ValueError("expected nine IQ header fields")
            numeric = [float(v) for v in fields[:7]]
            if not all(math.isfinite(v) for v in numeric) or numeric[1] <= 0 or numeric[2] < 1 or not numeric[2].is_integer():
                raise ValueError("invalid IQ sampling metadata")
            if int(fields[8]) >= 0:
                raise EquipmentCapabilityError("FastFrame records require a separate segmented workflow")
        except ValueError as exc:
            raise EquipmentResponseError(f"invalid IQ acquisition header: {exc}") from exc
        return last, fields

    def get_num_samples(self) -> int:
        _, fields = self._iq_header()
        return int(float(fields[2]))

    def save_IQ_data(self, path: str, *, file_format: str = "bin", key: str = "") -> Path:
        export_format = normalize_iq_format(file_format, path)
        if export_format not in {"bin", "mat", "iq.tar"}:
            raise EquipmentCapabilityError(f"unsupported IQ format {export_format!r}")
        record_id, fields = self._iq_header()
        count = int(float(fields[2]))
        raw = self._scpi.read_binary_block(f"FETC:RFIN:IQ? {record_id}")
        if len(raw) != count * 8:
            raise EquipmentResponseError("IQ payload does not match record header count")
        values = struct.unpack(f"<{count * 2}f", raw)
        if any(not math.isfinite(v) for v in values):
            raise EquipmentResponseError("invalid IQ sample")
        # Do not multiply by the Option 05 digital-output scaling factor: this
        # fetch returns floating-point IQ, not the external digital ADC stream.
        payload = struct.pack(f"<{count * 2}d", *values)
        metadata = {"sample_rate_hz": float(fields[1]), "num_samples": count,
                    "center_freq_hz": float(fields[3]), "acquisition_bandwidth_hz": float(fields[4]),
                    "trigger_position_s": float(fields[6]), "time_stamp": fields[7], "record_id": record_id,
                    "iq_dtype": "float64", "iq_byte_order": "little", "iq_units": "native floating IQ",
                    "native_header": fields, "run_id": self._run_id, "format": export_format}
        artifact = resolve_artifact_path(path)
        if export_format == "mat":
            write_iq_mat(artifact, payload, metadata=metadata)
        elif export_format == "iq.tar":
            write_iq_tar(artifact, payload, metadata=metadata)
        else:
            write_iq_bin(artifact, payload)
        record_artifact(domain="equipment", command="save_IQ_data", key=key or f"rtsa_iq_{record_id}",
                        path=artifact, value=metadata)
        return artifact


@instrument_model("rtsa", "tektronix-rsa5115b", "tektronix-rsa5126b")
@supported_commands(*_SPECTRUM, "get_num_samples", "save_IQ_data", "capture_iq")
class TekRsa5100bNative(TekNativeRtsa):
    """Exact RSA5100B models: finite acquisition, spectrum, recorded IQ, and capture_iq."""


@instrument_model("rtsa", "tektronix-rsa6114a")
@supported_commands(*_SPECTRUM)
class TekRsa6114aNative(TekNativeRtsa):
    """RSA6100A spectrum subset; B-series IQ header semantics are not assumed."""
