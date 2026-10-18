"""MIT-sourced family overrides send the referenced command and stay quiet."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from colosseum_equipment.instruments.factory import build_instrument
from colosseum_equipment.instruments.registry import reset_best_effort_warnings

from tests.support.stubs import RfStubTransport, StubTransport

if TYPE_CHECKING:
    import pytest


def _build(kind: str, model: str, transport: StubTransport | RfStubTransport):
    return build_instrument(kind, 1, {"model": model}, transport)


def test_rigol_dp800_set_voltage_uses_python_ivi_command(
    caplog: pytest.LogCaptureFixture,
) -> None:
    reset_best_effort_warnings()
    transport = RfStubTransport()
    instrument = _build("psu", "rigol-dp832", transport)
    with caplog.at_level(logging.WARNING, logger="colosseum.equipment"):
        instrument.set_voltage(5.0)
    assert "source:voltage:level 5.000000" in transport.written
    assert "using generic SCPI" not in caplog.text
    sibling = _build("psu", "rigol-dp832a", RfStubTransport())
    assert type(sibling).__bases__[0].__name__ == "RigolDp800"


def test_rigol_dp700_still_warns_on_generic(caplog: pytest.LogCaptureFixture) -> None:
    reset_best_effort_warnings()
    transport = RfStubTransport()
    instrument = _build("psu", "rigol-dp711", transport)
    with caplog.at_level(logging.WARNING, logger="colosseum.equipment"):
        instrument.set_voltage(3.3)
    assert transport.written == ["VOLT 3.300000"]
    assert "using generic SCPI" in caplog.text


def test_siglent_spd_single_set_voltage(caplog: pytest.LogCaptureFixture) -> None:
    reset_best_effort_warnings()
    transport = RfStubTransport()
    instrument = _build("psu", "siglent-spd1168x", transport)
    with caplog.at_level(logging.WARNING, logger="colosseum.equipment"):
        instrument.set_voltage(12.0)
    assert transport.written == ["CH1:VOLT 12"]
    assert "using generic SCPI" not in caplog.text


def test_rigol_dg800_set_frequency(caplog: pytest.LogCaptureFixture) -> None:
    reset_best_effort_warnings()
    transport = RfStubTransport()
    instrument = _build("asg", "rigol-dg811", transport)
    with caplog.at_level(logging.WARNING, logger="colosseum.equipment"):
        instrument.set_frequency(1e6)
    assert transport.written == [":SOUR1:FREQ 1000000.000000"]
    assert "using generic SCPI" not in caplog.text


def test_rigol_dho_timebase(caplog: pytest.LogCaptureFixture) -> None:
    reset_best_effort_warnings()
    transport = RfStubTransport({"*OPC?": "1"})
    instrument = _build("oscope", "rigol-dho804", transport)
    with caplog.at_level(logging.WARNING, logger="colosseum.equipment"):
        instrument.set_timebase_scale(1e-6)
    assert transport.written == [":TIM:MAIN:SCAL 1e-06"]
    assert "using generic SCPI" not in caplog.text


def test_siglent_sds1000x_e_measure_vpp(caplog: pytest.LogCaptureFixture) -> None:
    reset_best_effort_warnings()
    transport = RfStubTransport({"C1:PAVA? PKPK": "C1:PAVA PKPK,1.25V"})
    instrument = _build("oscope", "siglent-sds1104x-e", transport)
    with caplog.at_level(logging.WARNING, logger="colosseum.equipment"):
        value = instrument.measure_vpp(1)
    assert value == 1.25
    assert "using generic SCPI" not in caplog.text


def test_keithley_dmm6500_measure_voltage(caplog: pytest.LogCaptureFixture) -> None:
    reset_best_effort_warnings()
    transport = RfStubTransport({":READ?": "1.234"})
    instrument = _build("dmm", "keithley-dmm6500", transport)
    with caplog.at_level(logging.WARNING, logger="colosseum.equipment"):
        value = instrument.measure_voltage(1)
    assert value == 1.234
    assert transport.written == [':SENS:FUNC "VOLT:DC"']
    assert "using generic SCPI" not in caplog.text


def test_keysight_34401a_measure_voltage(caplog: pytest.LogCaptureFixture) -> None:
    reset_best_effort_warnings()
    transport = RfStubTransport({"MEAS:VOLT:DC? DEF,DEF": "2.5"})
    instrument = _build("dmm", "keysight-34401a", transport)
    with caplog.at_level(logging.WARNING, logger="colosseum.equipment"):
        value = instrument.measure_voltage(1)
    assert value == 2.5
    assert "using generic SCPI" not in caplog.text


def test_rigol_dsa800_center_frequency(caplog: pytest.LogCaptureFixture) -> None:
    reset_best_effort_warnings()
    transport = RfStubTransport()
    instrument = _build("speca", "rigol-dsa815", transport)
    with caplog.at_level(logging.WARNING, logger="colosseum.equipment"):
        instrument.set_center_frequency(1e9)
    assert transport.written == [":SENSe:FREQuency:CENTer 1000000000.0"]
    assert "using generic SCPI" not in caplog.text


def test_rigol_dsg3136b_set_power(caplog: pytest.LogCaptureFixture) -> None:
    reset_best_effort_warnings()
    transport = RfStubTransport()
    instrument = _build("vsg", "rigol-dsg3136b", transport)
    with caplog.at_level(logging.WARNING, logger="colosseum.equipment"):
        instrument.set_power(-10.0)
    assert transport.written == ["LEV -10.00"]
    assert "using generic SCPI" not in caplog.text
