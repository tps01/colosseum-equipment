"""IEEE 488.2 definite-length block helpers."""

from __future__ import annotations

from pathlib import Path

import pytest
from colosseum_equipment.exceptions import EquipmentResponseError
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


def test_read_binary_block_empty_read_raises_truncated() -> None:
    transport = RfStubTransport(
        {
            "__raw_chunks__": [b"#15ab", b"", b"", b""],
        },
    )
    scpi = SCPIHelper(transport)
    with pytest.raises(EquipmentResponseError, match="expected 5 payload bytes, got 2"):
        scpi.read_binary_block("DATA?")


@pytest.mark.parametrize(
    "seed",
    sorted((Path(__file__).parents[1] / "fixtures/fuzz/corpus").iterdir()),
    ids=lambda path: path.name,
)
def test_fuzz_seed_invariants(seed) -> None:
    from tests.fuzz.scpi_binary import check_input

    check_input(seed.read_bytes())


@pytest.mark.parametrize("target", ["ubx_stream", "mask_validation"])
def test_additional_fuzz_seed_invariants(target) -> None:
    from importlib import import_module

    check = import_module(f"tests.fuzz.{target}").check_input
    for seed in (Path(__file__).parents[1] / "fixtures/fuzz" / target).iterdir():
        check(seed.read_bytes())
