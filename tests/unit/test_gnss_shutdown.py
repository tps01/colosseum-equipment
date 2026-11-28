"""A timed-out worker remains owned until shutdown can actually finish."""

import io
import threading

import pytest

from colosseum_equipment.exceptions import EquipmentTimeoutError
from colosseum_equipment.instruments.gnss.generic import GenericGnss
from colosseum_equipment.instruments.gnss.listener import GnssListener
from tests.support.stubs import StubTransport


def test_listener_reports_blocked_reader_and_can_finish_later():
    entered = threading.Event()
    release = threading.Event()
    chunks = []

    def read(_size):
        entered.set()
        release.wait(5)
        return b"last bytes"

    listener = GnssListener(read, chunks.append)
    listener.start()
    try:
        assert entered.wait(1)
        with pytest.raises(EquipmentTimeoutError, match="listener"):
            listener.stop(timeout_s=0.01)
        assert listener.is_alive()
    finally:
        release.set()
        listener.stop()
    assert chunks == [b"last bytes"]


def test_failed_stop_retains_files_and_listener_for_retry():
    class BlockedListener:
        blocked = True

        def stop(self):
            if self.blocked:
                raise EquipmentTimeoutError("blocked listener")

    instrument = GenericGnss(StubTransport(), {})
    listener = BlockedListener()
    raw = io.StringIO()
    instrument._listener = listener
    instrument._raw_log = raw
    with pytest.raises(EquipmentTimeoutError):
        instrument.stop_logging()
    assert instrument._listener is listener
    assert not raw.closed
    listener.blocked = False
    instrument.stop_logging()
    assert instrument._listener is None
    assert raw.closed


def test_close_retries_epoch_timeout_and_finishes_recording_in_order(monkeypatch, tmp_path):
    from colosseum_equipment.instruments.gnss import generic

    events = []

    class BlockedTimer:
        blocked = True

        def join(self, timeout):
            assert timeout == 2.0
            assert instrument._epoch_stop.is_set()
            events.append("timer")

        def is_alive(self):
            return self.blocked

    class Listener:
        def stop(self):
            assert instrument._epoch_timer is None
            events.append("listener")

    def record_measurement(**kwargs):
        assert instrument._listener is None
        assert all(not stream.closed for stream in files)
        events.append(kwargs["command"])

    def record_wire(**kwargs):
        assert all(stream.closed for stream in files)
        events.append(kwargs["command"])

    transport = StubTransport()
    monkeypatch.setattr(transport, "close", lambda: events.append("transport"))
    monkeypatch.setattr(generic, "enqueue_measurement", record_measurement)
    monkeypatch.setattr(generic, "record_artifact", record_wire)
    instrument = GenericGnss(transport, {})
    timer = BlockedTimer()
    listener = Listener()
    files = io.StringIO(), io.BytesIO(), io.StringIO()
    instrument._epoch_timer = timer
    instrument._listener = listener
    instrument._raw_log, instrument._wire_log, instrument._track_csv = files
    instrument._wire_log_path = tmp_path / "wire.bin"
    instrument._logging_key = "recording"
    instrument._epochs_total = 1

    with pytest.raises(EquipmentTimeoutError, match="epoch timer"):
        instrument.close()
    assert events == ["timer"]
    assert instrument._epoch_timer is timer
    assert instrument._listener is listener
    assert all(not stream.closed for stream in files)
    with pytest.raises(RuntimeError, match="already logging"):
        instrument.start_logging("must-not-open.nmea")

    timer.blocked = False
    instrument.close()
    assert events == [
        "timer", "timer", "listener", "fix_availability", "longest_outage_s",
        "epochs_total", "epochs_nofix", "wire_log", "transport",
    ]
