Digital I/O and protocol adapters (``col.io``)
==============================================

Colosseum exposes bench digital I/O through ``col.io.dio``, and I2C/SPI masters
through ``col.io.i2c`` and ``col.io.spi``. Use ``driver = sim`` for offline runs
and CI. Live USB adapters use vendor runtimes loaded via ctypes (not pip packages):

* ``ftdi-ft232h`` — FT232H GPIO (pyftdi)
* ``ni-6501`` — NI USB-6501 static DIO (NI-DAQmx: ``nicaiu.dll`` / ``libnidaqmx.so``)
* ``ni-845x`` — NI USB-8451/8452 DIO, I2C, and SPI (NI-845x: ``Ni845x.dll`` / ``libni845x.so``)

Configuration
-------------

Example simulated DIO for smoke tests::

   [io.dio]
   dio_id = 1
   driver = sim
   port_lines = 8
   direction = 0xFF

Example FT232H on a lab bench::

   [io.dio]
   dio_id = 1
   driver = ftdi-ft232h
   resource = ftdi://ftdi:232h/1
   port_lines = 8
   direction = 0x0F

``port_lines`` is ``8`` for ADBUS (default) or ``16`` for ADBUS+ACBUS. ``direction`` is a bitmask where ``1`` means output and ``0`` means input.

NI USB-6501 (24 static lines)::

   [io.dio]
   dio_id = 1
   driver = ni-6501
   resource = Dev1
   port_lines = 24
   direction = 0x0000FF
   drive = open-drain

Lines map as ``P0.0..P2.7`` → ``0..23``. ``drive`` is ``open-drain`` (default,
onboard 4.7 kΩ to USB 5 V) or ``push-pull`` (active drive; keep total source
current within the device limit). ``set_pull`` is refused: the pull-up is fixed
hardware. Optional ``library`` overrides the DAQmx shared-library path.

NI USB-8452 DIO (8 lines on port 0)::

   [io.dio]
   dio_id = 2
   driver = ni-845x
   resource = USB-8452
   model = usb-8452
   port_lines = 8
   direction = 0x0F
   drive = push-pull
   voltage = 3.3

``model`` is ``usb-8451`` or ``usb-8452``. Voltage is device-wide (8451 fixed at
3.3 V; 8452 allows 1.2 / 1.5 / 1.8 / 2.5 / 3.3 V). Multiple ``io.*`` rows that
share the same ``resource`` must use the same voltage.

I2C and SPI (845x)::

   [io.i2c]
   i2c_id = 1
   driver = ni-845x
   resource = USB-8452
   model = usb-8452
   voltage = 3.3
   clock_hz = 100000
   address = 0x50
   address_bits = 7
   pullup = true

   [io.spi]
   spi_id = 1
   driver = ni-845x
   resource = USB-8452
   model = usb-8452
   voltage = 3.3
   clock_hz = 1000000
   mode = 0
   chip_select = 0
   bits_per_word = 8

8451 limits: I2C ≤ 250 kHz, SPI ≤ 12 MHz. 8452 limits: I2C ≤ 3.3 MHz, SPI ≤ 50 MHz.
Simulated protocol adapters::

   [io.i2c]
   i2c_id = 1
   driver = sim
   address = 0x50
   read_data = "aabb"

   [io.spi]
   spi_id = 1
   driver = sim
   mode = 0

API usage
---------

Configure direction, drive outputs, and record readbacks as measurements::

   col.io.dio.configure(dio_id=1, direction=0x0F)
   col.io.dio.write_port(dio_id=1, value=0b1010)
   value = col.io.dio.read_port(dio_id=1, key="port_a")
   col.io.dio.write_pin(dio_id=1, line=0, value=True)
   level = col.io.dio.read_pin(dio_id=1, line=0, key="reset")

I2C master (empty write is an address-only ACK probe)::

   col.io.i2c.configure(i2c_id=1, address=0x50, clock_hz=100000)
   col.io.i2c.write(i2c_id=1, data=b"")
   col.io.i2c.write_read(i2c_id=1, write_data=b"\x00", read_nbytes=2, key="reg0")

SPI full-duplex transfer::

   col.io.spi.configure(spi_id=1, mode=0, chip_select=0, clock_hz=1000000)
   col.io.spi.transfer(spi_id=1, data=b"\x01\x02", key="xfer")

``read_port``, ``read_pin``, ``i2c.read``, ``i2c.write_read``, and ``spi.transfer``
require ``key=`` and persist measurement rows under domain ``equipment`` in
``execution.sqlite``. Byte payloads are stored as hex. Writes and configure calls
are ``@command`` APIs.

Named pins and per-line setup
-----------------------------

Add a ``pins`` map to the selected DIO row; names resolve to zero-based lines::

   [io.dio]
   dio_id = 1
   driver = "sim"
   port_lines = 8
   direction = 0x01
   pins = { reset = 0, ready = 1 }

In a configured procedure, use either ``name`` or ``line``, not both::

   col.io.dio.configure_pin(dio_id=1, line=0, output=True)
   col.io.dio.configure_pin(dio_id=1, line=1, output=False)
   col.io.dio.set_pull(dio_id=1, line=1, pull="up")
   col.io.dio.write_pin(dio_id=1, name="reset", value=False)
   col.io.dio.read_pin(dio_id=1, name="reset", key="reset_low")
   col.shared.verify.verify_field(key="reset_low", expected_val=False)

The last line requires ``colosseum-shared``. It verifies the recorded readback;
a successful write alone does not establish the pin level. Sim supports pulls;
``ftdi-ft232h``, ``ni-6501``, and ``ni-845x`` DIO refuse ``set_pull`` (fixed or
absent per-line pull control). Use ``col.io.i2c.set_pullup`` for 845x I2C bus
pull-ups. Input pull behavior and driving a line are different operations.

Platform notes
--------------

**Linux:** install ``libusb`` (distribution package) so pyftdi can open FT232H
devices. Install NI-DAQmx and/or NI-845x from NI so the shared libraries are
on the loader path (or set ``library`` in config).

**Windows:** install the WinUSB driver for the FT232H (for example with Zadig) so
pyftdi can claim the interface. USB serial drivers alone are not sufficient for
MPSSE GPIO. Install NI-DAQmx for the USB-6501 and NI-845x software for the
USB-8451/8452; the DLLs are loaded from the system path.

See also :doc:`platform_notes` and :doc:`configuration`.

USB protocol adapters (0.6.0)
-----------------------------

The active adapters use the existing ``col.io.i2c`` and ``col.io.spi`` APIs.
Beagle analyzers use ``col.io.analyzer`` to observe traffic. They cannot issue
master transactions. All implementations remain within this plugin.

.. list-table:: Initial backend capabilities
   :header-rows: 1
   :widths: 25 30 45

   * - Device
     - Driver / model
     - Supported operations
   * - Aardvark
     - ``totalphase-aardvark``
     - I2C master (7/10-bit), pull-ups, repeated START; SPI master, CS 0
   * - Cheetah
     - ``totalphase-cheetah``
     - SPI master, CS 0..2, queued transfers
   * - USB2ANY
     - ``ti-usb2any``
     - I2C master (7/10-bit), pull-ups, repeated START; SPI master, dedicated CS 0
   * - Beagle I2C/SPI
     - ``totalphase-beagle`` / ``i2c-spi``
     - I2C or SPI capture, one protocol per capture
   * - Beagle USB 12
     - ``totalphase-beagle`` / ``usb-12``
     - Low/full-speed USB capture
   * - Beagle USB 480
     - ``totalphase-beagle`` / ``usb-480``
     - Low/full/high-speed USB capture; excludes USB 480 Power

Master SPI uses 8-bit words, MSB first, active-low chip select, and modes 0..3.
Each transfer is one chip-select transaction. Oversized transfers are rejected
rather than split across chip-select or STOP boundaries. Aardvark I2C and Cheetah
SPI accept at most 65,535 bytes per operation; Aardvark SPI is limited to 4096
bytes, and USB2ANY accepts at most 255. The installed
firmware may impose tighter limits and return an error. Cheetah supports
100 kHz..40 MHz; Aardvark SPI supports 125 kHz..8 MHz. Aardvark I2C supports
1..800 kHz. USB2ANY I2C rates are 10, 100, and 400 kHz; SPI requests are
367 Hz..8 MHz. SPI dividers are rounded down in frequency for USB2ANY.
Vendor-selected actual rates are available as backend ``actual_clock_hz``;
SPI backends and Aardvark I2C also write them to the debug log.

Runtime installation and licensing
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``pip install -e .`` still installs the package and its development/test tools.
Tests and simulated runs require no vendor SDK or attached hardware. Live
access requires the bench's separately installed vendor runtime, as with NI:

* Total Phase: install the vendor USB driver and matching Python 3 Software API.
  Place the unpacked SDK directory on ``PYTHONPATH`` so ``aardvark_py``,
  ``cheetah_py``, or ``beagle_py`` and their matching native libraries can be
  imported. Keep each SDK's files intact. The vendor Python bindings handle
  their own native symbol and version negotiation; ``library=`` is not used.
  Match SDK architecture to Python and use a vendor-supported Windows, Linux,
  or macOS runtime. Linux also needs the vendor's USB permission/udev setup.
* USB2ANY: the initial ABI is TI SDK 2.7's Windows x86 DLL. Use 32-bit Python
  3.10+ and the corresponding ``USB2ANY.dll``; ``library=`` can specify its
  path. Other OSes and the x64 ABI are explicitly refused. The loader binds
  stdcall exports with explicit argument types. Install/qualify matching
  firmware on the bench; this plugin never upgrades firmware.

No SDK package, vendor source, or vendor binary is copied into this repository,
added to pip dependencies, or included in its wheel. Total Phase's SDK license
is proprietary, outside ``RULES.md``'s dependency allowlist; it is not treated
as an approved redistributable dependency. Operators obtain external runtimes
from the vendor under their terms. Redistributing SDKs or adding SDK packages
would require a separate license review. USB2ANY SDK redistribution has not
been approved either.

References: `Aardvark manual <https://www.totalphase.com/support/articles/200468316-aardvark-i2c-spi-host-adapter-user-manual/>`_,
`Cheetah manual <https://www.totalphase.com/support/articles/200472636-cheetah-spi-host-adapter-user-manual/>`_,
`Beagle manual <https://www.totalphase.com/support/articles/200472426-beagle-protocol-analyzer-user-manual/>`_,
`Total Phase license <https://github.com/totalphase/aardvark_py/blob/master/LICENSE.txt>`_,
and `TI USB2ANY SDK 2.7 API reference <https://e2e.ti.com/cfs-file/__key/communityserver-discussions-components-files/48/api_5F00_reference_5F00_for_5F00_usb2any_5F00_sdk_5F00_2.7.0.pdf>`_.

Configuration and ownership
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use ``examples/configs/config.usb-adapters.toml.example`` as a hardware template.
``resource`` is a stable serial number, not the USB enumeration port. Total
Phase serials may include their printed hyphen. Devices already in use are
refused. Aardvark and USB2ANY I2C/SPI rows share a reference-counted handle;
configuration and each complete transaction are serialized. Rows sharing a
device must agree on target power, timeout, and USB2ANY library path.
Per-row protocol settings are reapplied before each transaction. One Beagle
serial may be owned by only one analyzer row at a time.

``target_power`` defaults to false and is distinct from logic voltage.
For Aardvark, true enables both vendor target-power outputs; for Cheetah,
true enables its target supply. USB2ANY enables only its 3.3 V supply, leaving
5 V and adjustable supplies off. Beagle I2C/SPI can explicitly enable target
power and pull-ups; both default off. USB 12/480 do not expose power control.
The new master backends do not implement programmable logic voltage; a
``voltage`` other than 3.3 is refused. Outputs are disabled when the final
device reference closes.

``timeout_ms`` controls Aardvark's I2C bus timeout (1..1000), Beagle read
timeout (1..1000), or USB2ANY's DLL receive timeout (2..200; default 25).
Cheetah has no configurable batch-shift timeout and refuses this setting.
USB2ANY serializes access across devices because its receive timeout is global.
Existing VISA autoconfig does not discover these adapters; configure them
explicitly.

Analyzer workflow and evidence
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Start capture before creating bus activity::

   col.io.analyzer.start(analyzer_id=1, path="capture/raw.jsonl")
   try:
       col.io.i2c.write_read(i2c_id=1, write_data=b"\x00", read_nbytes=2, key="reg0")
   finally:
       summary = col.io.analyzer.stop(analyzer_id=1, timeout_s=2.0)
       col.io.analyzer.export(analyzer_id=1, path="capture/raw.jsonl", key="bus")

``start`` returns after monitoring is enabled, then a worker streams packets
to disk. Omit ``path`` for a unique file name under ``captures/``. Existing
capture/export destinations are never overwritten. Configure an idle analyzer
with ``configure(analyzer_id=..., protocol=..., mode=..., sample_rate_hz=...)``.
USB models have a fixed sampling rate; I2C/SPI defaults to 50 MHz. SPI capture
uses active-low CS and MSB first. The selected mode determines the sample edge.

``stop`` drains until the bus is idle or its deadline expires, then disables
monitoring. An SDK read can add up to 1.1 seconds beyond the drain deadline.
USB 12/480 and Beagle I2C/SPI lack an atomic stop-and-drain operation:
``bg_disable`` discards unread buffers. Therefore all live summaries explicitly
set ``tail_may_be_discarded = true``, even when ``drained_to_idle`` is true.
Quiesce the source before stopping when the end of a transaction matters.
This API does not promise lossless full-rate USB 480 capture.

Captures have finite ``max_duration_s`` (default 60), ``max_records`` (100,000),
and ``max_bytes`` (64 MiB of serialized packet records, excluding metadata and
summary). Reaching the record/byte limit stops capture and marks detected loss;
a duration limit ends the observation window. A drain timeout also marks loss.
There is no unbounded in-memory packet queue. Shutdown stops active workers
before closing handles; if a native read hangs beyond its timeout, the handle
is retained rather than closed beneath a running read.

JSON Lines contains metadata, packet records, and a final summary. Packets
retain numeric vendor status/events, device timestamps in sampling-clock ticks,
and data offsets/durations. I2C keeps 16-bit words including ACK/NACK bits;
SPI stores separate MOSI/MISO hex; USB stores raw packet hex and events.
Short buffers and loss flags remain visible. USB class decoding, PCAP export,
and proprietary Data Center formats are outside this initial implementation.

``export`` registers one artifact and summary measurement under domain
``equipment``, command ``io.analyzer.export``. Detected loss or worker errors
produce a FAIL measurement. Failed captures remain exportable for diagnosis,
while ``stop`` raises their error. Inspect stop reason, flagged records, and
stop-boundary uncertainty when accepting evidence; a PASS artifact row alone
does not establish a valid protocol exchange.

``examples/test_protocol_capture.py`` uses
``examples/configs/config.analyzer.sim.toml`` for an offline example. Simulated
analyzer ``records`` are canned events, independent of the simulated master;
they do not validate a real bus or model electrical behavior.

Qualification
~~~~~~~~~~~~~

Automated tests use fake SDKs and simulation. Physical devices and vendor
SDK binaries were unavailable during implementation; these backends require
bench qualification before production use. For each OS/SDK/firmware combination,
verify serial selection, target power, I2C ACK/NACK and repeated START, SPI modes
and chip-select boundaries, disconnect handling, and final-handle cleanup.
For each Beagle model, compare capture payload and device timing with known
traffic, exercise overflow/limits and active shutdown, and confirm the USB 12
versus USB 480 speed capabilities. Archive the runtime versions with those
results. USB2ANY's zero-status write/combined APIs do not expose independent
byte counts; qualify their transfer-completeness behavior on hardware.
