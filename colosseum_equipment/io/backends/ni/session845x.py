"""Process-local refcounted NI-845x device sessions."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from typing import Any

from colosseum_equipment.io.backends.ni import ni845x as api
from colosseum_equipment.io.exceptions import IoConfigError, IoConnectionError

_lock = Lock()
_sessions: dict[str, _Session] = {}


@dataclass
class _Session:
    resource: str
    handle: Any
    lib: Any
    voltage: float
    refs: int = 0


def acquire_session(
    *,
    resource: str,
    voltage: float,
    library: str | None = None,
) -> _Session:
    """Open or reuse a device session. Voltage must match an existing session."""
    if not resource:
        raise IoConfigError("ni-845x requires resource= (MAX alias or device string)")
    with _lock:
        existing = _sessions.get(resource)
        if existing is not None:
            if abs(existing.voltage - voltage) > 0.05:
                raise IoConfigError(
                    f"ni-845x resource {resource!r} already opened at "
                    f"{existing.voltage} V; cannot reopen at {voltage} V",
                )
            existing.refs += 1
            return existing
        lib = api.load_ni845x(library=library)
        handle = api.open_device(lib, resource)
        try:
            level = api.voltage_level(voltage)
            api.check_status(
                lib,
                lib.ni845xSetIoVoltageLevel(handle, level),
                action="SetIoVoltageLevel",
            )
        except Exception:
            lib.ni845xClose(handle)
            raise
        session = _Session(resource=resource, handle=handle, lib=lib, voltage=voltage, refs=1)
        _sessions[resource] = session
        return session


def release_session(session: _Session) -> None:
    """Drop one reference; close the device when the last user leaves."""
    with _lock:
        current = _sessions.get(session.resource)
        if current is None or current is not session:
            return
        current.refs -= 1
        if current.refs > 0:
            return
        _sessions.pop(session.resource, None)
        try:
            current.lib.ni845xClose(current.handle)
        except Exception as exc:  # noqa: BLE001
            raise IoConnectionError(f"ni845xClose failed: {exc}") from exc


def reset_sessions() -> None:
    """Close all sessions (tests)."""
    with _lock:
        for session in list(_sessions.values()):
            try:
                session.lib.ni845xClose(session.handle)
            except Exception:  # noqa: BLE001
                pass
        _sessions.clear()


def locked(session: _Session) -> _DeviceLock:
    """Context manager that locks the NI-845x device for one transaction."""
    return _DeviceLock(session)


class _DeviceLock:
    def __init__(self, session: _Session) -> None:
        self._session = session

    def __enter__(self) -> _Session:
        api.check_status(
            self._session.lib,
            self._session.lib.ni845xDeviceLock(self._session.handle),
            action="DeviceLock",
        )
        return self._session

    def __exit__(self, *_exc: object) -> None:
        self._session.lib.ni845xDeviceUnlock(self._session.handle)
