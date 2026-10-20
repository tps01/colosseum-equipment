"""User-facing ``col.io`` namespace (registered by ``colosseum_equipment`` plugin)."""

from . import analyzer, dio, i2c, spi

__all__ = ["analyzer", "dio", "i2c", "spi"]
