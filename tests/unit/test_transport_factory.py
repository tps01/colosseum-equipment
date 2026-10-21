"""Transport factory defaults when config TOML omits driver."""

from __future__ import annotations

import logging
from unittest.mock import patch

import pytest
from colosseum.exceptions import ProceduralFault
from colosseum_equipment.transports.factory import open_transport
from colosseum_equipment.transports.sim import SimTransport


def _visa_kwargs(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "timeout": 5.0,
        "visa_backend": None,
        "sim_definition": None,
        "visa_library": None,
        "baudrate": None,
        "line_mode": False,
    }
    values.update(overrides)
    return values


def test_open_transport_defaults_to_visa_for_psu() -> None:
    with patch("colosseum_equipment.transports.factory.VISATransport") as visa_cls:
        visa_cls.return_value = object()
        open_transport("psu", 1, {"resource": "GPIB::1::INSTR"})
    visa_cls.assert_called_once_with("GPIB::1::INSTR", **_visa_kwargs())


def test_open_transport_defaults_to_asrl_for_serial_kind() -> None:
    with patch("colosseum_equipment.transports.factory.VISATransport") as visa_cls:
        visa_cls.return_value = object()
        open_transport("serial", 1, {"port": "COM4"})
    visa_cls.assert_called_once_with(
        "ASRL4::INSTR",
        **_visa_kwargs(baudrate=115200, line_mode=True),
    )


def test_open_transport_explicit_serial_driver_uses_pyvisa() -> None:
    with patch("colosseum_equipment.transports.factory.VISATransport") as visa_cls:
        visa_cls.return_value = object()
        open_transport("psu", 1, {"driver": "serial", "port": "COM2", "baudrate": 9600})
    visa_cls.assert_called_once_with(
        "ASRL2::INSTR",
        **_visa_kwargs(baudrate=9600, line_mode=True),
    )


def test_open_transport_explicit_sim() -> None:
    with patch("colosseum_equipment.transports.factory.SimTransport", spec=SimTransport) as sim_cls:
        sim_cls.return_value = object()
        open_transport("psu", 1, {"driver": "sim", "resource": "SIM::1"})
    sim_cls.assert_called_once_with("psu", 1, {"driver": "sim", "resource": "SIM::1"})


def test_open_transport_missing_resource_raises() -> None:
    with pytest.raises(ProceduralFault, match="missing `resource`"):
        open_transport("psu", 1, {})


def test_open_transport_port_without_driver_uses_asrl_for_attn() -> None:
    with patch("colosseum_equipment.transports.factory.VISATransport") as visa_cls:
        visa_cls.return_value = object()
        open_transport("attn", 1, {"port": "COM3"})
    visa_cls.assert_called_once_with(
        "ASRL3::INSTR",
        **_visa_kwargs(baudrate=115200, line_mode=True),
    )


def test_open_transport_gnss_com_uses_9600() -> None:
    with patch("colosseum_equipment.transports.factory.VISATransport") as visa_cls:
        visa_cls.return_value = object()
        open_transport("gnss", 1, {"port": "COM7"})
    visa_cls.assert_called_once_with(
        "ASRL7::INSTR",
        **_visa_kwargs(baudrate=9600, line_mode=True),
    )


def test_open_transport_serial_kind_without_port_raises() -> None:
    with pytest.raises(ProceduralFault, match="missing `port`"):
        open_transport("serial", 1, {})


def test_open_transport_both_fields_uses_visa_and_warns(caplog: pytest.LogCaptureFixture) -> None:
    with patch("colosseum_equipment.transports.factory.VISATransport") as visa_cls:
        visa_cls.return_value = object()
        with caplog.at_level(logging.WARNING, logger="colosseum.equipment"):
            open_transport("psu", 1, {"resource": "GPIB::1::INSTR", "port": "COM1"})
    visa_cls.assert_called_once()
    assert visa_cls.call_args.args[0] == "GPIB::1::INSTR"
    assert "ignoring port" in caplog.text
