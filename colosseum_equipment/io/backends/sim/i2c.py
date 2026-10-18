"""In-memory I2C master for offline runs and unit tests."""

from __future__ import annotations

from colosseum.context import get_context

from colosseum_equipment.io.exceptions import IoConfigError, IoConnectionError

_SIM_STATE_KEY = "io:sim:state"


def _state_key(i2c_id: int) -> str:
    return f"i2c:{i2c_id}"


class SimI2cBackend:
    """Simulated I2C master with optional NACK injection."""

    def __init__(
        self,
        *,
        i2c_id: int,
        address: int = 0x50,
        address_bits: int = 7,
        clock_hz: int = 100_000,
        pullup: bool = True,
        nack: bool = False,
        read_data: bytes = b"",
    ) -> None:
        self._i2c_id = i2c_id
        self._address = int(address)
        self._address_bits = int(address_bits)
        self._clock_hz = int(clock_hz)
        self._pullup = bool(pullup)
        self._nack = bool(nack)
        self._read_data = bytes(read_data)
        self._last_write = b""

    def _persist(self) -> None:
        ctx = get_context()
        state = ctx.resource_cache.setdefault(_SIM_STATE_KEY, {})
        state[_state_key(self._i2c_id)] = {
            "address": self._address,
            "address_bits": self._address_bits,
            "clock_hz": self._clock_hz,
            "pullup": self._pullup,
            "nack": self._nack,
            "read_data": self._read_data,
            "last_write": self._last_write,
        }

    @classmethod
    def from_cache(cls, *, i2c_id: int, config: dict) -> SimI2cBackend:
        ctx = get_context()
        state = ctx.resource_cache.setdefault(_SIM_STATE_KEY, {})
        key = _state_key(i2c_id)
        nack = bool(config.get("nack", False))
        read_raw = config.get("read_data", b"")
        if isinstance(read_raw, str):
            read_data = bytes.fromhex(read_raw.replace(" ", ""))
        else:
            read_data = bytes(read_raw or b"")
        if key not in state:
            backend = cls(
                i2c_id=i2c_id,
                address=int(config.get("address", 0x50)),
                address_bits=int(config.get("address_bits", 7)),
                clock_hz=int(config.get("clock_hz", 100_000)),
                pullup=bool(config.get("pullup", True)),
                nack=nack,
                read_data=read_data,
            )
            backend._persist()
            return backend
        entry = state[key]
        backend = cls(
            i2c_id=i2c_id,
            address=entry["address"],
            address_bits=entry["address_bits"],
            clock_hz=entry["clock_hz"],
            pullup=entry["pullup"],
            nack=entry.get("nack", nack),
            read_data=entry.get("read_data", read_data),
        )
        backend._last_write = entry.get("last_write", b"")
        return backend

    def _raise_if_nack(self) -> None:
        if self._nack:
            raise IoConnectionError("sim I2C NACK (address not acknowledged)")

    def configure(
        self,
        *,
        address: int | None = None,
        address_bits: int | None = None,
        clock_hz: int | None = None,
    ) -> None:
        if address is not None:
            self._address = int(address)
        if address_bits is not None:
            if address_bits not in (7, 10):
                raise IoConfigError(f"i2c address_bits must be 7 or 10; got {address_bits}")
            self._address_bits = int(address_bits)
        if clock_hz is not None:
            if clock_hz <= 0:
                raise IoConfigError(f"i2c clock_hz must be positive; got {clock_hz}")
            self._clock_hz = int(clock_hz)
        self._persist()

    def set_pullup(self, enabled: bool) -> None:
        self._pullup = bool(enabled)
        self._persist()

    def write(self, data: bytes) -> None:
        self._raise_if_nack()
        self._last_write = bytes(data)
        self._persist()

    def read(self, nbytes: int) -> bytes:
        self._raise_if_nack()
        n = int(nbytes)
        if n < 0:
            raise IoConfigError(f"i2c read nbytes must be >= 0; got {nbytes}")
        if n > len(self._read_data):
            # Pad with zeros so tests can request more than configured.
            return self._read_data + bytes(n - len(self._read_data))
        return self._read_data[:n]

    def write_read(self, write_data: bytes, read_nbytes: int) -> bytes:
        self.write(write_data)
        return self.read(read_nbytes)

    def close(self) -> None:
        return None
