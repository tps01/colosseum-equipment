# Colosseum Equipment

## Documentation

API reference (GitHub Pages): <https://tps01.github.io/colosseum-equipment/>

Framework hub: <https://tps01.github.io/colosseum-core/>

First-party Colosseum plugin providing `col.equipment.*` and `col.io.*`
(instruments, transports, DIO, I2C, SPI). NI USB-6501 and USB-845x adapters
load the installed NI-DAQmx / NI-845x runtimes via ctypes.

Version 0.6.0 adds USB2ANY and Aardvark I2C/SPI masters, Cheetah SPI, and
Beagle I2C/SPI, USB 12, and USB 480 capture through `col.io.analyzer`.
Vendor runtimes are installed separately and are not distributed in the wheel.
See the [adapter guide](docs/sphinx/source/guides/io_digital.rst) for setup,
capture limits, and hardware qualification requirements.

## Install

Download the wheel from [GitHub Releases](https://github.com/tps01/colosseum-equipment/releases)
and install it in the same environment as core. Replace `<version>` with
the downloaded filename. For development, use `python -m pip install -e .`.

```bash
python -m pip install "./colosseum_equipment-<version>-py3-none-any.whl"
```

This requires `colosseum-core` `>=0.17.1,<0.18` (threaded evidence queue and
portable artifact paths) and registers the `equipment` and `io`
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

## Trace / waveform masks

Author masks offline with `col.equipment.tools.create_mask`. In procedures use
`speca` / `oscope` `apply_mask_setup` and `verify_mask`. See
[mask workflow guide](https://tps01.github.io/colosseum-equipment/guides/masks.html).

## Serial ports: raw I/O vs SCPI

Each `[equipment.serial]` row is a COM/TTY port. Use `col.equipment.serial` for raw
read/write (DUT console, debug UART, USB-serial). Use
`col.equipment.scpi.query(serial_id=..., command="*IDN?")` for SCPI dialog on
the same port config. Two ports use two `[[equipment.serial]]` tables.

```python
col.equipment.serial.write(serial_id=1, data="AT", append_newline="\r\n")
col.equipment.serial.read_until(serial_id=1, terminator="OK", key="boot")
col.shared.regex.verify_match(key="boot", pattern=r"OK")
col.equipment.scpi.query(serial_id=2, command="*IDN?")
```

## Expected artifacts

Normal CLI runs write `summary.json`, `summary.txt`, `execution.sqlite`, and
`debug.log` under the run output directory. Reports are opt-in: add
`--report wats` to the run command to write `wats_<datetime>_<script>.json`,
or `--report junit` for `junit.xml`. Loading `metadata.yaml` enriches an
enabled report; it does not enable reporting. See the
[core reporting guide](https://tps01.github.io/colosseum-core/guides/output_artifacts.html).

## Develop

```bash
pip install -e ../colosseum-core
pip install -e .
pytest
ruff check colosseum_equipment
mypy
```

### External events after arming (0.5.0+)

Use `col.equipment.oscope.arm_single(oscope_id=...)` when the procedure must
create a load step or other event after the scope is armed. It returns without
waiting for that event. Generate the event, then call
`wait_complete(oscope_id=..., timeout_s=...)` before fetching. `acquire` remains
the blocking arm-and-wait operation for an already running/repetitive stimulus.
Generic SCPI arming is best effort; qualify the command dialect and trigger
readiness on the configured model. Tek MDO4000 has an explicit implementation.

Power sensors also expose `pwrmeter.acquire(pwrmeter_id=..., channel=...)` in
0.5.0 to complete a new acquisition before fetch-style peak/average statistics.
Use a qualified sensor mode/trigger/gate and transport timeout. U2000-series
average-only sensors explicitly refuse envelope-peak reads; a generic peak query
is not evidence of hardware capability.
