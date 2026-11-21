"""Exercise Quartus commands and packaged Tcl without a hardware bench."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import colosseum as col
import pytest
from colosseum.config import load_config
from colosseum.runner.run_options import RunOptions
from colosseum_equipment.exceptions import (
    EquipmentCapabilityError,
    EquipmentConnectionError,
    EquipmentResponseError,
    EquipmentTimeoutError,
)
from colosseum_equipment.jtag import quartus

_TCL = """
proc get_hardware_names {} { return [list {USB-BlasterII [remote bench]}] }
proc get_device_names {flag cable} { return [list {@1: 0x4BA00477: SOC} {@2: 0x02B050DD: FPGA}] }
proc open_device {h cable d device} { if {$device ne "@2: 0x02B050DD: FPGA"} { error "Wrong device" } }
proc device_lock {flag ms} { set ::locked 1 }
proc device_unlock {} { set ::locked 0 }
proc close_device {} { if {$::locked} { error "Still locked" } }
proc device_run_test_idle {} {}
proc device_ir_shift {flag value} { return 1 }
proc device_dr_shift {args} { return aabbccdd }
"""

_TOOLS = r"""
import sys, time
from pathlib import Path
tool, directory, *args = sys.argv[1:]
state = Path(directory)
if tool == "jtagconfig":
    if args[0] == "--enum":
        print("1) USB-BlasterII [remote bench]\n  4BA00477 SOC\n  02B050DD FPGA")
    elif args[0] == "--getparam":
        print((state / "clock").read_text())
    elif args[0] == "--setparam":
        (state / "clock").write_text(args[-1])
    elif args[0] == "--addserver":
        print(args[-1])
        sys.exit(args[-1] == "reject-me")
elif tool == "quartus_stp":
    import tkinter
    t = tkinter.Tcl()
    t.eval(HARDWARE)
    t.eval("source driver.tcl")
elif tool == "quartus_pgm":
    assert args[1] == "USB-BlasterII [remote bench]"
    assert args[-1].endswith("@2")
    if (state / "stall").exists():
        time.sleep(20)
    print("Quartus Programmer was successful")
""".replace("HARDWARE", repr(_TCL))


@pytest.fixture
def bench(io_runtime_context, io_bench, monkeypatch, tmp_path):
    tools = tmp_path / "Custom Quartus" / "quartus" / "bin64"
    tools.mkdir(parents=True)
    for name in ("jtagconfig", "quartus_pgm", "quartus_stp"):
        (tools / (name + ".exe" if os.name == "nt" else name)).touch()
    (tmp_path / "clock").write_text("6 MHz")
    calls = []
    launch = quartus._launch

    def fake_launch(tool, args, cwd, log):
        calls.append((tool.stem, args))
        return launch(Path(sys.executable), ["-B", "-c", _TOOLS, tool.stem, str(tmp_path), *args], cwd, log)

    monkeypatch.setattr(quartus, "_launch", fake_launch)
    load_config(io_bench(f"""
        [equipment.jtag]
        jtag_id = 1
        driver = "quartus"
        quartus_path = "{tools.parents[1].as_posix()}"
        jtag_server = "lab.example"
        jtag_server_password_env = "TEST_QUARTUS_PASSWORD"
        cfgmem_parts = ["flash"]
        ir_bits = 10
    """))
    return calls, {"jtag_id": 1, "target": "USB-BlasterII [remote bench]", "device": "@2"}


def test_inventory_and_flash(bench, tmp_path):
    calls, selected = bench
    api = col.equipment.jtag
    assert api.list_targets(jtag_id=1, key="targets")["targets"][0]["target"] == selected["target"]
    with pytest.raises(EquipmentConnectionError, match="exact Quartus remote cable"):
        api.list_devices(jtag_id=1, key="missing")
    devices = api.list_devices(**selected, key="chain")["devices"]
    assert [row["idcode"] for row in devices] == ["4BA00477", "02B050DD"]
    bit, flash = tmp_path / "design ;@ test.sof", tmp_path / "boot.jic"
    bit.touch()
    flash.touch()
    assert api.program_device(**selected, key="sof", image=bit)["configured"]
    assert api.list_cfgmem_parts(jtag_id=1, key="parts")["parts_source"] == "bench"
    assert api.program_cfgmem(**selected, key="program", image=flash, flash_part="flash")["flash_written"]
    verified = api.verify_cfgmem(**selected, key="verify", image=flash, flash_part="flash")
    assert verified["flash_verified"] and not verified["flash_written"]
    assert verified["flash_part"] == "flash"
    assert verified["flash_part_source"] == "bench"
    assert verified["flash_part_verified"] is False
    assert [args[-1] for tool, args in calls if tool == "quartus_pgm"] == [
        "p;image.sof@2", "pvi;image.jic@2", "iv;image.jic@2",
    ]
    resets = []
    boot = api.boot_from_cfgmem(**selected, key="boot", reset=lambda: resets.append(1), check_boot=lambda: bool(resets))
    assert boot["boot_method"] == "board_reset"


def test_stp_and_temporary_clock(bench, tmp_path):
    pytest.importorskip("tkinter")
    _, selected = bench
    api = col.equipment.jtag
    assert api.get_clock(**selected, key="get")["clock_hz"] == 6_000_000
    assert api.set_clock(**selected, key="set", clock_hz=16_000_000)["clock_scope"] == "cable"
    steps = [{"state": "IDLE"}, {"register": "IR", "bits": 10, "tdi": "006"},
             {"register": "DR", "bits": 32, "tdi": "00000000"}]
    result = api.scan(**selected, key="scan", scope="device", steps=steps, clock_hz=6_000_000)
    assert [row["tdo"] for row in result["scans"]] == ["001", "AABBCCDD"]
    assert (tmp_path / "clock").read_text() == "16000000"
    with pytest.raises(EquipmentCapabilityError, match="device scans"):
        api.scan(**selected, key="chain_scope", steps=steps)
    with pytest.raises(EquipmentCapabilityError, match="TAP state RESET"):
        api.scan(**selected, key="reset", scope="device", steps=[{"state": "RESET"}])
    result = api.run_tcl(**selected, key="tcl", tcl="lindex $argv 0", args=["a {$b} ;"])
    assert result["tcl_result"] == "a {$b} ;"
    result = api.run_tcl(**selected, key="selector", tcl="set jtag_device")
    assert result["tcl_result"] == "@2: 0x02B050DD: FPGA"
    with pytest.raises(EquipmentResponseError, match="Tcl rejected"):
        api.run_tcl(**selected, key="tcl_error", tcl="error {Tcl rejected}")


def test_timeout_restores_clock(bench, tmp_path):
    _, selected = bench
    image = tmp_path / "slow.sof"
    image.touch()
    (tmp_path / "stall").touch()
    with pytest.raises(EquipmentTimeoutError):
        col.equipment.jtag.program_device(**selected, key="timeout", image=image, clock_hz=16_000_000, timeout_s=2)
    assert (tmp_path / "clock").read_text() == "6000000"


def test_registration_is_explicit_and_private(bench, io_runtime_context, monkeypatch):
    calls, _ = bench
    monkeypatch.setenv("TEST_QUARTUS_PASSWORD", "reject-me")
    with pytest.raises(EquipmentConnectionError, match="check the Quartus server") as error:
        col.equipment.jtag.register_server(jtag_id=1, key="reject")
    assert "reject-me" not in str(error.value)
    assert not list(io_runtime_context.output_dir.glob("jtag/*.log"))
    monkeypatch.setenv("TEST_QUARTUS_PASSWORD", "test secret")
    assert col.equipment.jtag.register_server(jtag_id=1, key="register")["registered"]
    assert calls[-1] == ("jtagconfig", ["--addserver", "lab.example", "test secret"])
    io_runtime_context.run_options = RunOptions(dry_run=True)
    col.equipment.jtag.register_server(jtag_id=1, key="dry")
    assert len(calls) == 2



def test_quartus_ambiguous_cables_and_unknown_device():
    cables = quartus._inventory("1) USB-Blaster [USB-0]\n  04BA0047 ! ARM\n2) USB-Blaster [USB-1]")
    assert not cables[0]["devices"][0]["usable"]
    with pytest.raises(EquipmentConnectionError, match="exactly one Quartus target"):
        quartus._choose(cables, "target", None)
