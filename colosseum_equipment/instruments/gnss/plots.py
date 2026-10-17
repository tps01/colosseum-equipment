"""Matplotlib helpers for GNSS track, skyplot, and quality strips."""

from __future__ import annotations

import csv
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


def read_track_csv(path: Path) -> list[dict[str, float | str]]:
    rows: list[dict[str, float | str]] = []
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            try:
                rows.append(
                    {
                        "utc_iso": row.get("utc_iso") or "",
                        "latitude": float(row["latitude"]),
                        "longitude": float(row["longitude"]),
                        "altitude_m": float(row.get("altitude_m") or 0),
                        "fix_quality": float(row.get("fix_quality") or 0),
                        "satellites": float(row.get("satellites") or 0),
                        "hdop": float(row.get("hdop") or 0),
                    },
                )
            except (KeyError, TypeError, ValueError):
                continue
    return rows


def write_track_plot(rows: list[dict[str, float | str]], plot_path: Path) -> None:
    import matplotlib as mpl

    mpl.use("Agg")
    import matplotlib.pyplot as plt

    if not rows:
        raise ValueError("track has no samples to plot")
    lons = [float(row["longitude"]) for row in rows]
    lats = [float(row["latitude"]) for row in rows]
    plot_path.parent.mkdir(parents=True, exist_ok=True)
    figure, axis = plt.subplots(figsize=(7, 7))
    try:
        axis.plot(lons, lats, marker="o", markersize=3, linewidth=1)
        axis.set_xlabel("Longitude (deg)")
        axis.set_ylabel("Latitude (deg)")
        axis.set_title("GNSS track")
        axis.grid(True, alpha=0.3)
        axis.set_aspect("equal", adjustable="datalim")
        figure.savefig(plot_path, dpi=120, bbox_inches="tight")
    finally:
        plt.close(figure)


def write_skyplot(
    sats: dict[int, tuple[float, float, float]],
    plot_path: Path,
) -> None:
    """Polar skyplot: elevation from zenith, azimuth clockwise from north."""
    import matplotlib as mpl

    mpl.use("Agg")
    import matplotlib.pyplot as plt

    if not sats:
        raise ValueError("no GSV satellites to plot")
    plot_path.parent.mkdir(parents=True, exist_ok=True)
    figure, axis = plt.subplots(figsize=(6, 6), subplot_kw={"projection": "polar"})
    try:
        for prn, (elev, az, _snr) in sats.items():
            # Elevation 90 at center → radius = 90 - elev.
            radius = max(0.0, 90.0 - float(elev))
            theta = float(az) * (3.141592653589793 / 180.0)
            axis.plot(theta, radius, "o")
            axis.text(theta, radius, str(prn), fontsize=8)
        # PolarAxes methods are not on the generic Axes stub.
        axis.set_theta_zero_location("N")  # type: ignore[attr-defined]
        axis.set_theta_direction(-1)  # type: ignore[attr-defined]
        axis.set_rlim(0, 90)  # type: ignore[attr-defined]
        axis.set_rticks([0, 30, 60, 90])  # type: ignore[attr-defined]
        axis.set_title("GNSS skyplot")
        figure.savefig(plot_path, dpi=120, bbox_inches="tight")
    finally:
        plt.close(figure)


def write_quality_plot(rows: list[dict[str, float | str]], plot_path: Path) -> None:
    import matplotlib as mpl

    mpl.use("Agg")
    import matplotlib.pyplot as plt

    if not rows:
        raise ValueError("track has no samples to plot")
    elapsed = list(range(len(rows)))
    hdop = [float(row["hdop"]) for row in rows]
    sats = [float(row["satellites"]) for row in rows]
    plot_path.parent.mkdir(parents=True, exist_ok=True)
    figure, axis_hdop = plt.subplots(figsize=(8, 4))
    try:
        axis_hdop.plot(elapsed, hdop, color="C0", label="HDOP")
        axis_hdop.set_xlabel("Sample index")
        axis_hdop.set_ylabel("HDOP", color="C0")
        axis_sats = axis_hdop.twinx()
        axis_sats.plot(elapsed, sats, color="C1", label="Satellites")
        axis_sats.set_ylabel("Satellites", color="C1")
        axis_hdop.set_title("GNSS HDOP and satellites")
        axis_hdop.grid(True, alpha=0.3)
        figure.savefig(plot_path, dpi=120, bbox_inches="tight")
    finally:
        plt.close(figure)
