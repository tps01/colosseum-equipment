"""Genesys LAN/IEEE commands differ from generic PSU SCPI."""

from __future__ import annotations

import pytest
from colosseum_equipment.exceptions import EquipmentCapabilityError, EquipmentResponseError
from colosseum_equipment.instruments.factory import build_instrument

from tests.support.stubs import RfStubTransport


def _genesys(responses: dict[str, str] | None = None, **config: object):
    transport = RfStubTransport(responses)
    instrument = build_instrument(
        "psu",
        1,
        {"model": "tdk-genesys", **config},
        transport,
    )
    return instrument, transport


def test_genesys_uses_output_state_and_colon_source_commands() -> None:
    supply, transport = _genesys({
        ":VOLT?": "12.500000",
        ":CURR?": "1.250000",
        "OUTP:STAT?": "ON",
        "MEAS:VOLT?": "12.400000",
        "MEAS:CURR?": "0.500000",
        "SOUR:MOD?": "CV",
        ":VOLT:PROT:LEV?": "15.000000",
        ":CURR:PROT:STAT?": "OFF",
    })
    supply.set_voltage(12.5)
    supply.set_current_limit(1.25)
    supply.set_output(True)
    supply.set_output(False)
    supply.set_ovp_v(15)
    supply.toggle_ocp(True)
    assert supply.get_voltage() == pytest.approx(12.5)
    assert supply.get_current_limit() == pytest.approx(1.25)
    assert supply.get_output() is True
    assert supply.measure_power_w() == pytest.approx(6.2)
    assert supply.get_regulation_mode() == "cv"
    assert supply.get_ovp_v() == pytest.approx(15)
    assert supply.get_ocp_enabled() is False
    assert transport.written == [
        ":VOLT 12.500000",
        ":CURR 1.250000",
        "OUTP:STAT ON",
        "OUTP:STAT OFF",
        ":VOLT:PROT:LEV 15.000000",
        ":CURR:PROT:STAT ON",
    ]


def test_genesys_rejects_generic_ocp_level_and_extra_channels() -> None:
    supply, _transport = _genesys()
    with pytest.raises(EquipmentCapabilityError, match="set_ocp_a"):
        supply.set_ocp_a(1.0)
    with pytest.raises(EquipmentCapabilityError, match="one output"):
        build_instrument("psu", 1, {"model": "tdk-genesys", "channels": 2}, RfStubTransport())


def test_genesys_output_query_must_be_on_or_off() -> None:
    supply, _transport = _genesys({"OUTP:STAT?": "MAYBE"})
    with pytest.raises(EquipmentResponseError, match="output state"):
        supply.get_output()
