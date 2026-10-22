"""BK 9115 and Keithley 2260B command dialects."""

from __future__ import annotations

import pytest
from colosseum_equipment.exceptions import EquipmentCapabilityError, EquipmentResponseError
from colosseum_equipment.instruments.factory import build_instrument

from tests.support.stubs import RfStubTransport


def _supply(model: str, responses: dict[str, str] | None = None, **config: object):
    transport = RfStubTransport(responses)
    instrument = build_instrument("psu", 1, {"model": model, **config}, transport)
    return instrument, transport


def test_bk_9115_uses_documented_source_ovp_and_power_commands() -> None:
    supply, transport = _supply("bk-9115", {
        "VOLT?": "12.5",
        "CURR?": "1.25",
        "OUTP?": "1",
        "MEAS:VOLT?": "12.4",
        "MEAS:CURR?": "0.5",
        "MEAS:POW?": "6.2",
        "VOLT:PROT?": "15",
        "VOLT:PROT:STAT?": "0",
    })
    supply.set_voltage(12.5)
    supply.set_current_limit(1.25)
    supply.set_output(True)
    supply.set_output(False)
    supply.set_ovp_v(15)
    supply.toggle_ovp(True)
    supply.clear_protection()
    assert supply.get_voltage() == pytest.approx(12.5)
    assert supply.get_current_limit() == pytest.approx(1.25)
    assert supply.get_output() is True
    assert supply.measure_power_w() == pytest.approx(6.2)
    assert supply.get_ovp_v() == pytest.approx(15)
    assert supply.get_ovp_enabled() is False
    assert transport.written == [
        "VOLT 12.500000",
        "CURR 1.250000",
        "OUTP ON",
        "OUTP OFF",
        "VOLT:PROT 15.000000",
        "VOLT:PROT:STAT ON",
        "PROT:CLE",
    ]


def test_bk_9115_rejects_ocp_textual_output_and_extra_channels() -> None:
    supply, _transport = _supply("bk-9115", {"OUTP?": "ON"})
    with pytest.raises(EquipmentResponseError, match="output state"):
        supply.get_output()
    with pytest.raises(EquipmentCapabilityError, match="set_ocp_a"):
        supply.set_ocp_a(1.0)
    with pytest.raises(EquipmentCapabilityError, match="one output"):
        build_instrument("psu", 1, {"model": "bk-9115", "channels": 2}, RfStubTransport())


def test_keithley_2260b_accepts_textual_state_and_current_protection() -> None:
    supply, transport = _supply("keithley-2260b", {
        "OUTP?": "ON",
        "MEAS:POW?": "6.2",
        "VOLT:PROT?": "40",
        "CURR:PROT?": "2.5",
        "CURR:PROT:STAT?": "OFF",
    })
    supply.set_voltage(28)
    supply.set_current_limit(1.5)
    supply.set_output(False)
    supply.set_ovp_v(40)
    supply.set_ocp_a(2.5)
    supply.toggle_ocp(True)
    supply.clear_protection()
    assert supply.get_output() is True
    assert supply.measure_power_w() == pytest.approx(6.2)
    assert supply.get_ovp_v() == pytest.approx(40)
    assert supply.get_ocp_a() == pytest.approx(2.5)
    assert supply.get_ocp_enabled() is False
    assert transport.written == [
        "VOLT 28.000000",
        "CURR 1.500000",
        "OUTP OFF",
        "VOLT:PROT 40.000000",
        "CURR:PROT 2.500000",
        "CURR:PROT:STAT ON",
        "OUTP:PROT:CLE",
    ]
    off, _transport = _supply("keithley-2260b", {"OUTP?": "0"})
    assert off.get_output() is False


def test_keithley_2260b_rejects_ovp_enable_and_extra_channels() -> None:
    supply, _transport = _supply("keithley-2260b")
    with pytest.raises(EquipmentCapabilityError, match="toggle_ovp"):
        supply.toggle_ovp(True)
    with pytest.raises(EquipmentCapabilityError, match="get_regulation_mode"):
        supply.get_regulation_mode()
    with pytest.raises(EquipmentCapabilityError, match="one output"):
        build_instrument("psu", 1, {"model": "keithley-2260b", "channels": 2}, RfStubTransport())
