"""Catalog models from the programming-manual spreadsheet.

Mini-Circuits Prog_Manual-6 identities are registered in ``minicircuits.py``.
Vaunix LDA identities are registered in ``vaunix.py`` (SDK-only refuse).
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from colosseum_equipment.exceptions import EquipmentCapabilityError, EquipmentResponseError
from colosseum_equipment.instruments.attn.minicircuits import MiniCircuitsAttn
from colosseum_equipment.instruments._settle import wait_settle_s
from colosseum_equipment.instruments.registry import instrument_model

if TYPE_CHECKING:
    from colosseum_equipment.transports.base import Transport

# Native HTTP/Telnet/USB command subset; exact topology comes from bench configuration.

@instrument_model("attn", "minicircuits-rcm-ztm")
class MinicircuitsRcmZtm(MiniCircuitsAttn):
    """Manual: https://minicircuits.com/softwaredownload/Prog_Manual-Multi_Attenuators.pdf"""

    def __init__(self, transport: Transport, config: dict[str, Any]) -> None:
        if "block" not in config:
            raise EquipmentCapabilityError("RCM/ZTM requires an explicit attenuator block (1..99)")
        block = int(config["block"])
        self._block = f"{block:02d}"
        self._channels_per_block = int(config.get("channels_per_block", 4))
        if (
            block != float(config["block"]) or not 1 <= block <= 99
            or self._channels_per_block != float(config.get("channels_per_block", 4))
            or self._channels_per_block not in (4, 8)
        ):
            raise ValueError("block must be 1..99; channels_per_block must be 4 or 8")
        if config.get("channel") in (None, "") and config.get("path") in (None, ""):
            raise EquipmentCapabilityError("RCM/ZTM requires a default channel within its block")
        self._config = config
        self._default_channel = self._configured_channel()
        self._channel(None)
        super().__init__(transport, config)

    def _channel(self, channel: int | None) -> int:
        raw = channel if channel is not None else self._config.get("channel")
        if raw in (None, ""):
            raw = self._config.get("path")
        if raw is None or not float(raw).is_integer():
            raise ValueError("RCM/ZTM channel must be an integer")
        ch = super()._channel(channel)
        if ch is None or not 1 <= ch <= self._channels_per_block:
            raise EquipmentCapabilityError("channel is outside the configured attenuator block")
        return ch

    def _reply(self, command: str) -> str:
        raw = self._transport.query(command).strip()
        prefix = f":{self._block}:"
        if not raw.startswith(prefix) or ":" in raw[len(prefix):]:
            raise EquipmentResponseError(f"invalid RCM/ZTM block reply: {raw!r}")
        return raw[len(prefix):]

    def set_attenuation_db(
        self, attenuation_db: float, *, channel: int | None = None, settle_s: float | None = None,
    ) -> None:
        ch = self._channel(channel)
        if not math.isfinite(attenuation_db) or attenuation_db < 0:
            raise ValueError("attenuation must be finite and nonnegative")
        command = f":{self._block}:CHAN:{ch}:SETATT:{attenuation_db:.3f}"
        status = self._reply(command)
        if status != "1":
            # Status 2 means clamping: the requested attenuation was not applied.
            raise EquipmentResponseError(f"RCM/ZTM attenuation rejected/clamped: status {status!r}")
        wait_settle_s(self._config, settle_s=settle_s)

    def measure_attenuation_db(self, *, channel: int | None = None) -> float:
        ch = self._channel(channel)
        raw = self._reply(f":{self._block}:CHAN:{ch}:ATT?")
        try:
            value = float(raw)
        except ValueError as exc:
            raise EquipmentResponseError(f"invalid RCM/ZTM attenuation {raw!r}") from exc
        if not math.isfinite(value) or value < 0:
            raise EquipmentResponseError(f"invalid RCM/ZTM attenuation {raw!r}")
        return value

    def _configured_limit(self, key: str) -> float:
        if key not in self._config:
            raise EquipmentCapabilityError(f"RCM/ZTM requires {key} from the installed module specification")
        value = float(self._config[key])
        if not math.isfinite(value) or value < 0:
            raise ValueError(f"invalid {key}")
        return value

    def measure_min_attenuation_db(self) -> float:
        return self._configured_limit("min_attenuation_db")

    def measure_max_attenuation_db(self) -> float:
        return self._configured_limit("max_attenuation_db")

    def measure_step_db(self) -> float:
        return self._configured_limit("step_db")

    def preset(self) -> None:
        raise EquipmentCapabilityError("RCM/ZTM has no qualified rack-wide preset in this adapter")
