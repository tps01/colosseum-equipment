from __future__ import annotations

from typing import TYPE_CHECKING, Any

from colosseum_equipment._paths import resolve_artifact_path
from colosseum_equipment.instruments._base import ScpiInstrumentMixin
from colosseum_equipment.instruments.rtsa.iq_export import (
    normalize_iq_format,
    write_iq_bin,
    write_iq_mat,
    write_iq_tar,
)
from colosseum_equipment.protocols.scpi import SCPIHelper, wait_opc

if TYPE_CHECKING:
    from pathlib import Path

    from colosseum_equipment.transports.base import Transport


class GenericRtsa(ScpiInstrumentMixin):
    """Generic SCPI real-time spectrum analyzer (spectrum setup + IQ block download)."""

    _model = "generic"

    def __init__(self, transport: Transport, config: dict[str, Any]) -> None:
        self._scpi = SCPIHelper(transport)
        self._config = config
        self._model = str(config.get("model", "generic")).lower()
        if "center_freq" in config:
            self.set_center_freq(float(config["center_freq"]))
        if "span" in config:
            self.set_span(float(config["span"]))
        if "rbw" in config:
            self.set_bandwidth(float(config["rbw"]))

    def preset(self) -> None:
        self._scpi.write("*RST")
        wait_opc(self._scpi)

    def set_center_freq(self, frequency_hz: float) -> None:
        self._scpi.write(f"FREQ:CENT {frequency_hz:.6f}")

    def set_span(self, span_hz: float) -> None:
        self._scpi.write(f"FREQ:SPAN {span_hz:.6f}")

    def set_bandwidth(self, bandwidth_hz: float) -> None:
        self._scpi.write(f"BAND:RES {bandwidth_hz:.6f}")

    def set_acq_time(self, seconds: float) -> None:
        self._scpi.write(f"SWE:TIME {seconds:.9f}")

    def set_continuous_run(self, enabled: bool) -> None:
        self._scpi.write("INIT:CONT ON" if enabled else "INIT:CONT OFF")

    def set_num_samples(self, count: int) -> None:
        self._scpi.write(f"TRAC:IQ:POIN {int(count)}")

    def get_num_samples(self) -> int:
        return int(self._scpi.query_float("TRAC:IQ:POIN?"))

    def set_trigger_source(self, source: str) -> None:
        self._scpi.write(f"TRIG:SOUR {source}")

    def set_trigger_level(self, level_dbm: float) -> None:
        self._scpi.write(f"TRIG:LEV {level_dbm:.3f}")

    def set_trigger_position(self, position_dbm: float) -> None:
        self._scpi.write(f"TRIG:POS {position_dbm:.3f}")

    def run(self) -> None:
        self._scpi.write("INIT:IMM")
        wait_opc(self._scpi)

    def save_IQ_data(self, path: str, *, file_format: str = "bin") -> Path:
        payload = self._scpi.read_binary_block("TRAC:IQ:DATA?")
        export_format = normalize_iq_format(file_format, path)
        artifact_path = resolve_artifact_path(path)
        metadata = {
            "center_freq_hz": self._scpi.query_float("FREQ:CENT?"),
            "span_hz": self._scpi.query_float("FREQ:SPAN?"),
            "num_samples": self.get_num_samples(),
            "format": export_format,
        }
        if export_format == "mat":
            write_iq_mat(artifact_path, payload, metadata=metadata)
        elif export_format == "iq.tar":
            write_iq_tar(artifact_path, payload, metadata=metadata)
        else:
            write_iq_bin(artifact_path, payload)
        return artifact_path
