"""HP 8590 E/L programmer guide 08590-90235; 856xE/EC user guide, ch.5.

https://xdevs.com/doc/HP_Agilent_Keysight/08590-90235%208590E%2090L%2091C%20Prog%20Guide%20Jun95.pdf
https://device.report/m/c5c95d946588cdeb3355d41046c5b04816a1471e37ed488e5cf27039a500b320
"""
from __future__ import annotations

import math

from colosseum_equipment.exceptions import EquipmentCapabilityError, EquipmentResponseError
from colosseum_equipment.instruments._capabilities import supported_commands
from colosseum_equipment.instruments.registry import instrument_model
from colosseum_equipment.instruments.speca.generic import GenericSpecA
from colosseum_equipment.instruments.speca.trace_csv import parse_trace_amplitudes

_CONTROLS = (
    "set_center_frequency", "set_start_frequency", "set_stop_frequency", "set_span", "set_rbw",
    "set_vbw", "set_reference_level", "set_marker_frequency", "peak_search",
    "measure_marker_frequency",
)


class HpLegacySpectrum(GenericSpecA):
    """Native mnemonics; markers read current display data without rearming."""

    def set_center_frequency(self, frequency: float) -> None:
        self._scpi.write(f"CF {frequency:.6f}HZ;")

    def set_start_frequency(self, frequency_hz: float) -> None:
        self._scpi.write(f"FA {frequency_hz:.6f}HZ;")

    def set_stop_frequency(self, frequency_hz: float) -> None:
        self._scpi.write(f"FB {frequency_hz:.6f}HZ;")

    def set_span(self, span: float) -> None:
        self._scpi.write(f"SP {span:.6f}HZ;")

    def set_rbw(self, rbw: float) -> None:
        self._scpi.write(f"RB {rbw:.6f}HZ;")

    def set_vbw(self, vbw: float) -> None:
        self._scpi.write(f"VB {vbw:.6f}HZ;")

    def set_reference_level(self, level_dbm: float) -> None:
        self._scpi.write(f"RL {level_dbm:.6f}DBM;")

    def _marker(self, marker: int) -> None:
        if marker != 1:
            raise EquipmentCapabilityError("this subset addresses the active marker as marker 1")

    def set_marker_frequency(self, marker: int, frequency_hz: float) -> None:
        self._marker(marker)
        self._scpi.write(f"MKN {frequency_hz:.6f}HZ;")

    def peak_search(self, marker: int = 1) -> None:
        self._marker(marker)
        self._scpi.write("MKPK HI;")

    def measure_marker_frequency(self, marker: int = 1) -> float:
        self._marker(marker)
        return self._scpi.query_float("MKF?;")

    def close(self) -> None:
        self._scpi._transport.close()


@instrument_model("speca", "keysight-8593e")
@supported_commands(*_CONTROLS)
class Hp8593e(HpLegacySpectrum):
    """Setup and active-marker reads only; trace encoding is not inferred from 856x."""


@instrument_model("speca", "keysight-8563ec")
@supported_commands(*_CONTROLS, "save_trace_data", "measure_bw", "measure_trace_power_at_frequency")
class Hp8563ec(HpLegacySpectrum):
    """Native SNGLS;TS and TDF P trace A transfer, 601 dBm points.

    TS/TRA? follows the documented sequential acquisition example; transport
    timeout must cover the sweep. Trace transfers put trace A in view mode.
    """

    def _fetch_trace(
        self, trace: int, *, include_frequency: bool = True,
    ) -> tuple[list[float], list[float]]:
        if trace != 1:
            raise EquipmentCapabilityError("only trace A (trace 1) is implemented")
        self._scpi.write("AUNITS DBM;")
        self._scpi.write("CLRW TRA;")
        self._scpi.write("SNGLS;TS;")
        self._scpi.write("TDF P;")
        values = parse_trace_amplitudes(self._scpi.query("TRA?;"))
        start = self._scpi.query_float("FA?;")
        stop = self._scpi.query_float("FB?;")
        if len(values) != 601 or any(not math.isfinite(v) for v in values):
            raise EquipmentResponseError("8563EC trace A must contain 601 finite dBm values")
        if not math.isfinite(start) or not math.isfinite(stop) or stop <= start:
            raise EquipmentResponseError("frequency export requires a positive span")
        axis = [start + i * (stop - start) / 600 for i in range(601)]
        return (axis if include_frequency else [float(i) for i in range(601)]), values

