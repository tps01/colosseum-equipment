"""Mini-Circuits RC / ZTRC mechanical switch (ASCII SCPI).

Manual: Prog_Manual-2-Switch — ``SET[switch]=[state]``, ``SETP=[states]``, ``SWPORT?``.
Catalog: https://www.minicircuits.com/softwaredownload/Prog_Manual-2-Switch.pdf
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from colosseum_equipment.instruments._settle import wait_settle_s as _sleep_settle
from colosseum_equipment.instruments.registry import instrument_model
from colosseum_equipment.instruments.rfswitch._normalize import normalize_switch_path

if TYPE_CHECKING:
    from colosseum_equipment.transports.base import Transport


@instrument_model(
    "rfswitch",
    "minicircuits-rc",
    "minicircuits-ztrc",
    extra_optional=("path", "settle_s", "wait_settle_s"),
)
class MiniCircuitsRcSwitch:
    def __init__(self, transport: Transport, config: dict[str, Any]) -> None:
        self._transport = transport
        self._config = config
        if "path" in config:
            self.set_path(str(config["path"]))

    def _expect_ok(self, response: str, command: str) -> None:
        if response.strip() != "1":
            raise RuntimeError(f"Mini-Circuits command failed: {command!r} -> {response!r}")

    def set_switch(
        self,
        switch: str,
        state: int,
        *,
        wait_settle_s: float | None = None,
    ) -> None:
        letter = switch.strip().upper()[:1]
        cmd = f"SET{letter}={int(state)}"
        self._expect_ok(self._transport.query(cmd), cmd)
        _sleep_settle(self._config, settle_s=wait_settle_s)

    def set_path(self, path: str, *, wait_settle_s: float | None = None) -> None:
        path = path.strip()
        if path.upper().startswith("SETP="):
            cmd = path if path.upper().startswith("SETP=") else f"SETP={path.split('=', 1)[1]}"
            self._expect_ok(self._transport.query(cmd), cmd)
            _sleep_settle(self._config, settle_s=wait_settle_s)
            return
        for segment in path.split(";"):
            segment = segment.strip()
            if not segment or "=" not in segment:
                continue
            switch, _, value = segment.partition("=")
            self.set_switch(switch, int(value), wait_settle_s=0)
        _sleep_settle(self._config, settle_s=wait_settle_s)

    def measure_path(self) -> str:
        raw = self._transport.query("SWPORT?").strip()
        return normalize_switch_path(raw)

    def wait_settle(self, *, settle_s: float | None = None) -> None:
        _sleep_settle(self._config, settle_s=settle_s)

    def preset(self) -> None:
        self._transport.write("*RST")

    def close(self) -> None:
        self._transport.close()
