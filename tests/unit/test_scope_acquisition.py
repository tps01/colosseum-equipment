"""Single-shot arming must not wait for the event that the procedure creates."""

from __future__ import annotations

import csv
import logging

import pytest
from colosseum_equipment.instruments.oscope.generic import GenericOscope
from colosseum_equipment.instruments.oscope.tek_mdo4000 import TekMdo4000Oscope
from colosseum_equipment.instruments.registry import reset_best_effort_warnings


class Transport:
    def __init__(self):
        self.writes = []
        self.queries = []

    def write(self, command):
        self.writes.append(command)

    def query(self, command):
        self.queries.append(command)
        return "1"


def test_tek_waveform_csv_and_evidence_stay_quiet(
    unit_runtime_context,
    tmp_path,
    monkeypatch,
    caplog,
):
    reset_best_effort_warnings()
    scope = TekMdo4000Oscope(Transport(), {"model": "tektronix-mdo4000"})
    metadata = {"xinc_s": 0.5, "xorigin_s": 1.0, "capture_id": "capture-7"}
    monkeypatch.setattr(scope, "_read_waveform_points", lambda channel: ([2.0, 3.0], metadata))
    path = tmp_path / "wave.csv"
    with caplog.at_level(logging.WARNING, logger="colosseum.equipment"):
        assert scope.save_waveform(channel=1, path=str(path), key="wave") == path
    with path.open(newline="", encoding="utf-8") as handle:
        assert list(csv.reader(handle)) == [
            ["time_s", "voltage_v"],
            ["1.0", "2.0"],
            ["1.5", "3.0"],
        ]
    row = unit_runtime_context.db.get_measurement("equipment", "save_waveform", "wave")
    assert row is not None and row.value == metadata
    assert "using generic SCPI" not in caplog.text


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


@pytest.mark.parametrize(
    ("preamble", "payload", "error"),
    [
        ("2,0,2,1,0.5,-1,0,0.01,0,128", "#180.5,-0.5", None),
        ("2,0,2,1,0.5,-1,0,0.01,0,128", "#190.5,-0.5", "truncated"),
        ("2,0,2,1,0.5,-1,0,0.01,0,128", "0.5,nan", "invalid DS1054Z waveform samples"),
        ("2,0,3,1,0.5,-1,0,0.01,0,128", "0.5,-0.5", "waveform truncated"),
        ("2,0,2,1,0.5,-1,0,0.01,0,128", "0.5,-0.5,0.0", "point count"),
        ("2,0,2,1,0,-1,0,0.01,0,128", "", "time axis"),
        ("bad preamble", "", "invalid DS1054Z waveform preamble"),
    ],
)
def test_ds1054z_export_uses_ascii_volts_and_restores_transfer(
    preamble, payload, error, unit_runtime_context, tmp_path, monkeypatch,
):
    from colosseum_equipment.api import oscope
    from colosseum_equipment.exceptions import EquipmentResponseError
    from colosseum_equipment.instruments.factory import build_instrument

    replies = {
        "WAV:SOUR?": "CHAN2", "WAV:MODE?": "MAX", "WAV:FORM?": "BYTE",
        "WAV:PRE?": preamble, "WAV:DATA?": payload,
    }
    transport = Transport()

    def query(command):
        transport.queries.append(command)
        return replies[command]

    monkeypatch.setattr(transport, "query", query)
    scope = build_instrument("oscope", 1, {"model": "rigol-ds1054z"}, transport)
    monkeypatch.setattr(oscope, "get_cached_instrument", lambda *_: scope)
    path = tmp_path / "rigol.csv"

    if error:
        with pytest.raises(EquipmentResponseError, match=error):
            oscope.save_waveform(oscope_id=1, channel=1, path=str(path), key="rigol")
        assert not path.exists()
        assert unit_runtime_context.db.get_measurement("equipment", "save_waveform", "rigol") is None
    else:
        oscope.save_waveform(oscope_id=1, channel=1, path=str(path), key="rigol")
        with path.open(newline="", encoding="utf-8") as handle:
            assert list(csv.reader(handle)) == [["time_s", "voltage_v"], ["-1.0", "0.5"], ["-0.5", "-0.5"]]
        row = unit_runtime_context.db.get_measurement("equipment", "save_waveform", "rigol")
        assert row.value["points"] == 2

    assert transport.writes == [
        "WAV:SOUR CHAN1", "WAV:MODE NORM", "WAV:FORM ASC",
        "WAV:FORM BYTE", "WAV:MODE MAX", "WAV:SOUR CHAN2",
    ]
    assert transport.queries[:4] == ["WAV:SOUR?", "WAV:MODE?", "WAV:FORM?", "WAV:PRE?"]
