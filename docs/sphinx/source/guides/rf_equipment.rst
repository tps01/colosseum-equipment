RF equipment (VSG, ASG, spectrum analyzer, RTSA, VNA)
=======================================================

Colosseum exposes RF bench instruments through ``col.equipment.vsg`` (vector/signal generator),
``col.equipment.asg`` (analog signal generator), ``col.equipment.speca`` (classic spectrum analyzer),
``col.equipment.rtsa`` (real-time spectrum analyzer / IQ acquisition), and ``col.equipment.vna``.

Configure instruments in TOML (see the core configuration guide and the
complete bench files under ``examples/configs/``).
Select vendor behavior with ``model``. Per-function parameters and return types are documented in the
Python docstrings on ``colosseum_equipment.api`` modules (``vsg``, ``asg``, ``speca``, ``rtsa``, ``vna``).

Supported vendor models
-----------------------

* ``keysight-esg`` - Agilent/Keysight E4428C (analog) and E4438C (vector arb)
* ``keysight-e4407b`` - Agilent/Keysight E4407B ESA-E spectrum analyzer
* ``tektronix-rsa5100b`` - Tektronix RSA5100B / RSA6000 family RTSA (aliases
  ``tektronix-rsa5103b``, ``tektronix-rsa5115b``, ``tektronix-rsa5126b``,
  ``tektronix-rsa6000``; configure under ``equipment.rtsa``)
* ``generic`` - Keysight-style SCPI for offline PyVISA-sim or compatible lab gear

Example workflows
-----------------

* CW stimulus and swept spectrum: ``examples/test_rf_sweep.py`` (uses ``config.rf.visa-sim.toml`` or hardware config)
* Vector arb and RTSA capture: ``examples/test_rf_vector_mod.py``
* Offline trace plot: ``python examples/plot_trace.py outputs/<run>/traces/carrier.csv``

Offline CI without hardware uses ``examples/configs/config.rf.visa-sim.toml`` and ``pytest -m visa_sim``.
Hardware template: ``examples/configs/config.rf.hardware.toml.example``.

Trace and capture artifacts
---------------------------

``save_trace_data`` on ``col.equipment.speca`` writes a CSV under the active output directory and registers an
artifact row. Pass ``save_plot=True`` or ``plot_path=`` for an optional PNG (``speca_trace_plot``);
matplotlib support is included in the default installation.

RTSA spectrum / opaque IQ download uses ``save_IQ_data``. Length-mode IQ records
(center, span, acquisition bandwidth, duration) use ``col.equipment.rtsa.capture_iq``,
which decodes samples and writes ``mat`` / ``bin`` / ``iq.tar`` with
``sample_format`` ``f32``, ``i16``, or ``c64``. Models that do not implement the
call raise ``EquipmentCapabilityError``. On Tektronix RSA5100B / RSA6000 family
instruments, prefer a VISA socket resource such as
``TCPIP0::<ip>::4000::SOCKET``. Drivers override ``capture_iq`` for other RTSAs.

Capability errors
-----------------

Explicitly refused operations raise ``EquipmentCapabilityError``. Inherited
generic methods may instead send best-effort SCPI and warn once per model
and command. A successful write does not prove hardware support; the error
queue is not checked automatically. Distinguish vendor overrides, simulator
coverage, and actual bench validation. See the driver/capability notes for
per-model limits. Use ``col.equipment.scpi.write`` / ``query`` with exactly
one instrument ``*_id`` for manual-backed bespoke SCPI.

API reference
-------------

Public ``col.equipment.*`` RF APIs are documented in Python docstrings on the
``colosseum_equipment.api`` modules (``vsg``, ``asg``, ``speca``, ``rtsa``, ``vna``).
