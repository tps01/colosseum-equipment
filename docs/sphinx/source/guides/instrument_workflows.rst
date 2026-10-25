Instrument acquisition recipes
==============================

These recipes show how configuration, acquisition, readback, acceptance and
export fit together. The runnable simulator procedures are
``examples/test_power_rails.py``, ``test_rf_sweep.py`` and ``test_rf_vector_mod.py``.
Run from the repository root with their documented config files. Simulator
fixtures establish command flow and known responses, not hardware support or
instrument accuracy.

The other fragments below are **live-bench recipes**. Put the selected fragment
inside ``main`` in this scaffold, create ``config.toml`` with the matching
instrument rows, replace example resources/limits with your bench values, and
run ``colosseum run recipe.py -g config.toml``::

   import colosseum as col

   def main() -> None:
       # Insert one recipe here; CLI loads config.toml before this function.
       pass

   if __name__ == "__main__":
       col.config.load_config("config.toml")
       main()
       col.endex()

Each kind has its own integer ``<kind>_id``; the examples use 1. A typical VISA
row is::

   [equipment.dmm]
   dmm_id = 1
   resource = "TCPIP0::192.0.2.10::inst0::INSTR"
   model = "keysight-edu34450a"

Use the matching table/id/model for each recipe. The driver/capability notes
list aliases and model limitations. A catalog slug can inherit generic SCPI;
it does not establish support for every method. Vendor overrides and explicit
refusals take priority. Review the instrument's supported commands before use.

PSU and DMM: setpoint versus measured rail
------------------------------------------

The complete offline acceptance script includes required and optional checks::

   colosseum run examples/test_power_rails.py -g examples/configs/config.sim.toml

It deliberately records one optional FAIL on a valid DMM acquisition and exits
0 when required checks pass. An optional verifier cannot make a failed
measurement optional. The generic DMM has one channel unless configured
otherwise; a channel-count setting does not create a physical scanner.

For a live supply with multiple outputs (for example ``rigol-dp832``), pass
``channel=`` on every operation. Programmed readback and measured output have
different meanings::

   col.equipment.psu.set_voltage(psu_id=1, channel=1, voltage=3.3)
   col.equipment.psu.set_current_limit(psu_id=1, channel=1, current=0.5)
   col.equipment.psu.set_ovp_v(psu_id=1, channel=1, voltage=3.6)
   col.equipment.psu.toggle_ovp(psu_id=1, channel=1, enabled=True)
   try:
       col.equipment.psu.set_output(psu_id=1, channel=1, enabled=True)
       col.equipment.psu.get_voltage(psu_id=1, channel=1, key="programmed")
       col.equipment.psu.measure_voltage(psu_id=1, channel=1, key="supply_output")
       col.equipment.psu.verify_voltage(key="supply_output", expected_val=3.3, tolerance=0.1)
       col.equipment.dmm.measure_voltage(dmm_id=1, channel=1, key="dut_rail")
       col.equipment.dmm.verify_voltage(key="dut_rail", expected_val=3.3, tolerance=0.1)
   finally:
       col.equipment.psu.set_output(psu_id=1, channel=1, enabled=False)

Read trip state with ``get_fault_status`` and clear it with
``clear_protection`` only when the bench procedure calls for it. A readback of a
setpoint alone does not establish voltage at the DUT.

DMM fixed configuration and fetch
---------------------------------

One-shot ``measure_voltage`` configures DC volts and reads a new value. To keep
configuration fixed over a triggered acquisition (``keysight-edu34450a``)::

   col.equipment.dmm.set_function(dmm_id=1, function="VOLT:DC", channel=1)
   col.equipment.dmm.set_auto_range(dmm_id=1, enabled=False, channel=1)
   col.equipment.dmm.set_range(dmm_id=1, value=10.0, channel=1)
   col.equipment.dmm.set_nplc(dmm_id=1, nplc=1.0, channel=1)
   col.equipment.dmm.set_trigger_source(dmm_id=1, source="IMM", channel=1)
   col.equipment.dmm.initiate(dmm_id=1, channel=1)
   col.equipment.dmm.fetch(dmm_id=1, channel=1, key="fixed_dc")

``fetch`` has its own measurement command identity; ``verify_voltage`` looks up
``measure_voltage`` evidence, not arbitrary fetch rows. Install shared and use
``col.shared.verify.verify_field(key="fixed_dc", expected_val=3.3, tolerance=0.1)``
for a generic fetch comparison. AC volts/current and four-wire resistance use
their matching ``measure_*`` methods; do not reuse DC voltage acceptance limits
or invent a second channel on a single-input meter.

Electronic load: a CC step with cleanup
---------------------------------------

Use a supported load such as ``itech-it8600`` with a wired, powered source. For
a 0.5 A step, choose current limits/protection for the DUT before engaging::

   col.equipment.eload.set_mode(eload_id=1, mode="CC", channel=1)
   col.equipment.eload.set_current(eload_id=1, current=0.5, channel=1)
   try:
       col.equipment.eload.engage(eload_id=1, channel=1)
       col.equipment.eload.measure_current(eload_id=1, channel=1, key="load_current")
       col.equipment.eload.verify_current(key="load_current", expected_val=0.5, tolerance=0.02)
       col.equipment.eload.measure_voltage(eload_id=1, channel=1, key="loaded_rail")
       col.equipment.eload.verify_voltage(key="loaded_rail", expected_val=3.3, tolerance=0.1)
   finally:
       col.equipment.eload.disengage(eload_id=1, channel=1)

Transient/list mode is a different acquisition: configure its levels, timing
and trigger first, then run it and acquire the DUT response. Steady-state
current readback alone does not characterize a transient. Protection trip/clear
and list support depend on the selected model; consult its API page.

ASG plus counter: amplitude units and input setup
-------------------------------------------------

For a ``rigol-dg822`` ASG and ``keysight-53220a`` counter, wire output 1 to
input 1. Use waveform voltage amplitude rather than RF dBm. State the load
impedance so the displayed Vpp has a clear meaning::

   col.equipment.asg.set_waveform(asg_id=1, channel=1, waveform="sine")
   col.equipment.asg.set_load_ohms(asg_id=1, channel=1, ohms=50.0)
   col.equipment.asg.set_amplitude_vpp(asg_id=1, channel=1, vpp=1.0)
   col.equipment.asg.set_offset_v(asg_id=1, channel=1, offset_v=0.0)
   col.equipment.asg.set_frequency(asg_id=1, channel=1, frequency=1e6)
   col.equipment.freqcounter.set_coupling(freqcounter_id=1, channel=1, coupling="AC")
   col.equipment.freqcounter.set_impedance(freqcounter_id=1, channel=1, ohms=50.0)
   col.equipment.freqcounter.set_trigger_level_v(freqcounter_id=1, channel=1, level_v=0.0)
   col.equipment.freqcounter.set_gate_time(freqcounter_id=1, seconds=0.1)
   try:
       col.equipment.asg.set_output(asg_id=1, channel=1, enabled=True)
       col.equipment.freqcounter.measure_frequency(freqcounter_id=1, channel=1, key="clock")
       col.equipment.freqcounter.verify_frequency(key="clock", expected_val=1e6, tolerance=10.0)
   finally:
       col.equipment.asg.set_output(asg_id=1, channel=1, enabled=False)

Do not substitute a statistical result for a single reading without configuring
the counter's statistics count/function. Input channel count, coupling and
impedance restrictions are model-specific.

RF power sensor: zero and calibrate before measuring
----------------------------------------------------

With ``model="keysight-u2000"`` and the correct sensor resource, remove RF for
zeroing, then reconnect/apply the intended -10 dBm stimulus. In the recipe below
the stimulus is applied externally after zeroing::

   col.equipment.pwrmeter.zero_sensor(pwrmeter_id=1, channel=1)
   col.equipment.pwrmeter.set_frequency(pwrmeter_id=1, channel=1, frequency_hz=1e9)
   col.equipment.pwrmeter.set_averaging_count(pwrmeter_id=1, channel=1, count=16)
   # Apply the known RF stimulus here before the measurement.
   col.equipment.pwrmeter.acquire(pwrmeter_id=1, channel=1)
   col.equipment.pwrmeter.measure_power_dbm(pwrmeter_id=1, channel=1, key="rf_power")
   col.equipment.pwrmeter.verify_power_dbm(key="rf_power", expected_val=-10.0, tolerance=0.5)

``measure_power_w`` reports watts; ``measure_power_dbm`` reports dBm. Select the
matching verifier/units, sensor range, calibration frequency and averaging.
The U2000 is single-channel; extra channel IDs are not additional sensors.
Equipment 0.5.0 adds ``pwrmeter.acquire`` for a new measurement before fetch-style
statistics. Configure the sensor's measurement/gate/trigger mode first; generic
SCPI commands require qualification on the actual model. U2000 sensors provide
average power and explicitly refuse envelope-peak queries; see the
`Keysight average/peak comparison <https://www.keysight.com/us/en/assets/7018-03996/application-notes/5991-2642.pdf>`_.
A peak-capable sensor uses ``measure_power_peak_dbm`` after its fresh acquisition;
setting averaging count to one does not turn an average sensor into a peak sensor.

Scope: measure and export a completed capture
---------------------------------------------

For ``model="tektronix-mdo4000"`` on a wired channel-1 signal::

   col.equipment.oscope.set_channel_display(oscope_id=1, channel=1, enabled=True)
   col.equipment.oscope.set_channel_scale_v(oscope_id=1, channel=1, volts_per_div=0.5)
   col.equipment.oscope.set_timebase_scale(oscope_id=1, seconds_per_div=1e-6)
   col.equipment.oscope.set_trigger_source(oscope_id=1, source="CH1")
   col.equipment.oscope.set_trigger_level_v(oscope_id=1, level_v=0.5)
   col.equipment.oscope.set_trigger_slope(oscope_id=1, slope="rising")
   col.equipment.oscope.acquire(oscope_id=1, timeout_s=10.0)
   col.equipment.oscope.measure_vpp(oscope_id=1, channel=1, key="pulse_vpp")
   col.equipment.oscope.verify_vpp(key="pulse_vpp", expected_val=1.0, tolerance=0.1)
   col.equipment.oscope.save_waveform(oscope_id=1, channel=1, path="scope/pulse.csv", key="pulse_trace")
   col.equipment.oscope.save_screenshot(oscope_id=1, path="scope/pulse.png", key="pulse_screen")

``acquire`` arms and waits with a timeout. Fetch-style measurements/exports use
the completed capture; make a new acquisition deliberately when another record
is wanted. Timeout is an acquisition failure, not a zero waveform. Probe ratio,
coupling, termination and record length also belong in a real bench procedure.
For an event created by the procedure, Equipment 0.5.0 provides nonblocking
``arm_single``. Configure a normal trigger first, then arm, create the event and
call ``wait_complete`` before fetching. Do not call blocking ``acquire`` and
then attempt to create the event it is waiting for. Tek MDO4000 completion waits
for acquisition to stop; OPC alone does not accept a still-running acquisition.

Use :doc:`masks` for time-domain mask setup and CSV acceptance.

SpecA, VSG and RTSA: numerical acceptance and export
----------------------------------------------------

The RF simulator bench supplies an E4438C generator, E4407B analyzer and RSA5100B::

   colosseum run examples/test_rf_sweep.py -g examples/configs/config.rf.visa-sim.toml
   colosseum run examples/test_rf_vector_mod.py -g examples/configs/config.rf.visa-sim.toml

An IQ upload uses the sample format expected by the VSG loader (16-bit
interleaved I/Q for the supplied ``.bin``). RTSA exported bytes have the
receiver's acquisition format; do not assume an exported file can be fed back
to a generator without conversion. Sample clock, RF reference, trigger and
analysis bandwidth are separate settings. ``save_IQ_data`` saves the capture;
``iq.tar`` includes metadata and ``bin`` is raw payload.

For numeric acceptance on the supplied analyzer, place a marker then record
and verify its power::

   col.equipment.speca.single_sweep(speca_id=1)
   col.equipment.speca.set_marker_frequency(speca_id=1, marker=1, frequency_hz=1e9)
   col.equipment.speca.measure_marker_power(speca_id=1, marker=1, key="carrier")
   col.equipment.speca.verify_marker_power(key="carrier", expected_val=-42.5, tolerance=0.5)

The simulator's -42.5 dBm is a canned response. Channel power, ACPR and occupied
bandwidth require their corresponding instrument measurement setup; ordinary
marker power cannot substitute. Generic fetches and named-model exporters can
differ in whether they perform a sweep internally: the E4407B trace exporter
performs a single sweep. See its API/driver notes before correlating trace and
scalar evidence. Mask setup uses the same CWD → parameters-file directory → run
directory lookup order as verification. File exports require artifacts enabled.

Path-loss calibration from a VNA sweep
--------------------------------------

Capture fixture/cable loss on a VNA (S21 or S12), then reuse it on sources and
power measurements. CSV / TXT (``frequency_hz,value`` or headerless
frequency/loss) and Touchstone ``.s2p`` are accepted. Loss is nearest-bin only;
``programmed = desired - loss_db`` and ``corrected = raw - loss_db``::

   col.equipment.vna.set_trace_parameters(vna_id=1, trace=1, parameter="S21", format="MLOG")
   col.equipment.vna.save_trace_data(vna_id=1, path="vna/s21.csv", parameter="S21")
   col.equipment.load_calibration(filename="outputs/.../vna/s21.csv", key="fixture_a")
   col.equipment.vsg.set_frequency(vsg_id=1, frequency=1e9)
   col.equipment.vsg.set_power(vsg_id=1, power_dbm=0.0, calibration="fixture_a")
   # Retune instrument power so post-cal 0 dBm is held at the new frequency:
   col.equipment.vsg.set_frequency(vsg_id=1, frequency=2e9, calibration="fixture_a")
   col.equipment.speca.save_trace_data(speca_id=1, path="traces/dut.csv", calibration="fixture_a")

``set_power(..., calibration=)`` stores the desired post-path level.
``set_frequency(..., calibration=)`` on ASG/VSG requires that prior desired
level. SpecA / power-meter frequency setters only bind the lookup frequency;
measure and trace APIs subtract loss when ``calibration=`` is passed.

VNA and phase-noise results
---------------------------

A supported VNA recipe configures a trace before sweeping. For ``rohde-znb``
use the matching ``equipment.vna`` row::

   col.equipment.vna.set_start_frequency(vna_id=1, frequency_hz=1e9)
   col.equipment.vna.set_stop_frequency(vna_id=1, frequency_hz=2e9)
   col.equipment.vna.set_trace_parameters(vna_id=1, trace=1, parameter="S11", format="MLOG")
   col.equipment.vna.single_sweep(vna_id=1)
   col.equipment.vna.wait_complete(vna_id=1)
   col.equipment.vna.set_marker(vna_id=1, marker=1, frequency_hz=1.5e9, trace=1)
   col.equipment.vna.measure_marker_value(vna_id=1, marker=1, key="s11_db")
   col.equipment.vna.verify_marker_value(key="s11_db", expected_val=-20.0, tolerance=2.0)
   col.equipment.vna.save_trace_data(vna_id=1, trace=1, parameter="S11", file_format="csv", path="vna/s11.csv")

The marker is explicitly placed at 1.5 GHz before the scalar readback. The
example accepts -20 +/- 2 dB in MLOG format; tailor that limit to the DUT.
Negative S11 log magnitude and positive return loss have opposite signs.
``measure_s_parameter`` performs a new single sweep and returns the peak of the
formatted trace as one scalar. Its units depend on ``format``; it is neither a
complex S-parameter array nor automatically a value at your chosen frequency.
Use the explicit marker workflow for a frequency-specific check. Trace export
also performs a sweep, so its capture can differ from the earlier marker read.
A CSV is not a calibrated Touchstone network. Record calibration kit,
reference plane and state outside the trace as appropriate. ``anritsu-541xx``
has explicit export/operation limitations; another model's sequence is not
automatically portable to it.

For ``rohde-fswp`` phase noise, configure carrier and offset interval, initiate,
wait and then read/export::

   col.equipment.phasenoiseanalyzer.set_carrier_frequency_hz(phasenoiseanalyzer_id=1, frequency_hz=1e9)
   col.equipment.phasenoiseanalyzer.set_offset_start_hz(phasenoiseanalyzer_id=1, offset_hz=100.0)
   col.equipment.phasenoiseanalyzer.set_offset_stop_hz(phasenoiseanalyzer_id=1, offset_hz=1e6)
   col.equipment.phasenoiseanalyzer.initiate(phasenoiseanalyzer_id=1)
   col.equipment.phasenoiseanalyzer.wait_complete(phasenoiseanalyzer_id=1, timeout_s=120.0)
   col.equipment.phasenoiseanalyzer.measure_integrated_jitter_s(phasenoiseanalyzer_id=1, start_hz=100.0, stop_hz=1e6, key="jitter")
   col.equipment.phasenoiseanalyzer.save_trace_data(phasenoiseanalyzer_id=1, path="phase_noise/trace.csv")

Jitter is seconds integrated over a stated offset interval; spot phase noise is
dBc/Hz at an offset. Preserve those settings with evidence. An instrument/driver
that rejects explicit integration bounds cannot be assumed to have used them.

Routing, digital I/O and diagnostics
------------------------------------

Attenuator settling matters before the next RF reading::

   col.equipment.attn.set_attenuation_db(attn_id=1, channel=1, attenuation_db=10.0, settle_s=0.05)
   col.equipment.attn.measure_attenuation_db(attn_id=1, channel=1, key="attenuation")
   col.equipment.attn.verify_attenuation_db(key="attenuation", expected_val=10.0, tolerance=0.25)

Choose the channel/range/step supported by the model (for example ``adaura-r3``).
Read ``measure_min_attenuation_db``, ``measure_max_attenuation_db`` and
``measure_step_db`` when validating a sweep; do not round a requested value
silently in your test.

An RF switch path is a model-defined route, not an attenuation setting. For
``minicircuits-rc`` select a documented switch/state, settle, then
``measure_path`` and compare the normalized route text. ``set_path(path=...)``
accepts a routing string appropriate to the configured driver. Relay operations
similarly need known wiring: use ``set_relay`` / ``measure_relay`` for one
channel, ``set_all`` / ``measure_all`` for a bank, or ``pulse_relay`` for a timed
pulse. Declare bank size; a generic bank and ControlByWeb HTTP relay need not
offer the same operations. See :doc:`io_digital` for DIO pin setup, pulls and
backend restrictions, and :doc:`serial_ports` for line/block serial I/O.

For a known two-switch Mini-Circuits unit whose ``SWPORT?`` reports both A and
B states, this recipe selects A=1/B=0 and compares normalized readback (install
shared for the text comparison)::

   col.equipment.rfswitch.set_path(rfswitch_id=1, path="A=1;B=0", wait_settle_s=0.05)
   col.equipment.rfswitch.measure_path(rfswitch_id=1, key="rf_route")
   col.shared.verify.verify_field(key="rf_route", expected_val="A=1;B=0")

For a relay with a supported channel 1, energize, read back and restore it::

   try:
       col.equipment.relay.set_relay(relay_id=1, channel=1, enabled=True)
       col.equipment.relay.measure_relay(relay_id=1, channel=1, key="relay_closed")
       col.shared.verify.verify_field(key="relay_closed", expected_val=True)
   finally:
       col.equipment.relay.set_relay(relay_id=1, channel=1, enabled=False)

SCPI diagnostics are procedural reads, and some are destructive::

   col.equipment.scpi.status_byte(psu_id=1)
   col.equipment.scpi.esr(psu_id=1)
   col.equipment.scpi.drain_error_queue(psu_id=1, max_errors=10)

``esr`` reads and clears the event register; draining the error queue removes
entries. Capture these before ``clear_status`` when the error history matters.
Use exactly one target ID. These calls do not replace numerical acceptance.

GNSS freshness and acquisition
------------------------------

Use a receiver-specific ``equipment.gnss`` row (``port``/``baudrate`` for serial
or the supported VISA SOCKET resource), an antenna/signal, and enabled position
messages. A fix-dependent scalar flow is::

   col.equipment.gnss.mark_acquisition_start(gnss_id=1)
   col.equipment.gnss.wait_for_fix(gnss_id=1, timeout_s=60.0)
   col.equipment.gnss.measure_hdop(gnss_id=1, max_age_s=5.0, key="hdop")
   col.equipment.gnss.verify_hdop(key="hdop", limit=2.0)
   col.equipment.gnss.measure_satellites(gnss_id=1, max_age_s=5.0, key="satellites")

``cold_start`` deliberately changes receiver navigation state; use it instead
of merely marking T0 only when testing a cold acquisition. Missing/stale data
is an error, not a usable zero or an old fix. Background logging, continuity
summaries and plot exports are described in the driver notes. Listener threads
record epochs with ``enqueue_measurement``; finalize drains that queue before
the database closes, so the rows are durable in ``execution.sqlite``. This
requires ``colosseum-core>=0.17.1`` (the write queue is not in tagged 0.17.0).
Epoch identity is ``(equipment, track_epoch, logging key, row_index)``.
``@measurement`` values that are ``bytes`` are returned unchanged and stored as
``{"encoding": "hex", "data": "...", "nbytes": N}``.

``save_config`` exports supported u-blox CFG data or driver-managed NovAtel/
Septentrio log/stream settings. It is not a complete receiver backup. Stop
logging before load/save and preserve arbitrary configuration scripts yourself.

Autoconfig
----------

``col.equipment.autoconfig()`` scans the actual bench and can apply discovered
configuration. To review a reusable file, pass ``export_path="config.toml"``
and inspect model, resource and assigned IDs before writing acceptance tests.
Do not run discovery in offline documentation checks. An explicit config gives
stable IDs across benches and avoids accidentally selecting a different device.
