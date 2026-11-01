"""Unit tests for col.equipment.autoconfig()."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import colosseum.context as context_module
import pytest
from colosseum.config.loader import ConfigError
from colosseum.context import get_context
from colosseum_equipment.api._autoconfig import autoconfig
from colosseum_equipment.autoconfig.discovery import discover_equipment_config
from colosseum_equipment.network import IPv4NetworkBinding

if TYPE_CHECKING:
    from pathlib import Path


class _FakeInstrument:
    def __init__(
        self,
        idn: str = "",
        *,
        bare: str = "",
        fail_star: bool = False,
        fail_bare: bool = False,
        qm_ack: str = "",
        qm_data: str = "",
    ) -> None:
        self.timeout = 0
        self.baud_rate = 0
        self._idn = idn
        self._bare = bare
        self._fail_star = fail_star
        self._fail_bare = fail_bare
        self._qm_ack = qm_ack
        self._qm_data = qm_data
        self._qm_stage = 0
        self.closed = False
        self.queries: list[str] = []
        self.raw: list[bytes] = []

    def query(self, command: str) -> str:
        self.queries.append(command)
        if command == "*IDN?":
            if self._fail_star:
                raise TimeoutError("star timeout")
            return self._idn
        if command == "IDN?":
            if self._fail_bare:
                raise TimeoutError("bare timeout")
            return self._bare
        raise RuntimeError(f"unexpected query: {command}")

    def write_raw(self, payload: bytes) -> None:
        self.raw.append(payload)
        if payload == b"IDN?\r" and self._fail_bare:
            raise TimeoutError("bare timeout")
        if payload == b"QM\r":
            self._qm_stage = 1

    def read_raw(self, size: int = 1) -> bytes:
        _ = size
        if self.raw and self.raw[-1] == b"IDN?\r":
            return (self._bare.encode("ascii") + b"\r")[:1] and self._emit_line(self._bare)
        if self._qm_stage == 1:
            self._qm_stage = 2
            return self._emit_line(self._qm_ack)
        if self._qm_stage == 2:
            self._qm_stage = 0
            return self._emit_line(self._qm_data)
        return b""

    def _emit_line(self, text: str) -> bytes:
        # read_until loops one byte; provide full line via read() fallback path instead
        self._pending = text + "\r"
        return b""

    def read(self) -> str:
        pending = getattr(self, "_pending", "")
        self._pending = ""
        return pending

    def write_bytes(self, payload: bytes) -> None:
        self.write_raw(payload)

    def read_until(self, terminator: bytes) -> str:
        assert terminator == b"\r"
        if self.raw and self.raw[-1] == b"IDN?\r":
            if self._fail_bare:
                raise TimeoutError("bare timeout")
            return self._bare + "\r"
        if self._qm_stage == 1:
            self._qm_stage = 2
            return self._qm_ack + "\r"
        if self._qm_stage == 2:
            self._qm_stage = 0
            return self._qm_data + "\r"
        return "\r"

    def close(self) -> None:
        self.closed = True


class _FakeResourceManager:
    def __init__(self, resources: dict[str, _FakeInstrument | str]) -> None:
        self._resources = {
            key: (value if isinstance(value, _FakeInstrument) else _FakeInstrument(value))
            for key, value in resources.items()
        }
        self.opened: list[_FakeInstrument] = []

    def list_resources(self, query: str) -> tuple[str, ...]:
        _ = query
        return tuple(self._resources)

    def open_resource(self, resource: str) -> _FakeInstrument:
        if resource not in self._resources:
            raise RuntimeError(f"unknown resource: {resource}")
        # Return a fresh copy-like instance so baud retries reopen cleanly.
        template = self._resources[resource]
        inst = _FakeInstrument(
            template._idn,
            bare=template._bare,
            fail_star=template._fail_star,
            fail_bare=template._fail_bare,
            qm_ack=template._qm_ack,
            qm_data=template._qm_data,
        )
        self.opened.append(inst)
        return inst


@dataclass
class _ComPort:
    device: str


class _FakeSerialPort:
    def __init__(
        self,
        *,
        bare: str = "",
        idn: str = "",
        fail_idn: bool = True,
        qm_ack: str = "",
        qm_data: str = "",
        expected_baud: int | None = None,
    ) -> None:
        self.bare = bare
        self.idn = idn
        self.fail_idn = fail_idn
        self.qm_ack = qm_ack
        self.qm_data = qm_data
        self.expected_baud = expected_baud
        self.baudrate = 0
        self._stage = ""
        self.closed = False

    def reset_input_buffer(self) -> None:
        return None

    def write(self, payload: bytes) -> None:
        if payload == b"IDN?\r":
            self._stage = "bare"
        elif payload == b"*IDN?\n":
            self._stage = "star"
        elif payload == b"QM\r":
            self._stage = "qm_ack"
        else:
            self._stage = "other"

    def read_until(self, terminator: bytes) -> bytes:
        _ = terminator
        if self._stage == "bare":
            if self.fail_idn and not self.bare:
                raise TimeoutError("bare")
            return (self.bare + "\r").encode("ascii")
        if self._stage == "star":
            if self.fail_idn and not self.idn:
                raise TimeoutError("star")
            return (self.idn + "\n").encode("ascii")
        if self._stage == "qm_ack":
            self._stage = "qm_data"
            return (self.qm_ack + "\r").encode("ascii")
        if self._stage == "qm_data":
            self._stage = ""
            return (self.qm_data + "\r").encode("ascii")
        raise TimeoutError("unexpected read")

    def close(self) -> None:
        self.closed = True


class _LogCapture:
    def __init__(self) -> None:
        self.messages: list[tuple[str, str]] = []

    def info(self, msg: str, *args: object) -> None:
        self.messages.append(("info", msg % args if args else msg))

    def warning(self, msg: str, *args: object) -> None:
        self.messages.append(("warning", msg % args if args else msg))


def _discover(rm: _FakeResourceManager, **kwargs: object) -> object:
    kwargs.setdefault("list_comports", lambda: [])
    return discover_equipment_config(resource_manager=rm, timeout=1.0, **kwargs)  # type: ignore[arg-type]


def test_discover_assigns_ids_by_connection_order() -> None:
    rm = _FakeResourceManager(
        {
            "GPIB0::1::INSTR": "TDK-Lambda,GENESYS-28-80,1,1",
            "TCPIP0::192.168.1.29::INSTR": "TDK-Lambda,GENESYS-28-80,2,1",
            "GPIB0::2::INSTR": "Keysight Technologies,EDU34450A,1,1",
        },
    )
    result = _discover(rm)
    psu_rows = result.raw["equipment"]["psu"]
    assert len(psu_rows) == 2
    assert psu_rows[0]["psu_id"] == 1
    assert psu_rows[0]["resource"].startswith("TCPIP")
    assert psu_rows[1]["psu_id"] == 2
    assert psu_rows[1]["resource"].startswith("GPIB")
    assert result.raw["equipment"]["dmm"][0]["dmm_id"] == 1
    assert all(inst.closed for inst in rm.opened)


def test_discover_blacklist_excludes_tcpip_subnet() -> None:
    rm = _FakeResourceManager(
        {
            "TCPIP0::10.0.0.42::INSTR": "TDK-Lambda,GENESYS-28-80,1,1",
            "GPIB0::1::INSTR": "TDK-Lambda,GENESYS-28-80,2,1",
        },
    )
    bindings = [
        IPv4NetworkBinding(
            interface="eth0",
            address="10.0.0.5",
            network="10.0.0.0",
            prefix=24,
        ),
    ]
    result = _discover(rm, blacklist="eth0", network_bindings=bindings)
    assert len(result.blacklisted) == 1
    assert len(result.assignments) == 1
    assert result.assignments[0].resource.startswith("GPIB")


def test_discover_raises_when_no_classifiable_resources() -> None:
    rm = _FakeResourceManager({"GPIB0::1::INSTR": "UNKNOWN,WIDGET,1,1"})
    with pytest.raises(ConfigError, match="no classifiable"):
        _discover(rm)


def test_asrl_bare_lambda_selects_genesys_serial() -> None:
    rm = _FakeResourceManager(
        {
            "ASRL5::INSTR": _FakeInstrument(
                bare="LAMBDA, GEN30-50",
                fail_star=True,
            ),
        },
    )
    result = _discover(rm)
    row = result.raw["equipment"]["psu"][0]
    assert row["model"] == "tdk-genesys-serial"
    assert row["driver"] == "serial"
    assert row["baudrate"] == 9600
    assert row["port"] == "COM5"
    assert row["resource"] == "ASRL5::INSTR"


def test_asrl_bare_fail_falls_back_to_star_idn() -> None:
    rm = _FakeResourceManager(
        {
            "ASRL15::INSTR": _FakeInstrument(
                idn="Keysight Technologies,EDU34450A,1,1",
                fail_bare=True,
            ),
        },
    )
    result = _discover(rm)
    assert result.raw["equipment"]["dmm"][0]["model"] == "keysight-edu34450a"


def test_com_port_only_genesys_and_dedupe_asrl(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _ = monkeypatch
    rm = _FakeResourceManager(
        {
            "ASRL7::INSTR": _FakeInstrument(bare="LAMBDA,GEN30-80", fail_star=True),
        },
    )
    ports = {"COM8": _FakeSerialPort(bare="LAMBDA,GEN40-15", fail_idn=False)}

    def _open(port: str, baud: int, timeout: float) -> _FakeSerialPort:
        _ = timeout
        template = ports[port]
        if template.expected_baud is not None and baud != template.expected_baud:
            raise TimeoutError("wrong baud")
        opened = _FakeSerialPort(
            bare=template.bare,
            idn=template.idn,
            fail_idn=template.fail_idn,
            qm_ack=template.qm_ack,
            qm_data=template.qm_data,
        )
        opened.baudrate = baud
        return opened

    result = discover_equipment_config(
        resource_manager=rm,
        timeout=1.0,
        list_comports=lambda: [_ComPort("COM7"), _ComPort("COM8")],
        open_serial=_open,
    )
    psu = result.raw["equipment"]["psu"]
    assert len(psu) == 2
    ports_found = {row.get("port") for row in psu}
    assert ports_found == {"COM7", "COM8"}


def test_com_baud_tries_until_115200() -> None:
    rm = _FakeResourceManager({})

    def _open(port: str, baud: int, timeout: float) -> _FakeSerialPort:
        _ = port, timeout
        if baud != 115200:
            raise TimeoutError("no carrier")
        return _FakeSerialPort(bare="LAMBDA,GEN30-50", fail_idn=False)

    result = discover_equipment_config(
        resource_manager=rm,
        timeout=1.0,
        list_comports=lambda: [_ComPort("COM9")],
        open_serial=_open,
    )
    row = result.raw["equipment"]["psu"][0]
    assert row["baudrate"] == 115200
    assert row["port"] == "COM9"


def test_fluke_qm_after_idn_phase() -> None:
    rm = _FakeResourceManager({})
    state = {"idn_done": False}

    def _open(port: str, baud: int, timeout: float) -> _FakeSerialPort:
        _ = port, timeout
        if not state["idn_done"]:
            if baud == 19200:
                state["idn_done"] = True
            return _FakeSerialPort(fail_idn=True)
        if baud == 9600:
            return _FakeSerialPort(fail_idn=True, qm_ack="0", qm_data="QM, +1.234 VDC")
        raise TimeoutError("no qm")

    result = discover_equipment_config(
        resource_manager=rm,
        timeout=1.0,
        list_comports=lambda: [_ComPort("COM3")],
        open_serial=_open,
    )
    row = result.raw["equipment"]["dmm"][0]
    assert row["model"] == "fluke-189"
    assert row["driver"] == "serial"
    assert row["baudrate"] == 9600
    assert state["idn_done"] is True


def test_fluke_289_qm_dialect() -> None:
    rm = _FakeResourceManager({})
    state = {"idn_done": False}

    def _open(port: str, baud: int, timeout: float) -> _FakeSerialPort:
        _ = port, timeout
        if not state["idn_done"]:
            if baud == 19200:
                state["idn_done"] = True
            return _FakeSerialPort(fail_idn=True)
        if baud == 115200:
            return _FakeSerialPort(
                fail_idn=True,
                qm_ack="0",
                qm_data="1.23,VDC,NORMAL,0",
            )
        raise TimeoutError("skip")

    result = discover_equipment_config(
        resource_manager=rm,
        timeout=1.0,
        list_comports=lambda: [_ComPort("COM4")],
        open_serial=_open,
    )
    assert result.raw["equipment"]["dmm"][0]["model"] == "fluke-289"
    assert result.raw["equipment"]["dmm"][0]["baudrate"] == 115200


def test_live_log_order() -> None:
    rm = _FakeResourceManager(
        {"GPIB0::1::INSTR": "Keysight Technologies,EDU34450A,1,1"},
    )
    log = _LogCapture()
    _discover(rm, logger=log)
    texts = [msg for _, msg in log.messages]
    assert texts[0].startswith("Autoconfig scan starting")
    assert any(msg.startswith("Autoconfig probing") for msg in texts)
    assert any("assigned" in msg for msg in texts)
    assert texts[-1].startswith("Autoconfig summary")


def test_autoconfig_populates_config_store(monkeypatch: pytest.MonkeyPatch) -> None:
    import colosseum_equipment.api._autoconfig as autoconfig_module

    context_module._ACTIVE_CONTEXT = None
    rm = _FakeResourceManager(
        {"GPIB0::1::INSTR": "Keysight Technologies,EDU34450A,1,1"},
    )

    def _fake_discover(**kwargs: object) -> object:
        return discover_equipment_config(
            resource_manager=rm,
            timeout=float(kwargs.get("timeout", 5.0)),  # type: ignore[arg-type]
            blacklist=kwargs.get("blacklist"),  # type: ignore[arg-type]
            list_comports=lambda: [],
            logger=kwargs.get("logger"),  # type: ignore[arg-type]
        )

    monkeypatch.setattr(autoconfig_module, "discover_equipment_config", _fake_discover)
    store = autoconfig(timeout=1.0)
    ctx = get_context()
    assert ctx is not None
    assert ctx.config_path == "(autoconfig)"
    assert store.require_item("equipment.dmm", 1)["model"] == "keysight-edu34450a"
    assert ctx.logger is not None


def test_autoconfig_export_writes_toml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import colosseum_equipment.api._autoconfig as autoconfig_module
    from colosseum.config.toml_relaxed import read_relaxed_toml
    from colosseum.context import get_context, init_context
    from colosseum.runner.paths import ensure_output_dir

    context_module._ACTIVE_CONTEXT = None
    init_context(test_case_name="export_test")
    ensure_output_dir(get_context())
    rm = _FakeResourceManager(
        {"GPIB0::1::INSTR": "Keysight Technologies,EDU34450A,1,1"},
    )

    def _fake_discover(**kwargs: object) -> object:
        return discover_equipment_config(
            resource_manager=rm,
            timeout=float(kwargs.get("timeout", 5.0)),  # type: ignore[arg-type]
            blacklist=kwargs.get("blacklist"),  # type: ignore[arg-type]
            list_comports=lambda: [],
            logger=kwargs.get("logger"),  # type: ignore[arg-type]
        )

    monkeypatch.setattr(autoconfig_module, "discover_equipment_config", _fake_discover)
    export_path = tmp_path / "config.generated.toml"
    autoconfig(timeout=1.0, export_path=export_path)
    ctx = get_context()
    assert export_path.is_file()
    loaded = read_relaxed_toml(export_path)
    dmm_section = loaded["equipment"]["dmm"]
    row = dmm_section[0] if isinstance(dmm_section, list) else dmm_section
    assert row["model"] == "keysight-edu34450a"
    metadata = {row.key: row.value for row in ctx.db.fetch_run_metadata()}
    assert metadata["config_export_path"] == str(export_path.resolve())
