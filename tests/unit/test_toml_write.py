"""Unit tests for config TOML writer."""

from __future__ import annotations

import warnings
from typing import TYPE_CHECKING

import pytest
from colosseum.config.toml_relaxed import read_relaxed_toml
from colosseum_equipment.autoconfig.toml_write import (
    TomlWriteError,
    render_bench_toml,
    write_bench_toml,
    write_config_toml,
)

if TYPE_CHECKING:
    from pathlib import Path


def test_render_single_table_section() -> None:
    raw = {
        "equipment": {
            "dmm": {
                "dmm_id": 1,
                "model": "generic",
                "resource": "USB0::0x2A8D::0x8F01::INSTR",
            },
        },
    }
    text = render_bench_toml(raw, header_comment=None)
    assert "[equipment.dmm]" in text
    assert "[[equipment.dmm]]" not in text
    assert "model = generic" in text
    assert "resource = USB0::0x2A8D::0x8F01::INSTR" in text


def test_render_array_of_tables_for_multiple_rows() -> None:
    raw = {
        "equipment": {
            "psu": [
                {"psu_id": 1, "model": "generic", "resource": "GPIB0::1::INSTR"},
                {"psu_id": 2, "model": "tdk-genesys", "resource": "TCPIP0::10.0.0.5::INSTR"},
            ],
        },
    }
    text = render_bench_toml(raw, header_comment=None)
    assert text.count("[[equipment.psu]]") == 2
    assert "model = tdk-genesys" in text


def test_write_config_toml_round_trip(tmp_path: Path) -> None:
    raw = {
        "equipment": {
            "psu": [
                {"psu_id": 1, "model": "generic", "resource": "GPIB0::1::INSTR"},
                {"psu_id": 2, "model": "generic", "resource": "GPIB0::2::INSTR"},
            ],
            "dmm": {"dmm_id": 1, "model": "keysight-edu34450a", "resource": "USB0::INSTR"},
        },
    }
    path = write_config_toml(raw, tmp_path / "config.generated.toml", header_comment="# test")
    loaded = read_relaxed_toml(path)
    assert loaded == raw


def test_write_config_toml_rejects_directory(tmp_path: Path) -> None:
    target = tmp_path / "out"
    target.mkdir()
    with pytest.raises(TomlWriteError, match="directory"):
        write_config_toml({"equipment": {}}, target)


def test_write_bench_toml_deprecated_alias(tmp_path: Path) -> None:
    raw = {"equipment": {"dmm": {"dmm_id": 1, "model": "generic", "resource": "SIM::DMM1"}}}
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        path = write_bench_toml(raw, tmp_path / "legacy.toml")
    assert len(caught) == 1
    assert issubclass(caught[0].category, DeprecationWarning)
    assert read_relaxed_toml(path) == raw
