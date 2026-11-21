"""Process execution and evidence shared by the JTAG backends."""

from __future__ import annotations

import os
import shutil
import subprocess
from contextlib import nullcontext, suppress
from pathlib import Path
from typing import Any
from uuid import uuid4

import psutil
from colosseum.context import get_context

from colosseum_equipment._paths import resolve_artifact_path
from colosseum_equipment.evidence import record_artifact
from colosseum_equipment.exceptions import EquipmentConnectionError


def _launch(tool: Path, args: list[str], cwd: Path, log: Path | None) -> subprocess.Popen[bytes]:
    env = os.environ.copy()
    command: list[str] | str = [str(tool), *args]
    flags = 0
    if os.name == "nt":
        flags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
        if tool.suffix.lower() in {".bat", ".cmd"}:
            # Only fixed flags, a relative Tcl filename and a numeric listen port reach cmd.
            env["COLOSSEUM_VIVADO_LAUNCHER"] = str(tool)
            cmd = str(Path(os.environ["SYSTEMROOT"]) / "System32" / "cmd.exe")
            command = f'"{cmd}" /d /v:off /s /c ""%COLOSSEUM_VIVADO_LAUNCHER%" {" ".join(args)}"'
    try:
        with (log.open("ab") if log is not None else nullcontext(subprocess.PIPE)) as stream:
            return subprocess.Popen(
                command,
                cwd=cwd,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=stream,
                stderr=subprocess.STDOUT,
                creationflags=flags,
                start_new_session=os.name != "nt",
            )
    except OSError as exc:
        raise EquipmentConnectionError(f"Cannot launch {tool}: {exc}") from exc


def _stop(proc: subprocess.Popen[bytes], *, preserve: frozenset[str] = frozenset()) -> None:
    if proc.poll() is not None:
        return
    try:
        root = psutil.Process(proc.pid)
        children = []
        pending = root.children()
        while pending:
            child = pending.pop()
            with suppress(psutil.NoSuchProcess):
                if child.name().lower() not in preserve:
                    children.append(child)
                    pending.extend(child.children())
    except psutil.NoSuchProcess:
        return
    for child in reversed(children):
        with suppress(psutil.NoSuchProcess):
            child.terminate()
    proc.terminate()
    _, remaining = psutil.wait_procs(children, timeout=2)
    for child in remaining:
        with suppress(psutil.NoSuchProcess):
            child.kill()
    try:
        proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


def _tail(path: Path) -> str:
    with path.open("rb") as stream:
        stream.seek(max(0, stream.seek(0, os.SEEK_END) - 4096))
        return stream.read().decode("utf-8", errors="replace").strip()


def _record_log(log: Path, key: str, operation: str, status: str) -> None:
    if log.is_file() and not get_context().no_artifacts:
        artifact = resolve_artifact_path(f"jtag/{uuid4().hex}.log")
        shutil.copyfile(log, artifact)
        record_artifact(
            domain="equipment",
            command="jtag.log",
            key=key,
            path=artifact,
            value={"operation": operation},
            status=status,
        )


def scan_row(register: str, bits: int, value: int) -> dict[str, Any]:
    if value < 0 or value.bit_length() > bits:
        raise ValueError("TDO exceeds requested bit count")
    return {"register": register, "bits": bits, "tdo": f"{value:0{(bits + 3) // 4}X}"}
