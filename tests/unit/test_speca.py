"""SpecA SCPI delegation, bandwidth calculation, and trace plot artifacts."""

from __future__ import annotations

import csv
from unittest.mock import Mock

import numpy as np
import pytest
from colosseum_equipment.instruments.factory import build_instrument
from colosseum_equipment.instruments.speca.bandwidth import measure_bandwidth_hz
from colosseum_equipment.instruments.speca.generic import GenericSpecA
from colosseum_equipment.instruments.speca.keysight_e4407b import KeysightE4407BSpecA
from colosseum_equipment.instruments.speca.trace_csv import frequency_axis

from tests.support.stubs import RfStubTransport


@pytest.mark.parametrize("reference, expected", [
    ("max", (12.5, 25)), ("mean", (4.375, 43)), ("median", (5.625, 41)),
])
def test_threshold_reference_power(reference, expected):
    from colosseum_equipment.instruments.speca.bandwidth import bandwidth_edges_hz

    frequencies = [-10, 0, 10, 20, 30, 40, 50, 60]
    amplitudes = [-100, -20, -4, 0, -6, -10, -20, -100]
    edges = bandwidth_edges_hz(frequencies, amplitudes, start_hz=0, stop_hz=50,
                               threshold_db=3, ref_pwr_meas_method=reference)
    assert edges == pytest.approx(expected)
    inst = object.__new__(GenericSpecA)
    inst._fetch_trace = Mock(return_value=(frequencies, amplitudes))
    assert inst.measure_bw(0, 50, ref_pwr_meas_method=reference) == pytest.approx(expected[1] - expected[0])
    assert inst.measure_center_frequency_hz(0, 50, ref_pwr_meas_method=reference) == pytest.approx(sum(expected) / 2)
    assert measure_bandwidth_hz(frequencies, amplitudes, start_hz=0, stop_hz=50,
                                ref_pwr_meas_method=reference) == pytest.approx(expected[1] - expected[0])


@pytest.mark.parametrize("options", [
    {"ref_pwr_meas_method": "rms"},
    *[{"method": method, "ref_pwr_meas_method": reference}
      for method in ["fwhm", "occupied_power", "half_prominence"] for reference in ["mean", "median"]],
])
def test_invalid_reference_power_selection(options):
    from colosseum_equipment.instruments.speca.bandwidth import bandwidth_edges_hz

    with pytest.raises(ValueError, match="ref_pwr_meas_method"):
        bandwidth_edges_hz([0, 1, 2], [-10, 0, -10], start_hz=0, stop_hz=2, **options)


def test_reference_power_uses_smoothed_dbm_samples():
    from colosseum_equipment.instruments.speca.bandwidth import bandwidth_edges_hz

    assert bandwidth_edges_hz([0, 10, 20, 30, 40], [-40, 0, 0, 0, -40],
                              start_hz=0, stop_hz=40, smoothing_order=1, threshold_db=3,
                              ref_pwr_meas_method="mean") == pytest.approx((5.5, 34.5))


@pytest.mark.parametrize("method, expected", [("fwhm", (10, 30)), ("half_prominence", (11, 29))])
def test_power_bandwidth_edges(method, expected):
    from colosseum_equipment.instruments.speca.bandwidth import bandwidth_edges_hz

    amplitude = (10 * np.log10([.1, .5, 1, .5, .1])).tolist()
    edges = bandwidth_edges_hz([0, 10, 20, 30, 40], amplitude, start_hz=0, stop_hz=40, method=method)
    assert edges == pytest.approx(expected)
    # The same relative shape at large dBm values remains numerically stable.
    assert bandwidth_edges_hz([0, 10, 20, 30, 40], [a + 4000 for a in amplitude],
                              start_hz=0, stop_hz=40, method=method) == pytest.approx(expected)


@pytest.mark.parametrize("percent, expected", [(None, (.05, 9.95)), (80, (1, 9))])
def test_occupied_power_nonuniform_axis(percent, expected):
    from colosseum_equipment.instruments.speca.bandwidth import bandwidth_edges_hz

    edges = bandwidth_edges_hz([0, 2, 5, 10], [-20] * 4, start_hz=0, stop_hz=10,
                               method="occupied_power", occupied_power_pct=percent)
    assert edges == pytest.approx(expected)


def test_fwhm_asymmetry_plateaus_and_tied_peaks():
    from colosseum_equipment.instruments.speca.bandwidth import bandwidth_edges_hz

    for power, expected in [([.1, 1, .6, .1], (40 / 9, 22)),
                            ([.1, 1, 1, .1], (40 / 9, 230 / 9))]:
        assert bandwidth_edges_hz([0, 10, 20, 30], (10 * np.log10(power)).tolist(),
                                  start_hz=0, stop_hz=30, method="fwhm") == pytest.approx(expected)
    edges = bandwidth_edges_hz([0, 1, 2, 3, 4], [-20, 0, -20, 0, -20],
                               start_hz=0, stop_hz=4, method="half_prominence")
    assert edges == pytest.approx((.5, 1.5))


def test_power_methods_use_frequency_spacing_and_linear_smoothing():
    from colosseum_equipment.instruments.speca.bandwidth import bandwidth_edges_hz

    assert bandwidth_edges_hz([0, 1, 4], [-10, 0, -10], start_hz=0, stop_hz=4,
                              method="half_prominence") == pytest.approx((.5, 2.5))
    assert bandwidth_edges_hz([0, 10, 20, 30, 40], [-10, -10, 0, -10, -10],
                              start_hz=0, stop_hz=40, smoothing_order=1,
                              method="fwhm") == pytest.approx((10 / 3, 110 / 3))
    assert bandwidth_edges_hz([0, 1, 2], (10 * np.log10([.1, 1, .5])).tolist(),
                              start_hz=0, stop_hz=2, method="occupied_power",
                              occupied_power_pct=80) == pytest.approx((.13 / .55, 1 + .62 / .75))


@pytest.mark.parametrize("options", [
    {"method": "unknown"}, {"method": "fwhm", "threshold_db": 3},
    {"occupied_power_pct": 99}, {"method": "half_prominence", "occupied_power_pct": 99},
    *[{"method": "occupied_power", "occupied_power_pct": p} for p in [0, 100, -1, float("nan"), float("inf")]],
])
def test_invalid_bandwidth_selectors(options):
    from colosseum_equipment.instruments.speca.bandwidth import bandwidth_edges_hz

    with pytest.raises(ValueError):
        bandwidth_edges_hz([0, 1, 2], [-10, 0, -10], start_hz=0, stop_hz=2, **options)


@pytest.mark.parametrize("frequencies, amplitudes", [
    ([0, 0, 2], [-10, 0, -10]), ([0, 2, 1], [-10, 0, -10]),
    ([0, 1, 2], [-10, float("nan"), -10]), ([0, 1, float("inf")], [-10, 0, -10]),
    ([1], [0]),
])
def test_new_methods_reject_invalid_trace(frequencies, amplitudes):
    from colosseum_equipment.instruments.speca.bandwidth import bandwidth_edges_hz

    with pytest.raises(ValueError):
        bandwidth_edges_hz(frequencies, amplitudes, start_hz=0, stop_hz=3, method="fwhm")


@pytest.mark.parametrize("method", ["fwhm", "half_prominence"])
def test_missing_peak_edges_are_not_clipped(method):
    from colosseum_equipment.instruments.speca.bandwidth import bandwidth_edges_hz

    with pytest.raises(ValueError):
        bandwidth_edges_hz([0, 1, 2], [0, 0, 0], start_hz=0, stop_hz=2, method=method)


@pytest.mark.parametrize("method", ["fwhm", "half_prominence", "occupied_power"])
@pytest.mark.parametrize("measurement", ["measure_bw", "measure_center_frequency_hz"])
def test_measurement_api_method_forwarding(unit_runtime_context, monkeypatch, method, measurement):
    from colosseum_equipment.api import speca

    inst = Mock()
    getattr(inst, measurement).return_value = 10.0
    monkeypatch.setattr(speca, "get_cached_instrument", lambda *args: inst)
    percent = 95 if method == "occupied_power" else None
    assert getattr(speca, measurement)(speca_id=1, start_hz=0, stop_hz=40, key="signal",
                                      method=method, occupied_power_pct=percent, save_plot=True) == 10
    kwargs = getattr(inst, measurement).call_args.kwargs
    assert kwargs["method"] == method
    assert kwargs["occupied_power_pct"] == percent
    assert kwargs["threshold_db"] is None
    assert kwargs["save_plot"] is True
    assert kwargs["key"] == "signal"


@pytest.mark.parametrize("measurement", ["measure_bw", "measure_center_frequency_hz"])
def test_measurement_api_reference_power_forwarding(unit_runtime_context, monkeypatch, measurement):
    from colosseum_equipment.api import speca

    inst = Mock()
    getattr(inst, measurement).return_value = 10.0
    monkeypatch.setattr(speca, "get_cached_instrument", lambda *args: inst)
    getattr(speca, measurement)(speca_id=1, start_hz=0, stop_hz=50, key="signal",
                                threshold_db=6, ref_pwr_meas_method="median")
    assert getattr(inst, measurement).call_args.kwargs["ref_pwr_meas_method"] == "median"


@pytest.mark.plot
@pytest.mark.parametrize("measurement", ["measure_bw", "measure_center_frequency_hz"])
@pytest.mark.parametrize("method, reference", [
    (None, "max"), (None, "mean"), (None, "median"),
    ("fwhm", "max"), ("occupied_power", "max"), ("half_prominence", "max"),
])
def test_annotated_measurement_plot(unit_runtime_context, monkeypatch, tmp_path, measurement, method, reference):
    from matplotlib.figure import Figure
    from colosseum_equipment.instruments.speca import generic
    from colosseum_equipment.instruments.speca.bandwidth import bandwidth_edges_hz

    frequencies = [0, 10, 20, 30, 40]
    amplitudes = [-10, -3.01029995664, 0, -3.01029995664, -10]
    inst = object.__new__(GenericSpecA)
    inst._fetch_trace = Mock(return_value=(frequencies, amplitudes))
    artifacts = []
    figures = []
    original_save = Figure.savefig

    def save(figure, *args, **kwargs):
        figures.append(figure)
        return original_save(figure, *args, **kwargs)

    monkeypatch.setattr(Figure, "savefig", save)
    monkeypatch.setattr(generic, "record_artifact", lambda **kwargs: artifacts.append(kwargs))
    monkeypatch.setattr(generic, "resolve_artifact_path", lambda path: tmp_path / path)
    left, right = bandwidth_edges_hz(frequencies, amplitudes, start_hz=0, stop_hz=40, method=method,
                                          ref_pwr_meas_method=reference)
    result = getattr(inst, measurement)(0, 40, method=method, ref_pwr_meas_method=reference, key="signal", save_plot=True)
    inst._fetch_trace.assert_called_once()  # Plotting must not trigger a second acquisition.
    assert result == pytest.approx(right - left if measurement == "measure_bw" else (left + right) / 2)
    axis = figures[0].axes[0]
    assert list(axis.lines[0].get_xdata()) == frequencies
    assert list(axis.lines[0].get_ydata()) == amplitudes
    if measurement == "measure_bw":
        assert [line.get_xdata()[0] for line in axis.lines[1:]] == pytest.approx([left, right])
        assert f"Lower: {left:.3e} Hz" in axis.texts[0].get_text()
        assert f"Upper: {right:.3e} Hz" in axis.texts[0].get_text()
        assert f"Bandwidth: {right - left:.3e} Hz" in axis.texts[0].get_text()
    else:
        dot = axis.lines[1]
        assert dot.get_marker() == "o"
        assert dot.get_xdata()[0] == pytest.approx(result)
        assert dot.get_ydata()[0] == pytest.approx(np.interp(result, frequencies, amplitudes))
        assert axis.texts[0].get_text() == f"Center: {result:.3e} Hz"
    assert axis.texts[0].get_position() == (.02, .97)
    assert axis.xaxis.get_minor_locator().__class__.__name__ == "AutoMinorLocator"
    assert axis.yaxis.get_minor_locator().__class__.__name__ == "AutoMinorLocator"
    assert artifacts[0]["value"]["source_key"] == "signal"
    assert artifacts[0]["value"]["value"] == pytest.approx(result)
    assert artifacts[0]["value"]["ref_pwr_meas_method"] == (reference if method is None else None)
    assert artifacts[0]["key"] != "signal"
    assert artifacts[0]["path"].read_bytes().startswith(b"\x89PNG")
    getattr(inst, measurement)(0, 40, method=method, ref_pwr_meas_method=reference, key="signal", save_plot=True)
    assert artifacts[0]["path"] != artifacts[1]["path"]
    getattr(inst, measurement)(0, 40, method=method, ref_pwr_meas_method=reference, key="signal")
    assert len(artifacts) == len(figures) == 2


@pytest.mark.plot
def test_close_frequency_plot_labels_are_distinguishable(tmp_path, monkeypatch):
    from matplotlib.figure import Figure
    from colosseum_equipment.instruments.speca.trace_plot import _write_trace_plot

    figures = []
    original_save = Figure.savefig

    def save(figure, *args, **kwargs):
        figures.append(figure)
        return original_save(figure, *args, **kwargs)

    monkeypatch.setattr(Figure, "savefig", save)
    _write_trace_plot([999_999_000, 1_000_000_000, 1_000_001_000], [-30, -10, -30],
                      tmp_path / "close.png", edges_hz=(1_000_000_001, 1_000_000_002))
    labels = figures[0].axes[0].texts[0].get_text().splitlines()
    assert float(labels[0].split()[1]) == 1_000_000_001
    assert float(labels[1].split()[1]) == 1_000_000_002
    assert (tmp_path / "close.png").exists()


@pytest.mark.plot
def test_index_only_plot_preserves_global_style(tmp_path, monkeypatch):
    import matplotlib as mpl
    from matplotlib.figure import Figure
    from colosseum_equipment.instruments.speca.trace_plot import write_trace_plot

    csv_path = tmp_path / "index.csv"
    csv_path.write_text("index,amplitude_dbm\n0,-30\n1,-10\n2,-30\n")
    figures = []
    original_save = Figure.savefig

    def save(figure, *args, **kwargs):
        figures.append(figure)
        return original_save(figure, *args, **kwargs)

    monkeypatch.setattr(Figure, "savefig", save)
    font_before = list(mpl.rcParams["font.family"])
    write_trace_plot(csv_path, tmp_path / "index.png")
    axis = figures[0].axes[0]
    assert axis.get_xlabel() == "Index"
    assert axis.get_ylabel() == "Value"
    assert list(axis.lines[0].get_xdata()) == [0, 1, 2]
    assert not axis.texts
    assert mpl.rcParams["font.family"] == font_before


def test_saved_trace_analysis_does_not_acquire(tmp_path):
    path = tmp_path / "trace.csv"
    path.write_text("frequency_hz,amplitude_dbm\n0,-10\n10,0\n20,-10\n")
    inst = object.__new__(GenericSpecA)
    inst._fetch_trace = Mock(side_effect=AssertionError("unexpected sweep"))
    width = inst.measure_bw(0, 20, method="fwhm", trace_path=path)
    center = inst.measure_center_frequency_hz(0, 20, method="fwhm", trace_path=path)
    assert width == pytest.approx(100 / 9)
    assert center == 10


def test_generic_speca_control_commands_write_scpi() -> None:
    transport = RfStubTransport({"*OPC?": "1"})
    inst = build_instrument("speca", 1, {"model": "generic"}, transport)
    assert isinstance(inst, GenericSpecA)

    inst.set_start_frequency(1.0e9)
    inst.set_stop_frequency(2.0e9)
    inst.toggle_marker(1, True)
    inst.toggle_marker(2, False)
    inst.next_peak_right(1)
    inst.next_peak_left(1)
    inst.next_highest_peak(1)
    inst.set_sweep_points(801)
    inst.toggle_trigger_delay(True)
    inst.set_trigger_delay(0.001)
    inst.set_trigger_source("EXT")
    inst.user_preset()

    assert transport.written == [
        "FREQ:STAR 1000000000.000000",
        "FREQ:STOP 2000000000.000000",
        "CALC:MARK1:STAT ON",
        "CALC:MARK2:STAT OFF",
        "CALC:MARK1:MAX:NEXT",
        "CALC:MARK1:MAX:PREV",
        "CALC:MARK1:MAX:NH",
        "SWE:POIN 801",
        "TRIG:DEL:STAT ON",
        "TRIG:DEL 0.001000000",
        "TRIG:SOUR EXT",
        "*RCL 1",
    ]


def test_keysight_e4407b_start_stop_and_sweep_points() -> None:
    transport = RfStubTransport()
    inst = build_instrument("speca", 1, {"model": "keysight-e4407b"}, transport)
    assert isinstance(inst, KeysightE4407BSpecA)

    inst.set_start_frequency(1.0e9)
    inst.set_stop_frequency(2.0e9)
    inst.set_sweep_points(401)

    assert transport.written == [
        "SENS:FREQ:STAR 1000000000.000000",
        "SENS:FREQ:STOP 2000000000.000000",
        "SENS:SWE:POIN 401",
    ]


def test_measure_bandwidth_hz_flat_top_trace() -> None:
    center_hz = 1.5e9
    span_hz = 200e6
    count = 201
    frequencies = frequency_axis(center_hz, span_hz, count)
    amplitudes = [-50.0 if frequency < 1.45e9 or frequency > 1.55e9 else -10.0 for frequency in frequencies]

    bandwidth_hz = measure_bandwidth_hz(
        frequencies,
        amplitudes,
        start_hz=1.4e9,
        stop_hz=1.6e9,
        threshold_db=3.0,
    )
    assert bandwidth_hz == pytest.approx(100e6, rel=0.01)


def test_save_trace_data_csv_only(unit_runtime_context) -> None:
    transport = RfStubTransport(
        {
            "*OPC?": "1",
            "FREQ:CENT?": "1500000000.0",
            "FREQ:SPAN?": "200000000.0",
            "TRAC:DATA? TRACE1": "-10.0,-20.0,-30.0",
        },
    )
    inst = build_instrument("speca", 1, {"model": "generic"}, transport)
    csv_path = inst.save_trace_data("traces/speca.csv", save_plot=False)

    assert csv_path.exists()
    assert not csv_path.with_suffix(".png").exists()
    with csv_path.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 3
    assert rows[0]["frequency_hz"] == "1400000000.000000"
    assert rows[0]["amplitude_dbm"] == "-10.000000"


@pytest.mark.plot
def test_save_trace_data_with_plot(unit_runtime_context) -> None:
    transport = RfStubTransport(
        {
            "*OPC?": "1",
            "FREQ:CENT?": "1500000000.0",
            "FREQ:SPAN?": "200000000.0",
            "TRAC:DATA? TRACE1": "-10.0,-20.0,-30.0",
        },
    )
    inst = build_instrument("speca", 1, {"model": "generic"}, transport)
    csv_path = inst.save_trace_data("traces/speca.csv", save_plot=True)
    plot_path = csv_path.with_suffix(".png")

    assert csv_path.exists()
    assert plot_path.exists()
    with csv_path.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 3
    assert rows[0]["frequency_hz"] == "1400000000.000000"
    assert rows[0]["amplitude_dbm"] == "-10.000000"


def test_generic_speca_save_screenshot(unit_runtime_context) -> None:
    _ = unit_runtime_context
    transport = RfStubTransport({"__raw__": b"#14PNG!"})
    inst = build_instrument("speca", 1, {"model": "generic"}, transport)
    path = inst.save_screenshot("captures/screen.png")
    assert path.exists()
    assert path.read_bytes() == b"PNG!"
    assert "HCOP:SDUM:DATA?" in transport.written


def test_center_frequency_uses_bandwidth_crossings() -> None:
    from colosseum_equipment.instruments.speca.bandwidth import bandwidth_edges_hz

    left, right = bandwidth_edges_hz(
        [0.0, 10.0, 20.0, 30.0], [-10.0, 0.0, -2.0, -10.0],
        start_hz=0.0, stop_hz=30.0, threshold_db=3.0,
    )
    assert left == 7.0
    assert right == 21.25
    from unittest.mock import Mock

    from colosseum_equipment.instruments.speca.generic import GenericSpecA

    instrument = object.__new__(GenericSpecA)
    instrument._fetch_trace = Mock(return_value=([0.0, 10.0, 20.0, 30.0], [-10.0, 0.0, -2.0, -10.0]))
    assert instrument.measure_center_frequency_hz(0.0, 30.0) == 14.125
