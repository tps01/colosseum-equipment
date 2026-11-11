"""Background GNSS byte-stream listener for logging and shared fix state."""

from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING

from colosseum.logging import get_logger

from colosseum_equipment.exceptions import EquipmentTimeoutError

if TYPE_CHECKING:
    from collections.abc import Callable

_logger = get_logger("colosseum.equipment")


class GnssListener:
    """Daemon thread that owns transport reads while logging is active."""

    def __init__(
        self,
        read_bytes: Callable[[int], bytes],
        on_chunk: Callable[[bytes], None],
    ) -> None:
        self._read_bytes = read_bytes
        self._on_chunk = on_chunk
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._run,
            name="gnss-listener",
            daemon=True,
        )
        self._error_streak = 0

    def start(self) -> None:
        self._stop.clear()
        self._error_streak = 0
        self._thread.start()

    def stop(self, timeout_s: float = 2.0) -> None:
        """Stop reading; report a timeout rather than claiming the worker finished."""
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join(timeout=timeout_s)
            if self._thread.is_alive():
                raise EquipmentTimeoutError("gnss listener did not stop within the shutdown timeout")

    def is_alive(self) -> bool:
        return self._thread.is_alive()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                chunk = self._read_bytes(512)
            except EquipmentTimeoutError:
                time.sleep(0.02)
                continue
            except Exception as exc:
                self._error_streak += 1
                if self._error_streak == 1 or self._error_streak % 50 == 0:
                    _logger.warning("gnss listener read failed: %s", exc)
                time.sleep(0.02)
                continue
            self._error_streak = 0
            if chunk:
                try:
                    self._on_chunk(chunk)
                except Exception as exc:
                    _logger.warning("gnss listener chunk handling failed: %s", exc)
                    time.sleep(0.02)
            else:
                time.sleep(0.02)
