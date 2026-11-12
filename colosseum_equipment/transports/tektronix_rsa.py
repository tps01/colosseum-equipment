"""Direct RSA API session; vendor runtime is installed separately, never bundled.

Signatures: Tektronix 077-1031-04 Rev A, DEVICE / CONFIG / IQBLK / SPECTRUM.
The library has a process-global device context: one live session per process.
"""

from __future__ import annotations

import ctypes as ct
import os
import threading
from pathlib import Path
from typing import Any, NoReturn

from colosseum_equipment.exceptions import (
    EquipmentCapabilityError,
    EquipmentConnectionError,
    EquipmentResponseError,
    EquipmentTimeoutError,
)

USB_RSA_MODELS = frozenset(f"tektronix-{model}" for model in (
    "rsa306", "rsa306b", "rsa503a", "rsa507a", "rsa603a", "rsa607a",
))
_session_lock = threading.Lock()
_session_active = False
_SEARCH_MAX_DEVICES = 20
_SERIAL_LENGTH = 100
_TYPE_LENGTH = 20


class SpectrumSettings(ct.Structure):
    """C ABI fields, including the actual frequency axis returned by the runtime."""

    _fields_ = [
        ("span", ct.c_double), ("rbw", ct.c_double), ("enableVBW", ct.c_bool),
        ("vbw", ct.c_double), ("traceLength", ct.c_int), ("window", ct.c_int),
        ("verticalUnit", ct.c_int), ("actualStartFreq", ct.c_double),
        ("actualStopFreq", ct.c_double), ("actualFreqStepSize", ct.c_double),
        ("actualRBW", ct.c_double), ("actualVBW", ct.c_double),
        ("actualNumIQSamples", ct.c_double),
    ]


class IqAcquisitionInfo(ct.Structure):
    _fields_ = [
        ("sample0Timestamp", ct.c_uint64), ("triggerSampleIndex", ct.c_uint64),
        ("triggerTimestamp", ct.c_uint64), ("acqStatus", ct.c_uint32),
    ]


class RsaApiTransport:
    """Own the native context; text I/O is deliberately unavailable."""

    def __init__(self, config: dict[str, Any]) -> None:
        global _session_active
        self._closed = True
        self._connected = False
        self._directory: Any = None
        self._call_lock = threading.RLock()
        with _session_lock:
            if _session_active:
                raise EquipmentConnectionError("RSA API supports one active device context per process")
            _session_active = True
        try:
            library = str(config.get("rsa_api_library") or "C:/Tektronix/RSA_API/lib/x64/RSA_API.dll")
            path = Path(library).resolve()
            if not path.is_file():
                raise EquipmentConnectionError(
                    "install the RSA API runtime and set rsa_api_library to its library path",
                )
            if os.name == "nt":
                self._directory = os.add_dll_directory(str(path.parent))
            self._dll = ct.CDLL(str(path))
            self._bind()
            self._closed = False
            self._connect(str(config.get("resource", "")), str(config.get("model", "")))
        except Exception:
            if self._connected:
                self._dll.DEVICE_Disconnect()
            if self._directory is not None:
                self._directory.close()
            self._closed = True
            with _session_lock:
                _session_active = False
            raise

    def _bind(self) -> None:
        p_int, p_double = ct.POINTER(ct.c_int), ct.POINTER(ct.c_double)
        p_bool, p_float = ct.POINTER(ct.c_bool), ct.POINTER(ct.c_float)
        signatures: dict[str, list[Any]] = {
            "DEVICE_Search": [p_int, p_int, ct.c_char_p, ct.c_char_p],
            "DEVICE_Connect": [ct.c_int], "DEVICE_GetSerialNumber": [ct.c_char_p],
            "DEVICE_GetNomenclature": [ct.c_char_p], "DEVICE_Disconnect": [],
            "DEVICE_Run": [], "DEVICE_Stop": [], "CONFIG_Preset": [],
            "CONFIG_SetCenterFreq": [ct.c_double], "CONFIG_GetCenterFreq": [p_double],
            "CONFIG_SetReferenceLevel": [ct.c_double],
            "IQBLK_SetIQBandwidth": [ct.c_double], "IQBLK_GetIQBandwidth": [p_double],
            "IQBLK_GetIQSampleRate": [p_double], "IQBLK_SetIQRecordLength": [ct.c_int],
            "IQBLK_GetIQRecordLength": [p_int], "IQBLK_GetMaxIQRecordLength": [p_int],
            "IQBLK_AcquireIQData": [], "IQBLK_WaitForIQDataReady": [ct.c_int, p_bool],
            "IQBLK_GetIQDataDeinterleaved": [p_float, p_float, p_int, ct.c_int],
            "IQBLK_GetIQAcqInfo": [ct.POINTER(IqAcquisitionInfo)],
            "TRIG_SetTriggerMode": [ct.c_int], "TRIG_SetTriggerSource": [ct.c_int],
            "TRIG_SetIFPowerTriggerLevel": [ct.c_double],
            "TRIG_SetTriggerPositionPercent": [ct.c_double],
            "SPECTRUM_SetEnable": [ct.c_bool], "SPECTRUM_SetDefault": [],
            "SPECTRUM_GetSettings": [ct.POINTER(SpectrumSettings)],
            "SPECTRUM_SetSettings": [SpectrumSettings], "SPECTRUM_AcquireTrace": [],
            "SPECTRUM_WaitForDataReady": [ct.c_int, p_bool],
            "SPECTRUM_GetTrace": [ct.c_int, ct.c_int, p_float, p_int],
        }
        for name, args in signatures.items():
            function = getattr(self._dll, name)
            function.argtypes = args
            function.restype = ct.c_int

    def call(self, name: str, *args: object) -> None:
        with self._call_lock:
            if self._closed:
                raise EquipmentConnectionError("RSA API session is closed")
            status = int(getattr(self._dll, name)(*args))
        if status == 3001:  # errorTimeout, documented ReturnStatus value.
            raise EquipmentTimeoutError(f"RSA API {name} timed out")
        if status:
            raise EquipmentResponseError(f"RSA API {name} failed with status {status}")

    def _connect(self, serial: str, model: str) -> None:
        if not serial:
            raise EquipmentConnectionError("RSA API resource must be the device serial number or 'auto'")
        found = ct.c_int()
        ids = (ct.c_int * _SEARCH_MAX_DEVICES)()
        # DEVICE_Search writes a 2-D array for every discovered device, not one string.
        serial_buffer = ct.create_string_buffer(_SERIAL_LENGTH * _SEARCH_MAX_DEVICES)
        type_buffer = ct.create_string_buffer(_TYPE_LENGTH * _SEARCH_MAX_DEVICES)
        self.call("DEVICE_Search", ct.byref(found), ids, serial_buffer, type_buffer)
        if not 1 <= found.value <= _SEARCH_MAX_DEVICES:
            raise EquipmentConnectionError(f"RSA API search found {found.value} devices")
        if serial == "auto" and found.value != 1:
            raise EquipmentConnectionError("multiple RSA devices found; configure the exact serial number")
        for index in range(found.value):
            self.call("DEVICE_Connect", ids[index])
            self._connected = True
            self.call("DEVICE_GetSerialNumber", serial_buffer)
            if serial == "auto" or serial_buffer.value.decode("ascii") == serial:
                self.call("DEVICE_GetNomenclature", type_buffer)
                actual = type_buffer.value.decode("ascii").strip().lower()
                if actual != model.removeprefix("tektronix-"):
                    raise EquipmentConnectionError(f"RSA API found {actual!r}, expected {model!r}")
                self.call("CONFIG_Preset")
                return
            self.call("DEVICE_Disconnect")
            self._connected = False
        raise EquipmentConnectionError(f"RSA serial {serial!r} was not found")

    def write(self, _data: str) -> NoReturn:
        raise EquipmentCapabilityError("direct RSA API sessions do not accept SCPI text")

    def read(self) -> NoReturn:
        raise EquipmentCapabilityError("direct RSA API sessions do not expose text reads")

    def query(self, _data: str) -> NoReturn:
        raise EquipmentCapabilityError("direct RSA API sessions do not accept SCPI queries")

    def close(self) -> None:
        global _session_active
        with self._call_lock:
            if self._closed:
                return
            try:
                try:
                    self.call("DEVICE_Stop")
                finally:
                    if self._connected:
                        self.call("DEVICE_Disconnect")
            finally:
                self._connected = False
                self._closed = True
                if self._directory is not None:
                    self._directory.close()
                with _session_lock:
                    _session_active = False
