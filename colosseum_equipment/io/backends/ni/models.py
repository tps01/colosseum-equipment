"""USB-8451 / USB-8452 capability limits."""

from __future__ import annotations

from dataclasses import dataclass

from colosseum_equipment.io.exceptions import IoConfigError


@dataclass(frozen=True)
class Ni845xLimits:
    model: str
    max_i2c_hz: int
    max_spi_hz: int
    voltages: frozenset[float]


_LIMITS: dict[str, Ni845xLimits] = {
    "usb-8451": Ni845xLimits(
        model="usb-8451",
        max_i2c_hz=250_000,
        max_spi_hz=12_000_000,
        voltages=frozenset({3.3}),
    ),
    "usb-8452": Ni845xLimits(
        model="usb-8452",
        max_i2c_hz=3_300_000,
        max_spi_hz=50_000_000,
        voltages=frozenset({1.2, 1.5, 1.8, 2.5, 3.3}),
    ),
}


def normalize_model(model: str | None) -> str:
    if not model:
        raise IoConfigError("ni-845x requires model= (usb-8451 or usb-8452)")
    key = str(model).strip().lower().replace("_", "-")
    if key in ("8451", "ni-usb-8451", "usb8451"):
        key = "usb-8451"
    elif key in ("8452", "ni-usb-8452", "usb8452"):
        key = "usb-8452"
    if key not in _LIMITS:
        raise IoConfigError(f"unsupported ni-845x model {model!r}; use usb-8451 or usb-8452")
    return key


def limits_for(model: str | None) -> Ni845xLimits:
    return _LIMITS[normalize_model(model)]


def resolve_voltage(model: str | None, voltage: float | None) -> float:
    lim = limits_for(model)
    if voltage is None:
        return 3.3
    value = float(voltage)
    for allowed in lim.voltages:
        if abs(value - allowed) < 0.05:
            if lim.model == "usb-8451" and abs(allowed - 3.3) > 0.05:
                raise IoConfigError("usb-8451 I/O voltage is fixed at 3.3 V")
            return allowed
    raise IoConfigError(
        f"{lim.model} voltage must be one of {sorted(lim.voltages)}; got {voltage}",
    )


def check_i2c_clock(model: str | None, clock_hz: int) -> int:
    lim = limits_for(model)
    rate = int(clock_hz)
    if rate <= 0:
        raise IoConfigError(f"i2c clock_hz must be positive; got {clock_hz}")
    if rate > lim.max_i2c_hz:
        raise IoConfigError(
            f"{lim.model} I2C clock max is {lim.max_i2c_hz} Hz; got {rate}",
        )
    return rate


def check_spi_clock(model: str | None, clock_hz: int) -> int:
    lim = limits_for(model)
    rate = int(clock_hz)
    if rate <= 0:
        raise IoConfigError(f"spi clock_hz must be positive; got {clock_hz}")
    if rate > lim.max_spi_hz:
        raise IoConfigError(
            f"{lim.model} SPI clock max is {lim.max_spi_hz} Hz; got {rate}",
        )
    return rate
