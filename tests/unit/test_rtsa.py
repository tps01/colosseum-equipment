"""RTSA factory routing and SCPI delegation."""

from __future__ import annotations

import tarfile
import builtins
from typing import TYPE_CHECKING
from unittest.mock import Mock

import numpy as np
import pytest
from colosseum_equipment.exceptions import EquipmentCapabilityError, EquipmentResponseError
from colosseum_equipment.instruments.factory import build_instrument
from colosseum_equipment.instruments.rtsa.generic import GenericRtsa
from colosseum_equipment.instruments.rtsa.iq_export import (
    write_capture_iq,
    write_iq_mat,
)
from colosseum_equipment.instruments.rtsa.tektronix_rsa5100b import TektronixRSA5100BRtsa
from colosseum_equipment.instruments.vsg.iq_load import load_iq_interleaved_i16
from colosseum_equipment.protocols.scpi import format_definite_length_block
from scipy.io import loadmat

from tests.support.stubs import RfStubTransport


@pytest.mark.parametrize(("kind", "model", "query", "status"), [
    ("speca", "keysight-n9010b", "CAL:ALL?", "0"),
    ("rtsa", "tektronix-rsa5100b", "*CAL", "1"),
    ("rtsa", "tektronix-rsa5103b", "*CAL", "1"),
    ("rtsa", "tektronix-rsa5115b", "*CAL", "1"),
    ("rtsa", "tektronix-rsa5126b", "*CAL", "1"),
])
def test_align_all_uses_model_status_and_restores_timeout(
    unit_runtime_context, monkeypatch, kind, model, query, status,
):
    from colosseum_equipment.api import rtsa, speca

    transport = RfStubTransport()
    transport._timeout = 5.0
    timeout = Mock(side_effect=lambda value: setattr(transport, "_timeout", value))
    read = Mock(return_value=status)
    monkeypatch.setattr(transport, "set_timeout_s", timeout, raising=False)
    monkeypatch.setattr(transport, "query", read)
    inst = build_instrument(kind, 1, {"model": model}, transport)
    api = speca if kind == "speca" else rtsa
    monkeypatch.setattr(api, "get_cached_instrument", lambda *args: inst)
    ids = {f"{kind}_id": 1}
    read.assert_not_called()

    api.align_all(**ids)
    read.assert_called_once_with(query)
    assert [call.args for call in timeout.call_args_list] == [(600.0,), (5.0,)]
    assert transport._timeout == 5.0

    for reply in (str(1 - int(status)), "invalid"):
        read.return_value = reply
        with pytest.raises(EquipmentResponseError, match="alignment"):
            api.align_all(**ids)
        assert transport._timeout == 5.0
    read.side_effect = TimeoutError("alignment timed out")
    with pytest.raises(TimeoutError, match="alignment timed out"):
        api.align_all(**ids)
    assert transport._timeout == 5.0

    transport._timeout = 650.0
    read.side_effect = None
    read.return_value = status
    timeout.reset_mock()
    api.align_all(**ids)
    timeout.assert_not_called()
    assert not transport.written


@pytest.mark.parametrize(("kind", "model"), [
    ("speca", "generic"), ("speca", "keysight-e4440a"),
    ("rtsa", "generic"), ("rtsa", "tektronix-rsa6000"), ("rtsa", "tektronix-rsa6114a"),
])
def test_unverified_analyzer_alignment_does_not_send_a_command(kind, model, monkeypatch):
    transport = RfStubTransport()
    read = Mock()
    monkeypatch.setattr(transport, "query", read)
    inst = build_instrument(kind, 1, {"model": model}, transport)
    with pytest.raises(EquipmentCapabilityError, match="align_all"):
        inst.align_all()
    read.assert_not_called()
    assert not transport.written


@pytest.mark.parametrize("model", ["tektronix-rsa5115b", "tektronix-rsa5126b"])
def test_native_rsa_explicit_preset(unit_runtime_context, monkeypatch, model):
    from colosseum_equipment.api import rtsa

    transport = RfStubTransport()
    read = Mock(return_value="1")
    monkeypatch.setattr(transport, "query", read)
    inst = build_instrument("rtsa", 1, {"model": model}, transport)
    monkeypatch.setattr(rtsa, "get_cached_instrument", lambda *args: inst)
    assert not transport.written
    read.assert_not_called()

    rtsa.preset(rtsa_id=1)
    assert transport.written == ["*RST"]
    read.assert_called_once_with("*OPC?")


@pytest.mark.parametrize("file_format", ["bin", "iq.tar"])
def test_capture_non_mat_does_not_import_scipy(tmp_path, monkeypatch, file_format):
    original_import = builtins.__import__

    def import_without_scipy(name, *args, **kwargs):
        if name == "scipy" or name.startswith("scipy."):
            raise AssertionError("Non-MAT export must not import SciPy")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", import_without_scipy)
    samples = np.array([0.5 + 0.25j, -0.5 + 0j], dtype=np.complex64)
    path = tmp_path / f"capture.{file_format}"
    write_capture_iq(path, samples, file_format=file_format, sample_format="f32")
    expected = np.array([0.5, 0.25, -0.5, 0.0], dtype="<f4").tobytes()
    if file_format == "bin":
        assert path.read_bytes() == expected
    else:
        with tarfile.open(path) as archive:
            assert archive.extractfile("iq.bin").read() == expected

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize("model", ["signalhound-bb60c-spike", "signalhound-sm200c-spike"])
def test_spike_sample_rate_config_and_runtime(model):
    transport = RfStubTransport()
    inst = build_instrument("rtsa", 1, {"model": model, "sample_rate_hz": 1e6}, transport)
    assert transport.written.count("SENS:ZS:CAP:SRAT 1000000.0") == 1
    inst.set_sample_rate(2e6)
    assert transport.written[-1] == "SENS:ZS:CAP:SRAT 2000000.0"


@pytest.mark.parametrize(
    "model,replies",
    [
        ("tektronix-rsa6000", {"FETCh:RFIN:RECord:IDS?": "4,7", "FETCh:RFIN:IQ:HEADer? 4": "0,12500000,3"}),
        ("tektronix-rsa5115b", {"FETCh:RFIN:RECord:IDS?": "4,7", "FETCh:RFIN:IQ:HEADer? 4": "0,12500000,3"}),
        ("signalhound-bb60c-spike", {"SENS:ZS:CAP:SRAT?": "12500000"}),
    ],
)
def test_measure_sample_rate_records_readback(unit_runtime_context, monkeypatch, model, replies):
    from colosseum_equipment.api import rtsa

    transport = RfStubTransport(replies)
    inst = build_instrument("rtsa", 1, {"model": model}, transport)
    monkeypatch.setattr(rtsa, "get_cached_instrument", lambda *args: inst)
    from unittest.mock import patch

    with patch.object(transport, "query", wraps=transport.query) as query:
        assert rtsa.measure_sample_rate(rtsa_id=1, key="replay_rate") == 12_500_000
    assert [call.args[0] for call in query.call_args_list] == list(replies)
    row = unit_runtime_context.db.get_measurement("equipment", "rtsa.measure_sample_rate", "replay_rate", row_index=0)
    assert row is not None
    assert row.value == 12_500_000


def test_measure_sample_rate_rejects_no_tek_record(unit_runtime_context, monkeypatch):
    from colosseum_equipment.api import rtsa

    transport = RfStubTransport({"FETCh:RFIN:RECord:IDS?": "-1,-1"})
    inst = build_instrument("rtsa", 1, {"model": "tektronix-rsa6000"}, transport)
    monkeypatch.setattr(rtsa, "get_cached_instrument", lambda *args: inst)
    from unittest.mock import patch

    with patch.object(transport, "query", wraps=transport.query) as query:
        with pytest.raises(EquipmentResponseError, match="No completed IQ record"):
            rtsa.measure_sample_rate(rtsa_id=1, key="replay_rate")
    query.assert_called_once_with("FETCh:RFIN:RECord:IDS?")


@pytest.mark.parametrize("rate", [0, -1, float("nan"), float("inf"), -float("inf")])
def test_invalid_sample_rate_never_writes(rate, unit_runtime_context, monkeypatch):
    from colosseum_equipment.api import rtsa

    transport = RfStubTransport()
    inst = build_instrument("rtsa", 1, {"model": "signalhound-bb60c-spike"}, transport)
    monkeypatch.setattr(rtsa, "get_cached_instrument", lambda *args: inst)
    before = list(transport.written)
    with pytest.raises(ValueError, match="finite and positive"):
        rtsa.set_sample_rate(rtsa_id=1, sample_rate_hz=rate)
    with pytest.raises(ValueError, match="finite and positive"):
        inst.set_sample_rate(rate)
    assert transport.written == before
    with pytest.raises(ValueError, match="finite and positive"):
        build_instrument("rtsa", 1, {"model": "signalhound-bb60c-spike", "sample_rate_hz": rate}, transport)
    assert not any("SRAT" in cmd for cmd in transport.written)


@pytest.mark.parametrize("model", [
    "generic", "rigol-rsa3030", "siglent-ssa3032x-r", "tektronix-rsa5100b",
    "tektronix-rsa5115b", "tektronix-rsa6114a",
])
def test_unsupported_sample_rate_refuses_without_writes(model):
    transport = RfStubTransport()
    inst = build_instrument("rtsa", 1, {"model": model}, transport)
    before = list(transport.written)
    with pytest.raises(EquipmentCapabilityError, match="set_sample_rate") as error:
        inst.set_sample_rate(1e6)
    if model.startswith("tektronix"):
        assert "acquisition bandwidth" in str(error.value)
    assert transport.written == before
    with pytest.raises(EquipmentCapabilityError, match="set_sample_rate"):
        build_instrument("rtsa", 1, {"model": model, "sample_rate_hz": 1e6}, transport)


def test_sample_rate_parameters_and_broadcast(unit_runtime_context, monkeypatch):
    from colosseum_equipment.api import rtsa
    from colosseum_equipment.api import _broadcast
    from colosseum_equipment.exceptions import EquipmentError

    transports = [RfStubTransport() for _ in range(3)]
    instruments = [build_instrument("rtsa", i + 1, {"model": model}, transport)
                   for i, (model, transport) in enumerate(zip(
                       ["signalhound-bb60c-spike", "generic", "signalhound-sm200c-spike"], transports))]
    monkeypatch.setattr(rtsa, "get_cached_instrument", lambda kind, index: instruments[index - 1])
    monkeypatch.setattr(_broadcast, "resolve_equipment_ids", lambda *args: [1, 2, 3])
    unit_runtime_context.parameters_map = {"iq_rate": {"sample_rate_hz": 2e6}}
    rtsa.set_sample_rate(rtsa_id=1, sample_rate_hz=1e6, key="iq_rate")
    assert transports[0].written[-1] == "SENS:ZS:CAP:SRAT 2000000.0"
    with pytest.raises(EquipmentError, match="failed ids 2"):
        rtsa.set_sample_rate(rtsa_id="all", sample_rate_hz=3e6)
    assert transports[0].written[-1] == transports[2].written[-1] == "SENS:ZS:CAP:SRAT 3000000.0"
    assert not transports[1].written


def test_generic_rtsa_control_commands_write_scpi() -> None:
    transport = RfStubTransport({"*OPC?": "1", "TRAC:IQ:POIN?": "1024"})
    inst = build_instrument(
        "rtsa",
        1,
        {"model": "generic", "center_freq": 2.5e9, "span": 20e6, "rbw": 100e3},
        transport,
    )
    assert isinstance(inst, GenericRtsa)

    inst.set_acq_time(0.001)
    inst.set_continuous_run(False)
    inst.set_num_samples(1024)
    inst.set_trigger_source("EXT")
    inst.set_trigger_level(-20.0)
    inst.set_trigger_position(0.0)
    inst.run()
    assert inst.get_num_samples() == 1024

    assert transport.written == [
        "FREQ:CENT 2500000000.000000",
        "FREQ:SPAN 20000000.000000",
        "BAND:RES 100000.000000",
        "SWE:TIME 0.001000000",
        "INIT:CONT OFF",
        "TRAC:IQ:POIN 1024",
        "TRIG:SOUR EXT",
        "TRIG:LEV -20.000",
        "TRIG:POS 0.000",
        "INIT:IMM",
    ]


def test_generic_rtsa_save_iq_data(unit_runtime_context) -> None:
    _ = unit_runtime_context
    transport = RfStubTransport(
        {
            "*OPC?": "1",
            "FREQ:CENT?": "1000000000.0",
            "FREQ:SPAN?": "10000000.0",
            "TRAC:IQ:POIN?": "512",
            "__raw__": b"#14dead",
        },
    )
    inst = build_instrument("rtsa", 1, {"model": "generic"}, transport)
    path = inst.save_IQ_data("captures/generic_iq.bin", file_format="bin")
    assert path.exists()
    assert path.read_bytes() == b"dead"
    assert "TRAC:IQ:DATA?" in transport.written


def test_tek_rtsa_setters_write_scpi() -> None:
    transport = RfStubTransport({"DISP:WIND:ACT:MEAS?": "SPECtrum", "*OPC?": "1"})
    inst = build_instrument("rtsa", 1, {"model": "tektronix-rsa5100b"}, transport)
    assert isinstance(inst, TektronixRSA5100BRtsa)

    inst.set_center_freq(2.5e9)
    inst.set_span(20e6)
    inst.set_bandwidth(100e3)
    inst.set_trigger_source("EXTFront")
    inst.set_trigger_level(-20.0)
    inst.run()

    assert "DISP:SPEC:FREQ:OFFS 2500000000.000000" in transport.written
    assert "TRIG:SOUR EXTFront" in transport.written
    assert "INIT:IMM" in transport.written


def test_tek_save_iq_data_iq_tar(unit_runtime_context) -> None:
    transport = RfStubTransport(
        {
            "DISP:WIND:ACT:MEAS?": "SPECtrum",
            "DISP:SPEC:FREQ:OFFS?": "1000000000.0",
            "DISP:SPEC:FREQ:SCAL?": "10000000.0",
            "SENS:SPEC:ACQ:POIN?": "512",
            "__raw__": b"#14dead",
        },
    )
    inst = build_instrument("rtsa", 1, {"model": "tektronix-rsa5100b"}, transport)
    path = inst.save_IQ_data("captures/iq.iq.tar", file_format="iq.tar")
    assert path.exists()
    with tarfile.open(path, "r") as archive:
        names = archive.getnames()
        assert "iq.bin" in names
        assert "metadata.json" in names
        assert archive.extractfile("iq.bin").read() == b"dead"


def test_write_iq_mat(tmp_path: Path) -> None:
    payload = np.array([1.0, 2.0, 3.0, 4.0], dtype="<f8").tobytes()
    path = tmp_path / "capture.mat"

    write_iq_mat(path, payload, metadata={"sample_rate": 1e6})

    data = loadmat(path)
    np.testing.assert_allclose(data["iq"].ravel(), np.array([1 + 2j, 3 + 4j]))


def test_generic_and_catalog_capture_iq_unsupported() -> None:
    generic = build_instrument("rtsa", 1, {"model": "generic"}, RfStubTransport())
    with pytest.raises(EquipmentCapabilityError, match="capture_iq"):
        generic.capture_iq(
            center_hz=1e9,
            span_hz=10e6,
            bandwidth_hz=10e6,
            seconds=0.01,
            path="captures/iq.mat",
        )

    catalog = build_instrument("rtsa", 1, {"model": "rigol-rsa3030"}, RfStubTransport())
    with pytest.raises(EquipmentCapabilityError, match="capture_iq"):
        catalog.capture_iq(
            center_hz=1e9,
            span_hz=10e6,
            bandwidth_hz=10e6,
            seconds=0.01,
            path="captures/iq.mat",
        )


def test_write_capture_iq_sample_formats(tmp_path: Path) -> None:
    iq = np.array([0.5 + 0.25j, -0.25 + 0.5j], dtype=np.complex64)

    f32_path = tmp_path / "f32.bin"
    f32_meta = write_capture_iq(
        f32_path,
        iq,
        file_format="bin",
        sample_format="f32",
        metadata={"center_hz": 1e9},
    )
    assert f32_meta["sample_format"] == "f32"
    assert "peak" not in f32_meta
    raw_f32 = np.frombuffer(f32_path.read_bytes(), dtype="<f4")
    np.testing.assert_allclose(raw_f32, [0.5, 0.25, -0.25, 0.5], rtol=1e-6)

    c64_path = tmp_path / "c64.bin"
    write_capture_iq(c64_path, iq, file_format="bin", sample_format="c64")
    loaded_c64 = np.frombuffer(c64_path.read_bytes(), dtype="<c8")
    np.testing.assert_allclose(loaded_c64, iq, rtol=1e-6)

    i16_path = tmp_path / "i16.bin"
    i16_meta = write_capture_iq(
        i16_path,
        iq,
        file_format="bin",
        sample_format="i16",
        metadata={"center_hz": 1e9},
    )
    assert i16_meta["sample_format"] == "i16"
    assert i16_meta["peak"] == pytest.approx(0.5)
    assert load_iq_interleaved_i16(i16_path) == i16_path.read_bytes()
    ints = np.frombuffer(i16_path.read_bytes(), dtype="<i2")
    assert int(np.max(np.abs(ints))) == 32767

    mat_path = tmp_path / "iq.mat"
    write_capture_iq(mat_path, iq, file_format="mat", sample_format="f32")
    mat = loadmat(str(mat_path), squeeze_me=True, struct_as_record=False)
    np.testing.assert_allclose(np.asarray(mat["iq"]).ravel(), iq, rtol=1e-6)

    with pytest.raises(EquipmentResponseError, match="sample_format"):
        write_capture_iq(tmp_path / "bad.bin", iq, file_format="bin", sample_format="f64")


def test_tek_rsa_family_aliases_leave_exact_models_native() -> None:
    from colosseum_equipment.instruments.rtsa.tektronix_native import TekRsa5100bNative

    for model in ("tektronix-rsa5103b", "tektronix-rsa6000"):
        inst = build_instrument("rtsa", 1, {"model": model}, RfStubTransport())
        assert type(inst) is TektronixRSA5100BRtsa
    native = build_instrument("rtsa", 1, {"model": "tektronix-rsa5115b"}, RfStubTransport())
    assert type(native) is TekRsa5100bNative


@pytest.mark.parametrize("model", ["tektronix-rsa5100b", "tektronix-rsa5115b"])
def test_tek_capture_iq_iqvtime_sequence(unit_runtime_context, model: str) -> None:
    _ = unit_runtime_context
    samples = np.array([1.0, 2.0, 3.0, 4.0], dtype="<f4")
    block = format_definite_length_block(samples.tobytes())
    transport = RfStubTransport(
        {
            "*OPC?": "1",
            "FETCh:RFIN:RECord:IDS?": "1,1",
            "FETCh:RFIN:IQ:HEADer? 1": "0,1000000.0,2",
            "__raw__": block,
        },
    )
    inst = build_instrument("rtsa", 1, {"model": model}, transport)
    meta = inst.capture_iq(
        center_hz=503e6,
        span_hz=10e6,
        bandwidth_hz=10e6,
        seconds=0.5,
        path="captures/iq.mat",
        file_format="mat",
        sample_format="f32",
        timeout_s=5.0,
    )

    assert meta["sample_rate_hz"] == 1_000_000.0
    assert meta["num_samples"] == 2
    assert meta["sample_format"] == "f32"
    assert "DISP:SPEC" not in " ".join(transport.written)
    assert "FETCH:SPEC:IQ?" not in transport.written
    assert "DISPlay:GENeral:MEASview:NEW IQVTime" in transport.written
    assert "SENSe:ACQuisition:MODE LENGTH" in transport.written
    assert "SENSe:IQVTime:MAXTracepoints NEVerdecimate" in transport.written
    assert "SENSe:ACQuisition:SEConds 0.500000000" in transport.written
    assert "SENSe:ACQuisition:BANDwidth 10000000.000000" in transport.written
    assert "SENSe:IQVTime:FREQuency:CENTer 503000000.000000" in transport.written
    assert "INITIATE:IMMEDIATE" in transport.written
    assert any(cmd.startswith("FETCh:RFIN:IQ? 1,0,1") for cmd in transport.written)

    mat = loadmat(meta["path"], squeeze_me=True, struct_as_record=False)
    np.testing.assert_allclose(np.asarray(mat["iq"]).ravel(), [1 + 2j, 3 + 4j], rtol=1e-6)
@pytest.mark.parametrize("endianness,prefix", [("little", "<"), ("big", ">")])
@pytest.mark.parametrize("sample_format,dtype,expected", [
    ("f32", "f4", [1.0, -0.5, -1.0, 0.25]),
    ("c64", "c8", [1 - 0.5j, -1 + 0.25j]),
    ("i16", "i2", [32767, -16384, -32767, 8192]),
])
@pytest.mark.parametrize("file_format", ["bin", "iq.tar"])
def test_capture_byte_order(tmp_path, endianness, prefix, sample_format, dtype, expected, file_format):
    import json

    samples = np.array([1 - 0.5j, -1 + 0.25j], dtype=np.complex64)
    path = tmp_path / "samples"
    meta = write_capture_iq(path, samples, file_format=file_format,
                            sample_format=sample_format, endianness=endianness)
    assert meta["endianness"] == endianness
    if file_format == "iq.tar":
        with tarfile.open(path) as archive:
            payload = archive.extractfile("iq.bin").read()
            assert json.load(archive.extractfile("metadata.json"))["endianness"] == endianness
    else:
        payload = path.read_bytes()
    assert payload == np.array(expected, dtype=prefix + dtype).tobytes()


@pytest.mark.parametrize("file_format,endianness", [("mat", "big"), ("bin", "native")])
def test_capture_refuses_unsupported_byte_order(tmp_path, file_format, endianness):
    path = tmp_path / "capture"
    with pytest.raises(EquipmentResponseError, match="endianness"):
        write_capture_iq(path, np.array([1j]), file_format=file_format,
                         sample_format="i16", endianness=endianness)
    assert not path.exists()


@pytest.mark.parametrize("model", ["tektronix-rsa5100b", "tektronix-rsa5115b", "tektronix-rsa6114a"])
def test_tek_frontend_controls(model):
    io = RfStubTransport()
    inst = build_instrument("rtsa", 1, {"model": model}, io)
    io.written.clear()
    inst.set_auto_attenuation(False)
    inst.set_attenuation_db(-20)
    inst.set_reference_level(0)
    inst.toggle_preamp(True)
    inst.set_iq_bandwidth(1e6)
    assert io.written == [
        "INPUT:RF:ATTENUATION:AUTO OFF", "INPUT:RF:ATTENUATION -20.000",
        "INPUT:RLEVEL 0.000", "INPUT:RF:GAIN:STATE ON", "SENS:ACQ:BAND 1000000.000000",
    ]


@pytest.mark.parametrize("model", ["rigol-rsa5032", "rigol-rsa5065", "siglent-ssa3032x-r", "siglent-ssa3075x-r"])
def test_catalog_frontend_controls(model):
    io = RfStubTransport()
    inst = build_instrument("rtsa", 1, {"model": model}, io)
    inst.set_auto_attenuation(False)
    inst.set_attenuation_db(20)
    inst.set_reference_level(-10)
    inst.toggle_preamp(True)
    assert io.written == ["SENS:POW:RF:ATT:AUTO OFF", "SENS:POW:RF:ATT 20.000",
                          "DISP:WIND:TRAC:Y:SCAL:RLEV -10.000DBM", "SENS:POW:RF:GAIN:STAT ON"]


@pytest.mark.parametrize("method", [None, "fwhm", "occupied_power", "half_prominence"])
def test_offline_spectrum_measurements_record_and_plot(unit_runtime_context, monkeypatch, method):
    from colosseum_equipment.api import rtsa
    from colosseum_equipment.instruments.speca.bandwidth import bandwidth_edges_hz
    from colosseum_equipment.instruments.speca.trace_csv import write_trace_csv

    ctx = unit_runtime_context
    path = ctx.output_dir / "trace.csv"
    amplitudes = [-30, -10, 0, -10, -30]
    write_trace_csv(path, amplitudes, center_hz=100, span_hz=40)
    monkeypatch.setattr(rtsa, "get_cached_instrument", lambda *args: pytest.fail("offline analysis contacted hardware"))
    left, right = bandwidth_edges_hz([80, 90, 100, 110, 120], amplitudes,
                                     start_hz=80, stop_hz=120, method=method)
    captured = []
    original = rtsa._write_trace_plot

    def plot(*args, **kwargs):
        captured.append(kwargs)
        original(*args, **kwargs)

    monkeypatch.setattr(rtsa, "_write_trace_plot", plot)
    kwargs = {"rtsa_id": 1, "start_hz": 80, "stop_hz": 120, "trace_path": "trace.csv",
              "method": method, "save_plot": True}
    assert rtsa.measure_bw(**kwargs, key="width") == pytest.approx(right - left)
    assert rtsa.measure_center_frequency_hz(**kwargs, key="center") == pytest.approx((left + right) / 2)
    assert captured[0]["edges_hz"] == (left, right)
    assert captured[1]["center_hz"] == (left + right) / 2
    assert len(list((ctx.output_dir / "plots").glob("*.png"))) == 2
    assert ctx.db.get_measurement("equipment", "rtsa.measure_bw", "width", row_index=0).value == pytest.approx(right - left)


def test_live_spectrum_single_capture_and_power_calibration(unit_runtime_context, monkeypatch):
    from types import SimpleNamespace

    from colosseum_equipment.api import rtsa
    from colosseum_equipment.instruments.speca.trace_csv import write_trace_csv

    captures = []
    def acquire(path, *, trace):
        captures.append(trace)
        target = unit_runtime_context.output_dir / path
        write_trace_csv(target, [-30, -10, 0, -10, -30], center_hz=100, span_hz=40)
        return target

    monkeypatch.setattr(rtsa, "get_cached_instrument", lambda *args: SimpleNamespace(_acquire_spectrum_trace=acquire))
    rtsa.measure_bw(rtsa_id=1, start_hz=80, stop_hz=120, key="width", save_plot=True)
    assert captures == [1]
    corrected = []
    def correction(power, *, key, frequency_hz):
        corrected.append((power, key, frequency_hz))
        return power + 3

    monkeypatch.setattr(rtsa._cal, "correct_power_dbm", correction)
    assert rtsa.measure_trace_power_at_frequency(rtsa_id=1, frequency_hz=109,
                                                key="power", calibration="rx") == -7
    assert corrected == [(-10, "rx", 110)]


def test_frontend_broadcast_and_parameter_overrides(unit_runtime_context, monkeypatch):
    from colosseum_equipment.api import _broadcast, rtsa
    from colosseum_equipment.exceptions import EquipmentError

    transports = [RfStubTransport(), RfStubTransport(), RfStubTransport()]
    models = ["tektronix-rsa5100b", "generic", "signalhound-bb60c-spike"]
    instruments = [build_instrument("rtsa", i + 1, {"model": model}, io)
                   for i, (model, io) in enumerate(zip(models, transports, strict=True))]
    monkeypatch.setattr(rtsa, "get_cached_instrument", lambda kind, index: instruments[index - 1])
    monkeypatch.setattr(_broadcast, "resolve_equipment_ids", lambda *args: [1, 2, 3])
    unit_runtime_context.parameters_map = {"frontend": {"level_dbm": -15}}
    rtsa.set_reference_level(rtsa_id=1, level_dbm=0, key="frontend")
    assert transports[0].written[-1] == "INPUT:RLEVEL -15.000"
    with pytest.raises(EquipmentError, match="failed ids 2"):
        rtsa.set_reference_level(rtsa_id="all", level_dbm=-10)
    assert transports[0].written[-1] == "INPUT:RLEVEL -10.000"
    assert transports[2].written[-1] == "SENS:ZS:CAP:RLEV -10DBM"
    assert not transports[1].written


@pytest.mark.parametrize("model", ["tektronix-rsa5100b", "tektronix-rsa5115b"])
def test_capture_api_forwards_big_endian(unit_runtime_context, monkeypatch, model):
    from colosseum_equipment.api import rtsa

    block = format_definite_length_block(np.array([1, 2, 3, 4], dtype="<f4").tobytes())
    io = RfStubTransport({"*OPC?": "1", "FETCh:RFIN:RECord:IDS?": "1,1",
                          "FETCh:RFIN:IQ:HEADer? 1": "0,1000000.0,2", "__raw__": block})
    inst = build_instrument("rtsa", 1, {"model": model}, io)
    monkeypatch.setattr(rtsa, "get_cached_instrument", lambda *args: inst)
    meta = rtsa.capture_iq(rtsa_id=1, center_hz=1e9, span_hz=10e6, bandwidth_hz=10e6,
                           seconds=.01, path="iq.bin", file_format="bin", endianness="big", key="iq")
    assert meta["endianness"] == "big"
    assert (unit_runtime_context.output_dir / "iq.bin").read_bytes() == np.array([1, 2, 3, 4], dtype=">f4").tobytes()
