"""FPC1500 spectrum mode; 1178.4130.02 v13, remote control ch.20.

https://www.batronix.com/files/Rohde-%26-Schwarz/Spectrum-Analyser/FPC1500/FPC_UserManual_en.pdf
"""
from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from colosseum_equipment.exceptions import EquipmentResponseError
from colosseum_equipment.instruments._capabilities import supported_commands
from colosseum_equipment.instruments.registry import instrument_model
from colosseum_equipment.instruments.speca.generic import GenericSpecA
from colosseum_equipment.instruments.speca.trace_csv import parse_trace_amplitudes

if TYPE_CHECKING:
    from colosseum_equipment.transports.base import Transport


@instrument_model("speca", "rohde-fpc1500")
@supported_commands(
    "set_center_frequency", "set_start_frequency", "set_stop_frequency", "set_span", "set_rbw",
    "set_vbw", "set_sweep_time", "set_reference_level", "set_continuous_sweep", "arm_sweep",
    "single_sweep", "wait_complete", "save_trace_data", "measure_bw", "measure_trace_power_at_frequency",
)
class RohdeFpc1500(GenericSpecA):
    """Spectrum only; no VNA, receiver, tracking generator or licensed measurements."""

    def __init__(self, transport: Transport, config: dict[str, Any]) -> None:
        transport.write("INST:SEL SPEC")
        super().__init__(transport, config)

    def set_reference_level(self, level_dbm: float) -> None:
        self._scpi.write(f"DISP:TRAC:Y:RLEV {level_dbm}DBM")

    def single_sweep(self) -> None:
        self.arm_sweep()
        self.wait_complete(timeout_s=float(self._config.get("timeout", 60.0)))

    def _fetch_trace(
        self, trace: int, *, include_frequency: bool = True,
    ) -> tuple[list[float], list[float]]:
        if trace not in (1, 2):
            raise ValueError("FPC spectrum traces are 1 or 2")
        self._scpi.write(f"DISP:TRAC{trace}:MODE WRIT")
        self._scpi.write("FORM ASC")
        self.single_sweep()
        values = parse_trace_amplitudes(self._scpi.query(f"TRAC:DATA? TRACE{trace}"))
        start = self._scpi.query_float("FREQ:STAR?")
        stop = self._scpi.query_float("FREQ:STOP?")
        if len(values) < 2 or any(not math.isfinite(v) for v in values):
            raise EquipmentResponseError("empty or invalid spectrum data")
        if not math.isfinite(start) or not math.isfinite(stop) or stop <= start:
            raise EquipmentResponseError("frequency CSV requires a positive linear sweep span")
        # Firmware revisions have different fixed trace lengths (631 / 1183).
        axis = [start + i * (stop - start) / (len(values) - 1) for i in range(len(values))]
        return (axis if include_frequency else [float(i) for i in range(len(values))]), values

    def close(self) -> None:
        self._scpi._transport.close()
