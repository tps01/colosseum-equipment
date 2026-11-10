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
        require_adr: bool = False,
        adr_ack: str = "OK\r",
    ) -> None:
        self._idn = idn
        self._fail_star = fail_star
        self._fail_bare = fail_bare
        self._bare = bare
        self._require_adr = require_adr
        self._adr_ack = adr_ack
        self._addressed = False
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
        if payload.startswith(b"ADR ") and payload.endswith(b"\r"):
            self._addressed = self._adr_ack.strip().upper() == "OK"

    def read_until(self, terminator: bytes) -> str:
        assert terminator == b"\r"
        last = self.raw[-1] if self.raw else b""
        if last.startswith(b"ADR "):
            return self._adr_ack
        if self._fail_bare:
            raise EquipmentTimeoutError("timeout")
        if self._require_adr and not self._addressed:
            return "ERR\r"
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
        assert resolve_instrument_model("psu", dict(config), probe) == "tdk-genesys-serial"
        assert probe.queries == []
        assert probe.raw == [b"IDN?\r"]
    addressed = instrument_config("psu", cases[0][0], "tdk-genesys-serial")
    assert addressed["driver"] == "serial"
    assert addressed["baudrate"] == 9600
    assert addressed["model"] == "tdk-genesys-serial"
    omitted = instrument_config("psu", {"resource": "ASRL15::INSTR"}, "tdk-genesys-serial")
    assert omitted["driver"] == "serial"
    assert omitted["baudrate"] == 9600


def test_serial_genesys_adr_then_idn_when_cold() -> None:
    config: dict = {"resource": "ASRL15::INSTR"}
    probe = _Probe(bare="LAMBDA,GEN30-80\r", require_adr=True)
    assert resolve_instrument_model("psu", config, probe) == "tdk-genesys-serial"
    assert probe.raw == [b"IDN?\r", b"ADR 6\r", b"IDN?\r"]
    assert config["device_address"] == 6
    assert probe.queries == []


def test_serial_genesys_uses_configured_device_address_for_adr() -> None:
    config = {"port": "COM5", "device_address": 3, "baudrate": 9600}
    probe = _Probe(bare="LAMBDA, GEN30-50\r", require_adr=True)
    assert resolve_instrument_model("psu", config, probe) == "tdk-genesys-serial"
    assert probe.raw == [b"IDN?\r", b"ADR 3\r", b"IDN?\r"]


def test_serial_visa_non_lambda_idn_falls_back_to_star() -> None:
    failed = _Probe("LAMBDA_GEN40-38-IEEE", fail_bare=True)
    assert resolve_instrument_model("psu", {"resource": "ASRL15::INSTR"}, failed) == "tdk-genesys"
    assert failed.raw[0] == b"IDN?\r"
    assert b"ADR 6\r" in failed.raw
    assert failed.queries == ["*IDN?"]
    other = _Probe("LAMBDA,GEN60-25-LAN,1,1", bare="ACME,WIDGET\r")
    assert resolve_instrument_model("psu", {"port": "COM5"}, other) == "tdk-genesys"
    assert other.queries == ["*IDN?"]


def test_sim_http_and_relay_skip_the_probe() -> None:
    probe = _Probe("LAMBDA,GEN30-50")
    assert resolve_instrument_model("psu", {"driver": "sim"}, probe) == "generic"
    assert (
        resolve_instrument_model(
            "relay",
            {"resource": "http://192.168.1.2"},
            probe,
        )
        == "generic"
    )
    assert probe.queries == []


def test_gnss_omit_model_probes_vendor_stream() -> None:
    from colosseum_equipment.instruments.gnss.ubx import (
        CLS_MON,
        ID_MON_VER,
        build_ubx,
        mon_ver_poll,
    )

    # MON-VER payload: sw(30) + hw(10) with MOD=NEO-M9N in extension
    body = bytearray(70)
    body[0:7] = b"ROM SPG"
    body[30:36] = b"000A00"
    body[40:51] = b"MOD=NEO-M9N"
    frame = build_ubx(CLS_MON, ID_MON_VER, bytes(body))

    class _GnssProbe:
        def __init__(self) -> None:
            self._chunks = [frame]
            self.written: list[bytes] = []

        def flush(self) -> None:
            return None

        def write_bytes(self, payload: bytes) -> None:
            self.written.append(payload)

        def read_bytes(self, size: int = 512) -> bytes:
            _ = size
            if not self._chunks:
                return b""
            return self._chunks.pop(0)

    probe = _GnssProbe()
    assert resolve_instrument_model("gnss", {"port": "COM7"}, probe) == "ublox-m9"
    assert probe.written == [mon_ver_poll()]


def test_gnss_omit_model_without_reply_is_generic() -> None:
    class _Silent:
        def flush(self) -> None:
            return None

        def write_bytes(self, payload: bytes) -> None:
            _ = payload

        def read_bytes(self, size: int = 512) -> bytes:
            _ = size
            return b""

        def in_waiting(self) -> int:
            return 0

    assert resolve_instrument_model("gnss", {"port": "COM7"}, _Silent()) == "generic"
