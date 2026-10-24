"""Mini-Circuits attenuator SETATT dialect and Vaunix SDK refuse."""

from __future__ import annotations

import pytest
from colosseum_equipment.exceptions import EquipmentCapabilityError
from colosseum_equipment.instruments.attn.minicircuits import MiniCircuitsAttn
from colosseum_equipment.instruments.factory import build_instrument

from tests.support.stubs import RfStubTransport


def test_minicircuits_single_channel_setatt() -> None:
    transport = RfStubTransport({":SETATT=12.750": "1", ":ATT?": "12.75"})
    queries: list[str] = []
    original_query = transport.query

    def tracking_query(data: str) -> str:
        queries.append(data)
        return original_query(data)

    transport.query = tracking_query  # type: ignore[method-assign]
    inst = build_instrument("attn", 1, {"model": "minicircuits-rudat"}, transport)
    assert isinstance(inst, MiniCircuitsAttn)
    inst.set_attenuation_db(12.75)
    assert queries == [":SETATT=12.750"]
    assert inst.measure_attenuation_db() == pytest.approx(12.75)


def test_minicircuits_multi_channel_setatt() -> None:
    transport = RfStubTransport(
        {
            ":CHAN:2:SETATT:15.750": "1",
            ":ATT?": "10.0 15.75 20.0 25.0",
        },
    )
    inst = build_instrument("attn", 1, {"model": "minicircuits-rc4dat"}, transport)
    inst.set_attenuation_db(15.75, channel=2)
    assert inst.measure_attenuation_db(channel=2) == pytest.approx(15.75)


def test_vaunix_lda_refuses_scpi() -> None:
    transport = RfStubTransport()
    inst = build_instrument("attn", 1, {"model": "vaunix-lda"}, transport)
    with pytest.raises(EquipmentCapabilityError, match="not supported"):
        inst.set_attenuation_db(10.0)
