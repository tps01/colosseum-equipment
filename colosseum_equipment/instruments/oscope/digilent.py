"""Analog Discovery 3 finite, two-channel WaveForms acquisition."""

from __future__ import annotations

import ctypes as ct
import time
from math import isfinite, sqrt
from typing import Any

from colosseum_equipment.exceptions import EquipmentCapabilityError, EquipmentResponseError, EquipmentTimeoutError
from colosseum_equipment.instruments._capabilities import supported_commands
from colosseum_equipment.instruments.oscope.generic import GenericOscope
from colosseum_equipment.instruments.registry import _confirmed_generic_commands, instrument_model
from colosseum_equipment.transports.base import Transport
from colosseum_equipment.transports.digilent import MODEL, DigilentConnection, channel_index, finite

_COMMANDS = (
    "set_channel_display", "set_channel_scale_v", "get_channel_scale_v",
    "set_channel_offset_v", "get_channel_offset_v", "set_timebase_scale", "set_timebase_position_s",
    "set_record_length", "get_record_length", "set_trigger_source", "set_trigger_slope",
    "set_trigger_level_v", "arm_single", "single_acquire", "acquire", "wait_complete",
    "get_acquire_state", "force_trigger", "stop", "abort", "save_waveform",
    "measure_vmin", "measure_vmax", "measure_vpp", "measure_vrms",
)
_DIVISIONS = 10
_AD3_MAX_BUFFER = 65536
_DONE = 2  # DwfStateDone
_STATES = {0: "ready", 1: "armed", _DONE: "complete", 3: "running", 4: "configuring", 5: "prefill"}


@instrument_model("oscope", MODEL)
@supported_commands(*_COMMANDS)
@_confirmed_generic_commands("acquire", "save_waveform")
class DigilentScope(GenericOscope):
    def __init__(self, transport: Transport, config: dict[str, Any]) -> None:
        if not isinstance(transport, DigilentConnection):
            raise EquipmentCapabilityError("Analog Discovery 3 requires its WaveForms connection")
        super().__init__(transport, {**config, "channels": 2})
        self._device = transport
        self._enabled = [True, True]
        self._scale = [0.5, 0.5]
        self._offset = [0.0, 0.0]
        self._points = 4096
        self._seconds_per_div = 0.001
        self._position = 0.0
        self._trigger: int | None = None
        self._slope = 0
        self._level = 0.0
        self._armed_channels: tuple[int, ...] = ()
        self._triggered = False
        self._capture: dict[int, list[float]] = {}
        self._xinc = self._xorigin = 0.0

    def set_channel_display(self, channel: int, enabled: bool) -> None:
        self._enabled[channel_index(channel)] = enabled

    def set_channel_scale_v(self, channel: int, volts_per_div: float) -> None:
        self._scale[channel_index(channel)] = finite(volts_per_div, "scope scale", positive=True)

    def get_channel_scale_v(self, channel: int) -> float:
        return self._scale[channel_index(channel)]

    def set_channel_offset_v(self, channel: int, offset_v: float) -> None:
        self._offset[channel_index(channel)] = finite(offset_v, "scope offset")

    def get_channel_offset_v(self, channel: int) -> float:
        return self._offset[channel_index(channel)]

    def set_record_length(self, points: int) -> None:
        if type(points) is not int or not 2 <= points <= _AD3_MAX_BUFFER:
            raise ValueError(f"scope record length must be 2..{_AD3_MAX_BUFFER}")
        self._points = points

    def get_record_length(self) -> int:
        return self._points

    def set_timebase_scale(self, seconds_per_div: float) -> None:
        self._seconds_per_div = finite(seconds_per_div, "scope timebase", positive=True)

    def set_timebase_position_s(self, position_s: float) -> None:
        self._position = finite(position_s, "scope timebase position")

    def set_trigger_source(self, source: str) -> None:
        sources = {"NONE": None, "CHAN1": 0, "CHAN2": 1, "CH1": 0, "CH2": 1}
        try:
            self._trigger = sources[source.strip().upper()]
        except KeyError:
            raise EquipmentCapabilityError("AD3 trigger source must be NONE, CHAN1 or CHAN2") from None

    def set_trigger_slope(self, slope: str) -> None:
        slopes = {"rising": 0, "falling": 1, "pos": 0, "neg": 1}
        try:
            self._slope = slopes[slope.strip().lower()]
        except KeyError:
            raise EquipmentCapabilityError("AD3 trigger slope must be rising or falling") from None

    def set_trigger_level_v(self, level_v: float) -> None:
        self._level = finite(level_v, "trigger level")

    def arm_single(self) -> None:
        with self._device.lock:
            channels = tuple(index for index, enabled in enumerate(self._enabled) if enabled)
            if not channels or (self._trigger is not None and self._trigger not in channels):
                raise EquipmentCapabilityError("Enable at least one scope input and any selected trigger channel")
            rate = finite(self._points / (_DIVISIONS * self._seconds_per_div), "sample rate", positive=True)
            self.abort()
            call = self._device.call
            call("AnalogInAcquisitionModeSet", 0)  # acqmodeSingle
            for index in range(2):
                call("AnalogInChannelEnableSet", index, int(index in channels))
                if index in channels:
                    call("AnalogInChannelRangeSet", index, ct.c_double(_DIVISIONS * self._scale[index]))
                    call("AnalogInChannelOffsetSet", index, ct.c_double(self._offset[index]))
            self._configure_sampling(rate)
            self._configure_trigger()
            call("AnalogInConfigure", 1, 1)
            self._armed_channels = channels
            self._triggered = self._trigger is not None
            self._mark_capture()

    def _configure_sampling(self, rate: float) -> None:
        call = self._device.call
        minimum, maximum = ct.c_int(), ct.c_int()
        call("AnalogInBufferSizeInfo", ct.byref(minimum), ct.byref(maximum))
        if not minimum.value <= self._points <= maximum.value:
            raise ValueError(f"AD3 buffer for enabled channels supports {minimum.value}..{maximum.value} samples")
        call("AnalogInBufferSizeSet", self._points)
        low, high = ct.c_double(), ct.c_double()
        call("AnalogInFrequencyInfo", ct.byref(low), ct.byref(high))
        if not low.value <= rate <= high.value:
            raise ValueError(f"AD3 sample rate must be {low.value:g}..{high.value:g} samples/s")
        call("AnalogInFrequencySet", ct.c_double(rate))

    def _configure_trigger(self) -> None:
        call = self._device.call
        call("AnalogInTriggerSourceSet", ct.c_ubyte(0 if self._trigger is None else 2))
        if self._trigger is not None:
            call("AnalogInTriggerTypeSet", 0)  # trigtypeEdge
            call("AnalogInTriggerChannelSet", self._trigger)
            call("AnalogInTriggerConditionSet", self._slope)
            call("AnalogInTriggerLevelSet", ct.c_double(self._level))
            call("AnalogInTriggerPositionSet", ct.c_double(self._position))
            call("AnalogInTriggerAutoTimeoutSet", ct.c_double(0))

    def _status(self, *, read_data: bool) -> int:
        state = ct.c_ubyte()
        self._device.call("AnalogInStatus", int(read_data), ct.byref(state))
        return state.value

    def get_acquire_state(self) -> str:
        with self._device.lock:
            if self._capture:
                return "complete"
            if not self._armed_channels:
                return "idle"
            state = self._status(read_data=False)
            return _STATES.get(state, f"state {state}")

    def wait_complete(self, *, timeout_s: float) -> None:
        deadline = time.monotonic() + finite(timeout_s, "scope timeout", positive=True)
        with self._device.lock:
            capture_id = self._capture_id
        while True:
            with self._device.lock:
                if capture_id != self._capture_id or not self._armed_channels:
                    raise EquipmentResponseError("No current AD3 acquisition; arm the scope first")
                if self._capture:
                    return
                if self._status(read_data=True) == _DONE:
                    self._read_capture()
                    return
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise EquipmentTimeoutError("Analog Discovery 3 acquisition did not complete")
            time.sleep(min(remaining, 0.01))

    def _read_capture(self) -> None:
        call = self._device.call
        points, actual_rate, position = ct.c_int(), ct.c_double(), ct.c_double()
        call("AnalogInStatusSamplesValid", ct.byref(points))
        call("AnalogInFrequencyGet", ct.byref(actual_rate))
        if self._triggered:
            call("AnalogInTriggerPositionStatus", ct.byref(position))
        if not (1 < points.value <= _AD3_MAX_BUFFER and isfinite(actual_rate.value)
                and actual_rate.value > 0 and isfinite(position.value)):
            raise EquipmentResponseError("Invalid WaveForms acquisition metadata")
        samples = (ct.c_double * points.value)()
        capture = {}
        for index in self._armed_channels:
            call("AnalogInStatusData", index, samples, points.value)
            capture[index] = list(samples)
            if not all(map(isfinite, capture[index])):
                raise EquipmentResponseError("WaveForms acquisition contains nonfinite samples")
        self._xinc = 1 / actual_rate.value
        self._xorigin = position.value - points.value * self._xinc / 2 if self._triggered else 0.0
        self._capture = capture

    def force_trigger(self) -> None:
        with self._device.lock:
            if not self._armed_channels or self._capture:
                raise EquipmentResponseError("Arm the AD3 before forcing a trigger")
            self._device.call("AnalogInTriggerForce")

    def single_acquire(self) -> None:
        self.acquire(timeout_s=float(self._config.get("timeout", 10.0)))

    def abort(self) -> None:
        with self._device.lock:
            self._capture = {}
            self._capture_id = ""
            self._armed_channels = ()
            self._device.call("AnalogInConfigure", 0, 0)

    def stop(self) -> None:
        self.abort()

    def _samples(self, channel: int) -> list[float]:
        index = channel_index(channel)
        with self._device.lock:
            if index not in self._capture:
                raise EquipmentResponseError("No completed AD3 capture for this channel; arm and wait first")
            return self._capture[index]

    def _read_waveform_points(self, channel: int) -> tuple[list[float], dict[str, Any]]:
        with self._device.lock:
            volts = self._samples(channel)
            return volts, {
                "points": len(volts), "xinc_s": self._xinc, "xorigin_s": self._xorigin,
                "vertical_units": "V", "encoding": "waveforms", "capture_id": self._capture_id,
            }

    def measure_vmin(self, channel: int = 1) -> float:
        return min(self._samples(channel))

    def measure_vmax(self, channel: int = 1) -> float:
        return max(self._samples(channel))

    def measure_vpp(self, channel: int = 1) -> float:
        volts = self._samples(channel)
        return max(volts) - min(volts)

    def measure_vrms(self, channel: int = 1) -> float:
        volts = self._samples(channel)
        return sqrt(sum(voltage**2 for voltage in volts) / len(volts))
