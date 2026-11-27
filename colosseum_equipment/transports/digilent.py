"""Native WaveForms SDK connection shared by AD3 scope, generator and DIO."""

from __future__ import annotations

import ctypes as ct
import sys
from dataclasses import dataclass, field
from math import isfinite
from threading import RLock
from typing import Any

from colosseum_equipment.exceptions import EquipmentCapabilityError, EquipmentConnectionError

DRIVER = "digilent-dwf"
MODEL = "digilent-analog-discovery-3"
ANALOG_OUT_CARRIER = 0
_AD3_DEVICE = 10  # devidDiscovery3 in dwf.h
_lock = RLock()
_sessions: dict[str, _Session] = {}


def channel_index(channel: int) -> int:
    if type(channel) is not int or not 1 <= channel <= 2:
        raise EquipmentCapabilityError("Analog Discovery 3 analog channels are 1 and 2")
    return channel - 1


def finite(value: float, name: str, *, positive: bool = False) -> float:
    if not isfinite(value) or (positive and value <= 0):
        requirement = "finite and positive" if positive else "finite"
        raise ValueError(f"{name} must be {requirement}")
    return value


def _load_library(library: str | None) -> ct.CDLL:
    if sys.platform not in {"win32", "linux"}:
        raise EquipmentConnectionError("Analog Discovery 3 requires Windows or Linux")
    name = library or ("dwf.dll" if sys.platform == "win32" else "libdwf.so")
    try:
        sdk = ct.CDLL(name)
        sdk.FDwfDeviceClose.restype = None
        sdk.FDwfGetLastErrorMsg.restype = None
    except (OSError, AttributeError) as exc:
        raise EquipmentConnectionError(
            f"Cannot load WaveForms runtime {name!r}; install Digilent WaveForms with Adept for this host: {exc}",
        ) from exc
    return sdk


def _checked(sdk: ct.CDLL, function: str, *args: object) -> None:
    try:
        call = getattr(sdk, "FDwf" + function)
    except AttributeError as exc:
        raise EquipmentConnectionError(f"WaveForms runtime lacks FDwf{function}; update WaveForms") from exc
    if not call(*args):
        message = ct.create_string_buffer(512)
        sdk.FDwfGetLastErrorMsg(message)
        detail = message.value.decode(errors="replace")
        raise EquipmentConnectionError(f"WaveForms FDwf{function} failed: {detail or 'no SDK error text'}")


@dataclass
class _Session:
    sdk: ct.CDLL
    handle: int
    library: str | None
    roles: set[str] = field(default_factory=set)


def _open_session(serial: str, library: str | None) -> _Session:
    sdk = _load_library(library)
    count = ct.c_int()
    _checked(sdk, "Enum", _AD3_DEVICE, ct.byref(count))
    for index in range(count.value):
        identity = ct.create_string_buffer(32)
        _checked(sdk, "EnumSN", index, identity)
        if identity.value.decode().upper() != serial:
            continue
        opened = ct.c_int()
        _checked(sdk, "EnumDeviceIsOpened", index, ct.byref(opened))
        if opened.value:
            raise EquipmentConnectionError(
                f"Analog Discovery 3 {serial} is busy; close WaveForms or the other application",
            )
        handle = ct.c_int()
        _checked(sdk, "DeviceOpen", index, ct.byref(handle))
        if not handle.value:
            raise EquipmentConnectionError(f"WaveForms returned an invalid handle for Analog Discovery 3 {serial}")
        try:
            _checked(sdk, "DeviceAutoConfigureSet", handle, 0)
        except EquipmentConnectionError:
            sdk.FDwfDeviceClose(handle)
            raise
        return _Session(sdk, handle.value, library)
    raise EquipmentConnectionError(f"Analog Discovery 3 serial {serial} was not found by WaveForms")


class DigilentConnection:
    """One role's lease on a WaveForms device. The SDK has no raw SCPI interface."""

    lock = _lock

    def __init__(self, role: str, config: dict[str, Any]) -> None:
        self._serial = str(config.get("resource") or "").strip().upper()
        if not self._serial or str(config.get("model") or "").lower() != MODEL:
            raise EquipmentConnectionError(f"{DRIVER} requires model={MODEL!r} and the AD3 serial in resource")
        library = str(config["library"]) if config.get("library") else None
        self._role = role
        self._closed = False
        with self.lock:
            session = _sessions.get(self._serial)
            if session is None:
                session = _sessions[self._serial] = _open_session(self._serial, library)
            if session.library != library or role in session.roles:
                raise EquipmentConnectionError(
                    f"Conflicting {role} configuration for Analog Discovery 3 {self._serial}",
                )
            session.roles.add(role)
            self._session = session

    def call(self, function: str, *args: object) -> None:
        with self.lock:
            if self._closed:
                raise EquipmentConnectionError("Analog Discovery 3 connection is closed")
            _checked(self._session.sdk, function, self._session.handle, *args)

    def write(self, data: str) -> None:  # noqa: ARG002
        raise EquipmentCapabilityError("Analog Discovery 3 does not support raw SCPI")

    def read(self) -> str:
        raise EquipmentCapabilityError("Analog Discovery 3 does not support raw SCPI")

    def query(self, data: str) -> str:  # noqa: ARG002
        raise EquipmentCapabilityError("Analog Discovery 3 does not support raw SCPI")

    def stop_wavegen(self, index: int) -> None:
        # Stopping generation alone can leave the programmed idle voltage on the pin.
        try:
            self.call("AnalogOutNodeEnableSet", index, ANALOG_OUT_CARRIER, 0)
            self.call("AnalogOutConfigure", index, 3)  # Apply without starting.
        finally:
            self.call("AnalogOutConfigure", index, 0)

    def close(self) -> None:
        with self.lock:
            if self._closed:
                return
            session = self._session
            try:
                if self._role == "asg":
                    self.stop_wavegen(0)
                elif self._role == "oscope":
                    self.call("AnalogInConfigure", 0, 0)
                else:
                    self.call("DigitalIOReset")
                    self.call("DigitalIOConfigure")
            finally:
                try:
                    if self._role == "asg":
                        self.stop_wavegen(1)
                finally:
                    self._closed = True
                    session.roles.remove(self._role)
                    if not session.roles:
                        del _sessions[self._serial]
                        session.sdk.FDwfDeviceClose(session.handle)
