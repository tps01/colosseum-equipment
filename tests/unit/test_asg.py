"""Analog signal generator factory routing and SCPI delegation."""

from __future__ import annotations

import pytest
from colosseum_equipment.exceptions import EquipmentCapabilityError
from colosseum_equipment.instruments.asg.generic import GenericASG
from colosseum_equipment.instruments.factory import build_instrument

from tests.support.stubs import RfStubTransport


def test_generic_asg_setters_write_scpi() -> None:
    transport = RfStubTransport()
    inst = build_instrument("asg", 1, {"model": "generic"}, transport)
    assert isinstance(inst, GenericASG)

    inst.set_frequency(2.4e9)
    inst.set_amplitude_vpp(1.0)
    inst.set_output(True)
    inst.set_pulse_period(0.001)
    inst.set_pulse_width(0.0001)

    assert transport.written == [
        "FREQ 2400000000.000000",
        "SOUR1:VOLT:UNIT VPP",
        "SOUR1:VOLT 1.000000",
        "OUTP ON",
        "SOUR1:FUNC:PULS:PER 0.001000000",
        "SOUR1:FUNC:PULS:WIDT 0.000100000",
    ]


def test_generic_asg_refuses_rf_pulse_and_dbm() -> None:
    transport = RfStubTransport()
    inst = build_instrument("asg", 1, {"model": "generic"}, transport)
    with pytest.raises(EquipmentCapabilityError, match="set_power"):
        inst.set_power(-10.0)
    with pytest.raises(EquipmentCapabilityError, match="set_pulsegen_output"):
        inst.set_pulsegen_output(True)
    with pytest.raises(EquipmentCapabilityError, match="set_pulsemod_output"):
        inst.set_pulsemod_output(False)


def test_generic_asg_config_bootstrap() -> None:
    transport = RfStubTransport()
    build_instrument(
        "asg",
        1,
        {"model": "generic", "frequency": 1e9, "amplitude_vpp": 2.0, "output": True},
        transport,
    )
    assert transport.written == [
        "FREQ 1000000000.000000",
        "SOUR1:VOLT:UNIT VPP",
        "SOUR1:VOLT 2.000000",
        "OUTP ON",
    ]
