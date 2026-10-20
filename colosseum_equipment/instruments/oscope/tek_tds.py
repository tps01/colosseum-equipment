"""TDS2000/3000 acquisition with the older WFMPRE waveform preamble.

Manuals: Tektronix 077-0444-01 (TDS2000C) and 071-0381-03 (TDS3000B).
"""
from __future__ import annotations

import math
import struct
from typing import TYPE_CHECKING, Any

from colosseum_equipment.exceptions import EquipmentCapabilityError, EquipmentResponseError
from colosseum_equipment.instruments._capabilities import supported_commands
from colosseum_equipment.instruments.oscope.tek_mdo4000 import TekMdo4000Oscope
from colosseum_equipment.instruments.registry import instrument_model

if TYPE_CHECKING:
    from colosseum_equipment.transports.base import Transport


@instrument_model(
    "oscope", "tektronix-tds3034b", "tektronix-tds3032b", "tektronix-tds2024c", "tektronix-tds2014",
)
@supported_commands(
    "set_channel_display", "get_channel_display", "set_channel_scale_v", "get_channel_scale_v",
    "set_channel_coupling", "get_channel_coupling", "set_timebase_scale", "set_trigger_mode",
    "set_trigger_source", "set_trigger_level_v", "set_trigger_slope", "force_trigger",
    "set_acquire_mode", "set_acquire_averages", "run", "stop", "arm_single", "single_acquire",
    "abort", "get_acquire_state", "wait_complete", "acquire", "measure_vpp", "measure_vmax",
    "measure_vmin", "measure_vrms", "measure_frequency_hz", "measure_period_s",
    "measure_rise_time_s", "measure_fall_time_s", "save_waveform",
)
class TekTdsOscope(TekMdo4000Oscope):
    """Analog sample/average acquisition; screenshots and envelope mode excluded."""

    def __init__(self, transport: Transport, config: dict[str, Any]) -> None:
        maximum = 2 if str(config.get("model")).lower() == "tektronix-tds3032b" else 4
        channels = int(config.get("channels") or maximum)
        if not 1 <= channels <= maximum:
            raise EquipmentCapabilityError(f"model has {maximum} analog channels")
        super().__init__(transport, {**config, "channels": channels})
        self._scpi.write("HEADER OFF")

    def set_trigger_source(self, source: str) -> None:
        token = source.strip().upper()
        if token.startswith("CH"):
            self._require_channel(int(token[2:]))
        elif token not in {"EXT", "LINE"}:
            raise EquipmentCapabilityError(f"unsupported trigger source {source!r}")
        self._scpi.write(f"TRIG:MAIN:EDGE:SOU {token}")

    def set_trigger_level_v(self, level_v: float) -> None:
        self._scpi.write(f"TRIG:MAIN:LEV {level_v}")

    def set_trigger_mode(self, mode: str) -> None:
        token = {"auto": "AUTO", "normal": "NORMAL", "single": "NORMAL"}.get(mode.lower())
        if token is None:
            raise EquipmentCapabilityError(f"unsupported trigger mode {mode!r}")
        self._scpi.write(f"TRIG:MAIN:MODE {token}")

    def set_trigger_slope(self, slope: str) -> None:
        token = {"rising": "RISE", "pos": "RISE", "falling": "FALL", "neg": "FALL"}.get(slope.lower())
        if token is None:
            raise EquipmentCapabilityError(f"unsupported trigger slope {slope!r}")
        self._scpi.write(f"TRIG:MAIN:EDGE:SLO {token}")

    def set_acquire_mode(self, mode: str) -> None:
        if mode.lower() not in {"sample", "average"}:
            raise EquipmentCapabilityError("TDS export is qualified for sample/average acquisition")
        super().set_acquire_mode(mode)

    def single_acquire(self) -> None:
        self.acquire(timeout_s=float(self._config.get("timeout", 10.0)))

    def _require_stopped(self) -> None:
        if self.get_acquire_state().upper() not in {"0", "STOP"}:
            raise EquipmentCapabilityError("finish the single acquisition before fetching its data")

    def _immeas(self, meas_type: str, channel: int) -> float:
        self._require_stopped()
        value = super()._immeas(meas_type, channel)
        if not math.isfinite(value) or abs(value) >= 9e37:
            raise EquipmentResponseError("scope measurement is unavailable or out of range")
        return value

    def _read_waveform_points(self, channel: int) -> tuple[list[float], dict[str, Any]]:
        ch = self._require_channel(channel)
        self._require_stopped()
        self._scpi.write(f"DATA:SOU CH{ch}")
        self._scpi.write("DATA:ENC RIBINARY")
        self._scpi.write("DATA:WIDTH 1")
        self._scpi.write("DATA:START 1")
        count = int(self._scpi.query_float("WFMPRE:NR_PT?"))
        if count < 1:
            raise EquipmentResponseError("waveform preamble has no samples")
        self._scpi.write(f"DATA:STOP {count}")
        xinc = self._scpi.query_float("WFMPRE:XINCR?")
        xzero = self._scpi.query_float("WFMPRE:XZERO?")
        ptoff = self._scpi.query_float("WFMPRE:PT_OFF?")
        ymult = self._scpi.query_float("WFMPRE:YMULT?")
        yoff = self._scpi.query_float("WFMPRE:YOFF?")
        yzero = self._scpi.query_float("WFMPRE:YZERO?")
        xunit = self._scpi.query("WFMPRE:XUNIT?").strip('\"').upper()
        yunit = self._scpi.query("WFMPRE:YUNIT?").strip('\"').upper()
        if xunit not in {"S", "SECONDS"} or yunit not in {"V", "VOLTS"}:
            raise EquipmentCapabilityError("time/voltage CSV requires second/volt waveform units")
        raw = self._scpi.read_binary_block("CURVE?")
        if len(raw) != count:
            raise EquipmentResponseError(f"expected {count} waveform bytes, received {len(raw)}")
        if not all(math.isfinite(v) for v in (xinc, xzero, ptoff, ymult, yoff, yzero)) or xinc <= 0:
            raise EquipmentResponseError("invalid waveform scaling or time axis")
        samples = struct.unpack(f"{count}b", raw)
        values = [(value - yoff) * ymult + yzero for value in samples]
        return values, {
            "channel": ch, "points": count, "xinc_s": xinc,
            "xorigin_s": xzero - ptoff * xinc, "capture_id": self._capture_id,
            "vertical_units": "V", "encoding": "RIBINARY",
        }


@instrument_model(
    "oscope", "tektronix-mso58", "tektronix-mso64", "tektronix-tbs2204b",
    "tektronix-mso4104", "tektronix-tds7704b",
)
@supported_commands(
    "set_channel_display", "get_channel_display", "set_channel_scale_v", "get_channel_scale_v",
    "set_channel_offset_v", "get_channel_offset_v", "set_timebase_scale", "set_trigger_mode",
    "set_trigger_source", "set_trigger_level_v", "set_trigger_slope", "force_trigger",
    "run", "stop", "abort", "arm_single", "single_acquire", "get_acquire_state", "wait_complete",
    "acquire", "save_waveform",
)
class TekWfmOutOscope(TekMdo4000Oscope):
    """077-1305-05, Waveform Transfer and appendix D (analog YT only).

    https://download.tek.com/manual/5_6-Series-MSO54-MSO56-MSO58-MSO58L-MSO64-Programmer-Manual_EN-US_077130505.pdf
    Also: TBS2000B 077-1149-03, MSO4000 programmer manual waveform group,
    TDS7000/CSA7000 PHP014070 waveform group (family reference for TDS7704B).
    No immediate-measurement aliases or digital FlexChannel exports.
    """

    def __init__(self, transport: Transport, config: dict[str, Any]) -> None:
        maximum = 8 if str(config.get("model")).lower() == "tektronix-mso58" else 4
        channels = int(config.get("channels") or maximum)
        if not 1 <= channels <= maximum:
            raise EquipmentCapabilityError(f"model has {maximum} analog channels")
        super().__init__(transport, {**config, "channels": channels})
        self._scpi.write("HEADER OFF")

    def set_channel_display(self, channel: int, enabled: bool) -> None:
        ch = self._require_channel(channel)
        if self._model in {"tektronix-mso58", "tektronix-mso64"}:
            self._scpi.write(f"DISP:WAVEV1:CH{ch}:STATE {int(enabled)}")
        else:
            super().set_channel_display(ch, enabled)

    def get_channel_display(self, channel: int) -> bool:
        ch = self._require_channel(channel)
        if self._model in {"tektronix-mso58", "tektronix-mso64"}:
            return bool(int(self._scpi.query(f"DISP:WAVEV1:CH{ch}:STATE?")))
        return super().get_channel_display(ch)

    def set_trigger_level_v(self, level_v: float) -> None:
        source = self._scpi.query("TRIG:A:EDGE:SOU?").upper()
        if not source.startswith("CH") or not source[2:].isdigit():
            raise EquipmentCapabilityError("trigger level requires an analog CH source")
        self._require_channel(int(source[2:]))
        self._scpi.write(f"TRIG:A:LEV:{source} {level_v}")

    def single_acquire(self) -> None:
        self.acquire(timeout_s=float(self._config.get("timeout", 10.0)))

    def _read_waveform_points(self, channel: int) -> tuple[list[float], dict[str, Any]]:
        ch = self._require_channel(channel)
        if self.get_acquire_state().upper() not in {"0", "STOP"}:
            raise EquipmentCapabilityError("stop/complete acquisition before waveform export")
        self._scpi.write(f"DATA:SOU CH{ch}")
        self._scpi.write("DATA:ENC RIBINARY")
        self._scpi.write("DATA:WIDTH 2")
        self._scpi.write("DATA:START 1")
        count = int(self._scpi.query_float("WFMO:NR_PT?"))
        if count < 1:
            raise EquipmentResponseError("waveform has no samples")
        self._scpi.write(f"DATA:STOP {count}")
        if self._scpi.query("WFMO:PT_FMT?").upper() not in {"Y", "YT"}:
            raise EquipmentCapabilityError("only scalar analog YT waveforms are supported")
        if self._scpi.query("WFMO:XUNIT?").strip('"').upper() not in {"S", "SECONDS"}:
            raise EquipmentCapabilityError("waveform time axis must be seconds")
        if self._scpi.query("WFMO:YUNIT?").strip('"').upper() not in {"V", "VOLTS"}:
            raise EquipmentCapabilityError("waveform vertical axis must be volts")
        xinc = self._scpi.query_float("WFMO:XINCR?")
        xzero = self._scpi.query_float("WFMO:XZERO?")
        ptoff = self._scpi.query_float("WFMO:PT_OFF?")
        ymult = self._scpi.query_float("WFMO:YMULT?")
        yoff = self._scpi.query_float("WFMO:YOFF?")
        yzero = self._scpi.query_float("WFMO:YZERO?")
        if not all(math.isfinite(v) for v in (xinc, xzero, ptoff, ymult, yoff, yzero)) or xinc <= 0:
            raise EquipmentResponseError("invalid waveform scaling")
        raw = self._scpi.read_binary_block("CURVE?")
        if len(raw) != count * 2:
            raise EquipmentResponseError("waveform byte count differs from preamble")
        values = [(v - yoff) * ymult + yzero for v in struct.unpack(f">{count}h", raw)]
        return values, {"channel": ch, "points": count, "xinc_s": xinc,
                        "xorigin_s": xzero - ptoff * xinc, "capture_id": self._capture_id,
                        "vertical_units": "V", "encoding": "RIBINARY16 big-endian"}
