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
from colosseum_equipment.instruments.registry import _confirmed_generic_commands, instrument_model
from colosseum_equipment.instruments.speca.generic import GenericSpecA

if TYPE_CHECKING:
    from colosseum_equipment.transports.base import Transport


_MS272X_COMMANDS = (
    "set_center_frequency",
    "set_start_frequency",
    "set_stop_frequency",
    "set_span",
    "set_rbw",
    "set_vbw",
    "set_reference_level",
    "set_continuous_sweep",
    "arm_sweep",
    "single_sweep",
    "wait_complete",
    "abort",
    "save_trace_data",
    "measure_bw",
    "measure_center_frequency_hz",
    "measure_trace_power_at_frequency",
    "toggle_marker",
    "peak_search",
    "set_marker_frequency",
    "measure_marker_frequency",
    "measure_marker_power",
    "next_peak_left",
    "next_peak_right",
    "set_marker_to_center",
    "toggle_delta_marker",
    "measure_marker_delta_frequency",
    "measure_marker_delta_power",
    "set_detector",
    "set_averaging_count",
    "set_average_type",
)


@instrument_model("speca", "anritsu-ms2721b", "anritsu-ms2723b", "anritsu-ms2720t")
@supported_commands(*_MS272X_COMMANDS)
@_confirmed_generic_commands(*_MS272X_COMMANDS)
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

    def _marker_command(self, marker: int) -> str:
        if isinstance(marker, bool) or not isinstance(marker, int) or not 1 <= marker <= 6:
            raise ValueError("MS272x marker number must be 1..6")
        return f"CALC:MARK{marker}"

    def set_marker_frequency(self, marker: int, frequency_hz: float) -> None:
        command = self._marker_command(marker)
        if not math.isfinite(frequency_hz) or frequency_hz < 0:
            raise ValueError("marker frequency must be finite and nonnegative")
        self._scpi.write(f"{command}:X {frequency_hz:.6f}")

    def measure_marker_power(self, marker: int = 1) -> float:
        command = self._marker_command(marker)
        self._scpi.require_setting("UNIT:POW?", "DBM")
        return self._scpi.query_float(f"{command}:Y?")

    def next_peak_left(self, marker: int = 1) -> None:
        self._scpi.write(f"{self._marker_command(marker)}:MAX:LEFT")

    def next_peak_right(self, marker: int = 1) -> None:
        self._scpi.write(f"{self._marker_command(marker)}:MAX:RIGH")

    def set_marker_to_center(self, marker: int = 1) -> None:
        command = self._marker_command(marker)
        center = self._scpi.query_float("FREQ:CENT?")
        self._scpi.write(f"{command}:X {center:.6f}")

    def measure_marker_delta_power(self, marker: int = 1) -> float:
        command = self._marker_command(marker)
        self._scpi.require_setting("UNIT:POW?", "DBM")
        return self._scpi.query_float(f"{command}:DELT:Y?")

    def set_detector(self, detector: str) -> None:
        token = detector.strip().upper()
        if token not in {"POS", "NEG", "SAMP", "RMS"}:
            raise ValueError("MS272x detector must be POS, NEG, SAMP or RMS")
        self._scpi.write(f"DET {token}")

    def set_averaging_count(self, count: int) -> None:
        if isinstance(count, bool) or not isinstance(count, int) or not 2 <= count <= 65535:
            raise ValueError("MS272x average count must be 2..65535")
        self._scpi.write(f"AVER:COUN {count}")

    def set_average_type(self, average_type: str) -> None:
        # On these instruments TYPE selects trace processing, not log/RMS units.
        token = average_type.strip().upper()
        if token not in {"NONE", "SCAL", "MAX", "MIN"}:
            raise ValueError("MS272x average type must be NONE, SCAL, MAX or MIN")
        self._scpi.write(f"AVER:TYPE {token}")

    def _fetch_trace(
        self,
        trace: int,
        *,
        include_frequency: bool = True,
    ) -> tuple[list[float], list[float]]:
        if trace not in (1, 2, 3):
            raise ValueError("spectrum trace number must be 1..3")
        self._scpi.require_setting("UNIT:POW?", "DBM")
        with self._scpi.temporary_settings(('FORM:DATA', 'REAL,32')):
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
