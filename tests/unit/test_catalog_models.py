"""Spreadsheet catalog models register and build."""

from __future__ import annotations

import importlib
import inspect
import pkgutil

from colosseum_equipment.instruments.factory import build_instrument
from colosseum_equipment.instruments.registry import registered_models

from tests.support.stubs import StubTransport


def test_catalog_classes_register_and_build() -> None:
    import colosseum_equipment.instruments as instruments_pkg

    found = 0
    for info in pkgutil.iter_modules(instruments_pkg.__path__):
        if not info.ispkg:
            continue
        module_name = f"colosseum_equipment.instruments.{info.name}.catalog"
        try:
            module = importlib.import_module(module_name)
        except ModuleNotFoundError:
            continue
        for _name, cls in inspect.getmembers(module, inspect.isclass):
            if cls.__module__ != module.__name__:
                continue
            slug = cls.model_slug
            assert slug in registered_models(cls.instrument_kind)
            built = build_instrument(
                cls.instrument_kind,
                1,
                {"model": slug},
                StubTransport(),
            )
            assert isinstance(built, cls)
            found += 1
    # Dedicated Mini-Circuits attenuator / Vaunix refuse modules live outside catalog.py.
    assert found == 155


def test_catalog_aliases_use_the_existing_driver() -> None:
    scope = build_instrument("oscope", 1, {"model": "tektronix-mdo3024"}, StubTransport())
    assert type(scope).__name__ == "TekMdo4000Oscope"
    counter = build_instrument(
        "freqcounter",
        1,
        {"model": "tektronix-fca3003"},
        StubTransport(),
    )
    assert type(counter).__name__ == "TekFca3000FreqCounter"
    sensor = build_instrument("pwrmeter", 1, {"model": "keysight-u2004a"}, StubTransport())
    assert type(sensor).__name__ == "KeysightU2000PwrMeter"
    assert "rigol-dg2000" in registered_models("asg")
    assert "minicircuits-rc" in registered_models("rfswitch")
    assert "minicircuits-usb-switch" in registered_models("rfswitch")
