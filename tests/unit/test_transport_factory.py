"""Transport factory defaults when config TOML omits driver."""

from __future__ import annotations

import logging
from unittest.mock import patch

import pytest
from colosseum_equipment.exceptions import EquipmentConnectionError
from colosseum_equipment.transports.factory import open_transport
from colosseum_equipment.transports.sim import SimTransport


def test_open_transport_defaults_to_visa_for_psu() -> None:
    with patch("colosseum_equipment.transports.factory.VISATransport") as visa_cls:
        visa_cls.return_value = object()
        open_transport("psu", 1, {"resource": "GPIB::1::INSTR"})
    visa_cls.assert_called_once_with(
        "GPIB::1::INSTR",
        timeout=5.0,
        visa_backend=None,
        sim_definition=None,
        visa_library=None,
    )


def test_open_transport_defaults_to_serial_for_serial_kind() -> None:
    with patch("colosseum_equipment.transports.factory.SerialTransport") as serial_cls:
        serial_cls.return_value = object()
        open_transport("serial", 1, {"port": "COM4"})
    serial_cls.assert_called_once()


def test_open_transport_explicit_sim() -> None:
    with patch("colosseum_equipment.transports.factory.SimTransport", spec=SimTransport) as sim_cls:
        sim_cls.return_value = object()
        open_transport("psu", 1, {"driver": "sim", "resource": "SIM::1"})
    sim_cls.assert_called_once_with("psu", 1, {"driver": "sim", "resource": "SIM::1"})


def test_open_transport_missing_resource_raises() -> None:
    with pytest.raises(EquipmentConnectionError, match="missing `resource`"):
        open_transport("psu", 1, {})


def test_open_transport_port_without_driver_uses_serial_for_attn() -> None:
    with patch("colosseum_equipment.transports.factory.SerialTransport") as serial_cls:
        serial_cls.return_value = object()
        open_transport("attn", 1, {"port": "COM3"})
    serial_cls.assert_called_once()
    assert serial_cls.call_args.args[0] == "COM3"


def test_open_transport_serial_kind_without_port_raises() -> None:
    with pytest.raises(EquipmentConnectionError, match="missing `port`"):
        open_transport("serial", 1, {})


def test_open_transport_both_fields_uses_visa_and_warns(caplog: pytest.LogCaptureFixture) -> None:
    with patch("colosseum_equipment.transports.factory.VISATransport") as visa_cls:
        visa_cls.return_value = object()
        with caplog.at_level(logging.WARNING, logger="colosseum.equipment"):
            open_transport("psu", 1, {"resource": "GPIB::1::INSTR", "port": "COM1"})
    visa_cls.assert_called_once()
    assert visa_cls.call_args.args[0] == "GPIB::1::INSTR"
    assert "ignoring port" in caplog.text
