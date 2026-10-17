"""Instrument model registry."""

from __future__ import annotations

import pytest
from colosseum_equipment.instruments.registry import (
    build_registered,
    instrument_model,
    kind_id_params,
    kind_specs,
    registered_kinds,
    registered_models,
)

from tests.support.stubs import StubTransport


def test_registered_kinds_include_core_bench_types() -> None:
    kinds = registered_kinds()
    assert {
        "dmm",
        "psu",
        "vsg",
        "asg",
        "speca",
        "rtsa",
        "vna",
        "gnss",
        "relay",
        "phasenoiseanalyzer",
    }.issubset(kinds)
    assert "serial" in {spec.kind for spec in kind_specs()}


def test_build_registered_generic_dmm() -> None:
    from colosseum_equipment.instruments.dmm.generic import GenericDMM

    instrument = build_registered("dmm", "generic", StubTransport(), {})
    assert isinstance(instrument, GenericDMM)


def test_build_registered_unknown_model_raises() -> None:
    with pytest.raises(RuntimeError, match="Unsupported equipment model"):
        build_registered("dmm", "not-a-real-model", StubTransport(), {})


def test_kind_specs_are_the_config_and_scpi_map() -> None:
    specs = {spec.kind: spec for spec in kind_specs()}
    rtsa = specs["rtsa"].section()
    assert rtsa.dotted_path == "equipment.rtsa"
    assert rtsa.id_field == "rtsa_id"
    assert rtsa.required_keys == ("resource",)
    assert "center_freq" in rtsa.optional_keys
    serial = specs["serial"].section()
    assert serial.required_keys == ("port",)
    gnss = specs["gnss"].section()
    assert gnss.required_keys == ()
    assert "port" in gnss.optional_keys
    assert "connection" in gnss.optional_keys
    relay = specs["relay"].section()
    assert relay.required_keys == ("resource",)
    assert "username" in relay.optional_keys
    attn = specs["attn"].section()
    assert attn.required_keys == ()
    assert "port" in attn.optional_keys
    params = kind_id_params()
    assert params["rtsa_id"] == "rtsa"
    assert params["serial_id"] == "serial"
    assert params["gnss_id"] == "gnss"
    assert params["phasenoiseanalyzer_id"] == "phasenoiseanalyzer"
    pna = specs["phasenoiseanalyzer"].section()
    assert pna.required_keys == ("resource",)
    assert params["relay_id"] == "relay"
    assert set(params) == {spec.id_field for spec in specs.values()}


def test_documented_model_slugs_still_build() -> None:
    assert "tektronix-rsa5100b" in registered_models("rtsa")
    assert "keysight-53230a" in registered_models("freqcounter")
    assert "chroma-8601" in registered_models("eload")
    assert "minicircuits-ztrc" in registered_models("rfswitch")
    assert "keysight-esg" in registered_models("vsg")


def test_decorator_registers_a_model_without_a_second_list() -> None:
    from colosseum_equipment.instruments.psu.generic import GenericPSU

    @instrument_model("psu", "unit-test-psu", "unit-test-psu-alias")
    class _UnitTestPsu(GenericPSU):
        """Manual: https://example.invalid/psu"""

    built = build_registered("psu", "unit-test-psu-alias", StubTransport(), {})
    assert isinstance(built, _UnitTestPsu)
