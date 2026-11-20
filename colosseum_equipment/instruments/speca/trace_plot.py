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
                        f"trace CSV {path} row {row_number} must include both frequency_hz and amplitude",
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
    frequencies, amplitudes = read_trace_csv(csv_path)
    _write_trace_plot(frequencies, amplitudes, plot_path)


def _write_trace_plot(
    frequencies: list[float], amplitudes: list[float], plot_path: Path, *,
    center_hz: float | None = None, edges_hz: tuple[float, float] | None = None,
) -> None:
    import matplotlib as mpl

    mpl.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import AutoMinorLocator

    x_values = frequencies if frequencies else list(range(len(amplitudes)))
    x_label = "Frequency (Hz)" if frequencies else "Index"
    y_label = "Amplitude (dBm)" if frequencies else "Value"

    plot_path.parent.mkdir(parents=True, exist_ok=True)
    with mpl.rc_context({"font.family": "DejaVu Sans", "font.size": 10, "axes.linewidth": 0.8}):
        figure, axis = plt.subplots(figsize=(8, 4))
        try:
            axis.plot(x_values, amplitudes, color="black", linewidth=1.35, zorder=3)
            label = ""
            if center_hz is not None:
                import numpy as np

                axis.plot(center_hz, float(np.interp(center_hz, frequencies, amplitudes)),
                          "o", color="black", markersize=5, zorder=4)
                label = f"Center: {center_hz:.3e} Hz"
            if edges_hz is not None:
                left, right = edges_hz
                for edge in edges_hz:
                    axis.axvline(edge, color="0.15", linestyle="--", linewidth=1.15, zorder=2)
                precision = 3
                while left != right and f"{left:.{precision}e}" == f"{right:.{precision}e}" and precision < 16:
                    precision += 1
                label = (f"Lower: {left:.{precision}e} Hz\nUpper: {right:.{precision}e} Hz\n"
                         f"Bandwidth: {right - left:.3e} Hz")
            if label:
                figure.subplots_adjust(top=0.76 if edges_hz is not None else 0.85)
                axis.text(0.02, 1.04, label, transform=axis.transAxes, va="bottom", ha="left",
                          fontsize=9, clip_on=False,
                          bbox={"facecolor": "white", "edgecolor": "0.75", "pad": 5})
            axis.set_xlabel(x_label, fontsize=10, labelpad=7)
            axis.set_ylabel(y_label, fontsize=10, labelpad=7)
            axis.spines["top"].set_visible(False)
            axis.spines["right"].set_visible(False)
            axis.spines["left"].set_color("0.25")
            axis.spines["bottom"].set_color("0.25")
            axis.grid(True, which="major", color="0.87", linewidth=0.6)
            axis.set_axisbelow(True)
            axis.xaxis.set_minor_locator(AutoMinorLocator())
            axis.yaxis.set_minor_locator(AutoMinorLocator())
            axis.tick_params(which="major", colors="0.2", direction="out", length=3, width=0.7, labelsize=9)
            axis.tick_params(which="minor", colors="0.2", direction="out", length=1.8, width=0.6)
            figure.savefig(plot_path, dpi=120, bbox_inches="tight", facecolor="white")
        finally:
            plt.close(figure)
