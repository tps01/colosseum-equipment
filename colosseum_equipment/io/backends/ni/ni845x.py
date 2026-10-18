"""ctypes loader for the NI-845x C library (USB-8451 / USB-8452)."""

from __future__ import annotations

import ctypes
import sys
from ctypes import (
    POINTER,
    byref,
    c_char_p,
    c_int32,
    c_uint8,
    c_uint16,
    c_uint32,
    c_void_p,
)
from typing import Any

from colosseum_equipment.io.exceptions import IoConnectionError

# I/O voltage level constants (numeric values match NI header)
kNi845x33Volts = 33
kNi845x25Volts = 25
kNi845x18Volts = 18
kNi845x15Volts = 15
kNi845x12Volts = 12

VOLTAGE_TO_LEVEL: dict[float, int] = {
    3.3: kNi845x33Volts,
    2.5: kNi845x25Volts,
    1.8: kNi845x18Volts,
    1.5: kNi845x15Volts,
    1.2: kNi845x12Volts,
}

# I2C address size
kNi845xI2cAddress7Bit = 0
kNi845xI2cAddress10Bit = 1

# DIO driver type
kNi845xOpenDrain = 0
kNi845xPushPull = 1

# SPI clock polarity / phase
kNi845xSpiClockPolarityIdleLow = 0
kNi845xSpiClockPolarityIdleHigh = 1
kNi845xSpiClockPhaseFirstEdge = 0
kNi845xSpiClockPhaseSecondEdge = 1

NiHandle = c_void_p

_lib: Any | None = None
_lib_path: str | None = None


def _candidate_names() -> list[str]:
    if sys.platform.startswith("win"):
        return ["Ni845x.dll"]
    if sys.platform == "darwin":
        return ["libni845x.dylib", "ni845x"]
    return ["libni845x.so", "libni845x.so.1"]


def load_ni845x(*, library: str | None = None) -> Any:  # noqa: ANN401
    """Load NI-845x, optionally from an explicit path. Reuses a matching load."""
    global _lib, _lib_path
    path = (library or "").strip() or None
    # Reuse an injected fake (tests) or a prior load for the same path / default search.
    if _lib is not None and (path is None or _lib_path == path):
        return _lib
    names = [path] if path else _candidate_names()
    last_error: Exception | None = None
    for name in names:
        if not name:
            continue
        try:
            lib = ctypes.CDLL(name)
        except OSError as exc:
            last_error = exc
            continue
        _bind(lib)
        _lib = lib
        _lib_path = path
        return lib
    raise IoConnectionError(
        "NI-845x runtime not found (Ni845x.dll / libni845x.so). "
        "Install NI-845x, or set library= to the shared-library path."
        + (f" Last error: {last_error}" if last_error else ""),
    )


def reset_ni845x_loader() -> None:
    """Clear the cached library (tests)."""
    global _lib, _lib_path
    _lib = None
    _lib_path = None


def set_ni845x_library(lib: Any) -> None:  # noqa: ANN401
    """Inject a fake library object (tests)."""
    global _lib, _lib_path
    _lib = lib
    _lib_path = "__injected__"


def _bind(lib: Any) -> None:  # noqa: ANN401
    lib.ni845xOpen.argtypes = [c_char_p, POINTER(NiHandle)]
    lib.ni845xOpen.restype = c_int32

    lib.ni845xClose.argtypes = [NiHandle]
    lib.ni845xClose.restype = c_int32

    lib.ni845xDeviceLock.argtypes = [NiHandle]
    lib.ni845xDeviceLock.restype = c_int32

    lib.ni845xDeviceUnlock.argtypes = [NiHandle]
    lib.ni845xDeviceUnlock.restype = c_int32

    lib.ni845xSetIoVoltageLevel.argtypes = [NiHandle, c_uint8]
    lib.ni845xSetIoVoltageLevel.restype = c_int32

    lib.ni845xSetTimeout.argtypes = [NiHandle, c_uint32]
    lib.ni845xSetTimeout.restype = c_int32

    lib.ni845xStatusToString.argtypes = [c_int32, c_uint32, c_char_p]
    lib.ni845xStatusToString.restype = None

    # DIO
    lib.ni845xDioSetPortLineDirectionMap.argtypes = [NiHandle, c_uint8, c_uint8]
    lib.ni845xDioSetPortLineDirectionMap.restype = c_int32

    lib.ni845xDioSetDriverType.argtypes = [NiHandle, c_uint8, c_uint8]
    lib.ni845xDioSetDriverType.restype = c_int32

    lib.ni845xDioWritePort.argtypes = [NiHandle, c_uint8, c_uint8]
    lib.ni845xDioWritePort.restype = c_int32

    lib.ni845xDioReadPort.argtypes = [NiHandle, c_uint8, POINTER(c_uint8)]
    lib.ni845xDioReadPort.restype = c_int32

    lib.ni845xDioWriteLine.argtypes = [NiHandle, c_uint8, c_uint8, c_int32]
    lib.ni845xDioWriteLine.restype = c_int32

    lib.ni845xDioReadLine.argtypes = [NiHandle, c_uint8, c_uint8, POINTER(c_int32)]
    lib.ni845xDioReadLine.restype = c_int32

    # I2C configuration
    lib.ni845xI2cConfigurationOpen.argtypes = [POINTER(NiHandle)]
    lib.ni845xI2cConfigurationOpen.restype = c_int32

    lib.ni845xI2cConfigurationClose.argtypes = [NiHandle]
    lib.ni845xI2cConfigurationClose.restype = c_int32

    lib.ni845xI2cConfigurationSetAddress.argtypes = [NiHandle, c_uint16]
    lib.ni845xI2cConfigurationSetAddress.restype = c_int32

    lib.ni845xI2cConfigurationSetAddressSize.argtypes = [NiHandle, c_int32]
    lib.ni845xI2cConfigurationSetAddressSize.restype = c_int32

    lib.ni845xI2cConfigurationSetClockRate.argtypes = [NiHandle, c_uint16]
    lib.ni845xI2cConfigurationSetClockRate.restype = c_int32

    lib.ni845xI2cSetPullupEnable.argtypes = [NiHandle, c_uint8]
    lib.ni845xI2cSetPullupEnable.restype = c_int32

    lib.ni845xI2cWrite.argtypes = [NiHandle, NiHandle, c_uint32, c_char_p]
    lib.ni845xI2cWrite.restype = c_int32

    lib.ni845xI2cRead.argtypes = [NiHandle, NiHandle, c_uint32, c_char_p]
    lib.ni845xI2cRead.restype = c_int32

    lib.ni845xI2cWriteRead.argtypes = [
        NiHandle,
        NiHandle,
        c_uint32,
        c_char_p,
        c_uint32,
        c_char_p,
    ]
    lib.ni845xI2cWriteRead.restype = c_int32

    # SPI configuration
    lib.ni845xSpiConfigurationOpen.argtypes = [POINTER(NiHandle)]
    lib.ni845xSpiConfigurationOpen.restype = c_int32

    lib.ni845xSpiConfigurationClose.argtypes = [NiHandle]
    lib.ni845xSpiConfigurationClose.restype = c_int32

    lib.ni845xSpiConfigurationSetChipSelect.argtypes = [NiHandle, c_uint32]
    lib.ni845xSpiConfigurationSetChipSelect.restype = c_int32

    lib.ni845xSpiConfigurationSetClockRate.argtypes = [NiHandle, c_uint16]
    lib.ni845xSpiConfigurationSetClockRate.restype = c_int32

    lib.ni845xSpiConfigurationSetClockPolarity.argtypes = [NiHandle, c_int32]
    lib.ni845xSpiConfigurationSetClockPolarity.restype = c_int32

    lib.ni845xSpiConfigurationSetClockPhase.argtypes = [NiHandle, c_int32]
    lib.ni845xSpiConfigurationSetClockPhase.restype = c_int32

    lib.ni845xSpiConfigurationSetNumBitsPerSample.argtypes = [NiHandle, c_uint16]
    lib.ni845xSpiConfigurationSetNumBitsPerSample.restype = c_int32

    lib.ni845xSpiWriteRead.argtypes = [
        NiHandle,
        NiHandle,
        c_uint32,
        c_char_p,
        POINTER(c_uint32),
        c_char_p,
    ]
    lib.ni845xSpiWriteRead.restype = c_int32


def check_status(lib: Any, status: int, *, action: str) -> None:  # noqa: ANN401
    if status >= 0:
        return
    buf = ctypes.create_string_buffer(1024)
    try:
        lib.ni845xStatusToString(c_int32(status), 1024, buf)
        detail = buf.value.decode("utf-8", errors="replace").strip()
    except Exception:  # noqa: BLE001
        detail = ""
    message = f"NI-845x {action} failed (status={status})"
    if detail:
        message = f"{message}: {detail}"
    raise IoConnectionError(message)


def voltage_level(voltage: float) -> int:
    """Map a float voltage to an NI voltage-level constant."""
    for expected, level in VOLTAGE_TO_LEVEL.items():
        if abs(voltage - expected) < 0.05:
            return level
    raise IoConnectionError(
        f"unsupported NI-845x voltage {voltage}; "
        f"use one of {sorted(VOLTAGE_TO_LEVEL)}",
    )


def open_device(lib: Any, resource: str) -> Any:  # noqa: ANN401
    handle = NiHandle()
    check_status(
        lib,
        lib.ni845xOpen(resource.encode("ascii"), byref(handle)),
        action="Open",
    )
    return handle
