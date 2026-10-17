"""Rohde & Schwarz SMBV100B / FSW driver smoke tests."""

from __future__ import annotations

from colosseum_equipment.instruments.factory import build_instrument
from colosseum_equipment.instruments.registry import registered_models

from tests.support.stubs import RfStubTransport


def test_rohde_smbv_and_fsw_registered() -> None:
    assert "rohde-smbv100b" in registered_models("vsg")
    assert "rohde-fsw" in registered_models("speca")


def test_rohde_smbv_play_iq_scpi() -> None:
    transport = RfStubTransport({"*OPC?": "1"})
    inst = build_instrument("vsg", 1, {"model": "rohde-smbv100b"}, transport)
    inst.play_iq("IQ.bin", 2.4e9, -10.0, 10e6)
    assert any("SOUR:BB:ARB:WAV:SEL" in cmd for cmd in transport.written)
    assert any(cmd.startswith("SOUR:BB:ARB:CLOCK ") for cmd in transport.written)
    assert "SOUR:BB:ARB:STAT ON" in transport.written


def test_rohde_fsw_rbw_ref_level() -> None:
    transport = RfStubTransport()
    inst = build_instrument("speca", 1, {"model": "rohde-fsw"}, transport)
    inst.set_rbw(10e3)
    inst.set_reference_level(-20.0)
    assert "BAND 10000.000000" in transport.written
    assert "DISP:TRAC:Y:RLEV -20.000" in transport.written
