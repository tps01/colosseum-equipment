"""
Example: power-rail acceptance test.

Exercises:
  - col.config.load_config initializes runtime
  - PSU/DMM high-level APIs persist measurements and verifications
  - Optional verification does not gate exit code
  - Raw SCPI escape hatch available alongside decorated APIs

Run:
  set COLOSSEUM_CONFIG=config.sim.toml
  python examples/test_power_rails.py
  colosseum run examples/test_power_rails.py --config examples/configs/config.sim.toml

Expected artifacts (under outputs/<timestamp>_test_power_rails/):
  debug.log, execution.sqlite, summary.txt
"""

from __future__ import annotations

import os
import warnings
from pathlib import Path

import colosseum as col


def _config_filename() -> str:
    if name := os.environ.get("COLOSSEUM_CONFIG"):
        return name
    legacy = os.environ.get("COLOSSEUM_BENCH_CONFIG")
    if legacy:
        warnings.warn(
            "COLOSSEUM_BENCH_CONFIG is deprecated; set COLOSSEUM_CONFIG instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return legacy
    return "config.toml"


_CONFIG = Path(__file__).resolve().parent / "configs" / _config_filename()


def main() -> None:
    if not col.config.is_loaded():
        col.config.load_config(str(_CONFIG))

    # --- Stimulus: configure supply and enable output ---
    col.equipment.psu.set_voltage(psu_id=1, voltage=3.3)
    col.equipment.psu.set_current_limit(psu_id=1, current=1.0)
    col.equipment.psu.set_output(psu_id=1, enabled=True)

    try:
        # --- Measurement + required verification (architecture doc flow) ---
        col.equipment.dmm.measure_voltage(dmm_id=1, channel=1, key="vrail_3v3")
        col.equipment.dmm.verify_voltage(key="vrail_3v3", expected_val=3.3, tolerance=0.1)

        # Reuse the supported single DMM input. The simulated value is still 3.3 V,
        # so this different engineering limit deliberately produces an optional FAIL.
        col.equipment.dmm.measure_voltage(dmm_id=1, channel=1, key="engineering_probe_point")
        # --- Optional engineering check (FAIL/ERROR must not fail the run) ---
        col.equipment.dmm.verify_voltage(key="engineering_probe_point", expected_val=1.8, tolerance=0.1, optional=True)

        # --- Escape hatch: direct SCPI readback for bring-up / debug ---
        readback = col.equipment.scpi.query_float(psu_id=1, command="VOLT?")
        # Implementations may log at DEBUG; high-level APIs remain preferred in tests.

        if readback < 3.0:
            # Illustrative host-side guard; real tests should prefer verify_* APIs.
            raise RuntimeError(f"PSU readback unexpectedly low: {readback}")
    finally:
        col.equipment.psu.set_output(psu_id=1, enabled=False)


if __name__ == "__main__":
    main()
    col.endex()
