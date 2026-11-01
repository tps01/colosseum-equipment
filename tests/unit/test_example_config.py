"""Example scripts honor COLOSSEUM_CONFIG for the config filename."""

from __future__ import annotations

import importlib.util
from pathlib import Path

_EXAMPLE = (
    Path(__file__).resolve().parents[2] / "examples" / "test_power_rails.py"
)


def test_config_env_selects_filename(monkeypatch) -> None:
    monkeypatch.setenv("COLOSSEUM_CONFIG", "current.toml")
    spec = importlib.util.spec_from_file_location("example_power_rails_current", _EXAMPLE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module._config_filename() == "current.toml"


def test_default_config_filename(monkeypatch) -> None:
    monkeypatch.delenv("COLOSSEUM_CONFIG", raising=False)
    spec = importlib.util.spec_from_file_location("example_power_rails_default", _EXAMPLE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module._config_filename() == "config.toml"
