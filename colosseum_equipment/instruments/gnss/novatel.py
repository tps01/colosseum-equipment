"""NovAtel OEM7 / PwrPak7 / SMART7 GNSS (NMEA + BESTPOSB + field/sat logs).

Manual: OEM7 Commands and Logs Reference Manual (docs.novatel.com).
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from colosseum.logging import get_logger

from colosseum_equipment._paths import resolve_artifact_path
from colosseum_equipment.evidence import record_artifact
from colosseum_equipment.exceptions import EquipmentTimeoutError
from colosseum_equipment.instruments.gnss.generic import GenericGnss
from colosseum_equipment.instruments.gnss.messages import (
    LOGICAL_CLOCK,
    LOGICAL_DOP,
    LOGICAL_POSECEF,
    LOGICAL_PVT,
    LOGICAL_RAWX,
    LOGICAL_SAT,
    LOGICAL_STATUS,
    LOGICAL_TIME,
    MESSAGE_PROFILES,
    expand_profile_specs,
)
from colosseum_equipment.instruments.gnss.nmea import NmeaDop, NmeaFix
from colosseum_equipment.instruments.gnss.oem7 import (
    MSG_BESTPOS,
    MSG_BESTXYZ,
    MSG_CLOCKMODEL,
    MSG_PSRDOP,
    MSG_RANGE,
    MSG_RXSTATUS,
    MSG_SATVIS2,
    MSG_TIME,
    MSG_TRACKSTAT,
    Oem7StreamParser,
    bestpos_fields,
    parse_bestpos,
    parse_bestxyz,
    parse_clockmodel,
    parse_psrdop,
    parse_range,
    parse_rxstatus,
    parse_satvis2,
    parse_time,
    parse_trackstat,
)
from colosseum_equipment.instruments.registry import instrument_model

if TYPE_CHECKING:
    from colosseum_equipment.transports.base import Transport

_logger = get_logger("colosseum.equipment")

_CMD_TERMINATOR = b"\r\n"
_ACK_WAIT_S = 0.25

# Record-only OEM7 arms: msg-id → (parse, logical_id, vendor_name).
_OEM7_RECORD_ARMS: dict[int, tuple[Callable[[bytes], dict[str, Any] | None], str, str]] = {
    MSG_BESTXYZ: (parse_bestxyz, LOGICAL_POSECEF, "BESTXYZB"),
    MSG_TIME: (parse_time, LOGICAL_TIME, "TIMEB"),
    MSG_CLOCKMODEL: (parse_clockmodel, LOGICAL_CLOCK, "CLOCKMODELB"),
    MSG_RXSTATUS: (parse_rxstatus, LOGICAL_STATUS, "RXSTATUSB"),
    MSG_SATVIS2: (parse_satvis2, LOGICAL_SAT, "SATVIS2B"),
    MSG_TRACKSTAT: (parse_trackstat, LOGICAL_SAT, "TRACKSTATB"),
    MSG_RANGE: (parse_range, LOGICAL_RAWX, "RANGEB"),
}


def _period_s(rate_hz: float) -> float:
    """Convert rate_hz to an OEM7 ONTIME period (allows fractional seconds)."""
    if rate_hz <= 0:
        return 0.0
    period = 1.0 / rate_hz
    # OEM7 accepts fractional periods; keep a sane floor for very high rates.
    return max(0.01, period)


@instrument_model(
    "gnss",
    "novatel-oem7",
    "novatel",
    "novatel-oem7600",
    "novatel-pwrpak7",
    "novatel-smart7",
)
class NovatelGnss(GenericGnss):
    """Shared NovAtel OEM7 driver; ASCII LOG + BESTPOSB + evidence epochs."""

    def __init__(self, transport: Transport, config: dict[str, Any]) -> None:
        super().__init__(transport, config)
        self._parser = Oem7StreamParser()
        self._best: object | None = None
        # name -> (rate_hz, trigger)
        self._enabled_logs: dict[str, tuple[float, str]] = {}
        self._apply_message_profile("default")

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

    def _send_command(self, command: str, *, wait_ack: bool = True) -> None:
        text = command.strip()
        if not text:
            return
        self._write_bytes(text.encode("ascii") + _CMD_TERMINATOR)
        if wait_ack:
            self._drain_command_ack(text)

    def _drain_command_ack(self, command: str) -> None:
        deadline = time.monotonic() + _ACK_WAIT_S
        empty_streak = 0
        while time.monotonic() < deadline:
            chunk = self._read_bytes(512)
            if not chunk:
                empty_streak += 1
                # Bail quickly when the port is quiet (unit tests / no ACK).
                if empty_streak >= 3:
                    return
                time.sleep(0.01)
                continue
            empty_streak = 0
            for kind, payload in self._parser.feed(chunk):
                if kind == "ack" and isinstance(payload, str):
                    upper = payload.upper()
                    if "ERROR" in upper or upper.startswith("<ERROR"):
                        _logger.warning(
                            "gnss model `%s` command rejected (%s): %s",
                            self._model,
                            command,
                            payload,
                        )
                        return
                    if "OK" in upper or upper.startswith("<OK"):
                        return
                elif kind in {"nmea", "ascii", "oem7"}:
                    # Stream data interleaved with ACK; apply nav events.
                    self._apply_events([(kind, payload)])
        # No ACK within window — common on busy ports; continue best-effort.

    def _log_command(self, name: str, rate_hz: float, trigger: str) -> str:
        if rate_hz <= 0:
            return f"UNLOG {name}"
        trig = trigger.strip().lower()
        if trig == "onchanged":
            return f"LOG {name} ONCHANGED"
        period = _period_s(rate_hz)
        # Prefer integer wording when exact.
        if abs(period - round(period)) < 1e-9:
            return f"LOG {name} ONTIME {int(round(period))}"
        return f"LOG {name} ONTIME {period:g}"

    def _enable_logs(self, *, reset: bool = False) -> None:
        if reset:
            self._send_command("UNLOGALL THISPORT")
        for name, (rate_hz, trigger) in list(self._enabled_logs.items()):
            self._send_command(self._log_command(name, rate_hz, trigger))

    def _apply_message_profile(self, profile: str) -> None:
        name = profile.strip().lower()
        if name not in MESSAGE_PROFILES:
            raise ValueError(
                f"unknown message profile {profile!r}; expected one of {MESSAGE_PROFILES}",
            )
        self._message_profile = name
        specs = expand_profile_specs(name, vendor="novatel")
        managed = {spec.name.upper(): (float(spec.rate_hz), spec.trigger) for spec in specs}
        # Replace managed set (UNLOG removed ones on next enable with reset).
        self._enabled_logs = managed
        for msg, (rate_hz, _trig) in managed.items():
            self._session_message_rates[msg] = rate_hz
        self._enable_logs(reset=True)

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
            self._send_command(line)

    def save_config(self, path: str) -> Path:
        out_path = resolve_artifact_path(path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        self._send_command("LOG VERSIONA ONCE")
        self._send_command("LOG RXSTATUSA ONCE")
        lines = [
            "# Colosseum NovAtel OEM7 config snapshot (logging setup)",
            "# Re-apply with gnss.load_config",
        ]
        for name, (rate_hz, trigger) in self._enabled_logs.items():
            lines.append(self._log_command(name, rate_hz, trigger))
        for name, rate_hz in self._session_message_rates.items():
            if name.upper() in self._enabled_logs:
                continue
            lines.append(self._log_command(name.upper(), rate_hz, "ontime"))
        out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        record_artifact(
            domain="equipment",
            command="save_config",
            key=f"gnss{self._gnss_id}.config",
            path=out_path,
            value={
                "model": self._model,
                "logs": {k: v[0] for k, v in self._enabled_logs.items()},
            },
        )
        return out_path

    def set_message_rate(self, message: str, rate_hz: float) -> None:
        name = message.strip().upper()
        if rate_hz < 0:
            raise ValueError("rate_hz must be >= 0")
        trigger = "ontime"
        existing = self._enabled_logs.get(name)
        if existing is not None:
            trigger = existing[1]
        self._send_command(self._log_command(name, rate_hz, trigger))
        if rate_hz == 0:
            self._enabled_logs[name] = (0.0, trigger)
        else:
            self._enabled_logs[name] = (float(rate_hz), trigger)
        self._session_message_rates[name] = float(rate_hz)

    def _apply_events(self, events: list[tuple[str, object]]) -> None:
        for kind, payload in events:
            if kind == "nmea" and isinstance(payload, str):
                self._log_raw_line(payload)
                record_track = self._best is None
                self._ingest_nmea_line(payload, record_raw=False, record_track=record_track)
            elif kind in {"ascii", "ack"} and isinstance(payload, str):
                self._log_raw_line(payload)
            elif kind == "oem7" and isinstance(payload, tuple) and len(payload) == 2:
                msg_id, body = payload
                if not isinstance(body, bytes):
                    continue
                self._log_raw_line(f"#OEM7 {msg_id} {body.hex()}")
                self._handle_oem7(msg_id, body)

    def _handle_oem7_bestpos(self, body: bytes) -> None:
        best = parse_bestpos(body)
        if best is None:
            return
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
            if best.fix_quality > 0:
                self._fix = fix
                self._fix_recv_mono = now
            if best.lat_stdev_m is not None and best.lon_stdev_m is not None:
                self._h_acc_m = math.sqrt(best.lat_stdev_m**2 + best.lon_stdev_m**2)
            if best.hgt_stdev_m is not None:
                self._v_acc_m = float(best.hgt_stdev_m)
        if best.fix_quality > 0:
            self._note_first_fix()
        self._record_message_epoch(
            logical_id=LOGICAL_PVT,
            vendor_message="BESTPOSB",
            fields=bestpos_fields(best),
        )

    def _handle_oem7_psrdop(self, body: bytes) -> None:
        fields = parse_psrdop(body)
        if fields is None:
            return
        now = time.monotonic()
        with self._state_lock:
            self._dop = NmeaDop(
                fix_type="3d" if float(fields.get("pdop", 0)) > 0 else "none",
                pdop=float(fields.get("pdop", 0)),
                hdop=float(fields.get("hdop", 0)),
                vdop=float(fields.get("vdop", 0)),
                prns=(),
            )
            self._dop_recv_mono = now
            self._gdop = float(fields.get("gdop", 0))
        self._record_message_epoch(
            logical_id=LOGICAL_DOP,
            vendor_message="PSRDOPB",
            fields=fields,
        )

    def _handle_oem7(self, msg_id: int, body: bytes) -> None:
        if msg_id == MSG_BESTPOS:
            self._handle_oem7_bestpos(body)
            return
        if msg_id == MSG_PSRDOP:
            self._handle_oem7_psrdop(body)
            return
        arm = _OEM7_RECORD_ARMS.get(msg_id)
        if arm is None:
            return
        parse, logical_id, vendor_name = arm
        fields = parse(body)
        if fields is not None:
            self._record_message_epoch(
                logical_id=logical_id,
                vendor_message=vendor_name,
                fields=fields,
            )

    def _on_listener_chunk(self, data: bytes) -> None:
        if data:
            self._write_wire(data)
            self._note_bytes()
        self._apply_events(self._parser.feed(data))

    def _has_fix(self) -> bool:
        if self._best is not None and getattr(self._best, "fix_quality", 0) > 0:
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
        self._send_command("FRESET COLDSTART")
        self._best = None
        self._clear_nav_state()
