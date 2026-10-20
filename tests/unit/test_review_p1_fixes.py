"""Regression tests for review P1/P2 findings."""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from colosseum.database import MeasurementRow
from colosseum_equipment.instruments.factory import build_instrument
from colosseum_equipment.instruments.gnss.nmea import NmeaFix
from colosseum_equipment.instruments.oscope.generic import _parse_ascii_waveform
from colosseum_equipment.exceptions import EquipmentResponseError


class _ByteTransport:
    def __init__(self) -> None:
        self.written_bytes: list[bytes] = []

    def write_bytes(self, payload: bytes) -> None:
        self.written_bytes.append(payload)

    def read_bytes(self, size: int = 256) -> bytes:
        return b""

    def close(self) -> None:
        return None


def test_gnss_stale_fix_not_available() -> None:
    inst = build_instrument(
        "gnss",
        7,
        {"model": "generic", "gnss_id": 7},
        _ByteTransport(),
    )
    assert inst._gnss_id == 7
    now = time.monotonic()
    with inst._state_lock:
        inst._fix = NmeaFix(
            latitude=1.0,
            longitude=2.0,
            altitude_m=3.0,
            fix_quality=1,
            satellites=8,
            hdop=1.0,
            utc_time="120000.00",
        )
        inst._fix_recv_mono = now - 60.0
        inst._last_byte_mono = now - 60.0
    row = inst._build_epoch()
    assert row["stream_ok"] is False
    assert row["fix_ok"] is False


def test_gnss_ttff_without_logging() -> None:
    inst = build_instrument(
        "gnss",
        1,
        {"model": "generic", "gnss_id": 1},
        _ByteTransport(),
    )
    inst.mark_acquisition_start()
    with inst._state_lock:
        inst._fix = NmeaFix(
            latitude=1.0,
            longitude=2.0,
            altitude_m=3.0,
            fix_quality=1,
            satellites=8,
            hdop=1.0,
            utc_time="120000.00",
        )
        inst._fix_recv_mono = time.monotonic()
    inst._note_first_fix()
    assert inst.measure_ttff_s() >= 0.0


def test_parse_ascii_waveform_keeps_first_sample() -> None:
    # IEEE definite-length header glued to first sample: ``#2`` + ``11`` + payload.
    values = _parse_ascii_waveform("#2111.0,2.0,3.0", points_expected=3)
    assert values == [1.0, 2.0, 3.0]


def test_parse_ascii_waveform_rejects_truncation() -> None:
    with pytest.raises(EquipmentResponseError, match="truncated"):
        _parse_ascii_waveform("1.0,2.0", points_expected=3)


def test_serial_read_bytes_measurement_stores_hex(unit_runtime_context, tmp_path: Path) -> None:
    from colosseum_equipment.api import serial as serial_api

    _ = tmp_path
    channel = MagicMock()
    channel.read_bytes.return_value = b"\x00\xffABC"
    with patch("colosseum_equipment.api.serial._channel", return_value=channel):
        result = serial_api.read_bytes(serial_id=1, size=16, key="raw_chunk")
    assert result == b"\x00\xffABC"
    unit_runtime_context.db.drain()
    row = unit_runtime_context.db.get_measurement(
        "equipment", "serial.read_bytes", "raw_chunk", row_index=0,
    )
    assert row is not None
    assert isinstance(row.value, dict)
    assert row.value["encoding"] == "hex"
    assert row.value["data"] == "00ff414243"


def test_minimum_verifier_resolves_gnss_command(unit_runtime_context) -> None:
    from colosseum_equipment.api import gnss as gnss_api

    unit_runtime_context.db.insert_measurement(
        MeasurementRow(
            domain="equipment",
            command="gnss.measure_max_cn0_dbhz",
            key="cn0",
            value=42.0,
        ),
    )
    result = gnss_api.verify_max_cn0_dbhz(key="cn0", limit=30.0)
    assert result.status == "PASS"


def test_record_artifact_is_immediately_visible(unit_runtime_context, tmp_path: Path) -> None:
    from colosseum_equipment.evidence import record_artifact

    path = tmp_path / "trace.csv"
    path.write_text("frequency_hz,amplitude_dbm\n1e9,-50\n", encoding="utf-8")
    record_artifact(
        domain="equipment",
        command="save_trace_data",
        key="visible",
        path=path,
    )
    # No drain — synchronous insert must already be readable.
    row = unit_runtime_context.db.get_measurement(
        "equipment", "save_trace_data", "visible", row_index=0,
    )
    assert row is not None
    assert row.artifact_path == "trace.csv"
    resolved = unit_runtime_context.db.resolve_artifact_path(row.artifact_path)
    # In-memory unit DBs have no on-disk run dir; the active output dir still holds the file.
    if resolved is None or not resolved.is_file():
        resolved = unit_runtime_context.output_dir / str(row.artifact_path)
    assert resolved.is_file()
