from __future__ import annotations

import pytest

from colosseum_equipment.instruments.factory import build_instrument
from colosseum_equipment.transports.null_transport import NullTransport

@pytest.mark.parametrize(
    "kind",
    [
        "attn",
        "pwrmeter",
        "rfswitch",
        "oscope",
        "eload",
        "freqcounter",
        "vna",
        "rtsa",
    ],
)
def test_build_generic_kind_closes(kind: str) -> None:
    transport = NullTransport()
    instrument = build_instrument(kind, 1, {"model": "generic"}, transport)
    instrument.close()


def test_generic_rfswitch_set_switch_writes_route_scpi() -> None:
    from tests.support.stubs import RfStubTransport

    transport = RfStubTransport()
    instrument = build_instrument("rfswitch", 1, {"model": "generic"}, transport)
    instrument.set_switch("A", 1)
    instrument.set_switch("B", 0)
    assert transport.written == ["ROUT:CLOS (@A)", "ROUT:OPEN (@B)"]


def test_generic_oscope_save_screenshot(unit_runtime_context) -> None:
    from pathlib import Path

    from tests.support.stubs import RfStubTransport

    _ = unit_runtime_context
    transport = RfStubTransport({"__raw__": b"#14PNG!"})
    instrument = build_instrument("oscope", 1, {"model": "generic"}, transport)
    instrument.save_screenshot("captures/scope.png")
    matches = list(Path(unit_runtime_context.output_dir).rglob("scope.png"))
    assert matches
    assert matches[0].read_bytes() == b"PNG!"
    assert "HCOP:SDUM:DATA?" in transport.written

