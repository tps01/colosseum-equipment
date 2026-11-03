"""GNSS plots, message profiles, and multi-row field/sat verifiers."""

from __future__ import annotations

from pathlib import Path

import pytest

from colosseum_equipment.instruments.gnss.messages import (
    LOGICAL_PVT,
    LOGICAL_SAT,
    expand_profile,
    resolve_logical_message,
)
from colosseum_equipment.instruments.gnss.plots import (
    read_track_csv,
    write_deviation_plot,
    write_signal_levels_plot,
    write_skyplot,
)
from colosseum_equipment.instruments.gnss.ubx import (
    CLS_NAV,
    ID_NAV_STATUS,
    parse_nav_status,
    parse_nav_sat,
    parse_rxm_rawx,
)


def test_resolve_logical_message_aliases() -> None:
    assert resolve_logical_message("UbloxNavPVT") == LOGICAL_PVT
    assert resolve_logical_message("NAV-PVT") == LOGICAL_PVT
    assert resolve_logical_message("gnss_pvt") == LOGICAL_PVT
    assert resolve_logical_message("UbloxNavSAT") == LOGICAL_SAT
    assert resolve_logical_message("BESTPOSB") == LOGICAL_PVT
    assert resolve_logical_message("PVTGeodetic") == LOGICAL_PVT
    assert resolve_logical_message("PSRDOPB") == "gnss_dop"
    assert resolve_logical_message("SatVisibility") == LOGICAL_SAT
    assert resolve_logical_message("RANGEB") == "gnss_rawx"


def test_expand_profile_ublox_all_contains_field_and_sat() -> None:
    names = expand_profile("all", vendor="ublox")
    assert "NAV-PVT" in names
    assert "NAV-STATUS" in names
    assert "NAV-SAT" in names
    assert "RXM-RAWX" in names


def test_expand_profile_novatel_and_septentrio() -> None:
    nov = expand_profile("field", vendor="novatel")
    assert "BESTPOSB" in nov
    assert "BESTXYZB" in nov
    assert "TIMEB" in nov
    assert "RXSTATUSB" in nov
    sat = expand_profile("sat", vendor="novatel")
    assert "SATVIS2B" in sat
    assert "RANGEB" in sat
    sep = expand_profile("all", vendor="septentrio")
    assert "PVTGeodetic" in sep
    assert "DOP" in sep
    assert "MeasEpoch" in sep
    assert "SatVisibility" in sep


def test_parse_nav_status_and_sat() -> None:
    status_payload = bytes(
        [
            0,
            0,
            0,
            0,  # iTOW
            3,  # gpsFix
            0x01,  # flags gpsFixOk
            0,
            0,
            0,
            0,
            0,
            0,  # ttff
            0,
            0,
            0,
            0,  # msss
        ],
    )
    status = parse_nav_status(status_payload)
    assert status is not None
    assert status["gpsFix"] == 3
    assert status["gpsFixOk"] == 1

    # Minimal NAV-SAT: header + one SV
    sat_payload = bytearray(8 + 12)
    sat_payload[5] = 1  # numSvs
    sat_payload[8] = 0  # gnssId GPS
    sat_payload[9] = 7  # svId
    sat_payload[10] = 40  # cno
    sat_payload[11] = 45  # elev
    sat = parse_nav_sat(bytes(sat_payload))
    assert sat is not None
    assert sat["num_svs"] == 1.0
    assert isinstance(sat["svs"], list) and sat["svs"][0]["svId"] == 7

    rawx = parse_rxm_rawx(bytes(16))
    assert rawx is not None
    assert "num_svs" in rawx


def test_read_track_csv_preserves_fields(tmp_path: Path) -> None:
    path = tmp_path / "track.csv"
    path.write_text(
        "host_ts_iso,receiver_utc_iso,fix_ok,fix_quality,latitude,longitude,"
        "altitude_m,sats_used,sats_visible,hdop,pdop,vdop,gdop,speed_m_s,"
        "course_deg,h_acc_m,v_acc_m,max_cn0_dbhz,data_age_s,stream_ok\n"
        "t,u,True,1,1.0,2.0,3,4,5,0.8,1.1,1.2,1.3,0,0,1.5,2.5,35,0.1,True\n",
        encoding="utf-8",
    )
    rows = read_track_csv(path)
    assert len(rows) == 1
    assert rows[0]["h_acc_m"] == 1.5
    assert rows[0]["sats_visible"] == 5.0


@pytest.mark.plot
def test_signal_and_deviation_plots(tmp_path: Path) -> None:
    snap = [
        {"prn": 1, "constellation": "GPS", "elev": 40, "az": 10, "cn0": 38, "used": True},
        {"prn": 2, "constellation": "GPS", "elev": 20, "az": 90, "cn0": 28, "used": False},
    ]
    signal_path = tmp_path / "signals.png"
    write_signal_levels_plot(snap, signal_path)
    assert signal_path.is_file() and signal_path.stat().st_size > 100

    sky_path = tmp_path / "sky.png"
    write_skyplot(snap, sky_path)
    assert sky_path.is_file()

    rows = [
        {"latitude": 40.0, "longitude": -105.0},
        {"latitude": 40.00001, "longitude": -105.00001},
        {"latitude": 40.00002, "longitude": -104.99999},
    ]
    dev_path = tmp_path / "dev.png"
    stats = write_deviation_plot(rows, dev_path)
    assert dev_path.is_file()
    assert stats["n"] == 3.0
    assert stats["cep50_m"] >= 0.0


def test_verify_field_avg_and_sat_delta(unit_runtime_context) -> None:
    from colosseum.context import get_context
    from colosseum.database import MeasurementRow
    from colosseum_equipment.api import gnss as gnss_api

    _ = unit_runtime_context
    db = get_context().db
    for idx, hacc in enumerate((1000.0, 2000.0, 3000.0)):
        db.enqueue_measurement(
            MeasurementRow(
                domain="equipment",
                command=LOGICAL_PVT,
                key="open",
                row_index=idx,
                value={"hAcc": hacc, "vendor_message": "NAV-PVT"},
            ),
        )
    for idx, hacc in enumerate((4000.0, 5000.0)):
        db.enqueue_measurement(
            MeasurementRow(
                domain="equipment",
                command=LOGICAL_PVT,
                key="tunnel",
                row_index=idx,
                value={"hAcc": hacc, "vendor_message": "NAV-PVT"},
            ),
        )
    db.drain()

    ok = gnss_api.verify_field_avg(key="open", message="UbloxNavPVT", field="hAcc", maximum=2500.0)
    assert ok.status == "PASS"
    delta = gnss_api.verify_field_avg_delta(
        key_a="open",
        key_b="tunnel",
        message="NAV-PVT",
        field="hAcc",
        minimum=1000.0,
    )
    assert delta.status == "PASS"

    for idx, nsv in enumerate((10.0, 12.0)):
        db.enqueue_measurement(
            MeasurementRow(
                domain="equipment",
                command=LOGICAL_SAT,
                key="open",
                row_index=idx,
                value={"num_svs": nsv, "vendor_message": "NAV-SAT"},
            ),
        )
    for idx, nsv in enumerate((4.0, 6.0)):
        db.enqueue_measurement(
            MeasurementRow(
                domain="equipment",
                command=LOGICAL_SAT,
                key="tunnel",
                row_index=idx,
                value={"num_svs": nsv, "vendor_message": "NAV-SAT"},
            ),
        )
    db.drain()
    sat = gnss_api.verify_sat_avg_delta(
        key_a="open",
        key_b="tunnel",
        message="UbloxNavSAT",
        maximum=8.0,
    )
    assert sat.status == "PASS"

    status_ok = gnss_api.verify_field_equal_percent(
        key="open",
        message="UbloxNavPVT",
        field="hAcc",
        expected_val=2000.0,
        tolerance=1500.0,
        minimum=50.0,
    )
    assert status_ok.status == "PASS"


def test_ublox_message_profile_writes_cfg(unit_runtime_context) -> None:
    from colosseum_equipment.instruments.factory import build_instrument

    _ = unit_runtime_context

    class _Transport:
        def __init__(self) -> None:
            self.written: list[bytes] = []

        def write_bytes(self, data: bytes) -> None:
            self.written.append(data)

        def read_bytes(self, size: int = 256) -> bytes:
            return b""

        def close(self) -> None:
            return None

    transport = _Transport()
    instrument = build_instrument("gnss", 1, {"model": "ublox-m9"}, transport)
    before = len(transport.written)
    instrument.set_message_profile("field")
    assert len(transport.written) > before
    from colosseum_equipment.instruments.gnss.ubx import cfg_msg_rate

    assert cfg_msg_rate(CLS_NAV, ID_NAV_STATUS, 1) in transport.written
