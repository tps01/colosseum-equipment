# Colosseum Equipment

First-party Colosseum plugin providing `col.equipment.*` and `col.io.*` (instruments, transports, DIO).

## Install

```bash
pip install colosseum-core colosseum-shared
pip install -e ".[hardware,test]"
```

Optional extras: `io` (pyftdi), `plot` (matplotlib), `equipment-sim` (pyvisa-sim).

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
pip install -e ../colosseum-core -e ../colosseum-shared -e ".[test,static,plot]"
pytest
```
