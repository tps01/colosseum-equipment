"""SPI master APIs (``col.io.spi``). Measurements use domain ``equipment`` in SQLite."""

from __future__ import annotations

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
) -> None:
    """Update SPI clock, mode (0..3), chip select, and/or bits per word.

    :param spi_id: Configured ``io.spi`` id from config TOML.
    :type spi_id: int
    :param clock_hz: SCLK rate in hertz.
    :type clock_hz: int | None, optional
    :param mode: SPI mode 0..3 (CPOL/CPHA).
    :type mode: int | None, optional
    :param chip_select: Chip-select index 0..7.
    :type chip_select: int | None, optional
    :param bits_per_word: Bits per SPI sample (typically 8).
    :type bits_per_word: int | None, optional

    :returns: None
    """
    get_backend("spi", spi_id).configure(
        clock_hz=clock_hz,
        mode=mode,
        chip_select=chip_select,
        bits_per_word=bits_per_word,
    )


@measurement
def transfer(*, spi_id: int, data: bytes, key: str) -> bytes:
    """Full-duplex SPI transfer; returns bytes shifted in from MISO.

    :param spi_id: Configured ``io.spi`` id from config TOML.
    :type spi_id: int
    :param data: MOSI payload bytes.
    :type data: bytes
    :param key: Unique measurement key within domain ``equipment``.
    :type key: str

    :returns: MISO payload bytes (same length as ``data`` on success).
    :rtype: bytes
    """
    _ = key
    return bytes(get_backend("spi", spi_id).transfer(bytes(data)))
