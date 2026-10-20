"""Bounded, streaming Beagle capture and deterministic offline simulation."""

from __future__ import annotations

import json
import math
import shutil
from threading import Event, RLock, Thread
from time import monotonic
from typing import TYPE_CHECKING, Any, TextIO

from colosseum_equipment.io.backends._usb import checked, release
from colosseum_equipment.io.backends.totalphase import open_session
from colosseum_equipment.io.exceptions import IoConfigError, IoConnectionError

if TYPE_CHECKING:
    from pathlib import Path


class AnalyzerBackend:
    """One capture per device; data stays on disk rather than in an event queue."""

    def __init__(self, config: dict[str, Any]) -> None:
        self._sim = str(config.get("driver") or "").lower() == "sim"
        self._config = dict(config)
        self._lock = RLock()
        self._stop = Event()
        self._thread: Thread | None = None
        self._path: Path | None = None
        self._error: Exception | None = None
        self._closed = False
        self._summary: dict[str, Any] = {}
        self._drain_deadline = 0.0
        self._session = None
        self.configure()
        if not self._sim:
            self._session = open_session("bg", config, exclusive=True)
            try:
                self._validate_hardware()
            except Exception:
                release(self._session)
                self._session = None
                raise

    def configure(
        self, *, protocol: str | None = None, mode: int | None = None,
        sample_rate_hz: int | None = None,
    ) -> None:
        with self._lock:
            if self._closed:
                raise IoConnectionError("analyzer is closed")
            if self._thread is not None and self._thread.is_alive():
                raise IoConfigError("stop the capture before configuring the analyzer")
            config = dict(self._config)
            for name, value in (("protocol", protocol), ("mode", mode),
                                ("sample_rate_hz", sample_rate_hz)):
                if value is not None:
                    config[name] = value
            model = str(config.get("model") or "")
            selected = str(config.get("protocol") or ("usb" if model.startswith("usb-") else "i2c"))
            if not self._sim and model not in ("i2c-spi", "usb-12", "usb-480"):
                raise IoConfigError("Beagle model must be i2c-spi, usb-12, or usb-480")
            if selected not in ("i2c", "spi", "usb"):
                raise IoConfigError("analyzer protocol must be i2c, spi, or usb")
            if not self._sim and ((model == "i2c-spi") == (selected == "usb")):
                raise IoConfigError("protocol is not supported by this Beagle model")
            if int(config.get("mode", 0)) not in range(4):
                raise IoConfigError("SPI mode must be 0..3")
            rate = int(config.get("sample_rate_hz", 50_000_000 if model == "i2c-spi" else 0))
            if rate < 0 or (model == "i2c-spi" and not 1000 <= rate <= 50_000_000):
                raise IoConfigError("I2C/SPI sample_rate_hz must be 1000..50000000")
            if model.startswith("usb-") and rate:
                raise IoConfigError("USB analyzers have a fixed sample rate; omit sample_rate_hz")
            duration = float(config.get("max_duration_s", 60))
            if not math.isfinite(duration) or duration <= 0:
                raise IoConfigError("max_duration_s must be finite and positive")
            for name, default in (("max_records", 100_000), ("max_bytes", 64 * 1024 * 1024)):
                if int(config.get(name, default)) <= 0:
                    raise IoConfigError(f"{name} must be positive")
            if model.startswith("usb-") and config.get("target_power", False):
                raise IoConfigError("USB 12/480 do not support target power control")
            self._config = config
            self._protocol, self._model, self._rate = selected, model, rate

    def _validate_hardware(self) -> None:
        assert self._session is not None
        s = self._session
        features = checked(s.api.bg_features(s.handle), "bg_features")
        usb = bool(features & s.api.BG_FEATURE_USB)
        hs = bool(features & s.api.BG_FEATURE_USB_HS)
        ss = bool(features & s.api.BG_FEATURE_USB_SS)
        if ((self._model == "usb-12" and (not usb or hs or ss))
                or (self._model == "usb-480" and (not usb or not hs or ss))
                or (self._model == "i2c-spi" and (usb or not features & s.api.BG_FEATURE_I2C
                                                   or not features & s.api.BG_FEATURE_SPI))):
            raise IoConfigError("connected Beagle features do not match configured model")
        if self._model == "i2c-spi":
            checked(s.api.bg_target_power(s.handle, int(bool(self._config.get("target_power")))),
                    "bg_target_power")
            checked(s.api.bg_i2c_pullup(s.handle, int(bool(self._config.get("pullup", False)))),
                    "bg_i2c_pullup")
        elif self._model == "usb-480":
            usb_features = checked(s.api.bg_usb_features(s.handle), "bg_usb_features")
            if usb_features & s.api.BG_USB_FEATURE_IV_MON_LITE:
                raise IoConfigError("USB 480 Power is not the configured USB 480 model")

    def _enable(self) -> int:
        if self._sim:
            return self._rate or 60_000_000
        assert self._session is not None
        s = self._session
        if self._protocol == "spi":
            mode = int(self._config.get("mode", 0))
            edge = (s.api.BG_SPI_SCK_SAMPLING_EDGE_FALLING
                    if (mode >> 1) ^ (mode & 1) else s.api.BG_SPI_SCK_SAMPLING_EDGE_RISING)
            checked(s.api.bg_spi_configure(
                s.handle, s.api.BG_SPI_SS_ACTIVE_LOW, edge, s.api.BG_SPI_BITORDER_MSB,
            ), "bg_spi_configure")
        rate = checked(s.api.bg_samplerate(s.handle, self._rate // 1000), "bg_samplerate")
        if rate <= 0:
            raise IoConnectionError("bg_samplerate returned an invalid sample rate")
        protocol = getattr(s.api, f"BG_PROTOCOL_{self._protocol.upper()}")
        checked(s.api.bg_enable(s.handle, protocol), "bg_enable")
        return rate * 1000

    def start(self, path: Path) -> None:
        with self._lock:
            if self._closed:
                raise IoConnectionError("analyzer is closed")
            if self._thread is not None and self._thread.is_alive():
                raise IoConfigError("capture is already running")
            # Never silently replace a prior capture.
            handle = path.open("x", encoding="utf-8")
            try:
                rate = self._enable()
            except Exception:
                handle.close()
                path.unlink()
                raise
            self._path = path
            self._error = None
            self._stop.clear()
            self._summary = {
                "protocol": self._protocol, "model": self._model or "sim",
                "sample_rate_hz": rate, "records": 0, "bytes": 0,
                "flagged_records": 0, "loss_detected": False,
                "tail_may_be_discarded": False, "drained_to_idle": False,
                "stop_reason": "running",
            }
            try:
                handle.write(json.dumps({"type": "metadata", **self._summary}) + "\n")
                handle.flush()
                self._thread = Thread(target=self._capture, args=(handle,), daemon=True,
                                      name="colosseum-beagle")
                self._thread.start()
            except Exception as exc:
                self._thread = None
                self._error = exc
                self._summary.update(stop_reason="error", error=str(exc), loss_detected=True)
                try:
                    handle.close()
                finally:
                    if self._session is not None:
                        checked(self._session.api.bg_disable(self._session.handle), "bg_disable")
                raise

    def _read(self) -> dict[str, Any] | None:
        assert self._session is not None
        s = self._session
        limit = 65535
        if self._protocol == "usb":
            n, status, events, sop, duration, offset, data = s.api.bg_usb2_read(s.handle, limit)
            payload: dict[str, Any] = {"data": bytes(data[:min(n, limit)]).hex(), "events": events}
        elif self._protocol == "spi":
            n, status, sop, duration, offset, mosi, miso = s.api.bg_spi_read(s.handle, limit, limit)
            payload = {"mosi": bytes(mosi[:min(n, limit)]).hex(),
                       "miso": bytes(miso[:min(n, limit)]).hex()}
        else:
            n, status, sop, duration, offset, data = s.api.bg_i2c_read(s.handle, limit)
            # Preserve the ninth ACK/NACK bit rather than coercing u16 words to bytes.
            payload = {"words": list(data[:min(n, limit)])}
        checked(n, "Beagle read")
        if n == 0 and (status & ~s.api.BG_READ_TIMEOUT) == 0 and not payload.get("events"):
            return None
        loss_mask = 0
        for name in dir(s.api):
            if name.startswith("BG_READ_") and any(
                part in name for part in ("OVERFLOW", "LOST", "SHORT_BUFFER", "MIDDLE", "PARTIAL")
            ):
                loss_mask |= int(getattr(s.api, name))
        return {"type": "packet", "protocol": self._protocol, "count": n,
                "status": int(status), "time_sop_ticks": sop, "duration_ticks": duration,
                "data_offset_ticks": offset, "loss": bool(status & loss_mask) or n > limit,
                "flagged": bool(status & ~s.api.BG_READ_TIMEOUT), **payload}

    def _capture(self, handle: TextIO) -> None:
        started = monotonic()
        max_duration = float(self._config.get("max_duration_s", 60))
        max_records = int(self._config.get("max_records", 100_000))
        max_bytes = int(self._config.get("max_bytes", 64 * 1024 * 1024))
        sim_records = iter(self._config.get("records", []))
        try:
            while True:
                if monotonic() - started >= max_duration:
                    self._summary["stop_reason"] = "duration_limit"
                    break
                if self._stop.is_set() and monotonic() >= self._drain_deadline:
                    self._summary["stop_reason"] = "drain_timeout"
                    self._summary["loss_detected"] = True
                    break
                if self._sim:
                    packet = next(sim_records, None)
                    if packet is not None:
                        packet = {"type": "packet", "protocol": self._protocol, **packet}
                else:
                    packet = self._read()
                if packet is None:
                    if self._stop.is_set():
                        self._summary.update(stop_reason="stopped", drained_to_idle=True)
                        break
                    if self._sim:
                        self._stop.wait(0.01)
                    continue
                encoded = json.dumps(packet) + "\n"
                encoded_size = len(encoded.encode("utf-8"))
                if self._summary["bytes"] + encoded_size > max_bytes:
                    self._summary.update(stop_reason="byte_limit", loss_detected=True)
                    break
                handle.write(encoded)
                self._summary["records"] += 1
                self._summary["bytes"] += encoded_size
                self._summary["flagged_records"] += int(bool(packet.get("flagged")))
                self._summary["loss_detected"] |= bool(packet.get("loss"))
                if self._summary["records"] >= max_records:
                    self._summary.update(stop_reason="record_limit", loss_detected=True)
                    break
        except Exception as exc:  # noqa: BLE001 -- propagate worker failures through stop()
            self._error = exc
            self._summary.update(stop_reason="error", error=str(exc), loss_detected=True)
        finally:
            if self._session is not None:
                # These models have no atomic stop-and-drain. Read until idle or
                # deadline first, then disable. Traffic in that boundary can be lost.
                self._summary["tail_may_be_discarded"] = True
                try:
                    checked(self._session.api.bg_disable(self._session.handle), "bg_disable")
                except Exception as exc:  # noqa: BLE001 -- preserve shutdown failures
                    self._error = exc
                    self._summary.update(stop_reason="error", error=str(exc), loss_detected=True)
            self._summary["elapsed_s"] = monotonic() - started
            try:
                handle.write(json.dumps({"type": "summary", **self._summary}) + "\n")
            except Exception as exc:  # noqa: BLE001 -- propagate artifact failures
                self._error = exc
                self._summary.update(stop_reason="error", error=str(exc), loss_detected=True)
            finally:
                try:
                    handle.close()
                except Exception as exc:  # noqa: BLE001 -- surface failed flush/close
                    self._error = exc
                    self._summary.update(stop_reason="error", error=str(exc), loss_detected=True)

    def stop(self, timeout_s: float = 2.0) -> dict[str, Any]:
        if not math.isfinite(timeout_s) or timeout_s <= 0:
            raise IoConfigError("timeout_s must be finite and positive")
        with self._lock:
            thread = self._thread
            if thread is None:
                raise IoConfigError("no capture has been started")
            self._drain_deadline = monotonic() + timeout_s
            self._stop.set()
            # The SDK read timeout is at most one second. Never close its handle
            # while a native read is still running.
            thread.join(timeout_s + 1.1)
            if thread.is_alive():
                raise IoConnectionError("capture worker did not stop; device handle retained")
            if self._error is not None:
                raise IoConnectionError(f"capture failed: {self._error}") from self._error
            return dict(self._summary)

    def export(self, path: Path) -> dict[str, Any]:
        with self._lock:
            if self._path is None:
                raise IoConfigError("no capture has been started")
            if self._thread is not None and self._thread.is_alive():
                raise IoConfigError("stop the capture before exporting")
            if path.resolve() != self._path.resolve():
                # Exclusive destination creation avoids replacing other evidence.
                with self._path.open("rb") as src, path.open("xb") as dst:
                    shutil.copyfileobj(src, dst)
            # Failed captures remain exportable as diagnostic evidence.
            return dict(self._summary)

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            try:
                if self._thread is not None:
                    self.stop()
            finally:
                if self._thread is None or not self._thread.is_alive():
                    self._closed = True
                    if self._session is not None:
                        s, self._session = self._session, None
                        release(s)
