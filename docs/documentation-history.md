# Historical feature notes

These notes preserve the previous overview's release context. For current usage,
start with the getting-started and instrument workflow guides.

Version 0.7.1 selects the Genesys serial family from a bare `IDN?` on `COM` and
`ASRL` ports, and adds SCPI drivers for the BK Precision 9115 and Keithley 2260B
supplies.

Version 0.7.0 opens instrument resources through pyVISA, including `COM` ports
as `ASRL`. When `model` is omitted, `*IDN?` selects a known driver or the
generic one for that equipment kind. Genesys LAN and IEEE supplies use
`OUTP:STAT`.

Version 0.6.0 adds USB2ANY and Aardvark I2C/SPI masters, Cheetah SPI, and
Beagle I2C/SPI, USB 12, and USB 480 capture through `col.io.analyzer`.
Vendor runtimes are installed separately and are not distributed in the wheel.
See the [adapter guide](https://tps01.github.io/colosseum-equipment/guides/io_digital.html) for setup,
capture limits, and hardware qualification requirements.

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
