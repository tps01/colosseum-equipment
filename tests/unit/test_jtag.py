"""Exercise the public API and packaged Tcl against a fake Vivado process."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import colosseum as col
import pytest
from colosseum.config import load_config
from colosseum.runner.run_options import RunOptions
from colosseum_equipment.api import jtag
from colosseum_equipment.connections import close_all
from colosseum_equipment.exceptions import (
    EquipmentCapabilityError,
    EquipmentConnectionError,
    EquipmentResponseError,
    EquipmentTimeoutError,
)
from colosseum_equipment.jtag import vivado as _vivado

_TCL_FIXTURE = Path(__file__).with_name("vivado_jtag_fixture.tcl")


@pytest.fixture
def fake_vivado(io_runtime_context, io_bench, monkeypatch, tmp_path):
    pytest.importorskip("tkinter")
    install = tmp_path / "Custom AMD & tools" / "bin"
    install.mkdir(parents=True)
    for name in ("vivado", "hw_server"):
        (install / _vivado._bin(name)).touch()
    monkeypatch.delenv("XILINX_VIVADO", raising=False)

    def configure(extra="", *, explicit_server=True):
        path = install.parent.as_posix()
        endpoint = 'hw_server_url = "lab.example:3121"' if explicit_server else ""
        load_config(io_bench(f"""
            [equipment.jtag]
            jtag_id = 1
            vivado_path = "{path}"
            {endpoint}
            {extra}
        """))

    launches = []

    def launch(tool, args, cwd, log):
        launches.append((tool, args))
        if tool.name.startswith("hw_server"):
            code = "import time; time.sleep(60)"
        else:
            code = (
                "import tkinter; t=tkinter.Tcl(); "
                f"t.eval({str(_TCL_FIXTURE.read_text(encoding='utf-8'))!r}); "
                "t.eval('source driver.tcl')"
            )
        with log.open("ab") as stream:
            return subprocess.Popen([sys.executable, "-B", "-c", code], cwd=cwd,
                                    stdout=stream, stderr=subprocess.STDOUT)

    monkeypatch.setattr(_vivado, "_launch", launch)
    try:
        yield configure, launches
    finally:
        close_all()


def test_inventory_clock_and_scan(fake_vivado):
    configure, launches = fake_vivado
    configure('xvc_url = "192.0.2.8:2542"')
    targets = col.equipment.jtag.list_targets(jtag_id=1, key="targets")
    assert targets["targets"] == [{"target": "cable-1", "name": "test-target"}]
    assert targets["xvc_url"] == "192.0.2.8:2542"
    devices = col.equipment.jtag.list_devices(jtag_id=1, target="cable-1", key="chain")
    assert devices["devices"] == [{"index": 0, "device": "chip", "part": "xc7a35t", "idcode": "0362D093"}]
    clock = col.equipment.jtag.set_clock(jtag_id=1, clock_hz=1000000, key="clock")
    assert clock["clock_hz"] == clock["requested_clock_hz"] == 1000000
    assert col.equipment.jtag.get_clock(jtag_id=1, key="read_clock")["requested_clock_hz"] is None
    result = col.equipment.jtag.scan(
        jtag_id=1, key="tdo",
        steps=[{"state": "RESET"}, {"register": "IR", "bits": 6, "tdi": "09"},
               {"register": "DR", "bits": 32, "tdi": "00000000"}],
    )
    assert result["scans"] == [{"register": "IR", "bits": 6, "tdo": "01"},
                               {"register": "DR", "bits": 32, "tdo": "0362D093"}]
    assert all(tool.name == _vivado._bin("vivado") for tool, _ in launches)


def test_program_and_verify_flags(fake_vivado, tmp_path):
    configure, _ = fake_vivado
    configure('device = "chip"')
    bit = tmp_path / "image [test].bit"
    flash = tmp_path / "flash image.mcs"
    bit.touch()
    flash.touch()
    loaded = col.equipment.jtag.program_device(jtag_id=1, image=bit, key="bit")
    assert loaded["image"] == bit.as_posix()
    assert loaded["configured"] is True
    assert col.equipment.jtag.list_cfgmem_parts(jtag_id=1, key="parts")["parts"] == ["flash-a"]
    programmed = col.equipment.jtag.program_cfgmem(jtag_id=1, image=flash, flash_part="flash-a", key="flash")
    verified = col.equipment.jtag.verify_cfgmem(jtag_id=1, image=flash, flash_part="flash-a", key="verify")
    assert programmed["flash_written"] is True and programmed["flash_verified"] is True
    assert verified["flash_written"] is False and verified["flash_verified"] is True
    assert col.equipment.jtag.boot_from_cfgmem(jtag_id=1, key="boot")["configured"] is True


def test_custom_tcl_and_error(fake_vivado):
    configure, _ = fake_vivado
    configure()
    result = col.equipment.jtag.run_tcl(jtag_id=1, key="custom", tcl="lindex $argv 0", args=["a {$b} ; c"])
    assert result["tcl_result"] == "a {$b} ; c"
    with pytest.raises(EquipmentResponseError, match="requested error"):
        col.equipment.jtag.run_tcl(jtag_id=1, key="bad", tcl="error {requested error}")


def test_soc_boot_uses_board_evidence(fake_vivado, monkeypatch):
    configure, _ = fake_vivado
    configure()
    monkeypatch.setenv("FAKE_VIVADO_PART", "xczu7ev")
    with pytest.raises(EquipmentCapabilityError, match="requires board reset"):
        col.equipment.jtag.boot_from_cfgmem(jtag_id=1, key="native_boot")
    changes = []
    result = col.equipment.jtag.boot_from_cfgmem(
        jtag_id=1, key="soc_boot", reset=lambda: changes.append("reset"),
        check_boot=lambda: changes == ["reset"],
    )
    assert result["boot_method"] == "board_reset"
    assert result["configured"] is True


def test_board_boot_rejects_positive_evidence_after_deadline(fake_vivado, monkeypatch):
    configure, _ = fake_vivado
    configure()
    clock = SimpleNamespace(now=0.0)
    monkeypatch.setattr(jtag, "time", SimpleNamespace(monotonic=lambda: clock.now, sleep=lambda _: None))

    def check_boot():
        clock.now = 0.06
        return True

    result = col.equipment.jtag.boot_from_cfgmem(
        jtag_id=1, key="late_boot", reset=lambda: None, check_boot=check_boot, boot_timeout_s=0.01,
    )
    assert result.status == "FAIL"


@pytest.mark.parametrize(
    ("done", "exception", "message"),
    [
        ("1", None, None),
        ("0", EquipmentResponseError, "did not report configuration complete"),
        ("unreadable", EquipmentResponseError, "completion could not be read"),
        ("missing_dap", EquipmentCapabilityError, "No companion arm_dap"),
    ],
)
def test_versal_direct_programming_requires_dap_done(fake_vivado, tmp_path, monkeypatch, done, exception, message):
    configure, _ = fake_vivado
    configure('device = "chip"')
    monkeypatch.setenv("FAKE_VIVADO_PART", "xcvc1902")
    monkeypatch.setenv("FAKE_VERSAL_DONE", done)
    image = tmp_path / "design.pdi"
    image.touch()
    program = col.equipment.jtag.program_device
    if exception:
        with pytest.raises(exception, match=message):
            program(jtag_id=1, image=image, key="versal")
    else:
        assert program(jtag_id=1, image=image, key="versal")["configured"] is True


def test_unrecognized_versal_flash_flow_fails_before_programming(fake_vivado, tmp_path, monkeypatch):
    configure, _ = fake_vivado
    configure()
    monkeypatch.setenv("FAKE_VIVADO_PART", "xcvc1902")
    boot, init = tmp_path / "boot.pdi", tmp_path / "init.pdi"
    boot.touch()
    init.touch()
    with pytest.raises(EquipmentCapabilityError, match="initialization PDI property"):
        col.equipment.jtag.program_cfgmem(
            jtag_id=1, image=boot, initialization_pdi=init, flash_part="flash-a", key="flash",
        )


def test_target_ambiguity_is_reported_before_programming(fake_vivado, tmp_path, monkeypatch):
    configure, _ = fake_vivado
    configure()
    monkeypatch.setenv("FAKE_VIVADO_TARGETS", "two")
    bit = tmp_path / "image.bit"
    bit.touch()
    with pytest.raises(EquipmentConnectionError, match="exactly one target"):
        col.equipment.jtag.program_device(jtag_id=1, image=bit, key="bit")


def test_xvc_capabilities_and_dry_run_do_not_launch(fake_vivado, io_runtime_context, tmp_path):
    configure, launches = fake_vivado
    configure('xvc_url = "192.0.2.8:2542"')
    bit = tmp_path / "image.bit"
    bit.touch()
    with pytest.raises(EquipmentCapabilityError, match="xvc_programming"):
        col.equipment.jtag.program_device(jtag_id=1, image=bit, key="bit")
    with pytest.raises(EquipmentCapabilityError, match="chain scans"):
        col.equipment.jtag.scan(jtag_id=1, key="device", steps=[], scope="device")
    io_runtime_context.run_options = RunOptions(dry_run=True)
    col.equipment.jtag.list_targets(jtag_id=1, key="dry")
    assert not launches


@pytest.mark.parametrize("port_busy", [False, True])
def test_start_reuse_and_cleanup_own_server(fake_vivado, io_runtime_context, monkeypatch, port_busy):
    configure, launches = fake_vivado
    configure(explicit_server=False)
    monkeypatch.setattr(_vivado, "_listening", lambda port: port_busy if port == 3121 else True)
    monkeypatch.setenv("FAKE_VIVADO_REFUSE_DEFAULT", "true" if port_busy else "false")
    first = col.equipment.jtag.list_targets(jtag_id=1, key="one")
    second = col.equipment.jtag.list_targets(jtag_id=1, key="two")
    assert first["hw_server_url"] == second["hw_server_url"] != _vivado.DEFAULT_SERVER
    owned = next(value for value in io_runtime_context.resource_cache.values() if isinstance(value, _vivado._Server))
    assert sum(tool.name.startswith("hw_server") for tool, _ in launches) == 1
    close_all()
    assert owned.proc.poll() is not None


def test_reuse_default_server_without_owning_it(fake_vivado, io_runtime_context, monkeypatch):
    configure, launches = fake_vivado
    configure(explicit_server=False)
    monkeypatch.setattr(_vivado, "_listening", lambda port: port == 3121)
    result = col.equipment.jtag.list_targets(jtag_id=1, key="targets")
    assert result["hw_server_url"] == _vivado.DEFAULT_SERVER
    assert all(tool.name == _vivado._bin("vivado") for tool, _ in launches)
    assert not any(isinstance(value, _vivado._Server) for value in io_runtime_context.resource_cache.values())


def test_timeout_preserves_log(fake_vivado, io_runtime_context):
    configure, _ = fake_vivado
    configure()
    with pytest.raises(EquipmentTimeoutError):
        col.equipment.jtag.run_tcl(jtag_id=1, key="timeout", tcl="after 5000", timeout_s=1)
    assert list(io_runtime_context.output_dir.glob("jtag/*.log"))
