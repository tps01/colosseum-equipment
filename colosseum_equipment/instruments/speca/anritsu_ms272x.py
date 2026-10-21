"""MS272xB / MS2720T spectrum commands, little-endian REAL32 trace transfer.

References: 10580-00176 pp.25-27/37-40 and 10580-00341K ch.3/4.
https://dl.cdn-anritsu.com/en-us/test-measurement/files/Manuals/Programming-Manual/10580-00176.pdf
https://dl.cdn-anritsu.com/en-us/test-measurement/files/Manuals/Programming-Manual/10580-00341K.pdf
"""
from __future__ import annotations

import math
import struct
import time
from typing import TYPE_CHECKING, Any

from colosseum_equipment.exceptions import EquipmentCapabilityError, EquipmentResponseError, EquipmentTimeoutError
from colosseum_equipment.instruments._capabilities import supported_commands
from colosseum_equipment.instruments.registry import instrument_model
from colosseum_equipment.instruments.speca.generic import GenericSpecA

if TYPE_CHECKING:
    from colosseum_equipment.transports.base import Transport


@instrument_model("speca", "anritsu-ms2721b", "anritsu-ms2723b", "anritsu-ms2720t")
@supported_commands(
    "set_center_frequency", "set_start_frequency", "set_stop_frequency", "set_span", "set_rbw",
    "set_vbw", "set_reference_level", "set_continuous_sweep", "arm_sweep", "single_sweep",
    "wait_complete", "abort", "save_trace_data", "measure_bw", "measure_trace_power_at_frequency",
)
class AnritsuMs272x(GenericSpecA):
    """SPA mode must already be selected; mode changes need a long settling time.

    Configure the requested trace to live/write on the panel before acquisition.
    Sweep complete uses operation-register bit 8, not an assumed *OPC? command
    on older firmware. No licensed application or tracking-generator support.
    """

    def __init__(self, transport: Transport, config: dict[str, Any]) -> None:
        mode = transport.query("INST:SEL?").strip().strip('"').upper()
        if mode != "SPA":
            raise EquipmentCapabilityError("select SPA mode and allow settling before connecting")
        super().__init__(transport, config)

    def wait_complete(self, *, timeout_s: float = 60.0) -> None:
        deadline = time.monotonic() + timeout_s
        sweep_complete_bit = 1 << 8
        while time.monotonic() < deadline:
            if int(self._scpi.query("STAT:OPER?")) & sweep_complete_bit:
                return
            time.sleep(0.05)
        raise EquipmentTimeoutError("Anritsu sweep did not complete")

    def single_sweep(self) -> None:
        self.arm_sweep()
        self.wait_complete(timeout_s=float(self._config.get("timeout", 60.0)))

    def _fetch_trace(
        self, trace: int, *, include_frequency: bool = True,
    ) -> tuple[list[float], list[float]]:
        if trace not in (1, 2, 3):
            raise ValueError("spectrum trace number must be 1..3")
        self._scpi.write("UNIT:POW DBM")
        self._scpi.write("FORM:DATA REAL,32")
        self.single_sweep()
        raw = self._scpi.read_binary_block(f"TRAC:DATA? {trace}")
        if len(raw) < 8 or len(raw) % 4:
            raise EquipmentResponseError("invalid REAL32 spectrum byte count")
        values = list(struct.unpack(f"<{len(raw) // 4}f", raw))
        start = self._scpi.query_float("FREQ:STAR?")
        stop = self._scpi.query_float("FREQ:STOP?")
        if any(not math.isfinite(v) or abs(v) >= 9e37 for v in values):
            raise EquipmentResponseError("invalid spectrum amplitude")
        if not math.isfinite(start) or not math.isfinite(stop) or stop <= start:
            raise EquipmentResponseError("zero-span/time data cannot be exported as frequency CSV")
        axis = [start + i * (stop - start) / (len(values) - 1) for i in range(len(values))]
        return (axis if include_frequency else [float(i) for i in range(len(values))]), values

    def close(self) -> None:
        self._scpi._transport.close()
