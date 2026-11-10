"""Matplotlib helpers for GNSS track, skyplot, quality, signal, and deviation plots."""

from __future__ import annotations

import csv
import math
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

    from matplotlib.axes import Axes

_TRACK_FIELD_NAMES = (
    "host_ts_iso",
    "receiver_utc_iso",
    "fix_ok",
    "fix_quality",
    "latitude",
    "longitude",
    "altitude_m",
    "sats_used",
    "sats_visible",
    "hdop",
    "pdop",
    "vdop",
    "gdop",
    "speed_m_s",
    "course_deg",
    "h_acc_m",
    "v_acc_m",
    "max_cn0_dbhz",
    "data_age_s",
    "stream_ok",
)


def _float_or_none(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def read_track_csv(path: Path) -> list[dict[str, float | str]]:
    """Load track CSV preserving all known columns (blank numerics stay ``\"\"``)."""
    rows: list[dict[str, float | str]] = []
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            out: dict[str, float | str] = {}
            for name in _TRACK_FIELD_NAMES:
                raw = row.get(name, "")
                if name in {
                    "host_ts_iso",
                    "receiver_utc_iso",
                    "fix_ok",
                    "stream_ok",
                }:
                    out[name] = raw if raw is not None else ""
                    continue
                parsed = _float_or_none(raw)
                out[name] = parsed if parsed is not None else ("" if raw in (None, "") else str(raw))
            # Back-compat aliases used by older plot code / fabricated CSVs
            if "satellites" not in out and out.get("sats_used") != "":
                out["satellites"] = out.get("sats_used", "")
            if not out.get("receiver_utc_iso") and row.get("utc_iso"):
                out["receiver_utc_iso"] = str(row.get("utc_iso") or "")
            rows.append(out)
    return rows


def write_track_plot(
    rows: list[dict[str, float | str]],
    plot_path: Path,
    *,
    color_by: str = "hdop",
) -> None:
    import matplotlib as mpl

    mpl.use("Agg")
    import matplotlib.pyplot as plt

    if not rows:
        raise ValueError("track has no samples to plot")
    points: list[tuple[float, float, float]] = []
    for idx, row in enumerate(rows):
        lat = row.get("latitude")
        lon = row.get("longitude")
        if lat == "" or lon == "" or lat is None or lon is None:
            continue
        try:
            color_val = float(row.get(color_by, idx) or idx)
        except (TypeError, ValueError):
            color_val = float(idx)
        points.append((float(lon), float(lat), color_val))
    if not points:
        raise ValueError("track has no fix samples to plot")
    lons = [p[0] for p in points]
    lats = [p[1] for p in points]
    colors = [p[2] for p in points]
    plot_path.parent.mkdir(parents=True, exist_ok=True)
    figure, axis = plt.subplots(figsize=(7, 7))
    try:
        scatter = axis.scatter(lons, lats, c=colors, cmap="viridis", s=12)
        axis.plot(lons, lats, color="0.5", linewidth=0.8, alpha=0.5)
        axis.set_xlabel("Longitude (deg)")
        axis.set_ylabel("Latitude (deg)")
        axis.set_title(f"GNSS track (color={color_by})")
        axis.grid(True, alpha=0.3)
        axis.set_aspect("equal", adjustable="datalim")
        figure.colorbar(scatter, ax=axis, fraction=0.046, pad=0.04)
        figure.savefig(plot_path, dpi=120, bbox_inches="tight")
    finally:
        plt.close(figure)


_SKY_CONSTELLATION_COLORS = {
    "GPS": "C0",
    "GLONASS": "C1",
    "Galileo": "C2",
    "BeiDou": "C3",
    "QZSS": "C4",
}


def _skyplot_rows(
    sats: dict[int, tuple[float, float, float]] | list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if isinstance(sats, dict):
        return [
            {"prn": prn, "elev": elev, "az": az, "cn0": cn0, "constellation": "", "used": False}
            for prn, (elev, az, cn0) in sats.items()
        ]
    return list(sats)


def _draw_skyplot_sat(axis: Axes, row: dict[str, Any], *, vmax: float) -> None:
    elev = float(row.get("elev") or 0)
    az = float(row.get("az") or 0)
    cn0 = float(row.get("cn0") or 0)
    used = bool(row.get("used"))
    constellation = str(row.get("constellation") or "")
    radius = max(0.0, 90.0 - elev)
    theta = az * (math.pi / 180.0)
    size = 20 + 40 * (cn0 / vmax if vmax else 0)
    axis.scatter(
        theta,
        radius,
        s=size,
        c=[cn0],
        cmap="viridis",
        vmin=0,
        vmax=max(vmax, 1),
        edgecolors="black" if used else "0.6",
        linewidths=1.2 if used else 0.5,
        alpha=1.0 if used else 0.55,
    )
    # Keep constellation hue as a thin ring via annotation color
    face = _SKY_CONSTELLATION_COLORS.get(constellation, "C5")
    axis.text(theta, radius, str(row.get("prn")), fontsize=8, color=face)


def write_skyplot(
    sats: dict[int, tuple[float, float, float]] | list[dict[str, Any]],
    plot_path: Path,
) -> None:
    """Polar skyplot: elevation from zenith, azimuth clockwise from north.

    Accepts either legacy ``{prn: (elev, az, cn0)}`` or snapshot dict rows with
    ``prn`` / ``elev`` / ``az`` / ``cn0`` / ``constellation`` / ``used``.
    """
    import matplotlib as mpl

    mpl.use("Agg")
    import matplotlib.pyplot as plt

    rows = _skyplot_rows(sats)
    if not rows:
        raise ValueError("no GSV satellites to plot")

    plot_path.parent.mkdir(parents=True, exist_ok=True)
    figure, axis = plt.subplots(figsize=(6, 6), subplot_kw={"projection": "polar"})
    try:
        snrs = [float(r.get("cn0") or 0) for r in rows]
        vmax = max(snrs) if snrs else 1.0
        for row in rows:
            _draw_skyplot_sat(axis, row, vmax=vmax)
        axis.set_theta_zero_location("N")  # type: ignore[attr-defined]
        axis.set_theta_direction(-1)  # type: ignore[attr-defined]
        axis.set_rlim(0, 90)  # type: ignore[attr-defined]
        axis.set_rticks([0, 30, 60, 90])  # type: ignore[attr-defined]
        axis.set_title("GNSS skyplot")
        figure.savefig(plot_path, dpi=120, bbox_inches="tight")
    finally:
        plt.close(figure)


def _quality_series(
    rows: list[dict[str, float | str]],
    name: str,
    fallback: str = "",
) -> list[float]:
    out: list[float] = []
    for row in rows:
        raw = row.get(name, row.get(fallback, 0))
        try:
            out.append(float(raw) if raw != "" else 0.0)
        except (TypeError, ValueError):
            out.append(0.0)
    return out


def _quality_fix_ok(rows: list[dict[str, float | str]]) -> list[float]:
    fix_ok: list[float] = []
    for row in rows:
        raw = row.get("fix_ok")
        if raw in (True, "True", "true", "1", 1):
            fix_ok.append(1.0)
        elif raw in (False, "False", "false", "0", 0):
            fix_ok.append(0.0)
        else:
            fix_ok.append(0.0)
    return fix_ok


def _quality_sample_times(rows: list[dict[str, float | str]]) -> list[float]:
    # Prefer host timestamps when present; else sample index
    times: list[float] = []
    for idx, row in enumerate(rows):
        host = str(row.get("host_ts_iso") or "")
        if host:
            times.append(float(idx))
        else:
            times.append(float(idx))
    return times


def _plot_quality_dop_panel(
    axis: Axes,
    times: list[float],
    *,
    hdop: list[float],
    pdop: list[float],
    vdop: list[float],
) -> None:
    axis.plot(times, hdop, label="HDOP")
    if any(pdop):
        axis.plot(times, pdop, label="PDOP", alpha=0.85)
    if any(vdop):
        axis.plot(times, vdop, label="VDOP", alpha=0.85)
    axis.set_ylabel("DOP")
    axis.legend(loc="upper right", fontsize=8)
    axis.grid(True, alpha=0.3)
    axis.set_title("GNSS quality")


def _plot_quality_sat_panel(
    axis: Axes,
    times: list[float],
    *,
    sats: list[float],
    visible: list[float],
    cn0: list[float],
) -> None:
    axis.plot(times, sats, label="sats used")
    if any(visible):
        axis.plot(times, visible, label="sats visible", alpha=0.85)
    if any(cn0):
        axis.plot(times, cn0, label="max C/N0", alpha=0.7)
    axis.set_ylabel("Sats / C/N0")
    axis.legend(loc="upper right", fontsize=8)
    axis.grid(True, alpha=0.3)


def _plot_quality_fix_panel(
    axis: Axes,
    times: list[float],
    *,
    h_acc: list[float],
    fix_ok: list[float],
) -> None:
    if any(h_acc):
        axis.plot(times, h_acc, label="h_acc_m", color="C3")
    axis.fill_between(times, 0, fix_ok, alpha=0.25, color="C2", label="fix_ok")
    axis.set_ylabel("h_acc / fix")
    axis.set_xlabel("Sample index")
    axis.legend(loc="upper right", fontsize=8)
    axis.grid(True, alpha=0.3)


def _quality_panel_data(
    rows: list[dict[str, float | str]],
) -> tuple[list[float], dict[str, list[float]]]:
    times = _quality_sample_times(rows)
    series = {
        "hdop": _quality_series(rows, "hdop"),
        "pdop": _quality_series(rows, "pdop"),
        "vdop": _quality_series(rows, "vdop"),
        "sats": _quality_series(rows, "sats_used", "satellites"),
        "visible": _quality_series(rows, "sats_visible"),
        "cn0": _quality_series(rows, "max_cn0_dbhz"),
        "h_acc": _quality_series(rows, "h_acc_m"),
        "fix_ok": _quality_fix_ok(rows),
    }
    return times, series


def write_quality_plot(rows: list[dict[str, float | str]], plot_path: Path) -> None:
    import matplotlib as mpl

    mpl.use("Agg")
    import matplotlib.pyplot as plt

    if not rows:
        raise ValueError("track has no samples to plot")

    times, series = _quality_panel_data(rows)
    plot_path.parent.mkdir(parents=True, exist_ok=True)
    figure, axes = plt.subplots(3, 1, figsize=(9, 8), sharex=True)
    try:
        _plot_quality_dop_panel(
            axes[0],
            times,
            hdop=series["hdop"],
            pdop=series["pdop"],
            vdop=series["vdop"],
        )
        _plot_quality_sat_panel(
            axes[1],
            times,
            sats=series["sats"],
            visible=series["visible"],
            cn0=series["cn0"],
        )
        _plot_quality_fix_panel(
            axes[2],
            times,
            h_acc=series["h_acc"],
            fix_ok=series["fix_ok"],
        )
        figure.tight_layout()
        figure.savefig(plot_path, dpi=120, bbox_inches="tight")
    finally:
        plt.close(figure)


def write_signal_levels_plot(
    snapshot: list[dict[str, Any]],
    plot_path: Path,
) -> None:
    """Bar chart of per-satellite C/N0 grouped by constellation."""
    import matplotlib as mpl

    mpl.use("Agg")
    import matplotlib.pyplot as plt

    if not snapshot:
        raise ValueError("no satellites for signal levels plot")
    ordered = sorted(
        snapshot,
        key=lambda row: (str(row.get("constellation") or ""), int(row.get("prn") or 0)),
    )
    labels = [
        f"{row.get('constellation', '')[:3]}{row.get('prn')}"
        for row in ordered
    ]
    values = [float(row.get("cn0") or 0) for row in ordered]
    used_flags = [bool(row.get("used")) for row in ordered]
    colors = ["C0" if used else "0.75" for used in used_flags]
    plot_path.parent.mkdir(parents=True, exist_ok=True)
    figure, axis = plt.subplots(figsize=(max(8, len(labels) * 0.35), 4))
    try:
        axis.bar(range(len(labels)), values, color=colors)
        axis.set_xticks(range(len(labels)))
        axis.set_xticklabels(labels, rotation=75, ha="right", fontsize=8)
        axis.set_ylabel("C/N0 (dB-Hz)")
        axis.set_title("GNSS signal levels (faint = unused)")
        axis.grid(True, axis="y", alpha=0.3)
        figure.tight_layout()
        figure.savefig(plot_path, dpi=120, bbox_inches="tight")
    finally:
        plt.close(figure)


def _enu_offsets_m(
    rows: list[dict[str, float | str]],
    *,
    ref_lat: float | None,
    ref_lon: float | None,
) -> tuple[list[float], list[float], float, float]:
    fix_rows = [
        row
        for row in rows
        if row.get("latitude") not in ("", None) and row.get("longitude") not in ("", None)
    ]
    if not fix_rows:
        raise ValueError("track has no fix samples for deviation plot")
    lats = [float(row["latitude"]) for row in fix_rows]
    lons = [float(row["longitude"]) for row in fix_rows]
    mean_lat = sum(lats) / len(lats)
    mean_lon = sum(lons) / len(lons)
    origin_lat = mean_lat if ref_lat is None else ref_lat
    origin_lon = mean_lon if ref_lon is None else ref_lon
    meters_per_deg_lat = 111_320.0
    meters_per_deg_lon = 111_320.0 * math.cos(math.radians(origin_lat))
    east = [(lon - origin_lon) * meters_per_deg_lon for lon in lons]
    north = [(lat - origin_lat) * meters_per_deg_lat for lat in lats]
    return east, north, origin_lat, origin_lon


def write_deviation_plot(
    rows: list[dict[str, float | str]],
    plot_path: Path,
    *,
    ref_lat: float | None = None,
    ref_lon: float | None = None,
) -> dict[str, float]:
    """East/north scatter about mean or supplied reference; return CEP stats."""
    import matplotlib as mpl

    mpl.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle

    if not rows:
        raise ValueError("track has no samples to plot")
    east, north, origin_lat, origin_lon = _enu_offsets_m(rows, ref_lat=ref_lat, ref_lon=ref_lon)
    radii = [math.hypot(e, n) for e, n in zip(east, north, strict=True)]
    sorted_r = sorted(radii)
    n = len(sorted_r)

    def _percentile(p: float) -> float:
        if n == 0:
            return 0.0
        idx = min(n - 1, max(0, int(math.ceil(p / 100.0 * n) - 1)))
        return float(sorted_r[idx])

    cep50 = _percentile(50)
    cep95 = _percentile(95)
    plot_path.parent.mkdir(parents=True, exist_ok=True)
    figure, axis = plt.subplots(figsize=(6, 6))
    try:
        axis.scatter(east, north, s=10, alpha=0.7)
        axis.axhline(0.0, color="0.5", linewidth=0.8)
        axis.axvline(0.0, color="0.5", linewidth=0.8)
        for radius, style, label in (
            (cep50, "-", "CEP50"),
            (cep95, "--", "CEP95"),
        ):
            circle = Circle((0, 0), radius, fill=False, linestyle=style, label=label)
            axis.add_patch(circle)
        axis.set_aspect("equal", adjustable="datalim")
        axis.set_xlabel("East (m)")
        axis.set_ylabel("North (m)")
        axis.set_title(
            f"GNSS deviation (ref {origin_lat:.6f},{origin_lon:.6f}; n={n})",
        )
        axis.legend(loc="best", fontsize=8)
        axis.grid(True, alpha=0.3)
        figure.savefig(plot_path, dpi=120, bbox_inches="tight")
    finally:
        plt.close(figure)
    return {
        "cep50_m": cep50,
        "cep95_m": cep95,
        "n": float(n),
        "ref_lat": origin_lat,
        "ref_lon": origin_lon,
    }
