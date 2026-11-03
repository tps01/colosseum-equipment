"""In-memory 1-Wire master for offline runs and unit tests."""

from __future__ import annotations

from typing import Any

from colosseum.context import get_context

from colosseum_equipment.io.backends.ds2480b import hex_to_rom, rom_to_hex
from colosseum_equipment.io.exceptions import IoConfigError, IoConnectionError

_SIM_STATE_KEY = "io:sim:state"


def _state_key(onewire_id: int) -> str:
    return f"onewire:{onewire_id}"


class SimOneWireBackend:
    """Simulated 1-Wire bus with configurable ROMs and read data."""

    def __init__(
        self,
        *,
        onewire_id: int,
        presence: bool = True,
        roms: list[str] | None = None,
        read_data: bytes = b"",
        speed: str = "standard",
    ) -> None:
        self._onewire_id = onewire_id
        self._presence = bool(presence)
        self._roms = list(roms or [])
        self._read_data = bytes(read_data)
        self._speed = speed
        self._selected: str | None = None
        self._last_write = b""
        self._cursor = 0

    def _persist(self) -> None:
        ctx = get_context()
        state = ctx.resource_cache.setdefault(_SIM_STATE_KEY, {})
        state[_state_key(self._onewire_id)] = {
            "presence": self._presence,
            "roms": list(self._roms),
            "read_data": self._read_data,
            "speed": self._speed,
            "selected": self._selected,
            "last_write": self._last_write,
            "cursor": self._cursor,
        }

    @classmethod
    def from_cache(cls, *, onewire_id: int, config: dict[str, Any]) -> SimOneWireBackend:
        ctx = get_context()
        state = ctx.resource_cache.setdefault(_SIM_STATE_KEY, {})
        key = _state_key(onewire_id)
        raw_roms = config.get("roms") or config.get("devices") or []
        if isinstance(raw_roms, str):
            roms = [p.strip() for p in raw_roms.split(",") if p.strip()]
        else:
            roms = [str(item).strip() for item in raw_roms]
        read_raw = config.get("read_data", b"")
        if isinstance(read_raw, str):
            read_data = bytes.fromhex(read_raw.replace(" ", "")) if read_raw else b""
        else:
            read_data = bytes(read_raw or b"")
        presence = bool(config.get("presence", True))
        speed = str(config.get("speed") or "standard")
        if key not in state:
            backend = cls(
                onewire_id=onewire_id,
                presence=presence,
                roms=roms,
                read_data=read_data,
                speed=speed,
            )
            backend._persist()
            return backend
        entry = state[key]
        backend = cls(
            onewire_id=onewire_id,
            presence=entry["presence"],
            roms=list(entry["roms"]),
            read_data=entry["read_data"],
            speed=entry["speed"],
        )
        backend._selected = entry.get("selected")
        backend._last_write = entry.get("last_write", b"")
        backend._cursor = int(entry.get("cursor", 0))
        return backend

    def close(self) -> None:
        return None

    def configure(self, *, speed: str | None = None) -> dict[str, Any]:
        if speed is not None:
            name = speed.strip().lower()
            if name not in ("standard", "overdrive"):
                raise IoConfigError("onewire speed must be 'standard' or 'overdrive'")
            self._speed = name
        self._persist()
        return {
            "port": "(sim)",
            "baudrate": 9600,
            "timeout_s": 1.0,
            "speed": self._speed,
            "driver": "sim",
        }

    def reset(self, *, required: bool = False) -> bool:
        self._selected = None
        self._cursor = 0
        self._persist()
        if required and not self._presence:
            raise IoConnectionError("no 1-Wire presence pulse detected")
        return self._presence

    def search(self) -> list[str]:
        if not self.reset():
            return []
        return list(self._roms)

    def select(self, rom: str | bytes | None = None) -> None:
        if not self.reset(required=True):
            raise IoConnectionError("no 1-Wire presence pulse detected")
        raw = hex_to_rom(rom)
        if raw is None:
            if len(self._roms) > 1:
                raise IoConnectionError("SKIP ROM requires a single-drop bus")
            self._selected = self._roms[0] if self._roms else None
            self._persist()
            return
        hex_rom = rom_to_hex(raw)
        if self._roms and hex_rom not in self._roms:
            raise IoConnectionError(f"1-Wire ROM {hex_rom} not present on simulated bus")
        self._selected = hex_rom
        self._persist()

    def write(self, data: bytes) -> None:
        self._last_write = bytes(data)
        self._persist()

    def read(self, nbytes: int) -> bytes:
        if nbytes < 0:
            raise IoConfigError("nbytes must be >= 0")
        chunk = self._read_data[self._cursor : self._cursor + nbytes]
        if len(chunk) < nbytes:
            chunk = chunk + bytes(nbytes - len(chunk))
        self._cursor += nbytes
        self._persist()
        return chunk

    def write_read(self, write_data: bytes, read_nbytes: int) -> bytes:
        self.write(write_data)
        return self.read(read_nbytes)
