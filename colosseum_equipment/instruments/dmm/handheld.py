"""Read-only optical-serial display queries for Keysight and Fluke handhelds.

Protocol documentation / original wire observations:
https://sigrok.org/wiki/Agilent_U12xxx_series
https://mjoldfield.com/atelier/2011/06/agilent-macos.html
Requires the optical USB cable and explicit serial baudrate in configuration.
"""
from __future__ import annotations

import math
import re
from typing import TYPE_CHECKING, Any

from colosseum_equipment.exceptions import EquipmentCapabilityError, EquipmentResponseError
from colosseum_equipment.instruments.dmm.generic import GenericDMM

from colosseum_equipment.instruments._capabilities import supported_commands
from colosseum_equipment.instruments.dmm.bench import BenchDmm
from colosseum_equipment.instruments.registry import instrument_model


if TYPE_CHECKING:
    from colosseum_equipment.transports.base import Transport

@instrument_model("dmm", "keysight-u1252a", "keysight-u1272a")
@supported_commands("fetch", "get_function")
class KeysightHandheld(BenchDmm):
    """Fetch the primary display value and query its raw mode/unit descriptor.

    No remote measurement-mode changes or fresh-conversion guarantees. CONF?
    uses a handheld descriptor such as V,0,DC, not bench DMM SCPI function syntax.
    Read both function and value; native display units are not relabeled as SI.
    """

    def get_function(self, *, channel: int = 1) -> str:
        self._require_channel(channel)
        return self._scpi.query("CONF?").strip('\"')


# Native 189 display units from RemoteSpec89_18X; QM is not in base units.
_LEGACY_UNITS = {
    "OHMS": (1.0, "OHM"), "KOHMS": (1e3, "OHM"), "MOHMS": (1e6, "OHM"),
    "NS": (1e-9, "SIE"), "FARADS": (1.0, "F"), "NFARADS": (1e-9, "F"),
    "UFARADS": (1e-6, "F"), "MFARADS": (1e-3, "F"),
    "HZ": (1.0, "HZ"), "KHZ": (1e3, "HZ"), "MHZ": (1e6, "HZ"),
    "DEGC": (1.0, "CEL"), "DEGF": (1.0, "FAR"), "DBM": (1.0, "DBM"),
    "DBV": (1.0, "DBV"), "%": (1.0, "PCT"), "MS": (1e-3, "S"),
}
for _suffix in ("AC", "DC", "AC+DC"):
    for _prefix, _factor in (("", 1.0), ("M", 1e-3), ("U", 1e-6)):
        _LEGACY_UNITS[f"{_prefix}A{_suffix}"] = (_factor, f"A{_suffix}")
    for _prefix, _factor in (("", 1.0), ("M", 1e-3)):
        _LEGACY_UNITS[f"{_prefix}V{_suffix}"] = (_factor, f"V{_suffix}")


@instrument_model("dmm", "fluke-289", "fluke-189")
@supported_commands("fetch", "get_function")
class FlukeHandheld(GenericDMM):
    """Native read-only QM, CR ACK + CR data; 289 and 189 reply dialects differ.

    Fluke 287/289 Remote Interface Specification, QM, pp.4-6:
    https://btbm.ch/assets/uploads/Fluke28xRemoteInterfaceSpecifications.pdf
    Fluke 189/187 RemoteSpec89_18X, QM (manufacturer-authored archive):
    https://photonicsguy.ca/reference/flukemeter
    Reads the primary display, including held/relative values, not a new conversion.
    """

    def __init__(self, transport: Transport, config: dict[str, Any]) -> None:
        expected = 9600 if str(config.get("model")).lower() == "fluke-189" else 115200
        if config.get("driver") != "serial" or config.get("baudrate") != expected:
            raise EquipmentCapabilityError(f"use driver=serial and baudrate={expected} with the IR adapter")
        if int(config.get("channels") or config.get("channel_count") or 1) != 1:
            raise EquipmentCapabilityError("Fluke handheld exposes one primary display")
        if not callable(getattr(transport, "write_bytes", None)) or not callable(getattr(transport, "read_until", None)):
            raise EquipmentCapabilityError("Fluke QM requires a raw serial transport")
        super().__init__(transport, config)

    def _frame(self) -> str:
        raw = str(self._scpi._transport.read_until(b"\r"))  # type: ignore[attr-defined]
        if not raw.endswith("\r"):
            raise EquipmentResponseError("incomplete Fluke CR-terminated response")
        return raw.strip()

    def _reading(self, channel: int) -> tuple[float, str]:
        self._require_channel(channel)
        self._scpi._transport.write_bytes(b"QM\r")  # type: ignore[attr-defined]
        ack = self._frame()
        if ack != "0":
            raise EquipmentResponseError(f"Fluke QM acknowledgement {ack!r} (1=syntax, 2=execution, 5=no data)")
        raw = self._frame()
        if self._model == "fluke-189":
            match = re.fullmatch(r"QM,\s*([-+]\d+(?:\.\d*)?(?:[Ee][-+]?\d+)?)\s+(.+)", raw)
            if match is None:
                raise EquipmentResponseError(f"invalid or out-of-range Fluke display {raw!r}")
            unit = "".join(match[2].upper().split())
            if unit not in _LEGACY_UNITS:
                raise EquipmentCapabilityError(f"unsupported Fluke 189 display unit {match[2]!r}")
            factor, descriptor = _LEGACY_UNITS[unit]
            value = float(match[1]) * factor
        else:
            parts = [v.strip() for v in raw.split(",")]
            if len(parts) != 4 or parts[2].upper() != "NORMAL":
                raise EquipmentResponseError(f"invalid Fluke primary measurement {raw!r}")
            try:
                value = float(parts[0])
            except ValueError as exc:
                raise EquipmentResponseError(f"invalid Fluke primary value {raw!r}") from exc
            descriptor = parts[1].upper()
            if not descriptor or descriptor == "NONE":
                raise EquipmentCapabilityError("Fluke reading has no measurement unit")
        if not math.isfinite(value) or abs(value) >= 9e37:
            raise EquipmentResponseError("invalid/overload Fluke primary value")
        return value, descriptor

    def fetch(self, *, channel: int = 1) -> float:
        return self._reading(channel)[0]

    def get_function(self, *, channel: int = 1) -> str:
        return self._reading(channel)[1]
