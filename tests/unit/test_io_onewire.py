"""Unit tests for col.io.onewire (sim + DS2480B framing helpers)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import colosseum as col
import pytest
from colosseum.config import load_config
from colosseum_equipment.io.backends.ds2480b import hex_to_rom, rom_to_hex
from colosseum_equipment.io.backends.factory import open_onewire_backend
from colosseum_equipment.io.exceptions import IoConfigError, IoConnectionError

if TYPE_CHECKING:
    from colosseum.context import RuntimeContext


def test_rom_hex_roundtrip() -> None:
    rom = bytes.fromhex("28001122334455A1")
    assert hex_to_rom(rom_to_hex(rom)) == rom


def test_open_onewire_requires_driver() -> None:
    with pytest.raises(IoConfigError, match="requires driver"):
        open_onewire_backend(1, {})


def test_io_onewire_sim_search_select_read(
    io_runtime_context: RuntimeContext,
    io_bench,
) -> None:
    _ = io_runtime_context
    load_config(
        io_bench(
            """
            [io.onewire]
            onewire_id = 1
            driver = sim
            presence = true
            roms = ["28001122334455CE"]
            read_data = "aabb"
            """,
        ),
    )
    settings = col.io.onewire.configure(onewire_id=1, speed="standard")
    assert settings["speed"] == "standard"
    assert settings["driver"] == "sim"
    assert col.io.onewire.reset(onewire_id=1) is True
    roms = col.io.onewire.search(onewire_id=1, key="roms")
    assert roms == ["28001122334455CE"]
    col.io.onewire.select(onewire_id=1, rom=roms[0])
    assert (
        col.io.onewire.write_read(
            onewire_id=1,
            write_data=b"\xbe",
            read_nbytes=2,
            key="scratch",
        )
        == b"\xaa\xbb"
    )


def test_io_onewire_sim_required_presence_raises(
    io_runtime_context: RuntimeContext,
    io_bench,
) -> None:
    load_config(
        io_bench(
            """
            [io.onewire]
            onewire_id = 1
            driver = sim
            presence = false
            """,
        ),
    )
    assert col.io.onewire.reset(onewire_id=1) is False
    with pytest.raises(IoConnectionError, match="presence"):
        col.io.onewire.reset(onewire_id=1, required=True)


def test_io_onewire_sim_selects_lowercase_search_rom(
    io_runtime_context: RuntimeContext,
    io_bench,
) -> None:
    _ = io_runtime_context
    load_config(
        io_bench(
            """
            [io.onewire]
            onewire_id = 1
            driver = sim
            presence = true
            roms = ["28aabbccddeeff00"]
            """,
        ),
    )
    roms = col.io.onewire.search(onewire_id=1, key="roms")
    assert roms == ["28AABBCCDDEEFF00"]
    col.io.onewire.select(onewire_id=1, rom=roms[0])


def test_ds2480b_requires_port() -> None:
    with pytest.raises(IoConfigError, match="requires port="):
        open_onewire_backend(1, {"driver": "maxim-ds9481r"})
