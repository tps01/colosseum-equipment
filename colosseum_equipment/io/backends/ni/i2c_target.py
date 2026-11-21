"""Event-driven I2C target support for the USB-8452."""

from __future__ import annotations

from ctypes import POINTER, byref, c_bool, c_int32, c_uint8, c_uint16, c_uint32
from threading import RLock
from typing import Any

from colosseum_equipment.exceptions import EquipmentCapabilityError, EquipmentTimeoutError
from colosseum_equipment.io.backends._usb import target_address, target_data, target_response, target_wait_ms
from colosseum_equipment.io.backends.ni import ni845x as api
from colosseum_equipment.io.backends.ni import session845x
from colosseum_equipment.io.backends.ni.models import limits_for, resolve_voltage
from colosseum_equipment.io.exceptions import IoConfigError, IoConnectionError

# NI-845x Hardware and Software Manual, chapter 10. Bind lazily so older
# runtimes and the USB-8451 retain their existing controller support.
_HANDLE = api.NiHandle
_TARGET_FUNCTIONS = {
    "ConfigurationOpen": [POINTER(_HANDLE)],
    "ConfigurationSetAddress": [_HANDLE, c_uint16],
    "ConfigurationClose": [_HANDLE],
    "Start": [_HANDLE, _HANDLE],
    "Stop": [_HANDLE, _HANDLE],
    "WaitForEvent": [_HANDLE, _HANDLE, c_uint32, POINTER(c_uint8), POINTER(c_uint16)],
    "Read": [_HANDLE, _HANDLE, c_uint16, POINTER(c_uint16), POINTER(c_uint8), POINTER(c_bool)],
    "Write": [_HANDLE, _HANDLE, c_uint16, POINTER(c_uint8)],
    "GetWriteInfo": [_HANDLE, _HANDLE, POINTER(c_uint16)],
}
_NO_EVENT = 0
_COMMAND = 1
_DATA_AVAILABLE = 2
_DATA_REQUESTED = 3
_WRITE_COMPLETE = 4
_DEFAULT_DATA_BUFFER = 128


class Ni8452I2cTarget:
    def __init__(self, config: dict[str, Any]) -> None:
        model = str(config.get("model") or "")
        if limits_for(model).model != "usb-8452":
            raise EquipmentCapabilityError("NI I2C target mode requires a USB-8452")
        self._address = target_address(config)
        self._lock = RLock()
        self._active = False
        self._closed = False
        self._config = _HANDLE()
        self._response = b""
        self._session = session845x.acquire_session(
            resource=str(config.get("resource") or ""),
            voltage=resolve_voltage(model, config.get("voltage")),
            library=config.get("library"),
            timeout_ms=config.get("timeout_ms"),
            exclusive=True,
        )
        try:
            lib = self._session.lib
            for name, arguments in _TARGET_FUNCTIONS.items():
                function = getattr(lib, f"ni845xI2cSlave{name}", None)
                if function is None:
                    raise EquipmentCapabilityError(f"NI-845x runtime lacks I2C target operation {name}")
                function.argtypes = arguments
                function.restype = c_int32
            with session845x.locked(self._session):
                self._call("ConfigurationOpen", byref(self._config))
                self._call("ConfigurationSetAddress", self._config, self._address)
                api.check_status(
                    lib, lib.ni845xI2cSetPullupEnable(self._session.handle, int(bool(config.get("pullup", True)))),
                    action="I2cSetPullupEnable",
                )
        except Exception:
            self.close()
            raise

    def _call(self, action: str, *args: object) -> None:
        name = f"ni845xI2cSlave{action}"
        lib = self._session.lib
        api.check_status(lib, getattr(lib, name)(*args), action=name)

    def target_start(self, response: bytes) -> None:
        target_response(response, 65535)
        with self._lock:
            if self._closed or self._active:
                raise IoConfigError("NI I2C target must be open and stopped before arming")
            with session845x.locked(self._session) as session:
                self._call("Start", session.handle, self._config)
            self._response = response
            self._active = True

    def target_receive(self, timeout_ms: int) -> dict[str, Any]:
        timeout = target_wait_ms(timeout_ms)
        with self._lock:
            if not self._active:
                raise IoConfigError("start the NI I2C target before receiving")
            with session845x.locked(self._session) as session:
                event, flags = c_uint8(), c_uint16()
                self._call("WaitForEvent", session.handle, self._config, timeout, byref(event), byref(flags))
                result = self._process_event(event.value)
            return {**result, "address": self._address, "flags": flags.value}

    def _process_event(self, event: int) -> dict[str, Any]:
        handle, config = self._session.handle, self._config
        if event in {_COMMAND, _DATA_AVAILABLE}:
            data = (c_uint8 * _DEFAULT_DATA_BUFFER)()
            received, cleared = c_uint16(), c_bool()
            self._call("Read", handle, config, len(data), byref(received), data, byref(cleared))
            if not cleared.value or received.value > len(data):
                raise IoConnectionError("NI I2C target receive event was incomplete")
            return target_data(bytes(data[:received.value]))
        if event == _DATA_REQUESTED:
            response = (c_uint8 * len(self._response)).from_buffer_copy(self._response)
            self._call("Write", handle, config, len(response), response)
            return {"event": "read_requested", "nbytes": len(response)}
        if event == _WRITE_COMPLETE:
            written = c_uint16()
            self._call("GetWriteInfo", handle, config, byref(written))
            return {"event": "transmitted", "nbytes": written.value}
        if event == _NO_EVENT:
            raise EquipmentTimeoutError("no NI I2C target event before the timeout")
        raise IoConnectionError(f"unexpected NI I2C target event {event}")

    def target_stop(self) -> None:
        with self._lock:
            if self._active:
                with session845x.locked(self._session) as session:
                    self._call("Stop", session.handle, self._config)
                self._active = False

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            try:
                try:
                    self.target_stop()
                finally:
                    if self._config:
                        self._call("ConfigurationClose", self._config)
            finally:
                self._closed = True
                self._active = False
                session845x.release_session(self._session)
