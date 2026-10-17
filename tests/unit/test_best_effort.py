"""Named models inherit generic SCPI and warn once; overrides stay quiet."""

from __future__ import annotations

import logging

import pytest
from colosseum_equipment.exceptions import EquipmentCapabilityError
from colosseum_equipment.instruments.registry import instrument_model, reset_best_effort_warnings
from colosseum_equipment.instruments.rtsa.generic import GenericRtsa
from colosseum_equipment.instruments.vsg.generic import GenericVSG

from tests.support.stubs import RfStubTransport, StubTransport


def test_inherited_generic_command_warns_once(caplog: pytest.LogCaptureFixture) -> None:
    reset_best_effort_warnings()

    @instrument_model("rtsa", "unit-test-rtsa")
    class _Inherited(GenericRtsa):
        """Manual: https://example.invalid/rtsa"""

    transport = RfStubTransport()
    instrument = _Inherited(transport, {"model": "unit-test-rtsa"})
    with caplog.at_level(logging.WARNING, logger="colosseum.equipment"):
        instrument.set_center_freq(1e9)
        instrument.set_center_freq(2e9)
    assert transport.written == ["FREQ:CENT 1000000000.000000", "FREQ:CENT 2000000000.000000"]
    warnings = [record for record in caplog.records if "unit-test-rtsa" in record.message]
    assert len(warnings) == 1
    assert "set_center_freq" in warnings[0].message


def test_override_and_super_do_not_warn(caplog: pytest.LogCaptureFixture) -> None:
    reset_best_effort_warnings()

    @instrument_model("rtsa", "unit-test-override")
    class _Override(GenericRtsa):
        def set_center_freq(self, frequency_hz: float) -> None:
            self._scpi.write(f"VENDOR {frequency_hz:.0f}")

    @instrument_model("rtsa", "unit-test-super")
    class _CallsSuper(GenericRtsa):
        def set_center_freq(self, frequency_hz: float) -> None:
            super().set_center_freq(frequency_hz)

    override_transport = RfStubTransport()
    super_transport = RfStubTransport()
    override = _Override(override_transport, {"model": "unit-test-override"})
    calls_super = _CallsSuper(super_transport, {"model": "unit-test-super"})
    with caplog.at_level(logging.WARNING, logger="colosseum.equipment"):
        override.set_center_freq(10.0)
        calls_super.set_center_freq(20.0)
    assert override_transport.written == ["VENDOR 10"]
    assert super_transport.written == ["FREQ:CENT 20.000000"]
    assert "using generic SCPI" not in caplog.text


def test_generic_vsg_multicarrier_stays_unsupported() -> None:
    instrument = GenericVSG(StubTransport(), {"model": "generic"})
    with pytest.raises(EquipmentCapabilityError):
        instrument.set_multicarrier(2, 1e6)
