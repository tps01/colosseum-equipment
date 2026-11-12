"""Catalog models from the programming-manual spreadsheet.

Each class inherits the generic driver. Inherited commands are sent as
generic SCPI and log one warning per model and command. The class
docstring is the manual link.
"""

from __future__ import annotations

from colosseum_equipment.exceptions import EquipmentCapabilityError, EquipmentResponseError
from colosseum_equipment.instruments.dmm.generic import GenericDMM
from colosseum_equipment.instruments.dmm.keithley_dmm6500 import KeithleyDmm6500Family
from colosseum_equipment.instruments.dmm.keysight_34401a import Keysight34401A
from colosseum_equipment.instruments.registry import instrument_model

# TODO: Validate rigol-dm3058 inherited commands against its vendor manual and hardware.

@instrument_model("dmm", "rigol-dm3058")
class RigolDm3058(GenericDMM):
    """Manual: https://www.rigolna.com/support/downloads/"""

# TODO: Validate rigol-dm3068 inherited commands against its vendor manual and hardware.

@instrument_model("dmm", "rigol-dm3068")
class RigolDm3068(GenericDMM):
    """Manual: https://www.rigolna.com/support/downloads/"""

# Range/autorange/NPLC: DM858 PGC11101-1110, sections 3.17. Remaining inherited commands need review.

@instrument_model("dmm", "rigol-dm858")
class RigolDm858(GenericDMM):
    """Manual: https://www.rigolna.com/support/downloads/"""

    def _sense(self, channel: int, suffix: str, *, integrating: bool = False) -> str:
        self._require_channel(channel)
        raw = self._scpi.query("SENS:FUNC?").strip().strip('"').upper()
        function = {"VOLT": "VOLT:DC", "CURR": "CURR:DC"}.get(raw, raw)
        if function not in {"VOLT:DC", "CURR:DC", "VOLT:AC", "CURR:AC", "RES", "FRES", "CAP", "FREQ", "PER", "DIOD", "CONT", "TEMP"}:
            raise EquipmentResponseError(f"invalid DM858 function: {raw!r}")
        allowed = {"VOLT:DC", "CURR:DC", "RES", "FRES"}
        if not integrating:
            allowed |= {"VOLT:AC", "CURR:AC", "CAP"}
        if function not in allowed:
            raise EquipmentCapabilityError(f"{suffix} is unavailable for DM858 function {function}")
        return f"SENS:{function}:{suffix}"

    def set_range(self, value: float, *, channel: int = 1) -> None:
        self._scpi.write(f"{self._sense(channel, 'RANG')} {value}")

    def get_range(self, *, channel: int = 1) -> float:
        return self._scpi.query_float(f"{self._sense(channel, 'RANG')}?")

    def set_auto_range(self, enabled: bool, *, channel: int = 1) -> None:
        self._scpi.write(f"{self._sense(channel, 'RANG:AUTO')} {int(enabled)}")

    def get_auto_range(self, *, channel: int = 1) -> bool:
        return bool(int(self._scpi.query(f"{self._sense(channel, 'RANG:AUTO')}?")))

    def set_nplc(self, nplc: float, *, channel: int = 1) -> None:
        self._require_channel(channel)
        if nplc not in {0.4, 5, 20}:
            raise EquipmentCapabilityError("DM858 NPLC must be 0.4, 5 or 20")
        self._scpi.write(f"{self._sense(channel, 'NPLC', integrating=True)} {nplc}")

    def get_nplc(self, *, channel: int = 1) -> float:
        return self._scpi.query_float(f"{self._sense(channel, 'NPLC', integrating=True)}?")


# TODO: Validate siglent-sdm3045x inherited commands against its vendor manual and hardware.

@instrument_model("dmm", "siglent-sdm3045x")
class SiglentSdm3045x(GenericDMM):
    """Manual: https://www.siglent.com/na/service-support/resource-center/?current=siglent-manual-download"""

# TODO: Validate siglent-sdm3055 inherited commands against its vendor manual and hardware.

@instrument_model("dmm", "siglent-sdm3055")
class SiglentSdm3055(GenericDMM):
    """Manual: https://www.siglent.com/na/service-support/resource-center/?current=siglent-manual-download"""

# TODO: Validate siglent-sdm3065x inherited commands against its vendor manual and hardware.

@instrument_model("dmm", "siglent-sdm3065x")
class SiglentSdm3065x(GenericDMM):
    """Manual: https://www.siglent.com/na/service-support/resource-center/?current=siglent-manual-download"""


@instrument_model("dmm", "keysight-34401a")
class Keysight34401a(Keysight34401A):
    """Manual: https://www.keysight.com/us/en/assets/9018-01063/user-manuals/9018-01063.pdf"""

# TODO: Validate keysight-34460a inherited commands against its vendor manual and hardware.

@instrument_model("dmm", "keysight-34460a")
class Keysight34460a(GenericDMM):
    """Manual: https://www.keysight.com/ie/en/support/34465A/digital-multimeter-6-5-digit-truevolt-dmm.html"""

# TODO: Validate keysight-34461a inherited commands against its vendor manual and hardware.

@instrument_model("dmm", "keysight-34461a")
class Keysight34461a(GenericDMM):
    """Manual: https://www.keysight.com/ie/en/support/34465A/digital-multimeter-6-5-digit-truevolt-dmm.html"""

# TODO: Validate keysight-34465a inherited commands against its vendor manual and hardware.

@instrument_model("dmm", "keysight-34465a")
class Keysight34465a(GenericDMM):
    """Manual: https://www.keysight.com/ie/en/support/34465A/digital-multimeter-6-5-digit-truevolt-dmm.html"""

# TODO: Validate keysight-34470a inherited commands against its vendor manual and hardware.

@instrument_model("dmm", "keysight-34470a")
class Keysight34470a(GenericDMM):
    """Manual: https://www.keysight.com/ie/en/support/34465A/digital-multimeter-6-5-digit-truevolt-dmm.html"""


@instrument_model("dmm", "keithley-dmm6500")
class KeithleyDmm6500(KeithleyDmm6500Family):
    """Manual: https://www.tek.com/en/support/datasheets-manuals-software-downloads"""

# TODO: Validate keithley-dmm7510 inherited commands against its vendor manual and hardware.

@instrument_model("dmm", "keithley-dmm7510")
class KeithleyDmm7510(GenericDMM):
    """Manual: https://www.tek.com/en/support/datasheets-manuals-software-downloads"""
