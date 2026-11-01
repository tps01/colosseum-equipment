from __future__ import annotations

import csv
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


def read_trace_csv(path: Path) -> tuple[list[float], list[float]]:
    """Return ``(frequencies, amplitudes)`` from a SpecA trace CSV.

    When the header includes ``frequency_hz``, every data row must supply both
    a frequency and an amplitude (``amplitude_dbm`` or ``value``). Incomplete
    rows raise ``ValueError``. Amplitude-only CSVs (no ``frequency_hz`` column)
    still return an empty frequency list.
    """
    frequencies: list[float] = []
    amplitudes: list[float] = []
    with path.open(encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = set(reader.fieldnames or ())
        has_frequency = "frequency_hz" in fieldnames
        for row_number, row in enumerate(reader, start=2):
            amp_text = (row.get("amplitude_dbm") or row.get("value") or "").strip()
            if has_frequency:
                freq_text = (row.get("frequency_hz") or "").strip()
                if not freq_text or not amp_text:
                    raise ValueError(
                        f"trace CSV {path} row {row_number} must include both "
                        "frequency_hz and amplitude",
                    )
                frequencies.append(float(freq_text))
                amplitudes.append(float(amp_text))
                continue
            if not amp_text:
                raise ValueError(
                    f"trace CSV {path} row {row_number} must include amplitude_dbm or value",
                )
            amplitudes.append(float(amp_text))
    if not amplitudes:
        raise ValueError(f"trace CSV is empty: {path}")
    return frequencies, amplitudes


def write_trace_plot(csv_path: Path, plot_path: Path) -> None:
    import matplotlib as mpl

    mpl.use("Agg")
    import matplotlib.pyplot as plt

    frequencies, amplitudes = read_trace_csv(csv_path)
    x_values = frequencies if frequencies else list(range(len(amplitudes)))
    x_label = "Frequency (Hz)" if frequencies else "Index"
    y_label = "Amplitude (dBm)" if frequencies else "Value"

    plot_path.parent.mkdir(parents=True, exist_ok=True)
    figure, axis = plt.subplots(figsize=(8, 4))
    try:
        axis.plot(x_values, amplitudes)
        axis.set_xlabel(x_label)
        axis.set_ylabel(y_label)
        axis.grid(True, alpha=0.3)
        figure.savefig(plot_path, dpi=120, bbox_inches="tight")
    finally:
        plt.close(figure)
