"""Autoconfig entry point for ``col.equipment.autoconfig``."""

from __future__ import annotations

from typing import TYPE_CHECKING

from colosseum.config.loader import (
    ConfigError,
    ConfigStore,
    apply_raw_config,
    default_test_name,
)
from colosseum.context import apply_no_artifacts, get_context, init_context
from colosseum.logging.setup import setup_logging

from colosseum_equipment.autoconfig.discovery import discover_equipment_config
from colosseum_equipment.autoconfig.toml_write import TomlWriteError, write_config_toml

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path


def autoconfig(
    *,
    timeout: float = 5.0,
    visa_library: str | None = None,
    blacklist: str | Sequence[str] | None = None,
    export_path: str | Path | None = None,
    no_artifacts: bool = False,
) -> ConfigStore:
    """Scan VISA ``?*INSTR`` and serial COM ports; build equipment config.

    Serial ASRL/COM ports try bare ``IDN?`` then ``*IDN?`` across common bauds.
    Fluke handheld ``QM`` is probed only after IDN fails. FTDI adapters are not
    discovered.

    :param timeout: Probe timeout in seconds for each resource/port.
    :type timeout: float, optional
    :param visa_library: Optional PyVISA ``ResourceManager`` library path (for example ``@ivi``).
    :type visa_library: str | None, optional
    :param blacklist: Interface name(s) or local IPv4 address(es) whose subnets are excluded
        from TCPIP autoconfig (GPIB/USB/ASRL are unaffected).
    :type blacklist: str | Sequence[str] | None, optional
    :param export_path: When set, write the generated config to this TOML file path.
    :type export_path: str | Path | None, optional
    :param no_artifacts: When ``True``, skip ``outputs/``, ``debug.log``, and on-disk SQLite.
    :type no_artifacts: bool, optional

    :returns: Normalized configuration store for discovered equipment.
    :rtype: ConfigStore

    :raises ConfigError: When PyVISA is unavailable, no resources are found, or none classify.
    :raises RuntimeError: When ``no_artifacts`` is set after runtime bootstrap.
    """
    try:
        ctx = get_context()
    except RuntimeError:
        ctx = init_context(
            test_case_name=default_test_name(),
            config_path="(autoconfig)",
            no_artifacts=no_artifacts,
        )
    else:
        apply_no_artifacts(ctx, no_artifacts=no_artifacts)

    if ctx.logger is None:
        ctx.logger = setup_logging(ctx, console=True, file=False)

    result = discover_equipment_config(
        timeout=timeout,
        visa_library=visa_library,
        blacklist=blacklist,
        logger=ctx.logger,
    )
    store = apply_raw_config(ctx, result.raw, source_label="(autoconfig)")
    if export_path is not None:
        try:
            exported = write_config_toml(result.raw, export_path)
        except TomlWriteError as exc:
            raise ConfigError(str(exc)) from exc
        if ctx.logger is not None:
            ctx.logger.info("Autoconfig exported config to %s", exported)
        if ctx.db.is_initialized():
            ctx.db.insert_run_metadata("config_export_path", str(exported))
    return store
