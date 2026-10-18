from __future__ import annotations

import csv
from pathlib import Path


def write_phase_noise_trace_csv(path: Path, offsets_hz: list[float], values_dbc_hz: list[float]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["offset_hz", "phase_noise_dbc_hz"])
        for offset_hz, value in zip(offsets_hz, values_dbc_hz, strict=False):
            writer.writerow([f"{offset_hz:.6f}", f"{value:.6f}"])


def parse_trace_values(raw: str) -> list[float]:
    text = raw.strip()
    if not text:
        return []
    return [float(part) for part in text.split(",") if part.strip()]
