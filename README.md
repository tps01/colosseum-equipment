# Colosseum Equipment

First-party Colosseum plugin providing `col.equipment.*` and `col.io.*`
(instruments, transports, DIO).

## Install

```bash
pip install colosseum-equipment
```

This requires `colosseum-core` 0.16.1+ and registers the `equipment` and `io`
namespaces through the `colosseum.plugins` entry point.

The default installation includes VISA, serial, FTDI, plotting, PyVISA-sim, and
IQ MAT export support.

## Usage

```python
import colosseum as col

col.config.load_config("examples/configs/config.sim.toml")
# Or scan the lab:
# col.equipment.autoconfig()
col.equipment.psu.set_voltage(psu_id=1, voltage=3.3)
col.endex()
```

## Serial ports: raw I/O vs SCPI

Each `[equipment.serial]` row is a COM/TTY port. Use `col.equipment.serial` for raw
read/write (DUT console, debug UART, USB-serial). Use `col.equipment.scpi(...,
serial_id=)` for SCPI dialog on the same port config, like ping vs SCPI-over-TCP on
one network interface.

```python
col.equipment.serial.write(serial_id=1, data="AT", append_newline="\r\n")
col.equipment.serial.read_until(serial_id=1, terminator="OK", key="boot")
col.shared.regex.verify_match(key="boot", pattern=r"OK")
col.equipment.scpi.query(serial_id=2, command="*IDN?")
```

## Expected artifacts

Normal CLI runs write `summary.json`, `summary.txt`, `execution.sqlite`, and
`debug.log` under the run output directory. When metadata is loaded (see
`examples/configs/metadata.yaml`), core also emits a WATS-format
`wats_<datetime>_<script>.json` report alongside those files.

## Develop

```bash
pip install -e ../colosseum-core
pip install -e .
pytest
ruff check colosseum_equipment
mypy
```
