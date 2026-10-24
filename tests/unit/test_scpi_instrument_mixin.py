"""ScpiInstrumentMixin close behavior."""

from __future__ import annotations

from colosseum_equipment.instruments.dmm.generic import GenericDMM

from tests.support.stubs import RfStubTransport, StubTransport


class _ClosingStubTransport(StubTransport):
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


def test_generic_dmm_mixin_close() -> None:
    transport = _ClosingStubTransport()
    GenericDMM(transport).close()
    assert transport.closed is True


def test_generic_dmm_get_function_uses_sens_func() -> None:
    transport = RfStubTransport({"SENS:FUNC?": '"VOLT:DC"'})
    queries: list[str] = []
    original = transport.query

    def tracking_query(data: str) -> str:
        queries.append(data)
        return original(data)

    transport.query = tracking_query  # type: ignore[method-assign]
    dmm = GenericDMM(transport)
    assert dmm.get_function() == "VOLT:DC"
    assert queries == ["SENS:FUNC?"]
