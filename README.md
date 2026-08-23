# Colosseum Equipment

First-party Colosseum plugin providing `col.equipment.*` and `col.io.*` (instruments, transports, DIO).

## Install

```bash
pip install colosseum-equipment
```

The default installation includes VISA, serial, FTDI, plotting, PyVISA-sim, and IQ MAT export support.

## Usage

```python
import colosseum as col

col.config.load_config("examples/configs/bench.sim.toml")
# Or scan the lab:
# col.equipment.autoconfig()
col.equipment.psu.set_voltage(psu_id=1, voltage=3.3)
col.endex()
```

## Develop

```bash
pip install -e ../colosseum-core
pip install -e .
pytest
ruff check colosseum_equipment
mypy
```
