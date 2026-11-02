# Inventory expansion: implementation and qualification status

This change adds **83 model identities / 85 kind/model registrations** from
`misc_equipment.xlsx` across 12 existing equipment kinds. The first implementation
pass covered 55 identities; subsequent passes added 28. Two Spike devices each
have separate spectrum and IQ interfaces. Version **0.6.0** includes the audit
fixes described in the [manual analysis](inventory-manual-analysis.md).

These are bounded implementations based on command documentation and synthetic
recording-transport tests. The inventory expansion pass itself was not
hardware-qualified; CI does not gate physical qualification. Some lab
validation of pre-existing drivers exists outside this inventory table, but
those exercises are not recorded here as formal hardware-qualified rows.
Registration does not mean every generic API operation is supported. The table
below records the first implementation pass; the manual analysis lists the
additional profiles, source references and remaining category work.

## Implemented subsets

Models below use the vendor prefix shown; for example `keysight-34410a`.
Unsupported public operations raise `EquipmentCapabilityError` before sending
commands. Existing model registrations are retained. Shared ASCII framing and IQ TAR
directory fixes also apply to existing export paths.

| Category | New model slugs | Implemented behavior | Limits / qualification still required |
| --- | --- | --- | --- |
| Bench DMM | `keysight-34410a`, `keysight-34411a`, `keithley-2100`, `keithley-2001` | Function-qualified range/autorange and integration; trigger/initiate/fetch; one-shot DC/AC voltage/current, resistance, four-wire resistance and frequency | Scalar results only. Overload/nonfinite/array results are rejected. 3441x additionally has aperture and input-impedance selection; high input impedance is automatic and range dependent. No scanner or buffered acquisition. 2001 selects SCPI fetch format explicitly. |
| Handheld DMM | `keysight-u1252a`, `keysight-u1272a` | Read primary display with `fetch`; query native `CONF?` descriptor | Optical serial cable required; explicitly configure baud rate. No remote function switching or guarantee of a fresh conversion. Interpret the native display value together with its descriptor; no inferred SI conversion. |
| Power supplies | `keysight-e3644a`, `keysight-n6705a`, `rohde-hmp4040` | Voltage/current settings, output, measurements, basic protection subsets | E3644A range must be selected on panel. N6705A uses explicit module-slot channel lists; installed modules determine limits. HMP4040 always selects an output before commands. Derived power uses separate voltage/current readings. No N6705A digitizer, sequencing or module identification. |
| RF generators (`vsg`) | `keysight-e8257d`, `keysight-e8257c`, `keysight-e8241a`, `keysight-e4422b`, `keysight-n5183a`, `keysight-n5183b`, `rohde-smb100a`, `rohde-sma100b` | CW frequency, dBm level, RF output, reference source and setting readback | Readback reports programmed settings, not independently measured RF. No ARB/vector modulation or option-dependent sweeps. |
| Frequency counter | `keysight-53150a` | One-shot frequency with explicit LF/microwave input routing; reset | Not a universal time-interval counter. Period, duty cycle and generic gate controls are refused. |
| Spectrum analyzers | `keysight-n9000a`, `keysight-n9010a`, `keysight-n9010b`, `keysight-n9020a`, `keysight-n9020b`, `keysight-n9030a`, `keysight-e4440a` | Select SA application, configure sweep and markers, single sweep, dBm trace CSV and host bandwidth calculation | Linear frequency sweeps; zero-span frequency exports are refused. Licensed measurement applications, IQ and screenshots are excluded. Compare trace points, detector, sweep mode and amplitude against the display on each model. |
| VNA | `keysight-e5062a`, `keysight-e5071b`, `keysight-e8362b`, `keysight-n5222b`, `keysight-n5245b`, `keysight-n5247b`, `rohde-znle6` | Channel-aware sweep/averaging, trace configuration, scalar S-parameter peaks, actual-stimulus CSV | ENA bus triggering and paired formatted data are handled separately from PNA. PNA trace numbers must already exist. ZNLE owns `COL_trcN` measurement names. CSV is scalar data, not a full Touchstone matrix. ECal and S2P are refused. |
| Handheld VNA | `keysight-n9915a`, `keysight-n9917b` | NA mode, trace setup, sweep averaging and actual-axis CSV | NA option required; global mode is changed on connection. One measurement channel. Formatted data is one value per point, unlike ENA. No CAT/SA/IQA capability is implied. |
| RF power | `keysight-e4417a`, `keysight-n1912a`, `keysight-u8487a`, `keysight-u8488a`, `rohde-nrp18s`, `rohde-nrp33sn` | Frequency correction, averaging, fresh acquire and average fetch; zero/calibrate on the two meter bodies | Bodies explicitly route physical input to the calculation feed. Average power only, no envelope peak/gates. NRP watt values are converted to dBm. Direct NRP requires an existing SCPI-capable VISA/vendor interface, or the SN network interface; no legacy sensor DLL backend was added. |
| Oscilloscopes | `tektronix-tds3034b`, `tektronix-tds3032b`, `tektronix-tds2024c`, `tektronix-tds2014`, `rohde-rtb2004`, `rohde-rtm3004`, `keysight-dsaz204a`, `keysight-dsa71254` | Native single acquisition, completion checks and voltage waveform CSV; scalar measurements on Tek/Keysight | Signed Tek bytes and Infiniium WORD samples use native scaling; R&S ASCII is already scaled. Time origin is taken from instrument data. Infiniium clears stale ADER and latches completion; R&S interrupted acquisition is rejected. No screenshots, history/segmented or digital/logic exports. R&S scalar automatic measurements are not implemented. |
| Electronic loads | `chroma-63600-5`, `teledyne-t3el150303p` | Static CC/CV/CP/CR setup, load/input state and voltage/current/power reads | Chroma uses mainframe logical channels, high range and static L1; configure installed channel count and L1 on the instrument. Slew converts A/s to A/us. Teledyne uses `FUNC` and `SHOR`. No list/transient/parallel control. |
| Function / clock generators | `keysight-33250a`, `srs-cg635` | 33250A standard waveforms, voltage amplitude/offset, output load, AM/burst state; CG635 frequency and global run/stop | No arbitrary-memory upload. CG635 stop holds outputs low; it does not tri-state or disconnect them. CG635 has no generic voltage-waveform controls. |
| Phase noise | `keysight-e5052b` | PN1 offset span, averaging/correlation counts, initiation/completion, actual-axis CSV and spot noise | Carrier detection is instrument managed. Fetch does not rearm; initiate and wait before reading. Spot estimates interpolate dB linearly in log(offset), with no extrapolation. No jitter integration or generic carrier controls. |
| Signal Hound spectrum / IQ | `signalhound-bb60c-spike`, `signalhound-sm200c-spike` in `speca` or `rtsa` | Spike SA single-detector trace export; ZS finite IQ capture with real rate/count and BIN/MAT/IQ TAR export | Running Spike SCPI server required. One connection/mode per Spike instance. Choose one kind explicitly; no automatic selection between SA and IQ. Spectrum export requires dBm units. IQ rate and IF bandwidth are distinct. IQ is interleaved little-endian float64 in sqrt(mW), not normalized ADC counts. No direct SDK or continuous streaming. |

## Configuration and acquisition

Copy selected rows from
[`config.inventory.hardware.toml.example`](../../examples/configs/config.inventory.hardware.toml.example)
and replace resources with actual instrument addresses. Do not load two Spike
rows against the same server. Default resource transport is VISA; the handheld
example explicitly uses serial and a baud rate.

Autoconfig now recognizes the 78 direct model identities by manufacturer and exact
model field. Keithley `MODEL ` prefixes and spacing/hyphens are normalized.
Option suffixes and unknown revisions are not stripped speculatively. For
inventory descriptions such as `N9020A-526`, configure `keysight-n9020a` after
confirming the instrument actually identifies as N9020A; 526 is an installed
frequency option, not a second driver.

Scope sequencing follows the existing public API:

```python
col.equipment.oscope.arm_single(oscope_id=1)
# Generate the event under test after arming.
col.equipment.oscope.wait_complete(oscope_id=1, timeout_s=10)
col.equipment.oscope.save_waveform(oscope_id=1, channel=1, path="capture.csv")
```

For the first-pass average-power profiles, `acquire` selects immediate
triggering and completes a new acquisition;
`measure_power_avg_dbm` fetches its result without rearming.
`measure_power_dbm` performs both. For Spike IQ, call `acquire`, then
`save_IQ_data`. Spectrum/VNA trace exports perform a new sweep. Phase-noise trace
export and spot reads fetch the captured trace without starting another sweep.

## Remaining category work

The current category-by-category disposition is maintained in
[the manual analysis](inventory-manual-analysis.md). That follow-up implements
most remaining conventional bench instruments and documents unresolved model
identities, host-controlled sensors, SDK interfaces and deeper acquisition
workflows. The original plan is not fully completed; remaining entries are not
counted as covered merely because a generic kind exists.

The new ML2495A profile reads the current CW result and does not implement fresh
`acquire`. New native Tek RSA exports fetch a completed capture, without rearming.
The first-pass acquisition descriptions above apply to its original profiles.

## Hardware acceptance for each category

1. Record the actual `*IDN?`, firmware, fitted options/modules/sensors, resource
   and transport timeout. Open only the matching named driver.
2. Run each implemented setup/read path, then inspect the native error queue.
   Require no unsupported-command errors. Save command logs with the result.
3. Exercise output-off/input-off and channel switching before applying a source
   or load. Measure PSU/RF generator outputs independently; setting readback is
   not an accuracy check.
4. For acquisition devices, test a normal trigger and an absent/external trigger.
   Confirm timeout/interruption handling; fetching must not unexpectedly rearm.
5. Compare a known waveform/trace/capture against the front panel or vendor
   export: number of samples, frequency/time axis, scaling, units and endianness.
   Test nonuniform VNA axes and overload/unavailable measurements.
6. For a power sensor, qualify the actual sensor/body pair and average feed;
   compare dBm and watts against a known source. For handhelds, compare native
   descriptor, range and displayed value, including held/relative values.
7. Promote only the exercised operations to hardware-qualified status, recording
   instrument identity and evidence. This inventory table still has no formal
   hardware-qualified rows; lab checks outside the expansion pass are not
   listed here until they are captured that way.

## Command references

Driver docstrings retain reference names and revision identifiers. The main
references used for these implementations are:

- [Keysight 34410A/11A command reference](https://www.keysight.com/us/en/assets/9018-61141/programming-guides/9018-61141.pdf), [Keithley 2001 manual](https://download.tek.com/manual/2001-900-01(K-Aug2010)(Operator).pdf).
- [PNA programming help](https://helpfiles.keysight.com/csg/N52xxB/Programming/Programming_Guide.htm), [ENA programming help](https://helpfiles.keysight.com/csg/e5071c/programming/programming.htm), [FieldFox NA commands](https://helpfiles.keysight.com/csg/FFProgrammingHelpWebHelp/A_NA_Mode_Commands.htm). ENA B/A models still need hardware verification against their exact firmware.
- [R&S RTB2000 manual](https://www.batronix.com/pdf/Rohde-Schwarz/RTB2000/RTB_UserManual_en.pdf), [Infiniium programming guide](https://www.keysight.com/us/en/assets/9018-07141/programming-guides/9018-07141.pdf).
- [Chroma 63600 programming manual v2.2](https://assets.tequipment.net/assets/1/26/Chroma_63600_Series_-_Manual_V2.2.pdf), [CG635 programming manual](https://www.thinksrs.com/downloads/pdfs/manuals/CG635m.pdf).
- [E5052B programming help](https://helpfiles.keysight.com/csg/e5052b/welcome.htm), [Spike SCPI reference](https://signalhound.com/sigdownloads/Spike/docs/html/scpi_programming.html).
- Handheld protocol is based on [original wire observations](https://mjoldfield.com/atelier/2011/06/agilent-macos.html) and the [sigrok protocol description](https://sigrok.org/wiki/Agilent_U12xxx_series), rather than treating optical serial as bench-DMM SCPI.
