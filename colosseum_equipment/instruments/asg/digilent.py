"""Analog Discovery 3 standard Wavegen functions."""

from __future__ import annotations

import ctypes as ct
from contextlib import suppress
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Any

from colosseum_equipment.exceptions import EquipmentCapabilityError, EquipmentConnectionError
from colosseum_equipment.instruments._capabilities import supported_commands
from colosseum_equipment.instruments.asg.generic import GenericASG
from colosseum_equipment.instruments.registry import instrument_model
from colosseum_equipment.transports.base import Transport
from colosseum_equipment.transports.digilent import ANALOG_OUT_CARRIER, MODEL, DigilentConnection, channel_index, finite

_WAVEFORMS = {"sine": 1, "square": 2, "triangle": 3}  # FUNC values from dwf.h
_MAX_PEAK_V = 5.0


@dataclass(frozen=True)
class _Waveform:
    function: int = _WAVEFORMS["sine"]
    frequency: float = 1000.0
    vpp: float = 1.0
    offset: float = 0.0


@instrument_model("asg", MODEL)
@supported_commands("set_waveform", "set_frequency", "set_amplitude_vpp", "set_offset_v", "set_output")
class DigilentWavegen(GenericASG):
    def __init__(self, transport: Transport, config: dict[str, Any]) -> None:
        if not isinstance(transport, DigilentConnection):
            raise EquipmentCapabilityError("Analog Discovery 3 requires its WaveForms connection")
        self._device = transport
        self._waveforms = [_Waveform(), _Waveform()]
        self._running = [False, False]
        super().__init__(transport, {**config, "channels": 2})

    def set_waveform(self, waveform: str, *, channel: int = 1) -> None:
        try:
            function = _WAVEFORMS[waveform.strip().lower()]
        except KeyError:
            raise EquipmentCapabilityError("AD3 Wavegen supports sine, square and triangle") from None
        self._update(channel, lambda current: replace(current, function=function))

    def set_frequency(self, frequency: float, *, channel: int = 1) -> None:
        finite(frequency, "Wavegen frequency", positive=True)
        self._update(channel, lambda current: replace(current, frequency=frequency))

    def set_amplitude_vpp(self, vpp: float, *, channel: int = 1) -> None:
        finite(vpp, "Wavegen amplitude")
        self._update(channel, lambda current: replace(current, vpp=vpp))

    def set_offset_v(self, offset_v: float, *, channel: int = 1) -> None:
        finite(offset_v, "Wavegen offset")
        self._update(channel, lambda current: replace(current, offset=offset_v))

    def _update(self, channel: int, update: Callable[[_Waveform], _Waveform]) -> None:
        index = channel_index(channel)
        with self._device.lock:
            waveform = update(self._waveforms[index])
            if waveform.vpp < 0 or abs(waveform.offset) + waveform.vpp / 2 > _MAX_PEAK_V:
                raise ValueError("AD3 Wavegen offset ± half the Vpp must stay within ±5 V")
            if self._running[index]:
                self._apply(index, waveform, mode=3)  # apply without restarting
            self._waveforms[index] = waveform

    def _apply(self, index: int, waveform: _Waveform, *, mode: int) -> None:
        call = self._device.call
        low, high = ct.c_double(), ct.c_double()
        call("AnalogOutNodeFrequencyInfo", index, ANALOG_OUT_CARRIER, ct.byref(low), ct.byref(high))
        if not low.value <= waveform.frequency <= high.value:
            raise ValueError(f"AD3 Wavegen frequency must be {low.value:g}..{high.value:g} Hz")
        try:
            call("AnalogOutNodeEnableSet", index, ANALOG_OUT_CARRIER, 1)
            call("AnalogOutNodeFunctionSet", index, ANALOG_OUT_CARRIER, ct.c_ubyte(waveform.function))
            call("AnalogOutNodeFrequencySet", index, ANALOG_OUT_CARRIER, ct.c_double(waveform.frequency))
            call("AnalogOutNodeAmplitudeSet", index, ANALOG_OUT_CARRIER, ct.c_double(waveform.vpp / 2))
            call("AnalogOutNodeOffsetSet", index, ANALOG_OUT_CARRIER, ct.c_double(waveform.offset))
            call("AnalogOutConfigure", index, mode)
        except EquipmentConnectionError:
            with suppress(EquipmentConnectionError):
                self._device.stop_wavegen(index)
                self._running[index] = False
            raise

    def set_output(self, enabled: bool, *, channel: int = 1) -> None:
        index = channel_index(channel)
        with self._device.lock:
            if enabled:
                self._apply(index, self._waveforms[index], mode=1)
            else:
                self._device.stop_wavegen(index)
            self._running[index] = enabled
