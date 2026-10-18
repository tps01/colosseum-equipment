"""Unit tests for equipment mask schema, verify, apply, and editor smoke."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from colosseum.database import MeasurementRow
from colosseum_equipment.tools.mask_apply import (
    apply_oscope_mask_setup,
    apply_speca_mask_setup,
)
from colosseum_equipment.tools.mask_schema import (
    MaskSchemaError,
    list_mask_templates,
    load_mask,
    load_mask_template,
    save_mask,
    validate_mask,
)
from colosseum_equipment.tools.mask_verify import evaluate_mask, evaluate_mask_file, read_trace_xy


def _freq_mask(**overrides):
    base = {
        "version": 1,
        "domain": "frequency",
        "x_unit": "Hz",
        "y_unit": "dBm",
        "setup": {"center_hz": 1e9, "span_hz": 100e6, "ref_level_dbm": 0.0},
        "regions": [
            {
                "id": "band",
                "kind": "keep_below",
                "x0": 1e9,
                "x1": 1.1e9,
                "y0": -100,
                "y1": -40,
            },
        ],
    }
    base.update(overrides)
    return base


def test_validate_mask_normalizes_and_swaps_axes() -> None:
    mask = validate_mask(
        {
            "version": 1,
            "domain": "frequency",
            "regions": [
                {"kind": "keep_above", "x0": 2, "x1": 1, "y0": 10, "y1": 0, "id": "a"},
            ],
        },
    )
    region = mask["regions"][0]
    assert region["x0"] == 1
    assert region["x1"] == 2
    assert region["y0"] == 0
    assert region["y1"] == 10
    assert mask["x_unit"] == "Hz"
    assert mask["y_unit"] == "dBm"


def test_validate_mask_rejects_bad_kind() -> None:
    with pytest.raises(MaskSchemaError, match="kind"):
        validate_mask(
            {
                "version": 1,
                "domain": "time",
                "regions": [{"kind": "diamond", "x0": 0, "x1": 1, "y0": 0, "y1": 1}],
            },
        )


def test_save_load_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "masks" / "spur.json"
    saved = save_mask(path, _freq_mask())
    loaded = load_mask(saved)
    assert loaded["domain"] == "frequency"
    assert loaded["regions"][0]["id"] == "band"


def test_list_and_load_templates() -> None:
    ids = list_mask_templates()
    assert "freq_spur_floor" in ids
    assert "freq_harmonic_comb" in ids
    assert "time_pulse_envelope" in ids
    assert "freq_channel_mask" in ids
    spur = load_mask_template("freq_spur_floor")
    assert spur["domain"] == "frequency"
    assert len(spur["regions"]) >= 1
    pulse = load_mask_template("time_pulse_envelope")
    assert pulse["domain"] == "time"


def test_evaluate_keep_below_pass_fail() -> None:
    mask = validate_mask(_freq_mask())
    xs = [1.05e9, 1.05e9]
    ok = evaluate_mask(xs, [-50.0, -45.0], mask)
    assert ok.ok
    bad = evaluate_mask(xs, [-30.0, -50.0], mask)
    assert not bad.ok
    assert "band" in bad.message
    assert "keep_below" in bad.message


def test_evaluate_mask_requires_region_coverage() -> None:
    mask = validate_mask(_freq_mask())
    # Samples entirely outside the keep_below band must FAIL (not silent PASS).
    result = evaluate_mask([9e8, 9.1e8], [-50.0, -50.0], mask)
    assert not result.ok
    assert "no overlapping samples" in result.message


def test_evaluate_mask_rejects_domain_mismatch(tmp_path: Path) -> None:
    csv_path = tmp_path / "wave.csv"
    csv_path.write_text("time_s,voltage_v\n0.0,1.0\n", encoding="utf-8")
    with pytest.raises(ValueError, match="does not match"):
        evaluate_mask_file(csv_path, validate_mask(_freq_mask()))


def test_evaluate_keep_inside_and_outside() -> None:
    inside = validate_mask(
        {
            "version": 1,
            "domain": "time",
            "regions": [
                {
                    "id": "corridor",
                    "kind": "keep_inside",
                    "x0": 0,
                    "x1": 1,
                    "y0": -1,
                    "y1": 1,
                },
            ],
        },
    )
    assert evaluate_mask([0.5], [0.0], inside).ok
    assert not evaluate_mask([0.5], [2.0], inside).ok

    outside = validate_mask(
        {
            "version": 1,
            "domain": "time",
            "regions": [
                {
                    "id": "notch",
                    "kind": "keep_outside",
                    "x0": 0,
                    "x1": 1,
                    "y0": -0.5,
                    "y1": 0.5,
                },
            ],
        },
    )
    assert evaluate_mask([0.5], [1.0], outside).ok
    assert not evaluate_mask([0.5], [0.0], outside).ok


def test_evaluate_mask_file_csv(tmp_path: Path) -> None:
    csv_path = tmp_path / "trace.csv"
    csv_path.write_text(
        "frequency_hz,amplitude_dbm\n"
        "1000000000,-50\n"
        "1050000000,-35\n",
        encoding="utf-8",
    )
    mask = validate_mask(_freq_mask())
    result = evaluate_mask_file(csv_path, mask)
    assert not result.ok
    xs, ys, domain = read_trace_xy(csv_path)
    assert domain == "frequency"
    assert len(xs) == 2
    assert ys[1] == -35


def test_apply_mask_setup_speca(tmp_path: Path) -> None:
    path = tmp_path / "m.json"
    save_mask(
        path,
        _freq_mask(
            setup={
                "center_hz": 2.4e9,
                "span_hz": 50e6,
                "ref_level_dbm": -10.0,
                "rbw_hz": 1e5,
                "mystery": 1.0,
            },
        ),
    )
    inst = MagicMock()
    with patch(
        "colosseum_equipment.tools.mask_apply.get_cached_instrument",
        return_value=inst,
    ):
        setup = apply_speca_mask_setup(str(path), speca_id=1)
    inst.set_center_frequency.assert_called_once_with(2.4e9)
    inst.set_span.assert_called_once_with(50e6)
    inst.set_reference_level.assert_called_once_with(-10.0)
    inst.set_rbw.assert_called_once_with(1e5)
    assert setup["center_hz"] == 2.4e9


def test_apply_mask_setup_oscope(tmp_path: Path) -> None:
    path = tmp_path / "t.json"
    save_mask(
        path,
        {
            "version": 1,
            "domain": "time",
            "setup": {"timebase_s": 1e-6, "scale_v": 0.5, "offset_v": 0.1},
            "regions": [],
        },
    )
    inst = MagicMock()
    with patch(
        "colosseum_equipment.tools.mask_apply.get_cached_instrument",
        return_value=inst,
    ):
        apply_oscope_mask_setup(str(path), oscope_id=2)
    inst.set_timebase_scale.assert_called_once_with(1e-6)
    inst.set_channel_scale_v.assert_called_once_with(1, 0.5)
    inst.set_channel_offset_v.assert_called_once_with(1, 0.1)


@pytest.mark.parametrize("kind", ["speca", "oscope"])
def test_mask_setup_uses_verification_path_precedence(
    kind, unit_runtime_context, tmp_path: Path, monkeypatch,
) -> None:
    from colosseum.runner.runtime import ensure_output_dir
    from colosseum_equipment.tools.mask_verify import resolve_mask_path

    working = tmp_path / "working"
    working.mkdir()
    monkeypatch.chdir(working)
    output = ensure_output_dir(unit_runtime_context)
    params = tmp_path / "limits"
    params.mkdir()
    unit_runtime_context.parameters_path = str(params / "parameters.toml")
    beside = params / "mask.json"
    field = "center_hz" if kind == "speca" else "scale_v"
    mask = {
        "version": 1,
        "domain": "frequency" if kind == "speca" else "time",
        "setup": {field: 1.0},
        "regions": [],
    }
    save_mask(beside, mask)
    inst = MagicMock()
    apply = apply_speca_mask_setup if kind == "speca" else apply_oscope_mask_setup
    with patch("colosseum_equipment.tools.mask_apply.get_cached_instrument", return_value=inst):
        assert resolve_mask_path("mask.json") == beside
        assert apply("mask.json", **{f"{kind}_id": 1})[field] == 1.0
        # A same-named file in CWD takes precedence for both operations.
        mask["setup"] = {field: 2.0}
        save_mask(working / "mask.json", mask)
        assert apply("mask.json", **{f"{kind}_id": 1})[field] == 2.0
        (working / "mask.json").unlink()
        beside.unlink()
        mask["setup"] = {field: 3.0}
        save_mask(output / "mask.json", mask)
        assert apply("mask.json", **{f"{kind}_id": 1})[field] == 3.0
    if kind == "speca":
        inst.set_center_frequency.assert_called_with(3.0)
    else:
        inst.set_channel_scale_v.assert_called_with(1, 3.0)


def test_speca_verify_mask_api_pass_fail(unit_runtime_context, tmp_path: Path) -> None:
    from colosseum_equipment.api import speca as speca_api

    csv_path = tmp_path / "wifi.csv"
    csv_path.write_text(
        "frequency_hz,amplitude_dbm\n"
        "1000000000,-50\n"
        "1050000000,-55\n",
        encoding="utf-8",
    )
    mask_path = tmp_path / "mask.json"
    save_mask(mask_path, _freq_mask())
    unit_runtime_context.db.insert_measurement(
        MeasurementRow(
            domain="equipment",
            command="save_trace_data",
            key="wifi_spur_trace",
            artifact_path=str(csv_path),
            value={"path": str(csv_path)},
        ),
    )
    unit_runtime_context.db.drain()

    ok = speca_api.verify_mask(key="wifi_spur_trace", mask=str(mask_path))
    assert ok.status == "PASS"

    bad_csv = tmp_path / "bad.csv"
    bad_csv.write_text(
        "frequency_hz,amplitude_dbm\n1050000000,-10\n",
        encoding="utf-8",
    )
    unit_runtime_context.db.insert_measurement(
        MeasurementRow(
            domain="equipment",
            command="save_trace_data",
            key="wifi_spur_bad",
            artifact_path=str(bad_csv),
            value={"path": str(bad_csv)},
        ),
    )
    unit_runtime_context.db.drain()
    fail = speca_api.verify_mask(key="wifi_spur_bad", mask=str(mask_path))
    assert fail.status == "FAIL"
    assert "band" in (fail.message or "")


def test_oscope_verify_mask_api(unit_runtime_context, tmp_path: Path) -> None:
    from colosseum_equipment.api import oscope as oscope_api

    csv_path = tmp_path / "wave.csv"
    csv_path.write_text(
        "time_s,voltage_v\n"
        "0.0,0.05\n"
        "5e-6,1.0\n",
        encoding="utf-8",
    )
    mask_path = tmp_path / "pulse.json"
    save_mask(
        mask_path,
        {
            "version": 1,
            "domain": "time",
            "setup": {},
            "regions": [
                {
                    "id": "pulse_body",
                    "kind": "keep_inside",
                    "x0": 2e-6,
                    "x1": 8e-6,
                    "y0": 0.8,
                    "y1": 1.2,
                },
            ],
        },
    )
    unit_runtime_context.db.insert_measurement(
        MeasurementRow(
            domain="equipment",
            command="save_waveform",
            key="pulse_wave",
            artifact_path=str(csv_path),
            value={"path": str(csv_path)},
        ),
    )
    unit_runtime_context.db.drain()
    ok = oscope_api.verify_mask(key="pulse_wave", mask=str(mask_path))
    assert ok.status == "PASS"


def test_speca_apply_mask_setup_command(unit_runtime_context, tmp_path: Path) -> None:
    from colosseum_equipment.api import speca as speca_api

    _ = unit_runtime_context
    path = tmp_path / "m.json"
    save_mask(path, _freq_mask(setup={"center_hz": 1.5e9, "span_hz": 10e6}))
    with patch(
        "colosseum_equipment.api.speca.apply_speca_mask_setup",
    ) as apply_fn:
        speca_api.apply_mask_setup(speca_id=1, mask=str(path), key="setup_step")
    apply_fn.assert_called_once_with(str(path), speca_id=1)


def test_api_load_save_list(tmp_path: Path) -> None:
    from colosseum_equipment.api import tools as tools_api

    path = tmp_path / "out.json"
    tools_api.save_mask(path=str(path), mask=_freq_mask())
    loaded = tools_api.load_mask(path=str(path))
    assert loaded["regions"][0]["kind"] == "keep_below"
    assert "freq_spur_floor" in tools_api.list_mask_templates()
    assert not hasattr(tools_api, "verify_mask")
    assert not hasattr(tools_api, "apply_mask_setup")


@pytest.mark.gui
def test_mask_editor_constructs_and_destroys() -> None:
    try:
        import tkinter as tk
    except ImportError as exc:  # pragma: no cover
        pytest.skip(f"tkinter unavailable: {exc}")
    try:
        probe = tk.Tk()
        probe.destroy()
    except tk.TclError as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"no Tk display: {exc}")

    from colosseum_equipment.tools.mask_editor import MaskEditorApp

    app = MaskEditorApp(domain="frequency", template="freq_spur_floor")
    try:
        app._root.update_idletasks()
        assert len(app._mask["regions"]) >= 1
    finally:
        app._root.destroy()


def test_template_json_files_are_valid() -> None:
    root = Path(__file__).resolve().parents[2] / "colosseum_equipment" / "tools" / "mask_templates"
    for path in sorted(root.glob("*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        validate_mask(raw)
