from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from colosseum_equipment._paths import resolve_artifact_path
from colosseum_equipment.evidence import record_artifact
from colosseum_equipment.exceptions import EquipmentTimeoutError
from colosseum_equipment.instruments._base import ScpiInstrumentMixin
from colosseum_equipment.instruments._capabilities import unsupported
from colosseum_equipment.instruments.registry import best_effort_commands, instrument_model
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


@instrument_model("rtsa", "generic", extra_optional=("center_freq", "span", "rbw"))
@best_effort_commands
class GenericRtsa(ScpiInstrumentMixin):
    """Generic SCPI real-time spectrum analyzer (spectrum setup + IQ block download).

    ``run`` arms acquisition; ``wait_complete`` blocks with a timeout; ``abort`` cancels.
    ``save_IQ_data`` downloads the last completed IQ capture (does not re-arm).
    """

    _model = "generic"

    def __init__(self, transport: Transport, config: dict[str, Any]) -> None:
        self._scpi = SCPIHelper(transport)
        self._config = config
        self._model = str(config.get("model", "generic")).lower()
        self._run_id = ""
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
        """Arm or start a single acquisition (non-blocking)."""
        self._run_id = f"{time.monotonic():.6f}"
        self._scpi.write("INIT:IMM")

    def wait_complete(self, *, timeout_s: float = 60.0) -> None:
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
            f"rtsa model `{self._model}` acquisition did not complete within {timeout_s}s",
        )

    def abort(self) -> None:
        self._scpi.write(":ABOR")

    def acquire(self, *, timeout_s: float = 60.0) -> str:
        """Run a single acquisition and wait for completion."""
        self.set_continuous_run(False)
        self.run()
        self.wait_complete(timeout_s=timeout_s)
        return self._run_id

    def peak_search(self, marker: int = 1) -> None:
        unsupported(self._model, "peak_search")

    def save_spectrum_trace_data(self, path: str, *, trace: int = 1) -> Path:
        unsupported(self._model, "save_spectrum_trace_data")

    def save_IQ_data(self, path: str, *, file_format: str = "bin", key: str = "") -> Path:
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
        evidence_key = key or f"rtsa_iq_{self._run_id or 'last'}"
        record_artifact(
            domain="equipment",
            command="save_IQ_data",
            key=evidence_key,
            path=artifact_path,
            value=metadata,
        )
        return artifact_path
