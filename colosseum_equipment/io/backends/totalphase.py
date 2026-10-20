"""Adapters for locally installed, unmodified Total Phase Python runtimes.

No vendor SDK code or binaries are distributed by this package. The vendor
bindings perform their own native ABI/version negotiation.
"""

from __future__ import annotations

from array import array
from importlib import import_module
from typing import Any

from colosseum.logging import get_logger

from colosseum_equipment.io.backends._usb import (
    Session,
    UsbBackend,
    acquire,
    address,
    checked,
    count,
    size,
    spi_settings,
)
from colosseum_equipment.io.exceptions import IoConfigError, IoConnectionError

_logger = get_logger("colosseum.io")
_MODULES = {"aa": "aardvark_py", "ch": "cheetah_py", "bg": "beagle_py"}


def load_api(prefix: str) -> Any:  # noqa: ANN401
    name = _MODULES[prefix]
    try:
        api = import_module(name)
        if not getattr(api, f"{prefix.upper()}_LIBRARY_LOADED", True):
            raise IoConnectionError(f"{name} reports an incompatible native runtime")
        return api
    except (ImportError, OSError) as exc:
        raise IoConnectionError(
            f"Cannot load {name}. Install the vendor USB driver and matching Python "
            "Software API locally; place its directory on PYTHONPATH. "
            "Vendor SDKs are not included in colosseum-equipment.",
        ) from exc


def open_session(prefix: str, config: dict[str, Any], *, exclusive: bool = False) -> Session:
    resource = str(config.get("resource") or "").replace("-", "")
    if not resource.isdecimal() or not 0 < int(resource) <= 0xFFFFFFFF:
        raise IoConfigError("Total Phase resource must be the numeric device serial number")
    resource = str(int(resource))
    if config.get("library"):
        raise IoConfigError("Total Phase uses the vendor Python API on PYTHONPATH, not library=")
    if config.get("voltage") is not None and float(config["voltage"]) != 3.3:
        raise IoConfigError("these backends do not provide programmable logic voltage")
    power = bool(config.get("target_power", False))
    if prefix == "ch" and "timeout_ms" in config:
        raise IoConfigError("Cheetah batch shift has no configurable timeout_ms")
    timeout = int(config.get("timeout_ms", 500))
    if not 1 <= timeout <= 1000:
        raise IoConfigError("timeout_ms must be 1..1000")

    def _open() -> tuple[Any, int]:
        api = load_api(prefix)
        found, ports, ids = getattr(api, f"{prefix}_find_devices_ext")(256, 256)
        checked(found, f"{prefix}_find_devices_ext")
        if found > 256:
            raise IoConnectionError("Too many USB adapters to enumerate safely")
        matches = [int(p) for p, uid in zip(ports, ids, strict=True) if int(uid) == int(resource)]
        if len(matches) != 1:
            raise IoConnectionError(f"Total Phase serial {resource} was not uniquely found")
        port = matches[0]
        if port & 0x8000:
            raise IoConnectionError(f"Total Phase serial {resource} is already in use")
        handle = checked(getattr(api, f"{prefix}_open")(port), f"{prefix}_open")
        if handle == 0:
            raise IoConnectionError(f"{prefix}_open returned an invalid handle")
        try:
            if prefix == "aa":
                checked(api.aa_configure(handle, api.AA_CONFIG_SPI_I2C), "aa_configure")
                checked(api.aa_target_power(
                    handle, api.AA_TARGET_POWER_BOTH if power else api.AA_TARGET_POWER_NONE,
                ), "aa_target_power")
                checked(api.aa_i2c_bus_timeout(handle, timeout), "aa_i2c_bus_timeout")
            elif prefix == "ch":
                checked(api.ch_target_power(handle, int(power)), "ch_target_power")
            else:
                checked(api.bg_timeout(handle, timeout), "bg_timeout")
                checked(api.bg_latency(handle, min(timeout, 50)), "bg_latency")
        except Exception:
            getattr(api, f"{prefix}_close")(handle)
            raise
        return api, handle

    def _close(api: Any, handle: int) -> None:  # noqa: ANN401
        try:
            if prefix == "aa":
                checked(api.aa_target_power(handle, api.AA_TARGET_POWER_NONE), "aa_target_power")
            elif prefix == "ch":
                checked(api.ch_target_power(handle, 0), "ch_target_power")
            elif checked(api.bg_features(handle), "bg_features") & api.BG_FEATURE_I2C:
                checked(api.bg_target_power(handle, 0), "bg_target_power")
        finally:
            checked(getattr(api, f"{prefix}_close")(handle), f"{prefix}_close")

    settings: tuple[object, ...] = (power, timeout)
    if exclusive:
        settings += (object(),)
    return acquire(prefix, resource, settings, _open, _close)


def _i2c_status(status: int) -> None:
    if status != 0:
        raise IoConnectionError(f"Aardvark I2C failed (bus/NACK status {status:#x})")


class AardvarkI2cBackend(UsbBackend):
    def __init__(self, config: dict[str, Any]) -> None:
        self._address = int(config.get("address", 0x50))
        self._bits = int(config.get("address_bits", 7))
        self._clock = int(config.get("clock_hz", 100_000))
        self._pullup = bool(config.get("pullup", True))
        self._validate(self._address, self._bits, self._clock)
        self._session = open_session("aa", config)
        try:
            with self._session.lock:
                self._apply()
        except Exception:
            self.close()
            raise

    @staticmethod
    def _validate(addr: int, bits: int, clock: int) -> None:
        address(addr, bits)
        if not 1000 <= clock <= 800_000:
            raise IoConfigError("Aardvark I2C clock_hz must be 1000..800000")

    def _apply(self) -> None:
        s = self.session()
        self.actual_clock_hz = checked(
            s.api.aa_i2c_bitrate(s.handle, self._clock // 1000), "aa_i2c_bitrate",
        ) * 1000
        checked(s.api.aa_i2c_pullup(
            s.handle, s.api.AA_I2C_PULLUP_BOTH if self._pullup else s.api.AA_I2C_PULLUP_NONE,
        ), "aa_i2c_pullup")
        _logger.debug("Aardvark I2C actual clock %s Hz", self.actual_clock_hz)

    def configure(
        self, *, address: int | None = None, address_bits: int | None = None,
        clock_hz: int | None = None,
    ) -> None:
        addr = self._address if address is None else address
        bits = self._bits if address_bits is None else address_bits
        clock = self._clock if clock_hz is None else clock_hz
        self._validate(addr, bits, clock)
        with self.session().lock:
            self._address, self._bits, self._clock = addr, bits, clock
            self._apply()

    def set_pullup(self, enabled: bool) -> None:
        with self.session().lock:
            self._pullup = enabled
            self._apply()

    def _flags(self) -> int:
        return int(self.session().api.AA_I2C_10_BIT_ADDR) if self._bits == 10 else 0

    def write(self, data: bytes) -> None:
        size(len(data), 65535)
        with self.session().lock:
            self._apply()
            s = self.session()
            status, written = s.api.aa_i2c_write_ext(
                s.handle, self._address, self._flags(), array("B", data),
            )
            _i2c_status(status)
            count(written, len(data), "aa_i2c_write_ext")

    def read(self, nbytes: int) -> bytes:
        size(nbytes, 65535)
        with self.session().lock:
            self._apply()
            s = self.session()
            status, data, received = s.api.aa_i2c_read_ext(
                s.handle, self._address, self._flags(), nbytes,
            )
            _i2c_status(status)
            count(received, nbytes, "aa_i2c_read_ext")
            count(len(data), nbytes, "aa_i2c_read_ext buffer")
            return bytes(data)

    def write_read(self, write_data: bytes, read_nbytes: int) -> bytes:
        size(len(write_data), 65535)
        size(read_nbytes, 65535)
        with self.session().lock:
            self._apply()
            s = self.session()
            status, written, data, received = s.api.aa_i2c_write_read(
                s.handle, self._address, self._flags(), array("B", write_data), read_nbytes,
            )
            _i2c_status(status)
            count(written, len(write_data), "aa_i2c_write_read write")
            count(received, read_nbytes, "aa_i2c_write_read read")
            count(len(data), read_nbytes, "aa_i2c_write_read buffer")
            return bytes(data)


class TotalPhaseSpiBackend(UsbBackend):
    def __init__(self, config: dict[str, Any], *, cheetah: bool = False) -> None:
        self._cheetah = cheetah
        self._clock = int(config.get("clock_hz", 1_000_000))
        self._mode = int(config.get("mode", 0))
        self._cs = int(config.get("chip_select", 0))
        self._validate(self._clock, self._mode, self._cs, int(config.get("bits_per_word", 8)))
        self._session = open_session("ch" if cheetah else "aa", config)
        try:
            with self._session.lock:
                self._apply()
        except Exception:
            self.close()
            raise

    def _validate(self, clock: int, mode: int, cs: int, bits: int) -> None:
        spi_settings(clock, mode, cs, bits, 2 if self._cheetah else 0)
        minimum, maximum = (100_000, 40_000_000) if self._cheetah else (125_000, 8_000_000)
        if not minimum <= clock <= maximum:
            raise IoConfigError(f"SPI clock_hz must be {minimum}..{maximum}")

    def _apply(self) -> None:
        s = self.session()
        if self._cheetah:
            checked(s.api.ch_spi_configure(
                s.handle, self._mode >> 1, self._mode & 1, s.api.CH_SPI_BITORDER_MSB, 0,
            ), "ch_spi_configure")
            rate = s.api.ch_spi_bitrate(s.handle, self._clock // 1000)
        else:
            checked(s.api.aa_spi_configure(
                s.handle, self._mode >> 1, self._mode & 1, s.api.AA_SPI_BITORDER_MSB,
            ), "aa_spi_configure")
            rate = s.api.aa_spi_bitrate(s.handle, self._clock // 1000)
        self.actual_clock_hz = checked(rate, "SPI bitrate") * 1000
        _logger.debug("Total Phase SPI actual clock %s Hz", self.actual_clock_hz)

    def configure(
        self, *, clock_hz: int | None = None, mode: int | None = None,
        chip_select: int | None = None, bits_per_word: int | None = None,
    ) -> None:
        clock = self._clock if clock_hz is None else clock_hz
        selected_mode = self._mode if mode is None else mode
        cs = self._cs if chip_select is None else chip_select
        self._validate(clock, selected_mode, cs, 8 if bits_per_word is None else bits_per_word)
        with self.session().lock:
            self._clock, self._mode, self._cs = clock, selected_mode, cs
            self._apply()

    def transfer(self, data: bytes) -> bytes:
        # Aardvark's full-duplex host buffer is approximately 4 KiB, despite
        # the API's u16 length parameter. Cheetah supports a full u16 batch.
        size(len(data), 65535 if self._cheetah else 4096)
        with self.session().lock:
            self._apply()
            s = self.session()
            if not data:
                return b""
            if not self._cheetah:
                received, reply = s.api.aa_spi_write(s.handle, array("B", data), len(data))
            else:
                checked(s.api.ch_spi_queue_clear(s.handle), "ch_spi_queue_clear")
                try:
                    checked(s.api.ch_spi_queue_oe(s.handle, 1), "ch_spi_queue_oe")
                    checked(s.api.ch_spi_queue_ss(s.handle, 1 << self._cs), "ch_spi_queue_ss")
                    count(s.api.ch_spi_queue_array(s.handle, array("B", data)),
                          len(data), "ch_spi_queue_array")
                    checked(s.api.ch_spi_queue_ss(s.handle, 0), "ch_spi_queue_ss")
                    checked(s.api.ch_spi_queue_oe(s.handle, 0), "ch_spi_queue_oe")
                    received, reply = s.api.ch_spi_batch_shift(s.handle, len(data))
                finally:
                    # A failed shift can leave SS asserted. Send an explicit release.
                    checked(s.api.ch_spi_queue_clear(s.handle), "ch_spi_queue_clear")
                    checked(s.api.ch_spi_queue_ss(s.handle, 0), "ch_spi_queue_ss")
                    checked(s.api.ch_spi_queue_oe(s.handle, 0), "ch_spi_queue_oe")
                    result, _ = s.api.ch_spi_batch_shift(s.handle, 0)
                    checked(result, "ch_spi_batch_shift release")
                    checked(s.api.ch_spi_queue_clear(s.handle), "ch_spi_queue_clear")
            count(received, len(data), "SPI transfer")
            count(len(reply), len(data), "SPI transfer buffer")
            return bytes(reply)
