"""Unit tests for serial protocol helpers."""

from __future__ import annotations

from colosseum.context import init_context
from colosseum_equipment.protocols.serial import SerialChannel, strip_ansi
from colosseum_equipment.transports.sim import SimTransport


def test_strip_ansi_removes_csi_sequences() -> None:
    colored = "\x1b[31mERR\x1b[0m OK"
    assert strip_ansi(colored) == "ERR OK"


def test_serial_channel_write_and_read_until_on_sim(isolated_cwd) -> None:
    init_context(test_case_name="serial-protocol")
    transport = SimTransport(
        "serial",
        1,
        {"sim_read": "BOOT OK\r\nREADY\r\n"},
    )
    channel = SerialChannel(transport)
    channel.write("AT", append_newline="\r\n")
    boot = channel.read_until("OK")
    assert boot == "BOOT OK"
    channel.read_line()
    ready = channel.read_line()
    assert ready == "READY"
