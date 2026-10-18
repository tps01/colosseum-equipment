"""NovAtel OEM7 / PwrPak7 / SMART7 GNSS (NMEA + BESTPOSB).

Manual: OEM7 Commands and Logs Reference Manual (docs.novatel.com).
"""

from __future__ import annotations

import math
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from colosseum_equipment._paths import resolve_artifact_path
from colosseum_equipment.evidence import record_artifact
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

_DEFAULT_LOGS = (
    ("BESTPOSB", 1.0),
    ("GPGGA", 1.0),
    ("GPRMC", 1.0),
    ("GPGSV", 1.0),
)


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
        self._enabled_logs: dict[str, float] = {name: rate for name, rate in _DEFAULT_LOGS}
        self._enable_logs()

    def _wire_suffix(self) -> str:
        return ".gps"

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
        for name, rate_hz in self._enabled_logs.items():
            period = max(1, int(round(1.0 / rate_hz))) if rate_hz > 0 else 1
            self._write_bytes(f"LOG {name} ONTIME {period}\n".encode("ascii"))

    def _drain_reads(self, *, settle_s: float = 0.05) -> None:
        deadline = time.monotonic() + settle_s
        while time.monotonic() < deadline:
            chunk = self._read_bytes(512)
            if not chunk:
                time.sleep(0.01)
                continue
            self._apply_events(self._parser.feed(chunk))

    def load_config(self, path: str) -> None:
        resolved = Path(path)
        if not resolved.is_file():
            alt = resolve_artifact_path(path)
            resolved = alt if alt.is_file() else resolved
        if not resolved.is_file():
            raise FileNotFoundError(f"GNSS config not found: {path}")
        for raw_line in resolved.read_text(encoding="utf-8").splitlines():
            line = raw_line.split("#", 1)[0].strip()
            if not line:
                continue
            cmd = line if line.endswith("\n") else f"{line}\n"
            self._write_bytes(cmd.encode("ascii"))
            self._drain_reads(settle_s=0.05)

    def save_config(self, path: str) -> Path:
        out_path = resolve_artifact_path(path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        for once in ("LOG VERSIONA ONCE\n", "LOG RXSTATUSA ONCE\n"):
            self._write_bytes(once.encode("ascii"))
            self._drain_reads(settle_s=0.1)
        lines = [
            "# Colosseum NovAtel OEM7 config snapshot (logging setup)",
            "# Re-apply with gnss.load_config",
        ]
        for name, rate_hz in self._enabled_logs.items():
            if rate_hz <= 0:
                lines.append(f"UNLOG {name}")
            else:
                period = max(1, int(round(1.0 / rate_hz)))
                lines.append(f"LOG {name} ONTIME {period}")
        for name, rate_hz in self._session_message_rates.items():
            if name.upper() in self._enabled_logs:
                continue
            if rate_hz <= 0:
                lines.append(f"UNLOG {name}")
            else:
                period = max(1, int(round(1.0 / rate_hz)))
                lines.append(f"LOG {name} ONTIME {period}")
        out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        record_artifact(
            domain="equipment",
            command="save_config",
            key=f"gnss{self._gnss_id}.config",
            path=out_path,
            value={"model": self._model, "logs": dict(self._enabled_logs)},
        )
        return out_path

    def set_message_rate(self, message: str, rate_hz: float) -> None:
        name = message.strip().upper()
        if rate_hz < 0:
            raise ValueError("rate_hz must be >= 0")
        if rate_hz == 0:
            self._write_bytes(f"UNLOG {name}\n".encode("ascii"))
            self._enabled_logs[name] = 0.0
        else:
            period = max(1, int(math.ceil(1.0 / rate_hz)))
            self._write_bytes(f"LOG {name} ONTIME {period}\n".encode("ascii"))
            self._enabled_logs[name] = float(rate_hz)
        self._session_message_rates[name] = float(rate_hz)

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
                now = time.monotonic()
                with self._state_lock:
                    self._fix = fix
                    self._fix_recv_mono = now
                    if getattr(best, "lat_stdev_m", None) is not None:
                        self._h_acc_m = float(best.lat_stdev_m)  # type: ignore[attr-defined]
                    if getattr(best, "hgt_stdev_m", None) is not None:
                        self._v_acc_m = float(best.hgt_stdev_m)  # type: ignore[attr-defined]
                if fix.fix_quality > 0:
                    self._note_first_fix()

    def _on_listener_chunk(self, data: bytes) -> None:
        if data:
            self._write_wire(data)
            self._note_bytes()
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
                self._note_bytes()
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
