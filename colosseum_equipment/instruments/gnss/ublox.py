"""u-blox M8 / M10 / F9 / F10 GNSS (NMEA + UBX NAV-PVT / NAV-DOP).

Manuals:
- u-blox M10 SPG 5.00 Interface Description (UBX-20053845)
- u-blox F10 TIM 3.01 Interface Description (UBX-23003447)
"""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from colosseum.logging import get_logger

from colosseum_equipment._paths import resolve_artifact_path
from colosseum_equipment.evidence import record_artifact
from colosseum_equipment.exceptions import (
    EquipmentCapabilityError,
    EquipmentResponseError,
    StaleDataError,
)
from colosseum_equipment.instruments.gnss.generic import _BinaryGnss
from colosseum_equipment.instruments.gnss.nmea import NmeaDop, NmeaFix, NmeaVelocity
from colosseum_equipment.instruments.gnss.messages import (
    LOGICAL_CLOCK,
    LOGICAL_DOP,
    LOGICAL_MEASX,
    LOGICAL_POSECEF,
    LOGICAL_PVT,
    LOGICAL_RAWX,
    LOGICAL_SAT,
    LOGICAL_STATUS,
    LOGICAL_TIME,
    expand_profile,
)
from colosseum_equipment.instruments.gnss.ubx import (
    CLS_ACK,
    CLS_CFG,
    CLS_MON,
    CLS_NAV,
    CLS_RXM,
    ID_ACK_ACK,
    ID_ACK_NAK,
    ID_CFG_VALGET,
    ID_MON_VER,
    ID_NAV_CLOCK,
    ID_NAV_DOP,
    ID_NAV_POSECEF,
    ID_NAV_PVT,
    ID_NAV_SAT,
    ID_NAV_STATUS,
    ID_NAV_TIMEGPS,
    ID_RXM_MEASX,
    ID_RXM_RAWX,
    LEGACY_CFG_POLLS,
    NavPvt,
    UbxStreamParser,
    build_ubx,
    cfg_msg_rate,
    cfg_rst_cold,
    cfg_valget_poll,
    mon_ver_poll,
    nav_dop_fields,
    nav_pvt_fields,
    parse_mon_ver_series,
    parse_nav_clock,
    parse_nav_dop,
    parse_nav_posecef,
    parse_nav_pvt,
    parse_nav_sat,
    parse_nav_status,
    parse_nav_timegps,
    parse_rxm_measx,
    parse_rxm_rawx,
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

# Record-only NAV/RXM arms: (class, id) → (parse, logical_id, vendor_name).
_UBX_RECORD_ARMS: dict[
    tuple[int, int],
    tuple[Callable[[bytes], dict[str, Any] | None], str, str],
] = {
    (CLS_NAV, ID_NAV_STATUS): (parse_nav_status, LOGICAL_STATUS, "NAV-STATUS"),
    (CLS_NAV, ID_NAV_POSECEF): (parse_nav_posecef, LOGICAL_POSECEF, "NAV-POSECEF"),
    (CLS_NAV, ID_NAV_TIMEGPS): (parse_nav_timegps, LOGICAL_TIME, "NAV-TIMEGPS"),
    (CLS_NAV, ID_NAV_CLOCK): (parse_nav_clock, LOGICAL_CLOCK, "NAV-CLOCK"),
    (CLS_NAV, ID_NAV_SAT): (parse_nav_sat, LOGICAL_SAT, "NAV-SAT"),
    (CLS_RXM, ID_RXM_MEASX): (parse_rxm_measx, LOGICAL_MEASX, "RXM-MEASX"),
    (CLS_RXM, ID_RXM_RAWX): (parse_rxm_rawx, LOGICAL_RAWX, "RXM-RAWX"),
}


def _series_from_model(model: str) -> str | None:
    lower = model.lower()
    for token in ("m10", "f10", "f9", "m9", "m8"):
        if token in lower:
            return token
    return None


@instrument_model(
    "gnss",
    "ublox-m8",
    "ublox",
    "ublox-m9",
    "ublox-m10",
    "ublox-f9",
    "ublox-f10",
)
class UbloxGnss(_BinaryGnss):
    """Shared u-blox driver; series share NMEA + UBX NAV-PVT / NAV-DOP."""

    def __init__(self, transport: Transport, config: dict[str, Any]) -> None:
        super().__init__(transport, config)
        self._parser = UbxStreamParser()
        self._nav: NavPvt | None = None
        self._series = _series_from_model(self._model)
        self._enable_messages()

    def _wire_suffix(self) -> str:
        return ".ubx"

    def _enable_messages(self) -> None:
        """Enable messages for the active profile (default if unset)."""
        profile = getattr(self, "_message_profile", "default") or "default"
        for name in expand_profile(profile, vendor="ublox"):
            try:
                msg_class, msg_id = resolve_message_id(name)
            except KeyError:
                _logger.warning("gnss model `%s` unknown profile message `%s`", self._model, name)
                continue
            self._write_bytes(cfg_msg_rate(msg_class, msg_id, 1))
            self._session_message_rates[name.upper()] = 1.0

    def _apply_message_profile(self, profile: str) -> None:
        self._message_profile = profile.strip().lower()
        self._enable_messages()

    def _is_m8_family(self) -> bool:
        series = (self._series or _series_from_model(self._model) or "").lower()
        return series == "m8"

    def _refine_series_from_mon_ver(self, body: bytes) -> None:
        series = parse_mon_ver_series(body)
        if series is None:
            if self._series is None:
                _logger.info(
                    "gnss model `%s` MON-VER did not identify series; using gen9 defaults",
                    self._model,
                )
            return
        self._series = series
        if self._model in {"ublox", "ublox-m8", "ublox-m9", "ublox-m10", "ublox-f9", "ublox-f10"}:
            refined = f"ublox-{series}"
            if refined != self._model:
                _logger.info(
                    "gnss model `%s` refined to `%s` from MON-VER",
                    self._model,
                    refined,
                )
                self._model = refined

    def _apply_events(self, events: list[tuple[str, object]]) -> None:
        for kind, payload in events:
            if kind == "nmea" and isinstance(payload, str):
                self._log_raw_line(payload)
                self._ingest_nmea_line(payload, record_raw=False, record_track=False)
            elif kind == "ubx" and isinstance(payload, tuple) and len(payload) == 3:
                msg_class, msg_id, body = payload
                self._log_raw_line(f"#UBX {msg_class:02X}{msg_id:02X} {body.hex()}")
                if isinstance(body, bytes):
                    self._handle_ubx(msg_class, msg_id, body)

    def _handle_ubx_nav_pvt(self, body: bytes) -> None:
        nav = parse_nav_pvt(body)
        if nav is None:
            return
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
        self._record_message_epoch(
            logical_id=LOGICAL_PVT,
            vendor_message="NAV-PVT",
            fields=nav_pvt_fields(nav),
        )

    def _handle_ubx_nav_dop(self, body: bytes) -> None:
        dop = parse_nav_dop(body)
        if dop is None:
            return
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
        self._record_message_epoch(
            logical_id=LOGICAL_DOP,
            vendor_message="NAV-DOP",
            fields=nav_dop_fields(dop),
        )

    def _handle_ubx(self, msg_class: int, msg_id: int, body: bytes) -> None:
        if msg_class == CLS_NAV and msg_id == ID_NAV_PVT:
            self._handle_ubx_nav_pvt(body)
            return
        if msg_class == CLS_NAV and msg_id == ID_NAV_DOP:
            self._handle_ubx_nav_dop(body)
            return
        arm = _UBX_RECORD_ARMS.get((msg_class, msg_id))
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
                "gnss save_config/load_config should not run while logging; call stop_logging first",
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
        resolved = self._resolve_config_path(path)
        frames, info = load_config_path(resolved)
        if not frames:
            raise EquipmentResponseError(f"no CFG messages found in {path}")
        if info is not None:
            mismatch_model = self._model if self._series is None else f"ublox-{self._series}"
            warning = detect_mismatch(mismatch_model, info)
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

    def _save_config_mon_ver(self) -> str | None:
        """Poll MON-VER, refine series, return u-center hex line if present."""
        mon_line: str | None = None
        self._write_bytes(mon_ver_poll())
        for msg_class, msg_id, body in self._collect_ubx(
            timeout_s=1.5,
            want_class=CLS_MON,
            want_id=ID_MON_VER,
            max_msgs=1,
        ):
            mon_line = ucenter_hex_line("MON-VER", msg_class, msg_id, body)
            self._refine_series_from_mon_ver(body)
            break
        return mon_line

    def _save_config_poll_legacy(self) -> list[tuple[str, int, int, bytes]]:
        entries: list[tuple[str, int, int, bytes]] = []
        for name, msg_class, msg_id, poll_payload in LEGACY_CFG_POLLS:
            self._write_bytes(build_ubx(msg_class, msg_id, poll_payload))
            for cls, mid, body in self._collect_ubx(
                timeout_s=1.0,
                want_class=CLS_CFG,
                want_id=msg_id,
                max_msgs=4,
            ):
                entries.append((name, cls, mid, body))
        return entries

    def _save_config_poll_valget(self) -> list[tuple[str, int, int, bytes]]:
        # Gen 9+: walk CFG-VALGET pages from RAM layer
        entries: list[tuple[str, int, int, bytes]] = []
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
            if len(batch) < 2 and len(batch[0][2]) < 8:
                # Likely last page
                break
        return entries

    def _save_config_write(
        self,
        out_path: Path,
        *,
        mon_line: str | None,
        entries: list[tuple[str, int, int, bytes]],
    ) -> Path:
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

    def save_config(self, path: str) -> Path:
        if self._logging_active():
            raise RuntimeError(
                "gnss save_config should not run while logging; call stop_logging first",
            )
        out_path = resolve_artifact_path(path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        mon_line = self._save_config_mon_ver()
        entries = self._save_config_poll_legacy() if self._is_m8_family() else self._save_config_poll_valget()
        return self._save_config_write(out_path, mon_line=mon_line, entries=entries)

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
