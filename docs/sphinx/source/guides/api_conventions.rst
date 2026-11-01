API conventions and failures
============================

Call public APIs through ``import colosseum as col`` and the documented
``col.*`` path. Signatures show defaults and keyword-only arguments (after
``*``). Omitted optional arguments use those defaults; a required argument has
no default. See each callable for its units and driver-specific restrictions.

Commands record actions and re-raise exceptions unless ``optional=True``.
Measurements record returned evidence under ``key``; an exception records a
null ERROR row and re-raises unless ``optional=True``, which returns ``None``.
Verification FAIL/ERROR/BLOCKED outcomes are recorded without aborting later
steps. ``optional=True`` excludes an outcome from the aggregate verdict; it
does not make a later dependent verification optional.

Keep measurement keys distinct for separate facts. Instrument IDs and channels
do not distinguish measurements with the same domain, command, key, and row
index. See `evidence and verification <https://tps01.github.io/colosseum-core/guides/measurements_verifications.html>`__
for lookup rules and complete failure examples.

Broadcast id ``"all"``
----------------------

Selected **void** setup/control commands accept ``*_id="all"`` (for example
``psu_id``, ``vsg_id``) and apply the same arguments to every configured row of
that kind, in ascending id order. Fan-out is sequential (not simultaneous). If
any target fails, remaining ids still run, then one
``EquipmentError`` summarizes the failures. Channel numbers, remote waveform
names, and other args must be valid on every target. Shared **input** paths
(such as ``upload_waveform`` / ``apply_mask_setup``) are intentional; host
**output** path writers (``save_*``, ``start_logging``), waits, and
get/measure APIs stay single-id only.

Example::

   col.equipment.psu.set_output(psu_id="all", enabled=False)
   col.equipment.vsg.upload_waveform(
       vsg_id="all", local_path="wave.wfm", remote_name="WAVE1",
   )

The plugin uses Colosseum's standard run artifacts. See the
`output guide <https://tps01.github.io/colosseum-core/guides/output_artifacts.html>`__
for summaries and SQLite queries. Plugin captures require artifacts enabled.

Instrument ranges and capabilities
----------------------------------

Voltage, current, frequency, record length, and protection ranges depend on the
selected model, fitted options, and channel. A generic driver often forwards
the requested number without checking the instrument's full physical range.
Use that model's manual and qualify the operation; absence of a Python error
does not establish that hardware accepted a setpoint. See
:doc:`transports_support` and :doc:`instrument_workflows`.
