from __future__ import annotations

from typing import TYPE_CHECKING, Any

from colosseum_equipment.instruments._base import ScpiInstrumentMixin
from colosseum_equipment.instruments._settle import wait_settle_s
from colosseum_equipment.instruments.attn._limits import float_from_config_or_scpi
from colosseum_equipment.instruments.registry import best_effort_commands, instrument_model
from colosseum_equipment.protocols.scpi import SCPIHelper

if TYPE_CHECKING:
    from colosseum_equipment.transports.base import Transport

_ATTN_OPTIONAL = (
    "attenuation_db",
    "channel",
    "path",
    "port",
    "min_attenuation_db",
    "max_attenuation_db",
    "step_db",
    "settle_s",
)


@instrument_model("attn", "generic", extra_optional=_ATTN_OPTIONAL, address="either")
@best_effort_commands
class GenericAttn(ScpiInstrumentMixin):
    """Generic SCPI digital step attenuator (best-effort ``ATT`` commands)."""

    def __init__(self, transport: Transport, config: dict[str, Any]) -> None:
        self._scpi = SCPIHelper(transport)
        self._config = config
        self._default_channel = self._configured_channel()
        if "attenuation_db" in config:
            self.set_attenuation_db(float(config["attenuation_db"]))

    def _configured_channel(self) -> int | None:
        if "channel" in self._config and self._config["channel"] not in (None, ""):
            return int(self._config["channel"])
        if "path" in self._config and self._config["path"] not in (None, ""):
            return int(self._config["path"])
        return None

    def _channel(self, channel: int | None) -> int | None:
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
        if ch is None:
            self._scpi.write(f"ATT {attenuation_db:.3f}")
        else:
            self._scpi.write(f"ATT {ch},{attenuation_db:.3f}")
        wait_settle_s(self._config, settle_s=settle_s)

    def measure_attenuation_db(self, *, channel: int | None = None) -> float:
        ch = self._channel(channel)
        if ch is None:
            return self._scpi.query_float("ATT?")
        return self._scpi.query_float(f"ATT? {ch}")

    def measure_min_attenuation_db(self) -> float:
        return float_from_config_or_scpi(
            self._config,
            "min_attenuation_db",
            self._scpi,
            "ATT:MIN?",
            "MIN?",
            operation="measure_min_attenuation_db",
        )

    def measure_max_attenuation_db(self) -> float:
        return float_from_config_or_scpi(
            self._config,
            "max_attenuation_db",
            self._scpi,
            "ATT:MAX?",
            "MAX?",
            operation="measure_max_attenuation_db",
        )

    def measure_step_db(self) -> float:
        return float_from_config_or_scpi(
            self._config,
            "step_db",
            self._scpi,
            "ATT:STEP?",
            "STEP?",
            operation="measure_step_db",
        )

    def wait_settle(self, *, settle_s: float | None = None) -> None:
        wait_settle_s(self._config, settle_s=settle_s)

    def preset(self) -> None:
        self._scpi.write("*RST")
