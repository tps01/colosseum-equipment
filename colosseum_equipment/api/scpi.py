"""SCPI escape hatch (``col.equipment.scpi``).

Pass ``serial_id`` to run SCPI over a configured ``equipment.serial`` port (same as
``psu_id`` for VISA). For raw COM/TTY I/O use ``col.equipment.serial`` instead.
"""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any, cast

from colosseum.decorators import command

from colosseum_equipment.connections import get_transport
from colosseum_equipment.instruments.registry import kind_id_params
from colosseum_equipment.protocols.scpi import SCPIHelper

if TYPE_CHECKING:
    from collections.abc import Callable

_KIND_ID_PARAMS: dict[str, str] = kind_id_params()


def for_instrument(kind: str, equipment_id: int) -> SCPIHelper:
    return SCPIHelper(get_transport(kind, equipment_id))


def _resolve_kind(**kwargs: object) -> tuple[str, int]:
    selected = [
        (kwargs[param], kind)
        for param, kind in _KIND_ID_PARAMS.items()
        if kwargs.get(param) is not None
    ]
    if len(selected) != 1:
        names = ", ".join(f"{name}=" for name in _KIND_ID_PARAMS)
        raise ValueError(f"Specify exactly one of {names}")
    value, kind = selected[0]
    return kind, int(cast("int", value))


def _scpi_helper(**instrument_ids: object) -> SCPIHelper:
    kind, equipment_id = _resolve_kind(
        **{
            key: instrument_ids[key]
            for key in _KIND_ID_PARAMS
            if instrument_ids.get(key) is not None
        },
    )
    return for_instrument(kind, equipment_id)


def _make_scpi_api(name: str, method: str, return_annotation: object) -> Callable[..., object]:
    params = [
        inspect.Parameter("command", inspect.Parameter.KEYWORD_ONLY, annotation=str),
        *[
            inspect.Parameter(
                param, inspect.Parameter.KEYWORD_ONLY, default=None, annotation=int | None,
            )
            for param in _KIND_ID_PARAMS
        ],
    ]

    def api(*, command: str, **instrument_ids: int | None) -> object:
        helper = _scpi_helper(**instrument_ids)
        return getattr(helper, method)(command)

    api.__name__ = name
    api.__qualname__ = name
    api.__module__ = __name__
    api_any: Any = api
    api_any.__signature__ = inspect.Signature(params, return_annotation=return_annotation)
    id_list = ", ".join(sorted(_KIND_ID_PARAMS))
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
:param {id_list}: Pass exactly one ``*_id`` matching a configured instrument.

:returns: {returns_line}
:raises ValueError: If zero or more than one ``*_id`` is provided.
:raises EquipmentConnectionError: Transport or instrument connection failed.
"""
    return command(api_any)


write = _make_scpi_api("write", "write", None)
query = _make_scpi_api("query", "query", str)
query_float = _make_scpi_api("query_float", "query_float", float)


def _make_status_api(name: str, method: str, return_annotation: object) -> Callable[..., object]:
    params = [
        *[
            inspect.Parameter(
                param, inspect.Parameter.KEYWORD_ONLY, default=None, annotation=int | None,
            )
            for param in _KIND_ID_PARAMS
        ],
    ]

    def api(**instrument_ids: int | None) -> object:
        helper = _scpi_helper(**instrument_ids)
        return getattr(helper, method)()

    api.__name__ = name
    api.__qualname__ = name
    api.__module__ = __name__
    api_any: Any = api
    api_any.__signature__ = inspect.Signature(params, return_annotation=return_annotation)
    id_list = ", ".join(sorted(_KIND_ID_PARAMS))
    api.__doc__ = f"""SCPI status helper ``{method}`` on exactly one configured instrument.

:param {id_list}: Pass exactly one ``*_id`` matching a configured instrument.

:raises ValueError: If zero or more than one ``*_id`` is provided.
:raises EquipmentConnectionError: Transport or instrument connection failed.
"""
    return command(api_any)


status_byte = _make_status_api("status_byte", "status_byte", int)
esr = _make_status_api("esr", "esr", int)
clear_status = _make_status_api("clear_status", "clear_status", None)


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
                param, inspect.Parameter.KEYWORD_ONLY, default=None, annotation=int | None,
            )
            for param in _KIND_ID_PARAMS
        ],
    ]

    def api(*, max_errors: int = 50, **instrument_ids: int | None) -> list[str]:
        helper = _scpi_helper(**instrument_ids)
        return helper.drain_error_queue(max_errors=max_errors)

    api.__name__ = "drain_error_queue"
    api.__qualname__ = "drain_error_queue"
    api.__module__ = __name__
    api_any: Any = api
    api_any.__signature__ = inspect.Signature(params, return_annotation=list[str])
    id_list = ", ".join(sorted(_KIND_ID_PARAMS))
    api.__doc__ = f"""Drain SCPI ``SYST:ERR?`` until empty (or ``max_errors``).

:param max_errors: Maximum number of error strings to read.
:param {id_list}: Pass exactly one ``*_id`` matching a configured instrument.

:returns: List of raw error responses (last entry is typically ``0,"No error"``).
:raises ValueError: If zero or more than one ``*_id`` is provided.
"""
    return command(api_any)


drain_error_queue = _make_drain_error_queue()
