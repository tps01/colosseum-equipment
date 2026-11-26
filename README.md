# Colosseum Equipment

## Documentation

- [JTAG setup for Vivado and Quartus](docs/jtag.md)
- [Digilent Analog Discovery 3 setup and loopback](docs/equipment/digilent-ad3.md)

API reference (GitHub Pages): <https://tps01.github.io/colosseum-equipment/>

Framework hub: <https://tps01.github.io/colosseum-core/>

First-party Colosseum plugin providing `col.equipment.*` and `col.io.*`
(instruments, transports, DIO, I2C, SPI). NI USB-6501 and USB-845x adapters
load the installed NI-DAQmx / NI-845x runtimes via ctypes.

Most instrument resources open through pyVISA, including COM ports normalized to
ASRL. Native exceptions include B&K 8500 binary serial, Mini-Circuits RCM/ZTM
HTTP/Telnet/USB HID, and Tektronix USB RSA through `driver="rsa-api"` with the separately
installed vendor runtime. See `examples/configs/config.native-protocols.toml`.
When `model` is omitted, identity queries select a matching driver or the
generic driver for the equipment kind. See the
[transport and driver guide](https://tps01.github.io/colosseum-equipment/guides/transports_support.html)
for fallback behavior and qualification status. Vendor adapter runtimes are
installed separately; see the [adapter guide](https://tps01.github.io/colosseum-equipment/guides/io_digital.html).

## Install

Download the wheel from [GitHub Releases](https://github.com/tps01/colosseum-equipment/releases)
and install it in the same environment as core. Replace `<version>` with
the downloaded filename. For development, use
`python -m pip install -r requirements.txt`.

```bash
python -m pip install "./colosseum_equipment-<version>-py3-none-any.whl"
```

This requires `colosseum-core` `>=0.18,<0.19` (threaded evidence queue and
portable artifact paths) and registers the `equipment` and `io`
namespaces through the `colosseum.plugins` entry point.

The default installation includes VISA, serial, FTDI, plotting, PyVISA-sim, and
IQ MAT export support.

## Migrating to 0.18

TOML operating settings still apply when an instrument is first initialized,
including PSU setpoints/protection and explicitly configured generator outputs.
Setpoints are applied before enabling output. Cached reuse does not reapply
startup settings or undo later commands. An explicit `output = false` now also
turns a configured generator output off; omitting it leaves output state alone.

Measurements and exports now consume existing data. Use explicit configuration,
acquisition and completion commands before reading:

```python
col.equipment.speca.single_sweep(speca_id=1)
col.equipment.speca.save_trace_data(speca_id=1, path="traces/capture.csv")

col.equipment.dmm.set_function(dmm_id=1, function="VOLT:DC")
col.equipment.dmm.initiate(dmm_id=1)
col.equipment.dmm.measure_voltage(dmm_id=1, key="rail")
```

SpecA exports no longer suppress display updates, clear held traces, change
trace/detector modes, or sweep. Closing no longer enables display updates.
This also removes the unsupported E4407B `DISP:UPD` headers (#134, #135).
VNA reads validate the existing parameter/format instead of redefining traces.
Required transfer formats and channel selections are restored after success
or failure; unsupported snapshots require explicit preparation rather than
unsafe setting changes. ENA-style VNA reads require the requested trace selected
beforehand. HP 8563EC is an exception: its native `TDF P; TRA?;` transfer is
supported and leaves trace A in view mode. Export does not clear the trace,
change amplitude units, or start a sweep. Select dBm units before exporting,
using the panel or an explicit `AUNITS DBM;` command.

Power meters expose `configure_average()` separately from `acquire()` and
`measure_power_*()`. Counters expose `set_function()`, `set_statistics()` and
`initiate()`; the 53150A completes a measurement during `initiate(channel=...)`
and its subsequent read returns that captured result. Phase-noise setup uses
`set_spot_offset_hz()` and `set_integration_bounds_hz()` before acquisition.
For Keithley 2001, explicitly select `SYST:FETC:FORM SCPI` before fetching;
FRESH semantics would start a conversion.

GNSS construction and `start_logging()` no longer enable message profiles.
Call `set_message_profile()` or `set_message_rate()` explicitly; the `messages`
argument was removed from `start_logging()`. NovAtel profile changes remove only
previously managed subscriptions, without `UNLOGALL`.

Instrument applications must already be selected before use, using the panel
or explicit raw SCPI commands. Native USB RSA connections no longer preset:
use `configure_spectrum()` and `acquire_spectrum()` before spectrum export.
Declared native IQ bandwidth/record-length settings still apply. T3DSO custom
Vpp slots can be set explicitly with `oscope.configure_vpp()`; reads validate
the reported channel and calculation type without overwriting the slot.

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
links the model-by-model limits and qualification evidence, including Linux
GPIB host setup (`GPIB0::<pad>::INSTR`, not `/dev/gpib0`), USB CDC vs USBTMC vs
`USB::RAW`, and opt-in `gpib_scan` autoconfig.

## Trace / waveform masks

Author masks offline with `tools/mask_editor.py` in colosseum-library. In procedures use
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
pip install -r requirements.txt
pytest
ruff check colosseum_equipment
mypy
```

Historical feature notes: [documentation history](https://tps01.github.io/colosseum-equipment/guides/documentation-history.html).

For bounded SCPI parser fuzzing in Linux CI or Docker Desktop on Windows, see
[the fuzz fixture instructions](tests/fixtures/fuzz/README.md).
