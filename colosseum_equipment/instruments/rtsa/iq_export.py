from __future__ import annotations

import io
import json
import tarfile
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt

from colosseum_equipment.exceptions import EquipmentResponseError

_SAMPLE_FORMATS = frozenset({"f32", "i16", "c64"})


def normalize_iq_format(file_format: str, path: str) -> str:
    fmt = file_format.lower().lstrip(".")
    if fmt in {"bin", "mat", "iq.tar"}:
        return fmt
    suffix = Path(path).suffix.lower()
    if suffix == ".mat":
        return "mat"
    if suffix == ".bin":
        return "bin"
    if suffix == ".tar" or path.lower().endswith(".iq.tar"):
        return "iq.tar"
    return fmt


def normalize_sample_format(sample_format: str) -> str:
    fmt = sample_format.lower().lstrip(".")
    if fmt not in _SAMPLE_FORMATS:
        raise EquipmentResponseError(
            f"unsupported sample_format `{sample_format}` (use f32, i16, or c64)",
        )
    return fmt


def write_iq_bin(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def write_iq_mat(path: Path, payload: bytes, *, metadata: dict[str, Any] | None = None) -> None:
    from scipy.io import savemat

    count = len(payload) // 8
    if count == 0:
        iq = np.array([], dtype=np.complex128)
    else:
        raw = np.frombuffer(payload[: count * 8], dtype="<f8")
        iq = raw[0::2] + 1j * raw[1::2]
    mat_data: dict[str, Any] = {"iq": iq}
    if metadata:
        mat_data["metadata"] = metadata
    path.parent.mkdir(parents=True, exist_ok=True)
    savemat(path, mat_data)


def write_iq_tar(path: Path, payload: bytes, *, metadata: dict[str, Any] | None = None) -> None:
    meta = metadata or {}
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        iq_info = tarfile.TarInfo(name="iq.bin")
        iq_info.size = len(payload)
        archive.addfile(iq_info, io.BytesIO(payload))
        meta_bytes = json.dumps(meta, indent=2).encode("utf-8")
        meta_info = tarfile.TarInfo(name="metadata.json")
        meta_info.size = len(meta_bytes)
        archive.addfile(meta_info, io.BytesIO(meta_bytes))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(buffer.getvalue())


def _as_complex64(iq: npt.NDArray[Any]) -> npt.NDArray[np.complex64]:
    arr = np.asarray(iq)
    if arr.size == 0:
        return np.array([], dtype=np.complex64)
    if not np.iscomplexobj(arr):
        raise EquipmentResponseError("capture_iq export requires a complex IQ array")
    return np.asarray(arr.reshape(-1), dtype=np.complex64)


def encode_iq_samples(
    iq: npt.NDArray[Any],
    *,
    sample_format: str,
) -> tuple[bytes, dict[str, Any]]:
    """Encode complex samples for ``capture_iq`` file output.

    Returns ``(payload_bytes, extra_metadata)``. ``extra_metadata`` includes
    ``peak`` when ``sample_format`` is ``i16``.
    """
    fmt = normalize_sample_format(sample_format)
    samples = _as_complex64(iq)
    extra: dict[str, Any] = {"sample_format": fmt, "num_samples": int(samples.size)}
    if samples.size == 0:
        return b"", extra

    if fmt == "f32":
        interleaved = np.empty(samples.size * 2, dtype="<f4")
        interleaved[0::2] = samples.real.astype("<f4", copy=False)
        interleaved[1::2] = samples.imag.astype("<f4", copy=False)
        return interleaved.tobytes(), extra

    if fmt == "c64":
        return samples.astype("<c8", copy=False).tobytes(), extra

    # i16: peak-scale to full-scale int16 (same as VSG iq_load).
    i = samples.real.astype(np.float64, copy=False)
    q = samples.imag.astype(np.float64, copy=False)
    peak = float(max(np.max(np.abs(i)), np.max(np.abs(q)), 1e-30))
    scale = 32767.0 / peak
    interleaved = np.empty(samples.size * 2, dtype="<i2")
    interleaved[0::2] = np.clip(np.rint(i * scale), -32768, 32767).astype("<i2")
    interleaved[1::2] = np.clip(np.rint(q * scale), -32768, 32767).astype("<i2")
    extra["peak"] = peak
    return interleaved.tobytes(), extra


def write_capture_iq(
    path: Path,
    iq: npt.NDArray[Any],
    *,
    file_format: str,
    sample_format: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Write decoded IQ samples using ``file_format`` + ``sample_format``.

    Returns the metadata dict written alongside the samples (includes
    ``sample_format``, ``num_samples``, and ``peak`` for ``i16``).
    """
    from scipy.io import savemat

    export_format = normalize_iq_format(file_format, str(path))
    payload, encode_meta = encode_iq_samples(iq, sample_format=sample_format)
    out_meta = dict(metadata or {})
    out_meta.update(encode_meta)
    out_meta["format"] = export_format
    samples = _as_complex64(iq)

    if export_format == "mat":
        mat_data: dict[str, Any] = {"iq": samples, "metadata": out_meta}
        path.parent.mkdir(parents=True, exist_ok=True)
        savemat(path, mat_data)
    elif export_format == "iq.tar":
        write_iq_tar(path, payload, metadata=out_meta)
    else:
        write_iq_bin(path, payload)
    return out_meta
