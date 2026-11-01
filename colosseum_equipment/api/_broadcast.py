"""Fan-out helpers for void equipment APIs that accept ``*_id=\"all\"``."""

from __future__ import annotations

import logging
from collections.abc import Callable
from functools import wraps
from typing import Literal, TypeVar

from colosseum.config.loader import ConfigError
from colosseum.context import get_context

from colosseum_equipment.exceptions import EquipmentError

EquipmentId = int | Literal["all"]
_F = TypeVar("_F", bound=Callable[..., None])

_logger = logging.getLogger("colosseum.equipment.broadcast")


def list_equipment_ids(kind: str) -> list[int]:
    """Return sorted configured ids for ``equipment.<kind>``."""
    ctx = get_context()
    if ctx.config is None:
        raise ConfigError("Configuration is not loaded. Call col.config.load_config(path).")
    id_field = f"{kind}_id"
    return [int(row[id_field]) for row in ctx.config.list_items(f"equipment.{kind}")]


def resolve_equipment_ids(kind: str, equipment_id: EquipmentId) -> list[int]:
    """Resolve a single id or ``\"all\"`` into the list of targets."""
    if equipment_id != "all":
        return [int(equipment_id)]
    ids = list_equipment_ids(kind)
    if not ids:
        raise ConfigError(f"No configured equipment.{kind} rows for id='all'")
    return ids


def require_int_id(equipment_id: EquipmentId, *, kind: str) -> int:
    """Narrow ``EquipmentId`` to ``int`` after ``@broadcastable`` expansion."""
    if isinstance(equipment_id, int):
        return equipment_id
    raise TypeError(
        f"equipment.{kind} id='all' must be expanded by @broadcastable before instrument access",
    )


def broadcastable(kind: str, id_param: str) -> Callable[[_F], _F]:
    """Decorator (under ``@command``) that fans out when ``id_param=\"all\"``.

    Continues after per-id failures and raises :class:`EquipmentError` summarizing
    which ids failed. Numeric ids call the wrapped function once unchanged.
    """

    def decorate(fn: _F) -> _F:
        @wraps(fn)
        def wrapper(**kwargs: object) -> None:
            if id_param not in kwargs:
                raise TypeError(f"{fn.__name__} missing keyword-only argument '{id_param}'")
            equipment_id = kwargs[id_param]
            if equipment_id != "all":
                fn(**kwargs)
                return

            ids = resolve_equipment_ids(kind, "all")
            failures: list[tuple[int, BaseException]] = []
            for item_id in ids:
                try:
                    fn(**{**kwargs, id_param: item_id})
                except BaseException as exc:
                    if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                        raise
                    failures.append((item_id, exc))
                    _logger.warning(
                        "equipment.%s id=%s %s failed during id='all': %s",
                        kind,
                        item_id,
                        fn.__name__,
                        exc,
                    )
            if not failures:
                return

            parts = [f"id={item_id}: {type(exc).__name__}: {exc}" for item_id, exc in failures]
            failed = ", ".join(str(item_id) for item_id, _ in failures)
            raise EquipmentError(
                f"equipment.{kind} id='all' {fn.__name__}: failed ids {failed}; "
                + "; ".join(parts),
            )

        return wrapper  # type: ignore[return-value]

    return decorate
