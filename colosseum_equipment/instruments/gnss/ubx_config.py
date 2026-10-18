"""u-center GNSS Configuration .txt load/save helpers (legacy CFG + VALGET/VALSET)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from colosseum_equipment.instruments.gnss.ubx import (
    CLS_CFG,
    CLS_MON,
    ID_CFG_VALGET,
    ID_CFG_VALSET,
    ID_MON_VER,
    SET_LAYER_BBR,
    SET_LAYER_RAM,
    build_ubx,
    ucenter_hex_line,
)

_LINE_RE = re.compile(
    r"^\s*([A-Za-z0-9_-]+)\s*-\s*([0-9A-Fa-f][0-9A-Fa-f\s]*)\s*$",
)


@dataclass(frozen=True)
class ParsedUcenterLine:
    name: str
    msg_class: int
    msg_id: int
    payload: bytes
    raw_body: bytes  # class+id+len+payload


@dataclass(frozen=True)
class UcenterFileInfo:
    lines: tuple[ParsedUcenterLine, ...]
    has_valget: bool
    has_legacy_cfg: bool
    mon_ver_hex: str


def parse_ucenter_txt(text: str) -> UcenterFileInfo:
    """Parse a u-center GNSS Configuration ASCII file."""
    lines: list[ParsedUcenterLine] = []
    mon_ver_hex = ""
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = _LINE_RE.match(stripped)
        if not match:
            # First line is often a plain version string without " - "
            if not lines and not mon_ver_hex and " - " not in stripped:
                continue
            continue
        name, hex_part = match.group(1), match.group(2)
        body = bytes.fromhex(hex_part.replace(" ", ""))
        if len(body) < 4:
            continue
        msg_class = body[0]
        msg_id = body[1]
        length = body[2] | (body[3] << 8)
        payload = body[4 : 4 + length]
        if name.upper() in {"MON-VER", "MONVER"} or (
            msg_class == CLS_MON and msg_id == ID_MON_VER
        ):
            mon_ver_hex = body.hex(" ").upper()
            continue
        if msg_class != CLS_CFG:
            continue
        lines.append(
            ParsedUcenterLine(
                name=name.upper(),
                msg_class=msg_class,
                msg_id=msg_id,
                payload=payload,
                raw_body=body[: 4 + length],
            ),
        )
    has_valget = any(line.msg_id == ID_CFG_VALGET for line in lines)
    has_legacy = any(line.msg_id != ID_CFG_VALGET for line in lines)
    return UcenterFileInfo(
        lines=tuple(lines),
        has_valget=has_valget,
        has_legacy_cfg=has_legacy,
        mon_ver_hex=mon_ver_hex,
    )


def valget_payload_to_valset(
    valget_payload: bytes,
    *,
    layers: int = SET_LAYER_RAM | SET_LAYER_BBR,
) -> bytes:
    """Convert a CFG-VALGET response payload into a CFG-VALSET payload."""
    if len(valget_payload) < 4:
        raise ValueError("CFG-VALGET payload too short")
    version = valget_payload[0:1]
    # Skip poll layer + reserved; cfg key/value data starts at offset 4
    cfgdata = valget_payload[4:]
    transaction = b"\x00"
    reserved0 = b"\x00"
    return version + bytes((layers & 0xFF,)) + transaction + reserved0 + cfgdata


def frames_from_ucenter_file(
    info: UcenterFileInfo,
    *,
    layers: int = SET_LAYER_RAM | SET_LAYER_BBR,
) -> list[bytes]:
    """Build framed UBX SET messages from a parsed u-center file."""
    frames: list[bytes] = []
    for line in info.lines:
        if line.msg_id == ID_CFG_VALGET:
            payload = valget_payload_to_valset(line.payload, layers=layers)
            frames.append(build_ubx(CLS_CFG, ID_CFG_VALSET, payload))
        else:
            frames.append(build_ubx(line.msg_class, line.msg_id, line.payload))
    return frames


def frames_from_ubx_binary(data: bytes) -> list[bytes]:
    """Extract complete UBX frames from a binary .ubx dump."""
    frames: list[bytes] = []
    buf = bytearray(data)
    while len(buf) >= 8:
        try:
            start = buf.index(0xB5)
        except ValueError:
            break
        if start > 0:
            del buf[:start]
        if len(buf) < 6 or buf[1] != 0x62:
            del buf[0]
            continue
        length = buf[4] | (buf[5] << 8)
        total = 8 + length
        if len(buf) < total:
            break
        frames.append(bytes(buf[:total]))
        del buf[:total]
    return frames


def detect_mismatch(model: str, info: UcenterFileInfo) -> str | None:
    """Return a warning message if file flavor disagrees with model family."""
    family = model.lower()
    is_m8 = "m8" in family and "m10" not in family
    is_gen9 = any(token in family for token in ("f9", "m10", "f10"))
    if info.has_valget and is_m8:
        return (
            f"config file contains CFG-VALGET (gen 9+) but model `{model}` is M8-family; "
            "load may NAK — regenerate the file in u-center for this generation"
        )
    if info.has_legacy_cfg and not info.has_valget and is_gen9:
        return (
            f"config file looks like legacy CFG-only but model `{model}` is gen 9+; "
            "prefer a CFG-VALGET dump from u-center for this receiver"
        )
    return None


def format_ucenter_txt(
    *,
    mon_ver_line: str | None,
    entries: list[tuple[str, int, int, bytes]],
) -> str:
    """Build u-center .txt content from MON-VER + CFG response entries."""
    out: list[str] = []
    if mon_ver_line:
        out.append(mon_ver_line.rstrip("\n"))
    else:
        out.append("# Colosseum GNSS config export")
    for name, msg_class, msg_id, payload in entries:
        out.append(ucenter_hex_line(name, msg_class, msg_id, payload))
    return "\n".join(out) + "\n"


def load_config_path(path: Path) -> tuple[list[bytes], UcenterFileInfo | None]:
    """Load frames from a u-center .txt or binary .ubx path."""
    suffix = path.suffix.lower()
    data = path.read_bytes()
    if suffix == ".ubx" or (data[:2] == b"\xb5\x62"):
        return frames_from_ubx_binary(data), None
    text = data.decode("utf-8", errors="replace")
    info = parse_ucenter_txt(text)
    return frames_from_ucenter_file(info), info


def cfg_name(msg_class: int, msg_id: int) -> str:
    if msg_class == CLS_CFG and msg_id == ID_CFG_VALGET:
        return "CFG-VALGET"
    if msg_class == CLS_MON and msg_id == ID_MON_VER:
        return "MON-VER"
    # Best-effort labels for legacy dumps
    legacy = {
        0x00: "CFG-PRT",
        0x01: "CFG-MSG",
        0x08: "CFG-RATE",
        0x24: "CFG-NAV5",
        0x3E: "CFG-GNSS",
    }
    if msg_class == CLS_CFG and msg_id in legacy:
        return legacy[msg_id]
    return f"CFG-{msg_class:02X}{msg_id:02X}"
