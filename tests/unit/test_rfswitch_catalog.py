"""Catalog RF switch routing: Mini-Circuits ASCII vs Vaunix/ZTVX refuse."""

from __future__ import annotations

import pytest
from colosseum_equipment.exceptions import EquipmentCapabilityError
from colosseum_equipment.instruments.factory import build_instrument
from colosseum_equipment.instruments.rfswitch.minicircuits_rc import MiniCircuitsRcSwitch

from tests.support.stubs import RfStubTransport


def test_minicircuits_catalog_uses_rc_dialect() -> None:
    transport = RfStubTransport({"SETA=1": "1", "SWPORT?": "1"})
    inst = build_instrument("rfswitch", 1, {"model": "minicircuits-rcs"}, transport)
    assert isinstance(inst, MiniCircuitsRcSwitch)
    inst.set_switch("A", 1)
    assert inst.measure_path()


def test_vaunix_lsw_refuses_scpi() -> None:
    transport = RfStubTransport()
    inst = build_instrument("rfswitch", 1, {"model": "vaunix-lsw-802pdt"}, transport)
    with pytest.raises(EquipmentCapabilityError, match="not supported"):
        inst.set_path("A")


def test_ztvx_refuses_rout_inheritance() -> None:
    transport = RfStubTransport()
    inst = build_instrument("rfswitch", 1, {"model": "minicircuits-ztvx"}, transport)
    with pytest.raises(EquipmentCapabilityError, match="not supported"):
        inst.set_path("A1:B5")
