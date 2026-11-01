"""Tests for equipment id='all' broadcast fan-out."""

from __future__ import annotations

from unittest.mock import MagicMock

import colosseum as col
import pytest
from colosseum.config.loader import ConfigError, apply_raw_config
from colosseum.context import init_context
from colosseum_equipment.api import psu as psu_api
from colosseum_equipment.api import vsg as vsg_api
from colosseum_equipment.api._broadcast import (
    list_equipment_ids,
    resolve_equipment_ids,
)
from colosseum_equipment.exceptions import EquipmentError


def test_resolve_all_lists_sorted_psu_ids(unit_runtime_context) -> None:
    col.config.load_config("examples/configs/config.sim.toml")
    assert list_equipment_ids("psu") == [1, 2]
    assert resolve_equipment_ids("psu", "all") == [1, 2]
    assert resolve_equipment_ids("psu", 2) == [2]


def test_resolve_all_empty_raises(unit_runtime_context) -> None:
    apply_raw_config(unit_runtime_context, {}, source_label="(empty)")
    with pytest.raises(ConfigError, match="No configured equipment.psu"):
        resolve_equipment_ids("psu", "all")


def test_psu_set_output_all_calls_each_id(unit_runtime_context, monkeypatch) -> None:
    col.config.load_config("examples/configs/config.sim.toml")
    calls: list[tuple[int, bool]] = []

    def _fake_inst(psu_id: object) -> MagicMock:
        mock = MagicMock()

        def _set_output(enabled: bool, channel: int = 1) -> None:
            calls.append((int(psu_id), enabled))  # type: ignore[arg-type]

        mock.set_output.side_effect = _set_output
        return mock

    monkeypatch.setattr(psu_api, "_inst", _fake_inst)
    psu_api.set_output(psu_id="all", enabled=False)
    assert calls == [(1, False), (2, False)]


def test_psu_set_output_all_aggregates_failures(unit_runtime_context, monkeypatch) -> None:
    col.config.load_config("examples/configs/config.sim.toml")
    seen: list[int] = []

    def _fake_inst(psu_id: object) -> MagicMock:
        mock = MagicMock()

        def _set_output(enabled: bool, channel: int = 1) -> None:
            seen.append(int(psu_id))  # type: ignore[arg-type]
            if int(psu_id) == 1:  # type: ignore[arg-type]
                raise RuntimeError("boom-1")

        mock.set_output.side_effect = _set_output
        return mock

    monkeypatch.setattr(psu_api, "_inst", _fake_inst)
    with pytest.raises(EquipmentError, match="failed ids 1") as err:
        psu_api.set_output(psu_id="all", enabled=True)
    assert seen == [1, 2]
    assert "boom-1" in str(err.value)


def test_psu_numeric_id_unchanged(unit_runtime_context, monkeypatch) -> None:
    col.config.load_config("examples/configs/config.sim.toml")
    mock = MagicMock()
    monkeypatch.setattr(psu_api, "_inst", lambda psu_id: mock)
    psu_api.set_output(psu_id=2, enabled=True)
    mock.set_output.assert_called_once_with(True, channel=1)


def test_vsg_upload_waveform_all(tmp_path, monkeypatch) -> None:
    ctx = init_context(test_case_name="vsg_broadcast", no_artifacts=True)
    apply_raw_config(
        ctx,
        {
            "equipment": {
                "vsg": [
                    {"vsg_id": 1, "resource": "SIM::VSG1", "driver": "sim"},
                    {"vsg_id": 2, "resource": "SIM::VSG2", "driver": "sim"},
                ],
            },
        },
        source_label="(vsg-test)",
    )
    calls: list[tuple[int, str, str]] = []

    def _fake_get(kind: str, equipment_id: int) -> MagicMock:
        assert kind == "vsg"
        mock = MagicMock()

        def _upload(local_path: str, remote_name: str, **kwargs: object) -> None:
            calls.append((equipment_id, local_path, remote_name))

        mock.upload_waveform.side_effect = _upload
        return mock

    monkeypatch.setattr(vsg_api, "get_cached_instrument", _fake_get)
    monkeypatch.setattr(
        "colosseum_equipment.connections.get_cached_instrument",
        _fake_get,
    )
    wave = tmp_path / "wave.wfm"
    wave.write_bytes(b"iq")
    vsg_api.upload_waveform(
        vsg_id="all",
        local_path=str(wave),
        remote_name="WAVE1",
    )
    assert calls == [
        (1, str(wave), "WAVE1"),
        (2, str(wave), "WAVE1"),
    ]
