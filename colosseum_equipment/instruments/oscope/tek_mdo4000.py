"""Tektronix MDO4000/MSO4000B/DPO4000B oscilloscope (SCPI).

Manual: 077-0510-03 Programmer Manual — horizontal scale, measurements, acquire.
Catalog: https://www.tek.com/en/oscilloscope/mso4000-dpo4000-manual/mdo4000c-mdo4000b-mdo4000-mso4000b-dpo4000b-and-mdo3000-0

Validated workflow (documented):
  preset → set_channel_* → set_timebase_* → set_trigger_edge_* → set_acquire_*
  → single_acquire / acquire → measure_* / save_waveform / save_screenshot
"""

from __future__ import annotations

import csv
import struct
import time
from pathlib import Path
from typing import Any

from colosseum_equipment._paths import resolve_artifact_path
from colosseum_equipment.evidence import record_artifact
from colosseum_equipment.exceptions import (
    EquipmentCapabilityError,
    EquipmentResponseError,
    EquipmentTimeoutError,
)
from colosseum_equipment.instruments.oscope.generic import GenericOscope
from colosseum_equipment.instruments.registry import instrument_model
from colosseum_equipment.protocols.scpi import wait_opc

_TEK_ACQUIRE = {
    "sample": "SAMple",
    "peak": "PEAKdetect",
    "average": "AVErage",
    "hres": "HIRes",
}


@instrument_model(
    "oscope",
    "tektronix-mdo4000",
    "tektronix-mdo3012",
    "tektronix-mdo3014",
    "tektronix-mdo3022",
    "tektronix-mdo3024",
    "tektronix-mdo3032",
    "tektronix-mdo3034",
    "tektronix-mdo3052",
    "tektronix-mdo3054",
    "tektronix-mdo3102",
    "tektronix-mdo3104",
    "tektronix-mso4104b",
    "tektronix-mso4054b",
    "tektronix-dpo4034b",
    "tektronix-dpo4104b",
    "tektronix-mdo4104c",
)
class TekMdo4000Oscope(GenericOscope):
    _model = "tektronix-mdo4000"

    def set_channel_display(self, channel: int, enabled: bool) -> None:
        ch = self._require_channel(channel)
        self._scpi.write(f"SELect:CH{ch} {'ON' if enabled else 'OFF'}")

    def get_channel_display(self, channel: int) -> bool:
        ch = self._require_channel(channel)
        return bool(int(float(self._scpi.query(f"SELect:CH{ch}?"))))

    def set_channel_scale_v(self, channel: int, volts_per_div: float) -> None:
        ch = self._require_channel(channel)
        self._scpi.write(f"CH{ch}:SCAle {volts_per_div}")

    def get_channel_scale_v(self, channel: int) -> float:
        ch = self._require_channel(channel)
        return self._scpi.query_float(f"CH{ch}:SCAle?")

    def set_channel_offset_v(self, channel: int, offset_v: float) -> None:
        ch = self._require_channel(channel)
        self._scpi.write(f"CH{ch}:OFFSet {offset_v}")

    def get_channel_offset_v(self, channel: int) -> float:
        ch = self._require_channel(channel)
        return self._scpi.query_float(f"CH{ch}:OFFSet?")

    def set_channel_coupling(self, channel: int, coupling: str) -> None:
        ch = self._require_channel(channel)
        mode = coupling.strip().upper()
        if mode not in {"AC", "DC", "GND"}:
            raise EquipmentCapabilityError(f"unsupported coupling `{coupling}`")
        self._scpi.write(f"CH{ch}:COUPling {mode}")

    def get_channel_coupling(self, channel: int) -> str:
        ch = self._require_channel(channel)
        return self._scpi.query(f"CH{ch}:COUPling?").strip().upper()

    def set_channel_probe_attenuation(self, channel: int, attenuation: float) -> None:
        ch = self._require_channel(channel)
        self._scpi.write(f"CH{ch}:PRObe:GAIN {1.0 / attenuation}")

    def get_channel_probe_attenuation(self, channel: int) -> float:
        ch = self._require_channel(channel)
        gain = self._scpi.query_float(f"CH{ch}:PRObe:GAIN?")
        if gain == 0:
            raise EquipmentResponseError("probe gain is zero")
        return 1.0 / gain

    def set_channel_bandwidth_limit(self, channel: int, enabled: bool) -> None:
        ch = self._require_channel(channel)
        self._scpi.write(f"CH{ch}:BANdwidth {'TWEnty' if enabled else 'FULLbandwidth'}")

    def get_channel_bandwidth_limit(self, channel: int) -> bool:
        ch = self._require_channel(channel)
        raw = self._scpi.query(f"CH{ch}:BANdwidth?").strip().upper()
        return "FULL" not in raw

    def set_channel_impedance(self, channel: int, ohms: float) -> None:
        ch = self._require_channel(channel)
        if abs(ohms - 50.0) < 1e-6:
            self._scpi.write(f"CH{ch}:TERmination FIFTy")
        elif abs(ohms - 1e6) < 1.0:
            self._scpi.write(f"CH{ch}:TERmination MEGohm")
        else:
            raise EquipmentCapabilityError(
                f"oscope model `{self._model}` impedance must be 50 or 1e6 ohm",
            )

    def get_channel_impedance(self, channel: int) -> float:
        ch = self._require_channel(channel)
        raw = self._scpi.query(f"CH{ch}:TERmination?").strip().upper()
        if "FIF" in raw or "50" in raw:
            return 50.0
        return 1e6

    def set_timebase_scale(self, seconds_per_div: float) -> None:
        self._scpi.write(f"HORizontal:SCAle {seconds_per_div}")

    def set_timebase_position_s(self, position_s: float) -> None:
        self._scpi.write(f"HORizontal:POSition {position_s}")

    def set_record_length(self, points: int) -> None:
        self._scpi.write(f"HORizontal:RECOrdlength {int(points)}")

    def get_record_length(self) -> int:
        return int(float(self._scpi.query("HORizontal:RECOrdlength?")))

    def set_trigger_mode(self, mode: str) -> None:
        normalized = mode.strip().lower()
        mapping = {"auto": "AUTO", "normal": "NORMal", "single": "NORMal"}
        if normalized not in mapping:
            raise EquipmentCapabilityError(f"unsupported trigger mode `{mode}`")
        self._scpi.write(f"TRIGger:A:MODe {mapping[normalized]}")

    def set_trigger_source(self, source: str) -> None:
        self._scpi.write(f"TRIGger:A:EDGE:SOUrce {source}")

    def set_trigger_level_v(self, level_v: float) -> None:
        self._scpi.write(f"TRIGger:A:LEVel {level_v}")

    def set_trigger_slope(self, slope: str) -> None:
        normalized = slope.strip().lower()
        mapping = {
            "rising": "RISe",
            "falling": "FALL",
            "pos": "RISe",
            "neg": "FALL",
        }
        if normalized not in mapping:
            raise EquipmentCapabilityError(f"unsupported trigger slope `{slope}`")
        self._scpi.write(f"TRIGger:A:EDGE:SLOpe {mapping[normalized]}")

    def set_trigger_holdoff_s(self, holdoff_s: float) -> None:
        self._scpi.write(f"TRIGger:A:HOLDoff:TIME {holdoff_s}")

    def force_trigger(self) -> None:
        self._scpi.write("TRIGger FORCe")

    def set_acquire_mode(self, mode: str) -> None:
        key = mode.strip().lower()
        if key not in _TEK_ACQUIRE:
            raise EquipmentCapabilityError(f"unsupported acquire mode `{mode}`")
        self._scpi.write(f"ACQuire:MODe {_TEK_ACQUIRE[key]}")

    def set_acquire_averages(self, count: int) -> None:
        self._scpi.write(f"ACQuire:NUMAVg {int(count)}")

    def run(self) -> None:
        self._mark_capture()
        self._scpi.write("ACQuire:STOPAfter RUNSTop")
        self._scpi.write("ACQuire:STATE RUN")

    def stop(self) -> None:
        self._scpi.write("ACQuire:STATE STOP")

    def abort(self) -> None:
        self._scpi.write("ACQuire:STATE STOP")

    def single_acquire(self) -> None:
        self._mark_capture()
        self._scpi.write("ACQuire:STOPAfter SEQuence")
        self._scpi.write("ACQuire:STATE RUN")
        wait_opc(self._scpi)

    def get_acquire_state(self) -> str:
        return self._scpi.query("ACQuire:STATE?").strip()

    def wait_complete(self, *, timeout_s: float) -> None:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            state = self.get_acquire_state().upper()
            if state in {"0", "STOP"} or "STOP" in state:
                return
            try:
                if self._scpi.query("*OPC?").strip().startswith("1"):
                    return
            except Exception:
                pass
            time.sleep(0.05)
        raise EquipmentTimeoutError(
            f"oscope model `{self._model}` acquisition did not complete within {timeout_s}s",
        )

    def acquire(self, *, timeout_s: float = 10.0) -> str:
        self._mark_capture()
        self._scpi.write("ACQuire:STOPAfter SEQuence")
        self._scpi.write("ACQuire:STATE RUN")
        self.wait_complete(timeout_s=timeout_s)
        return self._capture_id

    def _immeas(self, meas_type: str, channel: int) -> float:
        ch = self._require_channel(channel)
        source = f"CH{ch}"
        self._scpi.write(f"MEASUrement:IMMed:SOUrce1 {source}")
        self._scpi.write(f"MEASUrement:IMMed:TYPe {meas_type}")
        return self._scpi.query_float("MEASUrement:IMMed:VALue?")

    def measure_vpp(self, channel: int = 1) -> float:
        return self._immeas("PK2pk", channel)

    def measure_vmax(self, channel: int = 1) -> float:
        return self._immeas("MAXIMUM", channel)

    def measure_vmin(self, channel: int = 1) -> float:
        return self._immeas("MINIMUM", channel)

    def measure_vrms(self, channel: int = 1) -> float:
        return self._immeas("RMS", channel)

    def measure_frequency_hz(self, channel: int = 1) -> float:
        return self._immeas("FREQuency", channel)

    def measure_period_s(self, channel: int = 1) -> float:
        return self._immeas("PERIod", channel)

    def measure_rise_time_s(self, channel: int = 1) -> float:
        return self._immeas("RISe", channel)

    def measure_fall_time_s(self, channel: int = 1) -> float:
        return self._immeas("FALL", channel)

    def _read_waveform_points(self, channel: int) -> tuple[list[float], dict[str, Any]]:
        ch = self._require_channel(channel)
        self._scpi.write(f"DATa:SOUrce CH{ch}")
        self._scpi.write("DATa:ENCdg RIBinary")
        self._scpi.write("DATa:WIDth 1")
        self._scpi.write("DATa:STARt 1")
        self._scpi.write("DATa:STOP 10000000")
        xincr = self._scpi.query_float("WFMOutpre:XINcr?")
        xzero = self._scpi.query_float("WFMOutpre:XZEro?")
        ymult = self._scpi.query_float("WFMOutpre:YMUlt?")
        yoff = self._scpi.query_float("WFMOutpre:YOFf?")
        yzero = self._scpi.query_float("WFMOutpre:YZEro?")
        points_expected = int(float(self._scpi.query("WFMOutpre:NR_Pt?")))
        raw = self._scpi.read_binary_block("CURVe?")
        if points_expected > 0 and len(raw) < int(0.9 * points_expected):
            raise EquipmentResponseError(
                f"waveform truncated: got {len(raw)} bytes, preamble expected {points_expected}",
            )
        # Signed RIBinary bytes
        samples = list(struct.unpack(f">{len(raw)}b", raw))
        volts = [(s - yoff) * ymult + yzero for s in samples]
        meta = {
            "channel": ch,
            "points": len(volts),
            "points_expected": points_expected,
            "xinc_s": xincr,
            "xorigin_s": xzero,
            "ymult_v": ymult,
            "yoff": yoff,
            "yzero_v": yzero,
            "vertical_units": "V",
            "encoding": "RIBinary",
            "capture_id": self._capture_id,
        }
        return volts, meta

    def save_waveform(self, *, channel: int, path: str, key: str = "") -> Path:
        volts, meta = self._read_waveform_points(channel)
        artifact_path = resolve_artifact_path(path)
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        xinc = float(meta["xinc_s"])
        xorigin = float(meta["xorigin_s"])
        with artifact_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["time_s", "voltage_v"])
            for index, voltage in enumerate(volts):
                writer.writerow([xorigin + index * xinc, voltage])
        evidence_key = key or f"oscope_wave_ch{channel}_{self._capture_id or 'last'}"
        record_artifact(
            domain="equipment",
            command="save_waveform",
            key=evidence_key,
            path=artifact_path,
            value=meta,
        )
        return artifact_path

    def save_screenshot(self, path: str, *, key: str = "") -> Path:
        artifact_path = resolve_artifact_path(path)
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        # Prefer binary hardcopy when available; fall back to instrument SAVE:IMAGE.
        try:
            self._scpi.write("HARDCopy:FORMat PNG")
            payload = self._scpi.read_binary_block("HARDCopy STARt")
            artifact_path.write_bytes(payload)
            byte_len = len(payload)
        except Exception:
            self._scpi.write(f'SAVE:IMAGE "{artifact_path}"')
            byte_len = 0
        evidence_key = key or f"oscope_screenshot_{self._capture_id or 'last'}"
        record_artifact(
            domain="equipment",
            command="save_screenshot",
            key=evidence_key,
            path=artifact_path,
            value={"capture_id": self._capture_id, "bytes": byte_len},
        )
        return artifact_path
