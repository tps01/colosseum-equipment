"""Streaming capture, loss reporting, and public evidence integration."""

import json
from array import array
from collections import deque
from threading import Event
from time import sleep

import colosseum as col
import pytest
from colosseum.config import load_config
from colosseum.plugins import loader as plugin_loader

from colosseum_equipment import register
from colosseum_equipment.connections import close_all
from colosseum_equipment.io.backends import _usb, totalphase
from colosseum_equipment.io.backends.analyzer import AnalyzerBackend
from colosseum_equipment.io.backends.factory import open_backend
from colosseum_equipment.io.exceptions import IoConfigError, IoConnectionError


class BeagleApi:
    BG_FEATURE_I2C = 1
    BG_FEATURE_SPI = 2
    BG_FEATURE_USB = 4
    BG_FEATURE_USB_HS = 16
    BG_FEATURE_USB_SS = 32
    BG_PROTOCOL_I2C = 1
    BG_PROTOCOL_SPI = 2
    BG_PROTOCOL_USB = 3
    BG_READ_TIMEOUT = 1
    BG_READ_ERR_SHORT_BUFFER = 8
    BG_SPI_SCK_SAMPLING_EDGE_RISING = 0
    BG_SPI_SCK_SAMPLING_EDGE_FALLING = 1
    BG_SPI_SS_ACTIVE_LOW = 0
    BG_SPI_BITORDER_MSB = 0
    BG_USB_FEATURE_IV_MON_LITE = 64

    def __init__(self):
        self.features = 3
        self.calls = []
        self.packets = deque()
        self.consumed = Event()
        self.closed = self.disabled = 0
        self.fail_read = False
        self.forever = False
        self.active = False

    def bg_find_devices_ext(self, ports, ids):
        return 1, [0], [1234567890]

    def bg_open(self, port):
        return 7

    def bg_close(self, handle):
        assert not self.active
        self.closed += 1
        return 1

    def bg_features(self, handle):
        return self.features

    def bg_usb_features(self, handle):
        return 1

    def bg_samplerate(self, handle, khz):
        return khz or 60000

    def bg_enable(self, handle, protocol):
        self.active = True
        self.calls.append(("enable", protocol))
        return 0

    def bg_disable(self, handle):
        self.active = False
        self.disabled += 1
        return 0

    def __getattr__(self, name):
        if name in ("bg_timeout", "bg_latency", "bg_target_power", "bg_i2c_pullup", "bg_spi_configure"):
            def call(*args):
                self.calls.append((name, *args))
                return 0
            return call
        raise AttributeError(name)

    def _packet(self):
        if self.fail_read:
            return -6, 0
        if self.packets:
            packet = self.packets.popleft()
            self.consumed.set()
            return packet
        if self.forever:
            return 1, 0
        sleep(0.001)
        return 0, self.BG_READ_TIMEOUT

    def bg_i2c_read(self, handle, limit):
        n, status = self._packet()
        return n, status, 1234, 30, 2, array("H", [0x142] * max(0, n))

    def bg_spi_read(self, handle, mosi_limit, miso_limit):
        n, status = self._packet()
        return n, status, 1234, 30, 2, array("B", [0xAB] * max(0, n)), array("B", [0xCD] * max(0, n))

    def bg_usb2_read(self, handle, limit):
        n, status = self._packet()
        return n, status, 16 if n else 0, 1234, 30, 2, array("B", [0xC3] * max(0, n))


@pytest.fixture
def bg(monkeypatch):
    api = BeagleApi()
    monkeypatch.setattr(totalphase, "load_api", lambda prefix: api)
    yield api
    assert not _usb._sessions


def config(**kwargs):
    return {"driver": "totalphase-beagle", "resource": "1234567890", "model": "i2c-spi",
            "protocol": "i2c", **kwargs}


@pytest.mark.parametrize("model,protocol,features", [
    ("i2c-spi", "i2c", 3), ("i2c-spi", "spi", 3),
    ("usb-12", "usb", 4), ("usb-480", "usb", 20),
])
def test_beagle_packets_preserve_timing_and_protocol_data(bg, tmp_path, model, protocol, features):
    bg.features = features
    bg.packets.append((1, 0))
    backend = open_backend("analyzer", 1, config(model=model, protocol=protocol))
    path = tmp_path / "trace.jsonl"
    try:
        backend.start(path)
        assert bg.active  # start returns only after enabling the instrument
        assert bg.consumed.wait(1)
        summary = backend.stop()
        assert summary["records"] == 1
        assert summary["drained_to_idle"]
        assert summary["tail_may_be_discarded"]
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        assert rows[1]["time_sop_ticks"] == 1234
        assert rows[1]["duration_ticks"] == 30
        assert rows[1]["data_offset_ticks"] == 2
        if protocol == "i2c":
            assert rows[1]["words"] == [0x142]  # keep ACK/NACK bit
        elif protocol == "spi":
            assert rows[1]["mosi"] == "ab" and rows[1]["miso"] == "cd"
        else:
            assert rows[1]["data"] == "c3" and rows[1]["events"] == 16
        assert rows[-1]["type"] == "summary"
        assert backend.export(tmp_path / "export.jsonl") == summary
        assert (tmp_path / "export.jsonl").read_bytes() == path.read_bytes()
    finally:
        backend.close()
    assert bg.closed == bg.disabled == 1


def test_beagle_model_and_ownership_validation(bg):
    with pytest.raises(IoConfigError, match="features"):
        AnalyzerBackend(config(model="usb-480", protocol="usb"))
    assert bg.closed == 1
    backend = AnalyzerBackend(config())
    try:
        with pytest.raises(IoConfigError, match="conflicting"):
            AnalyzerBackend(config())
    finally:
        backend.close()


def test_beagle_usb480_power_is_distinct(bg, monkeypatch):
    bg.features = 20
    monkeypatch.setattr(bg, "bg_usb_features", lambda handle: 65)
    with pytest.raises(IoConfigError, match="USB 480 Power"):
        AnalyzerBackend(config(model="usb-480", protocol="usb"))
    assert bg.closed == 1


def test_beagle_partial_initialization_turns_power_off(bg, monkeypatch):
    monkeypatch.setattr(bg, "bg_i2c_pullup", lambda *args: -6)
    with pytest.raises(IoConnectionError):
        AnalyzerBackend(config(target_power=True))
    assert ("bg_target_power", 7, 1) in bg.calls
    assert bg.calls[-1] == ("bg_target_power", 7, 0)
    assert bg.closed == 1


@pytest.mark.parametrize("changes", [
    {"model": "usb-480-power"}, {"model": "usb-12", "protocol": "spi"},
    {"mode": 4}, {"max_duration_s": float("nan")}, {"max_records": 0},
    {"max_bytes": -1}, {"model": "usb-12", "protocol": "usb", "sample_rate_hz": 50_000_000},
    {"model": "usb-480", "protocol": "usb", "target_power": True},
])
def test_bad_analyzer_configuration_is_rejected_before_open(bg, changes):
    with pytest.raises(IoConfigError):
        AnalyzerBackend(config(**changes))
    assert bg.closed == 0


def test_beagle_reports_vendor_loss_flags(bg, tmp_path):
    bg.packets.append((1, bg.BG_READ_ERR_SHORT_BUFFER))
    backend = AnalyzerBackend(config())
    try:
        backend.start(tmp_path / "loss.jsonl")
        assert bg.consumed.wait(1)
        summary = backend.stop()
        assert summary["loss_detected"] and summary["flagged_records"] == 1
    finally:
        backend.close()


def test_disconnect_propagates_but_diagnostic_capture_is_exportable(bg, tmp_path):
    bg.fail_read = True
    backend = AnalyzerBackend(config())
    try:
        backend.start(tmp_path / "error.jsonl")
        with pytest.raises(IoConnectionError, match="vendor status -6"):
            backend.stop()
        summary = backend.export(tmp_path / "diagnostic.jsonl")
        assert summary["stop_reason"] == "error" and summary["loss_detected"]
    finally:
        with pytest.raises(IoConnectionError):
            backend.close()
    assert bg.closed == 1


def test_busy_bus_drain_is_bounded(bg, tmp_path):
    bg.forever = True
    backend = AnalyzerBackend(config(max_records=1_000_000, max_bytes=100_000_000))
    try:
        backend.start(tmp_path / "busy.jsonl")
        summary = backend.stop(timeout_s=0.01)
        assert summary["stop_reason"] == "drain_timeout"
        assert summary["loss_detected"] and not summary["drained_to_idle"]
        assert bg.disabled == 1
    finally:
        backend.close()


@pytest.mark.parametrize("limits,reason", [
    ({"max_records": 1}, "record_limit"), ({"max_bytes": 1}, "byte_limit"),
    ({"max_duration_s": 0.01}, "duration_limit"),
])
def test_sim_capture_is_bounded(tmp_path, limits, reason):
    backend = AnalyzerBackend({"driver": "sim", "records": [{"data": "abcd"}] * 10, **limits})
    try:
        backend.start(tmp_path / "sim.jsonl")
        backend._thread.join(1)
        assert not backend._thread.is_alive()
        summary = backend.stop()
        assert summary["stop_reason"] == reason
        if reason != "duration_limit":
            assert summary["loss_detected"]
        assert not summary["tail_may_be_discarded"]
    finally:
        backend.close()


def test_capture_lifecycle_and_configuration(bg, tmp_path):
    backend = AnalyzerBackend(config(protocol="spi"))
    try:
        with pytest.raises(IoConfigError, match="no capture"):
            backend.stop()
        for mode in range(4):
            backend.configure(mode=mode)
            path = tmp_path / f"mode{mode}.jsonl"
            backend.start(path)
            assert ("bg_spi_configure", 7, 0, (mode >> 1) ^ (mode & 1), 0) in bg.calls
            with pytest.raises(IoConfigError, match="already running"):
                backend.start(path)
            with pytest.raises(IoConfigError, match="stop the capture"):
                backend.configure(mode=0)
            with pytest.raises(IoConfigError, match="stop the capture"):
                backend.export(tmp_path / "copy.jsonl")
            backend.stop()
            with pytest.raises(FileExistsError):
                backend.start(path)
    finally:
        backend.close()
    with pytest.raises(IoConnectionError, match="closed"):
        backend.start(tmp_path / "closed.jsonl")


class EquipmentEntryPoint:
    name = "equipment"
    value = "colosseum_equipment:register"

    def load(self):
        return register


def test_public_analyzer_config_evidence_and_active_shutdown(
    io_runtime_context, io_bench, monkeypatch,
):
    monkeypatch.setattr(plugin_loader, "entry_points_for_group", lambda group: [EquipmentEntryPoint()])
    load_config(io_bench('''
        [[io.analyzer]]
        analyzer_id = 1
        driver = "sim"
        protocol = "i2c"
        records = [{ words = [322], time_sop_ticks = 10, loss = true }]
        [[io.analyzer]]
        analyzer_id = 2
        driver = "sim"
        protocol = "usb"
    '''))
    col.io.analyzer.start(analyzer_id=1, path="raw.jsonl")
    result = col.io.analyzer.stop(analyzer_id=1)
    assert result["records"] == 1
    summary = col.io.analyzer.export(analyzer_id=1, path="capture.jsonl", key="bus")
    assert summary["loss_detected"]
    rows = io_runtime_context.db.list_measurements(
        domain="equipment", command="io.analyzer.export", key="bus",
    )
    assert len(rows) == 1
    assert rows[0].status == "FAIL"
    assert rows[0].artifact_path == "capture.jsonl"
    col.io.analyzer.start(analyzer_id=2)
    backend = io_runtime_context.resource_cache["io:backend:analyzer:2"]
    close_all()
    assert not backend._thread.is_alive()
    assert not io_runtime_context.resource_cache
