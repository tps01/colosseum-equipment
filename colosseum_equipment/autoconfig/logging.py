"""Live autoconfig progress logging."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from logging import Logger

    from .discovery import AutoconfigAssignment, AutoconfigResult, AutoconfigSkip
    from .network_filter import BlockedSubnet


class AutoconfigProgress(Protocol):
    def info(self, msg: str, *args: object) -> None: ...
    def warning(self, msg: str, *args: object) -> None: ...


def log_scan_start(logger: AutoconfigProgress | None) -> None:
    if logger is None:
        return
    logger.info("Autoconfig scan starting (VISA INSTR + serial COM)")


def log_probing(logger: AutoconfigProgress | None, target: str, *, baud: int | None = None) -> None:
    if logger is None:
        return
    if baud is None:
        logger.info("Autoconfig probing %s", target)
    else:
        logger.info("Autoconfig probing %s baud=%s", target, baud)


def log_assignment(logger: AutoconfigProgress | None, assignment: AutoconfigAssignment) -> None:
    if logger is None:
        return
    extras: list[str] = []
    if assignment.port:
        extras.append(f"port={assignment.port}")
    if assignment.driver:
        extras.append(f"driver={assignment.driver}")
    if assignment.baudrate is not None:
        extras.append(f"baudrate={assignment.baudrate}")
    suffix = f" {' '.join(extras)}" if extras else ""
    logger.info(
        "Autoconfig assigned %s id=%s resource=%s model=%s idn=%r%s",
        assignment.section,
        assignment.item_id,
        assignment.resource or "(none)",
        assignment.model,
        assignment.idn,
        suffix,
    )


def log_skip(logger: AutoconfigProgress | None, skip: AutoconfigSkip) -> None:
    if logger is None:
        return
    logger.warning(
        "Autoconfig skipped resource=%s reason=%s%s",
        skip.resource,
        skip.reason,
        f" idn={skip.idn!r}" if skip.idn else "",
    )


def log_blacklist(
    logger: AutoconfigProgress | None,
    resource: str,
    subnet: BlockedSubnet,
) -> None:
    if logger is None:
        return
    logger.info(
        "Autoconfig blacklisted resource=%s reason=subnet %s/%s (%s)",
        resource,
        subnet.network.network_address,
        subnet.network.prefixlen,
        subnet.interface,
    )


def log_summary(logger: AutoconfigProgress | None, result: AutoconfigResult) -> None:
    if logger is None:
        return
    for subnet in result.blacklist_subnets:
        logger.info(
            "Autoconfig blacklist: %s -> %s/%s (local %s)",
            subnet.interface,
            subnet.network.network_address,
            subnet.network.prefixlen,
            subnet.address,
        )
    for entry in result.unresolved_blacklist:
        logger.warning("Autoconfig blacklist entry not found: %s", entry)
    logger.info(
        "Autoconfig summary: %d assigned, %d blacklisted, %d skipped (scanned %d VISA)",
        len(result.assignments),
        len(result.blacklisted),
        len(result.skipped),
        result.scanned_count,
    )


def as_progress(logger: Logger | None) -> AutoconfigProgress | None:
    return logger
