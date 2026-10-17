"""Example scripts still accept the deprecated config environment variable."""

from __future__ import annotations

import importlib.util
import warnings
from pathlib import Path

_EXAMPLE = (
    Path(__file__).resolve().parents[2] / "examples" / "test_power_rails.py"
)


def test_legacy_bench_config_env_warns(monkeypatch) -> None:
    monkeypatch.delenv("COLOSSEUM_CONFIG", raising=False)
    monkeypatch.setenv("COLOSSEUM_BENCH_CONFIG", "legacy.toml")
    spec = importlib.util.spec_from_file_location("example_power_rails_env", _EXAMPLE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        spec.loader.exec_module(module)
        assert module._config_filename() == "legacy.toml"
    assert any(issubclass(item.category, DeprecationWarning) for item in caught)


def test_config_env_wins_without_deprecation(monkeypatch) -> None:
    monkeypatch.setenv("COLOSSEUM_CONFIG", "current.toml")
    monkeypatch.setenv("COLOSSEUM_BENCH_CONFIG", "legacy.toml")
    spec = importlib.util.spec_from_file_location("example_power_rails_current", _EXAMPLE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        spec.loader.exec_module(module)
        name = module._config_filename()
    assert name == "current.toml"
    assert not any(issubclass(item.category, DeprecationWarning) for item in caught)
