"""Fresh power capture and explicit refusal of an average-only sensor."""
from __future__ import annotations

import pytest
from colosseum_equipment.exceptions import EquipmentCapabilityError
from colosseum_equipment.instruments.pwrmeter.generic import GenericPwrMeter
from colosseum_equipment.instruments.pwrmeter.keysight_u2000 import KeysightU2000PwrMeter


class Transport:
    def __init__(self):
        self.events = []

    def write(self, command):
        self.events.append(command)

    def query(self, command):
        self.events.append(command)
        return "1" if command == "*OPC?" else "-10"


def test_fresh_peak_capture_then_fetch():
    transport = Transport()
    sensor = GenericPwrMeter(transport, {})
    sensor.acquire()
    assert sensor.measure_power_peak_dbm() == -10
    assert transport.events == ["INIT:CONT OFF", "INIT:IMM", "*OPC?", "FETC:PEAK?"]


def test_u2000_refuses_peak_without_query():
    transport = Transport()
    sensor = KeysightU2000PwrMeter(transport, {})
    with pytest.raises(EquipmentCapabilityError):
        sensor.measure_power_peak_dbm()
    assert transport.events == []
