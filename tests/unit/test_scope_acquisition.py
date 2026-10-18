"""Single-shot arming must not wait for the event that the procedure creates."""
from __future__ import annotations

import pytest
from colosseum_equipment.instruments.oscope.generic import GenericOscope
from colosseum_equipment.instruments.oscope.tek_mdo4000 import TekMdo4000Oscope


class Transport:
    def __init__(self):
        self.writes = []
        self.queries = []

    def write(self, command):
        self.writes.append(command)

    def query(self, command):
        self.queries.append(command)
        return "1"


@pytest.mark.parametrize("driver", [GenericOscope, TekMdo4000Oscope])
def test_arm_single_returns_before_event(driver):
    transport = Transport()
    scope = driver(transport, {})
    scope.arm_single()
    first = scope._capture_id
    assert first
    assert transport.queries == []
    assert transport.writes[-1] in ("SING", "ACQuire:STATE RUN")
    scope.arm_single()
    assert scope._capture_id != first
    assert transport.queries == []


@pytest.mark.parametrize("driver", [GenericOscope, TekMdo4000Oscope])
def test_blocking_capture_still_arms_then_waits(driver, monkeypatch):
    transport = Transport()
    scope = driver(transport, {})
    completed = []
    monkeypatch.setattr(scope, "wait_complete", lambda **kw: completed.append(list(transport.writes)))
    capture = scope.acquire(timeout_s=1)
    assert capture == scope._capture_id
    assert len(completed) == 1
    assert completed[0][-1] in ("SING", "ACQuire:STATE RUN")


def test_tek_wait_requires_acquisition_stopped(monkeypatch):
    transport = Transport()
    scope = TekMdo4000Oscope(transport, {})
    states = iter(["1", "0"])
    monkeypatch.setattr(scope, "get_acquire_state", lambda: next(states))
    monkeypatch.setattr("colosseum_equipment.instruments.oscope.tek_mdo4000.time.sleep", lambda _: None)
    scope.wait_complete(timeout_s=1)
    # OPC=1 alone must not accept a still-running single sequence.
    assert transport.queries == []


def test_tek_wait_times_out_while_still_running(monkeypatch):
    from colosseum_equipment.exceptions import EquipmentTimeoutError
    scope = TekMdo4000Oscope(Transport(), {})
    ticks = iter([0, 0.001, 2])
    monkeypatch.setattr(scope, "get_acquire_state", lambda: "1")
    monkeypatch.setattr("colosseum_equipment.instruments.oscope.tek_mdo4000.time.monotonic", lambda: next(ticks))
    monkeypatch.setattr("colosseum_equipment.instruments.oscope.tek_mdo4000.time.sleep", lambda _: None)
    with pytest.raises(EquipmentTimeoutError):
        scope.wait_complete(timeout_s=1)
