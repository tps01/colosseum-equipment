"""CW operation on modern RF generators; vector functions are not implied.

Manuals: Keysight PSG E8257D/E8267D/E8663D SCPI reference; MXG N5183A/B;
ESG E4400B family; R&S SMB100A/SMA100B operating manuals.
"""
from __future__ import annotations

from colosseum_equipment.exceptions import EquipmentCapabilityError
from colosseum_equipment.instruments._capabilities import supported_commands
from colosseum_equipment.instruments.registry import instrument_model
from colosseum_equipment.instruments.vsg.generic import GenericVSG


@instrument_model(
    "vsg", "keysight-e8257d", "keysight-e8257c", "keysight-e8241a", "keysight-e4422b",
    "keysight-n5183a", "keysight-n5183b", "rohde-smb100a", "rohde-sma100b",
)
@supported_commands(
    "set_frequency", "set_power", "set_output", "measure_frequency", "measure_power_dbm",
    "measure_output_state", "preset", "wait_complete", "set_ref_source",
)
class CwSignalGenerator(GenericVSG):
    """Common documented CW subset; no ARB, modulation or option-dependent sweeps.

    Frequency/power readback returns programmed settings, not a measured RF
    output. The connected analyzer/power meter supplies independent evidence.
    """

    def set_frequency(self, frequency: float) -> None:
        self._scpi.write(f"FREQ {frequency:.6f}")

    def set_power(self, power_dbm: float) -> None:
        self._scpi.write("UNIT:POW DBM")
        self._scpi.write(f"POW {power_dbm:.6f}")

    def measure_frequency(self) -> float:
        return self._scpi.query_float("FREQ?")

    def measure_power_dbm(self) -> float:
        self._scpi.write("UNIT:POW DBM")
        return self._scpi.query_float("POW?")

    def set_ref_source(self, source: str) -> None:
        token = source.strip().upper()
        token = {"INTERNAL": "INT", "EXTERNAL": "EXT"}.get(token, token)
        if token not in {"INT", "EXT"}:
            raise EquipmentCapabilityError(f"unsupported reference source {source!r}")
        self._scpi.write(f"ROSC:SOUR {token}")


@instrument_model("vsg", "rohde-smiq04b", "keysight-8648c", "keysight-83650l")
@supported_commands(
    "set_frequency", "set_power", "set_output", "measure_frequency", "measure_output_state",
    "preset", "wait_complete",
)
class LegacyScpiCw(GenericVSG):
    """SCPI personality only; frequency/level/output controls, no modulation.

    References: SMIQ operating manual vol.2 1125.5610.12-11, SOURce/OUTPut;
    8648A/B/C/D operation guide, ch.2 SCPI; 8360 L user guide, SCPI summary.
    Source URLs and dialect decisions: docs/equipment/inventory-manual-analysis.md.
    """

    def set_power(self, power_dbm: float) -> None:
        self._scpi.write(f"POW {power_dbm:.6f}DBM")

    def measure_frequency(self) -> float:
        return self._scpi.query_float("FREQ:CW?")


@instrument_model("vsg", "anritsu-mg3692c")
@supported_commands("set_frequency", "set_power", "set_output", "preset", "wait_complete")
class AnritsuMg3692c(GenericVSG):
    """10370-10375 MG369xC SCPI Programming Manual, frequency/power/output.

    Select SCPI on the front panel first; the native language is incompatible.
    """

    def set_frequency(self, frequency: float) -> None:
        self._scpi.write("FREQ:MODE FIX")
        self._scpi.write(f"FREQ {frequency:.6f}HZ")

    def set_power(self, power_dbm: float) -> None:
        self._scpi.write("POW:MODE FIX")
        self._scpi.write(f"POW {power_dbm:.6f}DBM")


@instrument_model("vsg", "tektronix-tsg4106a")
@supported_commands("set_frequency", "set_power", "set_output", "measure_frequency", "measure_output_state")
class TekTsg4106a(GenericVSG):
    """077-1079-00 pp.2-17, 2-24, 2-28: Type-N RF output only.

    https://download.tek.com/manual/TSG4100A-Series-Programmer-Manual-EN-EN.pdf
    AMPR query units depend on instrument state, so dBm readback is excluded.
    """

    def set_frequency(self, frequency: float) -> None:
        self._scpi.write(f"FREQ {frequency:.6f}")

    def set_power(self, power_dbm: float) -> None:
        self._scpi.write(f"AMPR {power_dbm:.6f} DBM")

    def set_output(self, enabled: bool) -> None:
        self._scpi.write(f"ENBR {int(enabled)}")

    def measure_frequency(self) -> float:
        return self._scpi.query_float("FREQ?")

    def measure_output_state(self) -> bool:
        return bool(int(self._scpi.query("ENBR?")))
