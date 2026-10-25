"""Path-loss calibration APIs exposed as ``col.equipment.load_calibration``."""

from __future__ import annotations

from colosseum.decorators import command

from colosseum_equipment import calibration as _cal


@command
def load_calibration(*, filename: str, key: str) -> None:
    """Load a VNA S21/S12 sweep file into the run database under ``key``.

    Accepts CSV / TXT (a ``frequency_hz,value`` header, or headerless
    ``frequency_hz,loss_db`` with any later columns ignored) and Touchstone
    ``.s2p`` (single-parameter or full 2-port; S21 magnitude is used).
    Later ASG / VSG / SpecA / power-meter calls pass ``calibration=key`` to apply
    nearest-bin path-loss offsets.

    :param filename: Path to a previously captured sweep file.
    :type filename: str
    :param key: Name used with ``calibration=`` on later equipment calls.
    :type key: str

    :returns: None

    :raises CalibrationError: File missing, unreadable, or empty.
    """
    _cal.load_calibration_file(filename=filename, key=key)
