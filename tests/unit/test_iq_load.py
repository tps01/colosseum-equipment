"""VSG IQ file loaders (.bin / .mat / .iq.tar)."""

from __future__ import annotations

import numpy as np
from colosseum_equipment.instruments.vsg.iq_load import load_iq_interleaved_i16, write_iq_tar_i16
from scipy.io import savemat


def test_load_bin_passthrough(tmp_path) -> None:
    payload = np.array([1000, -2000, 3000, -4000], dtype="<i2").tobytes()
    path = tmp_path / "w.bin"
    path.write_bytes(payload)
    assert load_iq_interleaved_i16(path) == payload


def test_load_mat_complex(tmp_path) -> None:
    iq = np.array([0.5 + 0.25j, -0.5 + 0.0j], dtype=np.complex128)
    path = tmp_path / "w.mat"
    savemat(path, {"iq": iq})
    loaded = load_iq_interleaved_i16(path)
    samples = np.frombuffer(loaded, dtype="<i2")
    assert len(samples) == 4
    assert samples[0] == 32767  # peak-normalized


def test_load_iq_tar_int16(tmp_path) -> None:
    payload = np.array([10, 20, 30, 40], dtype="<i2").tobytes()
    path = tmp_path / "w.iq.tar"
    write_iq_tar_i16(path, payload)
    assert load_iq_interleaved_i16(path) == payload
