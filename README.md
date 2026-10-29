# Colosseum Equipment

## Documentation

API reference (GitHub Pages): <https://tps01.github.io/colosseum-equipment/>

Framework hub: <https://tps01.github.io/colosseum-core/>

First-party Colosseum plugin providing `col.equipment.*` and `col.io.*`
(instruments, transports, DIO, I2C, SPI). NI USB-6501 and USB-845x adapters
load the installed NI-DAQmx / NI-845x runtimes via ctypes.

Instrument resources open through pyVISA, including COM ports normalized to
ASRL. When `model` is omitted, identity queries select a matching driver or the
generic driver for the equipment kind. See the
[transport and driver guide](https://tps01.github.io/colosseum-equipment/guides/transports_support.html)
for fallback behavior and qualification status. Vendor adapter runtimes are
installed separately; see the [adapter guide](https://tps01.github.io/colosseum-equipment/guides/io_digital.html).

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

## Inventory coverage

Model registrations describe implemented command subsets. They do not prove
hardware qualification or support for every function. The
[support matrix](https://tps01.github.io/colosseum-equipment/guides/transports_support.html)
links the model-by-model limits and qualification evidence.

## Trace / waveform masks

Author masks offline with `col.equipment.tools.create_mask`. In procedures use
`speca` / `oscope` `apply_mask_setup` and `verify_mask`. See
[mask workflow guide](https://tps01.github.io/colosseum-equipment/guides/masks.html).

## Serial ports: raw I/O vs SCPI

Each `[equipment.serial]` row is opened with pyVISA. `COM5` and `port = "COM5"`
are the resource `ASRL5::INSTR`; an `ASRL`/`TCPIP`/`GPIB`/`USB` string is used
as written. Use `col.equipment.serial` for raw read/write (DUT console, debug
UART, USB-serial). Use `col.equipment.scpi.query(serial_id=..., command="*IDN?")`
for SCPI dialog on the same port config. Two ports use two `[[equipment.serial]]`
tables. `model` is optional on SCPI instruments: when it is omitted, `*IDN?`
selects a known model for that equipment kind, otherwise the generic driver.

```python
col.equipment.serial.write(serial_id=1, data="AT", append_newline="\r\n")
col.equipment.serial.read_until(serial_id=1, terminator="OK", key="boot")
col.shared.regex.verify_match(key="boot", pattern=r"OK")
col.equipment.scpi.query(serial_id=2, command="*IDN?")
```

## Results

The plugin uses Colosseum's standard run artifacts. See the
[core output guide](https://tps01.github.io/colosseum-core/guides/output_artifacts.html)
for summaries, evidence queries, and opt-in reports.

## Develop

```bash
pip install -e ../colosseum-core
pip install -e .
pytest
ruff check colosseum_equipment
mypy
```


Historical feature notes: [documentation history](https://tps01.github.io/colosseum-equipment/guides/documentation-history.html).
