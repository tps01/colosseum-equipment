"""NI USB-845x I2C master via NI-845x."""

from __future__ import annotations

from ctypes import byref, create_string_buffer

from colosseum_equipment.io.backends.ni import ni845x as api
from colosseum_equipment.io.backends.ni import session845x
from colosseum_equipment.io.backends.ni.models import check_i2c_clock, resolve_voltage
from colosseum_equipment.io.exceptions import IoConfigError


class Ni845xI2cBackend:
    """USB-845x I2C master (basic API; no scripting / slave mode)."""

    def __init__(
        self,
        *,
        resource: str,
        model: str,
        voltage: float | None = 3.3,
        clock_hz: int = 100_000,
        address: int = 0x50,
        address_bits: int = 7,
        pullup: bool = True,
        library: str | None = None,
    ) -> None:
        self._model = model
        self._voltage = resolve_voltage(model, voltage)
        self._clock_hz = check_i2c_clock(model, clock_hz)
        self._address = int(address)
        if address_bits not in (7, 10):
            raise IoConfigError(f"i2c address_bits must be 7 or 10; got {address_bits}")
        self._address_bits = int(address_bits)
        self._pullup = bool(pullup)
        self._session = session845x.acquire_session(
            resource=resource,
            voltage=self._voltage,
            library=library,
        )
        self._config = api.NiHandle()
        try:
            with session845x.locked(self._session) as session:
                api.check_status(
                    session.lib,
                    session.lib.ni845xI2cConfigurationOpen(byref(self._config)),
                    action="I2cConfigurationOpen",
                )
                self._apply_config(session)
                api.check_status(
                    session.lib,
                    session.lib.ni845xI2cSetPullupEnable(
                        session.handle, 1 if self._pullup else 0,
                    ),
                    action="I2cSetPullupEnable",
                )
        except Exception:
            self._close_config()
            session845x.release_session(self._session)
            raise

    def _apply_config(self, session: session845x._Session) -> None:
        lib = session.lib
        size = (
            api.kNi845xI2cAddress7Bit
            if self._address_bits == 7
            else api.kNi845xI2cAddress10Bit
        )
        clock_khz = max(1, self._clock_hz // 1000)
        api.check_status(
            lib,
            lib.ni845xI2cConfigurationSetAddressSize(self._config, size),
            action="I2cConfigurationSetAddressSize",
        )
        api.check_status(
            lib,
            lib.ni845xI2cConfigurationSetAddress(self._config, self._address),
            action="I2cConfigurationSetAddress",
        )
        api.check_status(
            lib,
            lib.ni845xI2cConfigurationSetClockRate(self._config, clock_khz),
            action="I2cConfigurationSetClockRate",
        )

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
            self._clock_hz = check_i2c_clock(self._model, clock_hz)
        with session845x.locked(self._session) as session:
            self._apply_config(session)

    def set_pullup(self, enabled: bool) -> None:
        self._pullup = bool(enabled)
        with session845x.locked(self._session) as session:
            api.check_status(
                session.lib,
                session.lib.ni845xI2cSetPullupEnable(
                    session.handle, 1 if self._pullup else 0,
                ),
                action="I2cSetPullupEnable",
            )

    def write(self, data: bytes) -> None:
        payload = bytes(data)
        buf = create_string_buffer(payload) if payload else None
        with session845x.locked(self._session) as session:
            api.check_status(
                session.lib,
                session.lib.ni845xI2cWrite(
                    session.handle,
                    self._config,
                    len(payload),
                    buf,
                ),
                action="I2cWrite",
            )

    def read(self, nbytes: int) -> bytes:
        n = int(nbytes)
        if n < 0:
            raise IoConfigError(f"i2c read nbytes must be >= 0; got {nbytes}")
        buf = create_string_buffer(n) if n else create_string_buffer(1)
        with session845x.locked(self._session) as session:
            api.check_status(
                session.lib,
                session.lib.ni845xI2cRead(
                    session.handle,
                    self._config,
                    n,
                    buf if n else None,
                ),
                action="I2cRead",
            )
        return buf.raw[:n] if n else b""

    def write_read(self, write_data: bytes, read_nbytes: int) -> bytes:
        payload = bytes(write_data)
        n = int(read_nbytes)
        if n < 0:
            raise IoConfigError(f"i2c write_read read_nbytes must be >= 0; got {read_nbytes}")
        wbuf = create_string_buffer(payload) if payload else None
        rbuf = create_string_buffer(n) if n else create_string_buffer(1)
        with session845x.locked(self._session) as session:
            api.check_status(
                session.lib,
                session.lib.ni845xI2cWriteRead(
                    session.handle,
                    self._config,
                    len(payload),
                    wbuf,
                    n,
                    rbuf if n else None,
                ),
                action="I2cWriteRead",
            )
        return rbuf.raw[:n] if n else b""

    def _close_config(self) -> None:
        if self._config:
            try:
                self._session.lib.ni845xI2cConfigurationClose(self._config)
            except Exception:  # noqa: BLE001
                pass
            self._config = api.NiHandle()

    def close(self) -> None:
        try:
            self._close_config()
        finally:
            session845x.release_session(self._session)
