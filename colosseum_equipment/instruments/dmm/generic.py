from __future__ import annotations

from typing import TYPE_CHECKING, Any

from colosseum_equipment.exceptions import EquipmentCapabilityError
from colosseum_equipment.instruments._base import ScpiInstrumentMixin
from colosseum_equipment.instruments.registry import best_effort_commands, instrument_model
from colosseum_equipment.protocols.scpi import SCPIHelper

if TYPE_CHECKING:
    from colosseum_equipment.transports.base import Transport


@instrument_model("dmm", "generic", extra_optional=("channels", "channel_count"))
@best_effort_commands
class GenericDMM(ScpiInstrumentMixin):
    def __init__(self, transport: Transport, config: dict[str, Any] | None = None) -> None:
        self._scpi = SCPIHelper(transport)
        self._config = config or {}
        self._model = str(self._config.get("model", "generic")).lower()
        self._channel_count = int(
            self._config.get("channels") or self._config.get("channel_count") or 1,
        )

    def _require_channel(self, channel: int) -> int:
        ch = int(channel)
        if ch < 1 or ch > self._channel_count:
            raise EquipmentCapabilityError(
                f"dmm model `{self._model}` does not support channel {ch} "
                f"(valid 1..{self._channel_count})",
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
        return self._scpi.query("FUNC?").strip()

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
        return self._scpi.query_float("FETCH?")

    def measure_voltage_dc(self, channel: int = 1) -> float:
        self._require_channel(channel)
        self._scpi.write("CONF:VOLT:DC")
        return self._scpi.query_float("READ?")

    def measure_voltage_ac(self, channel: int = 1) -> float:
        self._require_channel(channel)
        self._scpi.write("CONF:VOLT:AC")
        return self._scpi.query_float("READ?")

    def measure_current_dc(self, channel: int = 1) -> float:
        self._require_channel(channel)
        self._scpi.write("CONF:CURR:DC")
        return self._scpi.query_float("READ?")

    def measure_current_ac(self, channel: int = 1) -> float:
        self._require_channel(channel)
        self._scpi.write("CONF:CURR:AC")
        return self._scpi.query_float("READ?")

    def measure_resistance_4w(self, channel: int = 1) -> float:
        self._require_channel(channel)
        self._scpi.write("CONF:FRES")
        return self._scpi.query_float("READ?")

    def measure_frequency_hz(self, channel: int = 1) -> float:
        self._require_channel(channel)
        self._scpi.write("CONF:FREQ")
        return self._scpi.query_float("READ?")

    def measure_voltage(self, channel: int = 1) -> float:
        """One-shot DC voltage (sets ``CONF:VOLT:DC`` then ``READ?``)."""
        return self.measure_voltage_dc(channel)

    def measure_current(self, channel: int = 1) -> float:
        """One-shot DC current (sets ``CONF:CURR:DC`` then ``READ?``)."""
        return self.measure_current_dc(channel)

    def measure_resistance(self, channel: int = 1) -> float:
        """One-shot 2-wire resistance (sets ``CONF:RES`` then ``READ?``)."""
        self._require_channel(channel)
        self._scpi.write("CONF:RES")
        return self._scpi.query_float("READ?")
