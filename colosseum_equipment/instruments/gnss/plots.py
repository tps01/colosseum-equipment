"""Matplotlib helpers for GNSS track, skyplot, and quality strips."""

from __future__ import annotations

import csv
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


def _float_or_none(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def read_track_csv(path: Path) -> list[dict[str, float | str]]:
    rows: list[dict[str, float | str]] = []
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            lat = _float_or_none(row.get("latitude"))
            lon = _float_or_none(row.get("longitude"))
            sats = row.get("sats_used") or row.get("satellites") or 0
            rows.append(
                {
                    "utc_iso": row.get("receiver_utc_iso") or row.get("utc_iso") or "",
                    "latitude": lat if lat is not None else "",
                    "longitude": lon if lon is not None else "",
                    "altitude_m": _float_or_none(row.get("altitude_m")) or 0,
                    "fix_quality": _float_or_none(row.get("fix_quality")) or 0,
                    "satellites": _float_or_none(sats) or 0,
                    "hdop": _float_or_none(row.get("hdop")) or 0,
                    "pdop": _float_or_none(row.get("pdop")) or 0,
                    "vdop": _float_or_none(row.get("vdop")) or 0,
                    "max_cn0_dbhz": _float_or_none(row.get("max_cn0_dbhz")) or 0,
                    "fix_ok": row.get("fix_ok") or "",
                },
            )
    return rows


def write_track_plot(rows: list[dict[str, float | str]], plot_path: Path) -> None:
    import matplotlib as mpl

    mpl.use("Agg")
    import matplotlib.pyplot as plt

    if not rows:
        raise ValueError("track has no samples to plot")
    points = [
        (float(row["longitude"]), float(row["latitude"]))
        for row in rows
        if row.get("longitude") != "" and row.get("latitude") != ""
    ]
    if not points:
        raise ValueError("track has no fix samples to plot")
    lons = [p[0] for p in points]
    lats = [p[1] for p in points]
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
        snrs = [float(snr) for _, (_, _, snr) in sats.items()]
        vmax = max(snrs) if snrs else 1.0
        for prn, (elev, az, snr) in sats.items():
            # Elevation 90 at center → radius = 90 - elev.
            radius = max(0.0, 90.0 - float(elev))
            theta = float(az) * (3.141592653589793 / 180.0)
            size = 20 + 40 * (float(snr) / vmax if vmax else 0)
            axis.scatter(theta, radius, s=size, c=[float(snr)], cmap="viridis", vmin=0, vmax=max(vmax, 1))
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

    def _series(name: str, fallback: str = "") -> list[float]:
        out: list[float] = []
        for row in rows:
            raw = row.get(name, row.get(fallback, 0))
            try:
                out.append(float(raw) if raw != "" else 0.0)
            except (TypeError, ValueError):
                out.append(0.0)
        return out

    hdop = _series("hdop")
    pdop = _series("pdop")
    sats = _series("sats_used", "satellites")
    cn0 = _series("max_cn0_dbhz")
    plot_path.parent.mkdir(parents=True, exist_ok=True)
    figure, axis_hdop = plt.subplots(figsize=(8, 4))
    try:
        axis_hdop.plot(elapsed, hdop, color="C0", label="HDOP")
        if any(pdop):
            axis_hdop.plot(elapsed, pdop, color="C2", label="PDOP", alpha=0.8)
        axis_hdop.set_xlabel("Sample index")
        axis_hdop.set_ylabel("DOP", color="C0")
        axis_sats = axis_hdop.twinx()
        axis_sats.plot(elapsed, sats, color="C1", label="Satellites")
        if any(cn0):
            axis_sats.plot(elapsed, cn0, color="C3", label="max C/N0", alpha=0.7)
        axis_sats.set_ylabel("Sats / C/N0", color="C1")
        axis_hdop.set_title("GNSS quality (DOP, satellites, C/N0)")
        axis_hdop.grid(True, alpha=0.3)
        figure.savefig(plot_path, dpi=120, bbox_inches="tight")
    finally:
        plt.close(figure)
