"""GNSS vendor identity probes (not ``*IDN?``)."""

from __future__ import annotations

import time

from colosseum.logging import get_logger

from colosseum_equipment.instruments.gnss.ubx import (
    CLS_MON,
    ID_MON_VER,
    UbxStreamParser,
    mon_ver_poll,
    parse_mon_ver_series,
)

_logger = get_logger("colosseum.equipment")


def _read_chunk(transport: object, size: int = 512) -> bytes:
    in_waiting = getattr(transport, "in_waiting", None)
    if callable(in_waiting):
        try:
            waiting = int(in_waiting())
        except Exception:
            waiting = -1
        if waiting == 0:
            return b""
        if waiting > 0:
            size = min(size, waiting)
    read_bytes = getattr(transport, "read_bytes", None)
    if callable(read_bytes):
        return bytes(read_bytes(size))
    read_raw = getattr(transport, "read_raw", None)
    if callable(read_raw):
        return bytes(read_raw(size))
    return b""


def _write_chunk(transport: object, payload: bytes) -> None:
    write_bytes = getattr(transport, "write_bytes", None)
    if callable(write_bytes):
        write_bytes(payload)
        return
    write_raw = getattr(transport, "write_raw", None)
    if callable(write_raw):
        write_raw(payload)
        return
    write = getattr(transport, "write", None)
    if callable(write):
        write(payload.decode("latin-1"))


def _collect_for(transport: object, timeout_s: float) -> bytes:
    deadline = time.monotonic() + timeout_s
    buf = bytearray()
    while time.monotonic() < deadline:
        chunk = _read_chunk(transport)
        if chunk:
            buf.extend(chunk)
            if len(buf) >= 64:
                break
        else:
            time.sleep(0.01)
    return bytes(buf)


def probe_ublox(transport: object, *, timeout_s: float = 0.45) -> str | None:
    """Poll UBX MON-VER; return ``ublox`` or a refined ``ublox-*`` series slug."""
    flush = getattr(transport, "flush", None)
    if callable(flush):
        try:
            flush()
        except Exception:
            pass
    _write_chunk(transport, mon_ver_poll())
    parser = UbxStreamParser()
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        chunk = _read_chunk(transport)
        if not chunk:
            time.sleep(0.01)
            continue
        for kind, payload in parser.feed(chunk):
            if kind != "ubx" or not isinstance(payload, tuple) or len(payload) != 3:
                continue
            msg_class, msg_id, body = payload
            if msg_class != CLS_MON or msg_id != ID_MON_VER or not isinstance(body, bytes):
                continue
            series = parse_mon_ver_series(body)
            return f"ublox-{series}" if series else "ublox"
    return None


def probe_novatel(transport: object, *, timeout_s: float = 0.3) -> str | None:
    """Send a one-shot VERSIONA request and look for a NovAtel ASCII reply."""
    _write_chunk(transport, b"log versiona once\r\n")
    data = _collect_for(transport, timeout_s)
    text = data.decode("ascii", errors="replace").upper()
    if "VERSIONA" in text or "#VERSION" in text or "NOVATEL" in text:
        return "novatel"
    # OEM7 binary sync can also appear on a busy port
    if b"\xaa\x44\x12" in data or b"\xaa\x44\x13" in data:
        return "novatel"
    return None


def probe_septentrio(transport: object, *, timeout_s: float = 0.3) -> str | None:
    """Ask for receiver info and look for Septentrio ASCII / SBF signatures."""
    _write_chunk(transport, b"exeGetReceiverCapabilities\n")
    data = _collect_for(transport, timeout_s)
    text = data.decode("ascii", errors="replace").upper()
    if "SEPTENTRIO" in text or "ASTERX" in text or "MOSAIC" in text:
        return "septentrio"
    if b"$@$" in data or data.startswith(b"$@") or b"\x24\x40" in data[:8]:
        return "septentrio"
    return None


def probe_gnss_model(transport: object, *, timeout_s: float | None = None) -> str | None:
    """Identify a GNSS vendor/family on an already-open transport.

    Returns a registered model slug or ``None`` when no probe hits.
    """
    ublox_t = 0.45 if timeout_s is None else timeout_s
    other_t = 0.3 if timeout_s is None else max(0.05, timeout_s * 0.65)
    for probe, seconds in (
        (probe_ublox, ublox_t),
        (probe_novatel, other_t),
        (probe_septentrio, other_t),
    ):
        try:
            hit = probe(transport, timeout_s=seconds)
        except Exception as exc:
            _logger.debug("gnss probe %s failed: %s", probe.__name__, exc)
            continue
        if hit:
            return hit
    return None
