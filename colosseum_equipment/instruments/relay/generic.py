"""Generic relay placeholder — vendor models implement HTTP control."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, NoReturn

from colosseum_equipment.exceptions import EquipmentCapabilityError
from colosseum_equipment.instruments.registry import instrument_model

if TYPE_CHECKING:
    from colosseum_equipment.transports.base import Transport


@instrument_model(
    "relay",
    "generic",
    address="http",
    extra_optional=("channel", "relay_count"),
)
class GenericRelay:
    _model = "generic"

    def __init__(self, transport: Transport, config: dict[str, Any]) -> None:
        self._transport = transport
        self._config = config
        self._model = str(config.get("model", "generic")).lower()
        self._default_channel = int(config.get("channel", 1))
        self._relay_count = int(config.get("relay_count", 8))

    def _unsupported(self, operation: str) -> NoReturn:
        raise EquipmentCapabilityError(
            f"relay model `{self._model}` does not support {operation}; "
            "configure controlbyweb-webrelay or controlbyweb-x410",
        )

    def set_relay(self, channel: int, enabled: bool) -> None:
        _ = channel, enabled
        self._unsupported("set_relay")

    def set_all(self, bitmask: int) -> None:
        _ = bitmask
        self._unsupported("set_all")

    def pulse_relay(self, channel: int, duration_s: float | None = None) -> None:
        _ = channel, duration_s
        self._unsupported("pulse_relay")

    def set_pulse_width_s(self, channel: int, width_s: float) -> None:
        _ = channel, width_s
        self._unsupported("set_pulse_width_s")

    def measure_relay(self, channel: int) -> bool:
        _ = channel
        self._unsupported("measure_relay")

    def measure_all(self) -> int:
        self._unsupported("measure_all")

    def close(self) -> None:
        self._transport.close()
