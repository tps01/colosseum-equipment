"""Infiniium single-shot acquisition with ADER event completion and WORD data.

Manuals: Keysight Infiniium Programmer's Guide 9018-07141 / 90000 series
9018-06975. Basic analog voltage acquisition; segmented acquisition excluded.
"""
from __future__ import annotations

import math
import struct
import time
from typing import Any

from colosseum_equipment.exceptions import EquipmentCapabilityError, EquipmentResponseError, EquipmentTimeoutError
from colosseum_equipment.instruments._capabilities import supported_commands
from colosseum_equipment.instruments.oscope.generic import GenericOscope
from colosseum_equipment.instruments.registry import instrument_model


@instrument_model("oscope", "keysight-dsaz204a", "keysight-dsa71254")
@supported_commands(
    "set_channel_display", "get_channel_display", "set_channel_scale_v", "get_channel_scale_v",
    "set_channel_offset_v", "get_channel_offset_v", "set_timebase_scale", "set_timebase_position_s",
    "set_trigger_mode", "set_trigger_source", "set_trigger_level_v", "set_trigger_slope",
    "run", "stop", "abort", "arm_single", "single_acquire", "get_acquire_state", "wait_complete",
    "acquire", "measure_vpp", "measure_vmax", "measure_vmin", "measure_vrms", "measure_frequency_hz",
    "measure_period_s", "measure_rise_time_s", "measure_fall_time_s", "save_waveform",
)
class KeysightInfiniium(GenericOscope):
    """ADER is read-to-clear, so completion is latched for repeated fetches."""

    _completed = False
    _single_pending = False

    def _require_channel(self, channel: int) -> int:
        ch = super()._require_channel(channel)
        if ch > 4:
            raise EquipmentCapabilityError("this Infiniium model has four analog channels")
        return ch

    def _require_voltage_channel(self, channel: int) -> None:
        unit = self._scpi.query(f"CHAN{channel}:UNIT?").strip('"').upper()
        if unit not in {"VOLT", "V"}:
            raise EquipmentCapabilityError("voltage measurements require a voltage channel unit")

    def set_timebase_position_s(self, position_s: float) -> None:
        self._scpi.write(f"TIM:POS {position_s}")

    def set_trigger_mode(self, mode: str) -> None:
        token = {"auto": "AUTO", "normal": "TRIG", "single": "TRIG"}.get(mode.lower())
        if token is None:
            raise EquipmentCapabilityError(f"unsupported trigger mode {mode!r}")
        self._scpi.write(f"TRIG:SWE {token}")

    def set_trigger_level_v(self, level_v: float) -> None:
        source = self._scpi.query("TRIG:EDGE:SOUR?").upper()
        if not source.startswith("CHAN") or not source[4:].isdigit():
            raise EquipmentCapabilityError("trigger level requires an analog channel source")
        self._require_channel(int(source[4:]))
        self._scpi.write(f"TRIG:LEV {source},{level_v}")

    def run(self) -> None:
        self._mark_capture()
        self._completed = False
        self._single_pending = False
        self._scpi.write("RUN")

    def stop(self) -> None:
        self._scpi.write("STOP")
        self._single_pending = False
        self._completed = False

    def abort(self) -> None:
        self.stop()

    def arm_single(self) -> None:
        self._completed = False
        self._single_pending = False
        self._scpi.write("STOP")
        self._scpi.query("ADER?")  # discard any event belonging to an older capture
        self._mark_capture()
        self._scpi.write("SING")
        self._single_pending = True

    def get_acquire_state(self) -> str:
        if self._single_pending and not self._completed:
            self._completed = bool(int(self._scpi.query("ADER?")) & 1)
        return "STOP" if self._completed else "RUN"

    def wait_complete(self, *, timeout_s: float) -> None:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            if self.get_acquire_state() == "STOP":
                return
            time.sleep(0.05)
        raise EquipmentTimeoutError("Infiniium acquisition did not complete")

    def single_acquire(self) -> None:
        self.acquire(timeout_s=float(self._config.get("timeout", 10.0)))

    def _require_completed(self) -> None:
        if not self._single_pending or self.get_acquire_state() != "STOP":
            raise EquipmentCapabilityError("complete a single acquisition before fetching")

    def _measure(self, name: str, channel: int) -> float:
        ch = self._require_channel(channel)
        self._require_completed()
        if name in {"VPP", "VMAX", "VMIN", "VRMS"}:
            self._require_voltage_channel(ch)
        value = self._scpi.query_float(f"MEAS:{name}? CHAN{ch}")
        if not math.isfinite(value) or abs(value) >= 9e37:
            raise EquipmentResponseError("invalid or unavailable scope measurement")
        return value

    def measure_vpp(self, channel: int = 1) -> float:
        return self._measure("VPP", channel)

    def measure_vmax(self, channel: int = 1) -> float:
        return self._measure("VMAX", channel)

    def measure_vmin(self, channel: int = 1) -> float:
        return self._measure("VMIN", channel)

    def measure_vrms(self, channel: int = 1) -> float:
        return self._measure("VRMS", channel)

    def measure_frequency_hz(self, channel: int = 1) -> float:
        return self._measure("FREQ", channel)

    def measure_period_s(self, channel: int = 1) -> float:
        return self._measure("PER", channel)

    def measure_rise_time_s(self, channel: int = 1) -> float:
        return self._measure("RIS", channel)

    def measure_fall_time_s(self, channel: int = 1) -> float:
        return self._measure("FALL", channel)

    def _read_waveform_points(self, channel: int) -> tuple[list[float], dict[str, Any]]:
        ch = self._require_channel(channel)
        self._require_completed()
        self._require_voltage_channel(ch)
        self._scpi.write(f"WAV:SOUR CHAN{ch}")
        self._scpi.write("WAV:FORM WORD")
        self._scpi.write("WAV:BYT LSBF")
        self._scpi.write("WAV:STR OFF")
        count = int(self._scpi.query_float("WAV:POIN?"))
        xinc = self._scpi.query_float("WAV:XINC?")
        xorigin = self._scpi.query_float("WAV:XOR?")
        yinc = self._scpi.query_float("WAV:YINC?")
        yorigin = self._scpi.query_float("WAV:YOR?")
        raw = self._scpi.read_binary_block("WAV:DATA?")
        if count < 1 or len(raw) != count * 2:
            raise EquipmentResponseError("Infiniium WORD payload length differs from preamble")
        if not all(math.isfinite(v) for v in (xinc, xorigin, yinc, yorigin)) or xinc <= 0:
            raise EquipmentResponseError("invalid waveform scaling or time axis")
        values = [value * yinc + yorigin for value in struct.unpack(f"<{count}h", raw)]
        return values, {"channel": ch, "points": count, "xinc_s": xinc, "xorigin_s": xorigin,
                        "capture_id": self._capture_id, "vertical_units": "V", "encoding": "WORD LSBF"}
