"""Septentrio AsteRx / mosaic GNSS (NMEA + SBF PVTGeodetic).

Manuals / reading list:
- AsteRx-U3 User Manual (COM / Ethernet NMEA+SBF streams)
- Septentrio Reference Guide / pysbf2 (ASCII enable commands, SBF layout)
"""

from __future__ import annotations

import math
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from colosseum.logging import get_logger

from colosseum_equipment._paths import resolve_artifact_path
from colosseum_equipment.evidence import record_artifact
from colosseum_equipment.exceptions import EquipmentTimeoutError
from colosseum_equipment.instruments.gnss.generic import GenericGnss
from colosseum_equipment.instruments.gnss.nmea import NmeaFix
from colosseum_equipment.instruments.gnss.sbf import (
    BLOCK_PVT_GEODETIC,
    PvtGeodetic,
    SbfStreamParser,
    parse_pvt_geodetic,
)
from colosseum_equipment.instruments.registry import instrument_model

if TYPE_CHECKING:
    from colosseum_equipment.transports.base import Transport

_logger = get_logger("colosseum.equipment")


@instrument_model(
    "gnss",
    "septentrio-asterx-u3",
    "septentrio-asterx-m3",
    "septentrio-mosaic-x5",
    "septentrio-mosaic-h",
)
class SeptentrioGnss(GenericGnss):
    """Shared Septentrio driver; RxTools ASCII + SBF PVTGeodetic."""

    def __init__(self, transport: Transport, config: dict[str, Any]) -> None:
        super().__init__(transport, config)
        self._parser = SbfStreamParser()
        self._pvt: PvtGeodetic | None = None
        self._connection = str(config.get("connection") or "COM1").strip() or "COM1"
        self._nmea_msgs = "GGA+RMC+GSV"
        self._sbf_msgs = "PVTGeodetic"
        self._nmea_period_s = 1
        self._sbf_period_s = 1
        self._enable_streams()

    def _wire_suffix(self) -> str:
        return ".sbf"

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

    def _enable_streams(self) -> None:
        conn = self._connection
        commands = (
            f"setNMEAOutput,Stream1,{conn},{self._nmea_msgs},sec{self._nmea_period_s}\n",
            f"setSBFOutput,Stream2,{conn},{self._sbf_msgs},sec{self._sbf_period_s}\n",
        )
        for command in commands:
            self._write_bytes(command.encode("ascii"))
            self._drain_command_reply(command.strip())

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
            self._drain_command_reply(cmd.strip())

    def save_config(self, path: str) -> Path:
        out_path = resolve_artifact_path(path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        conn = self._connection
        lines = [
            "# Colosseum Septentrio stream snapshot",
            f"setNMEAOutput,Stream1,{conn},{self._nmea_msgs},sec{self._nmea_period_s}",
            f"setSBFOutput,Stream2,{conn},{self._sbf_msgs},sec{self._sbf_period_s}",
        ]
        for name, rate_hz in self._session_message_rates.items():
            period = 0 if rate_hz <= 0 else max(1, int(math.ceil(1.0 / rate_hz)))
            upper = name.upper()
            if upper in {"GGA", "RMC", "GSV", "GSA", "VTG"} or upper.startswith("NMEA"):
                lines.append(
                    f"# session NMEA rate {name} -> sec{period}",
                )
            else:
                lines.append(
                    f"setSBFOutput,Stream2,{conn},{name},sec{period}",
                )
        out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        record_artifact(
            domain="equipment",
            command="save_config",
            key=f"gnss{self._gnss_id}.config",
            path=out_path,
            value={"model": self._model, "connection": conn},
        )
        return out_path

    def set_message_rate(self, message: str, rate_hz: float) -> None:
        if rate_hz < 0:
            raise ValueError("rate_hz must be >= 0")
        name = message.strip()
        period = 0 if rate_hz == 0 else max(1, int(math.ceil(1.0 / rate_hz)))
        conn = self._connection
        upper = name.upper().replace("_", "-")
        nmea_names = {"GGA", "RMC", "GSV", "GSA", "VTG", "NMEA-GGA", "NMEA-RMC", "NMEA-GSV"}
        if upper in nmea_names or upper.startswith("NMEA"):
            token = upper.split("-")[-1] if "-" in upper else upper
            # Merge into NMEA stream list
            parts = [p for p in self._nmea_msgs.split("+") if p]
            if period == 0:
                parts = [p for p in parts if p.upper() != token]
            elif token not in {p.upper() for p in parts}:
                parts.append(token)
            self._nmea_msgs = "+".join(parts) if parts else "GGA"
            self._nmea_period_s = period if period > 0 else self._nmea_period_s
            cmd = (
                f"setNMEAOutput,Stream1,{conn},{self._nmea_msgs},"
                f"sec{self._nmea_period_s}\n"
            )
        else:
            self._sbf_msgs = name if period > 0 else self._sbf_msgs
            self._sbf_period_s = period if period > 0 else self._sbf_period_s
            cmd = (
                f"setSBFOutput,Stream2,{conn},{self._sbf_msgs},"
                f"sec{self._sbf_period_s}\n"
            )
        self._write_bytes(cmd.encode("ascii"))
        self._drain_command_reply(cmd.strip())
        self._session_message_rates[name.upper()] = float(rate_hz)

    def _drain_command_reply(self, command: str) -> None:
        try:
            chunk = self._read_bytes(256)
        except Exception:
            return
        if not chunk:
            return
        for kind, payload in self._parser.feed(chunk):
            if kind != "nmea" or not isinstance(payload, str):
                continue
            if payload.startswith("$R:"):
                return
            if payload.startswith("$R?"):
                _logger.warning(
                    "gnss model `%s` command rejected (%s): %s",
                    self._model,
                    command,
                    payload,
                )
                return

    def _apply_events(self, events: list[tuple[str, object]]) -> None:
        for kind, payload in events:
            if kind == "nmea" and isinstance(payload, str):
                if payload.startswith("$R"):
                    continue
                self._log_raw_line(payload)
                # Prefer SBF for track; NMEA still updates GSV/HDOP/fallback fix.
                record_track = self._pvt is None or self._pvt.fix_quality == 0
                self._ingest_nmea_line(
                    payload,
                    record_raw=False,
                    record_track=record_track,
                )
                if self._fix is not None and self._pvt is not None and self._pvt.fix_quality > 0:
                    # Keep SBF position with latest NMEA HDOP when GGA arrives.
                    fix = self._fix
                    gga_hdop = fix.hdop
                    now = time.monotonic()
                    with self._state_lock:
                        self._fix = NmeaFix(
                            latitude=self._pvt.latitude,
                            longitude=self._pvt.longitude,
                            altitude_m=self._pvt.altitude_m,
                            fix_quality=self._pvt.fix_quality,
                            satellites=self._pvt.satellites,
                            hdop=gga_hdop,
                            utc_time=self._pvt.utc_time or fix.utc_time,
                        )
                        self._fix_recv_mono = now
                    self._note_first_fix()
            elif kind == "sbf" and isinstance(payload, tuple) and len(payload) == 2:
                block_number, body = payload
                if not isinstance(body, bytes):
                    continue
                self._log_raw_line(f"#SBF {block_number} {body.hex()}")
                if block_number != BLOCK_PVT_GEODETIC:
                    continue
                pvt = parse_pvt_geodetic(body)
                if pvt is None or pvt.fix_quality == 0:
                    continue
                self._pvt = pvt
                hdop = self._fix.hdop if self._fix is not None else 0.0
                fix = NmeaFix(
                    latitude=pvt.latitude,
                    longitude=pvt.longitude,
                    altitude_m=pvt.altitude_m,
                    fix_quality=pvt.fix_quality,
                    satellites=pvt.satellites,
                    hdop=hdop,
                    utc_time=pvt.utc_time,
                )
                now = time.monotonic()
                with self._state_lock:
                    self._fix = fix
                    self._fix_recv_mono = now
                    if pvt.utc_time:
                        self._utc_iso = pvt.utc_time
                self._note_first_fix()

    def _on_listener_chunk(self, data: bytes) -> None:
        if data:
            self._write_wire(data)
            self._note_bytes()
        self._apply_events(self._parser.feed(data))

    def _has_fix(self) -> bool:
        if self._pvt is not None and self._pvt.fix_quality > 0:
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
        command = "exeResetReceiver,Cold,none\n"
        self._write_bytes(command.encode("ascii"))
        self._drain_command_reply(command.strip())
        self._pvt = None
        self._clear_nav_state()
