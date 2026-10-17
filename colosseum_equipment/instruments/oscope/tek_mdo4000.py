"""Tektronix MDO4000/MSO4000B/DPO4000B oscilloscope (SCPI).

Manual: 077-0510-03 Programmer Manual — horizontal scale, measurements, acquire.
Catalog: https://www.tek.com/en/oscilloscope/mso4000-dpo4000-manual/mdo4000c-mdo4000b-mdo4000-mso4000b-dpo4000b-and-mdo3000-0
"""

from __future__ import annotations

from colosseum_equipment.instruments.oscope.generic import GenericOscope
from colosseum_equipment.instruments.registry import instrument_model
from colosseum_equipment.protocols.scpi import wait_opc


@instrument_model(
    "oscope",
    "tektronix-mdo4000",
    "tektronix-mdo3012",
    "tektronix-mdo3014",
    "tektronix-mdo3022",
    "tektronix-mdo3024",
    "tektronix-mdo3032",
    "tektronix-mdo3034",
    "tektronix-mdo3052",
    "tektronix-mdo3054",
    "tektronix-mdo3102",
    "tektronix-mdo3104",
    "tektronix-mso4104b",
    "tektronix-mso4054b",
    "tektronix-dpo4034b",
    "tektronix-dpo4104b",
    "tektronix-mdo4104c",
)
class TekMdo4000Oscope(GenericOscope):
    _model = "tektronix-mdo4000"

    def set_timebase_scale(self, seconds_per_div: float) -> None:
        self._scpi.write(f"HORizontal:SCAle {seconds_per_div}")

    def single_acquire(self) -> None:
        self._scpi.write("ACQuire:STATE RUN")
        wait_opc(self._scpi)
        self._scpi.write("ACQuire:STATE STOP")
        wait_opc(self._scpi)

    def measure_vpp(self, channel: int = 1) -> float:
        source = f"CH{channel}"
        self._scpi.write(f"MEASUrement:IMMediate:SOUrce1 {source}")
        self._scpi.write("MEASUrement:MEAS1:TYPE PK2pk")
        return self._scpi.query_float("MEASUrement:MEAS1:VALue?")

    def save_screenshot(self, path: str) -> None:
        self._scpi.write(f'SAVE:IMAGE "{path}"')
