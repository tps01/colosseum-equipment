"""VISA transport visa_library bench key."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from colosseum_equipment.transports.visa import VISATransport, open_resource_manager


def test_resource_manager_receives_visa_library() -> None:
    rm = MagicMock()
    inst = MagicMock()
    rm.open_resource.return_value = inst
    with patch("pyvisa.ResourceManager", return_value=rm) as rm_ctor:
        VISATransport("GPIB::1::INSTR", visa_library="@ivi")

    rm_ctor.assert_called_once_with("@ivi")
    rm.open_resource.assert_called_once_with("GPIB::1::INSTR")


def test_resource_manager_default_without_visa_library() -> None:
    rm = MagicMock()
    inst = MagicMock()
    rm.open_resource.return_value = inst
    with patch("pyvisa.ResourceManager", return_value=rm) as rm_ctor:
        VISATransport("GPIB::1::INSTR")

    rm_ctor.assert_called_once_with()


def test_open_resource_manager_falls_back_to_pyvisa_py() -> None:
    rm = object()

    def _ctor(library: str | None = None) -> object:
        if library is None:
            raise ValueError("Could not locate a VISA implementation")
        assert library == "@py"
        return rm

    with patch("pyvisa.ResourceManager", side_effect=_ctor) as rm_ctor:
        assert open_resource_manager() is rm
    assert [call.args for call in rm_ctor.call_args_list] == [(), ("@py",)]


def test_open_resource_manager_keeps_explicit_library() -> None:
    rm = object()
    with patch("pyvisa.ResourceManager", return_value=rm) as rm_ctor:
        assert open_resource_manager("@ivi") is rm
    rm_ctor.assert_called_once_with("@ivi")
