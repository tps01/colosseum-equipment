"""RTSA factory routing and SCPI delegation."""

from __future__ import annotations

import tarfile
from typing import TYPE_CHECKING

import numpy as np
from colosseum_equipment.instruments.factory import build_instrument
from colosseum_equipment.instruments.rtsa.generic import GenericRtsa
from colosseum_equipment.instruments.rtsa.iq_export import write_iq_mat
from colosseum_equipment.instruments.rtsa.tektronix_rsa5100b import TektronixRSA5100BRtsa
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
