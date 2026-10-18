"""Fabricate a thorough example execution.sqlite showcasing deep instrument APIs."""

from __future__ import annotations

import json
import math
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Allow running without install when invoked from repo root.
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "colosseum-core"))

from colosseum.database.schema import SCHEMA_SQL  # noqa: E402

OUT_DIR = (
    Path(__file__).resolve().parents[3]
    / "workshop_examples"
    / "deep_instrument_apis_demo"
    / "2026-10-18_112400_indoor_repeater_soak-pass"
)
# Prefer colocated under workshop if workshop_examples isn't intended —
# use pay_attention-style path under colosseum-equipment/examples/outputs
OUT_DIR = (
    Path(__file__).resolve().parents[1]
    / "examples"
    / "outputs"
    / "2026-10-18_112400_deep_instrument_apis_demo-pass"
)


def _ts(base: datetime, offset_s: float) -> str:
    return (base + timedelta(seconds=offset_s)).isoformat().replace("+00:00", "Z")


def insert_meas(
    cur: sqlite3.Cursor,
    *,
    domain: str,
    command: str,
    key: str,
    value,
    row_index: int = 0,
    units: str | None = None,
    artifact_path: str | None = None,
    status: str = "PASS",
    timestamp: str,
) -> None:
    cur.execute(
        """
        INSERT INTO measurements
        (domain, command, key, row_index, value_json, units, artifact_path, status, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            domain,
            command,
            key,
            row_index,
            json.dumps(value),
            units,
            artifact_path,
            status,
            timestamp,
        ),
    )


def insert_cmd(
    cur: sqlite3.Cursor,
    *,
    domain: str,
    command: str,
    key: str,
    result,
    status: str = "PASS",
    optional: bool = False,
    message: str = "",
    cause: str = "",
    timestamp: str,
) -> None:
    cur.execute(
        """
        INSERT INTO commands
        (domain, command, key, result_json, status, optional, message, cause, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            domain,
            command,
            key,
            json.dumps(result),
            status,
            1 if optional else 0,
            message,
            cause,
            timestamp,
        ),
    )


def insert_verify(
    cur: sqlite3.Cursor,
    *,
    domain: str,
    command: str,
    key: str,
    expected,
    actual,
    tolerance=None,
    compare_op: str = "within",
    status: str = "PASS",
    optional: bool = False,
    message: str = "",
    step_name: str = "",
    timestamp: str,
) -> None:
    cur.execute(
        """
        INSERT INTO verifications
        (domain, command, key, expected_json, actual_json, tolerance_json, compare_op,
         status, optional, message, step_name, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            domain,
            command,
            key,
            json.dumps(expected),
            json.dumps(actual),
            json.dumps(tolerance),
            compare_op,
            status,
            1 if optional else 0,
            message,
            step_name,
            timestamp,
        ),
    )


def insert_event(
    cur: sqlite3.Cursor,
    *,
    level: str,
    message: str,
    timestamp: str,
    source: str = "demo",
) -> None:
    cur.execute(
        "INSERT INTO events (level, source, message, timestamp) VALUES (?, ?, ?, ?)",
        (level, source, message, timestamp),
    )


def fabricate_gnss_epochs(cur: sqlite3.Cursor, base: datetime) -> None:
    """Indoor repeater soak: lock → dropout → reacquire → stable."""
    key = "repeater_soak"
    insert_cmd(
        cur,
        domain="equipment",
        command="start_logging",
        key=key,
        result={"path": "gnss/raw.nmea", "key": key},
        timestamp=_ts(base, 0),
    )
    insert_meas(
        cur,
        domain="equipment",
        command="log_artifacts",
        key=f"{key}.files",
        value={"raw": "gnss/raw.nmea", "track_csv": "gnss/raw_track.csv"},
        artifact_path="gnss/raw_track.csv",
        timestamp=_ts(base, 0.1),
    )

    # Scenario timeline (seconds):
    # 0-5: acquiring (nofix, sats visible, rising C/N0)
    # 5-20: locked 3D
    # 20-28: RF dropout (nofix, stream still ok then weak)
    # 28-60: reacquired and stable
    for i in range(60):
        t = float(i)
        host = _ts(base, 1.0 + t)
        if t < 5:
            fix_ok = False
            fq = 0
            lat = lon = alt = ""
            sats_used = 0
            sats_vis = 4 + i
            hdop = pdop = vdop = gdop = 99.0
            max_cn0 = 18.0 + i * 2.5
            stream_ok = True
            speed = course = ""
            h_acc = v_acc = ""
        elif t < 20:
            fix_ok = True
            fq = 1
            # small wander around SF
            lat = 37.7749 + 1e-6 * math.sin(t / 3)
            lon = -122.4194 + 1e-6 * math.cos(t / 3)
            alt = 12.4 + 0.05 * math.sin(t)
            sats_used = 10 + (i % 3)
            sats_vis = 14 + (i % 2)
            hdop = 0.85 + 0.05 * math.sin(t)
            pdop = 1.4 + 0.08 * math.cos(t)
            vdop = 1.1
            gdop = 1.9
            max_cn0 = 42.0 + (i % 5)
            stream_ok = True
            speed = 0.05
            course = 270.0
            h_acc = 1.8
            v_acc = 3.2
        elif t < 28:
            fix_ok = False
            fq = 0
            lat = lon = alt = ""
            sats_used = 0
            sats_vis = max(0, 8 - (i - 20))
            hdop = pdop = vdop = gdop = 99.0
            max_cn0 = max(0.0, 28.0 - (t - 20) * 3)
            stream_ok = t < 25  # brief stream loss mid-outage
            speed = course = ""
            h_acc = v_acc = ""
        else:
            fix_ok = True
            fq = 1
            lat = 37.77491 + 5e-7 * math.sin(t / 4)
            lon = -122.41941
            alt = 12.5
            sats_used = 11
            sats_vis = 16
            hdop = 0.9
            pdop = 1.5
            vdop = 1.15
            gdop = 2.0
            max_cn0 = 44.0
            stream_ok = True
            speed = 0.02
            course = 265.0
            h_acc = 1.5
            v_acc = 2.8

        epoch = {
            "host_ts_iso": host,
            "receiver_utc_iso": host.replace("2026-10-18T15:", "2026-10-18T15:").replace("Z", ""),
            "fix_ok": fix_ok,
            "fix_quality": float(fq),
            "latitude": lat,
            "longitude": lon,
            "altitude_m": alt,
            "sats_used": float(sats_used),
            "sats_visible": float(sats_vis),
            "hdop": float(hdop),
            "pdop": float(pdop),
            "vdop": float(vdop),
            "gdop": float(gdop),
            "speed_m_s": speed,
            "course_deg": course,
            "h_acc_m": h_acc,
            "v_acc_m": v_acc,
            "max_cn0_dbhz": float(max_cn0),
            "data_age_s": 0.2 if stream_ok else 4.5,
            "stream_ok": stream_ok,
            "gnss_id": 1,
            "model": "ublox-m10",
            "logging_window_key": key,
        }
        # nicer receiver utc
        epoch["receiver_utc_iso"] = host
        insert_meas(
            cur,
            domain="equipment",
            command="track_epoch",
            key=key,
            value=epoch,
            row_index=i,
            timestamp=host,
        )

    # Point measures during soak
    insert_meas(
        cur,
        domain="equipment",
        command="measure_max_cn0_dbhz",
        key="repeater_rf_presence",
        value=44.0,
        units="dB-Hz",
        timestamp=_ts(base, 35),
    )
    insert_meas(
        cur,
        domain="equipment",
        command="measure_satellites_visible",
        key="repeater_sats_vis",
        value=16.0,
        timestamp=_ts(base, 35.1),
    )
    insert_meas(
        cur,
        domain="equipment",
        command="measure_hdop",
        key="repeater_hdop",
        value=0.9,
        timestamp=_ts(base, 35.2),
    )
    insert_meas(
        cur,
        domain="equipment",
        command="measure_pdop",
        key="repeater_pdop",
        value=1.5,
        timestamp=_ts(base, 35.3),
    )
    insert_meas(
        cur,
        domain="equipment",
        command="measure_vdop",
        key="repeater_vdop",
        value=1.15,
        timestamp=_ts(base, 35.4),
    )
    insert_meas(
        cur,
        domain="equipment",
        command="measure_gdop",
        key="repeater_gdop",
        value=2.0,
        timestamp=_ts(base, 35.5),
    )
    insert_meas(
        cur,
        domain="equipment",
        command="measure_h_acc_m",
        key="repeater_h_acc",
        value=1.5,
        units="m",
        timestamp=_ts(base, 35.6),
    )
    insert_meas(
        cur,
        domain="equipment",
        command="measure_ttff_s",
        key="repeater_ttff",
        value=5.1,
        units="s",
        timestamp=_ts(base, 61),
    )
    insert_meas(
        cur,
        domain="equipment",
        command="get_fix_type",
        key="repeater_fix_type",
        value="3d",
        timestamp=_ts(base, 35.7),
    )
    insert_meas(
        cur,
        domain="equipment",
        command="get_constellations_present",
        key="repeater_consts",
        value=["GPS", "GLONASS", "Galileo"],
        timestamp=_ts(base, 35.8),
    )
    insert_meas(
        cur,
        domain="equipment",
        command="get_satellite_snapshot",
        key="repeater_sky",
        value=[
            {
                "prn": 1,
                "constellation": "GPS",
                "signal_id": "L1CA",
                "elev": 55.0,
                "az": 120.0,
                "cn0": 44.0,
                "used": True,
                "age_s": 0.3,
            },
            {
                "prn": 7,
                "constellation": "GPS",
                "signal_id": "L1CA",
                "elev": 22.0,
                "az": 310.0,
                "cn0": 38.0,
                "used": True,
                "age_s": 0.3,
            },
            {
                "prn": 12,
                "constellation": "GLONASS",
                "signal_id": "G1",
                "elev": 40.0,
                "az": 80.0,
                "cn0": 41.0,
                "used": True,
                "age_s": 0.4,
            },
            {
                "prn": 3,
                "constellation": "Galileo",
                "signal_id": "E1B",
                "elev": 15.0,
                "az": 200.0,
                "cn0": 32.0,
                "used": False,
                "age_s": 0.5,
            },
        ],
        timestamp=_ts(base, 35.9),
    )

    # Continuity summaries at stop
    insert_cmd(
        cur,
        domain="equipment",
        command="stop_logging",
        key=key,
        result=None,
        timestamp=_ts(base, 62),
    )
    insert_meas(
        cur,
        domain="equipment",
        command="fix_availability",
        key=f"{key}.fix_availability",
        value=(47 / 60),  # ~0.783
        timestamp=_ts(base, 62.1),
    )
    insert_meas(
        cur,
        domain="equipment",
        command="longest_outage_s",
        key=f"{key}.longest_outage_s",
        value=8.0,
        units="s",
        timestamp=_ts(base, 62.2),
    )
    insert_meas(
        cur,
        domain="equipment",
        command="reacquisition_s",
        key=f"{key}.reacquisition_s",
        value=8.0,
        units="s",
        timestamp=_ts(base, 62.3),
    )
    insert_meas(
        cur,
        domain="equipment",
        command="epochs_total",
        key=f"{key}.epochs_total",
        value=60.0,
        timestamp=_ts(base, 62.4),
    )
    insert_meas(
        cur,
        domain="equipment",
        command="epochs_nofix",
        key=f"{key}.epochs_nofix",
        value=13.0,
        timestamp=_ts(base, 62.5),
    )

    for cmd, path in (
        ("save_track_plot", "gnss/track.png"),
        ("save_skyplot", "gnss/sky.png"),
        ("save_quality_plot", "gnss/quality.png"),
    ):
        insert_meas(
            cur,
            domain="equipment",
            command=cmd,
            key=f"{key}.{cmd.replace('save_', '')}",
            value={"path": path},
            artifact_path=path,
            timestamp=_ts(base, 63),
        )

    insert_verify(
        cur,
        domain="equipment",
        command="verify_fix_availability",
        key=f"{key}.fix_availability",
        expected=0.7,
        actual=47 / 60,
        tolerance=None,
        compare_op=">=",
        status="PASS",
        step_name="soak_continuity",
        timestamp=_ts(base, 63.5),
    )
    insert_verify(
        cur,
        domain="equipment",
        command="verify_longest_outage_s",
        key=f"{key}.longest_outage_s",
        expected=15.0,
        actual=8.0,
        tolerance=None,
        compare_op="<=",
        status="PASS",
        step_name="soak_continuity",
        timestamp=_ts(base, 63.6),
    )
    insert_verify(
        cur,
        domain="equipment",
        command="verify_max_cn0_dbhz",
        key="repeater_rf_presence",
        expected=35.0,
        actual=44.0,
        compare_op=">=",
        status="PASS",
        step_name="rf_presence",
        timestamp=_ts(base, 63.7),
    )
    insert_verify(
        cur,
        domain="equipment",
        command="verify_hdop",
        key="repeater_hdop",
        expected=2.0,
        actual=0.9,
        compare_op="<=",
        status="PASS",
        step_name="geometry",
        timestamp=_ts(base, 63.8),
    )


def fabricate_oscope(cur: sqlite3.Cursor, base: datetime) -> None:
    t0 = 100.0
    capture_id = "a1b2c3d4e5f6"
    insert_cmd(
        cur,
        domain="equipment",
        command="preset",
        key="oscope1",
        result=None,
        timestamp=_ts(base, t0),
    )
    for cmd, result in (
        ("set_channel_display", {"channel": 1, "enabled": True}),
        ("set_channel_scale_v", {"channel": 1, "volts_per_div": 0.5}),
        ("set_channel_coupling", {"channel": 1, "coupling": "DC"}),
        ("set_channel_impedance", {"channel": 1, "ohms": 1e6}),
        ("set_timebase_scale", {"seconds_per_div": 1e-6}),
        ("set_trigger_mode", {"mode": "normal"}),
        ("set_trigger_source", {"source": "CH1"}),
        ("set_trigger_level_v", {"level_v": 0.0}),
        ("set_trigger_slope", {"slope": "rising"}),
        ("set_acquire_mode", {"mode": "sample"}),
    ):
        insert_cmd(
            cur,
            domain="equipment",
            command=cmd,
            key="oscope1",
            result=result,
            timestamp=_ts(base, t0 + 0.1),
        )
    insert_cmd(
        cur,
        domain="equipment",
        command="acquire",
        key="oscope1",
        result=capture_id,
        timestamp=_ts(base, t0 + 1),
    )
    for cmd, val, units in (
        ("measure_vpp", 3.28, "V"),
        ("measure_vmax", 1.65, "V"),
        ("measure_vmin", -1.63, "V"),
        ("measure_vrms", 1.16, "V"),
        ("measure_frequency_hz", 1_000_012.0, "Hz"),
        ("measure_period_s", 9.99988e-7, "s"),
        ("measure_rise_time_s", 12.4e-9, "s"),
        ("measure_fall_time_s", 13.1e-9, "s"),
        ("get_record_length", 10000.0, None),
        ("get_channel_scale_v", 0.5, "V/div"),
    ):
        insert_meas(
            cur,
            domain="equipment",
            command=cmd,
            key=f"scope_{cmd}",
            value=val,
            units=units,
            timestamp=_ts(base, t0 + 1.2),
        )
    insert_meas(
        cur,
        domain="equipment",
        command="get_acquire_state",
        key="scope_acq_state",
        value="STOP",
        timestamp=_ts(base, t0 + 1.3),
    )
    wave_meta = {
        "channel": 1,
        "points": 10000,
        "points_expected": 10000,
        "xinc_s": 1e-10,
        "xorigin_s": -5e-7,
        "ymult_v": 0.0008,
        "vertical_units": "V",
        "encoding": "RIBinary",
        "capture_id": capture_id,
    }
    insert_meas(
        cur,
        domain="equipment",
        command="save_waveform",
        key=f"oscope_wave_ch1_{capture_id}",
        value=wave_meta,
        artifact_path="oscope/ch1_waveform.csv",
        timestamp=_ts(base, t0 + 1.5),
    )
    insert_meas(
        cur,
        domain="equipment",
        command="save_screenshot",
        key=f"oscope_screenshot_{capture_id}",
        value={"capture_id": capture_id, "bytes": 48211},
        artifact_path="oscope/screen.png",
        timestamp=_ts(base, t0 + 1.6),
    )
    insert_verify(
        cur,
        domain="equipment",
        command="verify_vpp",
        key="scope_measure_vpp",
        expected=3.3,
        actual=3.28,
        tolerance=0.15,
        status="PASS",
        step_name="scope_capture",
        timestamp=_ts(base, t0 + 1.7),
    )


def fabricate_power_bench(cur: sqlite3.Cursor, base: datetime) -> None:
    t0 = 200.0
    # PSU
    for cmd, result in (
        ("set_voltage", {"channel": 1, "voltage": 5.0}),
        ("set_current_limit", {"channel": 1, "current": 0.5}),
        ("set_ovp_v", {"channel": 1, "voltage": 5.5}),
        ("set_ocp_a", {"channel": 1, "current": 0.6}),
        ("toggle_ovp", {"channel": 1, "enabled": True}),
        ("set_remote_sense", {"channel": 1, "enabled": True}),
        ("set_output", {"channel": 1, "enabled": True}),
    ):
        insert_cmd(
            cur,
            domain="equipment",
            command=cmd,
            key="psu1",
            result=result,
            timestamp=_ts(base, t0),
        )
    for cmd, val, units in (
        ("measure_voltage", 4.998, "V"),
        ("measure_current", 0.214, "A"),
        ("measure_power_w", 1.07, "W"),
        ("measure_output_state", 1.0, None),
        ("get_regulation_mode", "cv", None),
        ("get_voltage", 5.0, "V"),
        ("get_ovp_v", 5.5, "V"),
        ("get_fault_status", "NONE", None),
    ):
        insert_meas(
            cur,
            domain="equipment",
            command=cmd,
            key=f"dut_rail_{cmd}",
            value=val,
            units=units,
            timestamp=_ts(base, t0 + 1),
        )
    insert_verify(
        cur,
        domain="equipment",
        command="verify_voltage",
        key="dut_rail_measure_voltage",
        expected=5.0,
        actual=4.998,
        tolerance=0.05,
        status="PASS",
        step_name="psu_rail",
        timestamp=_ts(base, t0 + 1.2),
    )

    # Eload
    for cmd, result in (
        ("set_mode", {"mode": "CC", "channel": 1}),
        ("set_current", {"current": 0.2, "channel": 1}),
        ("set_transient_mode", {"mode": "pulse", "channel": 1}),
        ("set_transient_level_a", {"level_a": 0.4, "channel": 1}),
        ("set_transient_timer_s", {"timer_s": 0.001, "channel": 1}),
        ("engage", {"channel": 1}),
    ):
        insert_cmd(
            cur,
            domain="equipment",
            command=cmd,
            key="eload1",
            result=result,
            timestamp=_ts(base, t0 + 2),
        )
    for cmd, val, units in (
        ("measure_voltage", 4.95, "V"),
        ("measure_current", 0.201, "A"),
        ("measure_power_w", 0.995, "W"),
        ("measure_resistance_ohm", 24.6, "ohm"),
        ("measure_input_state", 1.0, None),
    ):
        insert_meas(
            cur,
            domain="equipment",
            command=cmd,
            key=f"load_{cmd}",
            value=val,
            units=units,
            timestamp=_ts(base, t0 + 3),
        )

    # DMM configure → initiate → fetch + one-shots
    for cmd, result in (
        ("set_function", {"function": "VOLT:DC"}),
        ("set_nplc", {"nplc": 10}),
        ("set_auto_range", {"enabled": True}),
        ("set_auto_zero", {"enabled": True}),
        ("initiate", {}),
    ):
        insert_cmd(
            cur,
            domain="equipment",
            command=cmd,
            key="dmm1",
            result=result,
            timestamp=_ts(base, t0 + 4),
        )
    insert_meas(
        cur,
        domain="equipment",
        command="fetch",
        key="dmm_fetch_vdc",
        value=4.9972,
        units="V",
        timestamp=_ts(base, t0 + 5),
    )
    for cmd, val, units in (
        ("measure_voltage_dc", 4.9971, "V"),
        ("measure_voltage_ac", 0.002, "V"),
        ("measure_current_dc", 0.00012, "A"),
        ("measure_resistance", 10002.4, "ohm"),
        ("measure_resistance_4w", 10001.1, "ohm"),
        ("measure_frequency_hz", 59.99, "Hz"),
    ):
        insert_meas(
            cur,
            domain="equipment",
            command=cmd,
            key=f"dmm_{cmd}",
            value=val,
            units=units,
            timestamp=_ts(base, t0 + 6),
        )


def fabricate_stimulus(cur: sqlite3.Cursor, base: datetime) -> None:
    t0 = 300.0
    for cmd, result in (
        ("set_waveform", {"channel": 1, "waveform": "sine"}),
        ("set_frequency", {"channel": 1, "frequency_hz": 1e6}),
        ("set_amplitude_vpp", {"channel": 1, "vpp": 1.0}),
        ("set_offset_v", {"channel": 1, "offset_v": 0.0}),
        ("set_load_ohms", {"channel": 1, "ohms": 50.0}),
        ("set_output", {"channel": 1, "enabled": True}),
    ):
        insert_cmd(
            cur,
            domain="equipment",
            command=cmd,
            key="asg1",
            result=result,
            timestamp=_ts(base, t0),
        )
    insert_meas(
        cur,
        domain="equipment",
        command="get_load_ohms",
        key="asg_load",
        value=50.0,
        units="ohm",
        timestamp=_ts(base, t0 + 0.5),
    )

    for cmd, result in (
        ("set_gate_time", {"gate_s": 0.1}),
        ("set_coupling", {"channel": 1, "coupling": "AC"}),
        ("set_impedance", {"channel": 1, "ohms": 50.0}),
        ("set_trigger_level_v", {"channel": 1, "level_v": 0.1}),
    ):
        insert_cmd(
            cur,
            domain="equipment",
            command=cmd,
            key="fc1",
            result=result,
            timestamp=_ts(base, t0 + 1),
        )
    for cmd, val, units in (
        ("measure_frequency", 1_000_003.2, "Hz"),
        ("measure_period", 9.999968e-7, "s"),
        ("measure_duty_cycle_pct", 49.8, "%"),
        ("measure_frequency_mean_hz", 1_000_002.8, "Hz"),
        ("measure_frequency_stdev_hz", 0.4, "Hz"),
    ):
        insert_meas(
            cur,
            domain="equipment",
            command=cmd,
            key=f"fc_{cmd}",
            value=val,
            units=units,
            timestamp=_ts(base, t0 + 2),
        )

    for cmd, result in (
        ("set_frequency", {"frequency_hz": 2.4e9, "channel": 1}),
        ("set_averaging_count", {"count": 16, "channel": 1}),
        ("set_offset_db", {"offset_db": -1.5, "channel": 1}),
        ("zero_sensor", {"channel": 1}),
    ):
        insert_cmd(
            cur,
            domain="equipment",
            command=cmd,
            key="pm1",
            result=result,
            timestamp=_ts(base, t0 + 3),
        )
    for cmd, val, units in (
        ("measure_power_dbm", -12.35, "dBm"),
        ("measure_power", -12.35, "dBm"),
        ("measure_power_w", 5.82e-5, "W"),
        ("measure_power_peak_dbm", -11.9, "dBm"),
        ("measure_power_avg_dbm", -12.4, "dBm"),
    ):
        insert_meas(
            cur,
            domain="equipment",
            command=cmd,
            key=f"pm_{cmd}",
            value=val,
            units=units,
            timestamp=_ts(base, t0 + 4),
        )
    insert_verify(
        cur,
        domain="equipment",
        command="verify_power_dbm",
        key="pm_measure_power_dbm",
        expected=-12.0,
        actual=-12.35,
        tolerance=1.0,
        status="PASS",
        step_name="tx_power",
        timestamp=_ts(base, t0 + 4.5),
    )


def fabricate_rf(cur: sqlite3.Cursor, base: datetime) -> None:
    t0 = 400.0
    # SpecA
    for cmd, result in (
        ("set_center_frequency", {"hz": 2.4e9}),
        ("set_span", {"hz": 20e6}),
        ("set_rbw", {"hz": 100e3}),
        ("set_attenuation_db", {"db": 10}),
        ("set_auto_attenuation", {"enabled": False}),
        ("toggle_preamp", {"enabled": False}),
        ("set_averaging_count", {"count": 10}),
        ("set_average_type", {"avg_type": "RMS"}),
        ("arm_sweep", {}),
        ("wait_complete", {"timeout_s": 5}),
    ):
        insert_cmd(
            cur,
            domain="equipment",
            command=cmd,
            key="sa1",
            result=result,
            timestamp=_ts(base, t0),
        )
    for cmd, val, units in (
        ("measure_peak_amplitude_dbm", -18.2, "dBm"),
        ("measure_peak_frequency_hz", 2.400012e9, "Hz"),
        ("measure_channel_power_dbm", -15.1, "dBm"),
        ("measure_acpr_db", -42.5, "dB"),
        ("measure_obw_hz", 1.8e6, "Hz"),
        ("measure_bw", 1.75e6, "Hz"),
    ):
        insert_meas(
            cur,
            domain="equipment",
            command=cmd,
            key=f"sa_{cmd}",
            value=val,
            units=units,
            timestamp=_ts(base, t0 + 2),
        )
    insert_meas(
        cur,
        domain="equipment",
        command="save_trace_data",
        key="sa_trace_wifi",
        value={
            "center_hz": 2.4e9,
            "span_hz": 20e6,
            "points": 1001,
            "rbw_hz": 100e3,
            "attenuation_db": 10,
            "averages": 10,
        },
        artifact_path="speca/wifi_trace.csv",
        timestamp=_ts(base, t0 + 2.5),
    )

    # RTSA
    insert_cmd(
        cur,
        domain="equipment",
        command="acquire",
        key="rtsa1",
        result={"timeout_s": 10},
        timestamp=_ts(base, t0 + 10),
    )
    insert_meas(
        cur,
        domain="equipment",
        command="save_IQ_data",
        key="rtsa_iq_burst",
        value={"samples": 262144, "fs_hz": 56e6, "center_hz": 2.4e9},
        artifact_path="rtsa/burst.iq.tar",
        timestamp=_ts(base, t0 + 11),
    )
    insert_meas(
        cur,
        domain="equipment",
        command="save_spectrum_trace_data",
        key="rtsa_spectrum",
        value={"points": 801, "span_hz": 40e6},
        artifact_path="rtsa/spectrum.csv",
        timestamp=_ts(base, t0 + 11.5),
    )

    # VNA
    for cmd, result in (
        ("set_frequency_start", {"hz": 1e9}),
        ("set_frequency_stop", {"hz": 6e9}),
        ("set_points", {"points": 401}),
        ("set_if_bandwidth", {"hz": 1e3}),
        ("set_averaging_count", {"count": 4}),
        ("toggle_averaging", {"enabled": True}),
        ("single_sweep", {}),
        ("wait_complete", {}),
    ):
        insert_cmd(
            cur,
            domain="equipment",
            command=cmd,
            key="vna1",
            result=result,
            timestamp=_ts(base, t0 + 20),
        )
    for cmd, val in (
        ("measure_s11_magnitude", -22.4),
        ("measure_s21_magnitude", -1.85),
        ("measure_s_parameter", {"parameter": "S21", "mag_db": -1.85, "phase_deg": -34.2}),
    ):
        insert_meas(
            cur,
            domain="equipment",
            command=cmd,
            key=f"vna_{cmd}",
            value=val,
            units="dB" if isinstance(val, float) else None,
            timestamp=_ts(base, t0 + 22),
        )
    insert_meas(
        cur,
        domain="equipment",
        command="save_trace_data",
        key="vna_s2p",
        value={
            "format": "s2p",
            "cal_state": "ON",
            "cal_set": "CALSET_1",
            "if_bw_hz": 1000,
            "points": 401,
            "sweep_type": "LIN",
            "freq_start_hz": 1e9,
            "freq_stop_hz": 6e9,
            "source_power_dbm": -10,
        },
        artifact_path="vna/dut.s2p",
        timestamp=_ts(base, t0 + 23),
    )

    # VSG
    for cmd, result in (
        ("set_frequency", {"hz": 2.4e9}),
        ("set_power", {"dbm": -10}),
        ("set_ref_source", {"source": "EXT"}),
        ("set_arb_sample_clock", {"hz": 100e6}),
        ("set_arb_trigger_source", {"source": "EXT"}),
        ("play_iq", {"filename": "wifi_pkt.wv"}),
        ("set_output", {"enabled": True}),
    ):
        insert_cmd(
            cur,
            domain="equipment",
            command=cmd,
            key="vsg1",
            result=result,
            timestamp=_ts(base, t0 + 30),
        )
    insert_meas(
        cur,
        domain="equipment",
        command="get_ref_locked",
        key="vsg_ref",
        value=1.0,
        timestamp=_ts(base, t0 + 31),
    )
    insert_meas(
        cur,
        domain="equipment",
        command="measure_power_dbm",
        key="vsg_out",
        value=-10.05,
        units="dBm",
        timestamp=_ts(base, t0 + 31.5),
    )

    # Phase noise
    for cmd, result in (
        ("set_carrier_frequency", {"hz": 10e9}),
        ("set_averaging_count", {"count": 8}),
        ("set_xcorr_count", {"count": 1000}),
        ("initiate", {}),
        ("wait_complete", {"timeout_s": 120}),
    ):
        insert_cmd(
            cur,
            domain="equipment",
            command=cmd,
            key="pn1",
            result=result,
            timestamp=_ts(base, t0 + 40),
        )
    insert_meas(
        cur,
        domain="equipment",
        command="measure_spot_noise_dbc_hz",
        key="pn_10k",
        value=-118.5,
        units="dBc/Hz",
        timestamp=_ts(base, t0 + 50),
    )
    insert_meas(
        cur,
        domain="equipment",
        command="measure_integrated_jitter_s",
        key="pn_jitter",
        value=45.2e-15,
        units="s",
        timestamp=_ts(base, t0 + 50.5),
    )
    insert_meas(
        cur,
        domain="equipment",
        command="save_trace_data",
        key="pn_trace",
        value={"carrier_hz": 10e9, "offsets": [100, 1e3, 10e3, 100e3, 1e6]},
        artifact_path="phasenoise/trace.csv",
        timestamp=_ts(base, t0 + 51),
    )


def fabricate_routing(cur: sqlite3.Cursor, base: datetime) -> None:
    t0 = 500.0
    insert_cmd(
        cur,
        domain="equipment",
        command="set_attenuation_db",
        key="attn1",
        result={"attenuation_db": 20.0, "channel": 1, "settle_s": 0.05},
        timestamp=_ts(base, t0),
    )
    for cmd, val, units in (
        ("measure_attenuation_db", 20.0, "dB"),
        ("measure_min_attenuation_db", 0.0, "dB"),
        ("measure_max_attenuation_db", 90.0, "dB"),
        ("measure_step_db", 0.25, "dB"),
    ):
        insert_meas(
            cur,
            domain="equipment",
            command=cmd,
            key=f"attn_{cmd}",
            value=val,
            units=units,
            timestamp=_ts(base, t0 + 0.5),
        )

    insert_cmd(
        cur,
        domain="equipment",
        command="set_path",
        key="sw1",
        result={"path": "A", "wait_settle_s": 0.02},
        timestamp=_ts(base, t0 + 1),
    )
    insert_meas(
        cur,
        domain="equipment",
        command="measure_path",
        key="sw_path",
        value="A",
        timestamp=_ts(base, t0 + 1.2),
    )

    insert_cmd(
        cur,
        domain="equipment",
        command="set_all",
        key="relay1",
        result={"mask": 0b0000_0101},
        timestamp=_ts(base, t0 + 2),
    )
    insert_meas(
        cur,
        domain="equipment",
        command="measure_all",
        key="relay_bank",
        value=5,
        timestamp=_ts(base, t0 + 2.2),
    )
    insert_cmd(
        cur,
        domain="equipment",
        command="set_pulse_width_s",
        key="relay1",
        result={"pulse_width_s": 0.25},
        timestamp=_ts(base, t0 + 2.3),
    )

    # DIO / serial
    insert_cmd(
        cur,
        domain="io",
        command="configure_pin",
        key="dio1",
        result={"pin": 0, "direction": "out"},
        timestamp=_ts(base, t0 + 3),
    )
    insert_cmd(
        cur,
        domain="io",
        command="set_pull",
        key="dio1",
        result={"pin": 1, "pull": "up"},
        timestamp=_ts(base, t0 + 3.1),
    )
    insert_meas(
        cur,
        domain="io",
        command="read_pin",
        key="dio_enable",
        value=1.0,
        timestamp=_ts(base, t0 + 3.2),
    )
    insert_cmd(
        cur,
        domain="equipment",
        command="write_bytes",
        key="serial1",
        result={"n": 12},
        timestamp=_ts(base, t0 + 4),
    )
    insert_meas(
        cur,
        domain="equipment",
        command="measure_in_waiting",
        key="serial_rx",
        value=64.0,
        timestamp=_ts(base, t0 + 4.2),
    )
    insert_meas(
        cur,
        domain="equipment",
        command="read_bytes",
        key="serial_rx_payload",
        value={"hex": "2447504747412c...", "n": 48},
        timestamp=_ts(base, t0 + 4.3),
    )

    # SCPI status helpers
    insert_meas(
        cur,
        domain="equipment",
        command="status_byte",
        key="sa_stb",
        value=16,
        timestamp=_ts(base, t0 + 5),
    )
    insert_meas(
        cur,
        domain="equipment",
        command="esr",
        key="sa_esr",
        value=0,
        timestamp=_ts(base, t0 + 5.1),
    )
    insert_cmd(
        cur,
        domain="equipment",
        command="clear_status",
        key="sa1",
        result=None,
        timestamp=_ts(base, t0 + 5.2),
    )
    insert_meas(
        cur,
        domain="equipment",
        command="drain_error_queue",
        key="sa_errors",
        value=['0,"No error"'],
        timestamp=_ts(base, t0 + 5.3),
    )


def write_placeholder_artifacts(out: Path) -> None:
    """Create tiny placeholder artifact files referenced by rows."""
    files = {
        "gnss/raw.nmea": "$GPGGA,150001.00,3746.494,N,12225.164,W,1,10,0.9,12.4,M,0.0,M,,*6A\n",
        "gnss/raw_track.csv": "host_ts_iso,receiver_utc_iso,fix_ok,fix_quality,latitude,longitude\n",
        "gnss/track.png": b"\x89PNG\r\n\x1a\nplaceholder",
        "gnss/sky.png": b"\x89PNG\r\n\x1a\nplaceholder",
        "gnss/quality.png": b"\x89PNG\r\n\x1a\nplaceholder",
        "oscope/ch1_waveform.csv": "time_s,voltage_v\n0,0.0\n1e-9,0.1\n",
        "oscope/screen.png": b"\x89PNG\r\n\x1a\nplaceholder",
        "speca/wifi_trace.csv": "freq_hz,ampl_dbm\n2.39e9,-70\n2.40e9,-18.2\n",
        "rtsa/burst.iq.tar": b"IQPLACEHOLDER",
        "rtsa/spectrum.csv": "freq_hz,ampl_dbm\n",
        "vna/dut.s2p": "! fabricated S2P\n# Hz S DB R 50\n",
        "phasenoise/trace.csv": "offset_hz,ldbchz\n100,-80\n1000,-105\n10000,-118.5\n",
    }
    for rel, content in files.items():
        path = out / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")


def main() -> Path:
    out = OUT_DIR
    out.mkdir(parents=True, exist_ok=True)
    write_placeholder_artifacts(out)
    db_path = out / "execution.sqlite"
    if db_path.exists():
        db_path.unlink()

    base = datetime(2026, 10, 18, 15, 24, 0, tzinfo=timezone.utc)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.executescript(SCHEMA_SQL)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO run_metadata (key, value) VALUES (?, ?)",
            ("test_case", "deep_instrument_apis_demo"),
        )
        cur.execute(
            "INSERT INTO run_metadata (key, value) VALUES (?, ?)",
            ("status", "PASS"),
        )
        cur.execute(
            "INSERT INTO run_metadata (key, value) VALUES (?, ?)",
            ("started_at", _ts(base, 0)),
        )
        cur.execute(
            "INSERT INTO run_metadata (key, value) VALUES (?, ?)",
            ("finished_at", _ts(base, 560)),
        )
        cur.execute(
            "INSERT INTO run_metadata (key, value) VALUES (?, ?)",
            (
                "description",
                "Fabricated demo of deep instrument API evidence "
                "(GNSS soak, oscope capture, power bench, RF, routing).",
            ),
        )

        insert_event(
            cur,
            level="INFO",
            message="Starting indoor repeater soak + deep API demo run",
            timestamp=_ts(base, 0),
        )
        fabricate_gnss_epochs(cur, base)
        insert_event(
            cur,
            level="WARNING",
            message="GNSS outage detected ~t=20s (8s) — reacquired",
            timestamp=_ts(base, 28),
        )
        fabricate_oscope(cur, base)
        fabricate_power_bench(cur, base)
        fabricate_stimulus(cur, base)
        fabricate_rf(cur, base)
        fabricate_routing(cur, base)
        insert_event(
            cur,
            level="INFO",
            message="Demo run complete — all deep-API evidence recorded",
            timestamp=_ts(base, 560),
        )
        conn.commit()

        n_meas = cur.execute("SELECT COUNT(*) FROM measurements").fetchone()[0]
        n_cmd = cur.execute("SELECT COUNT(*) FROM commands").fetchone()[0]
        n_ver = cur.execute("SELECT COUNT(*) FROM verifications").fetchone()[0]
        print(f"Wrote {db_path}")
        print(f"  measurements={n_meas} commands={n_cmd} verifications={n_ver}")
        print("  Highlight queries:")
        print("    SELECT * FROM measurements WHERE command='track_epoch' ORDER BY row_index;")
        print("    SELECT * FROM measurements WHERE command LIKE '%outage%' OR command LIKE 'fix_%';")
        print("    SELECT * FROM measurements WHERE artifact_path IS NOT NULL;")
    finally:
        conn.close()
    return db_path


if __name__ == "__main__":
    main()
