"""Signal Hound BB60C/SM200C spectrum acquisition through a running Spike server.

Manual: https://signalhound.com/sigdownloads/Spike/docs/html/scpi_programming.html
The resource is the Spike SCPI TCP socket, not a direct USB/device session.
"""
from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from colosseum_equipment.exceptions import EquipmentCapabilityError, EquipmentResponseError
from colosseum_equipment.instruments._capabilities import supported_commands
from colosseum_equipment.instruments.registry import instrument_model
from colosseum_equipment.instruments.speca.generic import GenericSpecA
from colosseum_equipment.instruments.speca.trace_csv import parse_trace_amplitudes

if TYPE_CHECKING:
    from colosseum_equipment.transports.base import Transport


@instrument_model("speca", "signalhound-bb60c-spike", "signalhound-sm200c-spike")
@supported_commands(
    "set_center_frequency", "set_start_frequency", "set_stop_frequency", "set_span", "set_rbw",
    "set_vbw", "set_sweep_time", "set_reference_level", "set_continuous_sweep", "arm_sweep", "single_sweep", "wait_complete",
    "save_trace_data", "measure_bw", "measure_trace_power_at_frequency",
)
class SignalHoundSpike(GenericSpecA):
    """Swept SA mode and write traces only; no min/max-pair ambiguity."""

    def __init__(self, transport: Transport, config: dict[str, Any]) -> None:
        transport.write("INST:SEL SA")
        super().__init__(transport, config)

    def single_sweep(self) -> None:
        self.arm_sweep()
        self.wait_complete(timeout_s=float(self._config.get("timeout", 60.0)))

    def set_reference_level(self, level_dbm: float) -> None:
        self._scpi.write(f"SENS:POW:RF:RLEV {level_dbm}DBM")

    def _fetch_trace(
        self, trace: int, *, include_frequency: bool = True,
    ) -> tuple[list[float], list[float]]:
        if not 1 <= trace <= 6:
            raise ValueError("Spike trace index must be 1..6")
        self._scpi.write(f"TRAC:SEL {trace}")
        self._scpi.write("TRAC:TYPE WRIT")
        self._scpi.write("TRAC:UPD ON")
        # Force a single detector result per frequency; MINMAX can return pairs.
        self._scpi.write("SENS:SWE:DET:FUNC MAX")
        self._scpi.write("FORM:TRAC ASC")
        if self._scpi.query("SENS:POW:RF:RLEV:UNIT?").upper() != "DBM":
            raise EquipmentCapabilityError("set reference level in dBm before exporting a dBm trace")
        self.single_sweep()
        count = int(self._scpi.query_float("TRAC:POIN?"))
        values = parse_trace_amplitudes(self._scpi.query("TRAC:DATA?"))
        if not values or len(values) != count or any(not math.isfinite(v) for v in values):
            raise EquipmentResponseError("Spike trace length differs from reported point count")
        start = self._scpi.query_float("TRAC:XSTAR?")
        increment = self._scpi.query_float("TRAC:XINC?")
        if not math.isfinite(start) or not math.isfinite(increment) or increment <= 0:
            raise EquipmentResponseError("Spike trace frequency increment must be positive")
        axis = [start + i * increment for i in range(count)] if include_frequency else [float(i) for i in range(count)]
        return axis, values

    def close(self) -> None:
        self._scpi._transport.close()
