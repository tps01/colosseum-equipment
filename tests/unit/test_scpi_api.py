"""SCPI helper API: instrument id resolution and command dispatch."""

from __future__ import annotations

import inspect
from unittest.mock import Mock

import pytest
from colosseum_equipment.api import scpi
from colosseum_equipment.exceptions import EquipmentResponseError, EquipmentTimeoutError

pytestmark = pytest.mark.usefixtures("unit_runtime_context")


def test_resolve_kind_requires_exactly_one_id() -> None:
    with pytest.raises(ValueError, match="Specify exactly one"):
        scpi._resolve_kind()
    with pytest.raises(ValueError, match="Specify exactly one"):
        scpi._resolve_kind(psu_id=1, dmm_id=2)


def test_resolve_kind_maps_psu_id() -> None:
    kind, equipment_id = scpi._resolve_kind(psu_id=3)
    assert kind == "psu"
    assert equipment_id == 3


def test_scpi_api_functions_expose_instrument_signature() -> None:
    params = list(scpi.write.__signature__.parameters)
    assert params[0] == "command"
    assert "psu_id" in params
    assert "vna_id" in params
    assert "rtsa_id" in params


@pytest.mark.parametrize(
    ("name", "wire", "reply", "expected", "arguments"),
    [
        ("clear_status", "*CLS", None, None, {}),
        ("esr", "*ESR?", "32", 32, {}),
        ("status_byte", "*STB?", "64", 64, {}),
        ("identify", "*IDN?", " Maker,Model,Serial,1.0\r\n", "Maker,Model,Serial,1.0", {}),
        ("reset", "*RST", None, None, {}),
        ("self_test", "*TST?", "0", 0, {}),
        ("self_test", "*TST?", "-7", -7, {}),
        ("set_ese", "*ESE 0", None, None, {"mask": 0}),
        ("get_ese", "*ESE?", "+255", 255, {}),
        ("set_sre", "*SRE 255", None, None, {"mask": 255}),
        ("get_sre", "*SRE?", "0", 0, {}),
        ("opc", "*OPC", None, None, {}),
        ("wait_opc", "*OPC?", "+1", None, {}),
        ("wait_to_continue", "*WAI", None, None, {}),
    ],
)
def test_common_api_dispatch(monkeypatch, name, wire, reply, expected, arguments) -> None:
    transport = Mock()
    transport.query.return_value = reply
    get_transport = Mock(return_value=transport)
    monkeypatch.setattr(scpi, "get_transport", get_transport)

    assert getattr(scpi, name)(serial_id=2, **arguments) == expected

    get_transport.assert_called_once_with("serial", 2)
    if reply is None:
        transport.write.assert_called_once_with(wire)
        transport.query.assert_not_called()
    else:
        transport.query.assert_called_once_with(wire)
        transport.write.assert_not_called()


@pytest.mark.parametrize(("name", "arguments"), [("identify", {}), ("set_ese", {"mask": 1})])
def test_common_api_requires_one_target(monkeypatch, name, arguments) -> None:
    get_transport = Mock()
    monkeypatch.setattr(scpi, "get_transport", get_transport)
    helper = getattr(scpi, name)

    with pytest.raises(ValueError, match="Specify exactly one"):
        helper(**arguments)
    with pytest.raises(ValueError, match="Specify exactly one"):
        helper(psu_id=1, dmm_id=2, **arguments)
    get_transport.assert_not_called()


@pytest.mark.parametrize("mask", [-1, 256, True, 1.0, "1", None])
def test_mask_validation_precedes_open(monkeypatch, mask) -> None:
    get_transport = Mock()
    monkeypatch.setattr(scpi, "get_transport", get_transport)

    with pytest.raises(ValueError, match="integer from 0 through 255"):
        scpi.set_sre(psu_id=1, mask=mask)
    get_transport.assert_not_called()


def test_mask_is_a_required_keyword() -> None:
    mask = inspect.signature(scpi.set_ese).parameters["mask"]
    assert mask.kind == inspect.Parameter.KEYWORD_ONLY
    assert mask.default is inspect.Parameter.empty
    with pytest.raises(TypeError, match="mask"):
        scpi.set_ese(psu_id=1)


@pytest.mark.parametrize(
    ("name", "reply", "message"),
    [
        ("self_test", "ERROR 3", "invalid integer"),
        ("get_ese", "1.5", "invalid integer"),
        ("get_sre", "256", "outside 0 through 255"),
        ("wait_opc", "10", "expected 1"),
        ("wait_opc", "", "invalid integer"),
    ],
)
def test_common_api_rejects_invalid_replies(monkeypatch, name, reply, message) -> None:
    transport = Mock()
    transport.query.return_value = reply
    monkeypatch.setattr(scpi, "get_transport", Mock(return_value=transport))

    with pytest.raises(EquipmentResponseError, match=message):
        getattr(scpi, name)(psu_id=1)


def test_wait_opc_propagates_timeout_without_retry(monkeypatch) -> None:
    transport = Mock()
    transport.query.side_effect = EquipmentTimeoutError("timed out")
    monkeypatch.setattr(scpi, "get_transport", Mock(return_value=transport))

    with pytest.raises(EquipmentTimeoutError, match="timed out"):
        scpi.wait_opc(psu_id=1)
    transport.query.assert_called_once_with("*OPC?")
    transport.write.assert_not_called()


@pytest.mark.parametrize("name", ["set_ese", "set_sre"])
@pytest.mark.parametrize("mask", [-1, 256, True, 1.0, "1", None])
def test_direct_scpi_helper_rejects_invalid_masks(monkeypatch, name, mask) -> None:
    transport = Mock()
    monkeypatch.setattr(scpi, "get_transport", Mock(return_value=transport))
    helper = scpi.for_instrument("psu", 1)

    with pytest.raises(ValueError, match="integer from 0 through 255"):
        getattr(helper, name)(mask=mask)
    transport.write.assert_not_called()
