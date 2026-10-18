"""GNSS config load/save, message rates, and binary wire capture."""

from __future__ import annotations

import time
from pathlib import Path

import pytest
from colosseum_equipment.exceptions import EquipmentCapabilityError
from colosseum_equipment.instruments.factory import build_instrument
from colosseum_equipment.instruments.gnss.ubx import (
    CLS_CFG,
    CLS_NAV,
    ID_CFG_MSG,
    ID_CFG_VALGET,
    ID_CFG_VALSET,
    ID_NAV_PVT,
    ID_NAV_SAT,
    SET_LAYER_BBR,
    SET_LAYER_RAM,
    build_ubx,
    cfg_msg_rate,
    ucenter_hex_line,
)
from colosseum_equipment.instruments.gnss.ubx_config import (
    detect_mismatch,
    frames_from_ucenter_file,
    load_config_path,
    parse_ucenter_txt,
    valget_payload_to_valset,
)


class _ByteTransport:
    def __init__(self, chunks: list[bytes] | None = None) -> None:
        self._chunks = list(chunks or [])
        self.written_bytes: list[bytes] = []

    def write_bytes(self, payload: bytes) -> None:
        self.written_bytes.append(payload)

    def read_bytes(self, size: int = 256) -> bytes:
        if not self._chunks:
            return b""
        return self._chunks.pop(0)

    def close(self) -> None:
        return None


def _gga_line() -> str:
    body = "GPGGA,123519,3746.4940,N,12225.1640,W,1,08,0.9,10.0,M,0.0,M,,"
    checksum = 0
    for char in body:
        checksum ^= ord(char)
    return f"${body}*{checksum:02X}"


def test_parse_ucenter_legacy_and_valget() -> None:
    legacy_payload = bytes((1, 7, 1))  # CFG-MSG enable NAV-PVT rate 1
    legacy_line = ucenter_hex_line("CFG-MSG", CLS_CFG, ID_CFG_MSG, legacy_payload)
    # Fake VALGET: version, layer RAM, reserved, then 4 bytes of kv
    valget_payload = bytes((0, 0, 0, 0)) + b"\x01\x02\x03\x04"
    valget_line = ucenter_hex_line("CFG-VALGET", CLS_CFG, ID_CFG_VALGET, valget_payload)
    text = "\n".join(
        [
            "u-blox AG - www.u-blox.com",
            legacy_line,
            valget_line,
        ],
    )
    info = parse_ucenter_txt(text)
    assert info.has_legacy_cfg
    assert info.has_valget
    frames = frames_from_ucenter_file(info)
    assert len(frames) == 2
    # First is legacy CFG-MSG
    assert frames[0][2:4] == bytes((CLS_CFG, ID_CFG_MSG))
    # Second is VALSET
    assert frames[1][2:4] == bytes((CLS_CFG, ID_CFG_VALSET))
    set_payload = frames[1][6:-2]
    assert set_payload[0] == 0  # version
    assert set_payload[1] == (SET_LAYER_RAM | SET_LAYER_BBR)
    assert set_payload[4:] == b"\x01\x02\x03\x04"


def test_valget_to_valset_layers() -> None:
    payload = bytes((1, 2, 0, 0)) + b"\xaa\xbb"
    out = valget_payload_to_valset(payload, layers=SET_LAYER_RAM)
    assert out[0] == 1
    assert out[1] == SET_LAYER_RAM
    assert out[4:] == b"\xaa\xbb"


def test_detect_mismatch_warns() -> None:
    info = parse_ucenter_txt(
        ucenter_hex_line("CFG-VALGET", CLS_CFG, ID_CFG_VALGET, bytes(8)),
    )
    assert detect_mismatch("ublox-m8", info)
    legacy = parse_ucenter_txt(
        ucenter_hex_line("CFG-MSG", CLS_CFG, ID_CFG_MSG, bytes((1, 7, 1))),
    )
    assert detect_mismatch("ublox-m10", legacy)


def test_load_config_path_txt_and_ubx(tmp_path: Path) -> None:
    txt = tmp_path / "cfg.txt"
    payload = bytes((CLS_NAV, ID_NAV_PVT, 1))
    txt.write_text(ucenter_hex_line("CFG-MSG", CLS_CFG, ID_CFG_MSG, payload), encoding="utf-8")
    frames, info = load_config_path(txt)
    assert info is not None
    assert len(frames) == 1

    binary = build_ubx(CLS_CFG, ID_CFG_MSG, payload)
    ubx_path = tmp_path / "cfg.ubx"
    ubx_path.write_bytes(binary + binary)
    frames2, info2 = load_config_path(ubx_path)
    assert info2 is None
    assert len(frames2) == 2


def test_ublox_load_config_sends_frames(tmp_path: Path) -> None:
    transport = _ByteTransport()
    instrument = build_instrument("gnss", 1, {"model": "ublox-m10"}, transport)
    transport.written_bytes.clear()
    payload = bytes((CLS_NAV, ID_NAV_SAT, 1))
    cfg = tmp_path / "m10.txt"
    cfg.write_text(ucenter_hex_line("CFG-MSG", CLS_CFG, ID_CFG_MSG, payload), encoding="utf-8")
    instrument.load_config(str(cfg))
    # load frames + re-enable NAV-PVT/DOP/GSV
    assert any(frame[2:4] == bytes((CLS_CFG, ID_CFG_MSG)) for frame in transport.written_bytes)
    assert len(transport.written_bytes) >= 4


def test_ublox_set_message_rate() -> None:
    transport = _ByteTransport()
    instrument = build_instrument("gnss", 1, {"model": "ublox-f9"}, transport)
    transport.written_bytes.clear()
    instrument.set_message_rate("NAV-SAT", 1.0)
    assert cfg_msg_rate(CLS_NAV, ID_NAV_SAT, 1) in transport.written_bytes
    instrument.set_message_rate("NAV-SAT", 0.0)
    assert cfg_msg_rate(CLS_NAV, ID_NAV_SAT, 0) in transport.written_bytes


def test_ublox_save_config_legacy(tmp_path: Path, unit_runtime_context) -> None:
    _ = unit_runtime_context
    # Respond to MON-VER + CFG-PRT poll with one CFG-PRT
    prt_payload = bytes(20)
    responses = [
        build_ubx(0x0A, 0x04, b"MOD=NEO-M8N\x00"),  # MON-VER
        build_ubx(CLS_CFG, 0x00, prt_payload),  # CFG-PRT
    ]
    # Pad empty reads for other polls
    transport = _ByteTransport(responses + [b""] * 40)
    instrument = build_instrument("gnss", 1, {"model": "ublox-m8"}, transport)
    out = tmp_path / "export.txt"
    # save writes under resolve_artifact_path — use relative path under run dir
    path = instrument.save_config("configs/m8_export.txt")
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "CFG-PRT" in text or "CFG-" in text


def test_wire_capture_generic(unit_runtime_context) -> None:
    _ = unit_runtime_context
    gga = (_gga_line() + "\n").encode("ascii")
    # Repeat so listener keeps getting data
    transport = _ByteTransport([gga, gga, gga, gga])
    instrument = build_instrument("gnss", 1, {"model": "generic"}, transport)
    try:
        instrument.start_logging("gnss/session.nmea", key="wire_test")
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            if instrument._wire_log_path and instrument._wire_log_path.is_file():
                if instrument._wire_log_path.stat().st_size > 0:
                    break
            time.sleep(0.05)
    finally:
        instrument.stop_logging()
    assert instrument._wire_log_path is not None
    assert instrument._wire_log_path.suffix == ".bin"
    wire = instrument._wire_log_path.read_bytes()
    assert b"$GPGGA" in wire


def test_wire_capture_ublox_suffix(unit_runtime_context) -> None:
    _ = unit_runtime_context
    transport = _ByteTransport([b"\xb5\x62\x01\x07" + b"\x00" * 20])
    instrument = build_instrument("gnss", 1, {"model": "ublox-m10"}, transport)
    try:
        instrument.start_logging("gnss/raw.nmea", key="ubx_wire")
        time.sleep(0.15)
    finally:
        instrument.stop_logging()
    assert instrument._wire_log_path is not None
    assert instrument._wire_log_path.name.endswith("_wire.ubx")


def test_novatel_load_and_set_rate(tmp_path: Path) -> None:
    transport = _ByteTransport()
    instrument = build_instrument("gnss", 1, {"model": "novatel-oem7"}, transport)
    transport.written_bytes.clear()
    script = tmp_path / "oem.txt"
    script.write_text("LOG RAWIMUSXB ONTIME 1\n# comment\n\n", encoding="utf-8")
    instrument.load_config(str(script))
    assert any(b"RAWIMUSXB" in w for w in transport.written_bytes)
    transport.written_bytes.clear()
    instrument.set_message_rate("BESTPOSB", 0.0)
    assert any(b"UNLOG BESTPOSB" in w for w in transport.written_bytes)


def test_septentrio_save_config(unit_runtime_context) -> None:
    _ = unit_runtime_context
    transport = _ByteTransport([b"$R:\n", b"$R:\n"])
    instrument = build_instrument(
        "gnss",
        1,
        {"model": "septentrio-asterx-u3", "connection": "COM1"},
        transport,
    )
    path = instrument.save_config("configs/sept.txt")
    text = path.read_text(encoding="utf-8")
    assert "setNMEAOutput" in text
    assert "setSBFOutput" in text
    assert "PVTGeodetic" in text


def test_generic_config_unsupported() -> None:
    transport = _ByteTransport()
    instrument = build_instrument("gnss", 1, {"model": "generic"}, transport)
    with pytest.raises(EquipmentCapabilityError):
        instrument.load_config("x.txt")
    with pytest.raises(EquipmentCapabilityError):
        instrument.save_config("x.txt")
    with pytest.raises(EquipmentCapabilityError):
        instrument.set_message_rate("GGA", 1.0)
