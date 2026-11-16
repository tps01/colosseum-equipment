"""PSU control and wait helpers."""

from __future__ import annotations

import pytest
from colosseum_equipment.exceptions import EquipmentTimeoutError
from colosseum_equipment.instruments.factory import build_instrument

from tests.support.stubs import RfStubTransport


class _CurrentRampTransport(RfStubTransport):
    def __init__(self, readings: list[float]) -> None:
        super().__init__()
        self._readings = list(readings)
        self._index = 0

    def query(self, data: str) -> str:
        if data.strip() == "MEAS:CURR?":
            if self._index < len(self._readings):
                value = self._readings[self._index]
                self._index += 1
                return str(value)
            return str(self._readings[-1])
        return super().query(data)


def test_wait_for_current_reaches_target() -> None:
    transport = _CurrentRampTransport([0.1, 0.5, 0.95, 1.0])
    inst = build_instrument("psu", 1, {"model": "generic"}, transport)
    inst.wait_for_current(1.0, timeout_s=1.0, tolerance=0.05)


def test_wait_for_current_times_out() -> None:
    transport = _CurrentRampTransport([0.1, 0.2, 0.2])
    inst = build_instrument("psu", 1, {"model": "generic"}, transport)
    with pytest.raises(EquipmentTimeoutError, match="did not reach"):
        inst.wait_for_current(1.0, timeout_s=0.2, tolerance=0.01)


def test_toml_setpoints_precede_output_enable_and_setup_failure_blocks_enable():
    from colosseum_equipment.instruments.factory import build_instrument
    from tests.support.stubs import RfStubTransport

    transport = RfStubTransport()
    supply = build_instrument('psu', 1, {'model': 'generic', 'voltage': 5, 'ocp': .1, 'ovp': 5.5}, transport)
    supply.set_output(True)
    assert transport.written == ['VOLT 5.000000', 'CURR 0.100000', 'VOLT:PROT 5.500000', 'OUTP ON']

    class FailingTransport(RfStubTransport):
        def write(self, command):
            super().write(command)
            if command.startswith('VOLT '):
                raise OSError('voltage setup failed')

    failed = FailingTransport()
    with pytest.raises(OSError):
        build_instrument('psu', 1, {'model': 'generic', 'voltage': 5}, failed).set_output(True)
    assert 'OUTP ON' not in failed.written
