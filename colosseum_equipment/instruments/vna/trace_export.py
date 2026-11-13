from __future__ import annotations

import csv
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


def parse_vna_trace_values(response: str) -> list[float]:
    text = response.strip()
    if not text:
        return []
    return [float(part.strip()) for part in text.split(",") if part.strip()]


def parse_vna_sdata(response: str) -> tuple[list[float], list[float]]:
    values = parse_vna_trace_values(response)
    if len(values) % 2 != 0:
        raise ValueError("SDATA response must contain real/imag pairs")
    reals = values[0::2]
    imags = values[1::2]
    return reals, imags


def frequency_axis(start_hz: float, stop_hz: float, count: int) -> list[float]:
    if count <= 0:
        return []
    if count == 1:
        return [start_hz]
    step = (stop_hz - start_hz) / (count - 1)
    return [start_hz + index * step for index in range(count)]


def write_trace_csv(path: Path, frequencies_hz: list[float], values: list[float]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["frequency_hz", "value"])
        for frequency, value in zip(frequencies_hz, values, strict=True):
            writer.writerow([f"{frequency:.6f}", f"{value:.6f}"])
