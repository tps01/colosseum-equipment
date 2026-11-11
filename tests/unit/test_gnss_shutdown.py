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


def test_epoch_timeout_retains_recording_resources():
    class BlockedTimer:
        def join(self, timeout):
            assert timeout == 2.0

        def is_alive(self):
            return True

    instrument = GenericGnss(StubTransport(), {})
    timer = BlockedTimer()
    raw = io.StringIO()
    instrument._epoch_timer = timer
    instrument._raw_log = raw
    try:
        with pytest.raises(EquipmentTimeoutError, match="epoch timer"):
            instrument.stop_logging()
        assert instrument._epoch_timer is timer
        assert not raw.closed
        with pytest.raises(RuntimeError, match="already logging"):
            instrument.start_logging("must-not-open.nmea")
    finally:
        raw.close()
