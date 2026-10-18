"""Sprint E: attn, rfswitch, relay, dio, serial API depth."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from colosseum_equipment.exceptions import EquipmentCapabilityError
from colosseum_equipment.instruments.factory import build_instrument
from colosseum_equipment.instruments.rfswitch._normalize import normalize_switch_path

from tests.support.stubs import RfStubTransport


class _HttpStub:
    def __init__(self, bodies: dict[str, str] | None = None) -> None:
        self.paths: list[str] = []
        self._bodies = bodies or {}

    def write(self, data: str) -> None:
        self.paths.append(data)

    def query(self, data: str) -> str:
        self.paths.append(data)
        return self._bodies.get(data, self._bodies.get(data.split("?", 1)[0], ""))

    def read(self) -> str:
        return ""

    def close(self) -> None:
        return None


def test_generic_attn_limits_from_config() -> None:
    transport = RfStubTransport({"MIN?": "0", "MAX?": "95", "STEP?": "0.25"})
    inst = build_instrument(
        "attn",
        1,
        {
            "model": "generic",
            "min_attenuation_db": 0,
            "max_attenuation_db": 90,
            "step_db": 0.5,
        },
        transport,
    )
    assert inst.measure_min_attenuation_db() == 0.0
    assert inst.measure_max_attenuation_db() == 90.0
    assert inst.measure_step_db() == 0.5


def test_minicircuits_switch_path_normalization() -> None:
    assert normalize_switch_path("1010") == "A=1;B=0;C=1;D=0"
    transport = RfStubTransport({"SWPORT?": "1010"})
    inst = build_instrument("rfswitch", 1, {"model": "minicircuits-rc"}, transport)
    assert inst.measure_path() == "A=1;B=0;C=1;D=0"


def test_controlbyweb_set_all_and_measure_all() -> None:
    stub = _HttpStub(
        {
            "state.json": '{"relay1":1,"relay2":0,"relay3":1,"relay4":0}',
        },
    )
    inst = build_instrument(
        "relay",
        1,
        {"model": "controlbyweb-x410", "resource": "http://192.168.1.2", "relay_count": 4},
        stub,
    )
    inst.set_all(0b0101)
    assert "state.json?relay1=1&relay2=0&relay3=1&relay4=0" in stub.paths
    inst.set_pulse_width_s(2, 0.75)
    assert "state.json?pulseTime2=0.75" in stub.paths
    assert inst.measure_all() == 0b0101


def test_generic_relay_set_all_unsupported() -> None:
    inst = build_instrument(
        "relay",
        1,
        {"model": "generic", "resource": "http://127.0.0.1"},
        _HttpStub(),
    )
    with pytest.raises(EquipmentCapabilityError):
        inst.set_all(1)


def test_serial_write_bytes_delegates(unit_runtime_context) -> None:
    import colosseum_equipment.api.serial as serial_api

    channel = MagicMock()
    with patch.object(serial_api, "_channel", return_value=channel):
        serial_api.write_bytes(serial_id=1, data=b"\x01\x02")
    channel.write_bytes.assert_called_once_with(b"\x01\x02")
