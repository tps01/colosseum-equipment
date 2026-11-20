"""SCPI escape hatch (``col.equipment.scpi``).

Pass ``serial_id`` to run SCPI over a configured ``equipment.serial`` port (same as
``psu_id`` for VISA). For raw COM/TTY I/O use ``col.equipment.serial`` instead.
"""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any, cast

from colosseum.decorators import command
from colosseum.logging import get_logger

from colosseum_equipment.connections import get_transport
from colosseum_equipment.instruments.registry import kind_id_params
from colosseum_equipment.protocols.scpi import SCPIHelper, validate_register_mask

if TYPE_CHECKING:
    from collections.abc import Callable

_KIND_ID_PARAMS: dict[str, str] = kind_id_params()
_logger = get_logger("colosseum.equipment")


def _selected_instrument(**instrument_ids: object) -> tuple[str, int]:
    return _resolve_kind(
        **{key: instrument_ids[key] for key in _KIND_ID_PARAMS if instrument_ids.get(key) is not None},
    )




def _resolve_kind(**kwargs: object) -> tuple[str, int]:
    selected = [(kwargs[param], kind) for param, kind in _KIND_ID_PARAMS.items() if kwargs.get(param) is not None]
    if len(selected) != 1:
        names = ", ".join(f"{name}=" for name in _KIND_ID_PARAMS)
        raise ValueError(f"Specify exactly one of {names}")
    value, kind = selected[0]
    return kind, int(cast("int", value))


def _scpi_helper(**instrument_ids: object) -> SCPIHelper:
    kind, equipment_id = _resolve_kind(
        **{key: instrument_ids[key] for key in _KIND_ID_PARAMS if instrument_ids.get(key) is not None},
    )
    return for_instrument(kind, equipment_id)


def _make_scpi_api(name: str, method: str, return_annotation: object) -> Callable[..., object]:
    params = [
        inspect.Parameter("command", inspect.Parameter.KEYWORD_ONLY, annotation=str),
        *[
            inspect.Parameter(
                param,
                inspect.Parameter.KEYWORD_ONLY,
                default=None,
                annotation=int | None,
            )
            for param in _KIND_ID_PARAMS
        ],
    ]

    action = {
        "write": "Sending SCPI write to %s %s",
        "query": "Querying SCPI on %s %s",
        "query_float": "Querying a SCPI number on %s %s",
    }[method]

    def api(*, command: str, **instrument_ids: int | None) -> object:
        kind, equipment_id = _selected_instrument(**instrument_ids)
        _logger.info(action, kind, equipment_id)
        helper = _scpi_helper(**instrument_ids)
        return getattr(helper, method)(command)

    api.__name__ = name
    api.__qualname__ = name
    api.__module__ = __name__
    api_any: Any = api
    api_any.__signature__ = inspect.Signature(params, return_annotation=return_annotation)
    id_fields = "\n".join(
        f":param {param}: Configured equipment.{kind} ID; defaults to None. "
        "Pass exactly one instrument ID to this call."
        for param, kind in sorted(_KIND_ID_PARAMS.items())
    )
    if return_annotation is type(None):
        returns_line = "None"
    elif return_annotation is str:
        returns_line = "Instrument response text."
    elif return_annotation is float:
        returns_line = "Parsed float from the instrument response."
    else:
        returns_line = "Value from the instrument."
    api.__doc__ = f"""Send SCPI ``{method}`` to exactly one configured instrument.

:param command: SCPI command string (including terminators as required by the driver).
:type command: str
{id_fields}

:returns: {returns_line}
:raises ValueError: If zero or more than one ``*_id`` is provided.
:raises EquipmentConnectionError: Transport or instrument connection failed.
"""
    return command(api_any)




def _make_common_api(
    method: str,
    description: str,
    return_annotation: object,
    *,
    takes_mask: bool = False,
) -> Callable[..., object]:
    params = [
        inspect.Parameter(
            param,
            inspect.Parameter.KEYWORD_ONLY,
            default=None,
            annotation=int | None,
        )
        for param in _KIND_ID_PARAMS
    ]
    mask_doc = ""
    if takes_mask:
        params.insert(0, inspect.Parameter("mask", inspect.Parameter.KEYWORD_ONLY, annotation=int))
        mask_doc = ":param mask: Register bit mask from 0 through 255.\n"

    def api(**arguments: int | None) -> object:
        method_args: dict[str, int] = {}
        if takes_mask:
            if "mask" not in arguments:
                raise TypeError(f"{method}() requires the keyword-only argument 'mask'")
            method_args["mask"] = validate_register_mask(arguments.pop("mask"))

        kind, equipment_id = _selected_instrument(**arguments)
        _logger.info("Running SCPI %s on %s %s", method, kind, equipment_id)
        helper = for_instrument(kind, equipment_id)
        return getattr(helper, method)(**method_args)

    api.__name__ = method
    api.__qualname__ = method
    api.__module__ = __name__
    api.__annotations__["return"] = return_annotation
    api_any: Any = api
    api_any.__signature__ = inspect.Signature(params, return_annotation=return_annotation)
    id_fields = "\n".join(
        f":param {param}: Configured equipment.{kind} ID; defaults to None. "
        "Pass exactly one instrument ID to this call."
        for param, kind in sorted(_KIND_ID_PARAMS.items())
    )
    api.__doc__ = f"""{description}

{mask_doc}{id_fields}

:raises ValueError: If the instrument selection or register mask is invalid.
:raises EquipmentConnectionError: Transport or instrument connection failed.
"""
    return command(api_any)


def _make_drain_error_queue() -> Callable[..., list[str]]:
    params = [
        inspect.Parameter(
            "max_errors",
            inspect.Parameter.KEYWORD_ONLY,
            default=50,
            annotation=int,
        ),
        *[
            inspect.Parameter(
                param,
                inspect.Parameter.KEYWORD_ONLY,
                default=None,
                annotation=int | None,
            )
            for param in _KIND_ID_PARAMS
        ],
    ]

    def api(*, max_errors: int = 50, **instrument_ids: int | None) -> list[str]:
        kind, equipment_id = _selected_instrument(**instrument_ids)
        _logger.info(
            "Draining SCPI error queue on %s %s (up to %s)",
            kind,
            equipment_id,
            max_errors,
        )
        helper = _scpi_helper(**instrument_ids)
        return helper.drain_error_queue(max_errors=max_errors)

    api.__name__ = "drain_error_queue"
    api.__qualname__ = "drain_error_queue"
    api.__module__ = __name__
    api_any: Any = api
    api_any.__signature__ = inspect.Signature(params, return_annotation=list[str])
    id_fields = "\n".join(
        f":param {param}: Configured equipment.{kind} ID; defaults to None. "
        "Pass exactly one instrument ID to this call."
        for param, kind in sorted(_KIND_ID_PARAMS.items())
    )
    api.__doc__ = f"""Drain SCPI ``SYST:ERR?`` until empty (or ``max_errors``).

:param max_errors: Maximum number of error strings to read.
{id_fields}

:returns: List of raw error responses (last entry is typically ``0,"No error"``).
:raises ValueError: If zero or more than one ``*_id`` is provided.
"""
    return command(api_any)


clear_status = _make_common_api("clear_status", "Clear instrument status (``*CLS``).", None)
drain_error_queue = _make_drain_error_queue()
esr = _make_common_api("esr", "Read and clear the event status register (``*ESR?``).", int)
get_ese = _make_common_api("get_ese", "Read the standard event enable mask (``*ESE?``).", int)
get_sre = _make_common_api("get_sre", "Read the service request enable mask (``*SRE?``).", int)
identify = _make_common_api("identify", "Return the trimmed instrument identity (``*IDN?``).", str)
opc = _make_common_api(
    "opc",
    "Request an operation-complete event when pending operations finish (``*OPC``).",
    None,
)
reset = _make_common_api("reset", "Reset the instrument (``*RST``).", None)
self_test = _make_common_api("self_test", "Run self-test and return its integer result (``*TST?``).", int)
set_ese = _make_common_api("set_ese", "Write the standard event enable mask (``*ESE``).", None, takes_mask=True)
set_sre = _make_common_api("set_sre", "Write the service request enable mask (``*SRE``).", None, takes_mask=True)
wait_opc = _make_common_api("wait_opc", "Wait for an operation-complete reply (``*OPC?``).", None)
wait_to_continue = _make_common_api(
    "wait_to_continue",
    "Tell the instrument to finish pending operations before processing later commands (``*WAI``).",
    None,
)


def for_instrument(kind: str, equipment_id: int) -> SCPIHelper:
    """Return a SCPI helper for one configured instrument.

    :param kind: Registered equipment kind, such as psu or dmm.
    :param equipment_id: Integer ID from that kind's configuration section.
    :returns: SCPIHelper using the cached transport; helper calls are not decorated evidence APIs.
    :raises EquipmentConnectionError: The transport could not be opened.
    """
    return SCPIHelper(get_transport(kind, equipment_id))


query = _make_scpi_api("query", "query", str)
query_float = _make_scpi_api("query_float", "query_float", float)
status_byte = _make_common_api("status_byte", "Read the status byte (``*STB?``).", int)
write = _make_scpi_api("write", "write", None)
