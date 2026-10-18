"""NI USB-845x SPI master via NI-845x."""

from __future__ import annotations

from ctypes import byref, c_uint32, create_string_buffer

from colosseum_equipment.io.backends.ni import ni845x as api
from colosseum_equipment.io.backends.ni import session845x
from colosseum_equipment.io.backends.ni.models import check_spi_clock, resolve_voltage
from colosseum_equipment.io.exceptions import IoConfigError


def _mode_polarity_phase(mode: int) -> tuple[int, int]:
    if mode not in (0, 1, 2, 3):
        raise IoConfigError(f"spi mode must be 0..3; got {mode}")
    # Mode: CPOL = mode >> 1, CPHA = mode & 1
    cpol = (
        api.kNi845xSpiClockPolarityIdleHigh
        if mode >> 1
        else api.kNi845xSpiClockPolarityIdleLow
    )
    cpha = (
        api.kNi845xSpiClockPhaseSecondEdge
        if mode & 1
        else api.kNi845xSpiClockPhaseFirstEdge
    )
    return cpol, cpha


class Ni845xSpiBackend:
    """USB-845x SPI master (basic WriteRead; no scripting / streaming / slave)."""

    def __init__(
        self,
        *,
        resource: str,
        model: str,
        voltage: float | None = 3.3,
        clock_hz: int = 1_000_000,
        mode: int = 0,
        chip_select: int = 0,
        bits_per_word: int = 8,
        library: str | None = None,
    ) -> None:
        self._model = model
        self._voltage = resolve_voltage(model, voltage)
        self._clock_hz = check_spi_clock(model, clock_hz)
        self._mode = int(mode)
        _mode_polarity_phase(self._mode)
        self._chip_select = int(chip_select)
        if self._chip_select < 0 or self._chip_select > 7:
            raise IoConfigError(f"spi chip_select must be 0..7; got {chip_select}")
        self._bits_per_word = int(bits_per_word)
        if self._bits_per_word < 1 or self._bits_per_word > 32:
            raise IoConfigError(f"spi bits_per_word must be 1..32; got {bits_per_word}")
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
                    session.lib.ni845xSpiConfigurationOpen(byref(self._config)),
                    action="SpiConfigurationOpen",
                )
                self._apply_config(session)
        except Exception:
            self._close_config()
            session845x.release_session(self._session)
            raise

    def _apply_config(self, session: session845x._Session) -> None:
        lib = session.lib
        cpol, cpha = _mode_polarity_phase(self._mode)
        clock_khz = max(1, self._clock_hz // 1000)
        api.check_status(
            lib,
            lib.ni845xSpiConfigurationSetChipSelect(self._config, self._chip_select),
            action="SpiConfigurationSetChipSelect",
        )
        api.check_status(
            lib,
            lib.ni845xSpiConfigurationSetClockRate(self._config, clock_khz),
            action="SpiConfigurationSetClockRate",
        )
        api.check_status(
            lib,
            lib.ni845xSpiConfigurationSetClockPolarity(self._config, cpol),
            action="SpiConfigurationSetClockPolarity",
        )
        api.check_status(
            lib,
            lib.ni845xSpiConfigurationSetClockPhase(self._config, cpha),
            action="SpiConfigurationSetClockPhase",
        )
        api.check_status(
            lib,
            lib.ni845xSpiConfigurationSetNumBitsPerSample(
                self._config, self._bits_per_word,
            ),
            action="SpiConfigurationSetNumBitsPerSample",
        )

    def configure(
        self,
        *,
        clock_hz: int | None = None,
        mode: int | None = None,
        chip_select: int | None = None,
        bits_per_word: int | None = None,
    ) -> None:
        if clock_hz is not None:
            self._clock_hz = check_spi_clock(self._model, clock_hz)
        if mode is not None:
            _mode_polarity_phase(int(mode))
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
        with session845x.locked(self._session) as session:
            self._apply_config(session)

    def transfer(self, data: bytes) -> bytes:
        payload = bytes(data)
        n = len(payload)
        wbuf = create_string_buffer(payload) if n else create_string_buffer(1)
        rbuf = create_string_buffer(n) if n else create_string_buffer(1)
        read_size = c_uint32(n)
        with session845x.locked(self._session) as session:
            api.check_status(
                session.lib,
                session.lib.ni845xSpiWriteRead(
                    session.handle,
                    self._config,
                    n,
                    wbuf if n else None,
                    byref(read_size),
                    rbuf if n else None,
                ),
                action="SpiWriteRead",
            )
        out_n = min(n, int(read_size.value))
        return rbuf.raw[:out_n] if out_n else b""

    def _close_config(self) -> None:
        if self._config:
            try:
                self._session.lib.ni845xSpiConfigurationClose(self._config)
            except Exception:  # noqa: BLE001
                pass
            self._config = api.NiHandle()

    def close(self) -> None:
        try:
            self._close_config()
        finally:
            session845x.release_session(self._session)
