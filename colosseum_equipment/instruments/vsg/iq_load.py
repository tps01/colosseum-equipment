"""Load local IQ files into 16-bit interleaved I/Q bytes for VSG upload."""

from __future__ import annotations

import io
import tarfile
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt

from colosseum_equipment.exceptions import EquipmentResponseError


def _float_to_i16_interleaved(i: npt.NDArray[Any], q: npt.NDArray[Any]) -> bytes:
    i = np.asarray(i, dtype=np.float64).reshape(-1)
    q = np.asarray(q, dtype=np.float64).reshape(-1)
    if i.size != q.size:
        raise EquipmentResponseError("I and Q arrays must have the same length")
    if i.size == 0:
        return b""
    peak = float(max(np.max(np.abs(i)), np.max(np.abs(q)), 1e-30))
    scale = 32767.0 / peak
    interleaved = np.empty(i.size * 2, dtype="<i2")
    interleaved[0::2] = np.clip(np.rint(i * scale), -32768, 32767).astype("<i2")
    interleaved[1::2] = np.clip(np.rint(q * scale), -32768, 32767).astype("<i2")
    return interleaved.tobytes()


def _array_to_i16_bytes(arr: npt.NDArray[Any]) -> bytes:
    data = np.asarray(arr)
    if np.iscomplexobj(data):
        flat = data.reshape(-1)
        return _float_to_i16_interleaved(flat.real, flat.imag)
    flat = data.reshape(-1)
    if flat.dtype == np.int16 or flat.dtype == np.dtype("<i2"):
        if flat.size % 2:
            raise EquipmentResponseError("int16 IQ payload length must be even")
        return np.asarray(flat, dtype="<i2").tobytes()
    if flat.size % 2:
        raise EquipmentResponseError("interleaved float IQ length must be even")
    return _float_to_i16_interleaved(flat[0::2], flat[1::2])


def _load_mat(path: Path) -> bytes:
    from scipy.io import loadmat

    mat = loadmat(str(path), squeeze_me=True, struct_as_record=False)
    for key in ("iq", "IQ", "Iq"):
        if key in mat:
            return _array_to_i16_bytes(mat[key])
    if "i" in mat and "q" in mat:
        return _float_to_i16_interleaved(mat["i"], mat["q"])
    if "I" in mat and "Q" in mat:
        return _float_to_i16_interleaved(mat["I"], mat["Q"])
    raise EquipmentResponseError(
        f"MAT file `{path}` must contain iq/IQ or i/q (I/Q) arrays",
    )


def _load_iq_tar(path: Path) -> bytes:
    with tarfile.open(path, mode="r:*") as archive:
        member = archive.getmember("iq.bin")
        handle = archive.extractfile(member)
        if handle is None:
            raise EquipmentResponseError(f"iq.tar missing iq.bin: {path}")
        payload = handle.read()
    if len(payload) >= 8 and len(payload) % 8 == 0:
        as_f64 = np.frombuffer(payload, dtype="<f8")
        if as_f64.size >= 2 and bool(np.all(np.isfinite(as_f64))) and float(np.max(np.abs(as_f64))) <= 2.0:
            return _float_to_i16_interleaved(as_f64[0::2], as_f64[1::2])
    if len(payload) >= 4 and len(payload) % 4 == 0:
        return payload
    raise EquipmentResponseError(
        f"iq.bin in `{path}` must contain whole 16-bit I/Q sample pairs",
    )


def load_iq_interleaved_i16(local_path: str | Path) -> bytes:
    """Return little-endian int16 interleaved I/Q bytes from ``.bin`` / ``.mat`` / ``.iq.tar``."""
    path = Path(local_path)
    if not path.is_file():
        raise EquipmentResponseError(f"waveform file not found: {local_path}")
    name = path.name.lower()
    suffix = path.suffix.lower()
    if suffix == ".bin":
        payload = path.read_bytes()
        if len(payload) < 4 or len(payload) % 4 != 0:
            raise EquipmentResponseError(
                "IQ waveform .bin payload must contain whole 16-bit I/Q sample pairs",
            )
        return payload
    if suffix == ".mat":
        return _load_mat(path)
    if name.endswith(".iq.tar") or suffix == ".tar":
        return _load_iq_tar(path)
    raise EquipmentResponseError(
        f"unsupported waveform format `{path.suffix}` (use .bin, .mat, or .iq.tar)",
    )


def write_iq_tar_i16(path: Path, payload: bytes) -> None:
    """Test helper: wrap int16 interleaved bytes as ``iq.tar``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        info = tarfile.TarInfo(name="iq.bin")
        info.size = len(payload)
        archive.addfile(info, io.BytesIO(payload))
    path.write_bytes(buffer.getvalue())
