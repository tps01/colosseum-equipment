from __future__ import annotations

from typing import Literal

import numpy as np
import numpy.typing as npt

BandwidthMethod = Literal["fwhm", "occupied_power", "half_prominence"]
RefPowerMethod = Literal["max", "mean", "median"]


def _smooth(values: list[float], order: int) -> list[float]:
    if order <= 0 or len(values) < 2:
        return list(values)
    smoothed: list[float] = []
    for index in range(len(values)):
        start = max(0, index - order)
        end = min(len(values), index + order + 1)
        segment = values[start:end]
        smoothed.append(sum(segment) / len(segment))
    return smoothed


def _crossing_frequency(
    frequencies_hz: list[float],
    amplitudes: list[float],
    *,
    start_index: int,
    step: int,
    threshold: float,
) -> float:
    index = start_index
    while 0 <= index < len(amplitudes):
        if amplitudes[index] <= threshold:
            if step > 0 and index > 0:
                left = index - 1
                f0, f1 = frequencies_hz[left], frequencies_hz[index]
                a0, a1 = amplitudes[left], amplitudes[index]
                if a1 != a0:
                    ratio = (threshold - a0) / (a1 - a0)
                    return f0 + ratio * (f1 - f0)
            if step < 0 and index < len(amplitudes) - 1:
                right = index + 1
                f0, f1 = frequencies_hz[index], frequencies_hz[right]
                a0, a1 = amplitudes[index], amplitudes[right]
                if a1 != a0:
                    ratio = (threshold - a0) / (a1 - a0)
                    return f0 + ratio * (f1 - f0)
            return frequencies_hz[index]
        index += step
    return frequencies_hz[max(0, min(len(frequencies_hz) - 1, index - step))]


def _validate_power_axis(
    frequencies_hz: list[float], amplitudes_dbm: list[float],
    start_hz: float, stop_hz: float, count: int,
) -> None:
    if (
        not np.isfinite([start_hz, stop_hz]).all()
        or not np.isfinite(frequencies_hz).all()
        or not np.isfinite(amplitudes_dbm).all()
        or not (np.diff(frequencies_hz) > 0).all()
        or count < 2
    ):
        raise ValueError("method requires finite samples, increasing frequencies and at least two in-band points")


def _power_edges(
    band_freqs: list[float], band_amps: list[float], method: BandwidthMethod,
    occupied_power_pct: float | None, smoothing_order: int,
) -> tuple[float, float]:
    from scipy.integrate import cumulative_trapezoid

    power = np.asarray(_smooth((10 ** ((np.asarray(band_amps) - max(band_amps)) / 10)).tolist(), smoothing_order))
    if method != "occupied_power":
        return _peak_edges(band_freqs, power, method)
    percent = 99.0 if occupied_power_pct is None else occupied_power_pct
    if not np.isfinite(percent) or not 0 < percent < 100:
        raise ValueError("occupied_power_pct must be finite and strictly between 0 and 100")
    cumulative = cumulative_trapezoid(power, band_freqs, initial=0)
    tail = (1 - percent / 100) / 2
    edges = np.interp([tail, 1 - tail], cumulative / cumulative[-1], band_freqs)
    return float(edges[0]), float(edges[1])


def _peak_edges(
    band_freqs: list[float], power: npt.NDArray[np.float64], method: BandwidthMethod,
) -> tuple[float, float]:
    from scipy.signal import peak_prominences, peak_widths

    peak = int(np.argmax(power))
    plateau_end = peak
    while plateau_end + 1 < len(power) and power[plateau_end + 1] == power[peak]:
        plateau_end += 1
    if peak == 0 or plateau_end == len(power) - 1:
        raise ValueError("dominant peak must have edges on both sides inside the analysis window")
    peak = (peak + plateau_end) // 2
    if method == "half_prominence":
        prominence = peak_prominences(power, [peak])
        if prominence[0][0] <= 0:
            raise ValueError("dominant peak has zero prominence")
        _, _, left, right = peak_widths(power, [peak], rel_height=0.5, prominence_data=prominence)
        edges = np.interp([left[0], right[0]], np.arange(len(power)), band_freqs)
        return float(edges[0]), float(edges[1])

    half = float(power[peak] / 2)
    if not (power[:peak] <= half).any() or not (power[peak + 1:] <= half).any():
        raise ValueError("FWHM crossings are missing inside the analysis window")
    values = power.tolist()
    return (
        _crossing_frequency(band_freqs, values, start_index=peak, step=-1, threshold=half),
        _crossing_frequency(band_freqs, values, start_index=peak, step=1, threshold=half),
    )


def _validate_methods(
    method: BandwidthMethod | None, threshold_db: float | None,
    occupied_power_pct: float | None, ref_pwr_meas_method: RefPowerMethod,
) -> None:
    if ref_pwr_meas_method not in ("max", "mean", "median"):
        raise ValueError("ref_pwr_meas_method must be max, mean or median")
    if method is not None and ref_pwr_meas_method != "max":
        raise ValueError("ref_pwr_meas_method applies only to threshold_db analysis")
    if method not in (None, "fwhm", "occupied_power", "half_prominence"):
        raise ValueError(f"unknown bandwidth method: {method!r}")
    if method is not None and threshold_db is not None:
        raise ValueError("method and threshold_db are mutually exclusive")
    if occupied_power_pct is not None and method != "occupied_power":
        raise ValueError("occupied_power_pct requires method='occupied_power'")


def bandwidth_edges_hz(
    frequencies_hz: list[float],
    amplitudes_dbm: list[float],
    *,
    start_hz: float,
    stop_hz: float,
    threshold_db: float | None = None,
    smoothing_order: int = 0,
    method: BandwidthMethod | None = None,
    occupied_power_pct: float | None = None,
    ref_pwr_meas_method: RefPowerMethod = "max",
) -> tuple[float, float]:
    _validate_methods(method, threshold_db, occupied_power_pct, ref_pwr_meas_method)
    if len(frequencies_hz) != len(amplitudes_dbm):
        raise ValueError("frequency and amplitude arrays must have equal length")
    if start_hz > stop_hz:
        raise ValueError("start_hz must be <= stop_hz")

    band_freqs: list[float] = []
    band_amps: list[float] = []
    for frequency, amplitude in zip(frequencies_hz, amplitudes_dbm, strict=True):
        if start_hz <= frequency <= stop_hz:
            band_freqs.append(frequency)
            band_amps.append(amplitude)

    if not band_freqs:
        raise ValueError("no trace points in the requested frequency band")

    if method is not None:
        _validate_power_axis(frequencies_hz, amplitudes_dbm, start_hz, stop_hz, len(band_freqs))
        return _power_edges(band_freqs, band_amps, method, occupied_power_pct, smoothing_order)

    smoothed = _smooth(band_amps, smoothing_order)
    peak_index = max(range(len(smoothed)), key=lambda index: smoothed[index])
    reference_dbm = smoothed[peak_index]
    if ref_pwr_meas_method != "max":
        reference_dbm = float(getattr(np, ref_pwr_meas_method)(smoothed))
    threshold_dbm = reference_dbm - (3.0 if threshold_db is None else threshold_db)

    left_hz = _crossing_frequency(
        band_freqs,
        smoothed,
        start_index=peak_index,
        step=-1,
        threshold=threshold_dbm,
    )
    right_hz = _crossing_frequency(
        band_freqs,
        smoothed,
        start_index=peak_index,
        step=1,
        threshold=threshold_dbm,
    )
    return left_hz, right_hz


def measure_bandwidth_hz(
    frequencies_hz: list[float], amplitudes_dbm: list[float], *, start_hz: float,
    stop_hz: float, threshold_db: float | None = None, smoothing_order: int = 0,
    method: BandwidthMethod | None = None, occupied_power_pct: float | None = None,
    ref_pwr_meas_method: RefPowerMethod = "max",
) -> float:
    left, right = bandwidth_edges_hz(
        frequencies_hz, amplitudes_dbm, start_hz=start_hz, stop_hz=stop_hz,
        threshold_db=threshold_db, smoothing_order=smoothing_order,
        method=method, occupied_power_pct=occupied_power_pct, ref_pwr_meas_method=ref_pwr_meas_method,
    )
    return max(0.0, right - left)
