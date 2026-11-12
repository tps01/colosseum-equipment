Transports, driver selection, and support
=========================================

Start with :doc:`getting_started` for an offline test and
:doc:`instrument_workflows` for live acquisition recipes. The full shared
transport key definitions are in :doc:`/config_reference`; category-specific
examples are in :doc:`/config_instruments` and :doc:`/config_io`.

Choose a transport
------------------

.. list-table::
   :header-rows: 1

   * - Connection
     - Configuration and prerequisite
   * - VISA USB, GPIB, or Ethernet
     - Supply the full ``resource`` and install a compatible system VISA backend.
       The Python pyVISA package alone does not install vendor VISA libraries.
       Linux GPIB needs host **linux-gpib** (see below). USBTMC may also use a
       kernel ``/dev/usbtmcN`` path when libusb cannot claim the interface.
   * - Serial / COM / ASRL
     - Set the actual port/resource and the instrument's baud/framing settings.
       COM ports normalize to ASRL. USB CDC instruments appear as
       ``/dev/ttyUSB*`` / ``/dev/ttyACM*`` (or ``COMn``) — use ASRL, not
       ``USB...::RAW``. See :doc:`serial_ports`.
   * - Simulation
     - ``driver="sim"`` uses fixtures. PyVISA-sim is a separate backend path;
       ``visa_backend="sim"`` also needs ``sim_definition``.
   * - HTTP-controlled equipment
     - Use only a model/driver implementing the required HTTP operations.
       Network connectivity does not make a SCPI instrument an HTTP API.
   * - USB I/O adapters
     - Install the matching vendor runtime and configure the adapter section.
       See :doc:`io_digital` for GPIO, I2C, SPI, and analyzer limits.

``interface`` alone does not choose the transport. Follow the driver/resource
rules in the configuration reference. For several PSUs, use
``[[equipment.psu]]`` with distinct ``psu_id`` values; a PSU and a DMM can each
use ID 1. Select those IDs explicitly in API calls.

USB personalities (CDC, USBTMC, RAW)
------------------------------------

A USB cable does not imply one VISA class:

* **USB CDC / serial** — the OS creates a TTY (``ttyUSB`` / ``ttyACM`` / ``COM``).
  Configure that as serial/ASRL. Autoconfig already probes pyserial COM ports.
* **USBTMC** — prefer ``USB...::INSTR``, or ``resource = "/dev/usbtmcN"`` on Linux
  when the kernel ``usbtmc`` driver owns the device.
* **``USB...::RAW``** — raw bulk endpoints, not a generic SCPI pipe. Incomplete
  udev permissions often show ``USB0::VID::PID::???::RAW``; fix permissions or
  use the CDC/USBTMC path for the instrument. Do not set ``resource`` to RAW
  unless a supported model documents that protocol.

Native protocol catalog adapters
--------------------------------

Version 0.13.0 adds three paths which require an explicit model. See
``examples/configs/config.native-protocols.toml`` for complete bench rows.

* **Original B&K 8500** (``bk-8500``): COM/ASRL at the configured baud rate
  (default 9600, 8N1). The adapter disables serial terminators and exchanges
  checksummed 26-byte packets. ``device_address`` defaults to 0 (range 0–254).
  Static CC/CV/CP/CR, setpoints, input switching, voltage/current/power/state
  readback, derived resistance and short-function selection are implemented.
  Construction selects remote control without enabling the input. Transient/list,
  protection, slew and preset operations refuse before I/O; 8500B is not covered.
* **Mini-Circuits RCM/ZTM** (``minicircuits-rcm-ztm``): use ``driver="http"``,
  ``driver="minicircuits-telnet"`` or ``driver="minicircuits-usb"``. Configure
  ``block`` (1–99), a default ``channel`` (or ``path``), and
  ``channels_per_block`` (4 by default, or 8 for RS8DAT). A row addresses one
  installed block, not an inferred mesh path. Set/read replies must match that
  block. Rejected or clamped attenuation raises an error; status 2 means the rack
  has already set its maximum rather than the requested value. Range/step getters
  require ``min_attenuation_db``, ``max_attenuation_db`` and ``step_db`` from the
  installed module's specification. Fractional block/channel values are refused;
  they are never rounded to another physical path. Rack-wide preset remains
  unsupported. These adapters do not issue address-assignment commands or infer
  mesh paths from endpoint numbers.
* **Tektronix USB RSA306/306B/503A/507A/603A/607A**: use ``driver="rsa-api"``.
  Install the matching Tektronix RSA API runtime separately and set
  ``rsa_api_library`` to its absolute library path. The default is
  ``C:/Tektronix/RSA_API/lib/x64/RSA_API.dll``. No vendor runtime is included in
  the wheel. ``resource`` is the exact serial number; ``"auto"`` is accepted only
  with one device connected. The reported model must match the configured model.
  One native device context may be open per process; use separate processes for
  multiple devices. Close SignalVu-PC before claiming a device through this API.

USB RSA ``run``/``wait_complete``/``acquire`` capture finite IQ blocks.
``iq_bandwidth_hz`` (default 40 MHz) determines the actual IQ sample rate;
``num_samples`` defaults to 1024 and is checked against the runtime's current
limit. ``sample_rate_hz``, if supplied, must match the resulting rate. ``span``
and ``rbw`` configure spectrum span and resolution bandwidth; they do not set
IQ sample rate. ``capture_iq`` configures the requested spectrum span and IQ
bandwidth separately and calculates record length from the actual rate. Immediate,
external and IF-power triggers are implemented; trigger position is 1–99 percent
despite the legacy public argument name ``position_dbm``. Continuous streaming,
DPX and peak-marker control are outside this subset.

Completed IQ records are retained for export without reacquisition; configuration
changes, aborts, failed captures and timeouts invalidate them. Short records,
nonfinite data and acquisition status flags (including overrange/USB transfer
errors) refuse export. ``save_IQ_data`` retains the established interleaved
little-endian float64 layout. ``capture_iq`` uses the shared f32/i16/c64 encodings
and bin/MAT/iq.tar containers. Metadata records the actual sample rate/bandwidth
and native timestamp ticks without claiming those ticks are UTC. Spectrum CSV
exports acquire trace 1 in dBm and use the actual frequency grid returned by the API.

These paths have manual-backed recording/ABI tests, not physical hardware
qualification. Runtime, firmware, sensor settling and installed rack topology
still need validation on the bench.

RCM/ZTM connection details (0.13.1)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

HTTP resources are origin URLs such as ``http://192.0.2.10:800/``. Configure
``password`` only when rack password security is enabled; leave ``username``
unset because the native protocol does not use HTTP Basic authentication.
The transport sends the documented ``PWD=...;``
prefix, percent-encodes the password, and preserves the trailing ``?`` on queries.
Connection failures redact the password-bearing URL.

For Telnet, set ``driver="minicircuits-telnet"`` and
``resource="telnet://192.0.2.10:23"`` (23 is the default port). The transport
consumes the connection greeting, performs password login when configured, and
uses CRLF command/reply framing. Telnet option requests are refused without
passing control bytes to the instrument parser. Each transaction has one
``timeout`` deadline, including fragmented replies. Timed-out, disconnected or
malformed sessions close; commands are not automatically retried, since a set
may already have executed. Close/reopen the row to establish a new session.

For USB, set ``driver="minicircuits-usb"`` and ``resource`` to the controller's
actual serial number. ``"auto"`` requires exactly one distinct matching HID
path. The transport selects VID 0x20CE / PID 0x0022, verifies the serial with
``:SN?``, and sends native 64-byte SCPI reports through HIDAPI. The HID report
ID is transport framing, separate from the native interrupt code. Commands are
limited to 63 ASCII bytes; returned reports must have the documented size,
command code and NUL terminator. Each block can have its own configuration row;
rows for one USB rack share one handle and serialize complete exchanges.
The handle closes when the final row releases it. A failed exchange invalidates
the shared session; close all rows for that rack before reopening, so a delayed
reply cannot be assigned to another command.
Use one controlling USB application per rack; close the vendor GUI before using
the plugin's USB connection.

USB uses the packaged ``hidapi`` dependency with its BSD-3-Clause license
alternative. No vendor .NET/ActiveX DLL or WinUSB driver replacement is required.
Linux hosts need HID device permissions (udev rules) and HIDAPI's system runtime
requirements. Host/runtime setup and actual firmware remain bench qualification
items; tests here use simulated sockets and HID handles.

Linux GPIB
----------

GPIB instruments use a controller board plus a primary address. Configure the
listener, not the board node::

    resource = "GPIB0::4::INSTR"

``/dev/gpib0`` is the **adapter** character device created by linux-gpib. It is
not a SCPI message pipe like ``/dev/usbtmc0``. Do **not** set
``resource = "/dev/gpib0"``; Colosseum would treat that as ASRL and fail.

Host prerequisites (not shipped in the wheel):

1. Install linux-gpib kernel and userspace; configure ``/etc/gpib.conf`` and run
   ``gpib_config`` so ``/dev/gpib0`` exists.
2. Membership in the ``gpib`` group (or equivalent udev rules).
3. Python ``gpib`` bindings from that linux-gpib install (what pyvisa-py loads).
   Do not rely on PyPI ``gpib-ctypes`` in this package (GPL-2.0; not allowlisted).
4. Confirm with ``pyvisa-info`` that the ``@py`` backend reports GPIB available.

``col.equipment.autoconfig(..., gpib_scan=True)`` probes primary addresses
``0``–``30`` on board ``0`` when ``list_resources`` returned no ``GPIB`` names
but a board appears present. Leave ``gpib_scan`` off unless you need that sweep.

Driver selection
----------------

1. A configured nonempty ``model`` skips automatic identity-based selection.
   Choose the registered slug for the actual model.
2. With no model, the plugin queries identity and tries a matching registration
   for that equipment kind. Genesys serial devices also use a bare ``IDN?``
   probe on serial/ASRL resources.
3. A failed/unknown identity, wrong-kind match, or unregistered identified
   model falls back to the kind's generic driver. Serial, GNSS, and relay kinds
   skip identity probing; sim and HTTP transports also use generic when no
   explicit model is configured.
   It is not proof that every generic command works on the instrument.

Connection/open failures can still raise; identity query failures are logged
and use generic. Fallback is not a replacement
for a working backend or resource. Inspect the resolved-model log entry before
qualifying a procedure. ``col.equipment.autoconfig`` discovers VISA ``?*INSTR``
and serial COM (Genesys bare ``IDN?`` with CR on ASRL; opt-in ``qm=True`` /
``gnss=True`` for Fluke ``QM`` and GNSS after IDN misses); review
its generated configuration before enabling outputs. Opt-in ``gpib_scan=True``
sweeps GPIB primary addresses when the board is present but enumeration is
empty. FTDI adapters stay manual. See :doc:`/api/autoconfig`.

What support means
------------------

.. list-table::
   :header-rows: 1

   * - Evidence of support
     - What it establishes
   * - Physical hardware qualification
     - A specified model, firmware, options, transport, and operation were checked
       on hardware. Do not infer it from a driver registration or simulated test.
   * - Specific driver implemented
     - The driver implements a documented subset. Hardware qualification can
       still be outstanding.
   * - Generic SCPI
     - The common dialect may work; qualify each operation on the actual model.
   * - Explicitly unsupported operation
     - ``EquipmentCapabilityError``; choose an implemented path or another driver.

Representative capability matrix
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table:: Implemented subsets; physical qualification is separate
   :header-rows: 1

   * - Kind and model examples
     - Implemented path
     - Limits to check
   * - DMM: ``keysight-34410a``, ``keithley-2001``
     - Scalar function/range setup, trigger/initiate/fetch, one-shot readings.
     - No scanner or buffered acquisition in these profiles.
   * - PSU: ``keysight-e3644a``, ``keysight-n6705a``
     - Voltage/current, output, measurements, protection subsets.
     - E3644A panel range; N6705A fitted modules/channels; no digitizer/sequencing.
   * - Scope: ``tektronix-tds3034b``, ``rohde-rtb2004``
     - Single acquisition, completion, scaled voltage-waveform CSV.
     - No segmented/history or logic export; R&S scalar automatic readings absent.
   * - Spectrum: ``keysight-n9020a``
     - SA sweep, markers, dBm trace CSV, host bandwidth calculation.
     - Linear frequency sweeps; no licensed-app, IQ, or screenshot support implied.
   * - VNA: ``keysight-e5071b``, ``rohde-znle6``
     - Sweep/averaging, scalar S-parameters, actual-stimulus CSV.
     - Scalar CSV is not a full Touchstone matrix; ECal/S2P refused.
   * - RF power: ``keysight-u8487a``, ``rohde-nrp18s``
     - Average-power acquire/fetch and correction.
     - No envelope peak/gates; direct NRP requires a SCPI-capable vendor/VISA path.
   * - Load: ``chroma-63600-5``, ``teledyne-t3el150303p``
     - Static CC/CV/CP/CR and scalar readback.
     - No transient/list/parallel controls in these profiles.

The model-by-model matrix is maintained in the
`inventory implementation and qualification table <https://github.com/tps01/colosseum-equipment/blob/develop/docs/equipment/inventory-rollout.md>`__
and its linked manual analysis. The inventory expansion pass reports synthetic
command-level tests; CI does not gate physical qualification, and formal
hardware-qualified rows are still empty in that table even when some lab
validation of older drivers exists elsewhere. Scope capture, IQ export,
triggering, and analyzer applications need per-operation checks; an installed
option or matching model name does not establish those capabilities.

Troubleshooting
---------------

If a resource is missing, enumerate it with the installed VISA backend and
confirm access independently of Colosseum. If a call raises capability errors,
check the selected model and operation subset. If a measurement cannot be
verified, check its command/key identity; a ``fetch`` row is different from a
``measure_voltage`` row. Required command errors abort later steps; keep local
hardware cleanup in ``finally``. See :doc:`api_conventions`.
