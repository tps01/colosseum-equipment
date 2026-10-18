"""Digital multimeter APIs (``col.equipment.dmm``).

One-shot measurements (``measure_voltage``, ``measure_voltage_dc``, etc.) configure
the function then issue ``READ?``. Use ``set_function`` → ``initiate`` → ``fetch``
when you need a fixed configuration across multiple samples.
"""

from __future__ import annotations

from typing import Any

from colosseum.decorators import command, measurement

from colosseum_equipment.api._verify import tolerance_verifier
from colosseum_equipment.connections import get_cached_instrument


def _inst(dmm_id: int) -> Any:
    return get_cached_instrument("dmm", dmm_id)


@command
def set_function(*, dmm_id: int, function: str, channel: int = 1) -> None:
    """Set measurement function (e.g. ``VOLT:DC``, ``CURR:AC``, ``RES``)."""
    _inst(dmm_id).set_function(function, channel=channel)


@command
def set_range(*, dmm_id: int, value: float, channel: int = 1) -> None:
    """Set manual measurement range for the active function."""
    _inst(dmm_id).set_range(value, channel=channel)


@command
def set_auto_range(*, dmm_id: int, enabled: bool, channel: int = 1) -> None:
    """Enable or disable autorange."""
    _inst(dmm_id).set_auto_range(enabled, channel=channel)


@command
def set_nplc(*, dmm_id: int, nplc: float, channel: int = 1) -> None:
    """Set integration time in power-line cycles (NPLC)."""
    _inst(dmm_id).set_nplc(nplc, channel=channel)


@command
def set_aperture_s(*, dmm_id: int, seconds: float, channel: int = 1) -> None:
    """Set aperture time in seconds (when supported)."""
    _inst(dmm_id).set_aperture_s(seconds, channel=channel)


@command
def set_auto_zero(*, dmm_id: int, enabled: bool, channel: int = 1) -> None:
    """Enable or disable auto-zero."""
    _inst(dmm_id).set_auto_zero(enabled, channel=channel)


@command
def set_input_z(*, dmm_id: int, ohms: float, channel: int = 1) -> None:
    """Set input impedance in ohms."""
    _inst(dmm_id).set_input_z(ohms, channel=channel)


@command
def set_trigger_source(*, dmm_id: int, source: str, channel: int = 1) -> None:
    """Set trigger source (e.g. ``IMM``, ``EXT``, ``BUS``)."""
    _inst(dmm_id).set_trigger_source(source, channel=channel)


@command
def initiate(*, dmm_id: int, channel: int = 1) -> None:
    """Arm a measurement (``INIT``); read with :func:`fetch`."""
    _inst(dmm_id).initiate(channel=channel)


@measurement
def get_function(*, dmm_id: int, channel: int = 1, key: str) -> str:
    """Read active measurement function."""
    _ = key
    return str(_inst(dmm_id).get_function(channel=channel))


@measurement
def get_range(*, dmm_id: int, channel: int = 1, key: str) -> float:
    """Read manual range setting."""
    _ = key
    return float(_inst(dmm_id).get_range(channel=channel))


@measurement
def get_auto_range(*, dmm_id: int, channel: int = 1, key: str) -> float:
    """Read autorange state (``1.0`` / ``0.0``)."""
    _ = key
    return 1.0 if _inst(dmm_id).get_auto_range(channel=channel) else 0.0


@measurement
def get_nplc(*, dmm_id: int, channel: int = 1, key: str) -> float:
    """Read NPLC setting."""
    _ = key
    return float(_inst(dmm_id).get_nplc(channel=channel))


@measurement
def get_aperture_s(*, dmm_id: int, channel: int = 1, key: str) -> float:
    """Read aperture time in seconds."""
    _ = key
    return float(_inst(dmm_id).get_aperture_s(channel=channel))


@measurement
def get_auto_zero(*, dmm_id: int, channel: int = 1, key: str) -> float:
    """Read auto-zero state (``1.0`` / ``0.0``)."""
    _ = key
    return 1.0 if _inst(dmm_id).get_auto_zero(channel=channel) else 0.0


@measurement
def get_input_z(*, dmm_id: int, channel: int = 1, key: str) -> float:
    """Read input impedance in ohms."""
    _ = key
    return float(_inst(dmm_id).get_input_z(channel=channel))


@measurement
def get_trigger_source(*, dmm_id: int, channel: int = 1, key: str) -> str:
    """Read trigger source."""
    _ = key
    return str(_inst(dmm_id).get_trigger_source(channel=channel))


@measurement
def fetch(*, dmm_id: int, channel: int = 1, key: str) -> float:
    """Fetch result after :func:`initiate`."""
    _ = key
    return float(_inst(dmm_id).fetch(channel=channel))


verify_fetch = tolerance_verifier("fetch", name="verify_fetch")


@measurement
def measure_voltage(*, dmm_id: int, channel: int = 1, key: str) -> float:
    """Measure DC voltage (alias for :func:`measure_voltage_dc`)."""
    _ = key
    return float(_inst(dmm_id).measure_voltage(channel))


verify_voltage = tolerance_verifier("measure_voltage", name="verify_voltage", unit="V")


@measurement
def measure_voltage_dc(*, dmm_id: int, channel: int = 1, key: str) -> float:
    """One-shot DC voltage (``CONF:VOLT:DC`` then ``READ?``)."""
    _ = key
    return float(_inst(dmm_id).measure_voltage_dc(channel))


verify_voltage_dc = tolerance_verifier("measure_voltage_dc", name="verify_voltage_dc", unit="V")


@measurement
def measure_voltage_ac(*, dmm_id: int, channel: int = 1, key: str) -> float:
    """One-shot AC voltage."""
    _ = key
    return float(_inst(dmm_id).measure_voltage_ac(channel))


verify_voltage_ac = tolerance_verifier("measure_voltage_ac", name="verify_voltage_ac", unit="V")


@measurement
def measure_current(*, dmm_id: int, channel: int = 1, key: str) -> float:
    """Measure DC current (alias for :func:`measure_current_dc`)."""
    _ = key
    return float(_inst(dmm_id).measure_current(channel))


verify_current = tolerance_verifier("measure_current", name="verify_current", unit="A")


@measurement
def measure_current_dc(*, dmm_id: int, channel: int = 1, key: str) -> float:
    """One-shot DC current."""
    _ = key
    return float(_inst(dmm_id).measure_current_dc(channel))


verify_current_dc = tolerance_verifier("measure_current_dc", name="verify_current_dc", unit="A")


@measurement
def measure_current_ac(*, dmm_id: int, channel: int = 1, key: str) -> float:
    """One-shot AC current."""
    _ = key
    return float(_inst(dmm_id).measure_current_ac(channel))


verify_current_ac = tolerance_verifier("measure_current_ac", name="verify_current_ac", unit="A")


@measurement
def measure_resistance(*, dmm_id: int, channel: int = 1, key: str) -> float:
    """Measure 2-wire resistance."""
    _ = key
    return float(_inst(dmm_id).measure_resistance(channel))


verify_resistance = tolerance_verifier("measure_resistance", name="verify_resistance", unit="ohm")


@measurement
def measure_resistance_4w(*, dmm_id: int, channel: int = 1, key: str) -> float:
    """Measure 4-wire resistance."""
    _ = key
    return float(_inst(dmm_id).measure_resistance_4w(channel))


verify_resistance_4w = tolerance_verifier(
    "measure_resistance_4w",
    name="verify_resistance_4w",
    unit="ohm",
)


@measurement
def measure_frequency_hz(*, dmm_id: int, channel: int = 1, key: str) -> float:
    """Measure frequency in hertz."""
    _ = key
    return float(_inst(dmm_id).measure_frequency_hz(channel))


verify_frequency_hz = tolerance_verifier(
    "measure_frequency_hz",
    name="verify_frequency_hz",
    unit="Hz",
)
