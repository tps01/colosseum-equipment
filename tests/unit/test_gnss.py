"""GNSS NMEA / u-blox UBX / Septentrio SBF drivers."""

from __future__ import annotations

import math
import struct
import time

import pytest
from colosseum_equipment.exceptions import EquipmentCapabilityError, EquipmentTimeoutError
from colosseum_equipment.instruments.factory import build_instrument
from colosseum_equipment.instruments.gnss.nmea import parse_gga, parse_gsv
from colosseum_equipment.instruments.gnss.novatel import NovatelGnss
from colosseum_equipment.instruments.gnss.oem7 import Oem7StreamParser, parse_bestpos
from colosseum_equipment.instruments.gnss.plots import (
    write_quality_plot,
    write_skyplot,
    write_track_plot,
)
from colosseum_equipment.instruments.gnss.sbf import (
    BLOCK_PVT_GEODETIC,
    build_sbf,
    parse_pvt_geodetic,
)
from colosseum_equipment.instruments.gnss.septentrio import SeptentrioGnss
from colosseum_equipment.instruments.gnss.ubx import (
    CLS_CFG,
    CLS_NAV,
    ID_CFG_RST,
    ID_NAV_PVT,
    build_ubx,
    cfg_rst_cold,
    parse_nav_pvt,
)
from colosseum_equipment.instruments.registry import registered_models


def _gga_line() -> str:
    # 37.7749 N, 122.4194 W — checksum computed for this payload
    body = "GPGGA,123519,3746.4940,N,12225.1640,W,1,08,0.9,10.0,M,0.0,M,,"
    checksum = 0
    for char in body:
        checksum ^= ord(char)
    return f"${body}*{checksum:02X}"


class _LineTransport:
    def __init__(self, lines: list[str]) -> None:
        self._lines = list(lines)
        self.written: list[str] = []

    def write(self, data: str) -> None:
        self.written.append(data)

    def read(self) -> str:
        if not self._lines:
            raise TimeoutError("no more lines")
        return self._lines.pop(0)

    def query(self, data: str) -> str:
        self.write(data)
        return self.read()

    def close(self) -> None:
        return None


class _ByteTransport:
    def __init__(self, chunks: list[bytes]) -> None:
        self._chunks = list(chunks)
        self.written_bytes: list[bytes] = []

    def write_bytes(self, payload: bytes) -> None:
        self.written_bytes.append(payload)

    def read_bytes(self, size: int = 256) -> bytes:
        if not self._chunks:
            return b""
        return self._chunks.pop(0)

    def write(self, data: str) -> None:
        self.write_bytes(data.encode("ascii"))

    def read(self) -> str:
        return ""

    def query(self, data: str) -> str:
        return ""

    def close(self) -> None:
        return None


def _nav_pvt_frame(*, lat_e7: int = 377749000, lon_e7: int = -1224194000) -> bytes:
    payload = bytearray(92)
    struct.pack_into("<I", payload, 0, 0)
    struct.pack_into("<HBBBBB", payload, 4, 2026, 10, 16, 12, 35, 19)
    payload[20] = 3  # 3D fix
    payload[21] = 0x01  # gnssFixOK
    payload[23] = 10
    struct.pack_into("<iiii", payload, 24, lon_e7, lat_e7, 0, 12500)
    struct.pack_into("<H", payload, 76, 90)  # pDOP = 0.90
    return build_ubx(CLS_NAV, ID_NAV_PVT, bytes(payload))


def test_parse_gga_fields() -> None:
    fix = parse_gga(_gga_line())
    assert fix is not None
    assert fix.fix_quality == 1
    assert fix.satellites == 8
    assert abs(fix.latitude - 37.7749) < 1e-4
    assert abs(fix.longitude + 122.4194) < 1e-4


def test_parse_nav_pvt_fields() -> None:
    frame = _nav_pvt_frame()
    # strip sync + header + checksum for payload-only helper via parser path
    length = frame[4] | (frame[5] << 8)
    payload = frame[6 : 6 + length]
    nav = parse_nav_pvt(payload)
    assert nav is not None
    assert nav.fix_ok
    assert abs(nav.latitude - 37.7749) < 1e-4
    assert nav.satellites == 10


def test_generic_gnss_reads_nmea_fix() -> None:
    transport = _LineTransport([_gga_line()])
    instrument = build_instrument("gnss", 1, {"model": "generic"}, transport)
    instrument.wait_for_fix(1.0)
    assert abs(instrument.measure_latitude() - 37.7749) < 1e-4


def test_ublox_aliases_registered() -> None:
    models = registered_models("gnss")
    assert {"ublox-m8", "ublox-m10", "ublox-f9", "ublox-f10", "generic"}.issubset(models)


def test_ublox_uses_nav_pvt() -> None:
    transport = _ByteTransport([_nav_pvt_frame()])
    instrument = build_instrument("gnss", 1, {"model": "ublox-m10"}, transport)
    instrument.wait_for_fix(1.0)
    assert abs(instrument.measure_latitude() - 37.7749) < 1e-4
    assert instrument.measure_satellites() == 10.0
    assert transport.written_bytes  # CFG-MSG enable


def test_generic_timeout_without_fix() -> None:
    transport = _LineTransport([])
    instrument = build_instrument("gnss", 1, {"model": "generic", "timeout": 0.05}, transport)
    with pytest.raises(EquipmentTimeoutError):
        instrument.wait_for_fix(0.05)


def _pvt_geodetic_frame(
    *,
    lat_deg: float = 37.7749,
    lon_deg: float = -122.4194,
    height_m: float = 12.5,
    mode_type: int = 1,
    nr_sv: int = 12,
) -> bytes:
    # Body layout matches Reference Guide / pysbf2 PVTGeodetic (4007).
    body = bytearray(80)
    struct.pack_into("<I", body, 0, 450_000)  # TOW ms
    struct.pack_into("<H", body, 4, 2300)  # WNc
    body[6] = mode_type & 0x0F
    body[7] = 0  # Error
    struct.pack_into("<ddd", body, 8, math.radians(lat_deg), math.radians(lon_deg), height_m)
    body[66] = nr_sv
    return build_sbf(BLOCK_PVT_GEODETIC, bytes(body))


def test_parse_pvt_geodetic_fields() -> None:
    frame = _pvt_geodetic_frame()
    length = frame[6] | (frame[7] << 8)
    payload = frame[8:length]
    pvt = parse_pvt_geodetic(payload)
    assert pvt is not None
    assert pvt.fix_quality == 1
    assert pvt.satellites == 12
    assert abs(pvt.latitude - 37.7749) < 1e-6
    assert abs(pvt.longitude + 122.4194) < 1e-6


def test_septentrio_aliases_registered() -> None:
    models = registered_models("gnss")
    assert {
        "septentrio-asterx-u3",
        "septentrio-asterx-m3",
        "septentrio-mosaic-x5",
        "septentrio-mosaic-h",
    }.issubset(models)
    transport = _ByteTransport([])
    instrument = build_instrument("gnss", 1, {"model": "septentrio-mosaic-x5"}, transport)
    assert isinstance(instrument, SeptentrioGnss)


def test_septentrio_uses_pvt_geodetic() -> None:
    reply = b"$R: setNMEAOutput,Stream1,COM1,GGA+RMC+GSV,sec1\n"
    reply2 = b"$R: setSBFOutput,Stream2,COM1,PVTGeodetic,sec1\n"
    transport = _ByteTransport([reply, reply2, _pvt_geodetic_frame()])
    instrument = build_instrument(
        "gnss",
        1,
        {"model": "septentrio-asterx-u3", "connection": "COM1"},
        transport,
    )
    instrument.wait_for_fix(1.0)
    assert abs(instrument.measure_latitude() - 37.7749) < 1e-4
    assert instrument.measure_satellites() == 12.0
    written = b"".join(transport.written_bytes).decode("ascii", errors="replace")
    assert "setNMEAOutput,Stream1,COM1,GGA+RMC+GSV,sec1" in written
    assert "setSBFOutput,Stream2,COM1,PVTGeodetic,sec1" in written


def test_septentrio_nmea_fallback() -> None:
    gga = (_gga_line() + "\n").encode("ascii")
    transport = _ByteTransport([b"$R?\n", b"$R?\n", gga])
    instrument = build_instrument("gnss", 1, {"model": "septentrio-asterx-u3"}, transport)
    instrument.wait_for_fix(1.0)
    assert abs(instrument.measure_latitude() - 37.7749) < 1e-4
    assert instrument.measure_satellites() == 8.0


def _gsv_line() -> str:
    body = "GPGSV,1,1,04,01,40,083,46,02,17,308,41,12,07,344,39,14,22,228,45"
    checksum = 0
    for char in body:
        checksum ^= ord(char)
    return f"${body}*{checksum:02X}"


def test_parse_gsv_fields() -> None:
    sats = parse_gsv(_gsv_line())
    assert len(sats) == 4
    assert sats[0] == (1, 40.0, 83.0, 46.0)


def test_generic_cold_start_unsupported() -> None:
    transport = _LineTransport([])
    instrument = build_instrument("gnss", 1, {"model": "generic"}, transport)
    with pytest.raises(EquipmentCapabilityError):
        instrument.cold_start()


def test_ublox_cold_start_writes_cfg_rst() -> None:
    transport = _ByteTransport([])
    instrument = build_instrument("gnss", 1, {"model": "ublox-m10"}, transport)
    transport.written_bytes.clear()
    instrument.cold_start()
    assert cfg_rst_cold() in transport.written_bytes
    assert transport.written_bytes[0][2:4] == bytes((CLS_CFG, ID_CFG_RST))


def test_septentrio_cold_start_writes_exe_reset() -> None:
    transport = _ByteTransport([b"$R:\n"])
    instrument = build_instrument("gnss", 1, {"model": "septentrio-asterx-u3"}, transport)
    transport.written_bytes.clear()
    instrument.cold_start()
    written = b"".join(transport.written_bytes).decode("ascii", errors="replace")
    assert "exeResetReceiver,Cold,none" in written


def test_start_logging_updates_fix(unit_runtime_context) -> None:
    _ = unit_runtime_context
    gga = (_gga_line() + "\n").encode("ascii")
    transport = _ByteTransport([gga])
    instrument = build_instrument("gnss", 1, {"model": "generic"}, transport)
    try:
        instrument.start_logging("gnss/session.nmea")
        instrument.wait_for_fix(2.0)
        assert abs(instrument.measure_latitude() - 37.7749) < 1e-4
    finally:
        instrument.stop_logging()
    assert instrument._raw_log_path is not None
    assert instrument._raw_log_path.is_file()
    assert instrument._track_csv_path is not None
    assert instrument._track_csv_path.is_file()
    assert instrument._track_samples


@pytest.mark.plot
def test_gnss_plot_writers(unit_runtime_context, tmp_path) -> None:
    _ = unit_runtime_context
    rows = [
        {
            "utc_iso": "2026-10-16T12:00:00Z",
            "latitude": 37.77,
            "longitude": -122.42,
            "altitude_m": 10.0,
            "fix_quality": 1.0,
            "satellites": 8.0,
            "hdop": 0.9,
        },
        {
            "utc_iso": "2026-10-16T12:00:01Z",
            "latitude": 37.771,
            "longitude": -122.421,
            "altitude_m": 11.0,
            "fix_quality": 1.0,
            "satellites": 9.0,
            "hdop": 0.8,
        },
    ]
    track = tmp_path / "track.png"
    quality = tmp_path / "quality.png"
    sky = tmp_path / "sky.png"
    write_track_plot(rows, track)
    write_quality_plot(rows, quality)
    write_skyplot({1: (40.0, 83.0, 46.0), 2: (17.0, 308.0, 41.0)}, sky)
    assert track.is_file() and track.stat().st_size > 0
    assert quality.is_file() and quality.stat().st_size > 0
    assert sky.is_file() and sky.stat().st_size > 0


_BESTPOSB_EXAMPLE = bytes(
    [
        0xAA,
        0x44,
        0x12,
        0x1C,
        0x2A,
        0x00,
        0x02,
        0x20,
        0x48,
        0x00,
        0x00,
        0x00,
        0x90,
        0xB4,
        0x93,
        0x05,
        0xB0,
        0xAB,
        0xB9,
        0x12,
        0x00,
        0x00,
        0x00,
        0x00,
        0x45,
        0x61,
        0xBC,
        0x0A,
        0x00,
        0x00,
        0x00,
        0x00,
        0x10,
        0x00,
        0x00,
        0x00,
        0x1B,
        0x04,
        0x50,
        0xB3,
        0xF2,
        0x8E,
        0x49,
        0x40,
        0x16,
        0xFA,
        0x6B,
        0xBE,
        0x7C,
        0x82,
        0x5C,
        0xC0,
        0x00,
        0x60,
        0x76,
        0x9F,
        0x44,
        0x9F,
        0x90,
        0x40,
        0xA6,
        0x2A,
        0x82,
        0xC1,
        0x3D,
        0x00,
        0x00,
        0x00,
        0x12,
        0x5A,
        0xCB,
        0x3F,
        0xCD,
        0x9E,
        0x98,
        0x3F,
        0xDB,
        0x66,
        0x40,
        0x40,
        0x00,
        0x30,
        0x30,
        0x30,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x0B,
        0x0B,
        0x00,
        0x00,
        0x00,
        0x06,
        0x00,
        0x03,
        0x42,
        0xDC,
        0x4C,
        0x48,
    ],
)


def test_parse_bestposb_example() -> None:
    events = Oem7StreamParser().feed(_BESTPOSB_EXAMPLE)
    assert events and events[0][0] == "oem7"
    _msg_id, body = events[0][1]
    best = parse_bestpos(body)
    assert best is not None
    assert best.fix_quality > 0
    assert abs(best.latitude - 51.11678) < 1e-4
    assert best.satellites == 11


def test_novatel_aliases_and_logs() -> None:
    models = registered_models("gnss")
    assert {
        "novatel-oem7",
        "novatel-oem7600",
        "novatel-pwrpak7",
        "novatel-smart7",
    }.issubset(models)
    transport = _ByteTransport([_BESTPOSB_EXAMPLE])
    instrument = build_instrument("gnss", 1, {"model": "novatel-pwrpak7"}, transport)
    assert isinstance(instrument, NovatelGnss)
    instrument.wait_for_fix(1.0)
    assert abs(instrument.measure_latitude() - 51.11678) < 1e-4
    written = b"".join(transport.written_bytes).decode("ascii", errors="replace")
    assert "LOG BESTPOSB ONTIME 1" in written
    assert "LOG GPGSV ONTIME 1" in written


def test_novatel_cold_start() -> None:
    transport = _ByteTransport([])
    instrument = build_instrument("gnss", 1, {"model": "novatel-oem7"}, transport)
    transport.written_bytes.clear()
    instrument.cold_start()
    assert b"FRESET COLDSTART\n" in transport.written_bytes


def test_save_plots_via_instrument(unit_runtime_context) -> None:
    _ = unit_runtime_context
    gga = (_gga_line() + "\n").encode("ascii")
    gsv = (_gsv_line() + "\n").encode("ascii")
    transport = _ByteTransport([gsv, gga])
    instrument = build_instrument("gnss", 1, {"model": "generic"}, transport)
    try:
        instrument.start_logging("gnss/run.nmea")
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline and not instrument._gsv:
            time.sleep(0.02)
        instrument.wait_for_fix(2.0)
        track = instrument.save_track_plot("gnss/track.png")
        sky = instrument.save_skyplot("gnss/sky.png")
        quality = instrument.save_quality_plot("gnss/quality.png")
    finally:
        instrument.stop_logging()
    assert track.is_file()
    assert sky.is_file()
    assert quality.is_file()
