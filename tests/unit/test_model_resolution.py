"""Model selection from *IDN? when the config omits model."""

from __future__ import annotations

from colosseum_equipment.exceptions import EquipmentTimeoutError
from colosseum_equipment.instruments.identify import (
    instrument_config,
    resolve_instrument_model,
)


class _Probe:
    def __init__(self, idn: str = "", *, fail_star: bool = False, bare: str = "") -> None:
        self._idn = idn
        self._fail_star = fail_star
        self._bare = bare
        self.queries: list[str] = []
        self.raw: list[bytes] = []

    def query(self, data: str) -> str:
        self.queries.append(data)
        if data == "*IDN?" and self._fail_star:
            raise EquipmentTimeoutError("timeout")
        return self._idn

    def flush(self) -> None:
        return None

    def write_bytes(self, payload: bytes) -> None:
        self.raw.append(payload)

    def read_until(self, terminator: bytes) -> str:
        assert terminator == b"\r"
        return self._bare


def test_explicit_model_does_not_query() -> None:
    probe = _Probe("LAMBDA,GEN30-50")
    model = resolve_instrument_model("psu", {"model": "generic"}, probe)
    assert model == "generic"
    assert probe.queries == []


def test_star_idn_selects_registered_genesys_model() -> None:
    probe = _Probe("LAMBDA_GEN40-38-IEEE")
    model = resolve_instrument_model("psu", {"resource": "TCPIP0::192.168.1.8::INSTR"}, probe)
    assert model == "tdk-genesys"
    assert probe.queries == ["*IDN?"]


def test_unknown_idn_and_kind_mismatch_use_generic() -> None:
    unknown = _Probe("ACME,WIDGET,1,1")
    assert resolve_instrument_model("psu", {"resource": "GPIB::1::INSTR"}, unknown) == "generic"
    mismatch = _Probe("Keysight Technologies,EDU34450A,MY123,1.0.0")
    assert resolve_instrument_model("psu", {"resource": "GPIB::2::INSTR"}, mismatch) == "generic"


def test_probe_error_uses_generic() -> None:
    probe = _Probe(fail_star=True)
    model = resolve_instrument_model("psu", {"resource": "GPIB::1::INSTR"}, probe)
    assert model == "generic"
    assert probe.raw == []


def test_asrl_bare_idn_selects_native_serial_when_address_is_set() -> None:
    probe = _Probe(fail_star=True, bare="LAMBDA, GEN30-50\r")
    config = {"port": "COM5", "device_address": 3, "baudrate": 9600}
    assert resolve_instrument_model("psu", config, probe) == "tdk-gen300-5-serial"
    assert probe.raw == [b"IDN?\r"]
    resolved = instrument_config("psu", config, "tdk-gen300-5-serial")
    assert resolved["driver"] == "serial"
    assert resolved["baudrate"] == 9600
    assert resolved["model"] == "tdk-gen300-5-serial"


def test_asrl_bare_idn_without_address_stays_generic() -> None:
    probe = _Probe(fail_star=True, bare="LAMBDA_GEN30-80\r")
    model = resolve_instrument_model("psu", {"port": "COM5"}, probe)
    assert model == "generic"


def test_sim_http_and_gnss_skip_the_probe() -> None:
    probe = _Probe("LAMBDA,GEN30-50")
    assert resolve_instrument_model("psu", {"driver": "sim"}, probe) == "generic"
    assert resolve_instrument_model(
        "relay", {"resource": "http://192.168.1.2"}, probe,
    ) == "generic"
    assert resolve_instrument_model("gnss", {"port": "COM7"}, probe) == "generic"
    assert probe.queries == []
