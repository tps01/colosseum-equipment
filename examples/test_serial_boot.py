"""Simulated serial boot banner check using col.shared.regex."""

from __future__ import annotations

import colosseum as col


def main() -> None:
    col.config.load_config("examples/configs/config.sim.toml")
    col.equipment.serial.write(serial_id=1, data="AT", append_newline="\r\n")
    col.equipment.serial.read_until(serial_id=1, terminator="OK", key="boot")
    col.shared.regex.verify_match(key="boot", pattern=r"OK")
    col.endex()


if __name__ == "__main__":
    main()
