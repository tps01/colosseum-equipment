"""RCM/ZTM HTTP authentication, Telnet framing and USB HID reports."""

import socket
from traceback import format_exception
from types import SimpleNamespace
from unittest.mock import MagicMock

import hid
import pytest

from colosseum_equipment.exceptions import (
    EquipmentCapabilityError, EquipmentConnectionError, EquipmentResponseError, EquipmentTimeoutError,
)
from colosseum_equipment.instruments.factory import build_instrument
from colosseum_equipment.transports.factory import open_transport


def rack(driver, resource, **config):
    row = {"model": "minicircuits-rcm-ztm", "driver": driver, "resource": resource, "block": 2, "channel": 3, **config}
    transport = open_transport("attn", 1, row)
    try:
        return build_instrument("attn", 1, row, transport), transport
    except Exception:
        transport.close()
        raise


class Socket:
    def __init__(self, received=b"\n"):
        self.received = bytearray(received)
        self.sent = []
        self.closed = False
        self.timeout = None

    def settimeout(self, timeout):
        self.timeout = timeout

    def recv(self, size):
        if not self.received:
            raise TimeoutError("test receive timeout")
        result = bytes(self.received[:size])
        del self.received[:size]
        return result

    def sendall(self, data):
        self.sent.append(data)

    def close(self):
        self.closed = True


def test_telnet_login_and_commands_use_native_crlf(monkeypatch):
    connection = Socket(b"\n1 - Success\r\n:02:1\r\n:02:12.75\r\n")
    opener = MagicMock(return_value=connection)
    monkeypatch.setattr(socket, "create_connection", opener)
    dev, transport = rack("minicircuits-telnet", "telnet://192.0.2.10:8023", password="PASS-123")
    try:
        dev.set_attenuation_db(12.75)
        assert dev.measure_attenuation_db() == 12.75
        assert connection.sent == [b"PWD=PASS-123;\r\n", b":02:CHAN:3:SETATT:12.750\r\n", b":02:CHAN:3:ATT?\r\n"]
        assert opener.call_args.args == (("192.0.2.10", 8023),)
    finally:
        transport.close()
    assert connection.closed


def test_telnet_refuses_options_without_corrupting_greeting_or_reply(monkeypatch):
    connection = Socket(b"\xff\xfb\x01\xff\xfd\x03\n:02:12.75\r\n")
    monkeypatch.setattr(socket, "create_connection", lambda *a, **k: connection)
    dev, transport = rack("minicircuits-telnet", "telnet://192.0.2.10")
    try:
        assert dev.measure_attenuation_db() == 12.75
        assert connection.sent[:2] == [b"\xff\xfe\x01", b"\xff\xfc\x03"]
    finally:
        transport.close()


def test_telnet_timeout_closes_session_and_cannot_consume_a_late_reply(monkeypatch):
    connection = Socket()
    monkeypatch.setattr(socket, "create_connection", lambda *a, **k: connection)
    dev, transport = rack("minicircuits-telnet", "telnet://192.0.2.10", timeout=.1)
    with pytest.raises(EquipmentTimeoutError):
        dev.measure_attenuation_db()
    assert connection.closed
    before = list(connection.sent)
    connection.received.extend(b":02:99\r\n")
    with pytest.raises(EquipmentConnectionError):
        dev.measure_attenuation_db()
    assert connection.sent == before
    transport.close()


def test_telnet_deadline_applies_to_entire_fragmented_reply(monkeypatch):
    from colosseum_equipment.transports import minicircuits
    connection = Socket()
    monkeypatch.setattr(socket, "create_connection", lambda *a, **k: connection)
    dev, transport = rack("minicircuits-telnet", "telnet://192.0.2.10", timeout=.1)
    tick = 0

    def monotonic():
        nonlocal tick
        tick += .02
        return tick

    monkeypatch.setattr(minicircuits, "time", SimpleNamespace(monotonic=monotonic))
    connection.received.extend(b":02:12.75\r\n")
    with pytest.raises(EquipmentTimeoutError):
        dev.measure_attenuation_db()
    assert connection.closed
    transport.close()


@pytest.mark.parametrize("reply", [b":02:12.75\n", b"x" * 4096, b":02:\xff\xff\r\n"])
def test_telnet_rejects_unterminated_oversize_and_non_ascii_data(monkeypatch, reply):
    connection = Socket()
    monkeypatch.setattr(socket, "create_connection", lambda *a, **k: connection)
    dev, transport = rack("minicircuits-telnet", "telnet://192.0.2.10")
    connection.received.extend(reply)
    with pytest.raises(EquipmentResponseError):
        dev.measure_attenuation_db()
    assert connection.closed
    transport.close()


@pytest.mark.parametrize("received,password", [(b"not a greeting\r\n", ""), (b"\n0 - Failed\r\n", "SECRET")])
def test_telnet_greeting_or_auth_failure_closes_socket(monkeypatch, received, password):
    from colosseum.exceptions import ProceduralFault
    connection = Socket(received)
    monkeypatch.setattr(socket, "create_connection", lambda *a, **k: connection)
    with pytest.raises(ProceduralFault) as error:
        rack("minicircuits-telnet", "telnet://192.0.2.10", password=password)
    assert "SECRET" not in str(error.value)
    assert connection.closed


def report(text, code=42):
    return [code, *text.encode("ascii"), 0] + [0] * (62 - len(text))


class HidDevice:
    def __init__(self, serial="SERIAL1"):
        self.serial = serial
        self.path = None
        self.written = []
        self.closed = False
        self.reply = None
        self.short_write = False
        self.read_timeouts = []

    def open_path(self, path):
        self.path = path

    def write(self, data):
        self.written.append(bytes(data))
        return len(data) - int(self.short_write)

    def read(self, size, timeout_ms):
        assert size == 64
        self.read_timeouts.append(timeout_ms)
        if self.reply is not None:
            return self.reply
        command = self.written[-1][2:].split(b"\0", 1)[0].decode("ascii")
        return report(self.serial if command == ":SN?" else ":02:12.75" if command.endswith("ATT?") else ":02:1")

    def close(self):
        self.closed = True


def mock_hid(monkeypatch, devices):
    enumerator = MagicMock(return_value=[{"path": bytes([index]), "serial_number": device.serial} for index, device in enumerate(devices)])
    monkeypatch.setattr(hid, "enumerate", enumerator)
    monkeypatch.setattr(hid, "device", lambda: devices.pop(0))
    return enumerator


def test_usb_report_id_and_native_code_preserve_block_channel_commands(monkeypatch):
    device = HidDevice()
    enumerator = mock_hid(monkeypatch, [device])
    dev, transport = rack("minicircuits-usb", "SERIAL1")
    try:
        dev.set_attenuation_db(12.75)
        assert dev.measure_attenuation_db() == 12.75
        enumerator.assert_called_once_with(0x20CE, 0x22)
        assert all(len(frame) == 65 and frame[:2] == b"\0\x2a" for frame in device.written)
        assert device.written[-1][2:].split(b"\0", 1)[0] == b":02:CHAN:3:ATT?"
        assert all(0 < timeout <= 5000 for timeout in device.read_timeouts)
    finally:
        transport.close()
    assert device.closed


@pytest.mark.parametrize("response", [[], [42, 0], [99] + [0] * 63, [42] + [65] * 63, [42, 255, 0] + [0] * 61])
def test_usb_rejects_timeout_short_wrong_code_and_invalid_strings(monkeypatch, response):
    device = HidDevice()
    mock_hid(monkeypatch, [device])
    dev, transport = rack("minicircuits-usb", "SERIAL1")
    try:
        device.reply = response
        with pytest.raises((EquipmentTimeoutError, EquipmentResponseError)):
            dev.measure_attenuation_db()
        assert device.closed
        device.reply = report(":02:99")
        with pytest.raises(EquipmentConnectionError):
            dev.measure_attenuation_db()
    finally:
        transport.close()


def test_usb_short_write_does_not_try_read_or_resend(monkeypatch):
    device = HidDevice()
    mock_hid(monkeypatch, [device])
    dev, transport = rack("minicircuits-usb", "SERIAL1")
    before = len(device.read_timeouts)
    try:
        device.short_write = True
        with pytest.raises(EquipmentConnectionError):
            dev.set_attenuation_db(10)
        assert len(device.read_timeouts) == before
        assert device.closed
    finally:
        transport.close()


def test_usb_blocks_share_one_report_session_until_both_close(monkeypatch):
    device = HidDevice()
    mock_hid(monkeypatch, [device])
    dev, first = rack("minicircuits-usb", "SERIAL1")
    other, second = rack("minicircuits-usb", "SERIAL1", block=3)
    try:
        first.close()
        assert not device.closed
        device.reply = report(":03:12.75")
        assert other.measure_attenuation_db() == 12.75
    finally:
        first.close()
        second.close()
    assert device.closed


def test_usb_failed_shared_session_cannot_reopen_until_all_rows_release_it(monkeypatch):
    from colosseum.exceptions import ProceduralFault
    device = HidDevice()
    mock_hid(monkeypatch, [device])
    dev, first = rack("minicircuits-usb", "SERIAL1")
    other, second = rack("minicircuits-usb", "SERIAL1", block=3)
    try:
        device.reply = []
        with pytest.raises(EquipmentTimeoutError):
            dev.measure_attenuation_db()
        before = len(device.written)
        with pytest.raises(EquipmentConnectionError):
            other.measure_attenuation_db()
        with pytest.raises(ProceduralFault):
            rack("minicircuits-usb", "SERIAL1")
        assert len(device.written) == before
    finally:
        first.close()
        second.close()


def test_usb_selects_actual_serial_and_closes_nonmatching_racks(monkeypatch):
    wrong, right = HidDevice("OTHER"), HidDevice("SERIAL1")
    mock_hid(monkeypatch, [wrong, right])
    dev, transport = rack("minicircuits-usb", "SERIAL1")
    try:
        assert wrong.closed
        assert dev.measure_attenuation_db() == 12.75
    finally:
        transport.close()


def test_usb_auto_selection_refuses_multiple_paths_before_open(monkeypatch):
    from colosseum.exceptions import ProceduralFault
    devices = [HidDevice("OTHER"), HidDevice("SERIAL1")]
    mock_hid(monkeypatch, devices)
    with pytest.raises(ProceduralFault):
        rack("minicircuits-usb", "auto")
    assert all(device.path is None for device in devices)


def test_http_uses_native_password_prefix_without_basic_auth(monkeypatch):
    from colosseum_equipment.transports import http
    connection = MagicMock()
    connection.getresponse.return_value.status = 200
    connection.getresponse.return_value.read.return_value = b":02:12.75"
    monkeypatch.setattr(http, "HTTPConnection", lambda *a, **k: connection)
    dev, transport = rack("http", "http://192.0.2.10", password="PASS 123")
    try:
        assert dev.measure_attenuation_db() == 12.75
        connection.request.assert_called_once_with("GET", "/PWD=PASS%20123;:02:CHAN:3:ATT?", headers={})
    finally:
        transport.close()


def test_http_native_password_is_absent_from_failure_traceback(monkeypatch):
    from colosseum_equipment.transports import http
    connection = MagicMock()
    connection.getresponse.return_value.status = 403
    connection.getresponse.return_value.read.return_value = b"denied"
    monkeypatch.setattr(http, "HTTPConnection", lambda *a, **k: connection)
    dev, transport = rack("http", "http://192.0.2.10", password="SECRET")
    try:
        with pytest.raises(EquipmentConnectionError) as error:
            dev.measure_attenuation_db()
        assert "SECRET" not in "".join(format_exception(error.value))
    finally:
        transport.close()


@pytest.mark.parametrize("driver,resource", [("minicircuits-telnet", "telnet://192.0.2.10"), ("minicircuits-usb", "SERIAL1")])
def test_native_transport_rejects_injected_or_overlong_usb_commands_before_send(monkeypatch, driver, resource):
    device, connection = HidDevice(), Socket()
    mock_hid(monkeypatch, [device])
    monkeypatch.setattr(socket, "create_connection", lambda *a, **k: connection)
    _, transport = rack(driver, resource)
    try:
        before = len(device.written), len(connection.sent)
        for command in (":ATT?\r\n:RESET", ":ATT?;:RESET", ":ATT?\0"):
            with pytest.raises(ValueError):
                transport.query(command)
        if driver == "minicircuits-usb":
            with pytest.raises(ValueError):
                transport.query(":" + "a" * 63)
        assert before == (len(device.written), len(connection.sent))
    finally:
        transport.close()


@pytest.mark.parametrize("config", [{"block": 2.5}, {"channel": 3.5}, {"channel": 0}, {"channels_per_block": 4.5}])
def test_rcm_invalid_topology_never_rounds_to_a_different_path(config):
    io = MagicMock()
    with pytest.raises((ValueError, EquipmentCapabilityError)):
        build_instrument("attn", 1, {"model": "minicircuits-rcm-ztm", "block": 2, "channel": 3, **config}, io)
    io.query.assert_not_called()


def test_rcm_path_alias_works_when_channel_is_unset():
    io = MagicMock()
    io.query.return_value = ":02:12.75"
    dev = build_instrument("attn", 1, {"model": "minicircuits-rcm-ztm", "block": 2, "channel": None, "path": 3}, io)
    assert dev.measure_attenuation_db() == 12.75
    io.query.assert_called_once_with(":02:CHAN:3:ATT?")
