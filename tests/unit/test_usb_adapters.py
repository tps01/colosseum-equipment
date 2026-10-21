"""Transaction and ownership contracts against fake vendor runtimes."""

from array import array
from types import SimpleNamespace

import pytest

from colosseum_equipment.io.backends import _usb, totalphase, usb2any
from colosseum_equipment.io.backends.factory import open_backend
from colosseum_equipment.io.exceptions import IoConfigError, IoConnectionError


class TotalPhaseApi:
    AA_CONFIG_SPI_I2C = 3
    AA_TARGET_POWER_NONE = 0
    AA_TARGET_POWER_BOTH = 3
    AA_I2C_PULLUP_NONE = 0
    AA_I2C_PULLUP_BOTH = 3
    AA_I2C_10_BIT_ADDR = 1
    AA_SPI_BITORDER_MSB = 0
    CH_SPI_BITORDER_MSB = 0

    def __init__(self):
        self.calls = []
        self.opened = self.closed = 0
        self.status = 0
        self.short = False
        self.busy = False
        self.fail_shift = False

    def __getattr__(self, name):
        if name.endswith("_find_devices_ext"):
            return lambda *args: (1, [0x8000 if self.busy else 2], [1234567890])
        if name.endswith("_open"):
            def open_device(port):
                self.opened += 1
                return 7
            return open_device
        if name.endswith("_close"):
            def close_device(handle):
                self.closed += 1
                return 1
            return close_device
        if name in ("aa_i2c_bitrate", "aa_spi_bitrate", "ch_spi_bitrate"):
            return lambda handle, rate: rate - 1
        if name in ("aa_configure", "aa_target_power", "aa_i2c_bus_timeout", "aa_i2c_pullup",
                    "ch_target_power", "aa_spi_configure", "ch_spi_configure",
                    "ch_spi_queue_clear", "ch_spi_queue_oe", "ch_spi_queue_ss"):
            def configure(*args):
                self.calls.append((name, *args))
                return 0
            return configure
        raise AttributeError(name)

    def aa_i2c_write_ext(self, handle, addr, flags, data):
        self.calls.append(("write", addr, flags, bytes(data)))
        return self.status, len(data) - int(self.short)

    def aa_i2c_read_ext(self, handle, addr, flags, n):
        return self.status, array("B", [0xAB] * n), n - int(self.short)

    def aa_i2c_write_read(self, handle, addr, flags, data, n):
        self.calls.append(("combined", addr, flags, bytes(data), n))
        return self.status, len(data), array("B", [0xCD] * n), n - int(self.short)

    def aa_spi_write(self, handle, data, n):
        return n - int(self.short), data

    def ch_spi_queue_array(self, handle, data):
        self.calls.append(("queue_data", bytes(data)))
        return len(data)

    def ch_spi_batch_shift(self, handle, n):
        self.calls.append(("shift", n))
        if self.fail_shift and n:
            return -6, array("B")
        return n - int(self.short and n > 0), array("B", [0x12] * n)


@pytest.fixture
def tp(monkeypatch):
    fake = TotalPhaseApi()
    monkeypatch.setattr(totalphase, "load_api", lambda prefix: fake)
    yield fake
    assert not _usb._sessions


def test_aardvark_shared_handle_and_atomic_transactions(tp):
    i2c = open_backend("i2c", 1, {"driver": "totalphase-aardvark", "resource": "1234-567890"})
    spi = open_backend("spi", 2, {"driver": "totalphase-aardvark", "resource": "1234567890"})
    assert tp.opened == 1
    i2c.write(b"")
    assert ("write", 0x50, 0, b"") in tp.calls
    i2c.configure(address=0x2FF, address_bits=10)
    assert i2c.write_read(b"\x03", 2) == b"\xcd\xcd"
    assert ("combined", 0x2FF, 1, b"\x03", 2) in tp.calls
    assert i2c.read(1) == b"\xab"
    assert i2c.actual_clock_hz == 99_000
    for mode in range(4):
        spi.configure(mode=mode)
        assert spi.transfer(b"\x55") == b"\x55"
        assert ("aa_spi_configure", 7, mode >> 1, mode & 1, 0) in tp.calls
    with pytest.raises(IoConfigError, match="4096"):
        spi.transfer(bytes(4097))
    i2c.close()
    i2c.close()
    assert tp.closed == 0
    spi.close()
    assert tp.closed == 1
    with pytest.raises(IoConnectionError, match="closed"):
        spi.transfer(b"x")


def test_shared_settings_reject_conflicting_power(tp):
    cfg = {"driver": "totalphase-aardvark", "resource": "1234567890"}
    first = open_backend("i2c", 1, cfg)
    try:
        with pytest.raises(IoConfigError, match="conflicting"):
            open_backend("spi", 1, {**cfg, "target_power": True})
        assert tp.opened == 1
    finally:
        first.close()


@pytest.mark.parametrize("operation", ["write", "read", "combined", "spi"])
def test_aardvark_rejects_short_transfers(tp, operation):
    cfg = {"driver": "totalphase-aardvark", "resource": "1234567890"}
    backend = open_backend("spi" if operation == "spi" else "i2c", 1, cfg)
    try:
        tp.short = True
        with pytest.raises(IoConnectionError, match="short transfer"):
            if operation == "write":
                backend.write(b"x")
            elif operation == "read":
                backend.read(1)
            elif operation == "combined":
                backend.write_read(b"x", 1)
            else:
                backend.transfer(b"x")
    finally:
        backend.close()


def test_aardvark_nack_and_invalid_reconfigure(tp):
    backend = open_backend("i2c", 1, {"driver": "totalphase-aardvark", "resource": "1234567890"})
    try:
        tp.status = 3
        with pytest.raises(IoConnectionError, match="NACK"):
            backend.write(b"")
        with pytest.raises(IoConfigError, match="address"):
            backend.configure(address=128)
        assert backend._address == 0x50
        with pytest.raises(IoConfigError, match="length"):
            backend.read(-1)
    finally:
        backend.close()


def test_cheetah_queue_and_release_after_failed_shift(tp):
    backend = open_backend("spi", 1, {"driver": "totalphase-cheetah", "resource": "1234567890",
                                      "chip_select": 2})
    try:
        assert backend.transfer(b"\x23\x45") == b"\x12\x12"
        assert ("ch_spi_queue_ss", 7, 4) in tp.calls
        tp.fail_shift = True
        with pytest.raises(IoConnectionError, match="vendor status -6"):
            backend.transfer(b"\x23")
        assert tp.calls[-5:] == [("ch_spi_queue_clear", 7), ("ch_spi_queue_ss", 7, 0),
                                 ("ch_spi_queue_oe", 7, 0), ("shift", 0),
                                 ("ch_spi_queue_clear", 7)]
        with pytest.raises(IoConfigError, match="chip_select"):
            backend.configure(chip_select=3)
    finally:
        backend.close()


def test_busy_serial_and_bad_configuration_do_not_open(tp):
    tp.busy = True
    with pytest.raises(IoConnectionError, match="in use"):
        open_backend("i2c", 1, {"driver": "totalphase-aardvark", "resource": "1234567890"})
    with pytest.raises(IoConfigError, match="bits_per_word"):
        open_backend("spi", 1, {"driver": "totalphase-cheetah", "bits_per_word": 16})
    with pytest.raises(IoConfigError, match="numeric"):
        open_backend("spi", 1, {"driver": "totalphase-cheetah", "resource": ""})
    assert tp.opened == 0


def test_initialization_failure_releases_handle(tp, monkeypatch):
    monkeypatch.setattr(tp, "aa_i2c_bitrate", lambda *args: -4)
    with pytest.raises(IoConnectionError, match="bitrate"):
        open_backend("i2c", 1, {"driver": "totalphase-aardvark", "resource": "1234567890"})
    assert tp.closed == 1


class Usb2AnyApi:
    def __init__(self):
        self.calls = []
        self.closed = 0
        self.short = False

    def u2aOpen(self, serial):
        self.calls.append(("open", serial))
        return 77

    def u2aClose(self, handle):
        self.closed += 1
        return 0

    def __getattr__(self, name):
        if name in ("u2aSuppressSplash", "u2aPower_Enable", "u2aSetReceiveTimeout",
                    "u2aI2C_Control", "u2aSPI_Control", "u2aI2C_RawWrite"):
            def call(*args):
                self.calls.append((name, *args))
                return 0
            return call
        raise AttributeError(name)

    def u2aI2C_RawRead(self, handle, addr, n, buf):
        for i in range(n):
            buf[i] = i
        return n - int(self.short)

    def u2aI2C_BlockWriteBlockRead(self, handle, addr, nw, wbuf, nr, rbuf):
        self.calls.append(("combined", addr, bytes(wbuf[:nw]), nr))
        for i in range(nr):
            rbuf[i] = 0xAB
        return 0

    def u2aSPI_WriteAndRead(self, handle, n, buf):
        for i in range(n):
            buf[i] ^= 0xFF
        return n - int(self.short)


@pytest.fixture
def ti(monkeypatch):
    fake = Usb2AnyApi()
    monkeypatch.setattr(usb2any, "load_api", lambda library: fake)
    yield fake
    assert not _usb._sessions


def test_usb2any_combined_status_and_spi_phase_mapping(ti):
    cfg = {"driver": "ti-usb2any", "resource": "AF14904609001C00"}
    i2c = open_backend("i2c", 1, cfg)
    spi = open_backend("spi", 1, cfg)
    try:
        assert i2c._session is spi._session
        i2c.configure(address=0x2FF, address_bits=10, clock_hz=400_000)
        assert i2c.write_read(b"\x42", 2) == b"\xab\xab"
        assert ("combined", 0x2FF, b"\x42", 2) in ti.calls
        assert ("u2aI2C_Control", 77, 1, 1, 1) in ti.calls
        i2c.write(b"")
        assert i2c.read(2) == b"\x00\x01"
        for mode in range(4):
            spi.configure(mode=mode, clock_hz=7_000_000)
            assert spi.actual_clock_hz == 6_000_000
            assert spi.transfer(b"\x55") == b"\xaa"
            assert ("u2aSPI_Control", 77, 1 - (mode & 1), mode >> 1, 1, 0, 1, 1, 0, 4) in ti.calls
        with pytest.raises(IoConfigError, match="length"):
            spi.transfer(bytes(256))
        ti.short = True
        with pytest.raises(IoConnectionError, match="short transfer"):
            spi.transfer(b"x")
        with pytest.raises(IoConnectionError, match="short transfer"):
            i2c.read(2)
    finally:
        i2c.close()
        spi.close()
    assert ti.closed == 1
    assert ("u2aPower_Enable", 77, 0, 0, 0) in ti.calls


def test_usb2any_rejects_invalid_clocks_before_open(ti):
    with pytest.raises(IoConfigError, match="clock_hz"):
        open_backend("i2c", 1, {"driver": "ti-usb2any", "clock_hz": 200_000})
    with pytest.raises(IoConfigError, match="clock_hz"):
        open_backend("spi", 1, {"driver": "ti-usb2any", "clock_hz": 1})
    with pytest.raises(IoConfigError, match="timeout_ms"):
        open_backend("spi", 1, {"driver": "ti-usb2any", "resource": "abc", "timeout_ms": 201})
    assert ti.calls == []


def test_usb2any_loader_binds_stdcall_exports(monkeypatch):
    class Function:
        pass

    class Dll:
        def __init__(self):
            self.exports = {}

        def __getattr__(self, name):
            if not name.startswith("_u2a"):
                raise AttributeError(name)
            fn = self.exports[name] = Function()
            return fn

    dll = Dll()
    monkeypatch.setattr(usb2any.sys, "platform", "win32")
    monkeypatch.setattr(usb2any.ctypes, "sizeof", lambda arg: 4)
    monkeypatch.setattr(usb2any.ctypes, "WinDLL", lambda name: dll, raising=False)
    usb2any.load_api.cache_clear()
    try:
        api = usb2any.load_api("test.dll")
        assert api.u2aSPI_Control is dll.exports["_u2aSPI_Control@36"]
        assert len(api.u2aI2C_BlockWriteBlockRead.argtypes) == 6
        assert api.u2aOpen.restype is usb2any.ctypes.c_int32
    finally:
        usb2any.load_api.cache_clear()


def test_missing_sdk_is_actionable(monkeypatch):
    def missing(name):
        raise ImportError("not installed")

    monkeypatch.setattr(totalphase, "import_module", missing)
    with pytest.raises(IoConnectionError, match="PYTHONPATH"):
        totalphase.load_api("aa")
    monkeypatch.setattr(totalphase, "import_module", lambda name: SimpleNamespace(AA_LIBRARY_LOADED=False))
    with pytest.raises(IoConnectionError, match="incompatible"):
        totalphase.load_api("aa")
