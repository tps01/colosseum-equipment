"""Run from the repository root; uses canned analyzer events, not a bus model."""

import colosseum as col

col.config.load_config("examples/configs/config.analyzer.sim.toml")
col.io.analyzer.start(analyzer_id=1, path="capture/raw.jsonl")
try:
    col.io.i2c.write_read(i2c_id=1, write_data=b"\x00", read_nbytes=2, key="register")
finally:
    col.io.analyzer.stop(analyzer_id=1)
    col.io.analyzer.export(analyzer_id=1, path="capture/raw.jsonl", key="bus_trace")
    col.endex()
