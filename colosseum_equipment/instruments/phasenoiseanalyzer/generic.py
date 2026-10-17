"""Generic SCPI phase noise analyzer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from colosseum_equipment.instruments._base import ScpiInstrumentMixin
from colosseum_equipment.instruments.registry import best_effort_commands, instrument_model
from colosseum_equipment.protocols.scpi import SCPIHelper, wait_opc

if TYPE_CHECKING:
    from colosseum_equipment.transports.base import Transport


@instrument_model("phasenoiseanalyzer", "generic")
@best_effort_commands
class GenericPhaseNoiseAnalyzer(ScpiInstrumentMixin):
    """Generic SCPI phase-noise analyzer (IEEE 488.2 + common mnemonics)."""

    _model = "generic"

    def __init__(self, transport: Transport, config: dict[str, Any]) -> None:
        self._scpi = SCPIHelper(transport)
        self._config = config
        self._model = str(config.get("model", "generic")).lower()

    def preset(self) -> None:
        self._scpi.write("*RST")
        wait_opc(self._scpi)

    def set_carrier_frequency_hz(self, frequency_hz: float) -> None:
        self._scpi.write(f"FREQ:CENT {frequency_hz:.6f}")

    def set_offset_start_hz(self, offset_hz: float) -> None:
        self._scpi.write(f"FREQ:STAR {offset_hz:.6f}")

    def set_offset_stop_hz(self, offset_hz: float) -> None:
        self._scpi.write(f"FREQ:STOP {offset_hz:.6f}")

    def initiate(self) -> None:
        self._scpi.write("INIT:IMM")

    def wait_opc(self) -> None:
        wait_opc(self._scpi)

    def measure_spot_noise_dbc_hz(self, offset_hz: float) -> float:
        self._scpi.write(f"CALC:SNO:X {offset_hz:.6f}")
        return self._scpi.query_float("CALC:SNO:Y?")

    def measure_carrier_frequency_hz(self) -> float:
        return self._scpi.query_float("FREQ:CENT?")
