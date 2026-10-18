"""Parameter-driven mask setup, simulated trace capture and verification.

Run from the repository root::

    colosseum run examples/test_mask_sim.py -g examples/configs/config.rf.visa-sim.toml --parameters examples/masks/parameters.toml

Expected: PASS and speca/wifi_trace.csv from canned samples. Mask paths resolve
beside parameters.toml. This is a workflow fixture, not a Wi-Fi compliance test.
"""

from pathlib import Path

import colosseum as col


def main() -> None:
    config = Path(__file__).with_name("configs") / "config.rf.visa-sim.toml"
    col.config.load_config(str(config))
    col.equipment.speca.apply_mask_setup(speca_id=1, key="speca_trace_1")
    # Omit the command key so the mask parameter is not injected into export.
    # The exporter records trace 1 under its default evidence key: speca_trace_1.
    col.equipment.speca.save_trace_data(speca_id=1, path="speca/wifi_trace.csv")
    col.equipment.speca.verify_mask(key="speca_trace_1")


if __name__ == "__main__":
    # The CLI attaches the parameters file before main().
    from colosseum.runner.cli import main as cli_main

    parameters = str(Path(__file__).with_name("masks") / "parameters.toml")
    cli_main(["run", __file__, "--parameters", parameters])
