"""Regressions for catalog entries which cannot use the inherited SCPI dialect."""

import struct
import ctypes as ct
from types import SimpleNamespace

import pytest

from colosseum_equipment.exceptions import EquipmentCapabilityError, EquipmentResponseError
from colosseum_equipment.instruments.factory import build_instrument


def packet(command, data=b"", address=0):
    frame = bytes([0xAA, address, command]) + data.ljust(22, b"\0")
    return frame + bytes([sum(frame) & 0xFF])


class BinaryLoadTransport:
    def __init__(self, replies=None):
        self.commands = []
        self.replies = list(replies or [])
        self.pending = b""

    def write_bytes(self, data):
        self.commands.append(data)
        self.pending = self.replies.pop(0) if self.replies else packet(0x12, b"\x80")

    def read_bytes(self, count):
        # Fragmented transport reads must still form exactly one reply.
        chunk, self.pending = self.pending[:min(count, 7)], self.pending[min(count, 7):]
        return chunk

    def write(self, data):
        raise AssertionError(f"unexpected text write: {data}")

    def query(self, data):
        raise AssertionError(f"unexpected text query: {data}")

    def close(self):
        pass


def test_bk8500_native_static_control_and_scaled_readback():
    io = BinaryLoadTransport()
    dev = build_instrument("eload", 1, {"model": "bk-8500"}, io)
    dev.set_mode("CP")
    dev.set_current(3)
    dev.set_voltage(16)
    dev.set_power(12.5)
    dev.set_resistance(10)
    dev.engage()
    dev.disengage()
    assert io.commands == [packet(0x20, b"\x01"), packet(0x5D, b"\0"), packet(0x28, b"\x02"), packet(0x2A, struct.pack("<I", 30000)), packet(0x2C, struct.pack("<I", 16000)), packet(0x2E, struct.pack("<I", 12500)), packet(0x30, struct.pack("<I", 10000)), packet(0x21, b"\1"), packet(0x21, b"\0")]
    data = struct.pack("<III", 12000, 20000, 24000) + b"\x08"
    io.replies = [packet(0x5F, data)] * 5
    assert dev.measure_voltage() == 12
    assert dev.measure_current() == 2
    assert dev.measure_power_w() == 24
    assert dev.measure_resistance_ohm() == 6
    assert dev.measure_input_state() is True


@pytest.mark.parametrize("reply", [b"", packet(0x12, b"\xa0"), packet(0x12, b"\x80", 1), packet(0x29, b"\0"), packet(0x12, b"\x80")[:-1] + b"\0"])
def test_bk8500_rejects_bad_packets_and_device_errors(reply):
    with pytest.raises(EquipmentResponseError):
        build_instrument("eload", 1, {"model": "bk-8500"}, BinaryLoadTransport([reply]))


def test_bk8500_never_falls_back_to_ascii_for_unsupported_operations():
    io = BinaryLoadTransport()
    dev = build_instrument("eload", 1, {"model": "bk-8500"}, io)
    before = list(io.commands)
    for method, args in [("preset", ()), ("set_slew_rate", (1,)), ("clear_protection", ()), ("toggle_list", (True,))]:
        with pytest.raises(EquipmentCapabilityError):
            getattr(dev, method)(*args)
    with pytest.raises(EquipmentCapabilityError):
        dev.engage(channel=2)
    with pytest.raises(ValueError):
        dev.set_current(-1)
    assert io.commands == before


class RackTransport:
    def __init__(self, replies):
        self.replies = replies
        self.commands = []

    def query(self, command):
        self.commands.append(command)
        return self.replies[command]

    def write(self, command):
        raise AssertionError(f"unexpected write: {command}")

    def close(self):
        pass


def test_rcm_addresses_configured_block_and_channel_and_checks_reply():
    io = RackTransport({":02:CHAN:3:SETATT:12.750": ":02:1", ":02:CHAN:3:ATT?": ":02:12.75"})
    dev = build_instrument("attn", 1, {"model": "minicircuits-rcm-ztm", "block": 2, "channel": 3}, io)
    dev.set_attenuation_db(12.75)
    assert dev.measure_attenuation_db() == 12.75
    assert io.commands == [":02:CHAN:3:SETATT:12.750", ":02:CHAN:3:ATT?"]


@pytest.mark.parametrize("reply", [":02:0", ":02:2", ":01:1", "1", "", ":02:nan"])
def test_rcm_never_accepts_failure_clamping_or_another_block(reply):
    io = RackTransport({":02:CHAN:1:SETATT:10.000": reply})
    dev = build_instrument("attn", 1, {"model": "minicircuits-rcm-ztm", "block": 2, "channel": 1}, io)
    with pytest.raises(EquipmentResponseError):
        dev.set_attenuation_db(10)


def test_rcm_requires_topology_and_does_not_guess_generic_limit_queries():
    with pytest.raises((ValueError, EquipmentCapabilityError)):
        build_instrument("attn", 1, {"model": "minicircuits-rcm-ztm"}, RackTransport({}))
    io = RackTransport({})
    dev = build_instrument("attn", 1, {"model": "minicircuits-rcm-ztm", "block": 1, "channel": 1}, io)
    with pytest.raises(EquipmentCapabilityError):
        dev.measure_max_attenuation_db()
    with pytest.raises(ValueError):
        dev.set_attenuation_db(float("nan"))
    assert io.commands == []


def test_rcm_http_read_preserves_trailing_query_marker(monkeypatch):
    from unittest.mock import MagicMock
    from colosseum_equipment.transports import http
    connection = MagicMock()
    connection.getresponse.return_value.status = 200
    connection.getresponse.return_value.read.return_value = b":02:12.75"
    monkeypatch.setattr(http, "HTTPConnection", lambda *args, **kwargs: connection)
    io = http.HttpTransport("http://192.0.2.10")
    dev = build_instrument("attn", 1, {"model": "minicircuits-rcm-ztm", "block": 2, "channel": 3}, io)
    assert dev.measure_attenuation_db() == 12.75
    connection.request.assert_called_once_with("GET", "/:02:CHAN:3:ATT?", headers={})


class ApiFunction:
    def __init__(self, library, name):
        self.library, self.name = library, name

    def __call__(self, *args):
        return self.library.dispatch(self.name, args)


class RsaLibrary:
    """Small ABI simulator: writable pointers, actual counts, status and selection."""

    def __init__(self):
        self.calls = []
        self.devices = [("ABC123", "RSA306B")]
        self.selected = 0
        self.count = 4
        self.ready = True
        self.status = 0
        self.short = False
        self.errors = {}
        self.center = 1e9
        self.bandwidth = 40e6

    def __getattr__(self, name):
        function = ApiFunction(self, name)
        setattr(self, name, function)
        return function

    def dispatch(self, name, args):
        self.calls.append((name, args))
        if name in self.errors:
            return self.errors[name]
        if name == "DEVICE_Search":
            assert len(args[2]) >= 20 * 100
            assert len(args[3]) >= 20 * 20
            args[0]._obj.value = len(self.devices)
            for index, (serial, model) in enumerate(self.devices):
                args[1][index] = index + 10
                ct.memmove(ct.addressof(args[2]) + index * 100, serial.encode() + b"\0", len(serial) + 1)
                ct.memmove(ct.addressof(args[3]) + index * 20, model.encode() + b"\0", len(model) + 1)
        elif name == "DEVICE_Connect":
            self.selected = args[0] - 10
        elif name == "DEVICE_GetSerialNumber":
            args[0].value = self.devices[self.selected][0].encode()
        elif name == "DEVICE_GetNomenclature":
            args[0].value = self.devices[self.selected][1].encode()
        elif name == "IQBLK_SetIQRecordLength":
            self.count = args[0]
        elif name == "IQBLK_GetIQRecordLength":
            args[0]._obj.value = self.count
        elif name == "IQBLK_GetMaxIQRecordLength":
            args[0]._obj.value = 100000
        elif name == "IQBLK_GetIQSampleRate":
            args[0]._obj.value = 1000
        elif name == "IQBLK_SetIQBandwidth":
            self.bandwidth = args[0]
        elif name == "IQBLK_GetIQBandwidth":
            args[0]._obj.value = self.bandwidth
        elif name == "CONFIG_SetCenterFreq":
            self.center = args[0]
        elif name == "CONFIG_GetCenterFreq":
            args[0]._obj.value = self.center
        elif name in {"IQBLK_WaitForIQDataReady", "SPECTRUM_WaitForDataReady"}:
            args[1]._obj.value = self.ready
        elif name == "IQBLK_GetIQDataDeinterleaved":
            args[2]._obj.value = self.count - int(self.short)
            for index in range(self.count):
                args[0][index], args[1][index] = index + 1, -index - 1
        elif name == "IQBLK_GetIQAcqInfo":
            args[0]._obj.acqStatus = self.status
            args[0]._obj.sample0Timestamp = 12345
        elif name == "SPECTRUM_GetSettings":
            settings = args[0]._obj
            settings.traceLength = 3
            settings.actualStartFreq = 100
            settings.actualFreqStepSize = 7
            settings.span, settings.rbw = 20, 1
        elif name == "SPECTRUM_GetTrace":
            args[3]._obj.value = 3
            args[2][:] = [-20, -10, -30]
        return 0


def open_rsa(monkeypatch, tmp_path, library=None, **config):
    from colosseum_equipment.transports import tektronix_rsa as native
    from colosseum_equipment.transports.factory import open_transport
    library = library or RsaLibrary()
    path = tmp_path / "RSA_API.dll"
    path.write_bytes(b"mock ABI library, never loaded")
    # Isolate vendor loading without changing NumPy's OS/DLL loading functions.
    monkeypatch.setattr(native, "ct", SimpleNamespace(**{**vars(native.ct), "CDLL": lambda _: library}))
    monkeypatch.setattr(native, "os", SimpleNamespace(name=native.os.name, add_dll_directory=lambda _: SimpleNamespace(close=lambda: None)))
    row = {"driver": "rsa-api", "resource": "ABC123", "model": "tektronix-rsa306b", "rsa_api_library": str(path), **config}
    transport = open_transport("rtsa", 1, row)
    try:
        dev = build_instrument("rtsa", 1, row, transport)
    except Exception:
        transport.close()
        raise
    return dev, library


def test_rsa_direct_api_captures_actual_iq_and_preserves_float64_save_contract(monkeypatch, tmp_path, unit_runtime_context):
    dev, library = open_rsa(monkeypatch, tmp_path, num_samples=4)
    try:
        dev.acquire()
        before = len(library.calls)
        path = dev.save_IQ_data(str(tmp_path / "iq.bin"))
        assert struct.unpack("<8d", path.read_bytes()) == (1, -1, 2, -2, 3, -3, 4, -4)
        assert len(library.calls) == before  # Export does not re-arm or fetch a different record.
        dev.set_center_freq(2e9)
        with pytest.raises(EquipmentCapabilityError):
            dev.save_IQ_data(str(tmp_path / "stale.bin"))
    finally:
        dev.close()


@pytest.mark.parametrize("short,status", [(True, 0), (False, 1), (False, 8)])
def test_rsa_rejects_partial_overrange_and_transfer_error_records(monkeypatch, tmp_path, short, status):
    library = RsaLibrary()
    library.short, library.status = short, status
    dev, _ = open_rsa(monkeypatch, tmp_path, library, num_samples=4)
    try:
        with pytest.raises(EquipmentResponseError):
            dev.acquire()
        with pytest.raises(EquipmentCapabilityError):
            dev.save_IQ_data(str(tmp_path / "bad.bin"))
        assert library.calls[-1][0] == "DEVICE_Stop"
    finally:
        dev.close()


def test_rsa_capture_uses_actual_sample_rate_and_existing_sample_encodings(monkeypatch, tmp_path, unit_runtime_context):
    import numpy as np
    dev, library = open_rsa(monkeypatch, tmp_path)
    try:
        metadata = dev.capture_iq(center_hz=2e9, span_hz=20e6, bandwidth_hz=10e6, seconds=.004, path=str(tmp_path / "capture.bin"), file_format="bin", sample_format="f32")
        assert metadata["num_samples"] == 4
        assert metadata["sample_rate_hz"] == 1000
        assert metadata["actual_duration_s"] == .004
        assert metadata["sample0_timestamp_ticks"] == 12345
        assert np.fromfile(metadata["path"], dtype="<f4").tolist() == [1, -1, 2, -2, 3, -3, 4, -4]
        assert library.bandwidth == 10e6
    finally:
        dev.close()


def test_rsa_spectrum_export_uses_native_actual_axis(monkeypatch, tmp_path, unit_runtime_context):
    dev, _ = open_rsa(monkeypatch, tmp_path)
    try:
        path = dev.save_spectrum_trace_data(str(tmp_path / "spectrum.csv"))
        assert path.read_text().splitlines()[1:] == ["100.000000,-20.000000", "107.000000,-10.000000", "114.000000,-30.000000"]
    finally:
        dev.close()


def test_rsa_selects_serial_from_multiple_devices_and_blocks_second_context(monkeypatch, tmp_path):
    from colosseum_equipment.exceptions import EquipmentConnectionError
    from colosseum_equipment.transports.tektronix_rsa import RsaApiTransport
    library = RsaLibrary()
    library.devices = [("OTHER", "RSA306B"), ("ABC123", "RSA306B")]
    dev, _ = open_rsa(monkeypatch, tmp_path, library)
    try:
        assert library.selected == 1
        with pytest.raises(EquipmentConnectionError, match="one active"):
            RsaApiTransport({})
    finally:
        dev.close()
        dev.close()  # Instrument and transport caches both close their resources.


def test_rsa_timeout_stops_device_and_does_not_export_old_capture(monkeypatch, tmp_path):
    from colosseum_equipment.exceptions import EquipmentTimeoutError
    dev, library = open_rsa(monkeypatch, tmp_path, num_samples=4)
    try:
        dev.acquire()
        library.ready = False
        with pytest.raises(EquipmentTimeoutError):
            dev.acquire(timeout_s=.001)
        with pytest.raises(EquipmentCapabilityError):
            dev.save_IQ_data(str(tmp_path / "stale.bin"))
        assert library.calls[-1][0] == "DEVICE_Stop"
    finally:
        dev.close()


@pytest.mark.parametrize("config", [{"resource": "auto"}, {"resource": "MISSING"}, {"model": "tektronix-rsa507a"}])
def test_rsa_ambiguous_missing_or_wrong_identity_releases_native_context(monkeypatch, tmp_path, config):
    from colosseum.exceptions import ProceduralFault
    from colosseum_equipment.transports import tektronix_rsa as native
    library = RsaLibrary()
    library.devices.append(("OTHER", "RSA306B"))
    with pytest.raises(ProceduralFault):
        open_rsa(monkeypatch, tmp_path, library, **config)
    assert native._session_active is False
    # A subsequent correct connection must work after the failed attempt.
    dev, _ = open_rsa(monkeypatch, tmp_path)
    dev.close()


def test_rsa_api_error_after_run_stops_and_invalidates_record(monkeypatch, tmp_path):
    dev, library = open_rsa(monkeypatch, tmp_path)
    try:
        library.errors["IQBLK_AcquireIQData"] = 302
        with pytest.raises(EquipmentResponseError, match="302"):
            dev.acquire()
        assert library.calls[-1][0] == "DEVICE_Stop"
        with pytest.raises(EquipmentCapabilityError):
            dev.save_IQ_data(str(tmp_path / "bad.bin"))
    finally:
        dev.close()


def test_rsa_failed_stop_does_not_leave_capture_exportable(monkeypatch, tmp_path):
    dev, library = open_rsa(monkeypatch, tmp_path, num_samples=4)
    try:
        library.errors["DEVICE_Stop"] = 302
        with pytest.raises(EquipmentResponseError):
            dev.acquire()
        with pytest.raises(EquipmentCapabilityError):
            dev.save_IQ_data(str(tmp_path / "failed.bin"))
    finally:
        library.errors.clear()
        dev.close()


def test_bk_factory_opens_binary_serial_with_9600_baud(monkeypatch):
    from unittest.mock import MagicMock
    import pyvisa
    from colosseum_equipment.transports.factory import open_transport
    from colosseum_equipment.transports import visa
    manager = MagicMock()
    session = manager.open_resource.return_value
    monkeypatch.setattr(visa, "_acquire_resource_manager", lambda *args: (manager, False))
    transport = open_transport("eload", 1, {"model": "bk-8500", "resource": "COM7"})
    try:
        assert session.baud_rate == 9600
        assert session.read_termination is None
        assert session.write_termination is None
        assert session.end_input == pyvisa.constants.SerialTermination.none
        assert session.end_output == pyvisa.constants.SerialTermination.none
        payload = packet(0x2A, b"\n\r\0\0")
        transport.write_bytes(payload)
        session.write_raw.assert_called_once_with(payload)
    finally:
        transport.close()


@pytest.mark.parametrize("kind,config", [("eload", {"model": "bk-8500", "resource": "USB0::1::INSTR"}), ("attn", {"model": "minicircuits-rcm-ztm", "resource": "USB0::1::INSTR"}), ("rtsa", {"model": "tektronix-rsa306b", "resource": "USB0::1::INSTR"}), ("dmm", {"driver": "rsa-api", "resource": "auto"})])
def test_native_models_do_not_open_unrelated_visa_endpoints(monkeypatch, kind, config):
    from unittest.mock import MagicMock
    from colosseum.exceptions import ProceduralFault
    from colosseum_equipment.transports import visa
    from colosseum_equipment.transports.factory import open_transport
    opener = MagicMock(side_effect=AssertionError("VISA must not be opened"))
    monkeypatch.setattr(visa, "VISATransport", opener)
    with pytest.raises(ProceduralFault):
        open_transport(kind, 1, config)
    opener.assert_not_called()
