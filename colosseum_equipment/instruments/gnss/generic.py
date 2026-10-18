"""Generic GNSS receiver using NMEA 0183 over serial or VISA."""

from __future__ import annotations

import csv
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, BinaryIO, TextIO

from colosseum_equipment._paths import resolve_artifact_path
from colosseum_equipment.evidence import enqueue_measurement, record_artifact
from colosseum_equipment.exceptions import (
    EquipmentCapabilityError,
    EquipmentError,
    EquipmentTimeoutError,
    NoFixError,
    NoStreamError,
    StaleDataError,
)
from colosseum_equipment.instruments._capabilities import unsupported
from colosseum_equipment.instruments.gnss.listener import GnssListener
from colosseum_equipment.instruments.gnss.nmea import (
    NmeaDop,
    NmeaFix,
    NmeaSat,
    NmeaVelocity,
    parse_gga,
    parse_gsa,
    parse_gsv_sats,
    parse_rmc,
    parse_vtg,
)
from colosseum_equipment.instruments.gnss.plots import (
    read_track_csv,
    write_quality_plot,
    write_skyplot,
    write_track_plot,
)
from colosseum_equipment.instruments.registry import instrument_model

if TYPE_CHECKING:
    from colosseum_equipment.transports.base import Transport

_TRACK_FIELDS = (
    "host_ts_iso",
    "receiver_utc_iso",
    "fix_ok",
    "fix_quality",
    "latitude",
    "longitude",
    "altitude_m",
    "sats_used",
    "sats_visible",
    "hdop",
    "pdop",
    "vdop",
    "gdop",
    "speed_m_s",
    "course_deg",
    "h_acc_m",
    "v_acc_m",
    "max_cn0_dbhz",
    "data_age_s",
    "stream_ok",
)

_DEFAULT_MAX_AGE_S = 5.0
_SAT_EXPIRE_S = 10.0
_STREAM_STALE_S = 3.0
_EPOCH_INTERVAL_S = 1.0
_MAX_TRACK_SAMPLES = 3600


def _host_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@instrument_model(
    "gnss",
    "generic",
    address="either",
    extra_optional=("connection", "baudrate", "sim_read"),
)
class GenericGnss:
    """NMEA-only GNSS. Named models that need UBX/SBF override this class."""

    _model = "generic"

    def __init__(self, transport: Transport, config: dict[str, Any]) -> None:
        self._transport = transport
        self._config = config
        self._model = str(config.get("model", "generic")).lower()
        self._gnss_id = int(config.get("gnss_id", config.get("id", 0)) or 0)
        self._fix: NmeaFix | None = None
        self._fix_recv_mono = 0.0
        self._utc_iso = ""
        self._dop: NmeaDop | None = None
        self._dop_recv_mono = 0.0
        self._velocity: NmeaVelocity | None = None
        self._velocity_recv_mono = 0.0
        self._h_acc_m: float | None = None
        self._v_acc_m: float | None = None
        self._gdop: float | None = None
        self._state_lock = threading.Lock()
        self._gsv: dict[tuple[str, int], tuple[NmeaSat, float]] = {}
        self._track_samples: list[dict[str, float | str | bool]] = []
        self._listener: GnssListener | None = None
        self._raw_log: TextIO | None = None
        self._wire_log: BinaryIO | None = None
        self._track_csv: TextIO | None = None
        self._track_writer: csv.DictWriter[str] | None = None
        self._raw_log_path: Path | None = None
        self._wire_log_path: Path | None = None
        self._track_csv_path: Path | None = None
        self._nmea_buf = bytearray()
        self._logging_key = ""
        self._session_message_rates: dict[str, float] = {}
        self._epoch_index = 0
        self._last_byte_mono = 0.0
        self._last_epoch_mono = 0.0
        self._epoch_timer: threading.Thread | None = None
        self._epoch_stop = threading.Event()
        self._acq_start_mono: float | None = None
        self._ttff_s: float | None = None
        self._epochs_total = 0
        self._epochs_nofix = 0
        self._outage_start_mono: float | None = None
        self._longest_outage_s = 0.0
        self._reacquisition_s: float | None = None
        self._had_fix = False

    def _read_line(self) -> str:
        read = getattr(self._transport, "read", None)
        if callable(read):
            return str(read())
        return self._transport.query("")

    def _read_bytes(self, size: int = 256) -> bytes:
        read_bytes = getattr(self._transport, "read_bytes", None)
        if callable(read_bytes):
            return bytes(read_bytes(size))
        read_raw = getattr(self._transport, "read_raw", None)
        if callable(read_raw):
            return bytes(read_raw(size))
        line = self._read_line()
        return (line + "\n").encode("ascii", errors="replace")

    def _logging_active(self) -> bool:
        return self._listener is not None and self._listener.is_alive()

    def _wire_suffix(self) -> str:
        """Binary wire-log suffix for offline tools (override per vendor)."""
        return ".bin"

    def _write_wire(self, data: bytes) -> None:
        if not data or self._wire_log is None:
            return
        self._wire_log.write(data)
        self._wire_log.flush()

    def _clear_nav_state(self) -> None:
        with self._state_lock:
            self._fix = None
            self._fix_recv_mono = 0.0
            self._utc_iso = ""
            self._dop = None
            self._velocity = None
            self._gsv.clear()
            self._h_acc_m = None
            self._v_acc_m = None
            self._gdop = None

    def _note_bytes(self) -> None:
        self._last_byte_mono = time.monotonic()

    def _expire_sats(self, now: float) -> None:
        stale = [key for key, (_, recv) in self._gsv.items() if now - recv > _SAT_EXPIRE_S]
        for key in stale:
            del self._gsv[key]

    def _max_cn0(self) -> float:
        values = [sat.snr for sat, _ in self._gsv.values() if sat.snr > 0]
        return max(values) if values else 0.0

    def _visible_count(self) -> int:
        return len(self._gsv)

    def _build_epoch(self, *, force_nofix: bool = False) -> dict[str, float | str | bool]:
        now = time.monotonic()
        with self._state_lock:
            self._expire_sats(now)
            fix = self._fix
            dop = self._dop
            vel = self._velocity
            age = (now - self._fix_recv_mono) if self._fix_recv_mono else float("inf")
            stream_ok = bool(
                self._last_byte_mono and (now - self._last_byte_mono) <= _STREAM_STALE_S,
            )
            # Continuity requires a fresh, quality fix on a live stream — not a
            # cached quality bit after disconnect / silence.
            fix_fresh = bool(self._fix_recv_mono) and age <= _STREAM_STALE_S
            quality_ok = bool(fix is not None and fix.fix_quality > 0)
            fix_ok = bool(quality_ok and fix_fresh and stream_ok) and not force_nofix
            row: dict[str, float | str | bool] = {
                "host_ts_iso": _host_iso(),
                "receiver_utc_iso": self._utc_iso or (fix.utc_time if fix else ""),
                "fix_ok": fix_ok,
                "fix_quality": float(fix.fix_quality) if fix else 0.0,
                "latitude": float(fix.latitude) if fix and fix_ok else "",
                "longitude": float(fix.longitude) if fix and fix_ok else "",
                "altitude_m": float(fix.altitude_m) if fix and fix_ok else "",
                "sats_used": float(fix.satellites) if fix else 0.0,
                "sats_visible": float(self._visible_count()),
                "hdop": float(dop.hdop if dop is not None else (fix.hdop if fix else 0.0)),
                "pdop": float(dop.pdop if dop is not None else 0.0),
                "vdop": float(dop.vdop if dop is not None else 0.0),
                "gdop": float(self._gdop if self._gdop is not None else 0.0),
                "speed_m_s": float(vel.speed_m_s) if vel is not None else "",
                "course_deg": float(vel.course_deg) if vel is not None else "",
                "h_acc_m": float(self._h_acc_m) if self._h_acc_m is not None else "",
                "v_acc_m": float(self._v_acc_m) if self._v_acc_m is not None else "",
                "max_cn0_dbhz": float(self._max_cn0()),
                "data_age_s": float(age if age != float("inf") else -1.0),
                "stream_ok": stream_ok,
            }
        return row

    def _note_first_fix(self) -> None:
        """Record TTFF when a valid fix arrives (logging not required)."""
        if self._acq_start_mono is None or self._ttff_s is not None:
            return
        with self._state_lock:
            fix = self._fix
            if fix is None or fix.fix_quality <= 0:
                return
        self._ttff_s = time.monotonic() - self._acq_start_mono

    def _update_continuity(self, fix_ok: bool) -> None:
        now = time.monotonic()
        if fix_ok:
            if self._acq_start_mono is not None and self._ttff_s is None:
                self._ttff_s = now - self._acq_start_mono
            if self._outage_start_mono is not None:
                gap = now - self._outage_start_mono
                self._longest_outage_s = max(self._longest_outage_s, gap)
                if self._had_fix and self._reacquisition_s is None:
                    self._reacquisition_s = gap
                self._outage_start_mono = None
            self._had_fix = True
        else:
            if self._outage_start_mono is None and (self._had_fix or self._epochs_total > 0):
                self._outage_start_mono = now

    def _append_epoch(self, row: dict[str, float | str | bool]) -> None:
        fix_ok = bool(row.get("fix_ok"))
        self._update_continuity(fix_ok)
        self._epochs_total += 1
        if not fix_ok:
            self._epochs_nofix += 1
        self._track_samples.append(row)
        if len(self._track_samples) > _MAX_TRACK_SAMPLES:
            self._track_samples = self._track_samples[-_MAX_TRACK_SAMPLES:]
        if self._track_writer is not None and self._track_csv is not None:
            self._track_writer.writerow(row)
            self._track_csv.flush()
        if self._logging_key:
            idx = self._epoch_index
            self._epoch_index += 1
            payload = {
                **row,
                "gnss_id": self._gnss_id,
                "model": self._model,
                "logging_key": self._logging_key,
            }
            enqueue_measurement(
                domain="equipment",
                command="track_epoch",
                key=self._logging_key,
                value=payload,
                row_index=idx,
            )

    def _emit_epoch(self) -> None:
        self._append_epoch(self._build_epoch())

    def _epoch_loop(self) -> None:
        while not self._epoch_stop.wait(_EPOCH_INTERVAL_S):
            self._emit_epoch()

    def _log_raw_line(self, text: str) -> None:
        if self._raw_log is None:
            return
        self._raw_log.write(text if text.endswith("\n") else f"{text}\n")
        self._raw_log.flush()

    def _ingest_nmea_line(
        self,
        line: str,
        *,
        record_raw: bool = True,
        record_track: bool = True,
    ) -> None:
        _ = record_track  # epochs are emitted on a timer while logging
        if record_raw:
            self._log_raw_line(line)
        self._note_bytes()
        now = time.monotonic()
        sats = parse_gsv_sats(line)
        if sats:
            with self._state_lock:
                for sat in sats:
                    self._gsv[(sat.constellation, sat.prn)] = (sat, now)
                self._expire_sats(now)
            return
        dop = parse_gsa(line)
        if dop is not None:
            with self._state_lock:
                self._dop = dop
                self._dop_recv_mono = now
            return
        vel = parse_vtg(line)
        if vel is not None:
            with self._state_lock:
                self._velocity = vel
                self._velocity_recv_mono = now
            return
        utc_iso, rmc_vel, _status = parse_rmc(line)
        if utc_iso is not None or rmc_vel is not None:
            with self._state_lock:
                if utc_iso:
                    self._utc_iso = utc_iso
                if rmc_vel is not None:
                    self._velocity = rmc_vel
                    self._velocity_recv_mono = now
            if utc_iso is not None:
                return
        fix = parse_gga(line)
        if fix is not None:
            with self._state_lock:
                self._fix = fix
                self._fix_recv_mono = now
                if fix.utc_time and not self._utc_iso:
                    self._utc_iso = fix.utc_time
            if fix.fix_quality > 0:
                self._note_first_fix()
            return

    def _ingest_line(self, line: str) -> None:
        self._ingest_nmea_line(line, record_raw=False, record_track=True)

    def _feed_nmea_bytes(self, data: bytes) -> None:
        if data:
            self._write_wire(data)
            self._note_bytes()
        self._nmea_buf.extend(data)
        while True:
            try:
                end = self._nmea_buf.index(0x0A)
            except ValueError:
                break
            raw = bytes(self._nmea_buf[: end + 1])
            del self._nmea_buf[: end + 1]
            line = raw.decode("ascii", errors="replace").strip()
            if line:
                self._ingest_nmea_line(line)

    def _on_listener_chunk(self, data: bytes) -> None:
        self._feed_nmea_bytes(data)

    def _poll_from_state(self, timeout_s: float) -> NmeaFix:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            with self._state_lock:
                if self._fix is not None and self._fix.fix_quality > 0:
                    return self._fix
            time.sleep(0.02)
        raise EquipmentTimeoutError(
            f"gnss model `{self._model}` did not report a fix within {timeout_s}s",
        )

    def _poll_transport(self, timeout_s: float) -> NmeaFix:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            try:
                line = self._read_line()
            except (EquipmentError, TimeoutError, OSError):
                line = ""
            if not line:
                continue
            self._ingest_line(line)
            if self._fix is not None and self._fix.fix_quality > 0:
                return self._fix
        raise EquipmentTimeoutError(
            f"gnss model `{self._model}` did not report a fix within {timeout_s}s",
        )

    def _poll(self, timeout_s: float) -> NmeaFix:
        if self._logging_active():
            return self._poll_from_state(timeout_s)
        return self._poll_transport(timeout_s)

    def wait_for_fix(self, timeout_s: float) -> None:
        self._poll(timeout_s)
        self._note_first_fix()

    def _ensure_stream(self, max_age_s: float) -> None:
        now = time.monotonic()
        if not self._last_byte_mono or (now - self._last_byte_mono) > max(
            max_age_s, _STREAM_STALE_S,
        ):
            if not self._logging_active():
                # Try a quick poll before declaring no stream.
                try:
                    self._poll(min(1.0, max_age_s))
                    return
                except EquipmentTimeoutError as exc:
                    raise NoStreamError(
                        f"gnss model `{self._model}` has no recent data",
                    ) from exc
            raise NoStreamError(f"gnss model `{self._model}` has no recent data")

    def _require_fresh_fix(self, max_age_s: float = _DEFAULT_MAX_AGE_S) -> NmeaFix:
        self._ensure_stream(max_age_s)
        with self._state_lock:
            fix = self._fix
            recv = self._fix_recv_mono
        if fix is None or fix.fix_quality <= 0 or not recv:
            try:
                return self._poll(min(max_age_s, float(self._config.get("timeout", 5.0))))
            except EquipmentTimeoutError as exc:
                raise NoFixError(f"gnss model `{self._model}` has no valid fix") from exc
        age = time.monotonic() - recv
        if age > max_age_s:
            raise StaleDataError(
                f"gnss fix is stale ({age:.2f}s > {max_age_s:.2f}s)",
            )
        return fix

    def measure_latitude(self, max_age_s: float = _DEFAULT_MAX_AGE_S) -> float:
        return self._require_fresh_fix(max_age_s).latitude

    def measure_longitude(self, max_age_s: float = _DEFAULT_MAX_AGE_S) -> float:
        return self._require_fresh_fix(max_age_s).longitude

    def measure_altitude_m(self, max_age_s: float = _DEFAULT_MAX_AGE_S) -> float:
        return self._require_fresh_fix(max_age_s).altitude_m

    def measure_fix_quality(self, max_age_s: float = _DEFAULT_MAX_AGE_S) -> float:
        return float(self._require_fresh_fix(max_age_s).fix_quality)

    def measure_satellites(self, max_age_s: float = _DEFAULT_MAX_AGE_S) -> float:
        return float(self._require_fresh_fix(max_age_s).satellites)

    def measure_hdop(self, max_age_s: float = _DEFAULT_MAX_AGE_S) -> float:
        self._ensure_stream(max_age_s)
        with self._state_lock:
            if self._dop is not None and (time.monotonic() - self._dop_recv_mono) <= max_age_s:
                return self._dop.hdop
        return self._require_fresh_fix(max_age_s).hdop

    def measure_pdop(self, max_age_s: float = _DEFAULT_MAX_AGE_S) -> float:
        self._ensure_stream(max_age_s)
        with self._state_lock:
            if self._dop is None or (time.monotonic() - self._dop_recv_mono) > max_age_s:
                raise StaleDataError("PDOP not available from recent GSA/NAV-DOP")
            return self._dop.pdop

    def measure_vdop(self, max_age_s: float = _DEFAULT_MAX_AGE_S) -> float:
        self._ensure_stream(max_age_s)
        with self._state_lock:
            if self._dop is None or (time.monotonic() - self._dop_recv_mono) > max_age_s:
                raise StaleDataError("VDOP not available from recent GSA/NAV-DOP")
            return self._dop.vdop

    def measure_gdop(self, max_age_s: float = _DEFAULT_MAX_AGE_S) -> float:
        self._ensure_stream(max_age_s)
        with self._state_lock:
            if self._gdop is None:
                raise EquipmentCapabilityError(
                    f"gnss model `{self._model}` does not report GDOP",
                )
            return float(self._gdop)

    def get_fix_type(self, max_age_s: float = _DEFAULT_MAX_AGE_S) -> str:
        self._ensure_stream(max_age_s)
        with self._state_lock:
            if self._dop is not None and (time.monotonic() - self._dop_recv_mono) <= max_age_s:
                return self._dop.fix_type
            if self._fix is not None and self._fix.fix_quality > 0:
                return "3d" if self._fix.fix_quality >= 1 else "none"
        return "none"

    def measure_satellites_visible(self, max_age_s: float = _DEFAULT_MAX_AGE_S) -> float:
        self._ensure_stream(max_age_s)
        with self._state_lock:
            self._expire_sats(time.monotonic())
            return float(len(self._gsv))

    def measure_max_cn0_dbhz(self, max_age_s: float = _DEFAULT_MAX_AGE_S) -> float:
        self._ensure_stream(max_age_s)
        with self._state_lock:
            self._expire_sats(time.monotonic())
            return float(self._max_cn0())

    def measure_mean_cn0_dbhz(self, max_age_s: float = _DEFAULT_MAX_AGE_S) -> float:
        self._ensure_stream(max_age_s)
        with self._state_lock:
            self._expire_sats(time.monotonic())
            values = [sat.snr for sat, _ in self._gsv.values() if sat.snr > 0]
            return float(sum(values) / len(values)) if values else 0.0

    def measure_cn0_dbhz(
        self,
        prn: int,
        constellation: str = "GPS",
        max_age_s: float = _DEFAULT_MAX_AGE_S,
    ) -> float:
        self._ensure_stream(max_age_s)
        key = (constellation, prn)
        with self._state_lock:
            self._expire_sats(time.monotonic())
            item = self._gsv.get(key)
            if item is None:
                raise StaleDataError(
                    f"no recent SNR for {constellation} PRN {prn}",
                )
            sat, recv = item
            if time.monotonic() - recv > max_age_s:
                raise StaleDataError(
                    f"SNR for {constellation} PRN {prn} is stale",
                )
            return float(sat.snr)

    def get_satellite_snapshot(
        self, max_age_s: float = _DEFAULT_MAX_AGE_S,
    ) -> list[dict[str, float | str | int | None]]:
        self._ensure_stream(max_age_s)
        now = time.monotonic()
        with self._state_lock:
            self._expire_sats(now)
            rows: list[dict[str, float | str | int | None]] = []
            for sat, recv in self._gsv.values():
                rows.append(
                    {
                        "prn": sat.prn,
                        "constellation": sat.constellation,
                        "signal_id": sat.signal_id,
                        "elev": sat.elevation_deg,
                        "az": sat.azimuth_deg,
                        "cn0": sat.snr,
                        "used": False,
                        "age_s": now - recv,
                    },
                )
            if self._dop is not None:
                used = set(self._dop.prns)
                for row in rows:
                    prn = row["prn"]
                    row["used"] = int(prn) in used if prn is not None else False
            return rows

    def get_constellations_present(
        self, max_age_s: float = _DEFAULT_MAX_AGE_S,
    ) -> list[str]:
        snap = self.get_satellite_snapshot(max_age_s=max_age_s)
        return sorted({str(row["constellation"]) for row in snap})

    def measure_speed_m_s(self, max_age_s: float = _DEFAULT_MAX_AGE_S) -> float:
        self._ensure_stream(max_age_s)
        with self._state_lock:
            if (
                self._velocity is None
                or (time.monotonic() - self._velocity_recv_mono) > max_age_s
            ):
                raise StaleDataError("speed not available from recent RMC/VTG")
            return self._velocity.speed_m_s

    def measure_course_deg(self, max_age_s: float = _DEFAULT_MAX_AGE_S) -> float:
        self._ensure_stream(max_age_s)
        with self._state_lock:
            if (
                self._velocity is None
                or (time.monotonic() - self._velocity_recv_mono) > max_age_s
            ):
                raise StaleDataError("course not available from recent RMC/VTG")
            return self._velocity.course_deg

    def measure_h_acc_m(self, max_age_s: float = _DEFAULT_MAX_AGE_S) -> float:
        _ = max_age_s
        raise EquipmentCapabilityError(
            f"gnss model `{self._model}` does not report horizontal accuracy",
        )

    def measure_v_acc_m(self, max_age_s: float = _DEFAULT_MAX_AGE_S) -> float:
        _ = max_age_s
        raise EquipmentCapabilityError(
            f"gnss model `{self._model}` does not report vertical accuracy",
        )

    def measure_geoid_separation_m(self, max_age_s: float = _DEFAULT_MAX_AGE_S) -> float:
        return float(self._require_fresh_fix(max_age_s).geoid_separation_m)

    def measure_data_age_s(self) -> float:
        with self._state_lock:
            if not self._fix_recv_mono:
                return float("inf")
            return time.monotonic() - self._fix_recv_mono

    def measure_utc_time(self, max_age_s: float = _DEFAULT_MAX_AGE_S) -> str:
        self._require_fresh_fix(max_age_s)
        with self._state_lock:
            if self._utc_iso:
                return self._utc_iso
            return self._fix.utc_time if self._fix else ""

    def mark_acquisition_start(self) -> None:
        self._acq_start_mono = time.monotonic()
        self._ttff_s = None

    def measure_ttff_s(self) -> float:
        if self._ttff_s is not None:
            return float(self._ttff_s)
        raise NoFixError("TTFF not available; call mark_acquisition_start/cold_start first")

    def measure_fix_availability(self) -> float:
        if self._epochs_total <= 0:
            return 0.0
        return float(self._epochs_total - self._epochs_nofix) / float(self._epochs_total)

    def measure_longest_outage_s(self) -> float:
        longest = self._longest_outage_s
        if self._outage_start_mono is not None:
            longest = max(longest, time.monotonic() - self._outage_start_mono)
        return float(longest)

    def measure_reacquisition_s(self) -> float:
        if self._reacquisition_s is None:
            raise NoFixError("no reacquisition observed in this logging window")
        return float(self._reacquisition_s)

    def cold_start(self) -> None:
        raise EquipmentCapabilityError(
            f"gnss model `{self._model}` does not support cold_start",
        )

    def load_config(self, path: str) -> None:
        unsupported(self._model, "load_config")

    def save_config(self, path: str) -> Path:
        unsupported(self._model, "save_config")

    def set_message_rate(self, message: str, rate_hz: float) -> None:
        unsupported(self._model, "set_message_rate", detail=f"message={message!r}")

    def start_logging(self, path: str, key: str = "") -> None:
        if self._logging_active():
            raise RuntimeError(f"gnss model `{self._model}` is already logging")
        if not key:
            key = f"gnss{self._gnss_id}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
        raw_path = resolve_artifact_path(path)
        stem = Path(path).stem
        track_path = resolve_artifact_path(
            str(Path(path).with_name(f"{stem}_track.csv")),
        )
        wire_rel = str(Path(path).with_name(f"{stem}_wire{self._wire_suffix()}"))
        wire_path = resolve_artifact_path(wire_rel)
        self._logging_key = key
        self._raw_log_path = raw_path
        self._wire_log_path = wire_path
        self._track_csv_path = track_path
        self._track_samples.clear()
        self._nmea_buf.clear()
        self._epoch_index = 0
        self._epochs_total = 0
        self._epochs_nofix = 0
        self._longest_outage_s = 0.0
        self._reacquisition_s = None
        self._outage_start_mono = None
        self._had_fix = False
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        wire_path.parent.mkdir(parents=True, exist_ok=True)
        self._raw_log = raw_path.open("w", encoding="utf-8", newline="")
        self._wire_log = wire_path.open("wb")
        self._track_csv = track_path.open("w", encoding="utf-8", newline="")
        self._track_writer = csv.DictWriter(self._track_csv, fieldnames=list(_TRACK_FIELDS))
        self._track_writer.writeheader()
        self._track_csv.flush()
        record_artifact(
            domain="equipment",
            command="log_artifacts",
            key=f"{key}.files",
            path=track_path,
            value={
                "raw": str(raw_path),
                "wire": str(wire_path),
                "track_csv": str(track_path),
            },
        )
        self._listener = GnssListener(self._read_bytes, self._on_listener_chunk)
        self._listener.start()
        self._epoch_stop.clear()
        self._epoch_timer = threading.Thread(
            target=self._epoch_loop,
            name=f"gnss-epoch-{self._gnss_id}",
            daemon=True,
        )
        self._epoch_timer.start()

    def stop_logging(self) -> None:
        self._epoch_stop.set()
        if self._epoch_timer is not None:
            self._epoch_timer.join(timeout=2.0)
            self._epoch_timer = None
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
        if self._logging_key and self._epochs_total:
            enqueue_measurement(
                domain="equipment",
                command="fix_availability",
                key=f"{self._logging_key}.fix_availability",
                value=self.measure_fix_availability(),
            )
            enqueue_measurement(
                domain="equipment",
                command="longest_outage_s",
                key=f"{self._logging_key}.longest_outage_s",
                value=self.measure_longest_outage_s(),
                units="s",
            )
            enqueue_measurement(
                domain="equipment",
                command="epochs_total",
                key=f"{self._logging_key}.epochs_total",
                value=float(self._epochs_total),
            )
            enqueue_measurement(
                domain="equipment",
                command="epochs_nofix",
                key=f"{self._logging_key}.epochs_nofix",
                value=float(self._epochs_nofix),
            )
            if self._reacquisition_s is not None:
                enqueue_measurement(
                    domain="equipment",
                    command="reacquisition_s",
                    key=f"{self._logging_key}.reacquisition_s",
                    value=float(self._reacquisition_s),
                    units="s",
                )
        if self._raw_log is not None:
            self._raw_log.close()
            self._raw_log = None
        if self._wire_log is not None:
            self._wire_log.close()
            self._wire_log = None
            if self._wire_log_path is not None and self._logging_key:
                record_artifact(
                    domain="equipment",
                    command="wire_log",
                    key=f"{self._logging_key}.wire",
                    path=self._wire_log_path,
                    value={"path": str(self._wire_log_path)},
                )
        if self._track_csv is not None:
            self._track_csv.close()
            self._track_csv = None
        self._track_writer = None

    def _track_rows(self) -> list[dict[str, float | str]]:
        # Prefer the full CSV (complete soak history) over the bounded in-memory tail.
        if self._track_csv_path is not None and self._track_csv_path.is_file():
            rows = read_track_csv(self._track_csv_path)
            if rows:
                return rows
        if self._track_samples:
            return [dict(row) for row in self._track_samples]
        return []

    def save_track_plot(self, path: str) -> Path:
        plot_path = resolve_artifact_path(path)
        write_track_plot(self._track_rows(), plot_path)
        if self._logging_key:
            record_artifact(
                domain="equipment",
                command="save_track_plot",
                key=f"{self._logging_key}.track_plot",
                path=plot_path,
            )
        return plot_path

    def save_skyplot(self, path: str) -> Path:
        plot_path = resolve_artifact_path(path)
        with self._state_lock:
            sats = {
                sat.prn: (sat.elevation_deg, sat.azimuth_deg, sat.snr)
                for sat, _ in self._gsv.values()
            }
        write_skyplot(sats, plot_path)
        if self._logging_key:
            record_artifact(
                domain="equipment",
                command="save_skyplot",
                key=f"{self._logging_key}.skyplot",
                path=plot_path,
            )
        return plot_path

    def save_quality_plot(self, path: str) -> Path:
        plot_path = resolve_artifact_path(path)
        write_quality_plot(self._track_rows(), plot_path)
        if self._logging_key:
            record_artifact(
                domain="equipment",
                command="save_quality_plot",
                key=f"{self._logging_key}.quality_plot",
                path=plot_path,
            )
        return plot_path

    def close(self) -> None:
        self.stop_logging()
        self._transport.close()
