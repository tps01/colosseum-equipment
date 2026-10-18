from __future__ import annotations

from typing import TYPE_CHECKING, Any

from colosseum_equipment.instruments._base import ScpiInstrumentMixin
from colosseum_equipment.instruments._settle import wait_settle_s as _sleep_settle
from colosseum_equipment.instruments.registry import best_effort_commands, instrument_model
from colosseum_equipment.protocols.scpi import SCPIHelper

if TYPE_CHECKING:
    from colosseum_equipment.transports.base import Transport


@instrument_model(
    "rfswitch",
    "generic",
    extra_optional=("path", "port", "settle_s", "wait_settle_s"),
    address="either",
)
@best_effort_commands
class GenericRfSwitch(ScpiInstrumentMixin):
    _model = "generic"
    """Generic SCPI RF switch matrix (preset path names in bench config)."""

    def __init__(self, transport: Transport, config: dict[str, Any]) -> None:
        self._scpi = SCPIHelper(transport)
        self._config = config
        self._model = str(config.get("model", "generic")).lower()
        if "path" in config:
            self.set_path(str(config["path"]))

    def set_path(self, path: str, *, wait_settle_s: float | None = None) -> None:
        self._scpi.write(f"ROUT:PATH {path}")
        _sleep_settle(self._config, settle_s=wait_settle_s)

    def set_switch(
        self,
        switch: str,
        state: int,
        *,
        wait_settle_s: float | None = None,
    ) -> None:
        channel = switch.strip()
        if int(state):
            self._scpi.write(f"ROUT:CLOS (@{channel})")
        else:
            self._scpi.write(f"ROUT:OPEN (@{channel})")
        _sleep_settle(self._config, settle_s=wait_settle_s)

    def measure_path(self) -> str:
        return self._scpi.query("ROUT:PATH?").strip()

    def wait_settle(self, *, settle_s: float | None = None) -> None:
        _sleep_settle(self._config, settle_s=settle_s)

    def preset(self) -> None:
        self._scpi.write("*RST")
