from __future__ import annotations

from typing import Any

from colosseum.context import get_context

from colosseum_equipment.transports.base import Transport


def _state_map() -> dict[str, dict[str, Any]]:
    ctx = get_context()
    key = "sim:state"
    if key not in ctx.resource_cache:
        ctx.resource_cache[key] = {}
    state: dict[str, dict[str, Any]] = ctx.resource_cache[key]
    return state


class SimTransport(Transport):
    """In-memory transport for offline tests and CI (driver=sim)."""

    def __init__(self, kind: str, equipment_id: int, config: dict[str, Any]) -> None:
        self.kind = kind
        self.equipment_id = equipment_id
        self.config = config
        states = _state_map()
        run_key = f"{kind}:{equipment_id}"
        if run_key not in states:
            if kind == "serial":
                states[run_key] = {
                    "sim_read": str(config.get("sim_read", "OK")),
                    "rx_offset": 0,
                    "tx_log": [],
                }
            else:
                states[run_key] = {
                    "voltage": float(config.get("voltage", 3.3)),
                    "current_limit": float(config.get("ocp", config.get("current", 1.0))),
                    "output_enabled": False,
                }
        self._state = states[run_key]

    def write_bytes(self, payload: bytes) -> None:
        text = payload.decode("ascii", errors="replace")
        if self.kind == "serial":
            self._state.setdefault("tx_log", []).append(text)
            return
        self.write(text)

    def read_line(self) -> str:
        if self.kind == "serial":
            return self._serial_take_until("\n").strip()
        return self.read()

    def read_until(self, terminator: str | bytes) -> str:
        if self.kind == "serial":
            term = terminator.decode("ascii") if isinstance(terminator, bytes) else terminator
            return self._serial_take_until(term)
        term = terminator.decode("ascii") if isinstance(terminator, bytes) else terminator
        line = self.read_line()
        if term in line:
            return line
        return line

    def _serial_take_until(self, terminator: str) -> str:
        sim_read = str(self._state.get("sim_read", "OK"))
        offset = int(self._state.get("rx_offset", 0))
        if offset >= len(sim_read):
            return ""
        idx = sim_read.find(terminator, offset)
        if idx < 0:
            chunk = sim_read[offset:]
            self._state["rx_offset"] = len(sim_read)
            return chunk
        end = idx + len(terminator)
        chunk = sim_read[offset:end]
        self._state["rx_offset"] = end
        return chunk

    def write(self, data: str) -> None:
        if self.kind == "serial":
            self._state.setdefault("tx_log", []).append(data)
            return
        cmd = data.strip().upper()
        if cmd.startswith("VOLT"):
            parts = cmd.split()
            if len(parts) >= 2:
                self._state["voltage"] = float(parts[-1])
        elif cmd.startswith("CURR"):
            parts = cmd.split()
            if len(parts) >= 2:
                self._state["current_limit"] = float(parts[-1])
        elif cmd in ("OUTP ON", "OUTP 1", "OUTP:STAT ON"):
            self._state["output_enabled"] = True
        elif cmd in ("OUTP OFF", "OUTP 0", "OUTP:STAT OFF"):
            self._state["output_enabled"] = False

    def read(self) -> str:
        return self.query("")

    def query(self, data: str) -> str:
        if self.kind == "serial":
            _ = data
            return self.read_line() or "OK"
        cmd = data.strip().upper()
        voltage = self._read_voltage()
        if cmd in ("VOLT?", "MEAS:VOLT?"):
            return f"{voltage:.6f}"
        if cmd in ("CURR?", "MEAS:CURR?"):
            return f"{self._state['current_limit']:.6f}"
        if cmd in ("READ?", "MEAS?", "MEAS:VOLT:DC?"):
            return f"{voltage:.6E}"
        if cmd.startswith("CONF"):
            return ""
        return "0"

    def _read_voltage(self) -> float:
        if self.kind == "dmm":
            psu_state = _state_map().get("psu:1")
            if psu_state is not None:
                return float(psu_state["voltage"])
        return float(self._state["voltage"])

    def close(self) -> None:
        return None
