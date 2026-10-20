"""Finite zero-span IQ acquisition through Spike SCPI, no vendor SDK dependency.

Manual: https://signalhound.com/sigdownloads/Spike/docs/html/scpi_programming.html
"""
from __future__ import annotations

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

if TYPE_CHECKING:
    from pathlib import Path
    from colosseum_equipment.transports.base import Transport


@instrument_model("rtsa", "signalhound-bb60c-spike", "signalhound-sm200c-spike")
@supported_commands(
    "set_center_freq", "set_bandwidth", "set_acq_time", "set_continuous_run", "set_num_samples",
    "get_num_samples", "set_trigger_source", "set_trigger_level", "set_trigger_position",
    "run", "wait_complete", "acquire", "save_IQ_data",
)
class SignalHoundSpikeIq(GenericRtsa):
    """Finite IQ captures; sample_rate_hz is independent of the analog IF bandwidth.

    Configure one mode/session per Spike instance. Do not concurrently configure
    a speca row and rtsa row pointing at the same global Spike mode.
    """

    def __init__(self, transport: Transport, config: dict[str, Any]) -> None:
        if "span" in config:
            raise EquipmentCapabilityError("use sample_rate_hz for IQ rate; span is not sample rate")
        transport.write("INST:SEL ZS")
        super().__init__(transport, config)
        if "sample_rate_hz" in config:
            self._scpi.write(f"SENS:ZS:CAP:SRAT {float(config['sample_rate_hz'])}")
        if "reference_level_dbm" in config:
            self._scpi.write(f"SENS:ZS:CAP:RLEV {float(config['reference_level_dbm'])}DBM")

    def set_center_freq(self, frequency_hz: float) -> None:
        self._scpi.write(f"SENS:ZS:CAP:CENT {frequency_hz:.6f}")

    def set_bandwidth(self, bandwidth_hz: float) -> None:
        self._scpi.write("SENS:ZS:CAP:IFBW:AUTO OFF")
        self._scpi.write(f"SENS:ZS:CAP:IFBW {bandwidth_hz:.6f}")

    def set_acq_time(self, seconds: float) -> None:
        if not math.isfinite(seconds) or seconds <= 0:
            raise ValueError("capture duration must be positive")
        self._scpi.write(f"SENS:ZS:CAP:SWE:TIME {seconds:.12f}")

    def set_num_samples(self, count: int) -> None:
        if count < 1:
            raise ValueError("sample count must be positive")
        rate = self._scpi.query_float("SENS:ZS:CAP:SRAT?")
        if not math.isfinite(rate) or rate <= 0:
            raise EquipmentResponseError("invalid sample rate")
        self.set_acq_time(count / rate)

    def get_num_samples(self) -> int:
        return int(self._scpi.query_float("FETC:ZS? 2"))

    def set_trigger_source(self, source: str) -> None:
        token = {"IMMEDIATE": "IMM", "EXTERNAL": "EXT"}.get(source.upper(), source.upper())
        if token not in {"IMM", "IF", "EXT", "FMT"}:
            raise EquipmentCapabilityError(f"unsupported Spike trigger {source!r}")
        self._scpi.write(f"TRIG:ZS:SOUR {token}")

    def set_trigger_level(self, level_dbm: float) -> None:
        self._scpi.write(f"TRIG:ZS:IF:LEV {level_dbm}DBM")

    def set_trigger_position(self, position_dbm: float) -> None:
        # Public legacy parameter name is misleading: this quantity is percent.
        if not 0 <= position_dbm <= 100:
            raise ValueError("trigger pre-position is a percentage, 0..100")
        self._scpi.write(f"TRIG:ZS:POS {position_dbm}")

    def save_IQ_data(self, path: str, *, file_format: str = "bin", key: str = "") -> Path:
        self._scpi.write("FORM:IQ ASC")
        count = self.get_num_samples()
        try:
            values = [float(v) for v in self._scpi.query("FETC:ZS? 1").split(",")]
        except ValueError as exc:
            raise EquipmentResponseError("malformed Spike IQ samples") from exc
        if count < 1 or len(values) != count * 2 or any(not math.isfinite(v) for v in values):
            raise EquipmentResponseError("Spike IQ data length/values differ from reported capture")
        rate = self._scpi.query_float("SENS:ZS:CAP:SRAT?")
        center = self._scpi.query_float("SENS:ZS:CAP:CENT?")
        if not math.isfinite(rate) or rate <= 0 or not math.isfinite(center):
            raise EquipmentResponseError("invalid capture sample rate")
        # Existing IQ writers consume interleaved little-endian float64 samples.
        payload = struct.pack(f"<{len(values)}d", *values)
        export_format = normalize_iq_format(file_format, path)
        if export_format not in {"bin", "mat", "iq.tar"}:
            raise EquipmentCapabilityError(f"unsupported IQ export format {export_format!r}")
        artifact = resolve_artifact_path(path)
        metadata = {"center_freq_hz": center, "sample_rate_hz": rate, "num_samples": count,
                    "iq_dtype": "float64", "iq_byte_order": "little", "iq_units": "sqrt(mW)",
                    "format": export_format, "run_id": self._run_id}
        if export_format == "mat":
            write_iq_mat(artifact, payload, metadata=metadata)
        elif export_format == "iq.tar":
            write_iq_tar(artifact, payload, metadata=metadata)
        else:
            write_iq_bin(artifact, payload)
        record_artifact(domain="equipment", command="save_IQ_data", key=key or f"rtsa_iq_{self._run_id}",
                        path=artifact, value=metadata)
        return artifact
