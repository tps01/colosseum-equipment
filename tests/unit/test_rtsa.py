"""RTSA factory routing and SCPI delegation."""

from __future__ import annotations

import tarfile
from pathlib import Path

import numpy as np
from scipy.io import loadmat

from colosseum_equipment.instruments.factory import build_instrument
from colosseum_equipment.instruments.rtsa.iq_export import write_iq_mat
from colosseum_equipment.instruments.rtsa.tektronix_rsa5100b import TektronixRSA5100BRtsa

from tests.support.stubs import RfStubTransport


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
        }
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
