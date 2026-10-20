"""RTSA factory routing and SCPI delegation."""

from __future__ import annotations

import tarfile
from typing import TYPE_CHECKING

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

if TYPE_CHECKING:
    from pathlib import Path


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
        f32_path, iq, file_format="bin", sample_format="f32", metadata={"center_hz": 1e9},
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
        i16_path, iq, file_format="bin", sample_format="i16", metadata={"center_hz": 1e9},
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


def test_tek_rsa5115b_alias_builds_same_driver() -> None:
    inst = build_instrument("rtsa", 1, {"model": "tektronix-rsa5115b"}, RfStubTransport())
    assert isinstance(inst, TektronixRSA5100BRtsa)


def test_tek_capture_iq_iqvtime_sequence(unit_runtime_context) -> None:
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
    inst = build_instrument("rtsa", 1, {"model": "tektronix-rsa5100b"}, transport)
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
