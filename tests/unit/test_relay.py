"""ControlByWeb relay drivers and HTTP transport."""

from __future__ import annotations

import base64

import pytest
from colosseum_equipment.exceptions import EquipmentCapabilityError, EquipmentResponseError
from colosseum_equipment.instruments.factory import build_instrument
from colosseum_equipment.instruments.registry import registered_models
from colosseum_equipment.transports.factory import open_transport, resolve_connection
from colosseum_equipment.transports.http import HttpTransport


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


def test_relay_models_registered() -> None:
    models = registered_models("relay")
    assert {"generic", "controlbyweb-webrelay", "controlbyweb-x410"}.issubset(models)


def test_generic_relay_unsupported() -> None:
    instrument = build_instrument(
        "relay",
        1,
        {"model": "generic", "resource": "http://127.0.0.1"},
        _HttpStub(),
    )
    with pytest.raises(EquipmentCapabilityError):
        instrument.set_relay(1, True)


def test_webrelay_set_and_measure_xml() -> None:
    stub = _HttpStub({"state.xml": "<datavalues><relay1>1</relay1></datavalues>"})
    instrument = build_instrument(
        "relay",
        1,
        {"model": "controlbyweb-webrelay", "resource": "http://192.168.1.2"},
        stub,
    )
    instrument.set_relay(1, True)
    instrument.pulse_relay(2, 1.5)
    assert "state.xml?relay1=1" in stub.paths
    assert "state.xml?pulseTime2=1.5&relay2=2" in stub.paths
    assert instrument.measure_relay(1) is True


def test_x410_set_and_measure_json() -> None:
    stub = _HttpStub({"state.json": '{"relay1":0,"relay2":1}'})
    instrument = build_instrument(
        "relay",
        1,
        {"model": "controlbyweb-x410", "resource": "http://192.168.1.2"},
        stub,
    )
    instrument.set_relay(1, False)
    assert "state.json?relay1=0" in stub.paths
    assert instrument.measure_relay(2) is True


def test_resolve_http_driver_for_relay_kind() -> None:
    driver, address = resolve_connection(
        "relay",
        {"resource": "http://10.0.0.5", "model": "controlbyweb-x410"},
    )
    assert driver == "http"
    assert address == "http://10.0.0.5"


def test_webrelay_rejects_doctype() -> None:
    stub = _HttpStub(
        {
            "state.xml": (
                "<!DOCTYPE datavalues [<!ENTITY xxe SYSTEM 'file:///secret'>]>"
                "<datavalues><relay1>&xxe;</relay1></datavalues>"
            ),
        },
    )
    instrument = build_instrument(
        "relay",
        1,
        {"model": "controlbyweb-webrelay", "resource": "http://192.168.1.2"},
        stub,
    )
    with pytest.raises(EquipmentResponseError, match="forbidden declaration"):
        instrument.measure_relay(1)


def test_http_transport_basic_auth_header(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    class _Resp:
        status = 200

        def read(self) -> bytes:
            return b'{"relay1":1}'

    class _FakeConnection:
        def __init__(
            self,
            host: str,
            port: int | None = None,
            timeout: float | None = None,
        ) -> None:
            seen["host"] = host
            seen["timeout"] = timeout

        def request(
            self,
            method: str,
            target: str,
            body: bytes | None = None,
            headers: dict[str, str] | None = None,
        ) -> None:
            seen["header"] = (headers or {}).get("Authorization")
            seen["target"] = target

        def getresponse(self) -> _Resp:
            return _Resp()

        def close(self) -> None:
            return None

    monkeypatch.setattr(
        "colosseum_equipment.transports.http.HTTPConnection",
        _FakeConnection,
    )
    transport = HttpTransport(
        "http://192.168.1.2",
        username="admin",
        password="secret",
        timeout=2.0,
    )
    body = transport.query("state.json")
    assert body == '{"relay1":1}'
    expected = "Basic " + base64.b64encode(b"admin:secret").decode("ascii")
    assert seen["header"] == expected


def test_open_transport_http(monkeypatch: pytest.MonkeyPatch) -> None:
    created: list[object] = []

    class _FakeHttp:
        def __init__(self, *args: object, **kwargs: object) -> None:
            created.append(kwargs)

        def close(self) -> None:
            return None

    monkeypatch.setattr("colosseum_equipment.transports.factory.HttpTransport", _FakeHttp)
    open_transport(
        "relay",
        1,
        {
            "resource": "http://192.168.1.2",
            "username": "u",
            "password": "p",
            "model": "controlbyweb-x410",
        },
    )
    assert created
    assert created[0]["username"] == "u"
