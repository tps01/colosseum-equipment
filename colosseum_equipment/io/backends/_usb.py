"""Local session ownership and validation for USB protocol adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock
from typing import TYPE_CHECKING, Any

from colosseum_equipment.io.exceptions import IoConfigError, IoConnectionError

if TYPE_CHECKING:
    from collections.abc import Callable


def checked(result: int, action: str) -> int:
    if result < 0:
        raise IoConnectionError(f"{action} failed (vendor status {result})")
    return result


def count(result: int, expected: int, action: str) -> None:
    checked(result, action)
    if result != expected:
        raise IoConnectionError(f"{action}: short transfer ({result}/{expected})")


def size(value: int, maximum: int) -> int:
    if not 0 <= value <= maximum:
        raise IoConfigError(f"transfer length must be 0..{maximum}; got {value}")
    return value


def address(value: int, bits: int) -> None:
    if bits not in (7, 10) or not 0 <= value < (1 << bits):
        raise IoConfigError("I2C address must fit address_bits (7 or 10)")


def spi_settings(clock_hz: int, mode: int, chip_select: int, bits: int, max_cs: int) -> None:
    if clock_hz <= 0:
        raise IoConfigError("clock_hz must be positive")
    if mode not in range(4):
        raise IoConfigError("SPI mode must be 0..3")
    if not 0 <= chip_select <= max_cs:
        raise IoConfigError(f"chip_select must be 0..{max_cs}")
    if bits != 8:
        raise IoConfigError("this adapter backend requires bits_per_word = 8")


@dataclass
class Session:
    api: Any
    handle: int
    settings: tuple[object, ...]
    closer: Callable[[], None]
    lock: RLock = field(default_factory=RLock)
    refs: int = 1


_lock = RLock()
_sessions: dict[tuple[str, str], Session] = {}


def acquire(
    driver: str,
    resource: str,
    settings: tuple[object, ...],
    opener: Callable[[], tuple[Any, int]],
    closer: Callable[[Any, int], None],
) -> Session:
    if not resource:
        raise IoConfigError(f"{driver} requires resource = serial number")
    with _lock:
        existing = _sessions.get((driver, resource))
        if existing is not None:
            if existing.settings != settings:
                raise IoConfigError(f"conflicting device-wide settings for {driver} {resource}")
            existing.refs += 1
            return existing
        api, handle = opener()
        session = Session(api, handle, settings, lambda: closer(api, handle))
        _sessions[driver, resource] = session
        return session


def release(session: Session) -> None:
    with _lock, session.lock:
        session.refs -= 1
        if session.refs:
            return
        for key, value in list(_sessions.items()):
            if value is session:
                del _sessions[key]
        session.closer()


class UsbBackend:
    """One reference to a shared physical adapter; transactions use its lock."""

    _session: Session
    _closed = False

    def session(self) -> Session:
        if self._closed:
            raise IoConnectionError("adapter is closed")
        return self._session

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            release(self._session)
