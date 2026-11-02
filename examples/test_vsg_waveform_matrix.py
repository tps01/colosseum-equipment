"""Parameter-driven IQ waveform matrix across two VSGs.

Each waveform lists center frequencies per ``vsg_id``. The script uploads once
per (waveform, VSG), plays, then retunes for each center. Case matrix and
verify limits come from ``examples/vsg_waveform_matrix/parameters.toml`` via
``col.load_parameter`` and ``key=`` injection. Swap that file for other packs.

Config defaults to two Rohde SMBV100B VSGs and a Keysight E4407B SpecA; edit
resources in the TOML for the bench. Waveform paths in parameters are relative
to ``examples/``.

Run from the repository root::

    colosseum run examples/test_vsg_waveform_matrix.py \\
      -g examples/configs/config.vsg_waveform_matrix.toml \\
      --parameters examples/vsg_waveform_matrix/parameters.toml
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import colosseum as col

_EXAMPLES = Path(__file__).resolve().parent
_CONFIG = _EXAMPLES / "configs" / "config.vsg_waveform_matrix.toml"
_PARAMETERS = _EXAMPLES / "vsg_waveform_matrix" / "parameters.toml"
_SPECA_ID = 1


def evidence_key(*, case_name: str, vsg_id: int, freq_hz: float) -> str:
    """Stable key shared by measure/verify and parameters.toml limit tables."""
    return f"{case_name}_vsg{vsg_id}_{int(freq_hz)}"


def load_cases() -> list[dict[str, Any]]:
    names = col.load_parameter(key="cases", field="names")
    cases: list[dict[str, Any]] = []
    for name in names:
        by_vsg_raw = col.load_parameter(key=name, field="by_vsg")
        cases.append(
            {
                "name": name,
                "local": _EXAMPLES / str(col.load_parameter(key=name, field="local")),
                "remote": str(col.load_parameter(key=name, field="remote")),
                "fs_hz": float(col.load_parameter(key=name, field="fs_hz")),
                "amp_dbm": float(col.load_parameter(key=name, field="amp_dbm")),
                "by_vsg": {
                    int(vsg_id): [float(freq) for freq in freqs]
                    for vsg_id, freqs in by_vsg_raw.items()
                },
            }
        )
    return cases


def upload_case(case: dict[str, Any]) -> None:
    local = case["local"]
    if not local.is_file():
        raise FileNotFoundError(f"waveform missing for {case['name']}: {local}")
    for vsg_id in case["by_vsg"]:
        col.equipment.vsg.upload_waveform(
            vsg_id=vsg_id,
            local_path=str(local),
            remote_name=case["remote"],
        )


def verify_point(*, case_name: str, vsg_id: int, freq_hz: float) -> None:
    """SA marker check; replace body as needed, keep key= stable."""
    key = evidence_key(case_name=case_name, vsg_id=vsg_id, freq_hz=freq_hz)
    col.equipment.speca.set_center_frequency(speca_id=_SPECA_ID, frequency=freq_hz)
    col.equipment.speca.single_sweep(speca_id=_SPECA_ID)
    col.equipment.speca.set_marker_frequency(
        speca_id=_SPECA_ID,
        marker=1,
        frequency_hz=freq_hz,
    )
    col.equipment.speca.measure_marker_power(speca_id=_SPECA_ID, marker=1, key=key)
    col.equipment.speca.verify_marker_power(key=key)


def run_case(case: dict[str, Any]) -> None:
    for vsg_id, freqs_hz in case["by_vsg"].items():
        col.equipment.vsg.play_iq(
            vsg_id=vsg_id,
            filename=case["remote"],
            center_freq_hz=freqs_hz[0],
            amplitude_dbm=case["amp_dbm"],
            sample_clock_hz=case["fs_hz"],
        )
        col.equipment.vsg.set_output(vsg_id=vsg_id, enabled=True)
        try:
            for freq_hz in freqs_hz:
                col.equipment.vsg.set_frequency(vsg_id=vsg_id, frequency=freq_hz)
                verify_point(case_name=case["name"], vsg_id=vsg_id, freq_hz=freq_hz)
        finally:
            col.equipment.vsg.set_output(vsg_id=vsg_id, enabled=False)


def main() -> None:
    col.config.load_config(str(_CONFIG))
    for case in load_cases():
        upload_case(case)
        run_case(case)


if __name__ == "__main__":
    from colosseum.runner.cli import main as cli_main

    cli_main(
        [
            "run",
            __file__,
            "-g",
            str(_CONFIG),
            "--parameters",
            str(_PARAMETERS),
        ]
    )
