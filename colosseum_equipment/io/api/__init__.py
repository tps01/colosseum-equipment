"""User-facing ``col.io`` namespace (registered by ``colosseum_equipment`` plugin)."""

from . import analyzer, dio, i2c, onewire, spi

__all__ = ["analyzer", "dio", "i2c", "onewire", "spi"]
