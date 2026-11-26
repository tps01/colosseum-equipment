"""Catalog models from the programming-manual spreadsheet.

Each class inherits the generic driver. Inherited commands are sent as
generic SCPI and log one warning per model and command. The class
docstring is the manual link.
"""

from __future__ import annotations

import math
from typing import Any

from colosseum_equipment.exceptions import EquipmentResponseError
from colosseum_equipment.instruments.oscope.generic import GenericOscope, _parse_ascii_waveform
from colosseum_equipment.instruments.oscope.rigol_dho import RigolDho
from colosseum_equipment.instruments.oscope.siglent_sds1000x_e import SiglentSds1000xE
from colosseum_equipment.instruments.registry import _confirmed_generic_commands, instrument_model

@instrument_model("oscope", "rigol-ds1054z")
@_confirmed_generic_commands("save_waveform")
class RigolDs1054z(GenericOscope):
    """RIGOL DS1000Z Programming Guide, Waveform command group."""

    def _read_waveform_points(self, channel: int) -> tuple[list[float], dict[str, Any]]:
        ch = self._require_channel(channel)
        with self._scpi.temporary_settings(
            ("WAV:SOUR", f"CHAN{ch}"), ("WAV:MODE", "NORM"), ("WAV:FORM", "ASC"),
        ):
            raw = self._scpi._setting_value("WAV:PRE?")
            fields = raw.split(",")
            try:
                if len(fields) != 10 or (int(fields[0]), int(fields[1])) != (2, 0):
                    raise ValueError("expected an ASCII normal-mode preamble")
                count = int(fields[2])
                interval, origin, reference = map(float, fields[4:7])
            except ValueError as exc:
                raise EquipmentResponseError(f"invalid DS1054Z waveform preamble: {raw!r}") from exc
            start = origin - reference * interval
            if count < 1 or not math.isfinite(interval) or interval <= 0 or not math.isfinite(start):
                raise EquipmentResponseError("invalid DS1054Z waveform point count or time axis")
            volts = _parse_ascii_waveform(self._scpi._setting_value("WAV:DATA?"), points_expected=count)
            if len(volts) != count or any(not math.isfinite(value) for value in volts):
                raise EquipmentResponseError("invalid DS1054Z waveform samples or point count")
        return volts, {
            "channel": ch,
            "points": count,
            "points_expected": count,
            "xinc_s": interval,
            "xorigin_s": start,
            "capture_id": self._capture_id,
            "vertical_units": "V",
            "encoding": "ascii",
        }

# TODO: Validate rigol-ds1074z inherited commands against its vendor manual and hardware.

@instrument_model("oscope", "rigol-ds1074z")
class RigolDs1074z(GenericOscope):
    """Manual: https://www.rigolna.com/support/downloads/"""

# TODO: Validate rigol-ds1104z inherited commands against its vendor manual and hardware.

@instrument_model("oscope", "rigol-ds1104z")
class RigolDs1104z(GenericOscope):
    """Manual: https://www.rigolna.com/support/downloads/"""

# TODO: Validate rigol-mso1074z inherited commands against its vendor manual and hardware.

@instrument_model("oscope", "rigol-mso1074z")
class RigolMso1074z(GenericOscope):
    """Manual: https://www.rigolna.com/support/downloads/"""

# TODO: Validate rigol-mso1104z inherited commands against its vendor manual and hardware.

@instrument_model("oscope", "rigol-mso1104z")
class RigolMso1104z(GenericOscope):
    """Manual: https://www.rigolna.com/support/downloads/"""


@instrument_model("oscope", "rigol-dho802")
class RigolDho802(RigolDho):
    """Manual: https://www.rigolna.com/support/downloads/"""


@instrument_model("oscope", "rigol-dho804")
class RigolDho804(RigolDho):
    """Manual: https://www.rigolna.com/support/downloads/"""


@instrument_model("oscope", "rigol-dho914")
class RigolDho914(RigolDho):
    """Manual: https://www.rigolna.com/support/downloads/"""


@instrument_model("oscope", "rigol-dho924")
class RigolDho924(RigolDho):
    """Manual: https://www.rigolna.com/support/downloads/"""


@instrument_model("oscope", "rigol-dho1074")
class RigolDho1074(RigolDho):
    """Manual: https://www.rigolna.com/support/downloads/"""


@instrument_model("oscope", "rigol-dho1104")
class RigolDho1104(RigolDho):
    """Manual: https://www.rigolna.com/support/downloads/"""

# TODO: Validate rigol-ds2000a inherited commands against its vendor manual and hardware.

@instrument_model("oscope", "rigol-ds2000a")
class RigolDs2000a(GenericOscope):
    """Manual: https://www.rigolna.com/support/downloads/"""

# TODO: Validate rigol-ds4000 inherited commands against its vendor manual and hardware.

@instrument_model("oscope", "rigol-ds4000")
class RigolDs4000(GenericOscope):
    """Manual: https://www.rigolna.com/support/downloads/"""

# TODO: Validate rigol-mso5000 inherited commands against its vendor manual and hardware.

@instrument_model("oscope", "rigol-mso5000")
class RigolMso5000(GenericOscope):
    """Manual: https://www.rigolna.com/support/downloads/"""

# TODO: Validate rigol-mso8000 inherited commands against its vendor manual and hardware.

@instrument_model("oscope", "rigol-mso8000")
class RigolMso8000(GenericOscope):
    """Manual: https://www.rigolna.com/support/downloads/"""

# TODO: Validate rigol-ds70000 inherited commands against its vendor manual and hardware.

@instrument_model("oscope", "rigol-ds70000")
class RigolDs70000(GenericOscope):
    """Manual: https://www.rigolna.com/support/downloads/"""


@instrument_model("oscope", "siglent-sds1102x-e")
class SiglentSds1102xE(SiglentSds1000xE):
    """Manual: https://siglentna.com/resources/documents/digital-oscilloscopes/"""


@instrument_model("oscope", "siglent-sds1104x-e")
class SiglentSds1104xE(SiglentSds1000xE):
    """Manual: https://siglentna.com/resources/documents/digital-oscilloscopes/"""


@instrument_model("oscope", "siglent-sds1202x-e")
class SiglentSds1202xE(SiglentSds1000xE):
    """Manual: https://siglentna.com/resources/documents/digital-oscilloscopes/"""


@instrument_model("oscope", "siglent-sds1204x-e")
class SiglentSds1204xE(SiglentSds1000xE):
    """Manual: https://siglentna.com/resources/documents/digital-oscilloscopes/"""

# TODO: Validate siglent-sds2000x-plus inherited commands against its vendor manual and hardware.

@instrument_model("oscope", "siglent-sds2000x-plus")
class SiglentSds2000xPlus(GenericOscope):
    """Manual: https://www.siglent.com/na/service-support/resource-center/?current=siglent-manual-download"""

# TODO: Validate siglent-sds5000x inherited commands against its vendor manual and hardware.

@instrument_model("oscope", "siglent-sds5000x")
class SiglentSds5000x(GenericOscope):
    """Manual: https://www.siglent.com/na/service-support/resource-center/?current=siglent-manual-download"""

# TODO: Validate siglent-sds6000a inherited commands against its vendor manual and hardware.

@instrument_model("oscope", "siglent-sds6000a")
class SiglentSds6000a(GenericOscope):
    """Manual: https://www.siglent.com/na/service-support/resource-center/?current=siglent-manual-download"""

# TODO: Validate siglent-sds7000a inherited commands against its vendor manual and hardware.

@instrument_model("oscope", "siglent-sds7000a")
class SiglentSds7000a(GenericOscope):
    """Manual: https://www.siglent.com/na/service-support/resource-center/?current=siglent-manual-download"""

# TODO: Validate siglent-sds800x-hd inherited commands against its vendor manual and hardware.

@instrument_model("oscope", "siglent-sds800x-hd")
class SiglentSds800xHd(GenericOscope):
    """Manual: https://www.siglent.com/na/service-support/resource-center/?current=siglent-manual-download"""
