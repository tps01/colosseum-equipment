"""Model selection from *IDN? or serial IDN? when the config omits model."""

from __future__ import annotations

from colosseum_equipment.exceptions import EquipmentTimeoutError
from colosseum_equipment.instruments.identify import (
    instrument_config,
    resolve_instrument_model,
)


class _Probe:
    def __init__(
        self,
        idn: str = "",
        *,
        fail_star: bool = False,
        fail_bare: bool = False,
        bare: str = "",
    ) -> None:
        self._idn = idn
        self._fail_star = fail_star
        self._fail_bare = fail_bare
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
        if self._fail_bare:
            raise EquipmentTimeoutError("timeout")
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


def test_serial_visa_bare_idn_selects_genesys_serial_without_star() -> None:
    cases = (
        ({"port": "COM5", "device_address": 3, "baudrate": 9600}, "LAMBDA, GEN30-50\r"),
        ({"resource": "ASRL15::INSTR"}, "LAMBDA_GEN30-80\r"),
        ({"resource": "COM15"}, "LAMBDA,GEN30-80\r"),
    )
    for config, identity in cases:
        probe = _Probe(bare=identity)
        assert resolve_instrument_model("psu", config, probe) == "tdk-genesys-serial"
        assert probe.queries == []
        assert probe.raw == [b"IDN?\r"]
    addressed = instrument_config("psu", cases[0][0], "tdk-genesys-serial")
    assert addressed["driver"] == "serial"
    assert addressed["baudrate"] == 9600
    assert addressed["model"] == "tdk-genesys-serial"
    omitted = instrument_config("psu", {"resource": "ASRL15::INSTR"}, "tdk-genesys-serial")
    assert omitted["driver"] == "serial"
    assert omitted["baudrate"] == 9600


def test_serial_visa_non_lambda_idn_falls_back_to_star() -> None:
    failed = _Probe("LAMBDA_GEN40-38-IEEE", fail_bare=True)
    assert resolve_instrument_model("psu", {"resource": "ASRL15::INSTR"}, failed) == "tdk-genesys"
    assert failed.raw == [b"IDN?\r"]
    assert failed.queries == ["*IDN?"]
    other = _Probe("LAMBDA,GEN60-25-LAN,1,1", bare="ACME,WIDGET\r")
    assert resolve_instrument_model("psu", {"port": "COM5"}, other) == "tdk-genesys"
    assert other.queries == ["*IDN?"]


def test_sim_http_and_gnss_skip_the_probe() -> None:
    probe = _Probe("LAMBDA,GEN30-50")
    assert resolve_instrument_model("psu", {"driver": "sim"}, probe) == "generic"
    assert resolve_instrument_model(
        "relay", {"resource": "http://192.168.1.2"}, probe,
    ) == "generic"
    assert resolve_instrument_model("gnss", {"port": "COM7"}, probe) == "generic"
    assert probe.queries == []
