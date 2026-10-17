"""Background GNSS byte-stream listener for logging and shared fix state."""

from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable


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

    def start(self) -> None:
        self._stop.clear()
        self._thread.start()

    def stop(self, timeout_s: float = 2.0) -> None:
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join(timeout=timeout_s)

    def is_alive(self) -> bool:
        return self._thread.is_alive()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                chunk = self._read_bytes(512)
            except Exception:
                time.sleep(0.02)
                continue
            if chunk:
                try:
                    self._on_chunk(chunk)
                except Exception:
                    time.sleep(0.02)
            else:
                time.sleep(0.02)
