from __future__ import annotations

import re
from typing import TYPE_CHECKING

from colosseum.logging import get_logger

from colosseum_equipment.exceptions import EquipmentResponseError

if TYPE_CHECKING:
    from colosseum_equipment.transports.base import Transport

_logger = get_logger("colosseum.equipment")


def parse_float(text: str) -> float:
    match = re.search(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", text)
    if not match:
        raise EquipmentResponseError(f"No numeric value in response: {text!r}")
    return float(match.group(0))


def format_definite_length_block(payload: bytes) -> bytes:
    length = len(payload)
    digits = str(length)
    return f"#{len(digits)}{length}".encode("ascii") + payload


def parse_definite_length_block(data: bytes) -> bytes:
    if not data.startswith(b"#"):
        return data
    if len(data) < 2 or data[1:2] not in b"123456789":
        raise EquipmentResponseError("malformed or indefinite SCPI block header")
    digit_count = int(chr(data[1]))
    digits = data[2 : 2 + digit_count]
    if len(digits) != digit_count or not digits.isdigit():
        raise EquipmentResponseError("truncated or invalid SCPI block length")
    length = int(digits)
    start = 2 + digit_count
    if len(data) < start + length:
        raise EquipmentResponseError(
            f"truncated SCPI block: expected {length} payload bytes, got {len(data) - start}",
        )
    if data[start + length:].strip(b"\r\n"):
        raise EquipmentResponseError("unexpected trailing data after SCPI block")
    return data[start : start + length]


def _raise_empty_binary_block(buffer: bytearray) -> None:
    if len(buffer) >= 2 and buffer[0:1] == b"#" and buffer[1:2] in b"123456789":
        digit_count = int(chr(buffer[1]))
        header_len = 2 + digit_count
        if len(buffer) >= header_len:
            digits = bytes(buffer[2:header_len])
            if digits.isdigit():
                payload_len = int(digits)
                got = max(0, len(buffer) - header_len)
                raise EquipmentResponseError(
                    "truncated SCPI block: expected "
                    f"{payload_len} payload bytes, got {got}",
                )
        raise EquipmentResponseError("truncated or invalid SCPI block length")
    raise EquipmentResponseError("malformed or indefinite SCPI block header")


def _extend_binary_block(buffer: bytearray, read_raw: object) -> None:
    chunk = read_raw()  # type: ignore[operator]
    if not chunk:
        _raise_empty_binary_block(buffer)
    buffer.extend(chunk)


def _binary_block_header_step(buffer: bytearray) -> str:
    """Return ``done`` or ``need_more`` for the definite-length header FSM."""
    if not buffer.startswith(b"#") or (
        len(buffer) >= 2 and buffer[1:2] not in b"123456789"
    ):
        return "done"
    if len(buffer) < 2:
        return "need_more"
    digit_count = int(chr(buffer[1]))
    header_len = 2 + digit_count
    if len(buffer) < header_len:
        return "need_more"
    digits = bytes(buffer[2:header_len])
    if not digits.isdigit():
        return "done"
    total = header_len + int(digits)
    if len(buffer) >= total:
        return "done"
    return "need_more"


class SCPIHelper:
    def __init__(self, transport: Transport) -> None:
        self._transport = transport

    def write(self, command: str) -> None:
        _logger.debug("SCPI write: %s", command)
        self._transport.write(command)

    def query(self, command: str) -> str:
        _logger.debug("SCPI query: %s", command)
        response = self._transport.query(command).strip()
        _logger.debug("SCPI response: %s", response[:200] + ("..." if len(response) > 200 else ""))
        return response

    def query_float(self, command: str) -> float:
        return parse_float(self.query(command))

    def write_binary_block(self, command_prefix: str, payload: bytes) -> None:
        block = format_definite_length_block(payload)
        write_raw = getattr(self._transport, "write_raw", None)
        if not callable(write_raw):
            raise EquipmentResponseError("Transport does not support binary block writes")
        # Raw writes bypass the transport's text terminator. End the SCPI
        # message explicitly so the next query cannot join the binary payload.
        write_raw(f"{command_prefix} ".encode("ascii") + block + b"\n")

    def read_binary_block(self, command: str) -> bytes:
        """Read a definite-length IEEE 488.2 binary block after ``command``.

        Continues calling the transport ``read_raw`` until the header length is
        satisfied so large IQ transfers are not truncated by a single read size.
        An empty ``read_raw`` is treated as EOF/no progress.
        """
        read_raw = getattr(self._transport, "read_raw", None)
        if not callable(read_raw):
            raise EquipmentResponseError("Transport does not support binary block reads")
        self.write(command)
        buffer = bytearray()
        _extend_binary_block(buffer, read_raw)
        while True:
            step = _binary_block_header_step(buffer)
            if step == "done":
                return parse_definite_length_block(bytes(buffer))
            if step == "need_more":
                _extend_binary_block(buffer, read_raw)
                continue
            raise AssertionError(f"unexpected binary-block step {step!r}")

    def status_byte(self) -> int:
        """Read the IEEE 488.2 status byte (``*STB?``)."""
        return int(float(self.query("*STB?")))

    def esr(self) -> int:
        """Read and clear the event status register (``*ESR?``)."""
        return int(float(self.query("*ESR?")))

    def clear_status(self) -> None:
        """Clear status registers (``*CLS``)."""
        self.write("*CLS")

    def drain_error_queue(self, *, max_errors: int = 50) -> list[str]:
        """Drain SCPI system error queue until empty or ``max_errors``.

        Uses ``SYST:ERR?``; stops when code is 0 / "No error".
        """
        errors: list[str] = []
        for _ in range(max(1, max_errors)):
            raw = self.query("SYST:ERR?")
            errors.append(raw)
            code_part = raw.split(",", 1)[0].strip()
            try:
                code = int(float(code_part))
            except ValueError:
                code = -1
            if code == 0:
                break
        return errors


def wait_opc(scpi: SCPIHelper) -> None:
    scpi.query("*OPC?")


def prepare_fast_sweep(scpi: SCPIHelper) -> None:
    scpi.write("DISP:UPD OFF")
