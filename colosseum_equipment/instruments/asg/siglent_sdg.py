"""SDG1000X/2000X/6000X/7000A: PG02_E05B, sections 3.3–3.7.

https://siglentna.com/wp-content/uploads/dlm_uploads/2023/08/SDG_Programming-Guide_PG02-E05B.pdf
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from colosseum_equipment.exceptions import EquipmentCapabilityError, EquipmentResponseError
from colosseum_equipment.instruments._channels import resolve_channel_count
from colosseum_equipment.instruments.asg.generic import GenericASG

if TYPE_CHECKING:
    from colosseum_equipment.transports.base import Transport


class SiglentSdg(GenericASG):
    """Basic-wave controls; waveform-specific limits remain instrument settings."""

    def __init__(self, transport: Transport, config: dict[str, Any]) -> None:
        if resolve_channel_count(config) not in (1, 2):
            raise EquipmentCapabilityError("SDG supports channels 1 and 2")
        super().__init__(transport, config)

    def _basic(self, channel: int, parameter: str, value: str | float) -> None:
        ch = self._require_channel(channel)
        self._scpi.write(f"C{ch}:BSWV {parameter},{value}")

    def set_frequency(self, frequency: float, *, channel: int = 1) -> None:
        self._basic(channel, "FRQ", frequency)

    def set_waveform(self, waveform: str, *, channel: int = 1) -> None:
        shapes = {"sine": "SINE", "square": "SQUARE", "ramp": "RAMP", "pulse": "PULSE", "noise": "NOISE", "arb": "ARB"}
        name = waveform.strip().lower()
        if name not in shapes:
            raise EquipmentCapabilityError(f"unsupported SDG waveform {waveform!r}")
        self._basic(channel, "WVTP", shapes[name])

    def set_amplitude_vpp(self, vpp: float, *, channel: int = 1) -> None:
        self._basic(channel, "AMP", vpp)

    def set_amplitude_vrms(self, vrms: float, *, channel: int = 1) -> None:
        self._basic(channel, "AMPVRMS", vrms)

    def set_offset_v(self, offset_v: float, *, channel: int = 1) -> None:
        self._basic(channel, "OFST", offset_v)

    def set_duty_cycle_pct(self, pct: float, *, channel: int = 1) -> None:
        self._basic(channel, "DUTY", pct)

    def set_pulse_period(self, period_s: float, *, channel: int = 1) -> None:
        self._basic(channel, "PERI", period_s)

    def set_pulse_width(self, width_s: float, *, channel: int = 1) -> None:
        self._basic(channel, "WIDTH", width_s)

    def set_output(self, enabled: bool, *, channel: int = 1) -> None:
        ch = self._require_channel(channel)
        self._scpi.write(f"C{ch}:OUTP {'ON' if enabled else 'OFF'}")

    def set_load_ohms(self, ohms: float, *, channel: int = 1) -> None:
        ch = self._require_channel(channel)
        if ohms != math.inf and not 50 <= ohms <= 100000:
            raise EquipmentCapabilityError("SDG load must be 50..100000 ohms or positive infinity (HiZ)")
        value = "HZ" if ohms == math.inf else str(ohms)
        self._scpi.write(f"C{ch}:OUTP LOAD,{value}")

    def get_load_ohms(self, *, channel: int = 1) -> float:
        ch = self._require_channel(channel)
        raw = self._scpi.query(f"C{ch}:OUTP?").strip()
        fields = raw.upper().split(",")
        try:
            if not fields[0].startswith(f"C{ch}:OUTP "):
                raise ValueError("wrong channel/header")
            load = fields[fields.index("LOAD") + 1].strip()
            value = math.inf if load == "HZ" else float(load)
            if value != math.inf and not 50 <= value <= 100000:
                raise ValueError("invalid load")
        except (ValueError, IndexError) as exc:
            raise EquipmentResponseError(f"invalid SDG output reply: {raw!r}") from exc
        return value

    def set_modulation_state(self, enabled: bool, *, channel: int = 1) -> None:
        ch = self._require_channel(channel)
        self._scpi.write(f"C{ch}:MDWV STATE,{'ON' if enabled else 'OFF'}")

    def set_burst_state(self, enabled: bool, *, channel: int = 1) -> None:
        ch = self._require_channel(channel)
        self._scpi.write(f"C{ch}:BTWV STATE,{'ON' if enabled else 'OFF'}")
