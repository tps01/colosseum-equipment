"""IEEE 488.2 definite-length block helpers."""

from __future__ import annotations

from colosseum_equipment.protocols.scpi import (
    SCPIHelper,
    format_definite_length_block,
    parse_definite_length_block,
)

from tests.support.stubs import RfStubTransport


def test_format_definite_length_block() -> None:
    payload = b"hello"
    assert format_definite_length_block(payload) == b"#15hello"


def test_parse_definite_length_block() -> None:
    data = b"#15hello"
    assert parse_definite_length_block(data) == b"hello"


def test_read_binary_block_reassembles_split_reads() -> None:
    payload = b"0123456789abcdef"
    full = format_definite_length_block(payload)
    assert full.startswith(b"#216")
    transport = RfStubTransport(
        {
            "__raw_chunks__": [
                full[:5],
                full[5:12],
                full[12:],
            ],
        },
    )
    scpi = SCPIHelper(transport)
    assert scpi.read_binary_block("FETCH:DATA?") == payload
    assert transport.written == ["FETCH:DATA?"]
