"""u-blox M8 / M10 / F9 / F10 GNSS (NMEA + UBX NAV-PVT).

Manuals:
- u-blox M10 SPG 5.00 Interface Description (UBX-20053845)
- u-blox F10 TIM 3.01 Interface Description (UBX-23003447)
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from colosseum_equipment.exceptions import EquipmentTimeoutError
from colosseum_equipment.instruments.gnss.generic import GenericGnss
from colosseum_equipment.instruments.gnss.nmea import NmeaFix
from colosseum_equipment.instruments.gnss.ubx import (
    CLS_NAV,
    CLS_NMEA,
    ID_NAV_PVT,
    ID_NMEA_GSV,
    NavPvt,
    UbxStreamParser,
    cfg_msg_rate,
    cfg_rst_cold,
    parse_nav_pvt,
)
from colosseum_equipment.instruments.registry import instrument_model

if TYPE_CHECKING:
    from colosseum_equipment.transports.base import Transport


@instrument_model("gnss", "ublox-m8", "ublox-m10", "ublox-f9", "ublox-f10")
class UbloxGnss(GenericGnss):
    """Shared u-blox driver; series share NMEA + UBX NAV-PVT."""

    def __init__(self, transport: Transport, config: dict[str, Any]) -> None:
        super().__init__(transport, config)
        self._parser = UbxStreamParser()
        self._nav: NavPvt | None = None
        self._enable_messages()

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
        # Rate 1 on the current I/O port for NAV-PVT and NMEA GSV (CFG-MSG).
        self._write_bytes(cfg_msg_rate(CLS_NAV, ID_NAV_PVT, 1))
        self._write_bytes(cfg_msg_rate(CLS_NMEA, ID_NMEA_GSV, 1))

    def _apply_events(self, events: list[tuple[str, object]]) -> None:
        for kind, payload in events:
            if kind == "nmea" and isinstance(payload, str):
                self._log_raw_line(payload)
                # Track samples come from NAV-PVT; still ingest GGA/GSV/RMC state.
                self._ingest_nmea_line(payload, record_raw=False, record_track=False)
            elif kind == "ubx" and isinstance(payload, tuple) and len(payload) == 3:
                msg_class, msg_id, body = payload
                self._log_raw_line(f"#UBX {msg_class:02X}{msg_id:02X} {body.hex()}")
                if msg_class == CLS_NAV and msg_id == ID_NAV_PVT and isinstance(body, bytes):
                    nav = parse_nav_pvt(body)
                    if nav is not None:
                        self._nav = nav
                        fix = NmeaFix(
                            latitude=nav.latitude,
                            longitude=nav.longitude,
                            altitude_m=nav.altitude_m,
                            fix_quality=nav.fix_quality,
                            satellites=nav.satellites,
                            hdop=nav.hdop,
                            utc_time=nav.utc_time,
                        )
                        with self._state_lock:
                            self._fix = fix
                            self._utc_iso = nav.utc_time
                            if nav.fix_ok:
                                self._append_track_sample(fix)

    def _on_listener_chunk(self, data: bytes) -> None:
        self._apply_events(self._parser.feed(data))

    def _has_fix(self) -> bool:
        if self._nav is not None and self._nav.fix_ok:
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
        self._write_bytes(cfg_rst_cold())
        self._nav = None
        self._clear_nav_state()
