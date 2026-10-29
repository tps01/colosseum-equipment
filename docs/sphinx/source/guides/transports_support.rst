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
   * - Serial / COM / ASRL
     - Set the actual port/resource and the instrument's baud/framing settings.
       COM ports normalize to ASRL. See :doc:`serial_ports`.
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
qualifying a procedure. ``col.equipment.autoconfig`` can discover lab resources;
review its generated configuration before enabling outputs. See
:doc:`/api/autoconfig`.

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
and its linked manual analysis. The inventory rollout reports synthetic
command-level tests and outstanding physical qualification. Scope capture,
IQ export, triggering, and analyzer applications need per-operation checks;
an installed option or matching model name does not establish those capabilities.

Troubleshooting
---------------

If a resource is missing, enumerate it with the installed VISA backend and
confirm access independently of Colosseum. If a call raises capability errors,
check the selected model and operation subset. If a measurement cannot be
verified, check its command/key identity; a ``fetch`` row is different from a
``measure_voltage`` row. Required command errors abort later steps; keep local
hardware cleanup in ``finally``. See :doc:`api_conventions`.
