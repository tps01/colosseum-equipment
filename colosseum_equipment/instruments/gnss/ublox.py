"""u-blox M8 / M10 / F9 / F10 GNSS (NMEA + UBX NAV-PVT / NAV-DOP).

Manuals:
- u-blox M10 SPG 5.00 Interface Description (UBX-20053845)
- u-blox F10 TIM 3.01 Interface Description (UBX-23003447)
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from colosseum.logging import get_logger

from colosseum_equipment._paths import resolve_artifact_path
from colosseum_equipment.evidence import record_artifact
from colosseum_equipment.exceptions import (
    EquipmentCapabilityError,
    EquipmentResponseError,
    EquipmentTimeoutError,
    StaleDataError,
)
from colosseum_equipment.instruments.gnss.generic import GenericGnss
from colosseum_equipment.instruments.gnss.nmea import NmeaDop, NmeaFix, NmeaVelocity
from colosseum_equipment.instruments.gnss.ubx import (
    CLS_ACK,
    CLS_CFG,
    CLS_MON,
    CLS_NAV,
    CLS_NMEA,
    ID_ACK_ACK,
    ID_ACK_NAK,
    ID_CFG_VALGET,
    ID_MON_VER,
    ID_NAV_DOP,
    ID_NAV_PVT,
    ID_NMEA_GSV,
    LEGACY_CFG_POLLS,
    NavPvt,
    UbxStreamParser,
    build_ubx,
    cfg_msg_rate,
    cfg_rst_cold,
    cfg_valget_poll,
    mon_ver_poll,
    parse_nav_dop,
    parse_nav_pvt,
    resolve_message_id,
    ucenter_hex_line,
)
from colosseum_equipment.instruments.gnss.ubx_config import (
    cfg_name,
    detect_mismatch,
    format_ucenter_txt,
    load_config_path,
)
from colosseum_equipment.instruments.registry import instrument_model

if TYPE_CHECKING:
    from colosseum_equipment.transports.base import Transport

_logger = get_logger("colosseum.equipment")


@instrument_model("gnss", "ublox-m8", "ublox-m10", "ublox-f9", "ublox-f10")
class UbloxGnss(GenericGnss):
    """Shared u-blox driver; series share NMEA + UBX NAV-PVT / NAV-DOP."""

    def __init__(self, transport: Transport, config: dict[str, Any]) -> None:
        super().__init__(transport, config)
        self._parser = UbxStreamParser()
        self._nav: NavPvt | None = None
        self._enable_messages()

    def _wire_suffix(self) -> str:
        return ".ubx"

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

    def _enable_messages(self) -> None:
        self._write_bytes(cfg_msg_rate(CLS_NAV, ID_NAV_PVT, 1))
        self._write_bytes(cfg_msg_rate(CLS_NAV, ID_NAV_DOP, 1))
        self._write_bytes(cfg_msg_rate(CLS_NMEA, ID_NMEA_GSV, 1))

    def _is_m8_family(self) -> bool:
        model = self._model.lower()
        return "m8" in model and "m10" not in model

    def _apply_events(self, events: list[tuple[str, object]]) -> None:
        for kind, payload in events:
            if kind == "nmea" and isinstance(payload, str):
                self._log_raw_line(payload)
                self._ingest_nmea_line(payload, record_raw=False, record_track=False)
            elif kind == "ubx" and isinstance(payload, tuple) and len(payload) == 3:
                msg_class, msg_id, body = payload
                self._log_raw_line(f"#UBX {msg_class:02X}{msg_id:02X} {body.hex()}")
                if not isinstance(body, bytes):
                    continue
                if msg_class == CLS_NAV and msg_id == ID_NAV_PVT:
                    nav = parse_nav_pvt(body)
                    if nav is not None:
                        self._nav = nav
                        fix = NmeaFix(
                            latitude=nav.latitude,
                            longitude=nav.longitude,
                            altitude_m=nav.altitude_m,
                            fix_quality=nav.fix_quality,
                            satellites=nav.satellites,
                            hdop=0.0,  # true HDOP comes from NAV-DOP / GSA
                            utc_time=nav.utc_time,
                        )
                        now = time.monotonic()
                        with self._state_lock:
                            self._fix = fix
                            self._fix_recv_mono = now
                            self._utc_iso = nav.utc_time
                            self._h_acc_m = nav.h_acc_m
                            self._v_acc_m = nav.v_acc_m
                            self._velocity = NmeaVelocity(
                                speed_m_s=nav.speed_m_s,
                                course_deg=nav.course_deg,
                            )
                            self._velocity_recv_mono = now
                        if fix.fix_quality > 0:
                            self._note_first_fix()
                elif msg_class == CLS_NAV and msg_id == ID_NAV_DOP:
                    dop = parse_nav_dop(body)
                    if dop is not None:
                        now = time.monotonic()
                        with self._state_lock:
                            self._dop = NmeaDop(
                                fix_type="3d" if dop.pdop > 0 else "none",
                                pdop=dop.pdop,
                                hdop=dop.hdop,
                                vdop=dop.vdop,
                                prns=(),
                            )
                            self._dop_recv_mono = now
                            self._gdop = dop.gdop

    def _on_listener_chunk(self, data: bytes) -> None:
        if data:
            self._write_wire(data)
            self._note_bytes()
        self._apply_events(self._parser.feed(data))

    def _collect_ubx(
        self,
        *,
        timeout_s: float,
        want_class: int | None = None,
        want_id: int | None = None,
        max_msgs: int = 32,
    ) -> list[tuple[int, int, bytes]]:
        """Read transport for a short window and collect matching UBX messages."""
        if self._logging_active():
            raise RuntimeError(
                "gnss save_config/load_config should not run while logging; "
                "call stop_logging first",
            )
        deadline = time.monotonic() + timeout_s
        found: list[tuple[int, int, bytes]] = []
        parser = UbxStreamParser()
        while time.monotonic() < deadline and len(found) < max_msgs:
            chunk = self._read_bytes(512)
            if not chunk:
                time.sleep(0.02)
                continue
            self._note_bytes()
            for kind, payload in parser.feed(chunk):
                if kind != "ubx" or not isinstance(payload, tuple) or len(payload) != 3:
                    continue
                msg_class, msg_id, body = payload
                if not isinstance(body, bytes):
                    continue
                if want_class is not None and msg_class != want_class:
                    continue
                if want_id is not None and msg_id != want_id:
                    continue
                found.append((msg_class, msg_id, body))
        return found

    def _drain_acks(self, *, timeout_s: float = 0.3) -> tuple[int, int]:
        acks = naks = 0
        for msg_class, msg_id, _body in self._collect_ubx(
            timeout_s=timeout_s,
            want_class=CLS_ACK,
            max_msgs=64,
        ):
            if msg_id == ID_ACK_ACK:
                acks += 1
            elif msg_id == ID_ACK_NAK:
                naks += 1
        return acks, naks

    def load_config(self, path: str) -> None:
        resolved = Path(path)
        if not resolved.is_file():
            # Allow paths relative to CWD; also try resolve_artifact for run-dir files
            alt = resolve_artifact_path(path)
            resolved = alt if alt.is_file() else resolved
        if not resolved.is_file():
            raise FileNotFoundError(f"GNSS config not found: {path}")
        frames, info = load_config_path(resolved)
        if not frames:
            raise EquipmentResponseError(f"no CFG messages found in {path}")
        if info is not None:
            warning = detect_mismatch(self._model, info)
            if warning:
                _logger.warning("%s", warning)
        total_naks = 0
        for frame in frames:
            self._write_bytes(frame)
            _acks, naks = self._drain_acks(timeout_s=0.25)
            total_naks += naks
        self._enable_messages()
        if total_naks and total_naks >= max(1, len(frames) // 2):
            raise EquipmentResponseError(
                f"gnss model `{self._model}` rejected {total_naks}/{len(frames)} "
                f"config messages from {path} (wrong generation or unsupported keys?)",
            )

    def save_config(self, path: str) -> Path:
        if self._logging_active():
            raise RuntimeError(
                "gnss save_config should not run while logging; call stop_logging first",
            )
        out_path = resolve_artifact_path(path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        mon_line: str | None = None
        self._write_bytes(mon_ver_poll())
        for msg_class, msg_id, body in self._collect_ubx(
            timeout_s=1.5,
            want_class=CLS_MON,
            want_id=ID_MON_VER,
            max_msgs=1,
        ):
            mon_line = ucenter_hex_line("MON-VER", msg_class, msg_id, body)
            break

        entries: list[tuple[str, int, int, bytes]] = []
        if self._is_m8_family():
            for name, msg_class, msg_id, poll_payload in LEGACY_CFG_POLLS:
                self._write_bytes(build_ubx(msg_class, msg_id, poll_payload))
                for cls, mid, body in self._collect_ubx(
                    timeout_s=1.0,
                    want_class=CLS_CFG,
                    want_id=msg_id,
                    max_msgs=4,
                ):
                    entries.append((name, cls, mid, body))
        else:
            # Gen 9+: walk CFG-VALGET pages from RAM layer
            position = 0
            for _ in range(64):
                self._write_bytes(cfg_valget_poll(layer=0, position=position))
                batch = self._collect_ubx(
                    timeout_s=1.2,
                    want_class=CLS_CFG,
                    want_id=ID_CFG_VALGET,
                    max_msgs=8,
                )
                if not batch:
                    break
                for cls, mid, body in batch:
                    entries.append((cfg_name(cls, mid), cls, mid, body))
                    # Advance by number of key/value bytes roughly; FW uses position
                    position += max(1, len(body) // 8)
                if len(batch) < 2:
                    # Likely last page
                    if len(batch[0][2]) < 8:
                        break

        if not entries:
            raise EquipmentResponseError(
                f"gnss model `{self._model}` returned no CFG data for save_config",
            )
        text = format_ucenter_txt(mon_ver_line=mon_line, entries=entries)
        out_path.write_text(text, encoding="utf-8")
        record_artifact(
            domain="equipment",
            command="save_config",
            key=f"gnss{self._gnss_id}.config",
            path=out_path,
            value={"model": self._model, "entries": len(entries)},
        )
        return out_path

    def set_message_rate(self, message: str, rate_hz: float) -> None:
        try:
            msg_class, msg_id = resolve_message_id(message)
        except KeyError as exc:
            raise EquipmentCapabilityError(
                f"gnss model `{self._model}` unknown message `{message}`",
            ) from exc
        if rate_hz < 0:
            raise ValueError("rate_hz must be >= 0")
        rate = 0 if rate_hz == 0 else max(1, int(round(rate_hz)))
        self._write_bytes(cfg_msg_rate(msg_class, msg_id, rate))
        self._session_message_rates[message.strip().upper()] = float(rate_hz)

    def _has_fix(self) -> bool:
        if self._nav is not None and self._nav.fix_ok:
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

    def measure_h_acc_m(self, max_age_s: float = 5.0) -> float:
        self._ensure_stream(max_age_s)
        with self._state_lock:
            if self._h_acc_m is None:
                raise StaleDataError("horizontal accuracy not available")
            return float(self._h_acc_m)

    def measure_v_acc_m(self, max_age_s: float = 5.0) -> float:
        self._ensure_stream(max_age_s)
        with self._state_lock:
            if self._v_acc_m is None:
                raise StaleDataError("vertical accuracy not available")
            return float(self._v_acc_m)

    def measure_gdop(self, max_age_s: float = 5.0) -> float:
        self._ensure_stream(max_age_s)
        with self._state_lock:
            if self._gdop is None:
                raise StaleDataError("GDOP not available from NAV-DOP")
            return float(self._gdop)

    def cold_start(self) -> None:
        self.mark_acquisition_start()
        self._write_bytes(cfg_rst_cold())
        self._nav = None
        self._clear_nav_state()
