"""SPI master APIs (``col.io.spi``). Measurements use domain ``equipment`` in SQLite."""

from __future__ import annotations

from typing import Any

from colosseum.decorators import command, measurement

from colosseum_equipment.io.connections import get_backend


@command
def configure(
    *,
    spi_id: int,
    clock_hz: int | None = None,
    mode: int | None = None,
    chip_select: int | None = None,
    bits_per_word: int | None = None,
) -> dict[str, Any]:
    """Update SPI clock, mode (0..3), chip select, and/or bits per word.

    :returns: Applied settings snapshot (clock_hz, mode, chip_select, …).

    :raises IoConnectionError: Transport or instrument connection failed.
    :raises IoConfigError: Invalid clock/mode/CS for the configured model.
    """
    return dict(
        get_backend("spi", spi_id).configure(
            clock_hz=clock_hz,
            mode=mode,
            chip_select=chip_select,
            bits_per_word=bits_per_word,
        ),
    )


@measurement
def transfer(*, spi_id: int, data: bytes, key: str) -> bytes:
    """Full-duplex SPI transfer; returns bytes shifted in from MISO.

    Short transfers raise ``IoConnectionError`` rather than returning truncated data.

    :raises IoConnectionError: Transport failure or incomplete transfer.
    :raises IoConfigError: Payload rejected by the configured model limits.
    """
    _ = key
    return bytes(get_backend("spi", spi_id).transfer(bytes(data)))
