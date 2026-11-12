"""Catalog models from the programming-manual spreadsheet.

Each class inherits the generic driver. Inherited commands are sent as
generic SCPI and log one warning per model and command. The class
docstring is the manual link.
"""

from __future__ import annotations

import math

from colosseum_equipment.exceptions import EquipmentResponseError
from colosseum_equipment.instruments.speca.trace_csv import frequency_axis, parse_trace_amplitudes

from colosseum_equipment.instruments.registry import instrument_model
from colosseum_equipment.instruments.speca.generic import GenericSpecA
from colosseum_equipment.instruments.speca.rigol_dsa800 import RigolDsa800


@instrument_model("speca", "rigol-dsa815")
class RigolDsa815(RigolDsa800):
    """Manual: https://www.rigolna.com/support/downloads/"""


@instrument_model("speca", "rigol-dsa815-tg")
class RigolDsa815Tg(RigolDsa800):
    """Manual: https://www.rigolna.com/support/downloads/"""


@instrument_model("speca", "rigol-dsa832")
class RigolDsa832(RigolDsa800):
    """Manual: https://www.rigolna.com/support/downloads/"""


@instrument_model("speca", "rigol-dsa875")
class RigolDsa875(RigolDsa800):
    """Manual: https://www.rigolna.com/support/downloads/"""


@instrument_model("speca", "rigol-dsa800e")
class RigolDsa800e(RigolDsa800):
    """Manual: https://www.rigolna.com/support/downloads/"""

# TODO: Validate rigol-dsa1000 inherited commands against its vendor manual and hardware.

@instrument_model("speca", "rigol-dsa1000")
class RigolDsa1000(GenericSpecA):
    """Manual: https://www.rigolna.com/support/downloads/"""

# TODO: Validate rigol-rsa3030 inherited commands against its vendor manual and hardware.

@instrument_model("speca", "rigol-rsa3030")
class RigolRsa3030(GenericSpecA):
    """Manual: https://www.rigolna.com/support/downloads/"""

# TODO: Validate rigol-rsa3045 inherited commands against its vendor manual and hardware.

@instrument_model("speca", "rigol-rsa3045")
class RigolRsa3045(GenericSpecA):
    """Manual: https://www.rigolna.com/support/downloads/"""

# TODO: Validate rigol-rsa5065 inherited commands against its vendor manual and hardware.

@instrument_model("speca", "rigol-rsa5065")
class RigolRsa5065(GenericSpecA):
    """Manual: https://www.rigolna.com/support/downloads/"""

# TODO: Validate siglent-ssa3021x inherited commands against its vendor manual and hardware.

@instrument_model("speca", "siglent-ssa3021x")
class SiglentSsa3021x(GenericSpecA):
    """Manual: https://siglentna.com/resources/documents/spectrum-analyzers/"""

    def _fetch_trace(self, trace: int, *, include_frequency: bool = True) -> tuple[list[float], list[float]]:
        if trace not in (1, 2, 3, 4):
            raise ValueError("SSA3000X trace number must be 1..4")
        self._scpi.write("UNIT:POW DBM")
        self._scpi.write("FORM ASC")
        self.single_sweep()
        center = self._scpi.query_float("FREQ:CENT?")
        span = self._scpi.query_float("FREQ:SPAN?")
        raw = self._scpi.query(f"TRAC:DATA? {trace}")
        try:
            if any(not part.strip() for part in raw.split(",")):
                raise ValueError("empty sample")
            values = parse_trace_amplitudes(raw)
        except ValueError as exc:
            raise EquipmentResponseError("malformed SSA3000X ASCII trace") from exc
        if len(values) < 2 or any(not math.isfinite(v) or abs(v) >= 9e37 for v in values):
            raise EquipmentResponseError("empty or invalid SSA3000X trace")
        if not math.isfinite(center) or not math.isfinite(span) or span < 0:
            raise EquipmentResponseError("invalid SSA3000X frequency axis")
        if include_frequency and span == 0:
            raise EquipmentResponseError("zero-span data cannot be exported as frequency CSV")
        axis = frequency_axis(center, span, len(values)) if include_frequency else [float(i) for i in range(len(values))]
        return axis, values

    def _peak(self, marker: int, direction: str) -> None:
        if marker not in (1, 2, 3, 4):
            raise ValueError("SSA3000X marker number must be 1..4")
        self._scpi.write(f"CALC:MARK{marker}:MAX:{direction}")

    def next_peak_right(self, marker: int = 1) -> None:
        self._peak(marker, "RIGH")

    def next_peak_left(self, marker: int = 1) -> None:
        self._peak(marker, "LEFT")

    def next_highest_peak(self, marker: int = 1) -> None:
        self._peak(marker, "NEXT")

    def close(self) -> None:
        self._scpi._transport.close()

# TODO: Validate siglent-ssa3032x inherited commands against its vendor manual and hardware.

@instrument_model("speca", "siglent-ssa3032x")
class SiglentSsa3032x(SiglentSsa3021x):
    """Manual: https://siglentna.com/resources/documents/spectrum-analyzers/"""

# TODO: Validate siglent-ssa3021x-plus inherited commands against its vendor manual and hardware.

@instrument_model("speca", "siglent-ssa3021x-plus")
class SiglentSsa3021xPlus(GenericSpecA):
    """Manual: https://siglentna.com/resources/documents/spectrum-analyzers/"""

# TODO: Validate siglent-ssa3032x-plus inherited commands against its vendor manual and hardware.

@instrument_model("speca", "siglent-ssa3032x-plus")
class SiglentSsa3032xPlus(GenericSpecA):
    """Manual: https://siglentna.com/resources/documents/spectrum-analyzers/"""

# TODO: Validate siglent-ssa3075x-plus inherited commands against its vendor manual and hardware.

@instrument_model("speca", "siglent-ssa3075x-plus")
class SiglentSsa3075xPlus(GenericSpecA):
    """Manual: https://siglentna.com/resources/documents/spectrum-analyzers/"""

# TODO: Validate siglent-ssa5000a inherited commands against its vendor manual and hardware.

@instrument_model("speca", "siglent-ssa5000a")
class SiglentSsa5000a(GenericSpecA):
    """Manual: https://siglentna.com/resources/documents/spectrum-analyzers/"""
