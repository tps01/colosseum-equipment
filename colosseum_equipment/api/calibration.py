"""Path-loss calibration APIs exposed as ``col.equipment.load_calibration``.

Configured IDs select bench TOML rows. Core records command and measurement
outcomes and applies its standard optional-failure handling. Unsupported model
operations raise ``EquipmentCapabilityError``; transport failures raise
``EquipmentConnectionError``.
Operation-specific validation and acquisition constraints are described below.
"""

from __future__ import annotations

from colosseum.decorators import command
from colosseum.logging import get_logger

from colosseum_equipment import calibration as _cal

_logger = get_logger("colosseum.equipment")


@command
def load_calibration(*, filename: str, key: str) -> None:
    """Load a VNA S21/S12 sweep file into the run database under ``key``.

    Accepts CSV / TXT (a ``frequency_hz,value`` header, or headerless
    ``frequency_hz,loss_db`` with any later columns ignored) and Touchstone
    ``.s2p`` (single-parameter or full 2-port; S21 magnitude is used).
    Later ASG / VSG / SpecA / power-meter calls pass ``calibration=key`` to apply
    nearest-bin path-loss offsets.

    :param filename: Path to a previously captured sweep file.

    :param key: Name used with ``calibration=`` on later equipment calls.

    :raises CalibrationError: File missing, unreadable, or empty.
    """
    _logger.info("Loading calibration %s from %s", key, filename)
    _cal.load_calibration_file(filename=filename, key=key)
