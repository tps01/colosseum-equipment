"""Finite IQ block and spectrum acquisition through the direct Tektronix RSA API.

077-1031-04 Rev A, CONFIG / IQBLK / SPECTRUM / TRIG function groups.
https://github.com/tektronix/RSA_API/tree/master/Python
"""

from __future__ import annotations

import ctypes as ct
import math
import time
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt

from colosseum_equipment._paths import resolve_artifact_path
from colosseum_equipment.evidence import record_artifact
from colosseum_equipment.exceptions import EquipmentCapabilityError, EquipmentResponseError, EquipmentTimeoutError
from colosseum_equipment.instruments._capabilities import supported_commands
from colosseum_equipment.instruments.rtsa.generic import GenericRtsa
from colosseum_equipment.instruments.rtsa.iq_export import (
    normalize_iq_format, normalize_sample_format, write_capture_iq,
    write_iq_bin, write_iq_mat, write_iq_tar,
)
from colosseum_equipment.instruments.speca.trace_csv import write_trace_csv
from colosseum_equipment.transports.base import Transport
from colosseum_equipment.transports.tektronix_rsa import IqAcquisitionInfo, RsaApiTransport, SpectrumSettings


@supported_commands(
    "preset", "set_center_freq", "set_span", "set_bandwidth", "set_acq_time",
    "set_continuous_run", "set_num_samples", "get_num_samples", "set_trigger_source",
    "set_trigger_level", "set_trigger_position", "run", "wait_complete", "abort",
    "acquire", "save_spectrum_trace_data", "save_IQ_data", "capture_iq",
)
class TekUsbRsa(GenericRtsa):
    """Native finite captures. Spectrum span/RBW and IQ bandwidth are distinct."""

    def __init__(self, transport: Transport, config: dict[str, Any]) -> None:
        if not isinstance(transport, RsaApiTransport):
            raise EquipmentCapabilityError("USB RSA models require driver=rsa-api, not a VISA/SCPI transport")
        self._api = transport
        self._config = config
        self._model = str(config.get("model", ""))
        self._run_id = ""
        self._running = False
        self._iq: npt.NDArray[np.complex64] | None = None
        self._metadata: dict[str, Any] = {}
        self._api.call("SPECTRUM_SetEnable", True)
        self._api.call("SPECTRUM_SetDefault")
        self._api.call("IQBLK_SetIQBandwidth", float(config.get("iq_bandwidth_hz", 40e6)))
        self.set_num_samples(int(config.get("num_samples", 1024)))
        self.set_trigger_source("IMM")
        if "center_freq" in config:
            self.set_center_freq(float(config["center_freq"]))
        if "reference_level_dbm" in config:
            level = float(config["reference_level_dbm"])
            if not math.isfinite(level):
                raise ValueError("reference level must be finite")
            self._api.call("CONFIG_SetReferenceLevel", level)
        if "span" in config:
            self.set_span(float(config["span"]))
        if "rbw" in config:
            self.set_bandwidth(float(config["rbw"]))
        if "sample_rate_hz" in config:
            rate = self._double("IQBLK_GetIQSampleRate")
            if not math.isclose(rate, float(config["sample_rate_hz"])):
                raise EquipmentCapabilityError("IQ sample rate is selected by IQ bandwidth; configure iq_bandwidth_hz")

    def _invalidate(self) -> None:
        self._iq = None
        self._metadata = {}
        if self._running:
            self._api.call("DEVICE_Stop")
            self._running = False

    def _double(self, name: str) -> float:
        result = ct.c_double()
        self._api.call(name, ct.byref(result))
        if not math.isfinite(result.value):
            raise EquipmentResponseError(f"RSA API {name} returned a nonfinite value")
        return result.value

    def preset(self) -> None:
        self._invalidate()
        self._api.call("CONFIG_Preset")

    def set_center_freq(self, frequency_hz: float) -> None:
        if not math.isfinite(frequency_hz) or frequency_hz < 0:
            raise ValueError("center frequency must be finite and nonnegative")
        self._invalidate()
        self._api.call("CONFIG_SetCenterFreq", frequency_hz)

    def _spectrum_settings(self, name: str, value: float) -> None:
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"{name} must be finite and positive")
        self._invalidate()
        self._api.call("SPECTRUM_SetEnable", True)
        settings = SpectrumSettings()
        self._api.call("SPECTRUM_GetSettings", ct.byref(settings))
        setattr(settings, name, value)
        settings.verticalUnit = 0  # SpectrumVerticalUnit_dBm.
        self._api.call("SPECTRUM_SetSettings", settings)

    def set_span(self, span_hz: float) -> None:
        self._spectrum_settings("span", span_hz)

    def set_bandwidth(self, bandwidth_hz: float) -> None:
        self._spectrum_settings("rbw", bandwidth_hz)

    def set_num_samples(self, count: int) -> None:
        if count < 2 or int(count) != count:
            raise ValueError("IQ record length must be an integer of at least two samples")
        limit = ct.c_int()
        self._api.call("IQBLK_GetMaxIQRecordLength", ct.byref(limit))
        if count > limit.value:
            raise EquipmentCapabilityError(f"IQ record exceeds runtime limit of {limit.value} samples")
        self._invalidate()
        self._api.call("IQBLK_SetIQRecordLength", count)

    def get_num_samples(self) -> int:
        count = ct.c_int()
        self._api.call("IQBLK_GetIQRecordLength", ct.byref(count))
        if count.value < 2:
            raise EquipmentResponseError("RSA API returned an invalid IQ record length")
        return count.value

    def set_acq_time(self, seconds: float) -> None:
        if not math.isfinite(seconds) or seconds <= 0:
            raise ValueError("acquisition duration must be finite and positive")
        rate = self._double("IQBLK_GetIQSampleRate")
        if rate <= 0:
            raise EquipmentResponseError("RSA API returned an invalid IQ sample rate")
        self.set_num_samples(math.ceil(seconds * rate))

    def set_continuous_run(self, enabled: bool) -> None:
        if enabled:
            raise EquipmentCapabilityError("USB RSA adapter implements finite records; continuous streaming is not implemented")

    def set_trigger_source(self, source: str) -> None:
        token = source.strip().upper()
        if token not in {"IMM", "IMMEDIATE", "FREE", "EXT", "EXTERNAL", "IF", "IFPOWER"}:
            raise EquipmentCapabilityError(f"unsupported USB RSA trigger source {source!r}")
        self._invalidate()
        immediate = token in {"IMM", "IMMEDIATE", "FREE"}
        self._api.call("TRIG_SetTriggerMode", 0 if immediate else 1)
        if not immediate:
            self._api.call("TRIG_SetTriggerSource", 0 if token in {"EXT", "EXTERNAL"} else 1)

    def set_trigger_level(self, level_dbm: float) -> None:
        if not math.isfinite(level_dbm):
            raise ValueError("trigger level must be finite")
        self._invalidate()
        self._api.call("TRIG_SetIFPowerTriggerLevel", level_dbm)

    def set_trigger_position(self, position_dbm: float) -> None:
        # Legacy public argument name; the API quantity is percent, not dBm.
        if not 1 <= position_dbm <= 99:
            raise ValueError("trigger position must be within 1..99 percent")
        self._invalidate()
        self._api.call("TRIG_SetTriggerPositionPercent", position_dbm)

    def run(self) -> None:
        self._invalidate()
        self._api.call("SPECTRUM_SetEnable", False)
        self._api.call("DEVICE_Run")
        self._running = True
        self._run_id = str(time.monotonic_ns())
        try:
            self._api.call("IQBLK_AcquireIQData")
        except Exception:
            self.abort()
            raise

    def _wait(self, function: str, timeout_s: float) -> None:
        if not math.isfinite(timeout_s) or timeout_s <= 0:
            raise ValueError("timeout must be finite and positive")
        deadline = time.monotonic() + timeout_s
        while (remaining := deadline - time.monotonic()) > 0:
            ready = ct.c_bool()
            self._api.call(function, max(1, min(100, math.ceil(remaining * 1000))), ct.byref(ready))
            if ready.value:
                return
        raise EquipmentTimeoutError(f"RSA acquisition did not complete within {timeout_s}s")

    def wait_complete(self, *, timeout_s: float = 60.0) -> None:
        if not self._running:
            if self._iq is not None:
                return
            raise EquipmentCapabilityError("run an IQ acquisition before waiting")
        try:
            self._wait("IQBLK_WaitForIQDataReady", timeout_s)
            count = self.get_num_samples()
            i_data, q_data = (ct.c_float * count)(), (ct.c_float * count)()
            received = ct.c_int()
            self._api.call("IQBLK_GetIQDataDeinterleaved", i_data, q_data, ct.byref(received), count)
            info = IqAcquisitionInfo()
            self._api.call("IQBLK_GetIQAcqInfo", ct.byref(info))
            if received.value != count or info.acqStatus:
                raise EquipmentResponseError(f"RSA IQ record incomplete/invalid: {received.value}/{count}, status {info.acqStatus:#x}")
            iq = np.ctypeslib.as_array(i_data) + 1j * np.ctypeslib.as_array(q_data)
            rate = self._double("IQBLK_GetIQSampleRate")
            if rate <= 0 or not np.isfinite(iq).all():
                raise EquipmentResponseError("RSA IQ samples/rate are invalid")
            self._metadata = {
                "sample_rate_hz": rate, "num_samples": count,
                "center_freq_hz": self._double("CONFIG_GetCenterFreq"),
                "acquisition_bandwidth_hz": self._double("IQBLK_GetIQBandwidth"),
                "sample0_timestamp_ticks": info.sample0Timestamp,
                "trigger_sample_index": info.triggerSampleIndex,
                "trigger_timestamp_ticks": info.triggerTimestamp,
                "acquisition_status": info.acqStatus, "run_id": self._run_id,
                "iq_units": "native RSA API floating IQ",
            }
            self._iq = np.asarray(iq, dtype=np.complex64)
        except Exception:
            self._iq = None
            self._metadata = {}
            raise
        finally:
            self._running = False
            try:
                self._api.call("DEVICE_Stop")
            except Exception:
                self._iq = None
                self._metadata = {}
                raise

    def abort(self) -> None:
        self._iq = None
        self._metadata = {}
        self._running = False
        self._api.call("DEVICE_Stop")

    def acquire(self, *, timeout_s: float = 60.0) -> str:
        if not math.isfinite(timeout_s) or timeout_s <= 0:
            raise ValueError("timeout must be finite and positive")
        self.run()
        self.wait_complete(timeout_s=timeout_s)
        return self._run_id

    def save_IQ_data(self, path: str, *, file_format: str = "bin", key: str = "") -> Path:
        if self._iq is None:
            raise EquipmentCapabilityError("no completed IQ record; acquire before exporting")
        fmt = normalize_iq_format(file_format, path)
        if fmt not in {"bin", "mat", "iq.tar"}:
            raise EquipmentCapabilityError(f"unsupported IQ container {fmt!r}")
        artifact = resolve_artifact_path(path)
        # Preserve the established save_IQ_data float64 encoding; capture_iq uses f32/i16/c64.
        values = np.empty(self._iq.size * 2, dtype="<f8")
        values[0::2], values[1::2] = self._iq.real, self._iq.imag
        metadata = {**self._metadata, "iq_dtype": "float64", "iq_byte_order": "little", "format": fmt}
        if fmt == "mat":
            write_iq_mat(artifact, values.tobytes(), metadata=metadata)
        elif fmt == "iq.tar":
            write_iq_tar(artifact, values.tobytes(), metadata=metadata)
        else:
            write_iq_bin(artifact, values.tobytes())
        record_artifact(domain="equipment", command="save_IQ_data", key=key or f"rtsa_iq_{self._run_id}", path=artifact, value=metadata)
        return artifact

    def capture_iq(
        self, *, center_hz: float, span_hz: float, bandwidth_hz: float, seconds: float,
        path: str, file_format: str = "mat", sample_format: str = "f32",
        timeout_s: float = 120.0, key: str = "",
    ) -> dict[str, Any]:
        fmt = normalize_iq_format(file_format, path)
        if fmt not in {"bin", "mat", "iq.tar"}:
            raise EquipmentCapabilityError(f"unsupported IQ container {fmt!r}")
        normalize_sample_format(sample_format)
        if not all(math.isfinite(v) and v > 0 for v in (span_hz, bandwidth_hz, seconds, timeout_s)):
            raise ValueError("span, IQ bandwidth, duration and timeout must be finite and positive")
        self.set_center_freq(center_hz)
        self.set_span(span_hz)
        self._api.call("IQBLK_SetIQBandwidth", bandwidth_hz)
        self.set_acq_time(seconds)
        self.set_trigger_source("IMM")
        self.acquire(timeout_s=timeout_s)
        assert self._iq is not None
        artifact = resolve_artifact_path(path)
        metadata = write_capture_iq(artifact, self._iq, file_format=fmt, sample_format=sample_format, metadata={
            **self._metadata, "center_hz": center_hz, "span_hz": span_hz,
            "bandwidth_hz": bandwidth_hz, "seconds": seconds,
            "actual_duration_s": self._iq.size / self._metadata["sample_rate_hz"],
        })
        metadata["path"] = str(artifact)
        record_artifact(domain="equipment", command="capture_iq", key=key or f"rtsa_capture_iq_{self._run_id}", path=artifact, value=metadata)
        return metadata

    def save_spectrum_trace_data(self, path: str, *, trace: int = 1) -> Path:
        if trace != 1:
            raise EquipmentCapabilityError("USB RSA adapter exports native spectrum trace 1")
        self._invalidate()
        self._api.call("SPECTRUM_SetEnable", True)
        settings = SpectrumSettings()
        self._api.call("SPECTRUM_GetSettings", ct.byref(settings))
        settings.verticalUnit = 0  # dBm.
        self._api.call("SPECTRUM_SetSettings", settings)
        self._api.call("SPECTRUM_GetSettings", ct.byref(settings))
        count = settings.traceLength
        if count < 2 or not math.isfinite(settings.actualStartFreq) or not math.isfinite(settings.actualFreqStepSize) or settings.actualFreqStepSize <= 0:
            raise EquipmentResponseError("RSA spectrum settings contain an invalid axis/length")
        values = (ct.c_float * count)()
        received = ct.c_int()
        self._api.call("DEVICE_Run")
        try:
            self._api.call("SPECTRUM_AcquireTrace")
            self._wait("SPECTRUM_WaitForDataReady", float(self._config.get("timeout", 5.0)))
            self._api.call("SPECTRUM_GetTrace", 0, count, values, ct.byref(received))
        finally:
            self._api.call("DEVICE_Stop")
        if received.value != count or not all(math.isfinite(v) for v in values):
            raise EquipmentResponseError("RSA spectrum trace is incomplete or invalid")
        span = settings.actualFreqStepSize * (count - 1)
        artifact = resolve_artifact_path(path)
        write_trace_csv(artifact, list(values), center_hz=settings.actualStartFreq + span / 2, span_hz=span, include_frequency=True)
        record_artifact(domain="equipment", command="save_spectrum_trace_data", key="rtsa_spec_trace_1", path=artifact, value={"points": count, "units": "dBm"})
        return artifact

    def close(self) -> None:
        self._iq = None
        self._api.close()
