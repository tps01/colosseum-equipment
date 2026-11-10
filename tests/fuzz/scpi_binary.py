"""Bounded SCPI block fuzzing: python -m tests.fuzz.scpi_binary [libFuzzer options]."""

from __future__ import annotations

import sys


def check_input(data: bytes) -> None:
    """Check parser robustness and independently constructed block invariants."""
    from colosseum_equipment.exceptions import EquipmentResponseError
    from colosseum_equipment.protocols.scpi import (
        format_definite_length_block,
        parse_definite_length_block,
    )

    try:
        result = parse_definite_length_block(data)
    except EquipmentResponseError:
        if not data.startswith(b"#"):
            raise
    else:
        assert isinstance(result, bytes)
        if not data.startswith(b"#"):
            assert result == data

    length = str(len(data)).encode("ascii")
    block = b"#" + str(len(length)).encode("ascii") + length + data
    assert format_definite_length_block(data) == block
    for suffix in (b"", b"\r", b"\n", b"\r\n"):
        assert parse_definite_length_block(block + suffix) == data

    longer = str(len(data) + 1).encode("ascii")
    truncated = b"#" + str(len(longer)).encode("ascii") + longer + data
    for invalid in (truncated, block + b"\x00"):
        try:
            parse_definite_length_block(invalid)
        except EquipmentResponseError:
            pass
        else:
            raise AssertionError(f"Accepted invalid block: {invalid!r}")


def main() -> None:
    """Instrument before target imports and forward CLI options to libFuzzer."""
    import atheris

    with atheris.instrument_imports():
        import colosseum_equipment.protocols.scpi  # noqa: F401

    atheris.Setup(sys.argv, atheris.instrument_func(check_input))
    atheris.Fuzz()


if __name__ == "__main__":
    main()
