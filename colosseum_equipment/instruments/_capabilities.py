from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import NoReturn, TypeVar

from colosseum_equipment.exceptions import EquipmentCapabilityError

_ModelT = TypeVar("_ModelT", bound=type)


def supported_commands(*names: str) -> Callable[[_ModelT], _ModelT]:
    """Restrict a new driver to its manual-backed public operations.

    Generic base classes expose several vendor dialects. A named driver must
    not accidentally send an inherited command outside its documented subset.
    Private helpers and transport cleanup remain available.
    """
    allowed = frozenset((*names, "close"))

    def decorate(cls: _ModelT) -> _ModelT:
        def refuse(method: Callable[..., object]) -> Callable[..., object]:
            @wraps(method)
            def call(self: object, *_args: object, **_kwargs: object) -> NoReturn:
                unsupported(
                    str(getattr(self, "_model", cls.__name__)), method.__name__,
                    detail="outside documented command subset",
                )

            return call

        for name in dir(cls):
            method = getattr(cls, name)
            if not name.startswith("_") and name not in allowed and callable(method):
                setattr(cls, name, refuse(method))
        return cls

    return decorate


def unsupported(model: str, operation: str, *, detail: str = "") -> NoReturn:
    message = f"{operation} is not supported by model `{model}`"
    if detail:
        message = f"{message} ({detail})"
    raise EquipmentCapabilityError(message)
