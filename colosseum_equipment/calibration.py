"""Path-loss calibration from VNA S21/S12 sweeps.

``load_calibration`` parses CSV/TXT/S2P into the run measurements DB. Source and
measure APIs look up nearest-bin loss via ``calibration=<key>``.

Convention: ``loss_db`` is S21/S12 magnitude in dB (typically ≤ 0).
Programmed generator power is ``desired_dbm - loss_db``; corrected readings are
``raw_dbm - loss_db``.
"""

from __future__ import annotations

import csv
import math
import re
from pathlib import Path

from colosseum.context import get_context
from colosseum.database import MeasurementRow
from colosseum.database.artifact_paths import stored_artifact_path

from colosseum_equipment.exceptions import EquipmentError
from colosseum_equipment.instruments.speca.trace_csv import nearest_trace_bin

_COMMAND = "load_calibration"
_DOMAIN = "equipment"

_ATTR_FREQ = "_cal_frequency_hz"
_ATTR_DESIRED = "_cal_desired_power_dbm"
_ATTR_KEY = "_cal_key"
_ATTR_FREQ_BY_CH = "_cal_frequency_hz_by_channel"
_ATTR_DESIRED_BY_CH = "_cal_desired_power_dbm_by_channel"
_ATTR_KEY_BY_CH = "_cal_key_by_channel"


class CalibrationError(EquipmentError):
    """Raised when a calibration file or key cannot be used."""


def parse_calibration_file(path: Path | str) -> tuple[list[float], list[float]]:
    """Return ``(frequencies_hz, loss_db)`` from a VNA sweep file."""
    file_path = Path(path)
    if not file_path.is_file():
        raise CalibrationError(f"calibration file not found: {file_path}")
    suffix = file_path.suffix.lower()
    text = file_path.read_text(encoding="utf-8")
    if suffix == ".s2p":
        return _parse_s2p(text)
    if suffix in {".csv", ".txt"} or suffix == "":
        return _parse_tabular(text)
    # Unknown extension: try tabular then Touchstone.
    try:
        return _parse_tabular(text)
    except CalibrationError:
        return _parse_s2p(text)


def store_calibration(
    *,
    key: str,
    frequencies_hz: list[float],
    loss_db: list[float],
    source_path: Path | str | None = None,
) -> None:
    """Insert/replace the calibration table in the run measurements DB."""
    if not key:
        raise CalibrationError("calibration key must be non-empty")
    if not frequencies_hz or len(frequencies_hz) != len(loss_db):
        raise CalibrationError("calibration requires equal non-empty frequency and loss arrays")
    if any(not math.isfinite(f) or f <= 0 for f in frequencies_hz):
        raise CalibrationError("calibration frequencies must be finite and positive")
    if any(not math.isfinite(v) for v in loss_db):
        raise CalibrationError("calibration loss values must be finite")

    try:
        ctx = get_context()
    except RuntimeError as exc:
        raise CalibrationError("load_calibration requires an active Colosseum run context") from exc
    if not ctx.db.is_initialized():
        raise CalibrationError("load_calibration requires an initialized measurements database")

    output_dir = getattr(ctx, "output_dir", None)
    artifact = None
    if source_path is not None:
        out = output_dir if isinstance(output_dir, Path) else None
        artifact = stored_artifact_path(source_path, out)

    row = MeasurementRow(
        domain=_DOMAIN,
        command=_COMMAND,
        key=key,
        value={"frequencies_hz": list(frequencies_hz), "loss_db": list(loss_db)},
        units="dB",
        artifact_path=artifact,
        status="PASS",
    )
    insert = getattr(ctx.db, "insert_measurement", None)
    if callable(insert):
        insert(row)
    else:
        ctx.db.enqueue_measurement(row)


def load_calibration_file(*, filename: str, key: str) -> None:
    """Parse ``filename`` and store frequency/loss pairs under ``key``."""
    path = Path(filename)
    frequencies, losses = parse_calibration_file(path)
    store_calibration(key=key, frequencies_hz=frequencies, loss_db=losses, source_path=path)


def loss_db(key: str, frequency_hz: float) -> float:
    """Nearest-bin path loss in dB for ``key`` at ``frequency_hz``."""
    frequencies, losses = _read_calibration(key)
    index = nearest_trace_bin(frequencies, frequency_hz)
    return float(losses[index])


def correct_power_dbm(raw_dbm: float, *, key: str, frequency_hz: float) -> float:
    """Apply path-loss correction to a measured power."""
    return float(raw_dbm) - loss_db(key, frequency_hz)


def programmed_power_dbm(desired_dbm: float, *, key: str, frequency_hz: float) -> float:
    """Instrument power that yields ``desired_dbm`` after the path."""
    return float(desired_dbm) - loss_db(key, frequency_hz)


def correct_trace_amplitudes(
    frequencies_hz: list[float],
    amplitudes_dbm: list[float],
    *,
    key: str,
) -> list[float]:
    """Subtract nearest-bin loss from each amplitude sample."""
    if len(frequencies_hz) != len(amplitudes_dbm):
        raise CalibrationError("trace frequency and amplitude lengths differ")
    if not frequencies_hz:
        raise CalibrationError("cannot apply calibration to an empty trace")
    return [
        float(amplitude) - loss_db(key, frequency)
        for frequency, amplitude in zip(frequencies_hz, amplitudes_dbm, strict=True)
    ]


def bind_frequency(instrument: object, frequency_hz: float, *, channel: int | None = None) -> None:
    """Remember the last frequency used for calibration lookups."""
    if channel is None:
        setattr(instrument, _ATTR_FREQ, float(frequency_hz))
        return
    freqs: dict[int, float] = getattr(instrument, _ATTR_FREQ_BY_CH, None) or {}
    freqs = dict(freqs)
    freqs[int(channel)] = float(frequency_hz)
    setattr(instrument, _ATTR_FREQ_BY_CH, freqs)


def bound_frequency(instrument: object, *, channel: int | None = None) -> float | None:
    if channel is None:
        value = getattr(instrument, _ATTR_FREQ, None)
        return float(value) if value is not None else None
    freqs = getattr(instrument, _ATTR_FREQ_BY_CH, None) or {}
    value = freqs.get(int(channel))
    return float(value) if value is not None else None


def remember_desired_power(
    instrument: object,
    desired_dbm: float,
    *,
    key: str,
    channel: int | None = None,
) -> None:
    if channel is None:
        setattr(instrument, _ATTR_DESIRED, float(desired_dbm))
        setattr(instrument, _ATTR_KEY, key)
        return
    desired: dict[int, float] = getattr(instrument, _ATTR_DESIRED_BY_CH, None) or {}
    keys: dict[int, str] = getattr(instrument, _ATTR_KEY_BY_CH, None) or {}
    desired = dict(desired)
    keys = dict(keys)
    desired[int(channel)] = float(desired_dbm)
    keys[int(channel)] = key
    setattr(instrument, _ATTR_DESIRED_BY_CH, desired)
    setattr(instrument, _ATTR_KEY_BY_CH, keys)


def desired_power_dbm(instrument: object, *, channel: int | None = None) -> float | None:
    if channel is None:
        value = getattr(instrument, _ATTR_DESIRED, None)
        return float(value) if value is not None else None
    desired = getattr(instrument, _ATTR_DESIRED_BY_CH, None) or {}
    value = desired.get(int(channel))
    return float(value) if value is not None else None


def clear_desired_power(instrument: object, *, channel: int | None = None) -> None:
    if channel is None:
        for attr in (_ATTR_DESIRED, _ATTR_KEY):
            if hasattr(instrument, attr):
                delattr(instrument, attr)
        return
    desired = getattr(instrument, _ATTR_DESIRED_BY_CH, None)
    keys = getattr(instrument, _ATTR_KEY_BY_CH, None)
    if isinstance(desired, dict):
        desired = dict(desired)
        desired.pop(int(channel), None)
        setattr(instrument, _ATTR_DESIRED_BY_CH, desired)
    if isinstance(keys, dict):
        keys = dict(keys)
        keys.pop(int(channel), None)
        setattr(instrument, _ATTR_KEY_BY_CH, keys)


def require_frequency(instrument: object, *, channel: int | None = None, what: str) -> float:
    frequency = bound_frequency(instrument, channel=channel)
    if frequency is None:
        raise CalibrationError(
            f"{what} with calibration= requires a prior set_frequency "
            "(or set_center_frequency) so path loss can be looked up",
        )
    return frequency


def require_desired_power(instrument: object, *, channel: int | None = None) -> float:
    desired = desired_power_dbm(instrument, channel=channel)
    if desired is None:
        raise CalibrationError(
            "set_frequency(..., calibration=) requires a prior "
            "set_power(..., calibration=) so post-cal desired power is known",
        )
    return desired


def _read_calibration(key: str) -> tuple[list[float], list[float]]:
    try:
        ctx = get_context()
    except RuntimeError as exc:
        raise CalibrationError(
            "calibration lookup requires an active Colosseum run context",
        ) from exc
    row = ctx.db.get_measurement(_DOMAIN, _COMMAND, key, row_index=0)
    if row is None:
        raise CalibrationError(f"unknown calibration key `{key}`; call load_calibration first")
    value = row.value
    if not isinstance(value, dict):
        raise CalibrationError(f"calibration key `{key}` has an invalid stored value")
    frequencies = value.get("frequencies_hz")
    losses = value.get("loss_db")
    if not isinstance(frequencies, list) or not isinstance(losses, list):
        raise CalibrationError(f"calibration key `{key}` is missing frequency/loss arrays")
    if not frequencies or len(frequencies) != len(losses):
        raise CalibrationError(f"calibration key `{key}` has empty or mismatched arrays")
    return [float(f) for f in frequencies], [float(v) for v in losses]


def _parse_tabular(text: str) -> tuple[list[float], list[float]]:
    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    if not lines:
        raise CalibrationError("calibration table is empty")

    sample = lines[0].lower()
    if "frequency" in sample or "value" in sample or "amplitude" in sample or "loss" in sample:
        reader = csv.DictReader(line for line in lines)
        if reader.fieldnames is None:
            raise CalibrationError("calibration CSV has no header")
        fields = {name.strip().lower(): name for name in reader.fieldnames if name}
        freq_key = _pick_field(fields, ("frequency_hz", "freq_hz", "frequency", "freq", "f"))
        loss_key = _pick_field(
            fields,
            ("value", "loss_db", "s21_db", "s12_db", "amplitude_dbm", "mag_db", "db"),
        )
        frequencies: list[float] = []
        losses: list[float] = []
        for row in reader:
            frequencies.append(float(row[freq_key]))
            losses.append(float(row[loss_key]))
        if not frequencies:
            raise CalibrationError("calibration CSV has no data rows")
        return frequencies, losses

    frequencies = []
    losses = []
    for line in lines:
        parts = re.split(r"[\s,;]+", line.strip())
        parts = [part for part in parts if part]
        if len(parts) < 2:
            raise CalibrationError(f"expected frequency and loss columns, got: {line!r}")
        frequencies.append(float(parts[0]))
        losses.append(float(parts[1]))
    return frequencies, losses


def _pick_field(fields: dict[str, str], candidates: tuple[str, ...]) -> str:
    for name in candidates:
        if name in fields:
            return fields[name]
    raise CalibrationError(
        "calibration table needs a frequency column and a loss/value column "
        f"(have {sorted(fields)})",
    )


def _parse_s2p(text: str) -> tuple[list[float], list[float]]:
    option = "RI"
    freq_scale = 1.0
    data_rows: list[list[float]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("!"):
            continue
        if line.startswith("#"):
            freq_scale, option = _parse_touchstone_option(line)
            continue
        parts = [float(part) for part in re.split(r"[\s,]+", line) if part]
        if len(parts) < 3:
            raise CalibrationError(f"invalid Touchstone data line: {raw!r}")
        data_rows.append(parts)
    if not data_rows:
        raise CalibrationError("Touchstone file has no data rows")

    frequencies: list[float] = []
    losses: list[float] = []
    for row in data_rows:
        frequency = row[0] * freq_scale
        if len(row) == 3:
            loss = _pair_to_db(row[1], row[2], option)
        elif len(row) >= 9:
            # Full 2-port: freq S11 S21 S12 S22 → use S21.
            loss = _pair_to_db(row[3], row[4], option)
        else:
            raise CalibrationError(
                "Touchstone rows must be single-parameter (3 values) or full 2-port (9 values)",
            )
        frequencies.append(frequency)
        losses.append(loss)
    return frequencies, losses


def _parse_touchstone_option(line: str) -> tuple[float, str]:
    tokens = line.lstrip("#").split()
    freq_scale = 1.0
    option = "RI"
    if tokens:
        unit = tokens[0].upper()
        freq_scale = {
            "HZ": 1.0,
            "KHZ": 1e3,
            "MHZ": 1e6,
            "GHZ": 1e9,
        }.get(unit, 1.0)
    for token in tokens[1:]:
        upper = token.upper()
        if upper in {"RI", "MA", "DB"}:
            option = upper
    return freq_scale, option


def _pair_to_db(first: float, second: float, option: str) -> float:
    if option == "DB":
        return float(first)
    magnitude = (
        abs(float(first)) if option == "MA" else abs(complex(float(first), float(second)))
    )
    if magnitude <= 0.0:
        return -200.0
    return 20.0 * math.log10(magnitude)
