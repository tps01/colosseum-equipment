"""Path-loss calibration from VNA sweeps."""

from __future__ import annotations

import csv
import sys
import types
from pathlib import Path
from unittest.mock import patch

import pytest

# Headless images may lack tkinter; stub before importing api package.
if "tkinter" not in sys.modules:
    tk = types.ModuleType("tkinter")
    for name in ("filedialog", "messagebox", "simpledialog", "ttk", "font", "colorchooser"):
        mod = types.ModuleType(f"tkinter.{name}")
        setattr(tk, name, mod)
        sys.modules[f"tkinter.{name}"] = mod
    tk.Tk = type("Tk", (), {"__init__": lambda self, *a, **k: None, "mainloop": lambda self: None})
    tk.StringVar = tk.BooleanVar = tk.IntVar = tk.DoubleVar = type("Var", (), {"__init__": lambda *a, **k: None, "get": lambda self: "", "set": lambda self, v: None})
    tk.END = "end"
    sys.modules["tkinter"] = tk

from colosseum_equipment import calibration as path_cal
from colosseum_equipment.api import asg as asg_api
from colosseum_equipment.api import calibration as cal_api
from colosseum_equipment.api import pwrmeter as pwrmeter_api
from colosseum_equipment.api import speca as speca_api
from colosseum_equipment.api import vsg as vsg_api
from colosseum_equipment.instruments.factory import build_instrument

from tests.support.stubs import RfStubTransport


def _write_csv(path: Path) -> Path:
    path.write_text(
        "frequency_hz,value\n1000000000,-10.0\n2000000000,-15.0\n",
        encoding="utf-8",
    )
    return path


def test_parse_vna_csv_and_headerless_txt(tmp_path: Path) -> None:
    csv_path = _write_csv(tmp_path / "s21.csv")
    freqs, losses = path_cal.parse_calibration_file(csv_path)
    assert freqs == [1e9, 2e9]
    assert losses == [-10.0, -15.0]

    txt = tmp_path / "s21.txt"
    txt.write_text("1e9 -10\n2e9\t-15\n", encoding="utf-8")
    freqs, losses = path_cal.parse_calibration_file(txt)
    assert freqs == pytest.approx([1e9, 2e9])
    assert losses == pytest.approx([-10.0, -15.0])


def test_parse_headerless_three_column_csv(tmp_path: Path) -> None:
    path = tmp_path / "vna.csv"
    path.write_text(
        "\n".join(
            (
                "10000000.0,-81.303819364,0.0",
                "20000000.0,-78.5753999207,0.0",
                "30000000.0,-74.4278824295,0.0",
                "40000000.0,-71.3905785337,0.0",
                "50000000.0,-75.6961723422,0.0",
                "60000000.0,-73.1089174359,0.0",
                "70000000.0,-68.9387572937,0.0",
                "80000000.0,-67.6583405168,0.0",
                "90000000.0,-66.9855173146,0.0",
                "100000000.0,-66.782563527,0.0",
                "110000000.0,-66.6548910549,0.0",
                "120000000.0,-65.1527723434,0.0",
                "130000000.0,-65.3911145084,0.0",
                "140000000.0,-63.735569749,0.0",
                "150000000.0,-63.7311648577,0.0",
                "160000000.0,-63.212330925,0.0",
            ),
        )
        + "\n",
        encoding="utf-8",
    )
    freqs, losses = path_cal.parse_calibration_file(path)
    assert freqs[:2] == pytest.approx([10_000_000.0, 20_000_000.0])
    assert losses[:2] == pytest.approx([-81.303819364, -78.5753999207])
    assert len(freqs) == len(losses) == 16
    assert freqs[-1] == pytest.approx(160_000_000.0)
    assert losses[-1] == pytest.approx(-63.212330925)


def test_parse_s2p_single_param_and_full_two_port(tmp_path: Path) -> None:
    single = tmp_path / "s21.s2p"
    single.write_text(
        "! single\n# Hz S RI R 50\n1000000000 0.1 0.0\n2000000000 0.01 0.0\n",
        encoding="utf-8",
    )
    freqs, losses = path_cal.parse_calibration_file(single)
    assert freqs == [1e9, 2e9]
    assert losses[0] == pytest.approx(-20.0)
    assert losses[1] == pytest.approx(-40.0)

    full = tmp_path / "full.s2p"
    full.write_text(
        "# Hz S RI R 50\n"
        "1e9 1 0 0.1 0 0 0 1 0\n",
        encoding="utf-8",
    )
    freqs, losses = path_cal.parse_calibration_file(full)
    assert freqs == pytest.approx([1e9])
    assert losses[0] == pytest.approx(-20.0)


def test_load_calibration_stores_and_nearest_lookup(unit_runtime_context, tmp_path: Path) -> None:
    path = _write_csv(tmp_path / "fixture.csv")
    cal_api.load_calibration(filename=str(path), key="fixture_a")
    assert path_cal.loss_db("fixture_a", 1.1e9) == pytest.approx(-10.0)
    assert path_cal.loss_db("fixture_a", 1.9e9) == pytest.approx(-15.0)
    assert path_cal.programmed_power_dbm(0.0, key="fixture_a", frequency_hz=1e9) == pytest.approx(10.0)
    assert path_cal.correct_power_dbm(-10.0, key="fixture_a", frequency_hz=1e9) == pytest.approx(0.0)


def test_vsg_set_power_and_frequency_retune(unit_runtime_context, tmp_path: Path) -> None:
    path = _write_csv(tmp_path / "cal.csv")
    cal_api.load_calibration(filename=str(path), key="cable")
    transport = RfStubTransport({})
    inst = build_instrument("vsg", 1, {"model": "generic"}, transport)

    with patch("colosseum_equipment.api.vsg.get_cached_instrument", return_value=inst):
        vsg_api.set_frequency(vsg_id=1, frequency=1e9)
        vsg_api.set_power(vsg_id=1, power_dbm=0.0, calibration="cable")
        assert any(cmd.startswith("POW:AMPL 10.000") for cmd in transport.written)

        transport.written.clear()
        vsg_api.set_frequency(vsg_id=1, frequency=2e9, calibration="cable")
        assert any("FREQ:CW 2000000000" in cmd for cmd in transport.written)
        assert any(cmd.startswith("POW:AMPL 15.000") for cmd in transport.written)


def test_play_iq_records_carrier_and_applies_calibration(
    unit_runtime_context, tmp_path: Path,
) -> None:
    path = _write_csv(tmp_path / "cal.csv")
    cal_api.load_calibration(filename=str(path), key="cable")
    transport = RfStubTransport({})
    inst = build_instrument("vsg", 1, {"model": "generic"}, transport)

    with patch("colosseum_equipment.api.vsg.get_cached_instrument", return_value=inst):
        vsg_api.play_iq(
            vsg_id=1,
            filename="WFM1:IQ.bin",
            center_freq_hz=1e9,
            amplitude_dbm=0.0,
            sample_clock_hz=100e6,
            calibration="cable",
        )
        assert any(cmd.startswith("POW:AMPL 10.000") for cmd in transport.written)

        transport.written.clear()
        vsg_api.set_frequency(vsg_id=1, frequency=2e9, calibration="cable")
        assert any(cmd.startswith("POW:AMPL 15.000") for cmd in transport.written)

        transport.written.clear()
        vsg_api.play_iq(
            vsg_id=1,
            filename="WFM1:IQ.bin",
            center_freq_hz=1e9,
            amplitude_dbm=-5.0,
            sample_clock_hz=100e6,
        )
        assert any(cmd.startswith("POW:AMPL -5.000") for cmd in transport.written)
        transport.written.clear()
        vsg_api.set_power(vsg_id=1, power_dbm=0.0, calibration="cable")
        assert any(cmd.startswith("POW:AMPL 10.000") for cmd in transport.written)


def test_vsg_set_frequency_calibration_requires_prior_desired(
    unit_runtime_context, tmp_path: Path,
) -> None:
    path = _write_csv(tmp_path / "cal.csv")
    cal_api.load_calibration(filename=str(path), key="cable")
    transport = RfStubTransport({})
    inst = build_instrument("vsg", 1, {"model": "generic"}, transport)

    with (
        patch("colosseum_equipment.api.vsg.get_cached_instrument", return_value=inst),
        pytest.raises(path_cal.CalibrationError, match="set_power"),
    ):
        vsg_api.set_frequency(vsg_id=1, frequency=2e9, calibration="cable")


def test_asg_set_power_uses_channel_frequency(unit_runtime_context, tmp_path: Path) -> None:
    path = _write_csv(tmp_path / "cal.csv")
    cal_api.load_calibration(filename=str(path), key="cable")

    class _Asg:
        def __init__(self) -> None:
            self.powers: list[tuple[float, int]] = []

        def set_frequency(self, frequency: float, *, channel: int = 1) -> None:
            self.frequency = (frequency, channel)

        def set_power(self, power_dbm: float, *, channel: int = 1) -> None:
            self.powers.append((power_dbm, channel))

    inst = _Asg()
    with patch("colosseum_equipment.api.asg.get_cached_instrument", return_value=inst):
        asg_api.set_frequency(asg_id=1, frequency=1e9, channel=1)
        asg_api.set_power(asg_id=1, power_dbm=-5.0, channel=1, calibration="cable")
    assert inst.powers == [(5.0, 1)]


def test_pwrmeter_measure_applies_loss(unit_runtime_context, tmp_path: Path) -> None:
    path = _write_csv(tmp_path / "cal.csv")
    cal_api.load_calibration(filename=str(path), key="cable")

    class _Meter:
        def set_frequency(self, frequency_hz: float, *, channel: int = 1) -> None:
            self.freq = frequency_hz

        def measure_power_dbm(self, *, channel: int = 1) -> float:
            return -10.0

    inst = _Meter()
    with patch("colosseum_equipment.api.pwrmeter.get_cached_instrument", return_value=inst):
        pwrmeter_api.set_frequency(pwrmeter_id=1, frequency_hz=1e9, calibration="cable")
        value = pwrmeter_api.measure_power_dbm(pwrmeter_id=1, key="p", calibration="cable")
    assert value == pytest.approx(0.0)


def test_speca_save_trace_applies_per_bin_loss(unit_runtime_context, tmp_path: Path) -> None:
    path = _write_csv(tmp_path / "cal.csv")
    cal_api.load_calibration(filename=str(path), key="cable")
    transport = RfStubTransport(
        {
            "*OPC?": "1",
            "FREQ:CENT?": "1500000000",
            "FREQ:SPAN?": "1000000000",
            "TRAC:DATA? TRACE1": "-10.0,-12.5,-15.0",
        },
    )
    inst = build_instrument("speca", 1, {"model": "generic"}, transport)

    with patch("colosseum_equipment.api.speca.get_cached_instrument", return_value=inst):
        speca_api.save_trace_data(
            speca_id=1,
            path="traces/calibrated.csv",
            calibration="cable",
        )
    matches = list(Path(unit_runtime_context.output_dir).rglob("calibrated.csv"))
    assert matches
    rows = list(csv.DictReader(matches[0].open(encoding="utf-8")))
    assert len(rows) == 3
    assert float(rows[0]["amplitude_dbm"]) == pytest.approx(0.0)
    assert float(rows[-1]["amplitude_dbm"]) == pytest.approx(0.0)


def test_unknown_key_raises(unit_runtime_context) -> None:
    with pytest.raises(path_cal.CalibrationError, match="unknown calibration key"):
        path_cal.loss_db("missing", 1e9)
