"""Integration tests for RF equipment via PyVISA-sim."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest
from colosseum.config import load_config
from colosseum.context import get_context

pytestmark = pytest.mark.visa_sim

REPO = Path(__file__).resolve().parents[2]
BENCH_RF = REPO / "examples" / "configs" / "config.rf.visa-sim.toml"


@pytest.fixture
def bench_rf() -> Path:
    assert BENCH_RF.is_file()
    return BENCH_RF


def test_load_config_rf_bench(bench_rf, isolated_cwd) -> None:
    store = load_config(bench_rf)
    vsg = store.list_items("equipment.vsg")
    speca = store.list_items("equipment.speca")
    rtsa = store.list_items("equipment.rtsa")
    assert vsg and vsg[0].get("model") == "keysight-esg"
    assert "driver" not in vsg[0]
    assert len(speca) == 1
    assert rtsa and rtsa[0].get("model") == "tektronix-rsa5100b"


def test_malformed_frequency_write_does_not_shift_later_queries(bench_rf, isolated_cwd) -> None:
    """A rejected numeric write must not leave ERROR sitting in front of the next query."""
    from colosseum_equipment.api import scpi

    load_config(bench_rf)
    assert float(scpi.query(vsg_id=1, command="FREQ:CW?")) == pytest.approx(1_000_000_000)
    assert float(scpi.query(vsg_id=1, command="POW:AMPL?")) == pytest.approx(-10)
    scpi.write(vsg_id=1, command="FREQ:CW wrong-type")
    assert scpi.query_float(vsg_id=1, command="FREQ:CW?") == pytest.approx(1_000_000_000)
    assert scpi.query_float(vsg_id=1, command="POW:AMPL?") == pytest.approx(-10)


def test_vsg_set_frequency_and_output(bench_rf, isolated_cwd) -> None:
    from colosseum_equipment.api import vsg

    load_config(bench_rf)
    vsg.set_frequency(vsg_id=1, frequency=2.4e9)
    vsg.set_power(vsg_id=1, power_dbm=-5.0)
    vsg.set_output(vsg_id=1, enabled=True)
    assert vsg.measure_frequency(vsg_id=1, key="cw_hz") == pytest.approx(2.4e9)
    assert vsg.measure_power_dbm(vsg_id=1, key="cw_dbm") == pytest.approx(-5.0)
    assert vsg.measure_output_state(vsg_id=1, key="rf_on") == pytest.approx(1.0)
    vsg.set_output(vsg_id=1, enabled=False)
    assert vsg.measure_output_state(vsg_id=1, key="rf_off") == pytest.approx(0.0)


def test_vector_esg_wlan_modulation_is_unsupported(bench_rf, isolated_cwd) -> None:
    from colosseum_equipment.api import vsg
    from colosseum_equipment.exceptions import EquipmentCapabilityError

    load_config(bench_rf)
    with pytest.raises(EquipmentCapabilityError, match="WLAN"):
        vsg.set_modulation(vsg_id=1, enabled=True, modulation_type="WLAN")


def test_speca_peak_and_marker_power(bench_rf, isolated_cwd) -> None:
    from colosseum_equipment.api import speca

    load_config(bench_rf)
    speca.set_center_frequency(speca_id=1, frequency=1e9)
    speca.peak_search(speca_id=1, marker=1)
    power = speca.measure_marker_power(speca_id=1, marker=1, key="carrier")
    assert power == pytest.approx(-42.5, rel=1e-3)


def test_speca_shutdown_hook_succeeds_after_use(bench_rf, isolated_cwd, caplog) -> None:
    from colosseum_equipment.connections import get_cached_instrument

    with caplog.at_level(logging.ERROR, logger="colosseum.plugins"):
        load_config(bench_rf)
        get_cached_instrument("speca", 1)
        get_context().plugin_registry.run_shutdown()

    assert "Plugin shutdown hook failed" not in caplog.text
    assert get_context().resource_cache == {}


def test_speca_marker_at_frequency_and_verify(bench_rf, isolated_cwd) -> None:
    from colosseum_equipment.api import speca

    load_config(bench_rf)
    speca.set_marker_frequency(speca_id=1, marker=1, frequency_hz=1e9)
    speca.measure_marker_power(speca_id=1, marker=1, key="marker_1ghz")
    result = speca.verify_marker_power(key="marker_1ghz", expected_val=-42.5, tolerance=0.5)
    assert result.status == "PASS"


def test_speca_trace_power_at_frequency_and_verify(bench_rf, isolated_cwd) -> None:
    from colosseum_equipment.api import speca

    load_config(bench_rf)
    speca.save_trace_data(speca_id=1, path="traces/verify.csv")
    speca.measure_trace_power_at_frequency(speca_id=1, frequency_hz=1e9, key="trace_1ghz")
    result = speca.verify_trace_power_at_frequency(key="trace_1ghz", expected_val=-41.0, tolerance=0.5)
    assert result.status == "PASS"


def test_speca_save_trace_data(bench_rf, isolated_cwd) -> None:
    from colosseum_equipment.api import speca

    load_config(bench_rf)
    speca.save_trace_data(speca_id=1, path="traces/carrier.csv")
    trace_files = list(Path.cwd().glob("outputs/*/traces/carrier.csv"))
    assert trace_files
    content = trace_files[0].read_text(encoding="utf-8")
    assert "frequency_hz" in content
    assert "-42.5" in content


def test_rtsa_center_span(bench_rf, isolated_cwd) -> None:
    from colosseum_equipment.api import rtsa, scpi

    load_config(bench_rf)
    rtsa.set_center_freq(rtsa_id=1, frequency_hz=2.5e9)
    rtsa.set_span(rtsa_id=1, span_hz=20e6)
    assert float(scpi.query(command="DISP:SPEC:FREQ:OFFS?", rtsa_id=1)) == pytest.approx(2.5e9)
    assert float(scpi.query(command="DISP:SPEC:FREQ:SCAL?", rtsa_id=1)) == pytest.approx(20e6)


def test_documented_vector_workflow_exports_real_fixture_values(bench_rf, isolated_cwd) -> None:
    """Catch queued simulator errors even when a command reports PASS."""
    import json
    import runpy
    import tarfile

    from colosseum_equipment.api import rtsa, scpi

    load_config(bench_rf)
    example = runpy.run_path(str(REPO / "examples" / "test_rf_vector_mod.py"))
    example["main"]()
    output = get_context().output_dir
    assert output is not None
    assert (output / "captures/iq.bin").read_bytes() == b"1234567890123456"
    lines = (output / "traces/modulated.csv").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 6
    assert float(lines[1].split(",")[0]) == pytest.approx(995e6)
    assert float(lines[1].split(",")[1]) == pytest.approx(-42.5)
    rtsa.save_IQ_data(rtsa_id=1, path="captures/iq.iq.tar", file_format="iq.tar")
    with tarfile.open(output / "captures/iq.iq.tar") as archive:
        metadata = json.load(archive.extractfile("metadata.json"))
    assert metadata["center_freq_hz"] == pytest.approx(1e9)
    assert metadata["span_hz"] == pytest.approx(10e6)
    assert metadata["num_samples"] == 1
    # Each session must still be aligned after upload, capture and metadata queries.
    for kind in ("vsg", "speca", "rtsa"):
        assert scpi.query(command="*OPC?", **{f"{kind}_id": 1}) == "1"


def test_documented_parameter_mask_workflow(bench_rf, isolated_cwd) -> None:
    import runpy

    from colosseum.config.parameters import attach_parameters

    load_config(bench_rf)
    attach_parameters(get_context(), REPO / "examples/masks/parameters.toml", required=True)
    example = runpy.run_path(str(REPO / "examples/test_mask_sim.py"))
    example["main"]()
    output = get_context().output_dir
    assert output is not None and (output / "speca/wifi_trace.csv").is_file()
    rows = get_context().db.fetch_all_verifications()
    assert [(row.key, row.status) for row in rows if row.command == "speca.verify_mask"] == [
        ("speca_trace_1", "PASS"),
    ]
