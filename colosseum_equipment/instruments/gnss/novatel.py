"""NovAtel OEM7 / PwrPak7 / SMART7 GNSS (NMEA + BESTPOSB).

Manual: OEM7 Commands and Logs Reference Manual (docs.novatel.com).
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from colosseum_equipment.exceptions import EquipmentTimeoutError
from colosseum_equipment.instruments.gnss.generic import GenericGnss
from colosseum_equipment.instruments.gnss.nmea import NmeaFix
from colosseum_equipment.instruments.gnss.oem7 import (
    MSG_BESTPOS,
    Oem7StreamParser,
    parse_bestpos,
)
from colosseum_equipment.instruments.registry import instrument_model

if TYPE_CHECKING:
    from colosseum_equipment.transports.base import Transport


@instrument_model(
    "gnss",
    "novatel-oem7",
    "novatel-oem7600",
    "novatel-pwrpak7",
    "novatel-smart7",
)
class NovatelGnss(GenericGnss):
    """Shared NovAtel OEM7 driver; ASCII LOG + BESTPOSB."""

    def __init__(self, transport: Transport, config: dict[str, Any]) -> None:
        super().__init__(transport, config)
        self._parser = Oem7StreamParser()
        self._best: object | None = None
        self._enable_logs()

    def _write_bytes(self, payload: bytes) -> None:
        write_bytes = getattr(self._transport, "write_bytes", None)
        if callable(write_bytes):
            write_bytes(payload)
            return
        write_raw = getattr(self._transport, "write_raw", None)
        if callable(write_raw):
            write_raw(payload)
            return
        self._transport.write(payload.decode("latin-1"))

    def _enable_logs(self) -> None:
        for command in (
            "LOG BESTPOSB ONTIME 1\n",
            "LOG GPGGA ONTIME 1\n",
            "LOG GPRMC ONTIME 1\n",
            "LOG GPGSV ONTIME 1\n",
        ):
            self._write_bytes(command.encode("ascii"))

    def _apply_events(self, events: list[tuple[str, object]]) -> None:
        for kind, payload in events:
            if kind == "nmea" and isinstance(payload, str):
                self._log_raw_line(payload)
                record_track = self._best is None
                self._ingest_nmea_line(payload, record_raw=False, record_track=record_track)
            elif kind == "ascii" and isinstance(payload, str):
                self._log_raw_line(payload)
            elif kind == "oem7" and isinstance(payload, tuple) and len(payload) == 2:
                msg_id, body = payload
                if not isinstance(body, bytes):
                    continue
                self._log_raw_line(f"#OEM7 {msg_id} {body.hex()}")
                if msg_id != MSG_BESTPOS:
                    continue
                best = parse_bestpos(body)
                if best is None or best.fix_quality == 0:
                    continue
                self._best = best
                hdop = self._fix.hdop if self._fix is not None else 0.0
                fix = NmeaFix(
                    latitude=best.latitude,
                    longitude=best.longitude,
                    altitude_m=best.altitude_m,
                    fix_quality=best.fix_quality,
                    satellites=best.satellites,
                    hdop=hdop,
                    utc_time=self._utc_iso,
                )
                with self._state_lock:
                    self._fix = fix
                    self._append_track_sample(fix)

    def _on_listener_chunk(self, data: bytes) -> None:
        self._apply_events(self._parser.feed(data))

    def _has_fix(self) -> bool:
        if self._best is not None:
            return True
        return self._fix is not None and self._fix.fix_quality > 0

    def _poll_transport(self, timeout_s: float) -> NmeaFix:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            chunk = self._read_bytes(512)
            if chunk:
                self._apply_events(self._parser.feed(chunk))
            if self._has_fix() and self._fix is not None:
                return self._fix
        raise EquipmentTimeoutError(
            f"gnss model `{self._model}` did not report a fix within {timeout_s}s",
        )

    def cold_start(self) -> None:
        self._write_bytes(b"FRESET COLDSTART\n")
        self._best = None
        self._clear_nav_state()
