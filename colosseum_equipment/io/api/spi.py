"""SPI master APIs (``col.io.spi``). Measurements use domain ``equipment`` in SQLite.

Configured IDs select bench TOML rows. Core records command and measurement
outcomes and applies its standard optional-failure handling. Unsupported model
operations raise ``EquipmentCapabilityError``; transport failures raise
``EquipmentConnectionError``.
Operation-specific validation and acquisition constraints are described below.
"""

from __future__ import annotations

from typing import Any

from colosseum.decorators import command, measurement
from colosseum.logging import get_logger

from colosseum_equipment.io.connections import get_backend

_logger = get_logger("colosseum.equipment")


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

    :param spi_id: Configured ``io.spi`` ID.
    :param clock_hz: SCLK rate in hertz.
    :param mode: SPI mode 0..3 (CPOL/CPHA).
    :param chip_select: Chip-select index 0..7.
    :param bits_per_word: Bits per SPI sample (typically 8).
    :returns: Applied settings snapshot (clock_hz, mode, chip_select, …).

    :raises IoConfigError: Invalid clock/mode/CS for the configured model.
    """
    _logger.info(
        "Configuring SPI %s clock %s Hz mode %s chip select %s",
        spi_id,
        clock_hz,
        mode,
        chip_select,
    )
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

    :param spi_id: Configured ``io.spi`` ID.
    :param data: MOSI payload bytes.
    :param key: Unique measurement key within domain ``equipment``.

    :returns: Bytes shifted in from MISO.

    :raises IoConnectionError: Transport failure or incomplete transfer.
    :raises IoConfigError: Payload rejected by the configured model limits.
    """
    _logger.info("Transferring %s bytes on SPI %s", len(data), spi_id)
    _ = key
    return bytes(get_backend("spi", spi_id).transfer(bytes(data)))
