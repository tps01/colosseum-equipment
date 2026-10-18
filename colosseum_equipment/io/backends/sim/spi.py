"""In-memory SPI master for offline runs and unit tests."""

from __future__ import annotations

from colosseum.context import get_context

from colosseum_equipment.io.exceptions import IoConfigError

_SIM_STATE_KEY = "io:sim:state"


def _state_key(spi_id: int) -> str:
    return f"spi:{spi_id}"


class SimSpiBackend:
    """Simulated SPI master; echo by default, or return configured read_data."""

    def __init__(
        self,
        *,
        spi_id: int,
        clock_hz: int = 1_000_000,
        mode: int = 0,
        chip_select: int = 0,
        bits_per_word: int = 8,
        read_data: bytes | None = None,
    ) -> None:
        self._spi_id = spi_id
        self._clock_hz = int(clock_hz)
        self._mode = int(mode)
        self._chip_select = int(chip_select)
        self._bits_per_word = int(bits_per_word)
        self._read_data = None if read_data is None else bytes(read_data)
        self._last_write = b""

    def _persist(self) -> None:
        ctx = get_context()
        state = ctx.resource_cache.setdefault(_SIM_STATE_KEY, {})
        state[_state_key(self._spi_id)] = {
            "clock_hz": self._clock_hz,
            "mode": self._mode,
            "chip_select": self._chip_select,
            "bits_per_word": self._bits_per_word,
            "read_data": self._read_data,
            "last_write": self._last_write,
        }

    @classmethod
    def from_cache(cls, *, spi_id: int, config: dict) -> SimSpiBackend:
        ctx = get_context()
        state = ctx.resource_cache.setdefault(_SIM_STATE_KEY, {})
        key = _state_key(spi_id)
        read_raw = config.get("read_data")
        if isinstance(read_raw, str):
            read_data: bytes | None = bytes.fromhex(read_raw.replace(" ", ""))
        elif read_raw is None:
            read_data = None
        else:
            read_data = bytes(read_raw)
        if key not in state:
            backend = cls(
                spi_id=spi_id,
                clock_hz=int(config.get("clock_hz", 1_000_000)),
                mode=int(config.get("mode", 0)),
                chip_select=int(config.get("chip_select", 0)),
                bits_per_word=int(config.get("bits_per_word", 8)),
                read_data=read_data,
            )
            backend._persist()
            return backend
        entry = state[key]
        backend = cls(
            spi_id=spi_id,
            clock_hz=entry["clock_hz"],
            mode=entry["mode"],
            chip_select=entry["chip_select"],
            bits_per_word=entry["bits_per_word"],
            read_data=entry.get("read_data", read_data),
        )
        backend._last_write = entry.get("last_write", b"")
        return backend

    def configure(
        self,
        *,
        clock_hz: int | None = None,
        mode: int | None = None,
        chip_select: int | None = None,
        bits_per_word: int | None = None,
    ) -> None:
        if clock_hz is not None:
            if clock_hz <= 0:
                raise IoConfigError(f"spi clock_hz must be positive; got {clock_hz}")
            self._clock_hz = int(clock_hz)
        if mode is not None:
            if mode not in (0, 1, 2, 3):
                raise IoConfigError(f"spi mode must be 0..3; got {mode}")
            self._mode = int(mode)
        if chip_select is not None:
            cs = int(chip_select)
            if cs < 0 or cs > 7:
                raise IoConfigError(f"spi chip_select must be 0..7; got {chip_select}")
            self._chip_select = cs
        if bits_per_word is not None:
            bpw = int(bits_per_word)
            if bpw < 1 or bpw > 32:
                raise IoConfigError(f"spi bits_per_word must be 1..32; got {bits_per_word}")
            self._bits_per_word = bpw
        self._persist()

    def transfer(self, data: bytes) -> bytes:
        payload = bytes(data)
        self._last_write = payload
        self._persist()
        if self._read_data is None:
            return payload
        n = len(payload)
        if n <= len(self._read_data):
            return self._read_data[:n]
        return self._read_data + bytes(n - len(self._read_data))

    def close(self) -> None:
        return None
