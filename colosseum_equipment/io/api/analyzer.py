"""Passive protocol captures (``col.io.analyzer``)."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from colosseum.decorators import command

from colosseum_equipment._paths import resolve_artifact_path
from colosseum_equipment.evidence import record_artifact
from colosseum_equipment.io.connections import get_backend


@command
def configure(
    *, analyzer_id: int, protocol: str | None = None, mode: int | None = None,
    sample_rate_hz: int | None = None,
) -> None:
    """Configure an idle analyzer. SPI modes use active-low CS and MSB first.

    :param analyzer_id: Configured ``io.analyzer`` id.
    :param protocol: ``i2c``, ``spi``, or ``usb``, subject to model capabilities.
    :param mode: SPI mode 0..3.
    :param sample_rate_hz: I2C/SPI sampling frequency; USB models have a fixed rate.
    """
    get_backend("analyzer", analyzer_id).configure(
        protocol=protocol, mode=mode, sample_rate_hz=sample_rate_hz,
    )


@command
def start(*, analyzer_id: int, path: str | None = None) -> None:
    """Enable capture before returning, then stream packets to JSON Lines.

    :param analyzer_id: Configured ``io.analyzer`` id.
    :param path: New capture file relative to run output. Defaults to a unique name.
    """
    relative = path or f"captures/analyzer_{analyzer_id}_{uuid4().hex}.jsonl"
    get_backend("analyzer", analyzer_id).start(resolve_artifact_path(relative))


@command
def stop(*, analyzer_id: int, timeout_s: float = 2.0) -> dict[str, Any]:
    """Drain until idle or deadline and stop; raise on a capture/SDK failure.

    :param analyzer_id: Configured ``io.analyzer`` id.
    :param timeout_s: Positive drain deadline. SDK reads can add up to 1.1 seconds.
    :returns: Summary including limits, detected loss, and stop-boundary uncertainty.
    """
    return dict(get_backend("analyzer", analyzer_id).stop(timeout_s))


@command
def export(*, analyzer_id: int, path: str, key: str) -> dict[str, Any]:
    """Export a stopped capture and record its summary and artifact in evidence.

    Failed captures can be exported for diagnosis; inspect ``stop_reason`` and
    ``loss_detected`` before accepting the evidence. Packet rows retain vendor
    status bits and device timestamps; this API does not decode USB classes.

    :param analyzer_id: Configured ``io.analyzer`` id.
    :param path: New destination relative to run output (or the original capture).
    :param key: Equipment-domain evidence key.
    :returns: Capture summary.
    """
    artifact = resolve_artifact_path(path)
    summary = dict(get_backend("analyzer", analyzer_id).export(artifact))
    record_artifact(domain="equipment", command="io.analyzer.export", key=key,
                    path=artifact, value=summary,
                    status="FAIL" if summary.get("loss_detected") else "PASS")
    return summary
