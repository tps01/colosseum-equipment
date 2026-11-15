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
  ``tektronix-rsa5103b`` and ``tektronix-rsa6000``; configure under
  ``equipment.rtsa``). Exact models ``tektronix-rsa5115b`` and
  ``tektronix-rsa5126b`` use native spectrum commands and still provide
  ``capture_iq``.
* ``generic`` - Keysight-style SCPI for offline PyVISA-sim or compatible lab gear

Example workflows
-----------------

* CW stimulus and swept spectrum: ``examples/test_rf_sweep.py`` (uses ``config.rf.visa-sim.toml`` or hardware config)
* Vector arb and RTSA capture: ``examples/test_rf_vector_mod.py``
* Multi-VSG IQ matrix from ``parameters.toml``: ``examples/test_vsg_waveform_matrix.py``
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

Bandwidth methods and annotated plots
--------------------------------------

``speca.measure_bw`` and ``speca.measure_center_frequency_hz`` share the same
edge analysis. Bandwidth is the distance between the edges; center frequency
is their midpoint, not the peak frequency or a power centroid.

* Omit both ``method`` and ``threshold_db`` to retain the existing 3 dB method.
  An explicit ``threshold_db`` selects another drop below the reference power. This legacy
  method interpolates in dBm and retains its existing window-boundary behavior.
* ``method="fwhm"`` measures full width at half the peak's **linear power**,
  equivalent to a 3.0103 dB drop. It interpolates in linear power, so it can
  differ from legacy threshold interpolation on a coarsely sampled trace.
* ``method="occupied_power"`` integrates linear power over frequency and finds
  equal-tail edges enclosing ``occupied_power_pct`` (default 99). This uses
  cumulative trapezoidal integration and interpolates the cumulative curve;
  it includes all in-window power, including background noise.
* ``method="half_prominence"`` measures the dominant peak at half its prominence
  above its local baseline in linear power. This differs from FWHM when the
  peak sits on an elevated background.

For threshold analysis, ``ref_pwr_meas_method="max"`` (the default), ``"mean"``
or ``"median"`` selects the reference power from smoothed dBm samples inside
``start_hz`` / ``stop_hz``. The crossing level is that statistic minus
``threshold_db`` (or 3 dB when omitted). Mean and median are arithmetic statistics
of dBm samples, not averages in linear watts or frequency-weighted integrals.
Crossings are still searched outward from the maximum sample, so a lower
reference generally produces a wider measured band. Non-default reference
methods cannot be combined with a named bandwidth ``method``.

For example::

   col.equipment.speca.measure_bw(
       speca_id=1, start_hz=850e3, stop_hz=1150e3,
       threshold_db=6.0, ref_pwr_meas_method="median",
       save_plot=True, key="bandwidth",
   )

A named ``method`` and an explicit ``threshold_db`` are mutually exclusive.
``occupied_power_pct`` is only accepted with ``occupied_power`` and must be
strictly between 0 and 100. New methods require finite samples, an increasing
frequency axis and at least two samples inside ``start_hz`` / ``stop_hz``.
Peak methods choose the highest peak, resolving ties toward lower frequency;
flat peaks use the middle of the plateau. Missing crossings or an unmeasurable
prominence raise ``ValueError``. Choose analysis bounds that isolate the desired
waveform and include its edges; occupied-power results also depend on those bounds.

``smoothing_order`` is a moving-average half-window in samples, not a
Savitzky-Golay polynomial order. Zero disables smoothing. Threshold analysis
smooths dBm; named methods smooth linear power before analysis.

For example::

   col.equipment.speca.measure_bw(
       speca_id=1, start_hz=850e3, stop_hz=1150e3,
       method="fwhm", save_plot=True, key="bandwidth",
   )
   col.equipment.speca.measure_center_frequency_hz(
       speca_id=1, start_hz=850e3, stop_hz=1150e3,
       method="occupied_power", occupied_power_pct=99.0,
       save_plot=True, key="center_frequency",
   )

``save_plot`` defaults to false. When true, a PNG under the run's ``plots/``
directory uses the same style as ``save_trace_data``: the full source trace
in dBm against frequency in Hz. Center measurements add a black dot on the trace
at the calculated center; bandwidth measurements add two dashed vertical lines
at the calculated edges. The upper-left box displays the measured frequencies
in scientific notation. The displayed trace remains unsmoothed even when
analysis uses smoothing. Each image has a unique filename and a separate plot
evidence key with source-key, method, edges and result metadata. Numeric
measurements and their verification keys remain unchanged.

Plotting uses the same trace arrays as analysis and never triggers another
sweep. An explicit ``trace_path`` analyzes a saved CSV; otherwise the existing
driver trace-selection behavior applies, including reuse of its last saved trace.
Calibration already applied to a saved trace is preserved. Plotting does not
apply an additional correction. An error saving a requested plot fails the
measurement normally.

These methods run in host trace analysis. The separate ``measure_obw_hz`` API
retains its native-instrument-query-first behavior and legacy threshold fallback;
use ``measure_bw(method="occupied_power")`` for the percentage-based host method.

Capability errors
-----------------

IQ sample rate
~~~~~~~~~~~~~~

Use ``col.equipment.rtsa.set_sample_rate(rtsa_id=1, sample_rate_hz=1e6)``
to set a finite, positive IQ rate in samples per second. ``rtsa_id="all"``
broadcasts to configured RTSAs; ``key=`` supports parameter-file overrides.
Signal Hound BB60C/SM200C Spike drivers support this operation through
``SENS:ZS:CAP:SRAT``. Their optional ``sample_rate_hz`` bench configuration
uses the same setter. Set the rate before a sample count when the driver
derives acquisition duration from count and rate.

Other current drivers raise ``EquipmentCapabilityError`` rather than send
an unverified command. Tektronix IQ rates follow acquisition bandwidth;
this setter does not adjust bandwidth. USB RSA ``sample_rate_hz`` configuration
remains a check against the bandwidth-derived rate. Unsupported SCPI drivers
now reject that configuration field rather than silently ignoring it.
``capture_iq`` and export sample formats are unchanged.

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

Trace center frequency
----------------------

``col.equipment.speca.measure_center_frequency_hz`` measures the midpoint of
threshold crossings using the same bounds, smoothing, and trace selection as
``measure_bw``. Use ``verify_center_frequency`` to check the recorded value
against an expected frequency and tolerance.
