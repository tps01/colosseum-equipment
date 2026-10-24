"""Mini-Circuits RUDAT/RCDAT/RC4DAT/RC8DAT/ZVVA programmable attenuators.

Manual: Prog_Manual-6-Programmable_Attenuator —
``:SETATT=[Att]``, ``:CHAN:[n]:SETATT:[Att]``, ``:ATT?``.
https://www.minicircuits.com/softwaredownload/Prog_Manual-6-Programmable_Attenuator.pdf
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from colosseum_equipment.exceptions import EquipmentCapabilityError, EquipmentResponseError
from colosseum_equipment.instruments._settle import wait_settle_s
from colosseum_equipment.instruments.attn._limits import float_from_config_or_scpi
from colosseum_equipment.instruments.registry import instrument_model
from colosseum_equipment.protocols.scpi import SCPIHelper

if TYPE_CHECKING:
    from colosseum_equipment.transports.base import Transport

_OPTIONAL = (
    "attenuation_db",
    "channel",
    "path",
    "port",
    "min_attenuation_db",
    "max_attenuation_db",
    "step_db",
    "settle_s",
)


@instrument_model(
    "attn",
    "minicircuits-rudat",
    "minicircuits-rcdat",
    "minicircuits-rc4dat",
    "minicircuits-rc8dat",
    "minicircuits-zvva",
    extra_optional=_OPTIONAL,
    address="either",
)
class MiniCircuitsAttn:
    """Prog_Manual-6 SETATT dialect (status reply on set; space-separated ATT?)."""

    def __init__(self, transport: Transport, config: dict[str, Any]) -> None:
        self._transport = transport
        self._scpi = SCPIHelper(transport)
        self._config = config
        self._model = str(config.get("model", "minicircuits-rudat")).lower()
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

    def _expect_set_status(self, response: str, command: str) -> None:
        token = response.strip().split()[0] if response.strip() else ""
        if token not in {"1", "2"}:
            raise EquipmentResponseError(
                f"Mini-Circuits attenuator rejected {command!r}: {response!r}",
            )

    def set_attenuation_db(
        self,
        attenuation_db: float,
        *,
        channel: int | None = None,
        settle_s: float | None = None,
    ) -> None:
        ch = self._channel(channel)
        if ch is None:
            cmd = f":SETATT={attenuation_db:.3f}"
        else:
            cmd = f":CHAN:{ch}:SETATT:{attenuation_db:.3f}"
        self._expect_set_status(self._transport.query(cmd), cmd)
        wait_settle_s(self._config, settle_s=settle_s)

    def measure_attenuation_db(self, *, channel: int | None = None) -> float:
        ch = self._channel(channel)
        raw = self._transport.query(":ATT?").strip()
        parts = raw.split()
        if not parts:
            raise EquipmentResponseError(f"empty ATT? reply: {raw!r}")
        if ch is None:
            if len(parts) != 1:
                raise EquipmentCapabilityError(
                    f"{self._model} ATT? returned {len(parts)} channels; "
                    "pass channel= for multi-channel models",
                )
            return float(parts[0])
        if ch < 1 or ch > len(parts):
            raise EquipmentCapabilityError(
                f"{self._model} has no channel {ch} in ATT? reply ({raw!r})",
            )
        return float(parts[ch - 1])

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
        self._transport.write("*RST")

    def close(self) -> None:
        self._transport.close()
