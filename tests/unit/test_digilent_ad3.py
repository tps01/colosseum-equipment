"""Exercise all AD3 roles through the public API with a recording WaveForms SDK."""

from __future__ import annotations

import csv
import ctypes as ct

import colosseum as col
import pytest
from colosseum.exceptions import ProceduralFault
from colosseum_equipment.connections import close_all
from colosseum_equipment.exceptions import EquipmentCapabilityError, EquipmentResponseError, EquipmentTimeoutError
from colosseum_equipment.io.exceptions import IoConfigError
from colosseum_equipment.transports import digilent


class FakeDwf:
    def __init__(self):
        self.events = []
        self.serials = [b"210000000001", b"210000000000"]
        self.busy = False
        self.state = 2
        self.fail = ""

    def __getattr__(self, name):
        if not name.startswith("FDwf"):
            raise AttributeError(name)
        operation = name.removeprefix("FDwf")

        def call(*args):
            values = tuple(getattr(arg, "value", arg) for arg in args)
            self.events.append((operation, *values))
            outputs = {
                "Enum": (len(self.serials),),
                "EnumDeviceIsOpened": (int(self.busy),),
                "DeviceOpen": (77,),
                "AnalogInBufferSizeInfo": (2, 8192),
                "AnalogInFrequencyInfo": (1.0, 125e6),
                "AnalogInStatus": (self.state,),
                "AnalogInStatusSamplesValid": (4,),
                "AnalogInFrequencyGet": (2000.0,),
                "AnalogInTriggerPositionStatus": (0.00025,),
                "AnalogOutNodeFrequencyInfo": (0.01, 25e6),
                "DigitalIOInputStatus": (0x10002,),
            }
            if operation in outputs:
                for target, value in zip(args[-len(outputs[operation]):], outputs[operation], strict=True):
                    target._obj.value = value
            elif operation == "EnumSN":
                args[1].value = self.serials[args[0]]
            elif operation == "AnalogInStatusData":
                args[2][:] = [-1.0, 0.0, 1.0, 0.0]
            elif operation == "GetLastErrorMsg":
                args[0].value = b"fake USB failure"
            return operation != self.fail

        return call


@pytest.fixture
def sdk(unit_runtime_context, monkeypatch):
    library = FakeDwf()
    monkeypatch.setattr(digilent, "_load_library", lambda name: library)
    col.config.load_config("examples/configs/config.digilent-ad3.toml")
    try:
        yield library
    finally:
        close_all()


def test_shared_device_scope_wavegen_and_gpio(sdk, unit_runtime_context):
    col.equipment.asg.set_waveform(asg_id=1, waveform="triangle", channel=2)
    col.equipment.asg.set_frequency(asg_id=1, frequency=2500, channel=2)
    col.equipment.asg.set_amplitude_vpp(asg_id=1, vpp=2, channel=2)
    assert not any(event[0].startswith("AnalogOut") for event in sdk.events)
    col.equipment.asg.set_output(asg_id=1, enabled=True, channel=2)
    assert ("AnalogOutNodeFunctionSet", 77, 1, 0, 3) in sdk.events
    assert ("AnalogOutNodeFrequencySet", 77, 1, 0, 2500.0) in sdk.events
    assert ("AnalogOutNodeAmplitudeSet", 77, 1, 0, 1.0) in sdk.events
    assert ("AnalogOutConfigure", 77, 1, 1) in sdk.events
    with pytest.raises(ValueError, match="±5 V"):
        col.equipment.asg.set_offset_v(asg_id=1, offset_v=4.5, channel=2)

    col.equipment.oscope.set_channel_display(oscope_id=1, channel=2, enabled=False)
    col.equipment.oscope.set_record_length(oscope_id=1, points=4)
    col.equipment.oscope.set_trigger_source(oscope_id=1, source="CHAN1")
    assert col.equipment.oscope.acquire(oscope_id=1)
    assert ("AnalogInTriggerSourceSet", 77, 2) in sdk.events
    assert ("AnalogInTriggerChannelSet", 77, 0) in sdk.events
    assert col.equipment.oscope.measure_vpp(oscope_id=1, key="vpp") == 2.0
    assert col.equipment.oscope.measure_vrms(oscope_id=1, key="rms") == pytest.approx(2**-0.5)
    assert col.equipment.oscope.measure_vmin(oscope_id=1, key="vmin") == -1.0
    assert col.equipment.oscope.measure_vmax(oscope_id=1, key="vmax") == 1.0
    col.equipment.oscope.save_waveform(oscope_id=1, channel=1, path="capture.csv", key="capture")
    with (unit_runtime_context.output_dir / "capture.csv").open(newline="") as handle:
        rows = list(csv.reader(handle))
    assert rows[0] == ["time_s", "voltage_v"]
    assert [float(row[0]) for row in rows[1:]] == pytest.approx([-0.00075, -0.00025, 0.00025, 0.00075])
    assert [float(row[1]) for row in rows[1:]] == [-1, 0, 1, 0]
    assert sdk.events.count(("AnalogInConfigure", 77, 1, 1)) == 1

    col.io.dio.configure(dio_id=1, direction=1, initial=1)
    assert sdk.events[-3:] == [
        ("DigitalIOOutputSet", 77, 1), ("DigitalIOOutputEnableSet", 77, 1), ("DigitalIOConfigure", 77),
    ]
    assert col.io.dio.read_port(dio_id=1, key="port") == 2
    assert col.io.dio.read_pin(dio_id=1, line=1, key="pin") is True
    col.io.dio.write_pin(dio_id=1, line=0, value=False)
    assert ("DigitalIOOutputSet", 77, 0) in sdk.events
    with pytest.raises(IoConfigError, match="not configured as output"):
        col.io.dio.write_pin(dio_id=1, line=1, value=True)
    with pytest.raises(EquipmentCapabilityError, match="per-pin"):
        col.io.dio.set_pull(dio_id=1, line=1, pull="up")

    assert [event[:2] for event in sdk.events if event[0] == "DeviceOpen"] == [("DeviceOpen", 1)]
    assert not any(event[0] == "DeviceClose" for event in sdk.events)
    close_all()
    close_all()
    assert sdk.events[-1] == ("DeviceClose", 77)
    assert sdk.events.count(("DeviceClose", 77)) == 1
    disable_index = sdk.events.index(("AnalogOutNodeEnableSet", 77, 1, 0, 0))
    assert sdk.events[disable_index + 1:disable_index + 3] == [
        ("AnalogOutConfigure", 77, 1, 3), ("AnalogOutConfigure", 77, 1, 0),
    ]
    assert sdk.events[-3:-1] == [("DigitalIOReset", 77), ("DigitalIOConfigure", 77)]


def test_scope_timeout_abort_and_rearm_do_not_return_stale_data(sdk):
    sdk.state = 1
    col.equipment.oscope.arm_single(oscope_id=1)
    with pytest.raises(EquipmentTimeoutError):
        col.equipment.oscope.wait_complete(oscope_id=1, timeout_s=0.001)
    with pytest.raises(EquipmentResponseError, match="No completed"):
        col.equipment.oscope.measure_vpp(oscope_id=1, key="pending")
    sdk.state = 2
    col.equipment.oscope.wait_complete(oscope_id=1, timeout_s=0.1)
    assert col.equipment.oscope.measure_vpp(oscope_id=1, key="done") == 2.0
    col.equipment.oscope.abort(oscope_id=1)
    with pytest.raises(EquipmentResponseError, match="No completed"):
        col.equipment.oscope.measure_vpp(oscope_id=1, key="aborted")


@pytest.mark.parametrize(("serials", "busy", "match"), [
    ([b"210000000001"], False, "was not found"),
    ([b"210000000000"], True, "is busy"),
])
def test_serial_selection_reports_missing_or_busy(sdk, serials, busy, match):
    sdk.serials, sdk.busy = serials, busy
    with pytest.raises(ProceduralFault, match=match):
        col.equipment.oscope.arm_single(oscope_id=1)
    assert not any(event[0] == "DeviceOpen" for event in sdk.events)


@pytest.mark.parametrize(("platform", "filename"), [("win32", "dwf.dll"), ("linux", "libdwf.so")])
def test_missing_runtime_has_installation_message(unit_runtime_context, monkeypatch, platform, filename):
    class MissingLibrary:
        def __call__(self, name):
            assert name == filename
            raise OSError("test: missing library")

    monkeypatch.setattr(digilent, "sys", type("Platform", (), {"platform": platform}))
    monkeypatch.setattr(ct, "CDLL", MissingLibrary())
    col.config.load_config("examples/configs/config.digilent-ad3.toml")
    with pytest.raises(ProceduralFault, match="install Digilent WaveForms with Adept"):
        col.equipment.oscope.arm_single(oscope_id=1)


def test_failed_device_setup_closes_handle_and_can_retry(sdk):
    sdk.fail = "DeviceAutoConfigureSet"
    with pytest.raises(ProceduralFault, match="fake USB failure"):
        col.equipment.oscope.arm_single(oscope_id=1)
    assert sdk.events[-1] == ("DeviceClose", 77)
    sdk.fail = ""
    col.equipment.oscope.arm_single(oscope_id=1)
    assert col.equipment.oscope.measure_vmax(oscope_id=1, key="done", optional=True) is None
    col.equipment.oscope.wait_complete(oscope_id=1, timeout_s=1)
    assert col.equipment.oscope.measure_vmax(oscope_id=1, key="complete") == 1.0
