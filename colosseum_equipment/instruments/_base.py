from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from colosseum_equipment.protocols.scpi import SCPIHelper


class ScpiInstrumentMixin:
    """Mixin for SCPI instruments that close via the underlying transport."""

    _scpi: SCPIHelper

    def close(self) -> None:
        self._scpi._transport.close()
