"""Batch JTAG operations for a configured bench. Supports Vivado and Quartus."""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from colosseum.context import get_context
from colosseum.decorators import CommandResult, command, measurement

from colosseum_equipment.exceptions import EquipmentCapabilityError
from colosseum_equipment.jtag import quartus, vivado

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

_DEFAULT_TIMEOUT_S = 300.0
_DRIVERS = {"vivado": vivado.run, "quartus": quartus.run}
_OVERRIDES = {"target", "device", "clock_hz", "timeout_s"}
_VIVADO_OVERRIDES = {"hw_server_url", "xvc_url"}
_ENDPOINT = re.compile(r"(?:TCP:)?(?:[A-Za-z\d.-]+|\[[0-9A-Fa-f:]+\]):(\d+)", re.IGNORECASE)


def _file(value: str | Path, suffixes: tuple[str, ...]) -> str:
    path = Path(value).expanduser().absolute()
    if not path.is_file() or path.suffix.lower() not in suffixes:
        raise ValueError(f"Expected an existing {'/'.join(suffixes)} file: {path}")
    return path.as_posix()


def _validate_endpoints(settings: dict[str, Any]) -> None:
    for field in ("hw_server_url", "xvc_url"):
        if value := settings.get(field):
            match = _ENDPOINT.fullmatch(str(value))
            if not match or not 1 <= int(match[1]) <= 65535:
                raise ValueError(f"{field} must be a host:port endpoint")
            if field == "xvc_url":
                settings[field] = re.sub("^tcp:", "", str(value), flags=re.I)


def _settings(driver: str, settings: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    if driver == "quartus" and any(settings.get(name) or overrides.get(name) for name in _VIVADO_OVERRIDES):
        raise EquipmentCapabilityError("Quartus uses a native JTAG server and cable selector")
    allowed = _OVERRIDES | _VIVADO_OVERRIDES if driver == "vivado" else _OVERRIDES
    unknown = overrides.keys() - allowed
    if unknown:
        raise TypeError(f"Unsupported JTAG options: {', '.join(sorted(unknown))}")
    settings = settings | {name: value for name, value in overrides.items() if value is not None}
    _validate_endpoints(settings)
    return settings


def _validate_scope(driver: str, scope: str, steps: list[str]) -> None:
    supported_scope = "chain" if driver == "vivado" else "device"
    if scope != supported_scope:
        raise EquipmentCapabilityError(f"{driver} supports raw {supported_scope} scans")
    if not steps:
        raise ValueError("Supply at least one scan step")


def _dispatch(jtag_id: int, key: str, operation: str, overrides: dict[str, Any], **fields: Any) -> dict[str, Any]:
    ctx = get_context()
    if ctx.config is None:
        raise ValueError("Load a bench config with an equipment.jtag row")
    settings = ctx.config.require_item("equipment.jtag", jtag_id)
    driver = settings.get("driver", "vivado")
    runner = _DRIVERS.get(driver)
    if runner is None:
        raise EquipmentCapabilityError(f"Unsupported JTAG driver: {driver}")
    settings = _settings(driver, settings, overrides)
    if driver == "vivado" and operation == "register_server":
        raise EquipmentCapabilityError("Vivado connects through hw_server_url")
    if driver != "quartus" and fields.get("while_tethered") is not None:
        raise EquipmentCapabilityError("Tethered evaluation requires Quartus")
    if operation == "scan":
        _validate_scope(driver, fields.pop("scope"), fields["steps"])
    clock = settings.get("clock_hz")
    if clock is not None and (type(clock) is not int or clock <= 0):
        raise ValueError("clock_hz must be a positive integer")
    mutating = {"program_device", "program_cfgmem", "verify_cfgmem", "boot", "boot_probe"}
    if settings.get("xvc_url") and operation in mutating and settings.get("xvc_programming") is not True:
        raise EquipmentCapabilityError("This operation requires xvc_programming = true for a qualified XVC endpoint")
    request = {name: settings.get(name) for name in ("xvc_url", "target", "device", "clock_hz")}
    if operation == "get_clock":
        request.pop("clock_hz")
    request.update(operation=operation, **fields)
    return runner(settings, request, timeout_s=float(settings.get("timeout_s", _DEFAULT_TIMEOUT_S)), key=key)


@command
def register_server(*, jtag_id: int, key: str) -> dict[str, Any]:
    """Register a Quartus remote server using the bench's credential environment variable.

    :param jtag_id: Configured JTAG bench ID.
    :param key: Evidence key for this operation.
    """
    return _dispatch(jtag_id, key, "register_server", {})


@measurement
def list_targets(*, jtag_id: int, key: str, **options: Any) -> dict[str, Any]:
    """List targets for the configured JTAG backend.

    :param jtag_id: Configured JTAG bench ID.
    :param key: Evidence key for this operation.
    :param options: Per-operation JTAG settings.
    """
    return _dispatch(jtag_id, key, "list_targets", options)


@measurement
def list_devices(*, jtag_id: int, key: str, **options: Any) -> dict[str, Any]:
    """Read ordered devices, exact selectors, and available IDCODEs.

    :param jtag_id: Configured JTAG bench ID.
    :param key: Evidence key for this operation.
    :param options: Per-operation JTAG settings, including the target selector.
    """
    return _dispatch(jtag_id, key, "list_devices", options)


@measurement
def get_clock(*, jtag_id: int, key: str, **options: Any) -> dict[str, Any]:
    """Read the clock reported for the selected target.

    :param jtag_id: Configured JTAG bench ID.
    :param key: Evidence key for this operation.
    :param options: Per-operation JTAG settings.
    """
    return _dispatch(jtag_id, key, "get_clock", options | {"clock_hz": None})


@command
def set_clock(*, jtag_id: int, clock_hz: int, key: str, **options: Any) -> dict[str, Any]:
    """Apply and report a clock in Hz with the backend-specific scope.

    :param jtag_id: Configured JTAG bench ID.
    :param key: Evidence key for this operation.
    :param clock_hz: Requested JTAG clock in Hz.
    :param options: Per-operation JTAG settings.
    """
    if clock_hz is None:
        raise ValueError("clock_hz must be a positive integer")
    return _dispatch(jtag_id, key, "set_clock", options | {"clock_hz": clock_hz})


@measurement
def scan(
    *, jtag_id: int, steps: Sequence[dict[str, Any]], key: str, scope: str = "chain", **options: Any,
) -> dict[str, Any]:
    """Run TAP and IR/DR steps in one batch job using chain or device scope.

    :param jtag_id: Configured JTAG bench ID.
    :param key: Evidence key for this operation.
    :param steps: Ordered TAP state changes or IR/DR shifts with a bit count and hex TDI.
    :param scope: Chain scope for Vivado or device scope for Quartus.
    :param options: Per-operation JTAG settings.
    """
    vectors = []
    for step in steps:
        if set(step) == {"state"} and step["state"] in {"RESET", "IDLE", "IRPAUSE", "DRPAUSE"}:
            vectors.append(str(step["state"]))
            continue
        if set(step) != {"register", "bits", "tdi"} or step["register"] not in {"IR", "DR"}:
            raise ValueError("A scan step must specify a TAP state or register, bits and TDI")
        bits, tdi = step["bits"], step["tdi"]
        if (
            type(bits) is not int
            or bits <= 0
            or not isinstance(tdi, str)
            or not re.fullmatch(r"(?:0[xX])?[0-9a-fA-F]+", tdi)
        ):
            raise ValueError("Supply a positive bit count and a hex TDI string")
        value = int(tdi, 16)
        if value.bit_length() > bits:
            raise ValueError("TDI exceeds the bit count")
        vectors.append(f"{step['register']} {bits} {value:X}")
    return _dispatch(jtag_id, key, "scan", options, steps=vectors, scope=scope) | {"scope": scope}


@command
def program_device(
    *, jtag_id: int, image: str | Path, key: str,
    while_tethered: Callable[[], None] | None = None, **options: Any,
) -> dict[str, Any]:
    """Program FPGA SRAM, optionally running a callback during Quartus evaluation.

    :param jtag_id: Configured JTAG bench ID.
    :param key: Evidence key for this operation.
    :param image: Path to a prebuilt bitstream or PDI for the selected device.
    :param while_tethered: Bounded callback to run while a time-limited Quartus image is active.
    :param options: Per-operation JTAG settings.
    """
    if while_tethered is not None and not callable(while_tethered):
        raise TypeError("while_tethered must be a callback")
    return _dispatch(jtag_id, key, "program_device", options, image=_file(image, (".bit", ".pdi", ".sof")),
                     while_tethered=while_tethered)


@measurement
def list_cfgmem_parts(*, jtag_id: int, key: str, **options: Any) -> dict[str, Any]:
    """Enumerate flash parts from the backend or the bench configuration.

    :param jtag_id: Configured JTAG bench ID.
    :param key: Evidence key for this operation.
    :param options: Per-operation JTAG settings.
    """
    return _dispatch(jtag_id, key, "list_cfgmem_parts", options)


def _flash(
    jtag_id: int,
    operation: str,
    key: str,
    image: str | Path,
    flash_part: str,
    fsbl: str | Path | None,
    initialization_pdi: str | Path | None,
    options: dict[str, Any],
) -> dict[str, Any]:
    if not flash_part.strip():
        raise ValueError("Supply an exact flash part")
    return _dispatch(
        jtag_id,
        key,
        operation,
        options,
        image=_file(image, (".mcs", ".bin", ".pdi", ".jic")),
        flash_part=flash_part,
        fsbl=_file(fsbl, (".elf",)) if fsbl is not None else None,
        initialization_pdi=_file(initialization_pdi, (".pdi",)) if initialization_pdi is not None else None,
    )


@command
def program_cfgmem(
    *,
    jtag_id: int,
    image: str | Path,
    flash_part: str,
    key: str,
    fsbl: str | Path | None = None,
    initialization_pdi: str | Path | None = None,
    **options: Any,
) -> dict[str, Any]:
    """Program and verify a prebuilt configuration-memory image.

    :param jtag_id: Configured JTAG bench ID.
    :param key: Evidence key for this operation.
    :param image: Path to a prebuilt configuration-memory image.
    :param flash_part: Exact configuration-memory part selector.
    :param fsbl: Optional Zynq first-stage bootloader ELF.
    :param initialization_pdi: Versal initialization PDI required for supported flash workflows.
    :param options: Per-operation JTAG settings.
    """
    return _flash(jtag_id, "program_cfgmem", key, image, flash_part, fsbl, initialization_pdi, options)


@command
def verify_cfgmem(
    *,
    jtag_id: int,
    image: str | Path,
    flash_part: str,
    key: str,
    fsbl: str | Path | None = None,
    initialization_pdi: str | Path | None = None,
    **options: Any,
) -> dict[str, Any]:
    """Compare flash to the image without requesting flash erase or write.

    :param jtag_id: Configured JTAG bench ID.
    :param key: Evidence key for this operation.
    :param image: Path to a prebuilt configuration-memory image.
    :param flash_part: Exact configuration-memory part selector.
    :param fsbl: Optional Zynq first-stage bootloader ELF.
    :param initialization_pdi: Versal initialization PDI required for supported flash workflows.
    :param options: Per-operation JTAG settings.
    """
    return _flash(jtag_id, "verify_cfgmem", key, image, flash_part, fsbl, initialization_pdi, options)


@command
def boot_from_cfgmem(
    *,
    jtag_id: int,
    key: str,
    reset: Callable[[], None] | None = None,
    check_boot: Callable[[], bool] | None = None,
    boot_timeout_s: float = 30,
    **options: Any,
) -> dict[str, Any] | CommandResult:
    """Soft-boot an FPGA, or reset a SoC through bounded board callbacks.

    :param jtag_id: Configured JTAG bench ID.
    :param key: Evidence key for this operation.
    :param reset: Optional board reset callback used with check_boot.
    :param check_boot: Callback returning whether the expected image has booted.
    :param boot_timeout_s: Time in seconds allowed for boot confirmation.
    :param options: Per-operation JTAG settings.
    """
    if not 0 < boot_timeout_s < float("inf"):
        raise ValueError("boot_timeout_s must be finite and positive")
    if reset is None:
        if check_boot is not None:
            raise ValueError("Supply both board callbacks or use native FPGA boot")
        result = _dispatch(jtag_id, key, "boot", options, boot_ms=max(1, int(boot_timeout_s * 1000)))
        if not result["configured"]:
            return CommandResult(status="FAIL", message=f"Configuration did not complete for {result.get('device')}")
        return result
    if check_boot is None:
        raise ValueError("Board reset requires a check of the expected boot image")
    result = _dispatch(jtag_id, key, "boot_probe", options)
    deadline = time.monotonic() + boot_timeout_s
    reset()
    while time.monotonic() < deadline:
        observed = check_boot()
        if type(observed) is not bool:
            raise ValueError("check_boot must return a bool")
        if observed and time.monotonic() < deadline:
            return result | {"boot_method": "board_reset", "configured": True}
        time.sleep(min(0.25, max(0, deadline - time.monotonic())))
    return CommandResult(status="FAIL", message=f"Expected boot evidence absent for {result.get('device')}")


@command
def run_tcl(
    *,
    jtag_id: int,
    key: str,
    script: str | Path | None = None,
    tcl: str | None = None,
    args: Sequence[str] = (),
    **options: Any,
) -> dict[str, Any]:
    """Execute one trusted local Tcl file or inline script on the selected target.

    :param jtag_id: Configured JTAG bench ID.
    :param key: Evidence key for this operation.
    :param script: Local Tcl script path. Supply either script or tcl.
    :param tcl: Inline Tcl source.
    :param args: Arguments exposed to the Tcl script as argv.
    :param options: Per-operation JTAG settings.
    """
    if (script is None) == (tcl is None):
        raise ValueError("Supply exactly one of script or tcl")
    if isinstance(args, str) or not all(isinstance(arg, str) for arg in args):
        raise ValueError("args must be a sequence of strings")
    return _dispatch(
        jtag_id,
        key,
        "run_tcl",
        options,
        script=_file(script, (".tcl",)) if script is not None else None,
        tcl=tcl,
        args=list(args),
    )
