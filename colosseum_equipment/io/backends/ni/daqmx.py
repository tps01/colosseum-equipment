"""ctypes loader for the NI-DAQmx C library (USB-6501 static DIO)."""

from __future__ import annotations

import ctypes
import sys
from ctypes import POINTER, byref, c_char_p, c_double, c_int32, c_uint8, c_uint32, c_void_p
from typing import Any

from colosseum_equipment.io.exceptions import IoConnectionError

# Line grouping for CreateDIChan / CreateDOChan
DAQmx_Val_ChanPerLine = 0
DAQmx_Val_ChanForAllLines = 1

# Digital output drive type
DAQmx_Val_ActiveDrive = 12573
DAQmx_Val_OpenCollector = 12574

# Fill mode for read/write
DAQmx_Val_GroupByChannel = 0

TaskHandle = c_void_p

_lib: Any | None = None
_lib_path: str | None = None


def _candidate_names() -> list[str]:
    if sys.platform.startswith("win"):
        return ["nicaiu.dll"]
    if sys.platform == "darwin":
        return ["libnidaqmx.dylib", "nidaqmx"]
    return ["libnidaqmx.so", "libnidaqmx.so.1"]


def load_daqmx(*, library: str | None = None) -> Any:  # noqa: ANN401
    """Load NI-DAQmx, optionally from an explicit path. Reuses a matching load."""
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
        "NI-DAQmx runtime not found (nicaiu.dll / libnidaqmx.so). "
        "Install NI-DAQmx, or set library= to the shared-library path."
        + (f" Last error: {last_error}" if last_error else ""),
    )


def reset_daqmx_loader() -> None:
    """Clear the cached library (tests)."""
    global _lib, _lib_path
    _lib = None
    _lib_path = None


def set_daqmx_library(lib: Any) -> None:  # noqa: ANN401
    """Inject a fake library object (tests)."""
    global _lib, _lib_path
    _lib = lib
    _lib_path = "__injected__"


def _bind(lib: Any) -> None:  # noqa: ANN401
    lib.DAQmxCreateTask.argtypes = [c_char_p, POINTER(TaskHandle)]
    lib.DAQmxCreateTask.restype = c_int32

    lib.DAQmxClearTask.argtypes = [TaskHandle]
    lib.DAQmxClearTask.restype = c_int32

    lib.DAQmxStartTask.argtypes = [TaskHandle]
    lib.DAQmxStartTask.restype = c_int32

    lib.DAQmxStopTask.argtypes = [TaskHandle]
    lib.DAQmxStopTask.restype = c_int32

    lib.DAQmxCreateDIChan.argtypes = [TaskHandle, c_char_p, c_char_p, c_int32]
    lib.DAQmxCreateDIChan.restype = c_int32

    lib.DAQmxCreateDOChan.argtypes = [TaskHandle, c_char_p, c_char_p, c_int32]
    lib.DAQmxCreateDOChan.restype = c_int32

    # ChanPerLine: one uInt8 per line
    lib.DAQmxReadDigitalLines.argtypes = [
        TaskHandle,
        c_int32,
        c_double,
        c_int32,
        POINTER(c_uint8),
        c_uint32,
        POINTER(c_int32),
        POINTER(c_int32),
        c_void_p,
    ]
    lib.DAQmxReadDigitalLines.restype = c_int32

    lib.DAQmxWriteDigitalLines.argtypes = [
        TaskHandle,
        c_int32,
        c_int32,
        c_double,
        c_int32,
        POINTER(c_uint8),
        POINTER(c_int32),
        c_void_p,
    ]
    lib.DAQmxWriteDigitalLines.restype = c_int32

    # Channel attribute: DO.OutputDriveType (int32)
    lib.DAQmxSetDOOutputDriveType.argtypes = [TaskHandle, c_char_p, c_int32]
    lib.DAQmxSetDOOutputDriveType.restype = c_int32

    lib.DAQmxGetExtendedErrorInfo.argtypes = [c_char_p, c_uint32]
    lib.DAQmxGetExtendedErrorInfo.restype = c_int32


def check_status(lib: Any, status: int, *, action: str) -> None:  # noqa: ANN401
    if status >= 0:
        return
    buf = ctypes.create_string_buffer(2048)
    try:
        lib.DAQmxGetExtendedErrorInfo(buf, 2048)
        detail = buf.value.decode("utf-8", errors="replace").strip()
    except Exception:  # noqa: BLE001
        detail = ""
    message = f"NI-DAQmx {action} failed (status={status})"
    if detail:
        message = f"{message}: {detail}"
    raise IoConnectionError(message)


def create_task(lib: Any, name: str = "") -> Any:  # noqa: ANN401
    handle = TaskHandle()
    task_name = name.encode("ascii") if name else None
    check_status(lib, lib.DAQmxCreateTask(task_name, byref(handle)), action="CreateTask")
    return handle


def clear_task(lib: Any, handle: Any) -> None:  # noqa: ANN401
    if handle:
        lib.DAQmxClearTask(handle)
