"""Adaura Technologies R3 programmable RF attenuator (text protocol).

Manual: AdauraTech Attenuator Manual R3 — ``SET [Ch] [Atten]``, ``STATUS``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from colosseum_equipment.exceptions import EquipmentCapabilityError
from colosseum_equipment.instruments._settle import wait_settle_s
from colosseum_equipment.instruments._text_protocol import parse_adaura_status_channel
from colosseum_equipment.instruments.registry import instrument_model

if TYPE_CHECKING:
    from colosseum_equipment.transports.base import Transport


@instrument_model(
    "attn",
    "adaura-r3",
    extra_optional=(
        "channel",
        "path",
        "min_attenuation_db",
        "max_attenuation_db",
        "step_db",
        "settle_s",
    ),
)
class AdauraR3Attn:
    def __init__(self, transport: Transport, config: dict[str, Any]) -> None:
        self._transport = transport
        self._config = config
        self._default_channel = int(config.get("channel", config.get("path", 1)))
        if "attenuation_db" in config:
            self.set_attenuation_db(float(config["attenuation_db"]))

    def _channel(self, channel: int | None) -> int:
        if channel is not None:
            return int(channel)
        return self._default_channel

    def set_attenuation_db(
        self,
        attenuation_db: float,
        *,
        channel: int | None = None,
        settle_s: float | None = None,
    ) -> None:
        ch = self._channel(channel)
        self._transport.write(f"SET {ch} {attenuation_db:.2f}")
        wait_settle_s(self._config, settle_s=settle_s)

    def measure_attenuation_db(self, *, channel: int | None = None) -> float:
        ch = self._channel(channel)
        response = self._transport.query("STATUS")
        return parse_adaura_status_channel(response, ch)

    def _limit_from_config(self, key: str, operation: str) -> float:
        if key not in self._config or self._config[key] in (None, ""):
            raise EquipmentCapabilityError(
                f"{operation} is not available; set `{key}` in bench TOML for adaura-r3",
            )
        return float(self._config[key])

    def measure_min_attenuation_db(self) -> float:
        return self._limit_from_config("min_attenuation_db", "measure_min_attenuation_db")

    def measure_max_attenuation_db(self) -> float:
        return self._limit_from_config("max_attenuation_db", "measure_max_attenuation_db")

    def measure_step_db(self) -> float:
        return self._limit_from_config("step_db", "measure_step_db")

    def wait_settle(self, *, settle_s: float | None = None) -> None:
        wait_settle_s(self._config, settle_s=settle_s)

    def preset(self) -> None:
        self._transport.write("RESET")

    def close(self) -> None:
        self._transport.close()
