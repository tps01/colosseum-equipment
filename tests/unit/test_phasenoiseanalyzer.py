"""Phase noise analyzer drivers."""

from __future__ import annotations

from colosseum_equipment.instruments.factory import build_instrument
from colosseum_equipment.instruments.phasenoiseanalyzer.rohde_fswp import (
    RohdeFswpPhaseNoiseAnalyzer,
)
from colosseum_equipment.instruments.registry import registered_models

from tests.support.stubs import RfStubTransport


def test_phasenoiseanalyzer_models_registered() -> None:
    models = registered_models("phasenoiseanalyzer")
    assert {"generic", "rohde-fswp"}.issubset(models)


def test_rohde_fswp_spot_noise_scpi() -> None:
    transport = RfStubTransport(
        {
            "*OPC?": "1",
            "CALC:SNO:Y?": "-120.5",
            "FREQ:CENT?": "1000000000.0",
        },
    )
    inst = build_instrument("phasenoiseanalyzer", 1, {"model": "rohde-fswp"}, transport)
    assert isinstance(inst, RohdeFswpPhaseNoiseAnalyzer)
    inst.set_carrier_frequency_hz(1e9)
    inst.set_offset_start_hz(1e3)
    inst.set_offset_stop_hz(10e6)
    value = inst.measure_spot_noise_dbc_hz(1e6)
    assert value == -120.5
    assert any(cmd.startswith("FREQ:CENT ") for cmd in transport.written)
    assert any(cmd.startswith("CALC:SNO:X ") for cmd in transport.written)
    assert "INIT:IMM" in transport.written
