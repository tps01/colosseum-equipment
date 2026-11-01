"""Trace CSV helpers for spectrum analyzers."""

from __future__ import annotations

import pytest
from colosseum_equipment.instruments.speca.trace_csv import (
    frequency_axis,
    nearest_trace_bin,
    parse_trace_amplitudes,
    read_trace_power_at_frequency,
    write_trace_csv,
)


def test_parse_trace_amplitudes() -> None:
    assert parse_trace_amplitudes("-42.5,-41.0,-40.5") == [-42.5, -41.0, -40.5]


def test_frequency_axis_endpoints() -> None:
    freqs = frequency_axis(1e9, 10e6, 3)
    assert freqs[0] == pytest.approx(995e6)
    assert freqs[1] == pytest.approx(1e9)
    assert freqs[2] == pytest.approx(1005e6)


def test_frequency_axis_empty_and_single_point() -> None:
    assert frequency_axis(1e9, 10e6, 0) == []
    assert frequency_axis(1e9, 10e6, -1) == []
    assert frequency_axis(1e9, 10e6, 1) == [1e9]


def test_write_trace_csv_with_frequency(tmp_path) -> None:
    path = tmp_path / "trace.csv"
    write_trace_csv(path, [-42.0, -41.0], center_hz=1e9, span_hz=10e6, include_frequency=True)
    text = path.read_text(encoding="utf-8")
    assert "frequency_hz,amplitude_dbm" in text
    assert "-42.000000" in text


def test_write_trace_csv_index_only_when_frequency_disabled(tmp_path) -> None:
    path = tmp_path / "index.csv"
    write_trace_csv(
        path,
        [-42.0, -41.0],
        center_hz=1e9,
        span_hz=10e6,
        include_frequency=False,
    )
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "index,amplitude_dbm"
    assert lines[1].startswith("0,")
    assert lines[2].startswith("1,")


def test_write_trace_csv_index_only_when_center_or_span_missing(tmp_path) -> None:
    path = tmp_path / "missing_axis.csv"
    write_trace_csv(path, [-40.0], include_frequency=True)
    text = path.read_text(encoding="utf-8")
    assert "index,amplitude_dbm" in text
    assert "frequency_hz" not in text


def test_nearest_trace_bin_picks_closest_frequency() -> None:
    frequencies = [995e6, 1e9, 1005e6]
    assert nearest_trace_bin(frequencies, 1.004e9) == 2
    assert nearest_trace_bin(frequencies, 1e9) == 1


def test_read_trace_power_at_frequency(tmp_path) -> None:
    path = tmp_path / "trace.csv"
    write_trace_csv(path, [-42.5, -41.0, -40.5], center_hz=1e9, span_hz=10e6, include_frequency=True)
    power, actual_hz = read_trace_power_at_frequency(path, 1e9)
    assert power == pytest.approx(-41.0)
    assert actual_hz == pytest.approx(1e9)
    edge_power, _ = read_trace_power_at_frequency(path, 995e6)
    assert edge_power == pytest.approx(-42.5)


def test_read_trace_power_rejects_incomplete_row(tmp_path) -> None:
    path = tmp_path / "incomplete.csv"
    path.write_text(
        "frequency_hz,amplitude_dbm\n,-10\n100,-20\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="row 2.*frequency_hz and amplitude_dbm"):
        read_trace_power_at_frequency(path, 100)


def test_read_trace_power_intact_pair(tmp_path) -> None:
    path = tmp_path / "intact.csv"
    path.write_text(
        "frequency_hz,amplitude_dbm\n50,-10\n100,-20\n",
        encoding="utf-8",
    )
    power, actual_hz = read_trace_power_at_frequency(path, 100)
    assert power == pytest.approx(-20.0)
    assert actual_hz == pytest.approx(100.0)


def test_read_trace_csv_rejects_incomplete_frequency_row(tmp_path) -> None:
    from colosseum_equipment.instruments.speca.trace_plot import read_trace_csv

    path = tmp_path / "plot_incomplete.csv"
    path.write_text(
        "frequency_hz,amplitude_dbm\n,-10\n100,-20\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="row 2.*frequency_hz and amplitude"):
        read_trace_csv(path)
