"""Colosseum equipment plugin (PSU, DMM, RF, SCPI, transports)."""

from importlib import metadata

from colosseum.config.sections import ConfigSectionSpec
from colosseum.logging import get_logger
from colosseum.plugins.registry import PluginRegistry

from colosseum_equipment.connections import close_all

__colosseum_domain__ = "equipment"

try:
    __version__ = metadata.version("colosseum-equipment")
except metadata.PackageNotFoundError:  # pragma: no cover
    __version__ = "0.0.0"

_logger = get_logger("colosseum.equipment")

_IO_CONFIG_SPECS = (
    ConfigSectionSpec(
        "io.dio",
        "dio_id",
        required_keys=(),
        optional_keys=(
            "driver",
            "resource",
            "port_lines",
            "direction",
            "model",
            "drive",
            "voltage",
            "library",
            "pins",
            "pin_names",
        ),
    ),
    ConfigSectionSpec(
        "io.i2c",
        "i2c_id",
        required_keys=(),
        optional_keys=(
            "driver",
            "resource",
            "model",
            "voltage",
            "clock_hz",
            "address",
            "address_bits",
            "pullup",
            "library",
            "nack",
            "read_data",
        ),
    ),
    ConfigSectionSpec(
        "io.spi",
        "spi_id",
        required_keys=(),
        optional_keys=(
            "driver",
            "resource",
            "model",
            "voltage",
            "clock_hz",
            "mode",
            "chip_select",
            "bits_per_word",
            "library",
            "read_data",
        ),
    ),
)


def register(registry: PluginRegistry) -> None:
    from colosseum_equipment import api
    from colosseum_equipment.instruments.registry import kind_specs
    from colosseum_equipment.io import api as io_api

    registry.register_namespace("equipment", api)
    registry.register_namespace("io", io_api)
    _logger.debug("Registered col.equipment and col.io namespaces")
    registry.register_shutdown(close_all)
    for kind_spec in kind_specs():
        registry.register_config_section(kind_spec.section())
    for io_spec in _IO_CONFIG_SPECS:
        registry.register_config_section(io_spec)
