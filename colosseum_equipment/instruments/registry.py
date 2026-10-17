"""Instrument kind and model registration.

A new model is one class file in ``instruments/<kind>/``:

.. code-block:: python

    @instrument_model("rtsa", "vendor-model")
    class VendorModel(GenericRtsa):
        '''Manual: https://example.invalid/programming-guide'''

The kind package loads that file on its own. Override only the methods whose
commands differ from the generic class.
"""

from __future__ import annotations

import importlib
import pkgutil
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from functools import wraps
from types import FunctionType
from typing import Any, TypeVar

from colosseum.config.sections import ConfigSectionSpec
from colosseum.logging import get_logger

from colosseum_equipment.instruments._config_keys import VISA_OPTIONAL_KEYS
from colosseum_equipment.transports.base import Transport

InstrumentBuilder = Callable[[Transport, dict[str, Any]], object]
_ModelT = TypeVar("_ModelT", bound=type)

_logger = get_logger("colosseum.equipment")
_builders: dict[str, dict[str, InstrumentBuilder]] = defaultdict(dict)
_kind_specs: dict[str, KindSpec] = {}
_load_state = "idle"
_best_effort_warned: set[tuple[str, str]] = set()

_SERIAL_OPTIONAL = ("driver", "baudrate", "timeout", "sim_read")
_HTTP_OPTIONAL = ("driver", "timeout", "username", "password")


@dataclass(frozen=True)
class KindSpec:
    """Config section for one equipment kind."""

    kind: str
    address: str = "visa"
    extra_optional: tuple[str, ...] = ()

    @property
    def id_field(self) -> str:
        return f"{self.kind}_id"

    def section(self) -> ConfigSectionSpec:
        if self.address == "serial":
            optional = tuple(dict.fromkeys((*_SERIAL_OPTIONAL, *self.extra_optional)))
            return ConfigSectionSpec(
                f"equipment.{self.kind}",
                self.id_field,
                required_keys=("port",),
                optional_keys=optional,
            )
        if self.address == "http":
            optional = tuple(dict.fromkeys((*_HTTP_OPTIONAL, *self.extra_optional)))
            return ConfigSectionSpec(
                f"equipment.{self.kind}",
                self.id_field,
                required_keys=("resource",),
                optional_keys=optional,
            )
        optional_keys = tuple(dict.fromkeys((*VISA_OPTIONAL_KEYS, *self.extra_optional)))
        if self.address == "either" and "port" not in optional_keys:
            optional_keys = (*optional_keys, "port")
        required = () if self.address == "either" else ("resource",)
        return ConfigSectionSpec(
            f"equipment.{self.kind}",
            self.id_field,
            required_keys=required,
            optional_keys=optional_keys,
        )


def register_kind(spec: KindSpec) -> None:
    _kind_specs[spec.kind] = spec


def register(kind: str, model: str, builder: InstrumentBuilder) -> None:
    _builders[kind][model.lower()] = builder


def register_aliases(kind: str, models: tuple[str, ...], builder: InstrumentBuilder) -> None:
    for model in models:
        register(kind, model, builder)


def instrument_model(
    kind: str,
    model: str,
    *aliases: str,
    extra_optional: tuple[str, ...] = (),
    address: str = "visa",
) -> Callable[[_ModelT], _ModelT]:
    """Register ``cls`` as ``model`` (and ``aliases``) for ``kind`` when the module imports."""

    def decorate(cls: _ModelT) -> _ModelT:
        if model == "generic":
            register_kind(KindSpec(kind, address=address, extra_optional=extra_optional))

        def build(transport: Transport, config: dict[str, Any]) -> object:
            return cls(transport, config)

        register(kind, model, build)
        for alias in aliases:
            register(kind, alias, build)
        cls.model_slug = model  # type: ignore[attr-defined]
        cls.instrument_kind = kind  # type: ignore[attr-defined]
        return cls

    return decorate


def best_effort_commands(cls: _ModelT) -> _ModelT:
    """Warn once when a named model inherits a generic command, then run it."""
    for name, member in list(vars(cls).items()):
        if name.startswith("_") or not isinstance(member, FunctionType):
            continue
        setattr(cls, name, _best_effort(member, cls))
    return cls


def _best_effort(method: FunctionType, owner: type) -> Callable[..., object]:
    @wraps(method)
    def wrapper(self: object, *args: object, **kwargs: object) -> object:
        live = getattr(type(self), method.__name__, None)
        if type(self) is not owner and live is wrapper:
            configured = getattr(self, "_model", None)
            if isinstance(configured, str) and configured not in ("", "generic"):
                model_name = configured
            else:
                model_name = str(getattr(type(self), "model_slug", type(self).__name__))
            if model_name != "generic":
                key = (model_name, method.__name__)
                if key not in _best_effort_warned:
                    _best_effort_warned.add(key)
                    kind_name = getattr(type(self), "instrument_kind", None) or getattr(
                        owner, "instrument_kind", "equipment",
                    )
                    _logger.warning(
                        "%s model `%s` %s is using generic SCPI; confirm the command "
                        "matches this instrument",
                        kind_name,
                        model_name,
                        method.__name__,
                    )
        return method(self, *args, **kwargs)

    return wrapper


def reset_best_effort_warnings() -> None:
    _best_effort_warned.clear()


def ensure_instruments_loaded() -> None:
    """Import every instrument package so model decorators run."""
    global _load_state
    if _load_state != "idle":
        return
    _load_state = "loading"
    try:
        import colosseum_equipment.instruments as instruments_pkg

        for info in pkgutil.iter_modules(instruments_pkg.__path__):
            if not info.ispkg:
                continue
            package_name = f"{instruments_pkg.__name__}.{info.name}"
            package = importlib.import_module(package_name)
            for module_info in pkgutil.iter_modules(package.__path__):
                if module_info.name.startswith("_"):
                    continue
                importlib.import_module(f"{package_name}.{module_info.name}")
        if "serial" not in _kind_specs:
            register_kind(KindSpec("serial", address="serial"))
    except Exception:
        _load_state = "idle"
        raise
    _load_state = "ready"


def kind_specs() -> tuple[KindSpec, ...]:
    ensure_instruments_loaded()
    return tuple(_kind_specs[name] for name in sorted(_kind_specs))


def kind_id_params() -> dict[str, str]:
    """Map ``col.equipment.scpi`` keyword (``rtsa_id``) to kind (``rtsa``)."""
    return {spec.id_field: spec.kind for spec in kind_specs()}


def build_registered(kind: str, model: str, transport: Transport, config: dict[str, Any]) -> object:
    ensure_instruments_loaded()
    model_key = model.lower()
    kind_map = _builders.get(kind)
    if not kind_map:
        raise RuntimeError(f"Unsupported equipment kind `{kind}`")
    if model_key in kind_map:
        return kind_map[model_key](transport, config)
    if model_key in ("generic", "") and "generic" in kind_map:
        return kind_map["generic"](transport, config)
    raise RuntimeError(f"Unsupported equipment model `{model}` for {kind}")


def registered_kinds() -> frozenset[str]:
    ensure_instruments_loaded()
    return frozenset(_builders)


def registered_models(kind: str) -> frozenset[str]:
    ensure_instruments_loaded()
    return frozenset(_builders.get(kind, {}))
