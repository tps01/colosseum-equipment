# Equipment JTAG

## Vivado on the test bench

Colosseum Equipment runs each operation in a bounded Vivado batch process on
Windows or Linux. Install Vivado and the cable drivers on the test bench.
Vivado 2025.2 is the initial command reference.

```toml
[equipment.jtag]
jtag_id = 1
driver = "vivado"
# vivado_path = "C:/AMD tools/Vivado/2025.2"
# hw_server_path = "C:/AMD tools/Vivado/2025.2/bin/hw_server.bat"
# hw_server_url = "lab-server.example:3121"
# xvc_url = "xvc-board.example:2542"
# xvc_programming = true
# target = "FILL_IN_HERE"
# device = "FILL_IN_HERE"
# clock_hz = 1000000
# timeout_s = 300
```

Explicit launcher paths or roots take precedence over XILINX_VIVADO and PATH.
An explicit hardware-server endpoint is externally managed. Otherwise the run
tries to reuse the local server on port 3121 and starts a private loopback
server if needed. Equipment shuts down owned servers at run end. The
hardware-server host must be able to reach the XVC endpoint. Use
xvc_programming only with an endpoint qualified for programming, such as an
external XVC-to-JTAG bridge. Debug Bridge IP supports debug access.

| API | Purpose |
| --- | --- |
| list_targets, list_devices | Discover exact selectors, ordered devices and IDCODEs |
| get_clock, set_clock | Read or apply the Vivado-reported clock rate in Hz for one job |
| scan | Perform chain-wide TAP transitions and IR/DR shifts in one job |
| program_device | Load an FPGA/Zynq .bit or a Versal .pdi |
| list_cfgmem_parts | List Vivado flash part names |
| program_cfgmem, verify_cfgmem | Program and verify an explicit flash part, or verify only |
| boot_from_cfgmem | FPGA soft boot, or board reset with independent boot evidence |
| run_tcl | Run a trusted local Tcl file or inline Tcl with arguments |

All operations take jtag_id and key. Operation overrides include hw_server_url,
xvc_url, target, device, clock_hz and timeout_s. Keep clock_hz in bench config or
pass it to each operation that needs it. The reported clock is the tool's
setting. Chain scans take ordered dictionaries with either state (RESET, IDLE,
IRPAUSE, DRPAUSE) or register (IR or DR), bits and tdi (hex). Supply full chain
vectors and compare the returned scans in the test.

Flash images are prebuilt and matched to the board. Supply .mcs or .bin for
standard FPGA or Zynq flash, and fsbl as an .elf for Zynq when the board's
Vivado workflow requires it. For Versal supply a boot .pdi and
initialization_pdi. A Versal release/device combination must expose an
unambiguous initialization-PDI property. If the tool cannot identify it,
the operation stops before flash programming. Verify-only can temporarily
load a helper into the device even though it leaves flash unchanged.
Binary images use the Vivado default offset. Set boot straps appropriately.
Direct Versal programming checks DONE on the companion `arm_dap` immediately
after the selected device in the chain and reports an error if its status
cannot be confirmed.
For SoCs, supply bounded reset() and check_boot() callbacks. The latter returns
True when board evidence identifies the expected image. A positive check
counts only if it returns before the boot deadline.

Dry runs skip vendor programs. With artifacts enabled, each job retains a log
under jtag/. The operations were exercised with offline fixtures. Match Vivado
and hardware-server releases and qualify flash, boot, cable and JTAG clock
behavior on your board before relying on the results.

- [Vivado Tcl target commands](https://docs.amd.com/r/2025.2-English/ug835-vivado-tcl-commands/open_hw_target)
- [FPGA and MPSoC memory workflows](https://docs.amd.com/r/2023.1-English/ug908-vivado-programming-debugging/Configuration-and-Boot-Memory-Verify-and-Readback-for-FPGAs-or-MPSoCs)
- [Versal configuration memory](https://docs.amd.com/r/2025.2-English/ug908-vivado-programming-debugging/Programming-a-Configuration-Memory-Device-Versal-Devices)

## Quartus on the test bench

The Quartus backend uses one operator-installed Quartus toolchain per bench.
Use Quartus Prime Pro for Agilex 7 and Quartus Prime Standard for Cyclone V.
Altera offers a free stand-alone Programmer. Discovery and programming use
`jtagconfig` and `quartus_pgm`. Device scans and custom Tcl also require an
installation with `quartus_stp`. Resolve the installation via `quartus_path`,
then `QUARTUS_ROOTDIR`, then the installation containing `jtagconfig` on PATH.

```toml
[equipment.jtag]
jtag_id = 1
driver = "quartus"
quartus_path = "C:/tools/Quartus/25.3"
# target = "EXACT CABLE NAME FROM list_targets"
# device = "@2"
# jtag_server = "lab-server.example"
# jtag_server_password_env = "BENCH_JTAG_PASSWORD"
# clock_hz = 6000000
# ir_bits = 10
# cfgmem_parts = ["PART_FROM_FIXTURE_DOCUMENTATION"]
```

Windows and Linux use Quartus's normal JTAG service lifecycle. For remote
access, the server must already be running and configured to accept connections.
Run `col.equipment.jtag.register_server(jtag_id=1, key="register")` explicitly
to add it to the local Quartus client. Supply the password in the named
environment variable. The vendor CLI receives it in process arguments, which
local process observers may be able to read. Colosseum keeps it out of recorded
arguments, logs, artifacts, and exceptions. The native registration persists
after the run. Use Quartus Hardware Setup to remove it. Then use `list_targets`
and select the exact remote cable name before accessing a device.

`set_clock` changes a cable-wide setting. A clock override on a hardware
operation is restored when the operation finishes, including on timeout.
Reserve the cable for the bench when testing at alternate TCK rates.
`scan(scope="device")` supports IR and DR shifts and IDLE. Use the selected
device's documented IR width for `ir_bits`. `run_tcl` scripts receive
`jtag_target`, `jtag_device` (empty if omitted), and `argv`.

Use a prebuilt SOF for direct programming and a prebuilt active-serial JIC for
flash program/verify. Identify the board's expected flash part with `flash_part`.
`list_cfgmem_parts` lists the names declared in the bench's `cfgmem_parts` and
reports `parts_source="bench"`. Quartus reports the expected name with
`flash_part_source="bench"` and `flash_part_verified=false`. The programmer's
`flash_verified` result applies to the JIC contents. Verify-only can temporarily configure the FPGA
with a flash helper. For boot, set the board to its intended flash boot mode
and supply bounded `reset` and `check_boot` callbacks.

### Hardware qualification

The Quartus command flow has offline fixture coverage. Live qualification is
pending for Agilex 7 QSPI with Quartus Pro 25.3.1 and Cyclone V QSPI with
Quartus Standard 25.1std. Record OS, Quartus release, cable, board revision, flash part, and
image identity during qualification. On each board, enumerate the chain,
program a SOF, program/verify the JIC, check verify-only with matching and
mismatching JICs, and boot by confirming an image-specific marker after reset.
Check remote registration and cable resolution on at least one bench.

- [Altera Programmer scripting](https://docs.altera.com/r/docs/683039/25.1.1/quartus-prime-pro-edition-user-guide/scripting-support)
- [Altera JTAG server commands](https://docs.altera.com/r/docs/683525/21.3/nios-ii-software-developer-handbook/jtagconfig)
- [Free stand-alone Programmer](https://docs.altera.com/r/docs/683039/25.1.1/quartus-prime-pro-edition-user-guide/stand-alone-programmer-and-tools)
