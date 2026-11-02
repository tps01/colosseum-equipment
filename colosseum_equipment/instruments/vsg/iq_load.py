"""Load local IQ files into 16-bit interleaved I/Q bytes for VSG upload."""

from __future__ import annotations

import io
import json
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


def _iq_tar_format(metadata: dict[str, Any]) -> str:
    sample_format = str(metadata.get("sample_format", "")).lower().lstrip(".")
    if sample_format in {"i16", "f32", "c64"}:
        return sample_format
    iq_dtype = str(metadata.get("iq_dtype", "")).lower()
    if iq_dtype in {"int16", "i16", "<i2"}:
        return "i16"
    if iq_dtype in {"float64", "f8", "<f8"}:
        return "f64"
    if iq_dtype in {"float32", "f4", "<f4"}:
        return "f32"
    if iq_dtype in {"complex64", "c8", "<c8"}:
        return "c64"
    return "i16"


def _load_iq_tar(path: Path) -> bytes:
    with tarfile.open(path, mode="r:*") as archive:
        member = archive.getmember("iq.bin")
        handle = archive.extractfile(member)
        if handle is None:
            raise EquipmentResponseError(f"iq.tar missing iq.bin: {path}")
        payload = handle.read()
        metadata: dict[str, Any] = {}
        try:
            meta_member = archive.getmember("metadata.json")
        except KeyError:
            meta_member = None
        if meta_member is not None:
            meta_handle = archive.extractfile(meta_member)
            if meta_handle is not None:
                metadata = json.loads(meta_handle.read().decode("utf-8"))
    fmt = _iq_tar_format(metadata)
    if fmt == "i16":
        if len(payload) >= 4 and len(payload) % 4 == 0:
            return payload
        raise EquipmentResponseError(
            f"iq.bin in `{path}` must contain whole 16-bit I/Q sample pairs",
        )
    if fmt == "f64":
        as_f64 = np.frombuffer(payload, dtype="<f8")
        if as_f64.size < 2 or as_f64.size % 2:
            raise EquipmentResponseError(f"iq.bin in `{path}` must contain float64 I/Q pairs")
        return _float_to_i16_interleaved(as_f64[0::2], as_f64[1::2])
    if fmt == "f32":
        as_f32 = np.frombuffer(payload, dtype="<f4")
        if as_f32.size < 2 or as_f32.size % 2:
            raise EquipmentResponseError(f"iq.bin in `{path}` must contain float32 I/Q pairs")
        return _float_to_i16_interleaved(as_f32[0::2], as_f32[1::2])
    as_c64 = np.frombuffer(payload, dtype="<c8")
    if as_c64.size < 1:
        raise EquipmentResponseError(f"iq.bin in `{path}` must contain complex64 samples")
    return _float_to_i16_interleaved(as_c64.real, as_c64.imag)


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
