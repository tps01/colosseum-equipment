"""Bounded Vivado jobs and run-owned hardware servers."""

from __future__ import annotations

import base64
import math
import os
import shutil
import socket
import subprocess
import time
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import RLock
from typing import Any

from colosseum.context import get_context

from colosseum_equipment.exceptions import (
    EquipmentCapabilityError,
    EquipmentConnectionError,
    EquipmentResponseError,
    EquipmentTimeoutError,
)

from ._process import _launch, _record_log, _stop, _tail, scan_row

STARTUP_S = 20.0
POLL_S = 0.1
DEFAULT_SERVER = "127.0.0.1:3121"
_DRIVER = Path(__file__).with_name("vivado_jtag.tcl")
_LOCK = RLock()


def _bin(name: str) -> str:
    return name + ".bat" if os.name == "nt" else name


def _find_tool(name: str, hint: str | Path | None) -> Path:
    if hint is None:
        found = shutil.which(_bin(name))
        if found:
            return Path(found).absolute()
        raise EquipmentConnectionError(f"{_bin(name)} was not found. Set {name}_path to its launcher or Vivado root.")
    path = Path(hint).expanduser().absolute()
    candidates = (path / "bin" / _bin(name), path / _bin(name)) if path.is_dir() else (path,)
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise EquipmentConnectionError(f"{name} launcher not found at {path}. Set {name}_path to a valid path.")


@dataclass
class _Server:
    endpoint: str
    proc: subprocess.Popen[bytes]
    scratch: TemporaryDirectory[str]

    def close(self) -> None:
        try:
            _stop(self.proc)
        finally:
            self.scratch.cleanup()


def _listening(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.15):
            return True
    except OSError:
        return False


def _start_server(tool: Path, budget: float) -> _Server:
    with closing(socket.socket()) as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    scratch = TemporaryDirectory(prefix="colosseum-hw-server-")
    path = Path(scratch.name)
    log = path / "server.log"
    proc = None
    ready = False
    try:
        proc = _launch(tool, [f"-stcp:127.0.0.1:{port}", "-p0"], path, log)
        end = time.monotonic() + min(budget, STARTUP_S)
        while time.monotonic() < end:
            if proc.poll() is not None:
                raise EquipmentConnectionError(f"hw_server exited during startup: {_tail(log)}")
            if _listening(port):
                ready = True
                return _Server(f"127.0.0.1:{port}", proc, scratch)
            time.sleep(POLL_S)
        raise EquipmentTimeoutError(f"hw_server did not start on loopback: {_tail(log)}")
    finally:
        if not ready:
            try:
                if proc is not None:
                    _stop(proc)
            finally:
                scratch.cleanup()


def _server(
    settings: dict[str, Any], vivado: Path, timeout: float, *, force_owned: bool = False,
) -> tuple[str, str | None]:
    if settings.get("hw_server_url"):
        return str(settings["hw_server_url"]), None
    cache = get_context().resource_cache
    hint = settings.get("hw_server_path") or vivado.parent
    key = f"equipment:vivado-server:{hint}"
    server = cache.get(key)
    if isinstance(server, _Server):
        if server.proc.poll() is None:
            return server.endpoint, key
        cache.pop(key)
        server.close()
    if not force_owned and _listening(3121):
        return DEFAULT_SERVER, None
    server = _start_server(_find_tool("hw_server", hint), timeout)
    cache[key] = server
    return server.endpoint, key


def _encode(value: object) -> str:
    return base64.b64encode(str(value).encode()).decode("ascii")


_ROWS = {
    "target_row": ("targets", ("target", "name")),
    "device_row": ("devices", ("device", "part", "idcode")),
    "scan_row": ("scans", ("register", "bits", "tdo")),
}
_BATCH_ARGS = ["-mode", "batch", "-source", "driver.tcl", "-nolog", "-nojournal"]
_OUTCOME_FIELDS = ("configured", "flash_written", "flash_verified")


def _result_row(tag: str, fields: list[str], result: dict[str, Any]) -> None:
    collection, columns = _ROWS[tag]
    row: dict[str, Any] = dict(zip(columns, fields, strict=True))
    if tag == "device_row":
        row["index"] = len(result[collection])
    if tag == "scan_row":
        bits = int(row["bits"])
        value = int(row["tdo"], 16)
        row = scan_row(row["register"], bits, value)
    result[collection].append(row)


def _decode_result(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {"targets": [], "devices": [], "parts": [], "scans": []}
    *rows, completion = path.read_text(encoding="ascii").splitlines()
    if completion != "complete":
        raise ValueError("Vivado did not emit a completion record")
    for line in rows:
        tag, *encoded = line.split("\t")
        fields = [base64.b64decode(value, validate=True).decode() for value in encoded]
        if tag == "part_row":
            result["parts"].append(fields[0])
        elif tag in _ROWS:
            _result_row(tag, fields, result)
        else:
            (result[tag],) = fields
    for name in ("clock_hz", "requested_clock_hz"):
        if name in result:
            result[name] = int(result[name]) if result[name] else None
    for name in (*_OUTCOME_FIELDS, "temporary_device_configuration", "clock_adjusted"):
        if name in result:
            result[name] = None if not result[name] else result[name] in ("true", "1")
    return result


def _write_request(work: Path, request: dict[str, Any]) -> None:
    shutil.copyfile(_DRIVER, work / "driver.tcl")
    with (work / "request").open("w", encoding="ascii") as stream:
        for name, value in request.items():
            if value is not None:
                for item in value if isinstance(value, list) else [value]:
                    stream.write(f"{name}\t{_encode(item)}\n")


def _execute(vivado: Path, work: Path, request: dict[str, Any], end: float) -> dict[str, Any]:
    _write_request(work, request)
    if end <= time.monotonic():
        raise EquipmentTimeoutError("No time remains to launch Vivado")
    log = work / "vivado.log"
    proc = _launch(vivado, _BATCH_ARGS, work, log)
    try:
        init_end = min(end, time.monotonic() + 60)
        while proc.poll() is None and not (work / "server-ready").exists():
            if time.monotonic() >= init_end:
                raise EquipmentTimeoutError(f"Vivado hardware-server connection timed out: {_tail(log)}")
            time.sleep(POLL_S)
        proc.wait(timeout=max(0, end - time.monotonic()))
    except subprocess.TimeoutExpired as exc:
        operation = request["operation"]
        try:
            outcome = _decode_result(work / "result")
        except (OSError, ValueError, IndexError):
            raise EquipmentTimeoutError(f"Vivado {operation} timed out: {_tail(log)}") from exc
        if "error" in outcome:
            detail = f"operation failed in {outcome['phase']}: {outcome['error']}"
        else:
            evidence = ", ".join(f"{name}={outcome[name]}" for name in _OUTCOME_FIELDS if name in outcome)
            detail = f"operation completed ({evidence})" if evidence else "operation completed"
        raise EquipmentTimeoutError(f"Vivado {operation} cleanup timed out after {detail}") from exc
    finally:
        _stop(proc)
    try:
        output = _decode_result(work / "result")
    except (OSError, ValueError, IndexError) as exc:
        raise EquipmentResponseError(f"Vivado returned incomplete evidence: {_tail(log)}") from exc
    if proc.returncode != 0 and "error" not in output:
        raise EquipmentResponseError(f"Vivado exited with status {proc.returncode}: {_tail(log)}")
    return output


def _raise_vendor_error(output: dict[str, Any], endpoint: str, owned_key: str | None) -> None:
    detail = output["error"]
    phase = output.get("phase", "vivado")
    if output.get("kind") == "capability":
        raise EquipmentCapabilityError(detail)
    if phase in {"server", "target"}:
        if phase == "server" and owned_key:
            resource = get_context().resource_cache.pop(owned_key, None)
            if isinstance(resource, _Server):
                resource.close()
        raise EquipmentConnectionError(f"Vivado {phase} failure at {endpoint}: {detail}")
    raise EquipmentResponseError(f"Vivado {phase} failure: {detail}")


def _job(vivado: Path, endpoint: str, request: dict[str, Any], end: float, key: str) -> dict[str, Any]:
    with TemporaryDirectory(prefix="colosseum-vivado-") as scratch:
        work = Path(scratch)
        status = "ERROR"
        try:
            output = _execute(vivado, work, dict(request, hw_server_url=endpoint), end)
            status = "ERROR" if "error" in output else "PASS"
            return output
        except EquipmentTimeoutError as exc:
            with (work / "vivado.log").open("a", encoding="utf-8") as stream:
                stream.write(f"\nColosseum: {exc}\n")
            raise
        finally:
            _record_log(work / "vivado.log", key, request["operation"], status)


def run(settings: dict[str, Any], request: dict[str, Any], *, timeout_s: float, key: str) -> dict[str, Any]:
    """Run one batch job. Only the managed hardware server survives between calls."""
    if not math.isfinite(timeout_s) or timeout_s <= 0:
        raise ValueError("timeout_s must be finite and positive")
    end = time.monotonic() + timeout_s
    vivado = _find_tool("vivado", settings.get("vivado_path") or os.environ.get("XILINX_VIVADO"))
    with _LOCK:
        endpoint, owned_key = _server(settings, vivado, max(0.0, end - time.monotonic()))
        output = _job(vivado, endpoint, request, end, key)
        if output.get("phase") == "server" and endpoint == DEFAULT_SERVER and not settings.get("hw_server_url"):
            # A TCP service on the default port was not usable by Vivado.
            endpoint, owned_key = _server(settings, vivado, max(0.0, end - time.monotonic()), force_owned=True)
            output = _job(vivado, endpoint, request, end, key)
        if "error" in output:
            _raise_vendor_error(output, endpoint, owned_key)
        return dict(output, hw_server_url=endpoint, xvc_url=request.get("xvc_url"))
