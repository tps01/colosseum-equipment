"""Quartus Programmer and device-scoped JTAG Tcl jobs."""

from __future__ import annotations

import math
import os
import re
import shutil
import subprocess
import time
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import RLock
from typing import TYPE_CHECKING, Any

from colosseum_equipment.exceptions import (
    EquipmentCapabilityError,
    EquipmentConnectionError,
    EquipmentResponseError,
    EquipmentTimeoutError,
)

from ._process import _launch, _record_log, _stop, _tail, scan_row

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

_LOCK = RLock()
_TCL = Path(__file__).with_name("quartus_jtag.tcl")
_SERVICES = frozenset({"jtagd", "jtagserver", "jtagserver.exe"})
_OPERATIONS = {"program_device": ("p", ".sof"), "program_cfgmem": ("pvi", ".jic"), "verify_cfgmem": ("iv", ".jic")}
_CABLE = re.compile(r"\s*(\d+)\)\s+(.+?)\s*")
_DEVICE = re.compile(r"\s+([0-9a-fA-F]{8})(?:\s+(.*?))?\s*")
_CLOCK = re.compile(r"\s*(\d+(?:\.\d+)?)\s*([kKmM]?)(?:Hz)?\s*", re.IGNORECASE)
_EVALUATION_PROMPT = "Please enter i for info and q to quit"


def _tool(name: str, root: Path) -> Path:
    exe = name + ".exe" if os.name == "nt" else name
    directories = ("", "bin64", "bin", "linux64", "quartus/bin64", "quartus/bin", "quartus/linux64",
                   "qprogrammer/bin64", "qprogrammer/quartus/bin64", "qprogrammer/quartus/bin")
    for directory in directories:
        candidate = root / directory / exe
        if candidate.is_file():
            return candidate
    raise EquipmentCapabilityError(f"{exe} is missing from {root}; select a Quartus installation that supplies it")


def _root(settings: dict[str, Any]) -> Path:
    hint = settings.get("quartus_path") or os.environ.get("QUARTUS_ROOTDIR")
    if hint:
        return Path(hint).expanduser().absolute()
    found = shutil.which("jtagconfig")
    if found:
        root = Path(found).absolute().parent
        return root.parent if root.name in {"bin", "bin64", "linux64"} else root
    raise EquipmentConnectionError("Quartus jtagconfig is unavailable; set quartus_path or QUARTUS_ROOTDIR")


class _Job:
    def __init__(self, root: Path, work: Path, deadline: float) -> None:
        self.root = root
        self.work = work
        self.log = work / "quartus.log"
        self.deadline = deadline

    def call(
        self, name: str, *args: str, private: bool = False, restoring: bool = False, reply: bytes | None = None,
        while_tethered: Callable[[], None] | None = None,
    ) -> str:
        tool = _tool(name, self.root)
        deadline = time.monotonic() + 5 if restoring else self.deadline
        if deadline <= time.monotonic():
            raise EquipmentTimeoutError(f"No time remains to run {name}")
        log = None if private else self.log
        offset = self.log.stat().st_size if not private and self.log.exists() else 0
        proc = _launch(tool, list(args), self.work, log, pipe_stdin=reply is not None)
        tethered = False
        try:
            try:
                if while_tethered is not None:
                    tethered = self._wait_for_tether(proc)
                    if tethered:
                        while_tethered()
            finally:
                payload, _ = proc.communicate(input=reply, timeout=max(0, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            raise EquipmentTimeoutError(f"{name} timed out") from None
        finally:
            _stop(proc, preserve=_SERVICES)
        if private:
            output = payload.decode("utf-8", errors="replace")
        else:
            with self.log.open("rb") as stream:
                stream.seek(offset)
                output = stream.read().decode("utf-8", errors="replace")
        if proc.returncode or re.search(r"(?im)^\s*Error(?:\s+\(\d+\))?:", output):
            detail = f": {_tail(self.log)}" if not private else "; check the Quartus server and credentials"
            error = EquipmentConnectionError if private else EquipmentResponseError
            raise error(f"{name} failed{detail}")
        if while_tethered is not None and not tethered:
            raise EquipmentResponseError("Quartus finished without opening a tethered evaluation")
        return "" if private else output

    def _wait_for_tether(self, proc: subprocess.Popen[bytes]) -> bool:
        while proc.poll() is None:
            remaining = self.deadline - time.monotonic()
            if remaining <= 0:
                raise EquipmentTimeoutError("Quartus did not reach its tethered evaluation prompt in time")
            tail = _tail(self.log)
            if "Configuration succeeded" in tail and _EVALUATION_PROMPT in tail:
                return True
            time.sleep(min(0.1, remaining))
        return False


def _inventory(output: str) -> list[dict[str, Any]]:
    cables: list[dict[str, Any]] = []
    for line in output.splitlines():
        if match := _CABLE.fullmatch(line):
            cables.append({"number": match[1], "target": match[2], "name": match[2], "devices": []})
        elif cables and (match := _DEVICE.fullmatch(line)):
            devices = cables[-1]["devices"]
            index = len(devices)
            description = match[2] or ""
            devices.append({"index": index, "device": f"@{index + 1}", "idcode": match[1].upper(),
                            "part": description.removeprefix("!").strip(), "usable": not description.startswith("!")})
    if not cables and not re.search(r"no (?:jtag )?hardware", output, re.I):
        raise EquipmentResponseError("Could not parse Quartus JTAG inventory")
    return cables


def _choose(rows: list[dict[str, Any]], field: str, selector: str | None) -> dict[str, Any]:
    matches = [row for row in rows if not selector or row[field] == selector]
    if len(matches) != 1:
        raise EquipmentConnectionError(f"Select exactly one Quartus {field}; available: {[row[field] for row in rows]}")
    return matches[0]


def _clock(job: _Job, cable: str, *, restoring: bool = False) -> int:
    output = job.call("jtagconfig", "--getparam", cable, "JtagClock", restoring=restoring)
    for line in reversed(output.splitlines()):
        if match := _CLOCK.fullmatch(line):
            hz = Decimal(match[1]) * {"": 1, "k": 1000, "m": 1_000_000}[match[2].lower()]
            if hz > 0 and hz == int(hz):
                return int(hz)
    raise EquipmentCapabilityError("Quartus cable did not report a readable JtagClock")


def _set_clock(job: _Job, cable: str, hz: int, *, restoring: bool = False) -> int:
    job.call("jtagconfig", "--setparam", cable, "JtagClock", str(hz), restoring=restoring)
    return _clock(job, cable, restoring=restoring)


@contextmanager
def _temporary_clock(job: _Job, target: dict[str, Any], requested: int | None) -> Iterator[dict[str, Any]]:
    if requested is None:
        yield {}
        return
    cable = target["number"]
    previous = _clock(job, cable)
    try:
        applied = _set_clock(job, cable, requested)
        yield {"clock_hz": applied, "requested_clock_hz": requested, "clock_scope": "batch",
               "clock_adjusted": applied != requested}
    finally:
        # Cable numbers can change when a cable is unplugged.
        current = _choose(_inventory(job.call("jtagconfig", "--enum", restoring=True)), "target", target["target"])
        if _set_clock(job, current["number"], previous, restoring=True) != previous:
            raise EquipmentResponseError("Quartus cable clock restoration did not read back the original rate")


def _register(job: _Job, settings: dict[str, Any]) -> dict[str, Any]:
    host = settings.get("jtag_server")
    variable = settings.get("jtag_server_password_env")
    if not isinstance(host, str) or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9.-]*", host):
        raise ValueError("jtag_server must be a DNS name or IPv4 address")
    password = os.environ.get(variable) if isinstance(variable, str) else None
    if not password:
        raise ValueError("Set the environment variable named by jtag_server_password_env")
    job.call("jtagconfig", "--addserver", host, password, private=True)
    return {"jtag_server": host, "registered": True}


def _parts(settings: dict[str, Any]) -> list[str]:
    parts = settings.get("cfgmem_parts", [])
    if not isinstance(parts, list) or not all(isinstance(p, str) and p.strip() for p in parts):
        raise ValueError("cfgmem_parts must be a list of flash part names")
    return list(dict.fromkeys(parts))


def _program(job: _Job, request: dict[str, Any], settings: dict[str, Any], target: str, device: str) -> dict[str, Any]:
    operation = request["operation"]
    flags, extension = _OPERATIONS[operation]
    image = Path(request["image"])
    if image.suffix.lower() != extension:
        raise EquipmentCapabilityError(f"Quartus {operation} requires an {extension} image")
    if request.get("fsbl") or request.get("initialization_pdi"):
        raise EquipmentCapabilityError("Quartus requires a prebuilt JIC with the correct flash loader")
    result: dict[str, Any] = {"image": image.as_posix()}
    flash = operation != "program_device"
    if flash:
        part = request["flash_part"]
        parts = _parts(settings)
        if parts and part not in parts:
            raise ValueError(f"Flash part {part!r} is absent from the bench cfgmem_parts")
        result.update(
            flash_part=part,
            flash_part_source="bench",
            flash_part_verified=False,
            flash_written=operation == "program_cfgmem",
            flash_verified=True,
            temporary_device_configuration=True,
        )
    else:
        result["configured"] = True
    # The programmer's operation grammar uses semicolons and @ as separators.
    staged = job.work / f"image{extension}"
    shutil.copyfile(image, staged)
    # Legacy Quartus waits for 'q' after configuring a time-limited SOF and retries on EOF.
    job.call("quartus_pgm", "-c", target, "-m", "jtag", "-o", f"{flags};{staged.name}{device}",
             reply=None if flash else b"q\n", while_tethered=request.get("while_tethered"))
    return result


def _tcl(job: _Job, request: dict[str, Any], settings: dict[str, Any], target: str, device: str) -> dict[str, Any]:
    steps = request.get("steps", [])
    for step in steps:
        kind, *args = step.split()
        if kind not in {"IDLE", "IR", "DR"}:
            raise EquipmentCapabilityError(f"Quartus device scans do not support TAP state {kind}")
        if kind == "IR" and settings.get("ir_bits") != int(args[0]):
            raise ValueError("Quartus IR scan width must match the bench ir_bits setting")
    fields = {name: request.get(name) for name in ("operation", "script", "tcl", "args", "steps")}
    fields.update(target=target, device=device, lock_ms=max(1, int(min(10, job.deadline - time.monotonic()) * 1000)))
    shutil.copyfile(_TCL, job.work / "driver.tcl")
    with (job.work / "request").open("w", encoding="ascii") as stream:
        for name, value in fields.items():
            if value is not None:
                items = value if isinstance(value, list) else [value]
                for item in items:
                    stream.write(f"{name}\t{str(item).encode().hex()}\n")
    job.call("quartus_stp", "-t", "driver.tcl")
    return _tcl_result(job.work / "result", steps)


def _tcl_result(path: Path, steps: list[str]) -> dict[str, Any]:
    try:
        *rows, complete = path.read_text(encoding="ascii").splitlines()
        if complete != "complete":
            raise ValueError("missing completion record")
        if not steps:
            (value,) = rows
            return {"tcl_result": bytes.fromhex(value).decode()}
        scans = []
        for step, value in zip((s for s in steps if s != "IDLE"), rows, strict=True):
            kind, bits, _ = step.split()
            scans.append(scan_row(kind, int(bits), int(value, 16)))
        return {"scans": scans}
    except (OSError, ValueError) as exc:
        raise EquipmentResponseError("Quartus Tcl returned incomplete or invalid evidence") from exc


def _target_operation(
    job: _Job, settings: dict[str, Any], request: dict[str, Any], cable: dict[str, Any],
) -> dict[str, Any]:
    operation = request["operation"]
    base = {"target": cable["target"]}
    if operation in {"get_clock", "set_clock"}:
        requested = request.get("clock_hz")
        number = cable["number"]
        applied = _set_clock(job, number, request["clock_hz"]) if operation == "set_clock" else _clock(job, number)
        return base | {"clock_scope": "cable", "clock_hz": applied, "requested_clock_hz": requested,
                       "clock_adjusted": requested is not None and applied != requested}
    if operation == "list_devices":
        return base | {"devices": cable["devices"]}
    device = ""
    if operation != "run_tcl" or request.get("device"):
        row = _choose(cable["devices"], "device", request.get("device"))
        if not row["usable"]:
            raise EquipmentCapabilityError(f"Quartus cannot use JTAG device {row['device']}")
        device = row["device"]
        base.update(device=device, part=row["part"], idcode=row["idcode"])
    with _temporary_clock(job, cable, request.get("clock_hz")) as clock:
        if operation in _OPERATIONS:
            result = _program(job, request, settings, cable["target"], device)
        elif operation == "boot_probe":
            result = {}
        else:
            result = _tcl(job, request, settings, cable["target"], device)
        return base | clock | result


def _dispatch(job: _Job, settings: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    operation = request["operation"]
    if operation == "register_server":
        return _register(job, settings)
    if operation == "list_cfgmem_parts":
        parts = _parts(settings)
        if not parts:
            raise EquipmentCapabilityError("Set cfgmem_parts in the Quartus bench configuration")
        return {"parts": parts, "parts_source": "bench"}
    if operation == "boot":
        raise EquipmentCapabilityError("Quartus boot requires board reset and boot evidence callbacks")
    target = request.get("target")
    if settings.get("jtag_server") and operation != "list_targets" and not target:
        raise EquipmentConnectionError("Select the exact Quartus remote cable name returned by list_targets")
    cables = _inventory(job.call("jtagconfig", "--enum"))
    if operation == "list_targets":
        return {"targets": [{"target": c["target"], "name": c["name"]} for c in cables]}
    return _target_operation(job, settings, request, _choose(cables, "target", target))


def run(settings: dict[str, Any], request: dict[str, Any], *, timeout_s: float, key: str) -> dict[str, Any]:
    if not math.isfinite(timeout_s) or timeout_s <= 0:
        raise ValueError("timeout_s must be finite and positive")
    deadline = time.monotonic() + timeout_s
    with _LOCK, TemporaryDirectory(prefix="colosseum-quartus-") as work:
        job = _Job(_root(settings), Path(work), deadline)
        status = "ERROR"
        try:
            result = _dispatch(job, settings, request)
            status = "PASS"
            return {"driver": "quartus", **result}
        finally:
            _record_log(job.log, key, request["operation"], status)
