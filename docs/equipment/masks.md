# Trace / waveform masks

Shared **bounding-box** masks for SpecA (frequency vs dBm) and oscilloscope
(time vs volts) workflows. Eye-diagram polygons and live instrument DPX overlays
are out of scope for v1.

## Roles

| When | API |
| --- | --- |
| Ahead of time (authoring) | `col.equipment.tools.create_mask` / `load_mask` / `save_mask` |
| In a procedure | `col.equipment.speca.apply_mask_setup` + `verify_mask` |
| In a procedure | `col.equipment.oscope.apply_mask_setup` + `verify_mask` |

Creating a mask is not part of a standard test procedure — edit offline, then
reference the JSON from `parameters.toml`.

## Procedure flow

1. Reference an existing mask from `parameters.toml` (`mask = "…"`)
2. `apply_mask_setup` so the instrument matches the mask `setup`
3. Acquire and export CSV using the evidence-key convention described below
4. `verify_mask(key=…)` against the saved CSV

```python
import colosseum as col

# Offline (once): col.equipment.tools.create_mask(domain="frequency", path="masks/wifi_spurious.json")

col.equipment.speca.apply_mask_setup(speca_id=1, key="speca_trace_1")  # mask= from parameters
# The E4407B exporter performs a single sweep internally.
col.equipment.speca.save_trace_data(
    speca_id=1,
    path="speca/wifi_trace.csv",
)
col.equipment.speca.verify_mask(key="speca_trace_1")  # mask= from parameters.toml
```

For an oscilloscope use an inline time-domain mask and an explicit capture key.
This variant assumes **no loaded parameters file** (or an empty `[pulse_trace]`
table if a parameters file is needed elsewhere):

```python
mask_path = "/bench/masks/pulse.json"  # existing time-domain mask
col.equipment.oscope.apply_mask_setup(oscope_id=1, mask=mask_path)
col.equipment.oscope.acquire(oscope_id=1, timeout_s=10.0)
col.equipment.oscope.save_waveform(oscope_id=1, channel=1, path="scope/pulse.csv", key="pulse_trace")
col.equipment.oscope.verify_mask(key="pulse_trace", mask=mask_path)
```

## Parameters example

```toml
[speca_trace_1]
mask = "masks/wifi_spurious.json"
```

Setup and verification resolve a relative mask path in this order: the process
CWD, the directory containing the loaded parameters file, then the active run
output directory. The first existing file wins. Absolute paths are used as-is.

When a parameters file is loaded, a keyed command receives that table's kwargs.
Do **not** pass the mask verification key to `save_trace_data`: it would receive
an unsupported `mask=` kwarg. Leaving the export command's key unset uses its
existing measurement key `speca_trace_1` for trace 1. Setup and verification can
then share that key's mask parameters. For a custom export key, use an inline
mask argument and avoid a mask-bearing parameters table on the export command.

Run the complete offline example from the repository root:

```bash
colosseum run examples/test_mask_sim.py -g examples/configs/config.rf.visa-sim.toml --parameters examples/masks/parameters.toml
```

The supplied parameters file names `wifi_spurious.json` beside itself. Expected:
PASS and `speca/wifi_trace.csv` from the PyVISA-sim analyzer. This validates the
workflow with canned samples; it is not a Wi-Fi compliance fixture. File capture
requires artifacts enabled.

## Mask JSON (`version: 1`)

| Field | Meaning |
| --- | --- |
| `domain` | `frequency` or `time` |
| `x_unit` / `y_unit` | Defaults `Hz`/`dBm` or `s`/`V` |
| `setup` | Instrument hint fields (see below) |
| `regions[]` | Axis-aligned boxes with a `kind` |

Region `kind` values:

- `keep_below` — in `[x0,x1]`, require `y <= y1` (`y0` is display floor)
- `keep_above` — require `y >= y0`
- `keep_inside` — require `y0 <= y <= y1`
- `keep_outside` — require `y < y0` or `y > y1`

Frequency `setup` keys: `center_hz`, `span_hz`, `ref_level_dbm`, `rbw_hz`, `vbw_hz`.

Time `setup` keys: `timebase_s`, `scale_v`, `offset_v`.

Unsupported setup keys are ignored with a warning when applying.

## Built-in templates

Standards-inspired **starting points** (not certified compliance kits). Retune
`setup` and region edges for your DUT.

| id | domain | Intent |
| --- | --- | --- |
| `freq_spur_floor` | frequency | Spur ceiling bands beside a carrier notch |
| `freq_harmonic_comb` | frequency | Keep-below boxes at harmonic offsets |
| `time_pulse_envelope` | time | Keep-inside amplitude corridor over a pulse |
| `freq_channel_mask` | frequency | Passband + adjacent-channel keep-below |

```python
col.equipment.tools.list_mask_templates()
col.equipment.tools.create_mask(domain="frequency", template="freq_spur_floor")
```

Cancel in the editor raises `RuntimeError("mask editor cancelled")`.
