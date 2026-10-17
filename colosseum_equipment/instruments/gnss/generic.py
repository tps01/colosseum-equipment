"""Generic GNSS receiver using NMEA 0183 GGA/RMC/GSV over serial or VISA."""

from __future__ import annotations

import csv
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, TextIO

from colosseum_equipment._paths import resolve_artifact_path
from colosseum_equipment.exceptions import EquipmentCapabilityError, EquipmentTimeoutError
from colosseum_equipment.instruments.gnss.listener import GnssListener
from colosseum_equipment.instruments.gnss.nmea import (
    NmeaFix,
    parse_gga,
    parse_gsv,
    parse_rmc_utc_date,
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
    "utc_iso",
    "latitude",
    "longitude",
    "altitude_m",
    "fix_quality",
    "satellites",
    "hdop",
)


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
        self._fix: NmeaFix | None = None
        self._utc_iso = ""
        self._state_lock = threading.Lock()
        self._gsv: dict[int, tuple[float, float, float]] = {}
        self._track_samples: list[dict[str, float | str]] = []
        self._listener: GnssListener | None = None
        self._raw_log: TextIO | None = None
        self._track_csv: TextIO | None = None
        self._track_writer: csv.DictWriter[str] | None = None
        self._raw_log_path: Path | None = None
        self._track_csv_path: Path | None = None
        self._nmea_buf = bytearray()

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

    def _clear_nav_state(self) -> None:
        with self._state_lock:
            self._fix = None
            self._utc_iso = ""
            self._gsv.clear()

    def _append_track_sample(self, fix: NmeaFix) -> None:
        utc = self._utc_iso or fix.utc_time
        row: dict[str, float | str] = {
            "utc_iso": utc,
            "latitude": fix.latitude,
            "longitude": fix.longitude,
            "altitude_m": fix.altitude_m,
            "fix_quality": float(fix.fix_quality),
            "satellites": float(fix.satellites),
            "hdop": fix.hdop,
        }
        self._track_samples.append(row)
        if self._track_writer is not None and self._track_csv is not None:
            self._track_writer.writerow(row)
            self._track_csv.flush()

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
        if record_raw:
            self._log_raw_line(line)
        sats = parse_gsv(line)
        if sats:
            with self._state_lock:
                for prn, elev, az, snr in sats:
                    self._gsv[prn] = (elev, az, snr)
            return
        fix = parse_gga(line)
        if fix is not None:
            with self._state_lock:
                self._fix = fix
                if fix.utc_time and not self._utc_iso:
                    self._utc_iso = fix.utc_time
                if record_track and fix.fix_quality > 0:
                    self._append_track_sample(fix)
            return
        iso = parse_rmc_utc_date(line)
        if iso is not None:
            with self._state_lock:
                self._utc_iso = iso

    def _ingest_line(self, line: str) -> None:
        self._ingest_nmea_line(line, record_raw=False, record_track=True)

    def _feed_nmea_bytes(self, data: bytes) -> None:
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
            except Exception:
                continue
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

    def _require_fix(self) -> NmeaFix:
        with self._state_lock:
            if self._fix is not None and self._fix.fix_quality > 0:
                return self._fix
        return self._poll(float(self._config.get("timeout", 5.0)))

    def measure_latitude(self) -> float:
        return self._require_fix().latitude

    def measure_longitude(self) -> float:
        return self._require_fix().longitude

    def measure_altitude_m(self) -> float:
        return self._require_fix().altitude_m

    def measure_fix_quality(self) -> float:
        return float(self._require_fix().fix_quality)

    def measure_satellites(self) -> float:
        return float(self._require_fix().satellites)

    def measure_hdop(self) -> float:
        return self._require_fix().hdop

    def measure_utc_time(self) -> str:
        self._require_fix()
        with self._state_lock:
            if self._utc_iso:
                return self._utc_iso
            return self._fix.utc_time if self._fix else ""

    def cold_start(self) -> None:
        raise EquipmentCapabilityError(
            f"gnss model `{self._model}` does not support cold_start",
        )

    def start_logging(self, path: str) -> None:
        if self._logging_active():
            raise RuntimeError(f"gnss model `{self._model}` is already logging")
        raw_path = resolve_artifact_path(path)
        track_path = resolve_artifact_path(
            str(Path(path).with_name(f"{Path(path).stem}_track.csv")),
        )
        self._raw_log_path = raw_path
        self._track_csv_path = track_path
        self._track_samples.clear()
        self._nmea_buf.clear()
        self._raw_log = raw_path.open("w", encoding="utf-8", newline="")
        self._track_csv = track_path.open("w", encoding="utf-8", newline="")
        self._track_writer = csv.DictWriter(self._track_csv, fieldnames=list(_TRACK_FIELDS))
        self._track_writer.writeheader()
        self._track_csv.flush()
        self._listener = GnssListener(self._read_bytes, self._on_listener_chunk)
        self._listener.start()

    def stop_logging(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
        if self._raw_log is not None:
            self._raw_log.close()
            self._raw_log = None
        if self._track_csv is not None:
            self._track_csv.close()
            self._track_csv = None
        self._track_writer = None

    def _track_rows(self) -> list[dict[str, float | str]]:
        if self._track_samples:
            return list(self._track_samples)
        if self._track_csv_path is not None and self._track_csv_path.is_file():
            return read_track_csv(self._track_csv_path)
        return []

    def save_track_plot(self, path: str) -> Path:
        plot_path = resolve_artifact_path(path)
        write_track_plot(self._track_rows(), plot_path)
        return plot_path

    def save_skyplot(self, path: str) -> Path:
        plot_path = resolve_artifact_path(path)
        with self._state_lock:
            sats = dict(self._gsv)
        write_skyplot(sats, plot_path)
        return plot_path

    def save_quality_plot(self, path: str) -> Path:
        plot_path = resolve_artifact_path(path)
        write_quality_plot(self._track_rows(), plot_path)
        return plot_path

    def close(self) -> None:
        self.stop_logging()
        self._transport.close()
