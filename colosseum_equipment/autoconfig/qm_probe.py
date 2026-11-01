"""Fluke handheld QM identity probe for autoconfig (after IDN fails)."""

from __future__ import annotations

import re

from colosseum_equipment.instruments.identify import flush_transport

_QM_189 = re.compile(
    r"^QM,\s*([-+]\d+(?:\.\d*)?(?:[Ee][-+]?\d+)?)\s+(.+)$",
)


def classify_qm_reply(ack: str, data: str) -> str | None:
    """Return ``fluke-189`` / ``fluke-289`` when ``ack``/``data`` match QM framing."""
    if ack.strip() != "0":
        return None
    raw = data.strip()
    if _QM_189.fullmatch(raw):
        return "fluke-189"
    parts = [part.strip() for part in raw.split(",")]
    if len(parts) == 4 and parts[2].upper() == "NORMAL":
        return "fluke-289"
    return None


def query_qm_model(transport: object) -> str | None:
    """Send ``QM\\r`` and classify a Fluke handheld model, or return ``None``."""
    flush_transport(transport)
    write_bytes = getattr(transport, "write_bytes", None)
    read_until = getattr(transport, "read_until", None)
    if not callable(write_bytes) or not callable(read_until):
        return None
    write_bytes(b"QM\r")
    ack = str(read_until(b"\r")).strip()
    data = str(read_until(b"\r"))
    return classify_qm_reply(ack, data)
