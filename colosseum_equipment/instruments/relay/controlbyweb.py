"""ControlByWeb WebRelay and X-410 HTTP relay control.

Protocol: ControlByWeb Integration & Communication Protocols Manual —
``GET /state.xml`` or ``GET /state.json`` with ``relayN=0|1|2`` and optional
``pulseTimeN``.
"""

from __future__ import annotations

import json
import re
from xml.etree import ElementTree as ET

from colosseum_equipment.exceptions import EquipmentResponseError
from colosseum_equipment.instruments.registry import instrument_model
from colosseum_equipment.instruments.relay.generic import GenericRelay


class ControlByWebRelay(GenericRelay):
    """Shared ControlByWeb GET helpers; subclasses set ``_state_path``."""

    _state_path = "state.xml"

    def _path(self, query: str = "") -> str:
        if query:
            return f"{self._state_path}?{query}"
        return self._state_path

    def set_relay(self, channel: int, enabled: bool) -> None:
        value = 1 if enabled else 0
        self._transport.write(self._path(f"relay{int(channel)}={value}"))

    def pulse_relay(self, channel: int, duration_s: float | None = None) -> None:
        n = int(channel)
        if duration_s is None:
            self._transport.write(self._path(f"relay{n}=2"))
            return
        self._transport.write(self._path(f"pulseTime{n}={duration_s:g}&relay{n}=2"))

    def measure_relay(self, channel: int) -> bool:
        body = self._transport.query(self._path())
        return self._parse_relay_state(body, int(channel))

    def _parse_relay_state(self, body: str, channel: int) -> bool:
        raise NotImplementedError


@instrument_model("relay", "controlbyweb-webrelay")
class ControlByWebWebRelay(ControlByWebRelay):
    """Classic WebRelay / WebRelay-Quad via ``state.xml``."""

    _state_path = "state.xml"

    def _parse_relay_state(self, body: str, channel: int) -> bool:
        text = body.strip()
        try:
            root = ET.fromstring(text)
        except ET.ParseError as exc:
            raise EquipmentResponseError(f"invalid WebRelay XML: {exc}") from exc
        tag = f"relay{channel}"
        node = root.find(tag)
        if node is None:
            node = root.find(f".//{tag}")
        if node is None or node.text is None:
            match = re.search(rf"<relay{channel}>([^<]+)</relay{channel}>", text, re.I)
            if not match:
                raise EquipmentResponseError(f"relay{channel} missing from state.xml")
            return match.group(1).strip() not in ("0", "0.0", "")
        return node.text.strip() not in ("0", "0.0", "")


@instrument_model("relay", "controlbyweb-x410")
class ControlByWebX410(ControlByWebRelay):
    """X-410 / X-400 series via ``state.json``."""

    _state_path = "state.json"

    def _parse_relay_state(self, body: str, channel: int) -> bool:
        try:
            data = json.loads(body)
        except json.JSONDecodeError as exc:
            raise EquipmentResponseError(f"invalid X-410 JSON: {exc}") from exc
        key = f"relay{channel}"
        if key not in data:
            raise EquipmentResponseError(f"{key} missing from state.json")
        value = data[key]
        if isinstance(value, bool):
            return value
        try:
            return int(value) != 0
        except (TypeError, ValueError) as exc:
            raise EquipmentResponseError(f"unexpected {key} value: {value!r}") from exc
