# Driver capabilities and documentation requests

This inventory distinguishes public API availability from per-model command
coverage. A model slug or a successful transport write does not establish
hardware support. New deep APIs in a development checkout may require a newer
core than a tagged release; see the GNSS compatibility note below.

For SpecA/oscope **mask** files (`tools.create_mask` offline;
`speca`/`oscope` `apply_mask_setup` + `verify_mask` in procedures), see
[mask guide](https://tps01.github.io/colosseum-equipment/guides/masks.html).

## Adding a model

Put one module in the kind package, for example
`colosseum_equipment/instruments/rtsa/vendor_model.py`:

```python
from colosseum_equipment.instruments.registry import instrument_model
from colosseum_equipment.instruments.rtsa.generic import GenericRtsa


@instrument_model("rtsa", "vendor-model")
class VendorModel(GenericRtsa):
    """Manual: https://example.invalid/programming-guide"""
```

Nothing else is edited. The package imports the new file on its own.
`col.equipment.rtsa` stays the public command list. Inherited methods send the
generic SCPI and log one warning per model and command so the string can be
checked against the manual. Override only the methods that must differ.
Aliases are extra decorator arguments:
`@instrument_model("rtsa", "vendor-model", "vendor-alias")`.

A new kind (rare) is a `generic.py` in a new package whose decorator is
`@instrument_model("kind", "generic", extra_optional=(...))`. Use
`address="either"` when the row may be VISA (`resource`) or serial (`port`),
`address="serial"` when it is serial only, or `address="http"` when the row
uses an `http(s)://` `resource` URL (optional `username` / `password`).

## Implemented vendor models

For the 0.6.0 additions from `misc_equipment.xlsx`, see the
[inventory rollout](inventory-rollout.md). It lists each named model's
implemented subset, command references, hardware qualification requirements and
remaining category work. The [manual analysis](inventory-manual-analysis.md)
records the follow-up source audit, native dialects and unresolved entries. Those drivers explicitly refuse inherited operations
outside their documented subset, rather than relying on best-effort warnings.

| `model` slug | Kind | Manual | Notes |
| --- | --- | --- | --- |
| `ublox-m8` | gnss | u-blox M8/M10/F9/F10 interface descriptions | aliases `ublox-m10`, `ublox-f9`, `ublox-f10`; NMEA + UBX NAV-PVT |
| `septentrio-asterx-u3` | gnss | AsteRx-U3 User Manual + Septentrio Reference Guide / ``pysbf2`` | aliases `septentrio-asterx-m3`, `septentrio-mosaic-x5`, `septentrio-mosaic-h`; NMEA + SBF PVTGeodetic; serial or VISA SOCKET |
| `novatel-oem7` | gnss | `https://docs.novatel.com/OEM7/Content/PDFs/OEM7_Commands_Logs_Manual.pdf` | aliases `novatel-oem7600`, `novatel-pwrpak7`, `novatel-smart7`; NMEA + BESTPOSB; `FRESET COLDSTART` |
| `rohde-smbv100b` | vsg | `https://scdn.rohde-schwarz.com/ur/pws/dl_downloads/pdm/cl_manuals/user_manual/1178_4460_01/SMBV100B_UserManual_en_15.pdf` | ARB play; upload `.bin` / `.mat` / `.iq.tar` (16-bit I/Q) |
| `rohde-fsw` | speca | `https://scdn.rohde-schwarz.com/ur/pws/dl_downloads/pdm/cl_manuals/user_manual/1173_9411_01/FSW_UserManual_en_57.pdf` | Spectrum analyzer SCPI |
| `rohde-fswp` | phasenoiseanalyzer | `https://scdn.rohde-schwarz.com/ur/pws/dl_downloads/pdm/cl_manuals/user_manual/1177_5633_01/FSWP_UserManual_en_17.pdf` | Spot noise `CALC:SNO:*` |
| `controlbyweb-webrelay` | relay | ControlByWeb Integration Manual | `state.xml` HTTP GET |
| `controlbyweb-x410` | relay | ControlByWeb Integration Manual | `state.json` HTTP GET |
| `keysight-edu34450a` | dmm | EDU34450A Programming Guide | DC V/I/R |
| `keysight-esg` | vsg | E4400-90506 | CW measure + arb (E4438C) |
| `keysight-e4407b` | speca | E4407B manual | - |
| `tektronix-rsa5100b` | rtsa | RSA5100B manual | IQ capture |
| `tdk-genesys` | psu | Genesys user guide | OVP/OCP |
| `adaura-r3` | attn | AdauraTech R3 manual | Text `SET` / `STATUS` |
| `itech-it8600` | eload | IT8600 Programming Guide | - |
| `chroma-8600` | eload | 8600 Series Programming Manual | alias `chroma-8601` |
| `agilent-6050` | eload | 06060-90005 | - |
| `keysight-53220a` | freqcounter | 53220A/53230A User's Guide | alias `keysight-53230a` |
| `tektronix-fca3000` | freqcounter | 077-0494-00 | aliases `tektronix-fca3100`, `tektronix-mca3000` |
| `tektronix-mdo4000` | oscope | 077-0510-03 MDO4000 programmer | MDO3000 and MSO/DPO4000 aliases in the catalog |
| `tektronix-t3dso2000` | oscope | T3DSO1000/2000 programming guide | - |
| `tektronix-ttr500` | vna | 077-1257-00 TTR500 programmer | SCPI `SENS<n>:*` |
| `rohde-znb` | vna | R&S ZNB user manual | SCPI `SENS<n>:*` |
| `anritsu-541xx` | vna | 10410-00147 GPIB User's Guide | GPIB mnemonics |
| `keysight-u2001a` | pwrmeter | U2000 programming guide | aliases `keysight-u2000a`, `keysight-u2000` |
| `minicircuits-rc` | rfswitch | `Prog_Manual-2-Switch` | alias `minicircuits-ztrc` |

### Config TOML examples

**GNSS deep API (named-model workflow tier):** `ublox-m10` (NAV-PVT + NAV-DOP;
true HDOP), `novatel-oem7`, and `septentrio-asterx-u3` are the reference
receivers. Continuity evidence: `start_logging(..., key=)` enqueues 1 Hz
`track_epoch` rows (including no-fix), then `stop_logging` writes availability /
outage summaries. Freshness-gated `measure_*` raise `NoFixError` /
`StaleDataError` / `NoStreamError`.

**GNSS config + wire recordings:**

- `load_config` / `save_config` — u-blox accepts u-center GNSS Configuration
  `.txt` (M8 legacy `CFG-*` and F9+/M10 `CFG-VALGET`→`VALSET` on load) or binary
  `.ubx`. NovAtel/Septentrio use ASCII command scripts (best-effort save of the
  streams/logs this driver manages). Call while logging is stopped.
- `set_message_rate(message, rate_hz)` — `CFG-MSG` (u-blox), `LOG`/`UNLOG`
  (NovAtel), `setNMEAOutput`/`setSBFOutput` (Septentrio); `rate_hz=0` disables.
- `start_logging` always writes a **binary wire sidecar**
  (`{stem}_wire.ubx` / `.gps` / `.sbf` / `.bin`) with every serial chunk before
  parse (u-center / Convert / RxTools friendly), plus the decoded text log and
  track CSV.

Indoor-repeater flow:

```python
gnss.save_config(gnss_id=1, path="configs/baseline_m10.txt")  # optional
gnss.load_config(gnss_id=1, path="configs/m10_repeater.txt")
gnss.set_message_rate(gnss_id=1, message="NAV-SAT", rate_hz=1)
gnss.start_logging(gnss_id=1, path="gnss/raw.nmea", key="soak")
# ... soak / measures ...
gnss.stop_logging(gnss_id=1)
# open gnss/raw_wire.ubx in u-center; use track CSV / epochs for verifies
```

**Oscope deep API (named-model workflow tier):** `tektronix-mdo4000` (077-0510-03)
is the documented acquisition workflow: preset → `set_channel_*` →
`set_timebase_*` → `set_trigger_*` → `set_acquire_*` → `acquire` /
`single_acquire` → `measure_*` / `save_waveform` / `save_screenshot` (same
`capture_id`). `measure_*` / `save_*` fetch the last capture and do not re-arm.
Other catalog scopes stay best-effort generic SCPI.

**SCPI status helpers (all VISA kinds):** `col.equipment.scpi.status_byte`,
`esr`, `clear_status`, `drain_error_queue` (``*STB?`` / ``*ESR?`` / ``*CLS`` /
``SYST:ERR?``).

**PSU deep API (named-model workflow tier):** `rigol-dp832` (multi-channel
``channels`` in TOML), `siglent-spd1168x`, and `tdk-genesys` are the reference
drivers for output/protection/sense SCPI; catalog slugs inherit generic commands
with one-time warnings.

**Eload deep API (named-model workflow tier):** `itech-it8600`, `chroma-8600`,
and `agilent-6050` cover CC/CV/CP/CR dialect differences; transient/list and
protection use generic SCPI on other catalog models.

**DMM deep API (named-model workflow tier):** `keysight-edu34450a`,
`keysight-34401a`, and `keithley-dmm6500` are reference measure/configure
drivers; configure→``initiate``→``fetch`` and AC/4W one-shots use generic SCPI
elsewhere.

**VSG waveforms:** `upload_waveform` accepts local `.bin`, `.mat`, or `.iq.tar`
(converted to 16-bit interleaved I/Q); then `play_iq` with the remote filename.

**R&S free-manual reading list** (PDFs on rohde-schwarz.com / scdn): SMBV100B,
FSW, FSWP (implemented); ZNB (existing `rohde-znb`); SMA100B (analog ASG) and
SMW200A (high-end VSG) documented for a later pass.

**u-blox GNSS (USB serial):**

```toml
[equipment.gnss]
gnss_id = 1
port = "COM7"
baudrate = 9600
model = "ublox-f9"
```

**Septentrio AsteRx-U3 (USB/RS-232 serial):**

```toml
[equipment.gnss]
gnss_id = 2
port = "COM5"
baudrate = 19200
model = "septentrio-asterx-u3"
connection = "COM1"
```

`connection` is the RxTools stream descriptor (`COM1`…`COM3`, `USB1`, `IPS1`, …)
passed to `setNMEAOutput` / `setSBFOutput` (default `COM1`). U3 I/O and web UI
streams: AsteRx-U3 User Manual; ASCII enable commands and SBF layout: Reference
Guide / pysbf2 reading list.

**Septentrio AsteRx-U3 (Ethernet TCP data socket via VISA):**

```toml
[equipment.gnss]
gnss_id = 3
resource = "TCPIP0::192.168.3.1::28785::SOCKET"
model = "septentrio-asterx-u3"
connection = "IPS1"
```

Port **28784** is reserved for commands on the U3; use a configured data port
(e.g. IPS1 on 28785, TCP2Way) for NMEA/SBF.

**NovAtel OEM7 (serial):**

```toml
[equipment.gnss]
gnss_id = 4
port = "COM6"
baudrate = 115200
model = "novatel-oem7"
```

**R&S SMBV100B (VISA):**

```toml
[equipment.vsg]
vsg_id = 1
resource = "TCPIP0::192.168.1.50::inst0::INSTR"
model = "rohde-smbv100b"
```

**R&S FSW (VISA):**

```toml
[equipment.speca]
speca_id = 1
resource = "TCPIP0::192.168.1.51::inst0::INSTR"
model = "rohde-fsw"
```

**R&S FSWP phase noise analyzer (VISA):**

```toml
[equipment.phasenoiseanalyzer]
phasenoiseanalyzer_id = 1
resource = "TCPIP0::192.168.1.52::inst0::INSTR"
model = "rohde-fswp"
```

**ControlByWeb X-410 (HTTP):**

```toml
[equipment.relay]
relay_id = 1
resource = "http://192.168.1.2"
model = "controlbyweb-x410"
username = "admin"
password = "webrelay"
```

**Keysight U2001A (USB VISA):**

```toml
[equipment.pwrmeter]
pwrmeter_id = 1
resource = "USB0::0x2A8D::0x2D18::INSTR"
model = "keysight-u2001a"
frequency = 1e9
```

**Mini-Circuits RC switch (Ethernet/TCP VISA or serial):**

```toml
[equipment.rfswitch]
rfswitch_id = 1
resource = "TCPIP0::192.168.100.100::inst0::INSTR"
model = "minicircuits-rc"
path = "A=1;B=0"
```

**Anritsu 541XXA (GPIB):**

```toml
[equipment.vna]
vna_id = 1
resource = "GPIB0::18::INSTR"
model = "anritsu-541xx"
frequency_unit = "GHz"
```

Use `frequency_unit = "MHz"` for 54107A/54109A/54111A per the GPIB guide.

## Catalog models

These slugs come from the programming-manual spreadsheet. A row whose
notes name an existing class is an alias of that driver. Every other
row inherits a generic driver directly or through the family class named
in its notes. Methods without vendor overrides use best-effort generic SCPI
and log one warning per model and command. The class
docstring records the manual link.

| `model` slug | Kind | Manual | Notes |
| --- | --- | --- | --- |
| `rigol-dg1022z` | asg | <https://www.rigolna.com/support/downloads/> | generic SCPI |
| `rigol-dg1032z` | asg | <https://www.rigolna.com/support/downloads/> | generic SCPI |
| `rigol-dg1062z` | asg | <https://www.rigolna.com/support/downloads/> | generic SCPI |
| `rigol-dg4062` | asg | <https://www.rigolna.com/products/waveform-generators/dg4000/> | generic SCPI |
| `rigol-dg4102` | asg | <https://www.rigolna.com/products/waveform-generators/dg4000/> | generic SCPI |
| `rigol-dg4162` | asg | <https://www.rigolna.com/products/waveform-generators/dg4000/> | generic SCPI |
| `rigol-dg4202` | asg | <https://www.rigolna.com/products/waveform-generators/dg4000/> | generic SCPI |
| `rigol-dg811` | asg | <https://www.rigolna.com/support/downloads/> | `RigolDg800` family overrides; other methods best-effort |
| `rigol-dg812` | asg | <https://www.rigolna.com/support/downloads/> | `RigolDg800` family overrides; other methods best-effort |
| `rigol-dg821` | asg | <https://www.rigolna.com/support/downloads/> | `RigolDg800` family overrides; other methods best-effort |
| `rigol-dg822` | asg | <https://www.rigolna.com/support/downloads/> | `RigolDg800` family overrides; other methods best-effort |
| `rigol-dg952` | asg | <https://www.rigolna.com/support/downloads/> | generic SCPI |
| `rigol-dg972` | asg | <https://www.rigolna.com/support/downloads/> | generic SCPI |
| `rigol-dg2000` | asg | <https://www.rigolna.com/support/downloads/> | generic SCPI |
| `rigol-dg5000` | asg | <https://www.rigolna.com/support/downloads/> | generic SCPI |
| `rigol-dg6000` | asg | <https://www.rigolna.com/support/downloads/> | generic SCPI |
| `rigol-dg70000` | asg | <https://www.rigolna.com/support/downloads/> | generic SCPI |
| `siglent-sdg1032x` | asg | <https://siglentna.com/resources/documents/waveform-generators/> | generic SCPI |
| `siglent-sdg1062x` | asg | <https://siglentna.com/resources/documents/waveform-generators/> | generic SCPI |
| `siglent-sdg2042x` | asg | <https://siglentna.com/resources/documents/waveform-generators/> | generic SCPI |
| `siglent-sdg2082x` | asg | <https://siglentna.com/resources/documents/waveform-generators/> | generic SCPI |
| `siglent-sdg2122x` | asg | <https://siglentna.com/resources/documents/waveform-generators/> | generic SCPI |
| `siglent-sdg6052x` | asg | <https://siglentna.com/resources/documents/waveform-generators/> | generic SCPI |
| `siglent-sdg6032x` | asg | <https://siglentna.com/resources/documents/waveform-generators/> | generic SCPI |
| `siglent-sdg3000x` | asg | <https://www.siglent.com/na/service-support/resource-center/?current=siglent-manual-download> | generic SCPI |
| `siglent-sdg7000a` | asg | <https://www.siglent.com/na/service-support/resource-center/?current=siglent-manual-download> | generic SCPI |
| `tektronix-afg31000` | asg | <https://www.tek.com/en/support/datasheets-manuals-software-downloads> | generic SCPI |
| `minicircuits-rudat` | attn | `https://www.minicircuits.com/softwaredownload/Prog_Manual-6-Programmable_Attenuator.pdf` | `:SETATT=` / `:ATT?` dialect |
| `minicircuits-rcdat` | attn | `https://www.minicircuits.com/softwaredownload/Prog_Manual-6-Programmable_Attenuator.pdf` | `:SETATT=` / `:ATT?` dialect |
| `minicircuits-rc4dat` | attn | `https://www.minicircuits.com/softwaredownload/Prog_Manual-6-Programmable_Attenuator.pdf` | `:CHAN:n:SETATT:` / `:ATT?` |
| `minicircuits-rc8dat` | attn | `https://www.minicircuits.com/softwaredownload/Prog_Manual-6-Programmable_Attenuator.pdf` | `:CHAN:n:SETATT:` / `:ATT?` |
| `minicircuits-zvva` | attn | `https://www.minicircuits.com/softwaredownload/Prog_Manual-6-Programmable_Attenuator.pdf` | `:SETATT=` / `:ATT?` dialect |
| `minicircuits-rcm-ztm` | attn | `https://www.minicircuits.com/softwaredownload/Prog_Manual-Modular_ZTM_RCM.pdf` | generic SCPI |
| `vaunix-lda-302p-1` | attn | <https://vaunix.com/digital-attenuators/> | SDK/DLL only (ops refused) |
| `vaunix-lda-302p-h` | attn | <https://vaunix.com/digital-attenuators/> | SDK/DLL only (ops refused) |
| `vaunix-lda` | attn | <https://vaunix.com/digital-attenuators/> | SDK/DLL only (ops refused) |
| `rigol-dm3058` | dmm | <https://www.rigolna.com/support/downloads/> | generic SCPI |
| `rigol-dm3068` | dmm | <https://www.rigolna.com/support/downloads/> | generic SCPI |
| `rigol-dm858` | dmm | <https://www.rigolna.com/support/downloads/> | generic SCPI |
| `siglent-sdm3045x` | dmm | <https://www.siglent.com/na/service-support/resource-center/?current=siglent-manual-download> | generic SCPI |
| `siglent-sdm3055` | dmm | <https://www.siglent.com/na/service-support/resource-center/?current=siglent-manual-download> | generic SCPI |
| `siglent-sdm3065x` | dmm | <https://www.siglent.com/na/service-support/resource-center/?current=siglent-manual-download> | generic SCPI |
| `keysight-34401a` | dmm | <https://www.keysight.com/us/en/assets/9018-01063/user-manuals/9018-01063.pdf> | `Keysight34401A` family overrides; other methods best-effort |
| `keysight-34460a` | dmm | <https://www.keysight.com/ie/en/support/34465A/digital-multimeter-6-5-digit-truevolt-dmm.html> | generic SCPI |
| `keysight-34461a` | dmm | <https://www.keysight.com/ie/en/support/34465A/digital-multimeter-6-5-digit-truevolt-dmm.html> | generic SCPI |
| `keysight-34465a` | dmm | <https://www.keysight.com/ie/en/support/34465A/digital-multimeter-6-5-digit-truevolt-dmm.html> | generic SCPI |
| `keysight-34470a` | dmm | <https://www.keysight.com/ie/en/support/34465A/digital-multimeter-6-5-digit-truevolt-dmm.html> | generic SCPI |
| `keithley-dmm6500` | dmm | <https://www.tek.com/en/support/datasheets-manuals-software-downloads> | `KeithleyDmm6500Family` family overrides; other methods best-effort |
| `keithley-dmm7510` | dmm | <https://www.tek.com/en/support/datasheets-manuals-software-downloads> | generic SCPI |
| `rigol-dl3021` | eload | <https://www.rigolna.com/europe/products/dc-load/DL3000.html> | generic SCPI |
| `rigol-dl3021a` | eload | <https://www.rigolna.com/europe/products/dc-load/DL3000.html> | generic SCPI |
| `rigol-dl3031` | eload | <https://www.rigolna.com/europe/products/dc-load/DL3000.html> | generic SCPI |
| `rigol-dl3031a` | eload | <https://www.rigolna.com/europe/products/dc-load/DL3000.html> | generic SCPI |
| `siglent-sdl1020x` | eload | <https://www.siglent.com/na/service-support/resource-center/?current=siglent-manual-download> | generic SCPI |
| `siglent-sdl1020x-e` | eload | <https://www.siglent.com/na/service-support/resource-center/?current=siglent-manual-download> | generic SCPI |
| `siglent-sdl1030x` | eload | <https://www.siglent.com/na/service-support/resource-center/?current=siglent-manual-download> | generic SCPI |
| `siglent-sdl1030x-e` | eload | <https://www.siglent.com/na/service-support/resource-center/?current=siglent-manual-download> | generic SCPI |
| `bk-8500` | eload | <https://www.bkprecision.com/> | generic SCPI |
| `bk-8600` | eload | <https://www.bkprecision.com/> | generic SCPI |
| `tektronix-fca3000` | freqcounter | <https://www.tek.com/en/frequency-counter/mca3000-manual/fca3000-and-fca3100-series-mca3000-series> | existing driver |
| `tektronix-fca3003` | freqcounter | <https://www.tek.com/en/frequency-counter/mca3000-manual/fca3000-and-fca3100-series-mca3000-series> | alias of `tektronix-fca3000` |
| `tektronix-fca3020` | freqcounter | <https://www.tek.com/en/frequency-counter/mca3000-manual/fca3000-and-fca3100-series-mca3000-series> | alias of `tektronix-fca3000` |
| `tektronix-fca3100` | freqcounter | <https://www.tek.com/en/frequency-counter/mca3000-manual/fca3000-and-fca3100-series-mca3000-series> | existing driver |
| `tektronix-fca3103` | freqcounter | <https://www.tek.com/en/frequency-counter/mca3000-manual/fca3000-and-fca3100-series-mca3000-series> | alias of `tektronix-fca3000` |
| `tektronix-fca3120` | freqcounter | <https://www.tek.com/en/frequency-counter/mca3000-manual/fca3000-and-fca3100-series-mca3000-series> | alias of `tektronix-fca3000` |
| `tektronix-mca3027` | freqcounter | <https://www.tek.com/en/frequency-counter/mca3000-manual/fca3000-and-fca3100-series-mca3000-series> | alias of `tektronix-fca3000` |
| `tektronix-mca3040` | freqcounter | <https://www.tek.com/en/frequency-counter/mca3000-manual/fca3000-and-fca3100-series-mca3000-series> | alias of `tektronix-fca3000` |
| `rigol-ds1054z` | oscope | <https://www.rigolna.com/support/downloads/> | generic SCPI |
| `rigol-ds1074z` | oscope | <https://www.rigolna.com/support/downloads/> | generic SCPI |
| `rigol-ds1104z` | oscope | <https://www.rigolna.com/support/downloads/> | generic SCPI |
| `rigol-mso1074z` | oscope | <https://www.rigolna.com/support/downloads/> | generic SCPI |
| `rigol-mso1104z` | oscope | <https://www.rigolna.com/support/downloads/> | generic SCPI |
| `rigol-dho802` | oscope | <https://www.rigolna.com/support/downloads/> | generic SCPI |
| `rigol-dho804` | oscope | <https://www.rigolna.com/support/downloads/> | generic SCPI |
| `rigol-dho914` | oscope | <https://www.rigolna.com/support/downloads/> | generic SCPI |
| `rigol-dho924` | oscope | <https://www.rigolna.com/support/downloads/> | generic SCPI |
| `rigol-dho1074` | oscope | <https://www.rigolna.com/support/downloads/> | generic SCPI |
| `rigol-dho1104` | oscope | <https://www.rigolna.com/support/downloads/> | generic SCPI |
| `rigol-ds2000a` | oscope | <https://www.rigolna.com/support/downloads/> | generic SCPI |
| `rigol-ds4000` | oscope | <https://www.rigolna.com/support/downloads/> | generic SCPI |
| `rigol-mso5000` | oscope | <https://www.rigolna.com/support/downloads/> | generic SCPI |
| `rigol-mso8000` | oscope | <https://www.rigolna.com/support/downloads/> | generic SCPI |
| `rigol-ds70000` | oscope | <https://www.rigolna.com/support/downloads/> | generic SCPI |
| `siglent-sds1102x-e` | oscope | <https://siglentna.com/resources/documents/digital-oscilloscopes/> | generic SCPI |
| `siglent-sds1104x-e` | oscope | <https://siglentna.com/resources/documents/digital-oscilloscopes/> | generic SCPI |
| `siglent-sds1202x-e` | oscope | <https://siglentna.com/resources/documents/digital-oscilloscopes/> | generic SCPI |
| `siglent-sds1204x-e` | oscope | <https://siglentna.com/resources/documents/digital-oscilloscopes/> | generic SCPI |
| `siglent-sds2000x-plus` | oscope | <https://www.siglent.com/na/service-support/resource-center/?current=siglent-manual-download> | generic SCPI |
| `siglent-sds5000x` | oscope | <https://www.siglent.com/na/service-support/resource-center/?current=siglent-manual-download> | generic SCPI |
| `siglent-sds6000a` | oscope | <https://www.siglent.com/na/service-support/resource-center/?current=siglent-manual-download> | generic SCPI |
| `siglent-sds7000a` | oscope | <https://www.siglent.com/na/service-support/resource-center/?current=siglent-manual-download> | generic SCPI |
| `siglent-sds800x-hd` | oscope | <https://www.siglent.com/na/service-support/resource-center/?current=siglent-manual-download> | generic SCPI |
| `tektronix-mdo3012` | oscope | <https://www.tek.com/en/oscilloscope/mso4000-dpo4000-manual/mdo4000c-mdo4000b-mdo4000-mso4000b-dpo4000b-and-mdo3000-0> | alias of `tektronix-mdo4000` |
| `tektronix-mdo3014` | oscope | <https://www.tek.com/en/oscilloscope/mso4000-dpo4000-manual/mdo4000c-mdo4000b-mdo4000-mso4000b-dpo4000b-and-mdo3000-0> | alias of `tektronix-mdo4000` |
| `tektronix-mdo3022` | oscope | <https://www.tek.com/en/oscilloscope/mso4000-dpo4000-manual/mdo4000c-mdo4000b-mdo4000-mso4000b-dpo4000b-and-mdo3000-0> | alias of `tektronix-mdo4000` |
| `tektronix-mdo3024` | oscope | <https://www.tek.com/en/oscilloscope/mso4000-dpo4000-manual/mdo4000c-mdo4000b-mdo4000-mso4000b-dpo4000b-and-mdo3000-0> | alias of `tektronix-mdo4000` |
| `tektronix-mdo3032` | oscope | <https://www.tek.com/en/oscilloscope/mso4000-dpo4000-manual/mdo4000c-mdo4000b-mdo4000-mso4000b-dpo4000b-and-mdo3000-0> | alias of `tektronix-mdo4000` |
| `tektronix-mdo3034` | oscope | <https://www.tek.com/en/oscilloscope/mso4000-dpo4000-manual/mdo4000c-mdo4000b-mdo4000-mso4000b-dpo4000b-and-mdo3000-0> | alias of `tektronix-mdo4000` |
| `tektronix-mdo3052` | oscope | <https://www.tek.com/en/oscilloscope/mso4000-dpo4000-manual/mdo4000c-mdo4000b-mdo4000-mso4000b-dpo4000b-and-mdo3000-0> | alias of `tektronix-mdo4000` |
| `tektronix-mdo3054` | oscope | <https://www.tek.com/en/oscilloscope/mso4000-dpo4000-manual/mdo4000c-mdo4000b-mdo4000-mso4000b-dpo4000b-and-mdo3000-0> | alias of `tektronix-mdo4000` |
| `tektronix-mdo3102` | oscope | <https://www.tek.com/en/oscilloscope/mso4000-dpo4000-manual/mdo4000c-mdo4000b-mdo4000-mso4000b-dpo4000b-and-mdo3000-0> | alias of `tektronix-mdo4000` |
| `tektronix-mdo3104` | oscope | <https://www.tek.com/en/oscilloscope/mso4000-dpo4000-manual/mdo4000c-mdo4000b-mdo4000-mso4000b-dpo4000b-and-mdo3000-0> | alias of `tektronix-mdo4000` |
| `tektronix-mso4104b` | oscope | <https://www.tek.com/en/oscilloscope/mso4000-dpo4000-manual/mdo4000c-mdo4000b-mdo4000-mso4000b-dpo4000b-and-mdo3000-0> | alias of `tektronix-mdo4000` |
| `tektronix-mso4054b` | oscope | <https://www.tek.com/en/oscilloscope/mso4000-dpo4000-manual/mdo4000c-mdo4000b-mdo4000-mso4000b-dpo4000b-and-mdo3000-0> | alias of `tektronix-mdo4000` |
| `tektronix-dpo4034b` | oscope | <https://www.tek.com/en/oscilloscope/mso4000-dpo4000-manual/mdo4000c-mdo4000b-mdo4000-mso4000b-dpo4000b-and-mdo3000-0> | alias of `tektronix-mdo4000` |
| `tektronix-dpo4104b` | oscope | <https://www.tek.com/en/oscilloscope/mso4000-dpo4000-manual/mdo4000c-mdo4000b-mdo4000-mso4000b-dpo4000b-and-mdo3000-0> | alias of `tektronix-mdo4000` |
| `tektronix-mdo4104c` | oscope | <https://www.tek.com/en/oscilloscope/mso4000-dpo4000-manual/mdo4000c-mdo4000b-mdo4000-mso4000b-dpo4000b-and-mdo3000-0> | alias of `tektronix-mdo4000` |
| `rigol-dp811` | psu | <https://www.rigolna.com/products/dc-power-loads/dp800/> | `RigolDp800` family overrides; other methods best-effort |
| `rigol-dp813` | psu | <https://www.rigolna.com/products/dc-power-loads/dp800/> | `RigolDp800` family overrides; other methods best-effort |
| `rigol-dp821` | psu | <https://www.rigolna.com/products/dc-power-loads/dp800/> | `RigolDp800` family overrides; other methods best-effort |
| `rigol-dp821a` | psu | <https://www.rigolna.com/products/dc-power-loads/dp800/> | `RigolDp800` family overrides; other methods best-effort |
| `rigol-dp822` | psu | <https://www.rigolna.com/products/dc-power-loads/dp800/> | `RigolDp800` family overrides; other methods best-effort |
| `rigol-dp831` | psu | <https://www.rigolna.com/products/dc-power-loads/dp800/> | `RigolDp800` family overrides; other methods best-effort |
| `rigol-dp832` | psu | <https://www.rigolna.com/products/dc-power-loads/dp800/> | `RigolDp800` family overrides; other methods best-effort |
| `rigol-dp832a` | psu | <https://www.rigolna.com/products/dc-power-loads/dp800/> | `RigolDp800` family overrides; other methods best-effort |
| `rigol-dp711` | psu | <https://www.rigolna.com/support/downloads/> | generic SCPI |
| `rigol-dp712` | psu | <https://www.rigolna.com/support/downloads/> | generic SCPI |
| `rigol-dp932u` | psu | <https://www.rigolna.com/support/downloads/> | generic SCPI |
| `rigol-dp932a` | psu | <https://www.rigolna.com/support/downloads/> | generic SCPI |
| `rigol-dp2000` | psu | <https://www.rigolna.com/support/downloads/> | generic SCPI |
| `rigol-dp1116a` | psu | <https://www.rigolna.com/support/downloads/> | generic SCPI |
| `siglent-spd3303x` | psu | <https://www.siglent.com/na/service-support/resource-center/?current=siglent-manual-download> | generic SCPI |
| `siglent-spd3303x-e` | psu | <https://www.siglent.com/na/service-support/resource-center/?current=siglent-manual-download> | generic SCPI |
| `siglent-spd3303c` | psu | <https://www.siglent.com/na/service-support/resource-center/?current=siglent-manual-download> | generic SCPI |
| `siglent-spd1168x` | psu | <https://www.siglent.com/na/service-support/resource-center/?current=siglent-manual-download> | `SiglentSpdSingle` family overrides; other methods best-effort |
| `siglent-spd1305x` | psu | <https://www.siglent.com/na/service-support/resource-center/?current=siglent-manual-download> | `SiglentSpdSingle` family overrides; other methods best-effort |
| `keysight-n6705c` | psu | <https://www.keysight.com/us/en/assets/9018-04227/service-manuals/9018-04227.pdf> | generic SCPI |
| `keysight-e4418b` | pwrmeter | <https://www.keysight.com/us/en/assets/9018-01176/programming-guides/9018-01176.pdf> | generic SCPI |
| `keysight-e4419b` | pwrmeter | <https://www.keysight.com/us/en/assets/9018-01176/programming-guides/9018-01176.pdf> | generic SCPI |
| `keysight-n1913a` | pwrmeter | <https://www.keysight.com/be/en/support/N1913A/epm-series-single-channel-power-meter.html> | generic SCPI |
| `keysight-n1914a` | pwrmeter | <https://www.keysight.com/be/en/support/N1913A/epm-series-single-channel-power-meter.html> | generic SCPI |
| `keysight-u2000a` | pwrmeter | <https://www.keysight.com/zz/en/assets/9018-01701/programming-guides/9018-01701.pdf> | existing driver |
| `keysight-u2001a` | pwrmeter | <https://www.keysight.com/zz/en/assets/9018-01701/programming-guides/9018-01701.pdf> | existing driver |
| `keysight-u2002a` | pwrmeter | <https://www.keysight.com/zz/en/assets/9018-01701/programming-guides/9018-01701.pdf> | alias of `keysight-u2001a` |
| `keysight-u2004a` | pwrmeter | <https://www.keysight.com/zz/en/assets/9018-01701/programming-guides/9018-01701.pdf> | alias of `keysight-u2001a` |
| `minicircuits-rc` | rfswitch | `https://www.minicircuits.com/softwaredownload/Prog_Manual-2-Switch.pdf` | existing driver |
| `minicircuits-ztrc` | rfswitch | `https://www.minicircuits.com/softwaredownload/Prog_Manual-2-Switch.pdf` | existing driver |
| `minicircuits-usb-switch` | rfswitch | <https://www.minicircuits.com/softwaredownload/Prog_Manual-2-Switch.pdf> | `SETA=` / `SWPORT?` (RC dialect) |
| `minicircuits-u2c` | rfswitch | <https://www.minicircuits.com/softwaredownload/Prog_Manual-2-Switch.pdf> | `SETA=` / `SWPORT?` (RC dialect) |
| `minicircuits-rcs` | rfswitch | <https://www.minicircuits.com/softwaredownload/Prog_Manual-2-Switch.pdf> | `SETA=` / `SWPORT?` (RC dialect) |
| `minicircuits-esb` | rfswitch | <https://www.minicircuits.com/softwaredownload/Prog_Manual-2-Switch.pdf> | `SETA=` / `SWPORT?` (RC dialect) |
| `minicircuits-ztvx` | rfswitch | <https://www.minicircuits.com/softwaredownload/Prog_Manual-ZT-Custom.pdf> | PATH dialect refused until implemented |
| `vaunix-lsw-802pdt` | rfswitch | <https://vaunix.com/support/> | SDK/DLL only (ops refused) |
| `vaunix-lsw-203pdt` | rfswitch | <https://vaunix.com/support/> | SDK/DLL only (ops refused) |
| `rigol-rsa3030` | rtsa | <https://www.rigolna.com/support/downloads/> | generic SCPI |
| `rigol-rsa3045` | rtsa | <https://www.rigolna.com/support/downloads/> | generic SCPI |
| `rigol-rsa3065` | rtsa | <https://www.rigolna.com/support/downloads/> | generic SCPI |
| `rigol-rsa5032` | rtsa | <https://www.rigolna.com/support/downloads/> | generic SCPI |
| `rigol-rsa5065` | rtsa | <https://www.rigolna.com/support/downloads/> | generic SCPI |
| `rigol-rsa800` | rtsa | <https://www.rigolna.com/support/downloads/> | generic SCPI |
| `rigol-rsa6000` | rtsa | <https://www.rigolna.com/support/downloads/> | generic SCPI |
| `siglent-ssa3032x-r` | rtsa | <https://siglentna.com/resources/documents/spectrum-analyzers/> | generic SCPI |
| `siglent-ssa3075x-r` | rtsa | <https://siglentna.com/resources/documents/spectrum-analyzers/> | generic SCPI |
| `tektronix-rsa306` | rtsa | <https://www.tek.com/en/manual/spectrum-analyzer/rsa306-rsa306b-and-rsa500a600a-programmer-manual-rsa306> | generic SCPI |
| `tektronix-rsa306b` | rtsa | <https://www.tek.com/en/manual/spectrum-analyzer/rsa306-rsa306b-and-rsa500a600a-programmer-manual-rsa306> | generic SCPI |
| `tektronix-rsa503a` | rtsa | <https://www.tek.com/en/manual/spectrum-analyzer/rsa306-rsa306b-and-rsa500a600a-programmer-manual-rsa306> | generic SCPI |
| `tektronix-rsa507a` | rtsa | <https://www.tek.com/en/manual/spectrum-analyzer/rsa306-rsa306b-and-rsa500a600a-programmer-manual-rsa306> | generic SCPI |
| `tektronix-rsa603a` | rtsa | <https://www.tek.com/en/manual/spectrum-analyzer/rsa306-rsa306b-and-rsa500a600a-programmer-manual-rsa306> | generic SCPI |
| `tektronix-rsa607a` | rtsa | <https://www.tek.com/en/manual/spectrum-analyzer/rsa306-rsa306b-and-rsa500a600a-programmer-manual-rsa306> | generic SCPI |
| `rigol-dsa815` | speca | <https://www.rigolna.com/support/downloads/> | generic SCPI |
| `rigol-dsa815-tg` | speca | <https://www.rigolna.com/support/downloads/> | generic SCPI |
| `rigol-dsa832` | speca | <https://www.rigolna.com/support/downloads/> | generic SCPI |
| `rigol-dsa875` | speca | <https://www.rigolna.com/support/downloads/> | generic SCPI |
| `rigol-dsa800e` | speca | <https://www.rigolna.com/support/downloads/> | generic SCPI |
| `rigol-dsa1000` | speca | <https://www.rigolna.com/support/downloads/> | generic SCPI |
| `rigol-rsa3030` | speca | <https://www.rigolna.com/support/downloads/> | generic SCPI |
| `rigol-rsa3045` | speca | <https://www.rigolna.com/support/downloads/> | generic SCPI |
| `rigol-rsa5065` | speca | <https://www.rigolna.com/support/downloads/> | generic SCPI |
| `siglent-ssa3021x` | speca | <https://siglentna.com/resources/documents/spectrum-analyzers/> | generic SCPI |
| `siglent-ssa3032x` | speca | <https://siglentna.com/resources/documents/spectrum-analyzers/> | generic SCPI |
| `siglent-ssa3021x-plus` | speca | <https://siglentna.com/resources/documents/spectrum-analyzers/> | generic SCPI |
| `siglent-ssa3032x-plus` | speca | <https://siglentna.com/resources/documents/spectrum-analyzers/> | generic SCPI |
| `siglent-ssa3075x-plus` | speca | <https://siglentna.com/resources/documents/spectrum-analyzers/> | generic SCPI |
| `siglent-ssa5000a` | speca | <https://siglentna.com/resources/documents/spectrum-analyzers/> | generic SCPI |
| `siglent-sna5000a` | vna | `https://siglentna.com/wp-content/uploads/dlm_uploads/2022/11/SNA5000A_ProgrammingGuide_PG09050_E03.pdf` | generic SCPI |
| `siglent-sna6000a` | vna | <https://www.siglent.com/na/service-support/resource-center/?current=siglent-manual-download> | generic SCPI |
| `siglent-sva1000x` | vna | <https://www.siglent.com/na/service-support/resource-center/?current=siglent-manual-download> | generic SCPI |
| `keysight-e5071c` | vna | `https://helpfiles.keysight.com/csg/e5071c/using_this_help.htm` | generic SCPI |
| `rigol-dna6000` | vna | <https://www.rigolna.com/support/downloads/> | generic SCPI |
| `rigol-dna6000-r` | vna | <https://www.rigolna.com/support/downloads/> | generic SCPI |
| `rigol-dsg3030` | vsg | <https://www.rigolna.com/support/downloads/> | generic SCPI |
| `rigol-dsg3060` | vsg | <https://www.rigolna.com/support/downloads/> | generic SCPI |
| `rigol-dsg3060b` | vsg | <https://www.rigolna.com/support/downloads/> | generic SCPI |
| `rigol-dsg3136b` | vsg | <https://www.rigolna.com/support/downloads/> | generic SCPI |
| `rigol-dsg800` | vsg | <https://www.rigolna.com/support/downloads/> | generic SCPI |
| `rigol-dsg5000` | vsg | <https://www.rigolna.com/support/downloads/> | generic SCPI |
| `siglent-ssg3000x` | vsg | <https://www.siglent.com/na/service-support/resource-center/?current=siglent-manual-download> | generic SCPI |
| `siglent-ssg5000x` | vsg | <https://www.siglent.com/na/service-support/resource-center/?current=siglent-manual-download> | generic SCPI |
| `siglent-ssg6000a` | vsg | <https://www.siglent.com/na/service-support/resource-center/?current=siglent-manual-download> | generic SCPI |
| `keysight-n5166b` | vsg | <https://www.keysight.com/vn/en/support/N5182B/mxg-x-series-rf-vector-signal-generator-9-khz-6-ghz.html> | generic SCPI |
| `keysight-n5171b` | vsg | <https://www.keysight.com/vn/en/support/N5182B/mxg-x-series-rf-vector-signal-generator-9-khz-6-ghz.html> | generic SCPI |
| `keysight-n5172b` | vsg | <https://www.keysight.com/vn/en/support/N5182B/mxg-x-series-rf-vector-signal-generator-9-khz-6-ghz.html> | generic SCPI |
| `keysight-n5181b` | vsg | <https://www.keysight.com/vn/en/support/N5182B/mxg-x-series-rf-vector-signal-generator-9-khz-6-ghz.html> | generic SCPI |
| `keysight-n5182b` | vsg | <https://www.keysight.com/vn/en/support/N5182B/mxg-x-series-rf-vector-signal-generator-9-khz-6-ghz.html> | generic SCPI |

## Implemented IO drivers

| `driver` slug | Kind | Dependency | Notes |
| --- | --- | --- | --- |
| `sim` | dio, i2c, spi | (core) | In-memory adapters for CI/offline |
| `ftdi-ft232h` | dio | pyftdi (installed by default) | FT232H GPIO adapter |
| `ni-6501` | dio | NI-DAQmx runtime (ctypes) | USB-6501; 24 lines P0..P2; `resource` = DAQmx name |
| `ni-845x` | dio, i2c, spi | NI-845x runtime (ctypes) | USB-8451/8452; require `model`; shared device voltage |

### IO config TOML examples

**Simulated DIO:**

```toml
[io.dio]
dio_id = 1
driver = "sim"
port_lines = 8
direction = 0xFF
```

**FT232H GPIO:**

```toml
[io.dio]
dio_id = 1
driver = "ftdi-ft232h"
resource = "ftdi://ftdi:232h/1"
port_lines = 8
direction = 0x0F
```

**NI USB-6501:**

```toml
[io.dio]
dio_id = 1
driver = "ni-6501"
resource = "Dev1"
port_lines = 24
direction = 0x0000FF
drive = "open-drain"
```

**NI USB-8452 (DIO + I2C + SPI):**

```toml
[io.dio]
dio_id = 1
driver = "ni-845x"
resource = "USB-8452"
model = "usb-8452"
port_lines = 8
direction = 0x0F
voltage = 3.3

[io.i2c]
i2c_id = 1
driver = "ni-845x"
resource = "USB-8452"
model = "usb-8452"
voltage = 3.3
clock_hz = 100000
address = 0x50

[io.spi]
spi_id = 1
driver = "ni-845x"
resource = "USB-8452"
model = "usb-8452"
voltage = 3.3
clock_hz = 1000000
mode = 0
chip_select = 0
```
