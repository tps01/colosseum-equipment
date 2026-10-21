"""R&S RTB/RTM and RTE/RTP acquisition with separate waveform dialects.

Manuals: R&S RTB2000 1333.1611.02 and RTM3000 1335.5070.02,
remote-control Waveform Setup and Documenting Results chapters.
"""
from __future__ import annotations

import math
import time
from typing import TYPE_CHECKING, Any

from colosseum_equipment.exceptions import EquipmentCapabilityError, EquipmentResponseError, EquipmentTimeoutError
from colosseum_equipment.instruments._capabilities import supported_commands
from colosseum_equipment.instruments.oscope.generic import GenericOscope, _parse_ascii_waveform
from colosseum_equipment.instruments.registry import instrument_model


if TYPE_CHECKING:
    from colosseum_equipment.transports.base import Transport

@instrument_model("oscope", "rohde-rtb2004", "rohde-rtm3004")
@supported_commands(
    "set_channel_display", "get_channel_display", "set_channel_scale_v", "get_channel_scale_v",
    "set_channel_offset_v", "get_channel_offset_v", "set_timebase_scale", "set_timebase_position_s",
    "set_trigger_source", "set_trigger_level_v", "set_trigger_slope", "set_trigger_mode",
    "set_record_length", "get_record_length", "run", "stop", "abort", "arm_single", "single_acquire",
    "get_acquire_state", "wait_complete", "acquire", "save_waveform",
)
class RohdeRtbRtm(GenericOscope):
    """Single normal waveform per channel; envelope/history/segmented export excluded."""

    def _require_channel(self, channel: int) -> int:
        ch = super()._require_channel(channel)
        if ch > 4:
            raise EquipmentCapabilityError("RTB2004/RTM3004 have four analog channels")
        return ch

    def set_channel_display(self, channel: int, enabled: bool) -> None:
        ch = self._require_channel(channel)
        self._scpi.write(f"CHAN{ch}:STAT {int(enabled)}")

    def get_channel_display(self, channel: int) -> bool:
        ch = self._require_channel(channel)
        return bool(int(float(self._scpi.query(f"CHAN{ch}:STAT?"))))

    def set_record_length(self, points: int) -> None:
        if points < 1:
            raise ValueError("record length must be positive")
        self._scpi.write(f"ACQ:POIN {points}")

    def get_record_length(self) -> int:
        return int(self._scpi.query_float("ACQ:POIN?"))

    def set_trigger_source(self, source: str) -> None:
        token = source.upper().replace("CHAN", "CH")
        if not token.startswith("CH") or not token[2:].isdigit():
            raise EquipmentCapabilityError("qualified trigger sources are analog channels")
        self._require_channel(int(token[2:]))
        self._scpi.write(f"TRIG:A:SOUR {token}")

    def set_trigger_level_v(self, level_v: float) -> None:
        source = self._scpi.query("TRIG:A:SOUR?").upper()
        if not source.startswith("CH") or not source[2:].isdigit():
            raise EquipmentCapabilityError("trigger level requires an analog channel source")
        ch = self._require_channel(int(source[2:]))
        self._scpi.write(f"TRIG:A:LEV{ch} {level_v}")

    def set_trigger_slope(self, slope: str) -> None:
        token = {"rising": "POS", "pos": "POS", "falling": "NEG", "neg": "NEG"}.get(slope.lower())
        if token is None:
            raise EquipmentCapabilityError(f"unsupported edge slope {slope!r}")
        self._scpi.write(f"TRIG:A:EDGE:SLOP {token}")

    def set_trigger_mode(self, mode: str) -> None:
        token = {"auto": "AUTO", "normal": "NORM", "single": "NORM"}.get(mode.lower())
        if token is None:
            raise EquipmentCapabilityError(f"unsupported trigger mode {mode!r}")
        self._scpi.write(f"TRIG:A:MODE {token}")

    def set_timebase_position_s(self, position_s: float) -> None:
        self._scpi.write(f"TIM:POS {position_s}")

    def run(self) -> None:
        self._mark_capture()
        self._scpi.write("RUN")

    def stop(self) -> None:
        self._scpi.write("STOP")

    def abort(self) -> None:
        self.stop()

    def arm_single(self) -> None:
        self._mark_capture()
        self._scpi.write("ACQ:NSIN:COUN 1")
        self._scpi.write("SING")

    def single_acquire(self) -> None:
        self.acquire(timeout_s=float(self._config.get("timeout", 10.0)))

    def get_acquire_state(self) -> str:
        return self._scpi.query("ACQ:STAT?").upper()

    def wait_complete(self, *, timeout_s: float) -> None:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            state = self.get_acquire_state()
            if state.startswith("COMP"):
                return
            if state.startswith(("STOP", "BRE")):
                raise EquipmentResponseError("acquisition stopped/interrupted before completion")
            time.sleep(0.05)
        raise EquipmentTimeoutError("scope single acquisition did not complete")

    def _read_waveform_points(self, channel: int) -> tuple[list[float], dict[str, Any]]:
        ch = self._require_channel(channel)
        if not self.get_acquire_state().startswith("COMP"):
            raise EquipmentCapabilityError("complete the single acquisition before exporting")
        unit = self._scpi.query(f"PROB{ch}:SET:ATT:UNIT?").strip('"').upper()
        if unit != "V":
            raise EquipmentCapabilityError("voltage waveform export requires a voltage probe unit")
        self._scpi.write("FORM ASC")
        self._scpi.write(f"CHAN{ch}:DATA:POIN MAX")
        header = self._scpi.query(f"CHAN{ch}:DATA:HEAD?").split(",")
        if len(header) != 4:
            raise EquipmentResponseError("expected four waveform header fields")
        count, values_per_sample = int(float(header[2])), int(float(header[3]))
        if count < 1 or values_per_sample != 1:
            raise EquipmentCapabilityError("only scalar waveform samples are supported")
        xinc = self._scpi.query_float(f"CHAN{ch}:DATA:XINC?")
        xorigin = self._scpi.query_float(f"CHAN{ch}:DATA:XOR?")
        values = _parse_ascii_waveform(self._scpi.query(f"CHAN{ch}:DATA?"), points_expected=count)
        if len(values) != count or any(not math.isfinite(v) for v in values):
            raise EquipmentResponseError("waveform sample count differs from header")
        if not math.isfinite(xinc) or xinc <= 0 or not math.isfinite(xorigin):
            raise EquipmentResponseError("invalid waveform time axis")
        # ASCII channel data is already scaled; never apply ADC scaling again.
        return values, {"channel": ch, "points": count, "xinc_s": xinc, "xorigin_s": xorigin,
                        "capture_id": self._capture_id, "vertical_units": "V", "encoding": "ASCII"}


@instrument_model("oscope", "rohde-rte1204", "rohde-rtp164")
@supported_commands(
    "set_channel_display", "get_channel_display", "set_channel_scale_v", "get_channel_scale_v",
    "set_channel_offset_v", "get_channel_offset_v", "set_timebase_scale", "set_trigger_mode",
    "run", "stop", "abort", "arm_single", "single_acquire", "wait_complete", "acquire", "save_waveform",
)
class RohdeRteRtp(GenericOscope):
    """RTE/RTP analog waveform 1, native RUNSingle and CHANn:WAV1:DATA.

    RTE user manual 1326.1032.02 v21; RTP 1337.9952.02 v18.
    Manufacturer's executable command reference and example:
    https://rsrtx.readthedocs.io/en/latest/examples.html
    https://rsrtx.readthedocs.io/en/latest/Channel_Waveform_Data_Header.html
    https://rsrtx.readthedocs.io/en/latest/Export_Waveform.html
    Owns the ESR/OPC workflow; use one controller and avoid panel changes during capture.
    """

    def __init__(self, transport: Transport, config: dict[str, Any]) -> None:
        channels = int(config.get("channels") or 4)
        if not 1 <= channels <= 4:
            raise EquipmentCapabilityError("RTE1204/RTP164 have four analog channels")
        super().__init__(transport, {**config, "channels": channels})
        self._single_pending = False
        self._single_complete = False

    def set_channel_display(self, channel: int, enabled: bool) -> None:
        ch = self._require_channel(channel)
        self._scpi.write(f"CHAN{ch}:STAT {int(enabled)}")

    def get_channel_display(self, channel: int) -> bool:
        ch = self._require_channel(channel)
        state = self._scpi.query(f"CHAN{ch}:STAT?").upper()
        if state not in {"0", "1", "OFF", "ON"}:
            raise EquipmentResponseError(f"invalid channel display state {state!r}")
        return state in {"1", "ON"}

    def set_trigger_mode(self, mode: str) -> None:
        token = {"auto": "AUTO", "normal": "NORM", "single": "NORM"}.get(mode.lower())
        if token is None:
            raise EquipmentCapabilityError(f"unsupported trigger mode {mode!r}")
        self._scpi.write(f"TRIG1:MODE {token}")

    def run(self) -> None:
        self._single_pending = self._single_complete = False
        self._mark_capture()
        self._scpi.write("RUNC")

    def stop(self) -> None:
        self._single_pending = self._single_complete = False
        self._scpi.write("STOP")

    def abort(self) -> None:
        self.stop()

    def arm_single(self) -> None:
        self._single_pending = self._single_complete = False
        if self._scpi.query("ACQ:SEGM:STAT?").upper() not in {"0", "OFF"}:
            raise EquipmentCapabilityError("disable fast segmentation for scalar waveform capture")
        self._scpi.write("STOP")
        self._scpi.query("*ESR?")  # Clear stale operation-complete/error events in this owned session.
        self._scpi.write("ACQ:COUN 1")
        self._mark_capture()
        self._scpi.write("RUNS")
        self._scpi.write("*OPC")
        self._single_pending = True

    def single_acquire(self) -> None:
        self.acquire(timeout_s=float(self._config.get("timeout", 10.0)))

    def wait_complete(self, *, timeout_s: float) -> None:
        if self._single_complete:
            return
        if not self._single_pending:
            raise EquipmentCapabilityError("arm a single acquisition before waiting")
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            event = int(self._scpi.query("*ESR?"))
            # IEEE 488.2 query/device/execution/command errors: bits 2..5.
            if event & 0x3C:
                self._single_pending = False
                raise EquipmentResponseError(f"scope acquisition reported ESR errors: {event}")
            if event & 1:
                self._single_pending = False
                if int(self._scpi.query("ACQ:CURR?")) < 1:
                    raise EquipmentResponseError("scope stopped without completing a waveform")
                self._single_complete = True
                return
            time.sleep(0.05)
        raise EquipmentTimeoutError("RTE/RTP single acquisition did not complete")

    def _read_waveform_points(self, channel: int) -> tuple[list[float], dict[str, Any]]:
        ch = self._require_channel(channel)
        if not self._single_complete:
            raise EquipmentCapabilityError("complete a driver-armed single acquisition before export")
        prefix = f"CHAN{ch}:WAV1"
        if self._scpi.query(f"{prefix}:HIST:STAT?").upper() not in {"0", "OFF"}:
            raise EquipmentCapabilityError("disable history display before exporting current capture")
        if self._scpi.query(f"PROB{ch}:SET:ATT:MODE?").upper() not in {"MAN", "MANUAL"}:
            raise EquipmentCapabilityError("select manual probe attenuation/unit for this voltage-only export")
        unit = self._scpi.query(f"PROB{ch}:SET:ATT:UNIT?").strip('"').upper()
        if unit != "V":
            raise EquipmentCapabilityError("voltage CSV requires a voltage probe unit")
        # These export switches also affect DATA? replies, not just saved files.
        for command in ("EXP:WAV:MULT OFF", "EXP:WAV:INCX OFF", "EXP:WAV:RAW OFF", "EXP:WAV:SCOP WFM", "FORM ASC"):
            self._scpi.write(command)
        fields = self._scpi.query(f"{prefix}:DATA:HEAD?").split(",")
        try:
            start, stop, size, values_per_sample = (float(v) for v in fields)
            if not all(math.isfinite(v) for v in (start, stop, size, values_per_sample)):
                raise ValueError("nonfinite waveform header")
            if not size.is_integer() or size < 2 or stop <= start:
                raise ValueError("invalid waveform count or time span")
        except ValueError as exc:
            raise EquipmentResponseError("expected valid four-field waveform header") from exc
        if values_per_sample != 1:
            raise EquipmentCapabilityError("peak/envelope sample pairs are not scalar waveform data")
        count = int(size)
        values = _parse_ascii_waveform(self._scpi.query(f"{prefix}:DATA?"), points_expected=count)
        if len(values) != count or not all(math.isfinite(v) for v in values):
            raise EquipmentResponseError("invalid waveform values or count")
        # The native header defines Stop as the time of the LAST sample.
        return values, {"channel": ch, "points": count, "xorigin_s": start,
                        "xinc_s": (stop - start) / (count - 1), "capture_id": self._capture_id,
                        "vertical_units": "V", "encoding": "scaled ASCII"}
