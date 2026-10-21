"""pyVISA resource sharing and ASRL byte helpers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from colosseum_equipment.connections import close_all
from colosseum_equipment.transports.visa import VISATransport, normalize_visa_resource


def test_normalize_com_port_to_asrl() -> None:
    assert normalize_visa_resource("COM5") == "ASRL5::INSTR"
    assert normalize_visa_resource("com12:") == "ASRL12::INSTR"
    assert normalize_visa_resource("ASRL4::INSTR") == "ASRL4::INSTR"
    assert normalize_visa_resource("GPIB0::19::INSTR") == "GPIB0::19::INSTR"
    assert normalize_visa_resource("/dev/ttyUSB0") == "ASRL/dev/ttyUSB0::INSTR"


def test_shared_manager_closes_with_the_runtime(unit_runtime_context) -> None:
    rm = MagicMock()
    rm.open_resource.return_value = MagicMock()
    with patch("pyvisa.ResourceManager", return_value=rm) as constructor:
        first = VISATransport("GPIB::1::INSTR")
        second = VISATransport("GPIB::2::INSTR", visa_library="@ivi")
    assert constructor.call_count == 2
    first.close()
    second.close()
    rm.close.assert_not_called()
    assert any(key.startswith("visa:manager:") for key in unit_runtime_context.resource_cache)
    close_all()
    assert rm.close.call_count == 2
    assert unit_runtime_context.resource_cache == {}


def test_one_library_is_opened_once(unit_runtime_context) -> None:
    rm = MagicMock()
    rm.open_resource.return_value = MagicMock()
    with patch("pyvisa.ResourceManager", return_value=rm) as constructor:
        VISATransport("GPIB::1::INSTR")
        VISATransport("GPIB::2::INSTR")
    constructor.assert_called_once_with()
    assert rm.open_resource.call_count == 2
    close_all()


def test_private_manager_closes_with_the_transport() -> None:
    rm = MagicMock()
    rm.open_resource.return_value = MagicMock()
    with patch("pyvisa.ResourceManager", return_value=rm):
        transport = VISATransport("GPIB::1::INSTR")
    transport.close()
    rm.close.assert_called_once()


def test_line_mode_sets_baud_and_newline() -> None:
    rm = MagicMock()
    inst = MagicMock()
    rm.open_resource.return_value = inst
    with patch("pyvisa.ResourceManager", return_value=rm):
        VISATransport("ASRL4::INSTR", baudrate=9600, line_mode=True)
    rm.open_resource.assert_called_once_with(
        "ASRL4::INSTR",
        read_termination="\n",
        write_termination="\n",
    )
    assert inst.baud_rate == 9600


def test_asrl_byte_helpers() -> None:
    rm = MagicMock()
    inst = MagicMock()
    inst.read_bytes.side_effect = [b"O", b"K", b"\r"]
    inst.bytes_in_buffer = 0
    rm.open_resource.return_value = inst
    with patch("pyvisa.ResourceManager", return_value=rm):
        transport = VISATransport("ASRL4::INSTR", line_mode=True, baudrate=9600)

    transport.write_bytes(b"IDN?\r")
    inst.write_raw.assert_called_once_with(b"IDN?\r")
    assert transport.read_until(b"\r") == "OK\r"
    assert transport.in_waiting() == 0
    transport.flush()
    inst.flush.assert_called_once()
