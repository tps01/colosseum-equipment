from __future__ import annotations

from typing import TYPE_CHECKING, Any

from colosseum_equipment.exceptions import EquipmentCapabilityError
from colosseum_equipment.instruments._base import ScpiInstrumentMixin
from colosseum_equipment.instruments.registry import best_effort_commands, instrument_model
from colosseum_equipment.protocols.scpi import SCPIHelper

if TYPE_CHECKING:
    from colosseum_equipment.transports.base import Transport


@instrument_model("dmm", "generic", extra_optional=("channels", "channel_count", "baudrate"))
@best_effort_commands
class GenericDMM(ScpiInstrumentMixin):
    def __init__(self, transport: Transport, config: dict[str, Any] | None = None) -> None:
        self._scpi = SCPIHelper(transport)
        self._config = config or {}
        self._model = str(self._config.get("model", "generic")).lower()
        from colosseum_equipment.instruments._channels import resolve_channel_count

        self._channel_count = resolve_channel_count(self._config)

    def _require_channel(self, channel: int) -> int:
        ch = int(channel)
        if ch < 1 or ch > self._channel_count:
            raise EquipmentCapabilityError(
                f"dmm model `{self._model}` does not support channel {ch} (valid 1..{self._channel_count})",
            )
        return ch

    def set_function(self, function: str, *, channel: int = 1) -> None:
        self._require_channel(channel)
        func = function.strip().upper()
        if not func.startswith(("VOLT", "CURR", "RES", "FREQ", "DIOD", "CONT", "CAP")):
            func = f"VOLT:{func}" if func in ("DC", "AC") else func
        self._scpi.write(f"CONF:{func}")

    def get_function(self, *, channel: int = 1) -> str:
        self._require_channel(channel)
        # Prefer SENSe:FUNCtion? (34401A and most bench DMMs); strip quotes if present.
        return self._scpi.query("SENS:FUNC?").strip().strip('"')

    def set_range(self, value: float, *, channel: int = 1) -> None:
        self._require_channel(channel)
        self._scpi.write(f"RANG {value}")

    def get_range(self, *, channel: int = 1) -> float:
        self._require_channel(channel)
        return self._scpi.query_float("RANG?")

    def set_auto_range(self, enabled: bool, *, channel: int = 1) -> None:
        self._require_channel(channel)
        self._scpi.write(f"RANG:AUTO {'ON' if enabled else 'OFF'}")

    def get_auto_range(self, *, channel: int = 1) -> bool:
        self._require_channel(channel)
        return bool(int(float(self._scpi.query("RANG:AUTO?"))))

    def set_nplc(self, nplc: float, *, channel: int = 1) -> None:
        self._require_channel(channel)
        self._scpi.write(f"NPLC {nplc}")

    def get_nplc(self, *, channel: int = 1) -> float:
        self._require_channel(channel)
        return self._scpi.query_float("NPLC?")

    def set_aperture_s(self, seconds: float, *, channel: int = 1) -> None:
        self._require_channel(channel)
        self._scpi.write(f"APER {seconds}")

    def get_aperture_s(self, *, channel: int = 1) -> float:
        self._require_channel(channel)
        return self._scpi.query_float("APER?")

    def set_auto_zero(self, enabled: bool, *, channel: int = 1) -> None:
        self._require_channel(channel)
        self._scpi.write(f"ZERO:AUTO {'ON' if enabled else 'OFF'}")

    def get_auto_zero(self, *, channel: int = 1) -> bool:
        self._require_channel(channel)
        return bool(int(float(self._scpi.query("ZERO:AUTO?"))))

    def set_input_z(self, ohms: float, *, channel: int = 1) -> None:
        self._require_channel(channel)
        self._scpi.write("INP:IMP:AUTO OFF")
        self._scpi.write(f"INP:IMP {ohms}")

    def get_input_z(self, *, channel: int = 1) -> float:
        self._require_channel(channel)
        return self._scpi.query_float("INP:IMP?")

    def set_trigger_source(self, source: str, *, channel: int = 1) -> None:
        self._require_channel(channel)
        self._scpi.write(f"TRIG:SOUR {source.upper()}")

    def get_trigger_source(self, *, channel: int = 1) -> str:
        self._require_channel(channel)
        return self._scpi.query("TRIG:SOUR?").strip()

    def initiate(self, *, channel: int = 1) -> None:
        self._require_channel(channel)
        self._scpi.write("INIT")

    def fetch(self, *, channel: int = 1) -> float:
        self._require_channel(channel)
        return self._scpi.query_float("FETC?")

    def _measure(self, function: str, channel: int) -> float:
        self._require_channel(channel)
        actual = self.get_function(channel=channel).strip().strip('"').upper()
        for full, short in (("VOLTAGE", "VOLT"), ("CURRENT", "CURR"),
                            ("FRESISTANCE", "FRES"), ("RESISTANCE", "RES"), ("FREQUENCY", "FREQ")):
            actual = actual.replace(full, short)
        if actual in {"VOLT", "CURR"}:
            actual += ":DC"
        if actual != function:
            raise EquipmentCapabilityError(
                f"configured DMM function is {actual!r}; call set_function({function!r}) before acquisition",
            )
        return self.fetch(channel=channel)

    def measure_voltage_dc(self, channel: int = 1) -> float:
        """Fetch an existing VOLT:DC result; configure and initiate explicitly first."""
        return self._measure("VOLT:DC", channel)

    def measure_voltage_ac(self, channel: int = 1) -> float:
        """Fetch an existing VOLT:AC result; configure and initiate explicitly first."""
        return self._measure("VOLT:AC", channel)

    def measure_current_dc(self, channel: int = 1) -> float:
        """Fetch an existing CURR:DC result; configure and initiate explicitly first."""
        return self._measure("CURR:DC", channel)

    def measure_current_ac(self, channel: int = 1) -> float:
        """Fetch an existing CURR:AC result; configure and initiate explicitly first."""
        return self._measure("CURR:AC", channel)

    def measure_resistance_4w(self, channel: int = 1) -> float:
        """Fetch an existing FRES result; configure and initiate explicitly first."""
        return self._measure("FRES", channel)

    def measure_frequency_hz(self, channel: int = 1) -> float:
        """Fetch an existing FREQ result; configure and initiate explicitly first."""
        return self._measure("FREQ", channel)

    def measure_voltage(self, channel: int = 1) -> float:
        """Fetch DC voltage from the existing acquisition."""
        return self.measure_voltage_dc(channel)

    def measure_current(self, channel: int = 1) -> float:
        """Fetch DC current from the existing acquisition."""
        return self.measure_current_dc(channel)

    def measure_resistance(self, channel: int = 1) -> float:
        """Fetch an existing RES result; configure and initiate explicitly first."""
        return self._measure("RES", channel)
