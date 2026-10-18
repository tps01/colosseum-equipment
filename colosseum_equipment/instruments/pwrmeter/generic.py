from __future__ import annotations

from typing import TYPE_CHECKING, Any

from colosseum_equipment.exceptions import EquipmentCapabilityError
from colosseum_equipment.instruments._base import ScpiInstrumentMixin
from colosseum_equipment.instruments.registry import best_effort_commands, instrument_model
from colosseum_equipment.protocols.scpi import SCPIHelper

if TYPE_CHECKING:
    from colosseum_equipment.transports.base import Transport


@instrument_model("pwrmeter", "generic", extra_optional=("frequency", "channels"))
@best_effort_commands
class GenericPwrMeter(ScpiInstrumentMixin):
    """Generic SCPI RF power meter."""

    _model = "generic"

    def __init__(self, transport: Transport, config: dict[str, Any]) -> None:
        self._scpi = SCPIHelper(transport)
        self._config = config
        self._model = str(config.get("model", "generic")).lower()
        self._channel_count = int(
            config.get("channels") or config.get("channel_count") or 1,
        )
        if "frequency" in config:
            self.set_frequency(float(config["frequency"]))

    def _require_channel(self, channel: int) -> int:
        ch = int(channel)
        if ch < 1 or ch > self._channel_count:
            raise EquipmentCapabilityError(
                f"pwrmeter model `{self._model}` does not support channel {ch} "
                f"(valid 1..{self._channel_count})",
            )
        return ch

    def _sensor_prefix(self, channel: int) -> str:
        ch = self._require_channel(channel)
        return "" if ch == 1 else f"SENS{ch}:"

    def set_frequency(self, frequency_hz: float, *, channel: int = 1) -> None:
        prefix = self._sensor_prefix(channel)
        self._scpi.write(f"{prefix}FREQ {frequency_hz:.6f}")

    def set_averaging_count(self, count: int, *, channel: int = 1) -> None:
        prefix = self._sensor_prefix(channel)
        self._scpi.write(f"{prefix}AVER:COUN {int(count)}")

    def set_offset_db(self, offset_db: float, *, channel: int = 1) -> None:
        prefix = self._sensor_prefix(channel)
        self._scpi.write(f"{prefix}CORR:OFFS {offset_db:.3f}")

    def measure_power_dbm(self, *, channel: int = 1) -> float:
        prefix = self._sensor_prefix(channel)
        return self._scpi.query_float(f"{prefix}MEAS:POW?")

    def measure_power(self, *, channel: int = 1) -> float:
        """Measured power in dBm (alias of :meth:`measure_power_dbm`)."""
        return self.measure_power_dbm(channel=channel)

    def measure_power_w(self, *, channel: int = 1) -> float:
        dbm = self.measure_power_dbm(channel=channel)
        return 10 ** ((dbm - 30.0) / 10.0)

    def measure_power_peak_dbm(self, *, channel: int = 1) -> float:
        prefix = self._sensor_prefix(channel)
        return self._scpi.query_float(f"{prefix}FETC:PEAK?")

    def measure_power_avg_dbm(self, *, channel: int = 1) -> float:
        prefix = self._sensor_prefix(channel)
        return self._scpi.query_float(f"{prefix}FETC:AVER?")

    def zero_sensor(self, *, channel: int = 1) -> None:
        prefix = self._sensor_prefix(channel)
        self._scpi.write(f"{prefix}CAL:ZERO")

    def calibrate(self, *, channel: int = 1) -> None:
        prefix = self._sensor_prefix(channel)
        self._scpi.write(f"{prefix}CAL:AUTO ONCE")

    def preset(self) -> None:
        self._scpi.write("*RST")
