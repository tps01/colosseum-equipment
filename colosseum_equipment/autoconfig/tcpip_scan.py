"""Find reachable standard VISA Ethernet endpoints in an explicit bench subnet."""

from __future__ import annotations

import os
import re
import socket
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from heapq import merge
from ipaddress import IPv4Address
from itertools import groupby, islice
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Sequence
    from ipaddress import IPv4Network

_ENDPOINTS = ((111, "inst0"), (4880, "hislip0"))
_SCAN_WORKERS = 32
_MAX_CONNECT_TIMEOUT_S = 0.2
_ARP_COMPLETE = 0x02
_WINDOWS_MAC = re.compile(r"(?:[0-9a-f]{2}-){5}[0-9a-f]{2}", re.IGNORECASE)


def _cached_ipv4_neighbors() -> set[IPv4Address]:
    """Read resolved IPv4 entries without sending any discovery traffic."""
    try:
        if sys.platform.startswith("linux"):
            rows = Path("/proc/net/arp").read_text(encoding="ascii").splitlines()[1:]
            return {
                IPv4Address(fields[0]) for row in rows
                if len(fields := row.split()) >= 3 and int(fields[2], 16) & _ARP_COMPLETE
            }
        if sys.platform == "win32":
            arp = Path(os.environ.get("SYSTEMROOT", r"C:\Windows")) / "System32" / "arp.exe"
            result = subprocess.run(
                [arp, "-a"], capture_output=True, encoding="ascii", errors="replace", check=True, timeout=3,
            )
            return {
                IPv4Address(fields[0]) for row in result.stdout.splitlines()
                if len(fields := row.split()) >= 2 and _WINDOWS_MAC.fullmatch(fields[1])
            }
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    return set()


def scan_hosts(networks: Sequence[IPv4Network], *, exhaustive: bool) -> Iterator[IPv4Address]:
    if exhaustive:
        ordered = merge(*(network.hosts() for network in networks))
        yield from (host for host, _ in groupby(ordered))
        return

    for host in sorted(_cached_ipv4_neighbors()):
        if host.is_multicast or host.is_loopback or host.is_unspecified or int(host) == 0xFFFFFFFF:
            continue
        if any(
            host in network
            and (network.prefixlen >= 31 or host not in (network.network_address, network.broadcast_address))
            for network in networks
        ):
            yield host


def _reachable(host: str, port: int, timeout: float) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _resources_at(address: IPv4Address, timeout: float) -> list[str]:
    host = str(address)
    return [
        f"TCPIP0::{host}::{endpoint}::INSTR"
        for port, endpoint in _ENDPOINTS
        if _reachable(host, port, timeout)
    ]


def reachable_resources(hosts: Iterable[IPv4Address], timeout: float) -> Iterator[list[str]]:
    """Check a bounded batch at a time, yielding each host's resources in input order."""
    remaining = iter(hosts)
    probe = partial(_resources_at, timeout=min(timeout, _MAX_CONNECT_TIMEOUT_S))
    with ThreadPoolExecutor(max_workers=_SCAN_WORKERS) as executor:
        while batch := list(islice(remaining, _SCAN_WORKERS)):
            yield from executor.map(probe, batch)
