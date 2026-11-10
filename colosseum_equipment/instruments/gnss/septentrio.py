"""Septentrio AsteRx / mosaic GNSS (NMEA + SBF PVT + field/sat blocks).

Manuals / reading list:
- AsteRx-U3 User Manual (COM / Ethernet NMEA+SBF streams)
- Septentrio Reference Guide / pysbf2 (ASCII enable commands, SBF layout)
"""

from __future__ import annotations

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
    LOGICAL_MEASX,
    LOGICAL_POSECEF,
    LOGICAL_PVT,
    LOGICAL_SAT,
    LOGICAL_STATUS,
    LOGICAL_TIME,
    MESSAGE_PROFILES,
    expand_profile_specs,
)
from colosseum_equipment.instruments.gnss.nmea import NmeaDop, NmeaFix
from colosseum_equipment.instruments.gnss.sbf import (
    BLOCK_CHANNEL_STATUS,
    BLOCK_DOP,
    BLOCK_MEAS_EPOCH,
    BLOCK_PVT_CARTESIAN,
    BLOCK_PVT_GEODETIC,
    BLOCK_RECEIVER_STATUS,
    BLOCK_RECEIVER_TIME,
    BLOCK_SAT_VISIBILITY,
    PvtGeodetic,
    SbfStreamParser,
    parse_channel_status,
    parse_dop,
    parse_meas_epoch,
    parse_pvt_cartesian,
    parse_pvt_geodetic,
    parse_receiver_status,
    parse_receiver_time,
    parse_sat_visibility,
    pvt_geodetic_fields,
)
from colosseum_equipment.instruments.registry import instrument_model

if TYPE_CHECKING:
    from colosseum_equipment.transports.base import Transport

_logger = get_logger("colosseum.equipment")

_NMEA_TOKENS = frozenset({"GGA", "RMC", "GSV", "GSA", "VTG"})
_REPLY_WAIT_S = 0.5

# Record-only SBF arms: block → (parse, logical_id, vendor_name).
_SBF_RECORD_ARMS: dict[int, tuple[Callable[[bytes], dict[str, Any] | None], str, str]] = {
    BLOCK_PVT_CARTESIAN: (parse_pvt_cartesian, LOGICAL_POSECEF, "PVTCartesian"),
    BLOCK_RECEIVER_TIME: (parse_receiver_time, LOGICAL_TIME, "ReceiverTime"),
    BLOCK_RECEIVER_STATUS: (parse_receiver_status, LOGICAL_STATUS, "ReceiverStatus"),
    BLOCK_SAT_VISIBILITY: (parse_sat_visibility, LOGICAL_SAT, "SatVisibility"),
    BLOCK_CHANNEL_STATUS: (parse_channel_status, LOGICAL_SAT, "ChannelStatus"),
    BLOCK_MEAS_EPOCH: (parse_meas_epoch, LOGICAL_MEASX, "MeasEpoch"),
}


def _interval_token(rate_hz: float) -> str:
    """Map rate_hz to a Septentrio discrete interval token."""
    if rate_hz <= 0:
        return "off"
    period_s = 1.0 / rate_hz
    # Prefer documented discrete tokens.
    candidates: list[tuple[float, str]] = [
        (0.1, "msec100"),
        (0.2, "msec200"),
        (0.5, "msec500"),
        (1.0, "sec1"),
        (2.0, "sec2"),
        (5.0, "sec5"),
        (10.0, "sec10"),
        (30.0, "sec30"),
        (60.0, "sec60"),
    ]
    best = min(candidates, key=lambda item: abs(item[0] - period_s))
    # If far from any discrete token, fall back to nearest whole second.
    if abs(best[0] - period_s) > 0.25 and period_s >= 1.0:
        return f"sec{max(1, int(round(period_s)))}"
    return best[1]


@instrument_model(
    "gnss",
    "septentrio-asterx-u3",
    "septentrio",
    "septentrio-asterx-m3",
    "septentrio-mosaic-x5",
    "septentrio-mosaic-h",
)
class SeptentrioGnss(GenericGnss):
    """Shared Septentrio driver; RxTools ASCII + SBF evidence epochs."""

    def __init__(self, transport: Transport, config: dict[str, Any]) -> None:
        super().__init__(transport, config)
        self._parser = SbfStreamParser()
        self._pvt: PvtGeodetic | None = None
        raw_conn = config.get("connection")
        if raw_conn is None or not str(raw_conn).strip():
            self._connection = "COM1"
            _logger.warning(
                "gnss model `%s` config missing `connection`; defaulting to COM1. "
                "Set connection to the receiver port that matches the open transport "
                "(e.g. USB1, IPS1) or streams may land on another interface.",
                self._model,
            )
        else:
            self._connection = str(raw_conn).strip()
        self._nmea_msgs = "GGA+RMC+GSV"
        self._sbf_msgs = "PVTGeodetic+DOP"
        self._nmea_rate_hz = 1.0
        self._sbf_rate_hz = 1.0
        self._nmea_enabled: dict[str, float] = {"GGA": 1.0, "RMC": 1.0, "GSV": 1.0}
        self._sbf_enabled: dict[str, float] = {"PVTGeodetic": 1.0, "DOP": 1.0}
        self._apply_message_profile("default")

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

    def _send_command(self, command: str) -> None:
        text = command if command.endswith("\n") else f"{command}\n"
        self._write_bytes(text.encode("ascii"))
        self._drain_command_reply(text.strip())

    def _enable_streams(self) -> None:
        conn = self._connection
        nmea = "+".join(self._nmea_enabled.keys()) if self._nmea_enabled else "none"
        sbf = "+".join(self._sbf_enabled.keys()) if self._sbf_enabled else "none"
        self._nmea_msgs = nmea
        self._sbf_msgs = sbf
        nmea_tok = _interval_token(self._nmea_rate_hz)
        sbf_tok = _interval_token(self._sbf_rate_hz)
        # Protocol permission is separate from stream scheduling.
        self._send_command(f"setDataInOut,{conn},,+NMEA+SBF")
        if self._nmea_enabled:
            self._send_command(f"setNMEAOutput,Stream1,{conn},{nmea},{nmea_tok}")
        else:
            self._send_command(f"setNMEAOutput,Stream1,{conn},none,off")
        if self._sbf_enabled:
            self._send_command(f"setSBFOutput,Stream2,{conn},{sbf},{sbf_tok}")
        else:
            self._send_command(f"setSBFOutput,Stream2,{conn},none,off")

    def _apply_message_profile(self, profile: str) -> None:
        name = profile.strip().lower()
        if name not in MESSAGE_PROFILES:
            raise ValueError(
                f"unknown message profile {profile!r}; expected one of {MESSAGE_PROFILES}",
            )
        self._message_profile = name
        nmea: dict[str, float] = {}
        sbf: dict[str, float] = {}
        nmea_rates: list[float] = []
        sbf_rates: list[float] = []
        for spec in expand_profile_specs(name, vendor="septentrio"):
            upper = spec.name.upper()
            if upper in _NMEA_TOKENS or upper.startswith("NMEA"):
                token = upper.split("-")[-1]
                nmea[token] = float(spec.rate_hz)
                nmea_rates.append(float(spec.rate_hz))
            else:
                sbf[spec.name] = float(spec.rate_hz)
                sbf_rates.append(float(spec.rate_hz))
            self._session_message_rates[upper] = float(spec.rate_hz)
        self._nmea_enabled = nmea
        self._sbf_enabled = sbf
        self._nmea_rate_hz = min(nmea_rates) if nmea_rates else 1.0
        # Shared 1 Hz SBF stream for parity v1 when rates differ slightly.
        self._sbf_rate_hz = min(sbf_rates) if sbf_rates else 1.0
        self._enable_streams()

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
        conn = self._connection
        nmea_tok = _interval_token(self._nmea_rate_hz)
        sbf_tok = _interval_token(self._sbf_rate_hz)
        lines = [
            "# Colosseum Septentrio stream snapshot",
            f"setDataInOut,{conn},,+NMEA+SBF",
            f"setNMEAOutput,Stream1,{conn},{self._nmea_msgs},{nmea_tok}",
            f"setSBFOutput,Stream2,{conn},{self._sbf_msgs},{sbf_tok}",
        ]
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
        upper = name.upper().replace("_", "-")
        if upper in _NMEA_TOKENS or upper.startswith("NMEA"):
            token = upper.split("-")[-1] if "-" in upper else upper
            if rate_hz == 0:
                self._nmea_enabled.pop(token, None)
            else:
                self._nmea_enabled[token] = float(rate_hz)
                self._nmea_rate_hz = float(rate_hz)
        else:
            # Keep SBF block list; remove on disable, merge on enable.
            key = name
            # Prefer canonical casing from current list when present.
            for existing in list(self._sbf_enabled):
                if existing.upper() == name.upper():
                    key = existing
                    break
            if rate_hz == 0:
                self._sbf_enabled.pop(key, None)
            else:
                self._sbf_enabled[key] = float(rate_hz)
                self._sbf_rate_hz = float(rate_hz)
        self._session_message_rates[upper] = float(rate_hz)
        self._enable_streams()

    def _drain_command_reply(self, command: str) -> None:
        deadline = time.monotonic() + _REPLY_WAIT_S
        empty_streak = 0
        while time.monotonic() < deadline:
            try:
                chunk = self._read_bytes(256)
            except Exception:
                return
            if not chunk:
                empty_streak += 1
                if empty_streak >= 3:
                    return
                time.sleep(0.01)
                continue
            empty_streak = 0
            for kind, payload in self._parser.feed(chunk):
                if kind == "nmea" and isinstance(payload, str):
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
                    # Live NMEA interleaved with replies — keep it.
                    self._apply_events([(kind, payload)])
                elif kind == "sbf":
                    self._apply_events([(kind, payload)])

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
                self._handle_sbf(block_number, body)

    def _record_pvt_clock_fields(self, pvt: PvtGeodetic) -> None:
        # Clock fields from PVT when no separate clock block.
        if pvt.clock_bias_ms is None and pvt.clock_drift_ppm is None:
            return
        clock_fields: dict[str, Any] = {}
        if pvt.clock_bias_ms is not None:
            clock_fields["clkBias"] = pvt.clock_bias_ms
        if pvt.clock_drift_ppm is not None:
            clock_fields["clkDrift"] = pvt.clock_drift_ppm
        self._record_message_epoch(
            logical_id=LOGICAL_CLOCK,
            vendor_message="PVTGeodetic",
            fields=clock_fields,
        )

    def _handle_sbf_pvt(self, body: bytes) -> None:
        pvt = parse_pvt_geodetic(body)
        if pvt is None:
            return
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
            if pvt.fix_quality > 0:
                self._fix = fix
                self._fix_recv_mono = now
            if pvt.utc_time:
                self._utc_iso = pvt.utc_time
        if pvt.fix_quality > 0:
            self._note_first_fix()
        self._record_message_epoch(
            logical_id=LOGICAL_PVT,
            vendor_message="PVTGeodetic",
            fields=pvt_geodetic_fields(pvt),
        )
        self._record_pvt_clock_fields(pvt)

    def _handle_sbf_dop(self, body: bytes) -> None:
        fields = parse_dop(body)
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
            vendor_message="DOP",
            fields=fields,
        )

    def _handle_sbf(self, block_number: int, body: bytes) -> None:
        if block_number == BLOCK_PVT_GEODETIC:
            self._handle_sbf_pvt(body)
            return
        if block_number == BLOCK_DOP:
            self._handle_sbf_dop(body)
            return
        arm = _SBF_RECORD_ARMS.get(block_number)
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
        self._send_command("exeResetReceiver,Cold,none")
        self._pvt = None
        self._clear_nav_state()
