"""I-EQ: serial API on sim transport."""

from __future__ import annotations

import colosseum as col
from colosseum.config import load_config
from tests.support.helpers import run_endex_expect_code


def test_serial_read_until_sim(bench_sim, isolated_cwd) -> None:
    load_config(bench_sim)
    col.equipment.serial.write(serial_id=1, data="AT", append_newline="\r\n")
    banner = col.equipment.serial.read_until(serial_id=1, terminator="OK", key="boot")
    assert "OK" in banner
    run_endex_expect_code(0)


def test_serial_with_shared_regex_verify(bench_sim, isolated_cwd) -> None:
    pytest = __import__("pytest")
    shared = pytest.importorskip("colosseum_shared")
    _ = shared
    import colosseum as col_mod

    load_config(bench_sim)
    col_mod.equipment.serial.write(serial_id=1, data="AT", append_newline="\r\n")
    col_mod.equipment.serial.read_until(serial_id=1, terminator="OK", key="boot")
    result = col_mod.shared.regex.verify_match(key="boot", pattern=r"OK")
    assert result.status == "PASS"
    run_endex_expect_code(0)
