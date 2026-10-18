"""Unit tests for NI USB-6501 and USB-845x IO backends (fake native libraries)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import colosseum as col
import pytest
from colosseum.config import load_config
from colosseum.plugins import loader as plugin_loader
from colosseum_equipment import register as register_equipment
from colosseum_equipment.connections import close_all
from colosseum_equipment.exceptions import EquipmentCapabilityError
from colosseum_equipment.io.backends.ni import daqmx as daqmx_api
from colosseum_equipment.io.backends.ni import ni845x as ni845x_api
from colosseum_equipment.io.backends.ni import session845x
from colosseum_equipment.io.backends.ni.dio_845x import Ni845xDioBackend
from colosseum_equipment.io.backends.ni.dio_6501 import Ni6501DioBackend
from colosseum_equipment.io.backends.ni.i2c import Ni845xI2cBackend
from colosseum_equipment.io.backends.ni.models import check_i2c_clock, resolve_voltage
from colosseum_equipment.io.backends.ni.spi import Ni845xSpiBackend
from colosseum_equipment.io.exceptions import IoConfigError, IoConnectionError

if TYPE_CHECKING:
    from colosseum.context import RuntimeContext


def _hid(handle: Any) -> int:
    """Extract an integer id from a ctypes handle or bare int."""
    if handle is None:
        return 0
    if isinstance(handle, int):
        return handle
    value = getattr(handle, "value", handle)
    if value is None:
        return 0
    if isinstance(value, (bytes, bytearray)):
        return int.from_bytes(value, "little")
    return int(value)


def _set_handle(handle_p: Any, hid: int) -> None:
    target = getattr(handle_p, "_obj", handle_p)
    target.value = hid


def _set_out(ptr: Any, value: int) -> None:
    target = getattr(ptr, "_obj", ptr)
    target.value = value


class _EquipmentEntryPoint:
    name = "equipment"
    value = "colosseum_equipment:register"

    def load(self) -> Any:
        return register_equipment


@pytest.fixture
def equipment_plugins_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """Avoid loading sibling plugins that may lack optional deps in this env."""
    monkeypatch.setattr(
        plugin_loader,
        "entry_points_for_group",
        lambda _group: [_EquipmentEntryPoint()],
    )


class _FakeDaqmx:
    """Minimal DAQmx stand-in for ChanPerLine static DIO."""

    def __init__(self) -> None:
        self.tasks: dict[int, dict[str, Any]] = {}
        self._next = 1
        self.drive_type: int | None = None
        self.writes: list[list[int]] = []
        self.di_levels: dict[str, int] = {}

    def DAQmxCreateTask(self, _name: Any, handle_p: Any) -> int:
        hid = self._next
        self._next += 1
        self.tasks[hid] = {"lines": [], "kind": None, "started": False}
        _set_handle(handle_p, hid)
        return 0

    def DAQmxClearTask(self, handle: Any) -> int:
        self.tasks.pop(_hid(handle), None)
        return 0

    def DAQmxStartTask(self, handle: Any) -> int:
        self.tasks[_hid(handle)]["started"] = True
        return 0

    def DAQmxStopTask(self, handle: Any) -> int:
        _ = handle
        return 0

    def _parse_lines(self, channels: bytes | None) -> list[str]:
        text = (channels or b"").decode("ascii")
        return [part.strip() for part in text.split(",") if part.strip()]

    def DAQmxCreateDOChan(self, handle: Any, channels: bytes, _name: Any, _group: int) -> int:
        task = self.tasks[_hid(handle)]
        task["kind"] = "do"
        task["lines"] = self._parse_lines(channels)
        return 0

    def DAQmxCreateDIChan(self, handle: Any, channels: bytes, _name: Any, _group: int) -> int:
        task = self.tasks[_hid(handle)]
        task["kind"] = "di"
        task["lines"] = self._parse_lines(channels)
        return 0

    def DAQmxSetDOOutputDriveType(self, _handle: Any, _channels: bytes, drive: int) -> int:
        self.drive_type = int(drive)
        return 0

    def DAQmxWriteDigitalLines(
        self,
        handle: Any,
        _n: int,
        _auto: int,
        _timeout: float,
        _layout: int,
        data: Any,
        written: Any,
        _reserved: Any,
    ) -> int:
        task = self.tasks[_hid(handle)]
        values = [int(data[i]) for i in range(len(task["lines"]))]
        self.writes.append(values)
        for channel, level in zip(task["lines"], values, strict=True):
            self.di_levels[channel] = level
        _set_out(written, 1)
        return 0

    def DAQmxReadDigitalLines(
        self,
        handle: Any,
        _n: int,
        _timeout: float,
        _layout: int,
        data: Any,
        _size: int,
        read: Any,
        bytes_per: Any,
        _reserved: Any,
    ) -> int:
        task = self.tasks[_hid(handle)]
        for index, channel in enumerate(task["lines"]):
            data[index] = self.di_levels.get(channel, 0)
        _set_out(read, 1)
        _set_out(bytes_per, 1)
        return 0

    def DAQmxGetExtendedErrorInfo(self, buf: Any, _size: int) -> int:
        buf.value = b"fake daqmx error"
        return 0


class _FakeNi845x:
    """Minimal NI-845x stand-in covering open/lock/DIO/I2C/SPI."""

    def __init__(self) -> None:
        self._next = 1
        self.devices: dict[int, dict[str, Any]] = {}
        self.configs: dict[int, dict[str, Any]] = {}
        self.voltage: int | None = None
        self.i2c_writes: list[bytes] = []
        self.i2c_read_queue: list[bytes] = []
        self.spi_transfers: list[bytes] = []
        self.spi_miso: bytes = b""
        self.fail_i2c_status: int | None = None
        self.dio_direction = 0
        self.dio_value = 0
        self.dio_driver = 1
        self.pullup = 1
        self.closed_devices: list[int] = []

    def _new_handle(self, store: dict[int, dict[str, Any]], **fields: Any) -> int:
        hid = self._next
        self._next += 1
        store[hid] = dict(fields)
        return hid

    def ni845xOpen(self, resource: bytes, handle_p: Any) -> int:
        text = resource.decode("ascii") if isinstance(resource, (bytes, bytearray)) else str(resource)
        hid = self._new_handle(self.devices, resource=text, locks=0)
        _set_handle(handle_p, hid)
        return 0

    def ni845xClose(self, handle: Any) -> int:
        hid = _hid(handle)
        self.devices.pop(hid, None)
        self.closed_devices.append(hid)
        return 0

    def ni845xDeviceLock(self, handle: Any) -> int:
        self.devices[_hid(handle)]["locks"] += 1
        return 0

    def ni845xDeviceUnlock(self, handle: Any) -> int:
        self.devices[_hid(handle)]["locks"] -= 1
        return 0

    def ni845xSetIoVoltageLevel(self, _handle: Any, level: int) -> int:
        self.voltage = int(level)
        return 0

    def ni845xSetTimeout(self, _handle: Any, _ms: int) -> int:
        return 0

    def ni845xStatusToString(self, status: int, _size: int, buf: Any) -> None:
        buf.value = f"status {int(status)}".encode("ascii")

    def ni845xDioSetPortLineDirectionMap(self, _h: Any, _port: int, direction: int) -> int:
        self.dio_direction = int(direction)
        return 0

    def ni845xDioSetDriverType(self, _h: Any, _port: int, driver: int) -> int:
        self.dio_driver = int(driver)
        return 0

    def ni845xDioWritePort(self, _h: Any, _port: int, value: int) -> int:
        self.dio_value = int(value) & self.dio_direction
        return 0

    def ni845xDioReadPort(self, _h: Any, _port: int, value_p: Any) -> int:
        _set_out(value_p, self.dio_value)
        return 0

    def ni845xDioWriteLine(self, _h: Any, _port: int, line: int, value: int) -> int:
        bit = 1 << int(line)
        if value:
            self.dio_value |= bit
        else:
            self.dio_value &= ~bit
        return 0

    def ni845xDioReadLine(self, _h: Any, _port: int, line: int, value_p: Any) -> int:
        _set_out(value_p, 1 if self.dio_value & (1 << int(line)) else 0)
        return 0

    def ni845xI2cConfigurationOpen(self, handle_p: Any) -> int:
        hid = self._new_handle(self.configs, kind="i2c", address=0, clock_khz=100)
        _set_handle(handle_p, hid)
        return 0

    def ni845xI2cConfigurationClose(self, handle: Any) -> int:
        self.configs.pop(_hid(handle), None)
        return 0

    def ni845xI2cConfigurationSetAddress(self, handle: Any, address: int) -> int:
        self.configs[_hid(handle)]["address"] = int(address)
        return 0

    def ni845xI2cConfigurationSetAddressSize(self, handle: Any, size: int) -> int:
        self.configs[_hid(handle)]["address_size"] = int(size)
        return 0

    def ni845xI2cConfigurationSetClockRate(self, handle: Any, rate: int) -> int:
        self.configs[_hid(handle)]["clock_khz"] = int(rate)
        return 0

    def ni845xI2cSetPullupEnable(self, _h: Any, enabled: int) -> int:
        self.pullup = int(enabled)
        return 0

    @staticmethod
    def _buffer_bytes(data: Any, size: int) -> bytes:
        if not data or size <= 0:
            return b""
        if isinstance(data, (bytes, bytearray)):
            return bytes(data[:size])
        raw = getattr(data, "raw", None)
        if isinstance(raw, (bytes, bytearray)):
            return bytes(raw[:size])
        return bytes(bytearray(data[i] for i in range(size)))

    def ni845xI2cWrite(self, _dev: Any, _cfg: Any, size: int, data: Any) -> int:
        if self.fail_i2c_status is not None:
            return self.fail_i2c_status
        self.i2c_writes.append(self._buffer_bytes(data, size))
        return 0

    def ni845xI2cRead(self, _dev: Any, _cfg: Any, size: int, data: Any) -> int:
        if self.fail_i2c_status is not None:
            return self.fail_i2c_status
        payload = self.i2c_read_queue.pop(0) if self.i2c_read_queue else bytes(size)
        if data and size:
            for i in range(min(size, len(payload))):
                data[i] = payload[i]
        return 0

    def ni845xI2cWriteRead(
        self,
        _dev: Any,
        _cfg: Any,
        wsize: int,
        wdata: Any,
        rsize: int,
        rdata: Any,
    ) -> int:
        self.ni845xI2cWrite(_dev, _cfg, wsize, wdata)
        return self.ni845xI2cRead(_dev, _cfg, rsize, rdata)

    def ni845xSpiConfigurationOpen(self, handle_p: Any) -> int:
        hid = self._new_handle(
            self.configs, kind="spi", cs=0, clock_khz=1000, mode_pol=0, mode_pha=0,
        )
        _set_handle(handle_p, hid)
        return 0

    def ni845xSpiConfigurationClose(self, handle: Any) -> int:
        self.configs.pop(_hid(handle), None)
        return 0

    def ni845xSpiConfigurationSetChipSelect(self, handle: Any, cs: int) -> int:
        self.configs[_hid(handle)]["cs"] = int(cs)
        return 0

    def ni845xSpiConfigurationSetClockRate(self, handle: Any, rate: int) -> int:
        self.configs[_hid(handle)]["clock_khz"] = int(rate)
        return 0

    def ni845xSpiConfigurationSetClockPolarity(self, handle: Any, pol: int) -> int:
        self.configs[_hid(handle)]["mode_pol"] = int(pol)
        return 0

    def ni845xSpiConfigurationSetClockPhase(self, handle: Any, pha: int) -> int:
        self.configs[_hid(handle)]["mode_pha"] = int(pha)
        return 0

    def ni845xSpiConfigurationSetNumBitsPerSample(self, handle: Any, bits: int) -> int:
        self.configs[_hid(handle)]["bits"] = int(bits)
        return 0

    def ni845xSpiWriteRead(
        self,
        _dev: Any,
        _cfg: Any,
        wsize: int,
        wdata: Any,
        rsize_p: Any,
        rdata: Any,
    ) -> int:
        payload = self._buffer_bytes(wdata, wsize)
        self.spi_transfers.append(payload)
        reply = self.spi_miso[:wsize] if self.spi_miso else payload
        if rdata and wsize:
            for i in range(min(wsize, len(reply))):
                rdata[i] = reply[i]
        _set_out(rsize_p, wsize)
        return 0


@pytest.fixture(autouse=True)
def _reset_ni_loaders() -> None:
    yield
    session845x.reset_sessions()
    daqmx_api.reset_daqmx_loader()
    ni845x_api.reset_ni845x_loader()


def test_ni6501_line_mapping_and_drive(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeDaqmx()
    daqmx_api.set_daqmx_library(fake)
    # lines 0,1 output; rest input — port0 bits 0-1
    backend = Ni6501DioBackend(resource="Dev1", direction=0b11, drive="push-pull")
    assert fake.drive_type == daqmx_api.DAQmx_Val_ActiveDrive
    backend.write_port(0b11)
    assert fake.writes[-1] == [1, 1]
    # Simulate external levels on input line 2
    fake.di_levels["Dev1/port0/line2"] = 1
    value = backend.read_port()
    assert value & 0b100
    assert value & 0b11 == 0b11
    backend.write_pin(0, False)
    assert fake.writes[-1][0] == 0
    backend.close()
    assert not fake.tasks


def test_ni6501_open_drain_default(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeDaqmx()
    daqmx_api.set_daqmx_library(fake)
    backend = Ni6501DioBackend(resource="Dev1", direction=0xFF)
    assert fake.drive_type == daqmx_api.DAQmx_Val_OpenCollector
    with pytest.raises(EquipmentCapabilityError, match="set_pull"):
        backend.set_pull(0, "up")
    backend.close()


def test_ni6501_rejects_bad_drive() -> None:
    daqmx_api.set_daqmx_library(_FakeDaqmx())
    with pytest.raises(IoConfigError, match="drive"):
        Ni6501DioBackend(resource="Dev1", direction=0, drive="magic")


def test_model_voltage_and_clock_limits() -> None:
    assert resolve_voltage("usb-8451", None) == 3.3
    with pytest.raises(IoConfigError, match="3.3"):
        resolve_voltage("usb-8451", 1.8)
    assert resolve_voltage("usb-8452", 1.8) == 1.8
    check_i2c_clock("usb-8451", 250_000)
    with pytest.raises(IoConfigError, match="250000"):
        check_i2c_clock("usb-8451", 400_000)
    with pytest.raises(IoConfigError, match="3300000"):
        check_i2c_clock("usb-8452", 4_000_000)


def test_845x_shared_session_voltage_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeNi845x()
    ni845x_api.set_ni845x_library(fake)
    first = Ni845xDioBackend(
        resource="USB-8452", model="usb-8452", direction=0x0F, voltage=1.8,
    )
    with pytest.raises(IoConfigError, match="already opened"):
        Ni845xI2cBackend(
            resource="USB-8452", model="usb-8452", voltage=3.3, address=0x50,
        )
    first.close()


def test_845x_dio_i2c_spi_transactions(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeNi845x()
    ni845x_api.set_ni845x_library(fake)
    dio = Ni845xDioBackend(
        resource="USB-8452", model="usb-8452", direction=0x0F, voltage=3.3,
    )
    dio.write_port(0b1010)
    assert fake.dio_value == 0b1010
    assert dio.read_pin(1) is True

    i2c = Ni845xI2cBackend(
        resource="USB-8452", model="usb-8452", voltage=3.3, clock_hz=100_000, address=0x50,
    )
    i2c.write(b"")  # address ACK probe
    assert fake.i2c_writes[-1] == b""
    fake.i2c_read_queue.append(b"\x12\x34")
    assert i2c.write_read(b"\x00", 2) == b"\x12\x34"

    spi = Ni845xSpiBackend(
        resource="USB-8452",
        model="usb-8452",
        voltage=3.3,
        clock_hz=1_000_000,
        mode=3,
        chip_select=2,
    )
    fake.spi_miso = b"\xAA\xBB"
    assert spi.transfer(b"\x01\x02") == b"\xAA\xBB"
    cfg = next(c for c in fake.configs.values() if c.get("kind") == "spi")
    assert cfg["cs"] == 2
    assert cfg["mode_pol"] == ni845x_api.kNi845xSpiClockPolarityIdleHigh
    assert cfg["mode_pha"] == ni845x_api.kNi845xSpiClockPhaseSecondEdge

    spi.close()
    i2c.close()
    dio.close()
    assert fake.closed_devices


def test_8451_rejects_fast_spi(monkeypatch: pytest.MonkeyPatch) -> None:
    ni845x_api.set_ni845x_library(_FakeNi845x())
    with pytest.raises(IoConfigError, match="12000000"):
        Ni845xSpiBackend(
            resource="USB-8451", model="usb-8451", clock_hz=20_000_000,
        )


def test_i2c_nack_maps_to_connection_error(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeNi845x()
    fake.fail_i2c_status = -1
    ni845x_api.set_ni845x_library(fake)
    i2c = Ni845xI2cBackend(resource="USB-8452", model="usb-8452", address=0x50)
    with pytest.raises(IoConnectionError, match="I2cWrite"):
        i2c.write(b"\x00")
    i2c.close()


def test_factory_and_public_api_sim(
    io_runtime_context: RuntimeContext,
    io_bench,
    equipment_plugins_only: None,
) -> None:
    _ = io_runtime_context, equipment_plugins_only
    load_config(
        io_bench(
            """
            [io.dio]
            dio_id = 1
            driver = sim
            port_lines = 8
            direction = 0xFF

            [io.i2c]
            i2c_id = 1
            driver = sim
            address = 0x50
            read_data = "aabb"

            [io.spi]
            spi_id = 1
            driver = sim
            mode = 0
            chip_select = 1
            """,
        ),
    )
    col.io.i2c.write(i2c_id=1, data=b"\x01")
    assert col.io.i2c.read(i2c_id=1, nbytes=2, key="i2c_rd") == b"\xaa\xbb"
    assert col.io.i2c.write_read(i2c_id=1, write_data=b"\x00", read_nbytes=2, key="i2c_wr") == b"\xaa\xbb"
    assert col.io.spi.transfer(spi_id=1, data=b"\x10\x20", key="spi_x") == b"\x10\x20"
    col.io.spi.configure(spi_id=1, mode=2, chip_select=3)
    close_all()


def test_sim_i2c_nack(
    io_runtime_context: RuntimeContext,
    io_bench,
    equipment_plugins_only: None,
) -> None:
    _ = io_runtime_context, equipment_plugins_only
    load_config(
        io_bench(
            """
            [io.i2c]
            i2c_id = 1
            driver = sim
            nack = true
            """,
        ),
    )
    with pytest.raises(IoConnectionError, match="NACK"):
        col.io.i2c.write(i2c_id=1, data=b"")


def test_factory_ni_drivers_with_fakes(monkeypatch: pytest.MonkeyPatch) -> None:
    from colosseum_equipment.io.backends import factory as io_factory

    daqmx_api.set_daqmx_library(_FakeDaqmx())
    ni845x_api.set_ni845x_library(_FakeNi845x())
    dio6501 = io_factory.open_dio_backend(
        1, {"driver": "ni-6501", "resource": "Dev1", "direction": 0xFF},
    )
    assert isinstance(dio6501, Ni6501DioBackend)
    dio6501.close()
    dio845 = io_factory.open_dio_backend(
        2,
        {
            "driver": "ni-845x",
            "resource": "USB-8452",
            "model": "usb-8452",
            "direction": 0x0F,
        },
    )
    assert isinstance(dio845, Ni845xDioBackend)
    dio845.close()
    i2c = io_factory.open_i2c_backend(
        1,
        {
            "driver": "ni-845x",
            "resource": "USB-8452",
            "model": "usb-8452",
            "address": 0x48,
        },
    )
    assert isinstance(i2c, Ni845xI2cBackend)
    i2c.close()


def test_close_all_releases_845x_session(
    io_runtime_context: RuntimeContext,
    io_bench,
    monkeypatch: pytest.MonkeyPatch,
    equipment_plugins_only: None,
) -> None:
    _ = monkeypatch, equipment_plugins_only
    ctx = io_runtime_context
    fake = _FakeNi845x()
    ni845x_api.set_ni845x_library(fake)
    load_config(
        io_bench(
            """
            [io.i2c]
            i2c_id = 1
            driver = ni-845x
            resource = "USB-8452"
            model = usb-8452
            address = 0x50
            """,
        ),
    )
    col.io.i2c.write(i2c_id=1, data=b"\x00")
    assert "io:backend:i2c:1" in ctx.resource_cache
    close_all()
    assert "io:backend:i2c:1" not in ctx.resource_cache
    assert fake.closed_devices
