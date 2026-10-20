"""ENA, PNA and ZNLE trace acquisition using their selected-measurement dialects.

Manuals: Keysight ENA/PNA online programming help and R&S ZNL/ZNLE
1178.5966.02. CSV contains the actual stimulus axis; single traces are not S2P.
"""
from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from colosseum_equipment._paths import resolve_artifact_path
from colosseum_equipment.evidence import record_artifact
from colosseum_equipment.exceptions import EquipmentCapabilityError, EquipmentResponseError
from colosseum_equipment.instruments._capabilities import supported_commands
from colosseum_equipment.instruments.registry import instrument_model
from colosseum_equipment.instruments.vna.generic import GenericVna
from colosseum_equipment.instruments.vna.trace_export import parse_vna_trace_values, write_trace_csv

if TYPE_CHECKING:
    from pathlib import Path

    from colosseum_equipment.transports.base import Transport

_COMMANDS = (
    "preset", "set_start_frequency", "set_stop_frequency", "set_points", "single_sweep",
    "wait_complete", "abort", "set_averaging_count", "toggle_averaging", "set_if_bw",
    "set_tx_power", "set_trace_parameters", "save_trace_data", "measure_s11_magnitude",
    "measure_s21_magnitude", "measure_s_parameter",
)


class InventoryVna(GenericVna):
    """Shared channel-aware controls, strict axis validation and scalar trace measures."""

    def _channel(self) -> int:
        channel = int(self._config.get("channel", 1))
        if channel < 1:
            raise EquipmentCapabilityError("VNA measurement channel must be positive")
        return channel

    def _sens(self) -> str:
        return f"SENS{self._channel()}"

    def _calc(self) -> str:
        return f"CALC{self._channel()}"

    def _init(self, channel: int | None = None) -> str:
        return f"INIT{channel or self._channel()}"

    def set_start_frequency(self, frequency_hz: float) -> None:
        self._scpi.write(f"{self._sens()}:FREQ:STAR {frequency_hz:.6f}")

    def set_stop_frequency(self, frequency_hz: float) -> None:
        self._scpi.write(f"{self._sens()}:FREQ:STOP {frequency_hz:.6f}")

    def set_points(self, count: int) -> None:
        if count < 2:
            raise ValueError("VNA sweep requires at least two points")
        self._scpi.write(f"{self._sens()}:SWE:POIN {count}")

    def set_tx_power(self, power_dbm: float, *, port: int = 1) -> None:
        if port != 1:
            raise EquipmentCapabilityError("per-port source-power control is not qualified")
        self._scpi.write(f"SOUR{self._channel()}:POW {power_dbm:.3f}")

    def _validate_trace(self, trace: int, parameter: str, fmt: str) -> tuple[str, str]:
        if trace < 1:
            raise ValueError("trace number must be positive")
        param, form = parameter.upper(), fmt.upper()
        if param not in {"S11", "S21", "S12", "S22"}:
            raise EquipmentCapabilityError("qualified S-parameters are S11, S21, S12 and S22")
        if form not in {"MLOG", "MLIN", "PHAS", "REAL", "IMAG"}:
            raise EquipmentCapabilityError(f"unsupported scalar trace format {fmt!r}")
        return param, form

    def _select_trace(self, trace: int) -> None:
        self._scpi.write(f"{self._calc()}:PAR{trace}:SEL")

    def set_trace_parameters(self, trace: int, parameter: str, format: str) -> None:
        param, form = self._validate_trace(trace, parameter, format)
        self._scpi.write(f"{self._calc()}:PAR{trace}:DEF {param}")
        self._select_trace(trace)
        self._scpi.write(f"{self._calc()}:FORM {form}")

    def _sweep_once(self) -> None:
        self._scpi.write(f"{self._init()}:CONT OFF")
        self._scpi.write(f"{self._init()}:IMM")
        self.wait_complete()

    def single_sweep(self) -> None:
        averaging = bool(int(float(self._scpi.query(f"{self._sens()}:AVER?"))))
        count = int(self._scpi.query_float(f"{self._sens()}:AVER:COUN?")) if averaging else 1
        if count < 1 or count > 65536:
            raise EquipmentResponseError(f"invalid averaging count {count}")
        if averaging:
            self._scpi.write(f"{self._sens()}:AVER:CLE")
        for _ in range(count):
            self._sweep_once()

    def wait_complete(self) -> None:
        if self._scpi.query("*OPC?") != "1":
            raise EquipmentResponseError("VNA did not report operation completion")

    def _query_frequencies(self) -> list[float]:
        return parse_vna_trace_values(self._scpi.query(f"{self._sens()}:FREQ:DATA?"))

    def _trace_values(self, trace: int) -> list[float]:
        self._select_trace(trace)
        self._scpi.write("FORM:DATA ASC")
        return parse_vna_trace_values(self._scpi.query(f"{self._calc()}:DATA:FDAT?"))

    def save_trace_data(
        self, path: str, *, trace: int = 1, file_format: str = "csv", parameter: str = "S11",
    ) -> Path:
        if file_format.lower() != "csv" or path.lower().endswith((".s1p", ".s2p")):
            raise EquipmentCapabilityError("formatted trace export is CSV, not a full Touchstone matrix")
        # Set the requested parameter so an existing S21 trace cannot be mislabeled S11.
        self.set_trace_parameters(trace, parameter, "MLOG")
        self.single_sweep()
        values = self._trace_values(trace)
        frequencies = self._query_frequencies()
        if not values or len(values) != len(frequencies):
            raise EquipmentResponseError("VNA stimulus/data length mismatch; refusing invented axis")
        if any(not math.isfinite(v) or abs(v) >= 9e37 for v in values):
            raise EquipmentResponseError("invalid VNA trace value")
        if any(not math.isfinite(f) or f <= 0 for f in frequencies):
            raise EquipmentResponseError("invalid VNA stimulus frequency")
        artifact = resolve_artifact_path(path)
        write_trace_csv(artifact, frequencies, values)
        record_artifact(
            domain="equipment", command="save_trace_data", key=f"vna_trace_{trace}_{parameter.lower()}",
            path=artifact, value={"trace": trace, "parameter": parameter, "units": "dB", "points": len(values)},
        )
        return artifact

    def _measure_trace_peak(self, trace: int, parameter: str, fmt: str) -> float:
        self.set_trace_parameters(trace, parameter, fmt)
        self.single_sweep()
        values = self._trace_values(trace)
        if not values or any(not math.isfinite(v) or abs(v) >= 9e37 for v in values):
            raise EquipmentResponseError("empty or invalid VNA trace")
        return max(values)


@instrument_model("vna", "keysight-e5071b", "keysight-e5062a")
@supported_commands(*_COMMANDS)
class KeysightEna(InventoryVna):
    """Manual: https://helpfiles.keysight.com/csg/e5071c/programming/programming.htm

    ENA uses a bus trigger; unlike PNA, INIT:IMM is not the sweep command.
    """

    def _sweep_once(self) -> None:
        self._scpi.write("TRIG:SOUR BUS")
        self._scpi.write("TRIG:AVER OFF")
        self._scpi.write(f"{self._init()}:CONT ON")
        self._scpi.write("TRIG:SING")
        self.wait_complete()

    def _trace_values(self, trace: int) -> list[float]:
        values = super()._trace_values(trace)
        # ENA FDATA is primary/secondary pairs even for scalar display formats.
        if len(values) % 2:
            raise EquipmentResponseError("ENA formatted trace must contain primary/secondary pairs")
        return values[::2]


@instrument_model("vna", "keysight-n5245b", "keysight-n5247b", "keysight-n5222b")
@supported_commands(*_COMMANDS)
class KeysightPna(InventoryVna):
    """Manual: https://helpfiles.keysight.com/csg/N52xxB/Programming/Programming_Guide.htm

    Trace numbers select existing PNA measurement numbers; create measurements
    on the instrument before configuring them through this subset.
    """

    def _sweep_once(self) -> None:
        # PNA INIT:CONT is global, not an indexed channel setting. Arm just the
        # configured channel via its sweep mode; require internal triggers.
        # Keysight PNA Initiate / Sense:Sweep / Trigger command references.
        self._scpi.write("TRIG:SOUR IMM")
        self._scpi.write(f"{self._sens()}:SWE:MODE SING")
        self.wait_complete()

    def _select_trace(self, trace: int) -> None:
        self._scpi.write(f"{self._calc()}:PAR:MNUM {trace}")

    def set_trace_parameters(self, trace: int, parameter: str, format: str) -> None:
        param, form = self._validate_trace(trace, parameter, format)
        self._select_trace(trace)
        self._scpi.write(f'{self._calc()}:PAR:MOD:EXT "{param}"')
        self._scpi.write(f"{self._calc()}:FORM {form}")

    def _trace_values(self, trace: int) -> list[float]:
        self._select_trace(trace)
        self._scpi.write("FORM:DATA ASC")
        return parse_vna_trace_values(self._scpi.query(f"{self._calc()}:DATA? FDATA"))

    def _query_frequencies(self) -> list[float]:
        return parse_vna_trace_values(self._scpi.query(f"{self._sens()}:X?"))


@instrument_model("vna", "rohde-znle6")
@supported_commands(*_COMMANDS)
class RohdeZnle(InventoryVna):
    """Manual: https://www.rohde-schwarz.com/manual/znle

    COL_trcN names are owned by this driver and reassigned on configuration.
    """

    def _select_trace(self, trace: int) -> None:
        self._scpi.write(f"{self._calc()}:PAR:SEL 'COL_trc{trace}'")

    def set_trace_parameters(self, trace: int, parameter: str, format: str) -> None:
        param, form = self._validate_trace(trace, parameter, format)
        self._scpi.write(f"{self._calc()}:PAR:SDEF 'COL_trc{trace}','{param}'")
        self._select_trace(trace)
        self._scpi.write(f"{self._calc()}:FORM {form}")

    def _trace_values(self, trace: int) -> list[float]:
        self._select_trace(trace)
        self._scpi.write("FORM ASC")
        return parse_vna_trace_values(self._scpi.query(f"{self._calc()}:DATA? FDAT"))

    def _query_frequencies(self) -> list[float]:
        return parse_vna_trace_values(self._scpi.query(f"{self._calc()}:DATA:STIM?"))


@instrument_model("vna", "keysight-e8362b")
@supported_commands(*_COMMANDS)
class KeysightPnaLegacy(KeysightPna):
    """Legacy PNA uses PAR:MOD, before B-series extended measurement syntax."""

    def set_trace_parameters(self, trace: int, parameter: str, format: str) -> None:
        param, form = self._validate_trace(trace, parameter, format)
        self._select_trace(trace)
        self._scpi.write(f"{self._calc()}:PAR:MOD {param}")
        self._scpi.write(f"{self._calc()}:FORM {form}")


@instrument_model("vna", "keysight-n9915a", "keysight-n9917b")
@supported_commands(*_COMMANDS)
class KeysightFieldFox(InventoryVna):
    """FieldFox NA mode with sweep averaging, one scalar value per trace point.

    Manual: https://helpfiles.keysight.com/csg/FFProgrammingHelpWebHelp/A_NA_Mode_Commands.htm
    Requires the NA option. Mode selection changes the instrument's global mode.
    """

    def __init__(self, transport: Transport, config: dict[str, Any]) -> None:
        if int(config.get("channel", 1)) != 1:
            raise EquipmentCapabilityError("FieldFox exposes one NA measurement channel")
        super().__init__(transport, config)
        self._average_count = 1
        self._scpi.write('INST:SEL "NA"')
        self.wait_complete()

    def _sens(self) -> str:
        return "SENS"

    def _calc(self) -> str:
        return "CALC"

    def _init(self, channel: int | None = None) -> str:
        return "INIT"

    def set_if_bw(self, bandwidth_hz: float) -> None:
        self._scpi.write(f"BWID {bandwidth_hz:.6f}")

    def set_tx_power(self, power_dbm: float, *, port: int = 1) -> None:
        if port != 1:
            raise EquipmentCapabilityError("FieldFox NA source power is global")
        self._scpi.write(f"SOUR:POW {power_dbm:.3f}")

    def set_averaging_count(self, count: int) -> None:
        if not 1 <= count <= 10000:
            raise ValueError("FieldFox averaging count is 1..10000")
        self._average_count = count
        self._scpi.write(f"SENS:AVER:COUN {count}")

    def toggle_averaging(self, enabled: bool) -> None:
        self._scpi.write(f"SENS:AVER:COUN {self._average_count if enabled else 1}")

    def single_sweep(self) -> None:
        count = int(self._scpi.query_float("SENS:AVER:COUN?"))
        if not 1 <= count <= 10000:
            raise EquipmentResponseError("invalid FieldFox averaging count")
        self._scpi.write("TRIG:SOUR IMM")
        self._scpi.write("SENS:AVER:MODE SWEEP")
        self._scpi.write("SENS:AVER:CLE")
        for _ in range(count):
            self._sweep_once()
