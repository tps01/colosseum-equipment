from __future__ import annotations

import ftplib  # nosec B402  # lab VSG waveform upload; config supplies FTP host
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

from colosseum.logging import get_logger

from colosseum_equipment.exceptions import EquipmentResponseError
from colosseum_equipment.instruments.vsg.iq_load import load_iq_interleaved_i16
from colosseum_equipment.protocols.scpi import (
    SCPIHelper,
    format_definite_length_block,
    wait_opc,
)

_logger = get_logger("colosseum.equipment")
_ftp_host_warned = False

if TYPE_CHECKING:
    from colosseum_equipment.transports.base import Transport

_FTP_WAVEFORM_DIR = "/USER/BBG1/WAVEFORM"
_FTP_BLOCK_SIZE = 8192
_METHODS = frozenset({"auto", "ftp", "tcpip"})


def _is_tcpip_resource(resource: str) -> bool:
    return resource.upper().startswith("TCPIP")


def _parse_visa_host(resource: str) -> str | None:
    if not _is_tcpip_resource(resource):
        return None
    parts = resource.split("::")
    if len(parts) >= 2 and parts[1]:
        return parts[1]
    return None


def _resolve_ftp_host(config: dict[str, Any]) -> str:
    global _ftp_host_warned
    if config.get("ftp_host"):
        return str(config["ftp_host"])
    host = _parse_visa_host(str(config.get("resource", "")))
    if host:
        if not _ftp_host_warned:
            _ftp_host_warned = True
            _logger.warning(
                "VSG waveform FTP host parsed from TCPIP resource `%s`; set ftp_host to confirm",
                config.get("resource", ""),
            )
        return host
    raise EquipmentResponseError(
        "FTP waveform upload requires TCPIP resource or equipment.vsg ftp_host in config",
    )


def _iq_sample_count(payload: bytes) -> int:
    if len(payload) < 4 or len(payload) % 4 != 0:
        raise EquipmentResponseError(
            "IQ waveform .bin payload must contain whole 16-bit I/Q sample pairs",
        )
    return len(payload) // 4


def _supports_scpi_binary_upload(transport: Transport) -> bool:
    return callable(getattr(transport, "write_raw", None))


def _normalize_method(method: str) -> str:
    value = method.strip().lower()
    if value not in _METHODS:
        raise EquipmentResponseError(
            f"waveform upload method must be auto, ftp, or tcpip, got {method!r}",
        )
    return value


def _ftp_available(config: dict[str, Any]) -> bool:
    if config.get("ftp_host"):
        return True
    return _parse_visa_host(str(config.get("resource", ""))) is not None


def _select_method(method: str, config: dict[str, Any], transport: Transport) -> str:
    """Call ``method`` wins. Config ``upload_method`` applies only when the call is auto."""
    chosen = _normalize_method(method)
    if chosen == "auto":
        chosen = _normalize_method(str(config.get("upload_method", "auto")))
    if chosen != "auto":
        return chosen
    if _ftp_available(config):
        return "ftp"
    if _supports_scpi_binary_upload(transport):
        return "tcpip"
    return "ftp"


class _UploadProgress:
    """FTP block callback. A terminal gets one updating line; otherwise log each quarter."""

    def __init__(self, total: int, label: str) -> None:
        self._total = max(int(total), 1)
        self._sent = 0
        self._label = label
        self._tty = sys.stderr.isatty()
        self._last_milestone = -1
        self._finished = False

    def __call__(self, block: bytes) -> None:
        self._sent = min(self._total, self._sent + len(block))
        percent = 100.0 * self._sent / self._total
        if self._tty:
            width = 24
            filled = int(width * self._sent / self._total)
            bar = "#" * filled + "." * (width - filled)
            sys.stderr.write(
                f"\r{self._label} [{bar}] {percent:5.1f}% {self._sent}/{self._total}",
            )
            sys.stderr.flush()
            if self._sent >= self._total:
                self.close()
            return
        milestone = min(100, int(percent) // 25 * 25)
        if milestone > self._last_milestone:
            self._last_milestone = milestone
            _logger.info(
                "%s %d%% (%d/%d bytes)",
                self._label,
                milestone,
                self._sent,
                self._total,
            )
            if milestone == 100:
                self._finished = True

    def close(self) -> None:
        if self._finished or not self._tty:
            return
        self._finished = True
        sys.stderr.write("\n")
        sys.stderr.flush()


def _upload_via_scpi(
    scpi: SCPIHelper,
    transport: Transport,
    remote_name: str,
    payload: bytes,
) -> None:
    prefix = f'MMEM:DATA "{remote_name}"'
    message_len = (
        len(f"{prefix} ".encode("ascii"))
        + len(format_definite_length_block(payload))
        + 1
    )
    _logger.info(
        "VSG TCPIP waveform upload starting: %d bytes -> %s",
        len(payload),
        remote_name,
    )
    write_raw = getattr(transport, "write_raw", None)
    if not callable(write_raw):
        raise EquipmentResponseError(
            "TCPIP waveform upload requires a transport with write_raw",
        )
    session = getattr(transport, "large_binary_write", None)
    if callable(session):
        with session(message_len):
            scpi.write_binary_block(prefix, payload)
    else:
        scpi.write_binary_block(prefix, payload)
    _logger.info(
        "VSG TCPIP waveform upload finished: %d bytes -> %s",
        len(payload),
        remote_name,
    )
    wait_opc(scpi)


def _remote_basename(remote_name: str, local_path: Path) -> str:
    if ":" in remote_name:
        return remote_name.rsplit(":", 1)[-1]
    return Path(remote_name).name or local_path.name


def _upload_via_ftp(
    config: dict[str, Any], local_path: Path, remote_name: str, payload: bytes,
) -> None:
    host = _resolve_ftp_host(config)
    user = str(config.get("ftp_user", "anonymous"))
    password = str(config.get("ftp_password", ""))
    remote_basename = _remote_basename(remote_name, local_path)
    remote_path = f"{_FTP_WAVEFORM_DIR}/{remote_basename}"

    progress = _UploadProgress(len(payload), f"FTP {remote_basename}")
    _logger.info(
        "VSG FTP waveform upload starting: %d bytes -> %s",
        len(payload),
        remote_path,
    )
    try:
        with ftplib.FTP(host, timeout=30) as ftp:  # nosec B321  # intentional instrument FTP
            ftp.login(user=user, passwd=password)
            ftp.storbinary(
                f"STOR {remote_path}",
                _BytesIO(payload),
                blocksize=_FTP_BLOCK_SIZE,
                callback=progress,
            )
    finally:
        progress.close()


class _BytesIO:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload
        self._offset = 0

    def read(self, size: int = -1) -> bytes:
        if size < 0:
            chunk = self._payload[self._offset :]
            self._offset = len(self._payload)
            return chunk
        chunk = self._payload[self._offset : self._offset + size]
        self._offset += len(chunk)
        return chunk


def _apply_first_last_blanking(scpi: SCPIHelper, remote_name: str, sample_count: int) -> None:
    waveform_ref = remote_name if ":" in remote_name else f"WFM1:{remote_name}"
    scpi.write(f'RAD:ARB:MARK:CLEAR:ALL "{waveform_ref}",1')
    scpi.write(f'RAD:ARB:MARK:SET "{waveform_ref}",1,1,1,1,0')
    scpi.write(f'RAD:ARB:MARK:SET "{waveform_ref}",1,{sample_count},1,1,0')
    scpi.write("RAD:ARB:MDEStination:PULSe M1")


def upload_waveform_file(
    scpi: SCPIHelper,
    transport: Transport,
    config: dict[str, Any],
    local_path: str,
    remote_name: str,
    *,
    first_last_blanking: bool = False,
    method: str = "auto",
) -> None:
    path = Path(local_path)
    payload = load_iq_interleaved_i16(path)
    selected = _select_method(method, config, transport)

    if selected == "tcpip":
        if not _supports_scpi_binary_upload(transport):
            raise EquipmentResponseError(
                "TCPIP waveform upload requires a transport with write_raw",
            )
        _upload_via_scpi(scpi, transport, remote_name, payload)
    else:
        _upload_via_ftp(config, path, remote_name, payload)

    if first_last_blanking:
        _apply_first_last_blanking(scpi, remote_name, _iq_sample_count(payload))
