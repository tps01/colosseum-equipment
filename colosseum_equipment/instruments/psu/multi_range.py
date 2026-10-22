"""BK Precision 9115 and Keithley 2260B single-output multi-range supplies."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from colosseum_equipment.exceptions import EquipmentCapabilityError, EquipmentResponseError
from colosseum_equipment.instruments._capabilities import supported_commands
from colosseum_equipment.instruments.psu.generic import GenericPSU
from colosseum_equipment.instruments.registry import instrument_model

if TYPE_CHECKING:
    from colosseum_equipment.transports.base import Transport


_SOURCE = (
    "set_voltage",
    "set_current_limit",
    "set_output",
    "get_voltage",
    "get_current_limit",
    "get_output",
    "measure_voltage",
    "measure_current",
    "measure_power_w",
    "measure_output_state",
    "wait_for_voltage",
    "wait_for_current",
    "set_ovp_v",
    "get_ovp_v",
)


def _binary(raw: str, label: str, *, textual: bool) -> bool:
    value = raw.strip().upper()
    if value == "1" or (textual and value == "ON"):
        return True
    if value == "0" or (textual and value == "OFF"):
        return False
    raise EquipmentResponseError(f"invalid {label}: {raw!r}")


class _MultiRangePSU(GenericPSU):
    """Shared VOLT/CURR/OUTP/MEAS commands. Subclasses own protection differences."""

    _output_message = "supply has one output"
    _textual_output = False

    def __init__(self, transport: Transport, config: dict[str, Any]) -> None:
        if int(config.get("channels") or config.get("channel_count") or 1) != 1:
            raise EquipmentCapabilityError(self._output_message)
        super().__init__(transport, config)

    def get_output(self, *, channel: int = 1) -> bool:
        self._require_channel(channel)
        return _binary(self._scpi.query("OUTP?"), "output state", textual=self._textual_output)

    def measure_power_w(self, *, channel: int = 1) -> float:
        self._require_channel(channel)
        return self._scpi.query_float("MEAS:POW?")


@instrument_model("psu", "bk-9115")
@supported_commands(*_SOURCE, "toggle_ovp", "get_ovp_enabled", "clear_protection")
class Bk9115PSU(_MultiRangePSU):
    """9115 series SCPI. One output; connection does not enable it.

    Manual: https://bkpmedia.s3.us-west-1.amazonaws.com/downloads/programming_manuals/en-us/9115_Series_programming_manual.pdf
    ``OUTP?`` and ``VOLT:PROT:STAT?`` return ``0`` or ``1``. Clear OVP with
    ``PROT:CLE``. The manual has no current-protection level or enable command.
    """

    _output_message = "9115 has one output"

    def get_ovp_enabled(self, *, channel: int = 1) -> bool:
        self._require_channel(channel)
        return _binary(self._scpi.query("VOLT:PROT:STAT?"), "OVP state", textual=False)

    def clear_protection(self, *, channel: int = 1) -> None:
        self._require_channel(channel)
        self._scpi.write("PROT:CLE")


@instrument_model("psu", "keithley-2260b")
@supported_commands(
    *_SOURCE,
    "set_ocp_a",
    "get_ocp_a",
    "toggle_ocp",
    "get_ocp_enabled",
    "clear_protection",
)
class Keithley2260bPSU(_MultiRangePSU):
    """2260B family SCPI, including 2260B-30-36 and 2260B-80-13.

    Manual: https://download.tek.com/manual/077104703%5FOct2024%5F2260B%5FProgramming.pdf
    ``OUTP?`` and ``CURR:PROT:STAT?`` accept ``0``/``1``/``ON``/``OFF``. OVP is a
    level only. ``OUTP:MODE`` selects slew priority, not CV/CC regulation.
    One output; connection does not enable it.
    """

    _output_message = "2260B has one output"
    _textual_output = True

    def get_ocp_enabled(self, *, channel: int = 1) -> bool:
        self._require_channel(channel)
        return _binary(self._scpi.query("CURR:PROT:STAT?"), "OCP state", textual=True)
