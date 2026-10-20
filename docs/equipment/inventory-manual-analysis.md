# Remaining inventory: manual analysis and implementation

Version 0.8.1 continues the `misc_equipment.xlsx` rollout inside existing kinds.
The second implementation pass added 24 identities; the third resolved four more: RTE1204, RTP164,
Fluke 289 and Fluke 189. The rollout now has **83 identities / 85 kind/model
registrations** across the same 12 kinds. The two extra registrations are the
separate Spike spectrum/IQ profiles from the first pass. No equipment category
was introduced. There are 78 exact-model discovery mappings. Native Fluke and
Genesys serial profiles, and the two Spike identities, require explicit selection.

This is documentation-based verification, with synthetic recording-transport
regressions. No claim of hardware validation is made. Manuals substantiate the
protocol, command spelling, sequencing, units and transfer interpretation;
tests check that the implementation follows that analysis. Synthetic replies
are not instrument recordings and cannot establish firmware behavior or
measurement accuracy. Hardware comparison is useful follow-up, not a
prerequisite for accepting the documented implementation work.

Manufacturer-authored documents are linked below, including third-party mirrors
where the original download is unavailable or inaccessible. A family reference
is identified explicitly rather than represented as an exact-model capture.
Only documented subsets are exposed. Unsupported public operations raise
`EquipmentCapabilityError` before issuing their generic command.

## RF generators (`vsg`)

| Profile | Evidence | Implemented subset and analysis |
| --- | --- | --- |
| `rohde-smiq04b` | [SMIQ operating manual vol.2, 1125.5610.12-11](https://scdn.rohde-schwarz.com/ur/pws/dl_downloads/dl_common_library/dl_manuals/dl_user_manual/Smiqb_OperatingManual_V2_en_11.pdf), SOURce/OUTPut groups | CW frequency and setting readback, explicit dBm level, RF enable/state, reset/completion. SCPI personality and CW operation must be selected. Vector/modulation/reference controls are excluded. |
| `keysight-8648c` | [8648A/B/C/D operation guide, chapter 2](https://manualzz.com/doc/38451919/agilent-8648-a--b--c--d-signal-generator-operation-and-se...) | Same small SCPI CW subset. Select SCPI rather than the older 8656/8657 compatibility language. Explicit `DBM` avoids dependence on the active amplitude unit. |
| `keysight-83650l` | [8360 L-Series user guide, SCPI summary](https://docs.alltest.net/manual/Alltest-HP-Agilent-Keysight-83650L-Manual.pdf) | CW controls only; configure CW mode first. No speculative HP native-language or swept-source commands. |
| `anritsu-mg3692c` | [MG369xC SCPI programming manual, 10370-10375E](https://dl.cdn-anritsu.com/en-us/test-measurement/files/Manuals/Programming-Manual/10370-10375E.pdf), frequency/power mode groups | Explicit frequency and power `MODE FIX` before their settings, dBm power, RF output, reset/completion. The separate native Anritsu language is not interchangeable with SCPI. No setting readback is inferred from other vendors. |
| `tektronix-tsg4106a` | [TSG4100A programmer manual, 077-1079-00](https://download.tek.com/manual/TSG4100A-Series-Programmer-Manual-EN-EN.pdf), pp.2-17, 2-24, 2-28 | `FREQ`, `AMPR … DBM`, `ENBR`; frequency/output-state readback. This addresses the Type-N RF connector. The low-frequency BNC uses different commands. Power readback is excluded because `AMPR?` returns the currently selected units. |

Tests distinguish these dialects and assert that setting frequency/level does
not explicitly enable output. Frequency readback reports the programmed setting,
not independently measured RF. For the legacy SCPI profiles, setting a CW
parameter does not promise to exit a prior sweep mode. Panel CW setup is a
precondition; modulation and level offsets remain instrument configuration.

**8684D remains unregistered.** The [HP operation-manual excerpt](https://docs.alltest.net/manual/Alltest-HP-Agilent-Keysight-8684D-Manual.pdf)
substantiates front-panel frequency/level/modulation operation, but the retrieved
material does not establish a remote programming interface or command set.
Next step: identify the fitted interface and obtain its remote-command section;
do not assign 8648 or 8360 SCPI to this older model merely from its manufacturer.

## Spectrum analyzers (`speca`)

| Profiles | Evidence | Implemented subset and analysis |
| --- | --- | --- |
| `anritsu-ms2721b`, `anritsu-ms2723b` | [10580-00176, original MS272xB programming manual](https://dl.cdn-anritsu.com/en-us/test-measurement/files/Manuals/Programming-Manual/10580-00176.pdf), pp.25–27, 37–40 | SPA frequency/RBW/VBW/reference setup, arm/single/wait/abort, dBm trace CSV and host bandwidth/interpolation. Trace query uses numeric trace identifiers 1–3 and little-endian REAL32 definite blocks. Completion polls operation status bit 8 (`256`), as specified by this manual, instead of assuming `*OPC?`. |
| `anritsu-ms2720t` | [10580-00341K programming manual](https://dl.cdn-anritsu.com/en-us/test-measurement/files/Manuals/Programming-Manual/10580-00341K.pdf), SPA, FORMAT, INITiate and TRACe groups | Same SPA subset and numeric binary trace workflow. Query the current application before configuration. A non-SPA session is refused; the documented long mode-switch settling interval is not hidden behind an immediate fetch. |
| `rohde-fpc1500` | [FPC user manual 1178.4130.02 v13](https://www.batronix.com/files/Rohde-%26-Schwarz/Spectrum-Analyser/FPC1500/FPC_UserManual_en.pdf), operating modes and remote spectrum commands | Select `INST:SEL SPEC`, native reference level, sweep setup/completion, ASCII dBm trace 1/2, CSV and host calculations. Select trace write mode before sweeping. Different manual/firmware revisions report 631 or 1183 points; derive the count from the returned trace. The `SWE:POIN` command found in the VNA section is not used for spectrum mode. |
| `keysight-8593e` | [8590 E/L programmer guide, 08590-90235, June 1995](https://xdevs.com/doc/HP_Agilent_Keysight/08590-90235%208590E%2090L%2091C%20Prog%20Guide%20Jun95.pdf) | Native `CF/FA/FB/SP/RB/VB/RL`, active-marker frequency placement/read and peak search. No SCPI sweep or trace aliases. Marker 1 represents the active marker; only its frequency is exposed. |
| `keysight-8563ec` | [856xE/EC user guide, chapter 5 and language reference](https://device.report/m/c5c95d946588cdeb3355d41046c5b04816a1471e37ed488e5cf27039a500b320) | Native setup/marker-frequency controls plus trace-A export and host calculations. `AUNITS DBM`, clear-write trace A, `SNGLS;TS`, `TDF P`, `TRA?` follow the documented parameter-unit transfer. Require 601 values and use `FA?/FB?` endpoints. Transfer leaves trace A in view mode, so each subsequent fetch restores clear-write before its sweep. The transport timeout must cover completion. |

For Anritsu, set the requested trace to live/write on the instrument before
acquisition; this subset does not manage held/reference traces. Frequency CSV
requires a positive linear span; zero-span/time data is rejected. Tests cover
little-endian negative amplitudes, operation-bit completion, firmware-dependent
FPC point counts and the HP clear-write/sweep/transfer sequence. Marker power
readback is excluded on both HP profiles because absolute versus delta-marker
state needs its own implementation; trace power on the 8563EC is available.

**ZPH-B4 is an option, not an analyzer identity.** The manufacturer's
[ZPH specifications, ordering information](https://scdn.rohde-schwarz.com/ur/pws/dl_downloads/pdm/cl_brochures_and_datasheets/specifications/3607_6638_22/Cable-Rider-ZPH_specs_en_3607-6638-22_v1000.pdf)
identifies it as a 3-to-4 GHz frequency upgrade. Spectrum operation additionally
requires the combi host model `.12` and ZPH-K1. Identify the host and installed
options before implementing a ZPH profile; B4 alone does not establish SA
capability.

**E7495B remains unregistered.** The [E7495A/B measurement guide](https://www.keysight.com/us/en/assets/9018-04875/user-manuals/9018-04875.pdf)
identifies a multifunction base-station test set and PC trace-analysis workflow.
The retrieved material does not substantiate an ESA/X-Series remote SCPI
personality. Next step is its exact remote protocol and measurement-mode
reference, then an SA subset in the existing `speca` kind if that interface
supports it. Absence of a retrieved command reference is not proof that remote
control is impossible.

## Oscilloscopes (`oscope`)

New profiles are `tektronix-mso58`, `tektronix-mso64`,
`tektronix-tbs2204b`, `tektronix-mso4104` and `tektronix-tds7704b`.
They expose analog channel display/scale/offset, timebase scale, edge trigger,
single acquisition/completion and voltage waveform CSV. MSO58 permits eight
analog channels; the other profiles permit four. Scalar measurements, digital
channels, arbitrary acquisition-mode changes, screenshots and segmented/history
exports are excluded from these new profiles.

References:

- [MSO54/56/58/64 programmer manual 077-1305-05](https://download.tek.com/manual/5_6-Series-MSO54-MSO56-MSO58-MSO58L-MSO64-Programmer-Manual_EN-US_077130505.pdf), Display Control, Trigger, Acquisition, Waveform Transfer and appendix D. MSO58/MSO64 use `DISP:WAVEV1:CHn:STATE` for display control, rather than the older `SELect:CHn` dialect. This subset owns waveform view 1.
- [TBS2000B programmer manual 077-1149-04](https://download.tek.com/manual/TBS2000B-Programmer-Manual-EN-US-077114904.pdf), waveform transfer and trigger commands; the earlier 077-1149-03 reference has the same native preamble group.
- [MSO4104 documentation catalog](https://www.manualslib.com/products/Tektronix-Mso4104-8778831.html), the original MSO4000 programmer manual's waveform group. The original model is registered separately from the existing MSO4104B profile.
- [TDS7000/CSA7000 programmer reference](https://download.tek.com/manual/PHP014070web.pdf), waveform group. **Family-reference analysis for TDS7704B**, not an exact B-revision command recording; this is a lower-confidence profile than an exact-model manual audit.

The fetch requires a stopped acquisition, disables response headers, selects
analog source and signed big-endian 16-bit `RIBINARY`, and checks the preamble's
point format and second/volt units. Only scalar `Y`/`YT` data is accepted.
Min/max envelope pairs are refused. Exact byte count must match the preamble;
voltage is `(sample - YOFF) * YMULT + YZERO`; time origin is
`XZERO - PT_OFF * XINCR`. Tests use signed extrema, nonzero offset/origin,
envelope refusal and truncated payloads. Probe units remain a necessary part
of the response validation.

### RTE1204 and RTP164 resolution

`rohde-rte1204` and `rohde-rtp164` now implement analog channel state,
scale/offset, timebase scale, trigger mode, continuous run/stop, single
acquisition and voltage waveform CSV. They use the native RTE/RTP dialect,
separate from RTB/RTM. Exact guides are [RTE v21](https://cdn.rohde-schwarz.com.cn/pws/dl_downloads/pdm/cl_manuals/user_manual/1326_1032_01/RTE_UserManual_en_21.pdf)
and [RTP v18](https://scdn.rohde-schwarz.com/ur/pws/dl_downloads/pdm/cl_manuals/user_manual/1337_9952_01/RTP1320_UserManual_en_18.pdf).
The manufacturer's [RsRtx examples](https://rsrtx.readthedocs.io/en/latest/examples.html)
and generated command reference resolve the previous transfer uncertainty:
[RUNSingle](https://rsrtx.readthedocs.io/en/latest/Run.html),
[acquisition count](https://rsrtx.readthedocs.io/en/latest/Acquire.html),
[header](https://rsrtx.readthedocs.io/en/latest/Channel_Waveform_Data_Header.html),
[values](https://rsrtx.readthedocs.io/en/latest/Channel_Waveform_Data_Values.html)
and [export switches](https://rsrtx.readthedocs.io/en/latest/Export_Waveform.html).
These are protocol references, not a dependency on the vendor SDK.

The profile owns waveform 1 and the ESR/OPC completion workflow. Arm checks
segmentation is off, stops prior acquisition, consumes stale ESR events, sets
one acquisition, sends `RUNS` and queues `*OPC`. Waiting polls ESR bit 0, checks
IEEE error bits and requires a completed acquisition count. This avoids repeated
blocking `*OPC?` queries and refuses stale/aborted driver captures. A timeout does
not enable export; call `abort` before reusing a timed-out session. Use one
controller and avoid panel changes while acquiring. Individual queries are
subject to the configured transport timeout; the polling deadline does not
preempt an in-flight transport call. The single count also controls averaging;
this is a one-acquisition subset, not an average-accumulation workflow.

Export requires manual probe attenuation with explicit voltage units and refuses
history display and envelope/peak pairs. The manufacturer’s
[probe unit reference](https://rsrtx.readthedocs.io/en/latest/Probe_Setup_Attenuation_Unit.html)
only establishes the setting’s effect in manual mode; automatic probe-unit
resolution is not assumed. Set the actual probe ratio and voltage unit on the
panel before capture.
It disables multichannel export, included X-values and raw integer samples,
selects the full waveform, then reads scaled ASCII from `CHANn:WAV1:DATA?`.
Those switches affect remote query data as well as files. The four-field header
specifies first and last sample times, count and values per sample. Therefore
`dt=(last-first)/(count-1)`, with exact count and finite-value checks. No RTB
`DATA:XINC?` command is assumed. The count must be at least two to establish an
axis. Native trigger-source/level APIs, arbitrary acquisition modes, screenshots,
math/digital/history/segmented exports remain excluded.

Tests distinguish stale and new completion events, cancellation, no-trigger
timeout, ESR errors, single-channel export framing, time endpoints, units,
envelope pairs, fractional counts and missing/extra samples.

## RF power meters (`pwrmeter`)

### Implemented hosts

`anritsu-ml2495a` uses the [ML248xB/ML249xA remote programming manual,
13000-00239J](https://dl.cdn-anritsu.com/en-us/test-measurement/files/Manuals/Programming-Manual/13000-00239J.pdf),
chapters 6 and 11. Physical input A maps to API channel 1; configure channel 1
as CW, relative off and dBm. Frequency correction selects its explicit frequency
source, and moving-average count accepts 1–512. `CWO 1` (without `?`) returns a
labelled `CWO1,<value>` response. Parse that label rather than taking the first
number as power. Wrong-channel, array, overload and malformed results are
rejected. This is a **current CW display/result read**, without a promise of a
freshly triggered conversion. `acquire`, peak and pulse/profile APIs are refused.
Tests distinguish the native label, invalid values and unsupported acquisition.

`rohde-nrx` uses the [NRX user manual 1178.5566.02 v09](https://assets.testequity.com/te1/Documents/pdf/rs/RS_NRX_UserManual_en_09.pdf),
sections 13.3/13.4, 13.6.3/4/6, 13.7 and the sensor filter commands. See also
[v04 filter reference](https://assets.tequipment.net/assets/1/26/Rohde_and_Schwarz_NRX_-_Manual.pdf)
and the [manufacturer's native/emulation command comparison](https://scdn.rohde-schwarz.com/ur/pws/dl_downloads/pdm/cl_manuals/application_sheet/1179_3238_01/NRX_RemoteEmulation_AppSheet_en_04.pdf),
table 4-1's **native NRX column**. Configure only connected fixed ports A–D
using `channels=1..4`. Pane n explicitly owns sensor n, continuous-average mode,
`(SENSn)` calculation, average feed, absolute dBm and no relative result.
Acquisition uses continuous-off, BUS source, initiate, immediate bus trigger,
then completion; fetch alone does not rearm. Frequency correction and averaging
address the same sensor. USB/LAN sensor-index selection, sensor discovery,
NRT directionality, peak and gates are excluded. Inventory `NRX BASE` denotes
the body, not a separately identified sensor or guaranteed four installed ports.

### Other power entries and disposition

| Inventory item | Evidence / finding | Next work within existing kind |
| --- | --- | --- |
| LadyBug LB479A / LB480A | [Manufacturer's LB4xx programming guide v2.1](https://www.ladybug-tech.com/downloads/documentation/PowerMeter_Programming%20Guide_2_1.pdf) identifies `LB_API2.DLL` and WinAPI/stdcall. [Current resources](https://www.ladybug-tech.com/resources/) separate these legacy devices from newer USBTMC sensors. | A real SDK-backed adapter needs runtime/library discovery, API error handling and scalar/unit fixtures. Check installed SDK ABI and redistribution terms. No dependency, DLL redistribution or fictitious SCPI registration was added. |
| NRP-Z81 | [R&S application 1GP69](https://scdn.rohde-schwarz.com/ur/pws/dl_downloads/dl_application/application_notes/1gp69/1GP69_0E.pdf) describes the NRP-Z VXI PnP and NrpControl2 architecture; [1GP61 toolkit](https://scdn.rohde-schwarz.com/ur/pws/dl_downloads/dl_application/application_notes/1gp61/1GP61_0E.pdf) demonstrates driver calls. | Use a compatible meter host, or implement the actual legacy NRP-Z API transport. Do not infer USBTMC from the connector or newer NRP18S profile. Validate body/sensor compatibility separately. |
| Bird 5000-EX / 5011-EF | [Bird 920-5000-EX instruction manual](https://birdrf.com/hubfs/discontinued-manuals/920-5000-EX_digital-power-meter.pdf) identifies the body and attached terminating sensor; the body has EIA-232 at 9600 8N1. | The [official serial example and attached protocol](https://birdrf.zendesk.com/hc/en-us/articles/23630642924439-How-do-I-use-the-RS-232-port-on-my-5000-series-Wideband-RF-Power-Sensor-to-automate-power-measurements) were located in this follow-up. Its attachment explicitly covers 5012A, not the 5000-EX body or 5011-EF sensor. Obtain the matching body protocol before reusing its interrogation/configuration/stream sequence. 5011-EF is not a standalone VISA meter. |
| Anritsu PSN50 | [Manufacturer's support/downloads](https://www.anritsu.com/en-us/test-measurement/support/downloads?model=PSN50) describes USB host use with handhelds and serial legacy-host use. CalXpert is calibration software, not a retrieved SCPI programming reference. | Identify the intended host or exact direct communication protocol. Host USB power-meter application commands are separate from the SPA analyzer subset. |
| Anritsu MA2411B | The sensor record does not establish an independently addressable SCPI instrument; the [ML2495A documentation set](https://www.anritsu.com/en-us/test-measurement/products/ml2495a) documents host-controlled sensor measurements. Exact sensor/body compatibility has not been established here. | Confirm actual sensor label, compatible body/cable and firmware before selecting a host or implementing peak measurement. No automatic assignment to the new ML2495A profile. |
| HP 8990A | [Exact 8990A operation guide, 08990-90001](https://www.keysight.com/jp/ja/assets/9018-02107/user-manuals/9018-02107.pdf) and an [archived programming-manual listing](https://www.eserviceinfo.com/downloadsm/173333/Agilent_HP%208990A%20Programming.html) were located. Common search results instead return the newer 8990B guide. | The correct programming manual is 08990-90002, as confirmed by the [8990A operation manual](https://www.artisantg.com/info/Keysight_Agilent_8990A_Manual_202321014364.pdf). Archive download/preview attempts did not yield its command text. Retrieve and audit that reference, sensor inputs, result units and acquisition model. Neither an EPM average alias nor the 8990B command set is substantiated. |
| Keysight E9300A, E9327A, N1921A, N1922A, N8487A, 8481D | These are attached sensors; the first-pass EPM-P/P-Series body profiles control compatible pairs. | Check each body's published compatibility table, sensor calibration and firmware. Sensor names do not become independent connection rows. Peak/gate work needs the appropriate body API, not an alias to average measurement. |

## Function/arbitrary generators (`asg`)

`gwinstek-afg3032` is based on the manufacturer-authored
[AFG-3021/3022/3031/3032 full user manual](https://manuals.plus/m/a280818d4836eb6fd43db9736ecd68ba3366153452db7a74237f12aa1000aca7),
remote interface pp.300–308. It exposes two-channel frequency, explicit VPP/VRMS
amplitude, output, AM state and burst state. Native amplitude uses `AMPLitude`,
not the generic `VOLT` setting. Waveform/offset/load remain panel setup:
`APPLy` enables output, making it inappropriate for a shape-only setter without
additional output-state handling. The quick-start guide alone is insufficient
for this decision. Tests check channel 2 and the absence of `APPLy` side effects.

**SFG-2120:** the [SFG-2000/2100 user manual](https://www.gwinstek.com/en-US/products/downloadSeriesDownNew/12777/481)
and [manufacturer's product description](https://www.gwinstek.com/en-US/products/detail/SFG-2000)
identify a different generator family. No remote command reference was
established by the retrieved documentation. Leave it unregistered unless an
actual fitted remote interface is identified; do not substitute MFG-2120 or
AFG-3032 commands based on a similar number.

**M8195A:** the [M8195A user guide, general programming](https://www.keysight.com/us/en/assets/9018-04320/user-manuals/9018-04320.pdf),
section 6.14, defines `FREQ:RAST` as the DAC sample frequency. It is not waveform
repetition frequency. The [manufacturer's sine-generation example](https://docs.keysight.com/kkbopen/how-do-you-programmatically-generate-sine-waves-on-the-m8195a-for-display-and-for-saving-to-a-csv-file-614517493.html)
uses calculated samples and waveform download. Remaining implementation is
waveform memory allocation/upload, DAC mode/channel mapping, signed sample
encoding and scaling, clock/rate, sequence/run/abort and output-state handling.
Those belong in an extended `asg` workflow; no new category is needed. A generic
frequency/amplitude alias would misrepresent this device, so none was added.

## Electronic loads (`eload`)

`ametek-pla4k-600-240` uses the manufacturer-authored
[PLA/PLW programming guide](https://www.manualsdir.com/manuals/754240/ametek-pla-plw-programming-manual.html),
MODE, INPUT, CURRENT, VOLTAGE, POWER, RESISTANCE and MEASURE groups. The profile
provides one-input static CC/CV/CP/CR, input enable/state, voltage/current reads
and reset. Select SCPI personality before connecting; the legacy AMREL language
is separate. This is a **family programming reference**; the exact older 4 kW
rating has not been independently verified from a manufacturer's model table.
No new software limits are inferred from its inventory name.

Slew and protection clearing are deliberately excluded: the documented slew
parameter is a transition time, while the existing API expects A/s; clearing a
trip can restore the previous input state. Tests assert that a generic slew-rate
command is refused. Dynamic/list operation still needs native trigger/abort,
timing and transition-time semantics.

**Chroma module records:** `63630-80-60` is an installed module controlled via
the existing `chroma-63600-5` mainframe profile, not another transport endpoint.
`63630-80-20` remains an unresolved inventory identity; the
[63600 series manual](https://assets.tequipment.net/assets/1/26/Chroma_63600_Series_-_Manual_V2.2.pdf)
does not justify silently correcting it to a different module. Confirm the
label and logical channel layout before defining ranges. The existing static
L1 implementation is retained; list/transient/parallel behavior is unfinished.

## Real-time spectrum analyzers (`rtsa`)

`tektronix-rsa5115b` and `tektronix-rsa5126b` use the
[exact RSA5100B programmer manual 077-0901-05](https://download.tek.com/manual/RSA5100B-Programming-Manual-EN-US-077-0901-05_077090105.pdf)
([full manufacturer-authored text mirror](https://device.report/m/768f72f644270bfba95235a6ebec01ffc4c9b48f1a5d831974c45f533cdae63b)).
`tektronix-rsa6114a` uses the [original RSA6100A/RSA5100A programmer reference](https://www.manualslib.com/manual/1311017/Tektronix-Rsa5100a-Series.html)
for the **shared spectrum subset only**. A B-series IQ header is not assumed on
the A-series instrument.

The new profiles create the Spectrum view and configure native
`SENS:SPEC:FREQ:CENT/SPAN` and resolution bandwidth. Display frequency offsets
are not RF tuning commands. Existing generic sample-count/trigger aliases are
refused. Configure trigger, capture length and sensor/front-end settings on the
instrument, use `acquire` to finish a finite capture, then export. Exports read
captured data without starting another acquisition.

Spectrum export fetches little-endian float32 `FETC:SPEC:TRACn?` for traces 1–3,
requires dBm units and a linear x-axis, and queries actual frequency endpoints.
IQ export on the B profiles queries first/last record IDs and explicitly selects
the last record. Its nine-field native header supplies the actual sample rate,
IQ pair count, center frequency, bandwidth, trigger position and timestamp.
The binary payload must contain exactly that many interleaved float32 I/Q pairs.
FastFrame records and invalid/truncated data are refused. Native floating IQ is
preserved without inventing volts or multiplying by the separately documented
Option 05 external-digital-output scale factor.

Existing BIN/MAT/IQ TAR writers receive interleaved little-endian float64 to
maintain their established contract; MAT contains complex samples and the TAR
contains metadata. Tests check actual header rate/count, record selection,
negative I/Q values, all three formats, FastFrame rejection, frequency tuning
and linear-axis validation. Standalone BIN has no metadata container; preserve
the recorded equipment evidence alongside it, or use the TAR/MAT exports.

**RSA3036B remains unresolved.** The inventory string could not be substantiated
as an exact manufacturer/model identity. The [manufacturer’s RSA3000B model table](https://www.tek.com/en/datasheet/rsa3000b-series)
lists RSA3303B, RSA3308B and RSA3408B, which also do not establish the inventory
identity. It is not automatically corrected to RSA3303B, RSA306B or a Rigol RSA3030. Obtain the actual label/IDN before adding an exact
profile. Existing `tektronix-rsa5100b` behavior is unchanged; select the new exact
slugs to use the documented native implementation described here.

## Power supplies (`psu`)

`tdk-gen300-5-serial` uses the manufacturer-authored
[Genesys 750/1500 W user manual, chapter 7](https://www.atecorp.com/getmedia/13512e00-f13e-448e-9adc-d54daa8115e8/gen600-2-6-manual.pdf).
The model table includes GEN300-5. This is explicitly the native serial
personality; the existing `tdk-genesys` SCPI family match is not evidence of a
native interface. No SCPI `*IDN?` discovery rule selects this profile.

Require `driver="serial"`, an explicit panel-matching `baudrate` and
`device_address` (0–30). The transport uses 8N1. Write raw ASCII plus CR, select
`ADR n`, require `OK`, and consume an acknowledgement after every setting.
Commands are `PV`, `PC`, `OUT`, `MV?`, `MC?` and `OVP`; `OUT?` returns `ON`/`OFF`,
not a SCPI number. Command/execution errors fail the operation. No broadcast,
reset, stored-setting recall or automatic output-enable command is sent on
connection. Disable unsolicited SRQ messages for this synchronous subset.
Voltage/current-derived power uses separate measurements.

The [configuration example](../../examples/configs/config.inventory.hardware.toml.example)
contains a native serial row. Tests exercise address-before-setting ordering,
CR rather than LF framing, acknowledgement consumption, textual output state
and an execution-error reply. GPIB/LAN option personalities require their own
matching documentation; they are not selected from a serial model name.

## Handheld, clamp and ScopeMeter entries (`dmm` / `oscope`)

### Fluke 289 and 189 resolution

`fluke-289` and `fluke-189` now expose `fetch` and `get_function` using native
read-only `QM` requests. The manufacturer-authored references are the
[287/289 remote-interface specification](https://btbm.ch/assets/uploads/Fluke28xRemoteInterfaceSpecifications.pdf)
and [189/187 archived specification](https://photonicsguy.ca/reference/flukemeter).
The [independent fluke-cli example](https://github.com/mrtumnus/fluke-cli/blob/master/fluke.py)
corroborates CR framing and separate model handling; no third-party code or
additional dependency was incorporated.

Use an optical serial adapter, `driver="serial"`, and explicit baud rate:
115200 for the 289, 9600 for the 189, both 8N1. Connection issues no reset or
function-change command. A read sends `QM\r`, consumes a full CR-terminated
acknowledgement, requires success `0`, then consumes a separate CR data frame.
No SCPI `*IDN?` discovery rule selects these native protocols.

The 289 returns value, unit, state and attribute; accept only NORMAL finite
readings below the overload sentinel. Values already use the meter's base
units. The 189 returns `QM,` followed by a signed display value and unit. Explicit
prefix conversion handles examples such as `+47.66 KOhms` -> 47660 ohms and
`-121.43 mVDC` -> -0.12143 V. Unknown 189 units are refused. `get_function` returns
the normalized unit/mode descriptor; temperature and logarithmic values retain
the reported measurement convention. Each call queries the current primary
display: it can be held or relative and does not promise a fresh conversion.
`fetch` and `get_function` are separate reads, not an atomic reading/descriptor
snapshot. The panel function must remain stable between calls. The 289
attribute field is not exposed by this scalar API. Remote function switching,
reset, logging-memory download and fresh acquisition are excluded.

Tests exercise manufacturer example values, kilo/mega/milli/micro prefixes,
acknowledgement errors/no-data, truncated frames, overload/blank/nonfinite
values, incompatible reply formats, baud-rate validation and unsupported
operations before I/O.

### Other handheld records

- Fluke 87/85 variants, 28 II, 233, 179, 117, 323, T5-600, AC50A and Extech
  380941: no usable direct remote protocol was established for the actual
  inventory versions. The documented 87-IV interface is not evidence for
  inventory 87III/87V. A detachable display or electrical clamp does not itself
  imply PC control. Check the exact model and accessories.
- Fluke 3000 FC / v3000 FC / v3001 FC require their actual gateway/software
  workflow. The [pc3000 FC description](https://www.fluke.com/en-ie/product/accessories/adapters/fluke-pc3000-fc)
  establishes a PC adapter and downloadable timestamped recordings. The
  [ir3000 FC accessory](https://www.fluke.com/en/product/accessories/adapters/fluke-ir3000-fc)
  is a different adapter for listed compatible meters. Next work is a documented
  gateway API or recording importer, not an invented serial `READ?`.
- Fluke 125B belongs to the existing oscilloscope family for waveform work.
  Establish its FlukeView/optical interface, framing, channel units and timebase
  metadata before implementing a download. No Tek or R&S waveform aliases apply.

## Existing deeper operations

Bench DMM scalar acquisition, VNA scalar/actual-axis CSV, E5052B spot phase noise
and the 53150A subset retain their first-pass implementations and references in
[the rollout](inventory-rollout.md). No additional inventory identity remains
for the frequency-counter or phase-noise category in the current list.
Buffered DMM/scanner capture, VNA full S2P/ECal and integrated jitter remain
unfinished features rather than additional model coverage:

1. DMM buffers: define trigger/sample counts, asynchronous completion, actual
   array count, timestamps/status and overload behavior; test fetch without
   rearming and partial buffers.
2. VNA S2P: fetch all four **complex** S-parameters on the actual stimulus axis,
   establish port order/reference impedance and sweep consistency, then write
   Touchstone. Scalar display CSV cannot stand in for complex S2P. ECal needs
   explicit module/port/standard workflow.
3. Jitter: document SSB-to-phase conversion, offset integration limits,
   interpolation convention and carrier normalization; test against analytic
   spectra before adding an integrated result to the existing phase-noise API.

These analyses leave concrete next steps where code was not substantiated.
They do not count unresolved identities, host accessories, SDK dependencies or
unimplemented workflows as coverage.

## Pre-PR audit and fixes (0.8.1)

The audit covered every added driver module, its permitted inherited operations,
exact-model discovery, transport framing, artifact writers and the documentation
claims. Seven finding groups were fixed before preparing the PR:

| Finding | Impact | Resolution and regression |
| --- | --- | --- |
| PNA indexed `INITn:CONT` was used as if continuous triggering were a channel setting | A sweep could affect the wrong channel or fail before data retrieval | Use documented internal trigger plus `SENSn:SWE:MODE SING`, then completion. Averaging repeats this channel-specific sweep. Cover both B-series and legacy PNA profiles. |
| Keysight spectrum fetch did not unfreeze the requested trace; PSA inherited X-Series detector syntax and six-trace limits | A new sweep could export old held data, or issue unsupported PSA commands | Set `TRACn:MODE WRIT` before an immediate sweep. This also enables X-Series trace updates; TYPE alone is insufficient. Limit E4440A to three traces and use its native `DET` command. |
| Average-power one-shot paths inherited prior trigger source | An external/BUS setup could prevent the promised immediate fresh reading | Select `TRIGn:SOUR IMM` on Keysight meter bodies and `TRIG:SOUR IMM` on U848x/NRP before initiate. Fetch alone still does not rearm. NRX retains its explicit BUS-trigger workflow. |
| ASCII waveform parser ignored declared definite-block length | Truncated framing could be accepted if the numeric token count happened to match | Reuse the validated definite-block parser, reject unexpected trailing data, and preserve payload whitespace and legacy ASCII indefinite framing. Correct the old test fixture's declared length from 13 to its actual 11 bytes. |
| Native Genesys framing/address validation was incomplete | A serial timeout could turn a partial reply into apparent success; a fractional address could be truncated to a different device | Require a complete CR-terminated frame before accepting `OK` or a value. Cover incomplete ACK/measurement replies and reject fractional/boolean device addresses before I/O. |
| IQ TAR writer did not create parent directories | BIN/MAT worked with a new output directory while TAR failed | Create parents consistently; all three Spike and native Tek export formats are exercised under initially absent directories. |
| Case-insensitive TDS3032B model lookup did not preserve its two-channel limit | Uppercase configuration could expose nonexistent channels 3/4 | Normalize the model before determining channel count; assert rejection before channel I/O. |

Command references added during the audit include the manufacturer’s
[PNA initiate](https://helpfiles.keysight.com/csg/N52xxB/Programming/GP-IB_Command_Finder/Initiate.htm)
and [sweep-mode](https://helpfiles.keysight.com/csg/N52xxB/Programming/GP-IB_Command_Finder/Sense/Sweep_SCPI.htm)
references, [PSA trace modes](https://manualsdump.com/en/manuals/agilent_technologies-e4440a-e4448a-e4440-90189-e4446a-e4443a-e4445a/276621/448),
[X-Series trace control](https://www.manualslib.com/manual/3476579/Keysight-X-Series.html),
[EPM-P programming guide](https://www.keysight.com/us/en/assets/9018-01324/programming-guides/9018-01324.pdf)
and [U8480 programming guide](https://res.cloudinary.com/iwh/image/upload/q_auto%2Cg_center/assets/1/7/Keysight_U8480_programming_guide.pdf).
Global trigger-source settings are owned by these acquisition profiles; use one
controller per instrument. Manual-derived command analysis does not establish
fitted-option compatibility, firmware behavior or hardware measurement accuracy.

## Checkout verification

- Full suite: **402 passed, 1 skipped**. The focused inventory/discovery tests
  comprise 138 passing cases, including the native protocol and invalid-IQ tests.
- Ruff passes for package source and the inventory/discovery tests; mypy passes
  for all 210 source files. `pip check` reports no broken requirements.
- All 85 rollout registrations resolve; the 78 exact discovery mappings are
  checked against registered builders. Existing kind names are unchanged.
- A 0.8.1 wheel builds successfully and contains every package module; metadata
  and model registrations were verified. All package sources parse using the
  Python 3.10 grammar. Runtime tests here use Python 3.12; CI covers 3.10/3.12.
- The TOML example parses and loads through core configuration validation,
  including native serial address/baud-rate keys. This does not open hardware.

The skipped test does not supply hardware qualification. Manual analysis and
synthetic command/response checks are the validation mechanisms for this pass.
