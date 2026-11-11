"""High-level vector/signal generator APIs exposed as ``col.equipment.vsg``.

Configure instruments with ``[equipment.vsg]`` in bench TOML (``vsg_id``,
``resource``, optional ``model`` and ``driver``; default driver is VISA/SCPI).
Unsupported operations on a given ``model`` raise
:class:`~colosseum_equipment.exceptions.EquipmentCapabilityError`.

Configured IDs select bench TOML rows. Core records command and measurement
outcomes and applies its standard optional-failure handling. Unsupported model
operations raise ``EquipmentCapabilityError``; transport failures raise
``EquipmentConnectionError``.
Operation-specific validation and acquisition constraints are described below.

Commands with an ``EquipmentId`` parameter also accept ``"all"``: targets run
sequentially and failures aggregate. Measurements require numeric IDs.
"""

from __future__ import annotations

from colosseum.decorators import command, measurement
from colosseum.logging import get_logger

from colosseum_equipment import calibration as _cal
from colosseum_equipment.api._broadcast import EquipmentId, broadcastable, require_int_id
from colosseum_equipment.api._verify import tolerance_verifier
from colosseum_equipment.connections import get_cached_instrument

_logger = get_logger("colosseum.equipment")


@command
@broadcastable("vsg", "vsg_id")
def set_frequency(*, vsg_id: EquipmentId, frequency: float, calibration: str | None = None) -> None:
    """Set CW output frequency in hertz.

    When ``calibration`` is set, retunes programmed power so the post-cal
    (desired) output level from the last ``set_power(..., calibration=)`` or
    ``play_iq`` is held at the new frequency.

    :param vsg_id: Configured ``equipment.vsg`` ID.

    :param frequency: Output frequency in hertz. A number is hertz; a string may
        use a ``Hz``, ``kHz``, ``MHz``, or ``GHz`` suffix (``1GHz``, ``10 MHz``).

    :param calibration: Key from :func:`colosseum_equipment.api.calibration.load_calibration`.
    """
    _logger.info("Setting frequency on VSG %s to %s Hz", vsg_id, frequency)
    inst = get_cached_instrument("vsg", require_int_id(vsg_id, kind="vsg"))
    inst.set_frequency(frequency)
    _cal.bind_frequency(inst, frequency)
    if calibration is not None:
        desired = _cal.require_desired_power(inst)
        programmed = _cal.programmed_power_dbm(desired, key=calibration, frequency_hz=frequency)
        inst.set_power(programmed)
        _cal.remember_desired_power(inst, desired, key=calibration)


@command
@broadcastable("vsg", "vsg_id")
def set_power(*, vsg_id: EquipmentId, power_dbm: float, calibration: str | None = None) -> None:
    """Set output power in dBm.

    With ``calibration``, ``power_dbm`` is the desired post-path level; the
    instrument is programmed to ``power_dbm - loss_db`` at the last-set frequency.

    :param vsg_id: Configured ``equipment.vsg`` ID.

    :param power_dbm: Output power in dBm (post-cal desired when ``calibration`` is set).

    :param calibration: Key from :func:`colosseum_equipment.api.calibration.load_calibration`.
    """
    _logger.info("Setting output power on VSG %s to %s dBm", vsg_id, power_dbm)
    inst = get_cached_instrument("vsg", require_int_id(vsg_id, kind="vsg"))
    if calibration is None:
        _cal.clear_desired_power(inst)
        inst.set_power(power_dbm)
        return
    frequency = _cal.require_frequency(inst, what="set_power")
    programmed = _cal.programmed_power_dbm(power_dbm, key=calibration, frequency_hz=frequency)
    inst.set_power(programmed)
    _cal.remember_desired_power(inst, power_dbm, key=calibration)


@command
@broadcastable("vsg", "vsg_id")
def set_output(*, vsg_id: EquipmentId, enabled: bool) -> None:
    """Enable or disable RF output.

    :param vsg_id: Configured ``equipment.vsg`` ID.

    :param enabled: ``True`` to enable RF output, ``False`` to disable.
    """
    _logger.info("%s RF output on VSG %s", "Enabling" if enabled else "Disabling", vsg_id)
    get_cached_instrument("vsg", require_int_id(vsg_id, kind="vsg")).set_output(enabled)


@command
@broadcastable("vsg", "vsg_id")
def preset(*, vsg_id: EquipmentId) -> None:
    """Return the instrument to a default preset state.

    :param vsg_id: Configured ``equipment.vsg`` ID.
    """
    _logger.info("Presetting VSG %s", vsg_id)
    get_cached_instrument("vsg", require_int_id(vsg_id, kind="vsg")).preset()


@command
def wait_complete(*, vsg_id: int) -> None:
    """Block until pending instrument operations complete (*OPC?*).

    :param vsg_id: Configured ``equipment.vsg`` ID.
    """
    _logger.info("Waiting for VSG %s operation to complete", vsg_id)
    get_cached_instrument("vsg", require_int_id(vsg_id, kind="vsg")).wait_complete()


@command
@broadcastable("vsg", "vsg_id")
def set_alc(*, vsg_id: EquipmentId, enabled: bool) -> None:
    """Enable or disable automatic level control (ALC).

    :param vsg_id: Configured ``equipment.vsg`` ID.

    :param enabled: ``True`` to enable ALC, ``False`` to disable.
    """
    _logger.info("%s ALC on VSG %s", "Enabling" if enabled else "Disabling", vsg_id)
    get_cached_instrument("vsg", require_int_id(vsg_id, kind="vsg")).set_alc(enabled)


@command
@broadcastable("vsg", "vsg_id")
def set_attenuation(*, vsg_id: EquipmentId, attenuation_db: float) -> None:
    """Set output attenuation in dB.

    :param vsg_id: Configured ``equipment.vsg`` ID.

    :param attenuation_db: Output attenuation in dB.
    """
    _logger.info("Setting attenuation on VSG %s to %s dB", vsg_id, attenuation_db)
    get_cached_instrument("vsg", require_int_id(vsg_id, kind="vsg")).set_attenuation(attenuation_db)


@command
@broadcastable("vsg", "vsg_id")
def set_phase(*, vsg_id: EquipmentId, phase_deg: float) -> None:
    """Set RF phase in degrees (vector models).

    :param vsg_id: Configured ``equipment.vsg`` ID.

    :param phase_deg: RF phase in degrees.
    """
    _logger.info("Setting phase on VSG %s to %s degrees", vsg_id, phase_deg)
    get_cached_instrument("vsg", require_int_id(vsg_id, kind="vsg")).set_phase(phase_deg)


@command
@broadcastable("vsg", "vsg_id")
def set_output_blanking(*, vsg_id: EquipmentId, enabled: bool) -> None:
    """Enable or disable output blanking.

    :param vsg_id: Configured ``equipment.vsg`` ID.

    :param enabled: ``True`` to enable output blanking, ``False`` to disable.
    """
    _logger.info("%s output blanking on VSG %s", "Enabling" if enabled else "Disabling", vsg_id)
    get_cached_instrument("vsg", require_int_id(vsg_id, kind="vsg")).set_output_blanking(enabled)


@command
@broadcastable("vsg", "vsg_id")
def upload_waveform(
    *,
    vsg_id: EquipmentId,
    local_path: str,
    remote_name: str,
    first_last_blanking: bool = False,
    method: str = "auto",
) -> None:
    """Upload an IQ waveform to instrument memory (``.bin``, ``.mat``, or ``.iq.tar``).

    Local files are converted to 16-bit interleaved I/Q before upload.
    ``method="auto"`` uses FTP when ``ftp_host`` is set or the VISA resource is
    TCPIP, and otherwise sends one SCPI ``MMEM:DATA`` block. ``method="ftp"``
    always stores the file in ``/USER/BBG1/WAVEFORM`` in 8192-byte blocks and
    draws a progress line on a terminal. ``method="tcpip"`` sends that block in
    one write. A ``TCPIP0::host::5025::SOCKET`` resource is the faster SCPI
    choice; ``inst0::INSTR`` stays near 60 kbit/s because VXI-11 acknowledges
    small payloads. A bench ``upload_method`` is used only when this call leaves
    ``method="auto"``.

    Set ``first_last_blanking=True`` to configure first/last-sample RF blanking
    for IQ loop playback. Call ``play_iq`` with the remote filename after upload.

    Requires a capable ``model`` (for example ``keysight-esg`` with E4438C IDN).

    :param vsg_id: Configured ``equipment.vsg`` ID.

    :param local_path: Path to local ``.bin`` / ``.mat`` / ``.iq.tar`` waveform.

    :param remote_name: Destination filename on the instrument.

    :param first_last_blanking: When True, configure first/last-sample RF blanking for IQ playback.

    :param method: ``auto``, ``ftp``, or ``tcpip``. Call value wins over config ``upload_method``.

    :raises EquipmentResponseError: Unknown method, or TCPIP selected without ``write_raw``.
    """
    _logger.info("Uploading %s to VSG %s as %s", local_path, vsg_id, remote_name)
    get_cached_instrument("vsg", require_int_id(vsg_id, kind="vsg")).upload_waveform(
        local_path,
        remote_name,
        first_last_blanking=first_last_blanking,
        method=method,
    )


@command
@broadcastable("vsg", "vsg_id")
def delete_waveform(*, vsg_id: EquipmentId, remote_name: str) -> None:
    """Delete a waveform and its associated marker/header files from instrument memory.

    :param vsg_id: Configured ``equipment.vsg`` ID.

    :param remote_name: Waveform filename on the instrument to delete.
    """
    _logger.info("Deleting waveform %s from VSG %s", remote_name, vsg_id)
    get_cached_instrument("vsg", require_int_id(vsg_id, kind="vsg")).delete_waveform(remote_name)


@command
@broadcastable("vsg", "vsg_id")
def delete_all_waveforms(*, vsg_id: EquipmentId) -> None:
    """Delete all waveforms from volatile arb memory on the instrument.

    :param vsg_id: Configured ``equipment.vsg`` ID.
    """
    _logger.info("Deleting all waveforms from VSG %s", vsg_id)
    get_cached_instrument("vsg", require_int_id(vsg_id, kind="vsg")).delete_all_waveforms()


@command
@broadcastable("vsg", "vsg_id")
def set_multicarrier(*, vsg_id: EquipmentId, num_tones: int, spacing_hz: float) -> None:
    """Configure multicarrier tone count and frequency spacing in hertz.

    :param vsg_id: Configured ``equipment.vsg`` ID.

    :param num_tones: Number of carrier tones.

    :param spacing_hz: Frequency spacing between tones in hertz.
    """
    _logger.info(
        "Setting multicarrier on VSG %s to %s tones spaced %s Hz",
        vsg_id,
        num_tones,
        spacing_hz,
    )
    get_cached_instrument("vsg", require_int_id(vsg_id, kind="vsg")).set_multicarrier(num_tones, spacing_hz)


@command
@broadcastable("vsg", "vsg_id")
def toggle_multitone(*, vsg_id: EquipmentId, enabled: bool) -> None:
    """Enable or disable multitone arbitrary waveform playback.

    :param vsg_id: Configured ``equipment.vsg`` ID.

    :param enabled: ``True`` to enable multitone playback, ``False`` to disable.
    """
    _logger.info("%s multitone on VSG %s", "Enabling" if enabled else "Disabling", vsg_id)
    get_cached_instrument("vsg", require_int_id(vsg_id, kind="vsg")).toggle_multitone(enabled)


@command
@broadcastable("vsg", "vsg_id")
def play_iq(
    *,
    vsg_id: EquipmentId,
    filename: str,
    center_freq_hz: float,
    amplitude_dbm: float,
    sample_clock_hz: float,
    calibration: str | None = None,
) -> None:
    """Select an uploaded IQ waveform and start playback at the given carrier and sample clock.

    The carrier and amplitude are recorded for a later ``set_power`` or
    ``set_frequency`` that passes ``calibration``. With ``calibration``,
    ``amplitude_dbm`` is the desired post-path level and the instrument is
    programmed to ``amplitude_dbm - loss_db``, the same offset ``set_power`` uses.

    :param vsg_id: Configured ``equipment.vsg`` ID.

    :param filename: Uploaded waveform filename on the instrument.

    :param center_freq_hz: Carrier center frequency in hertz.

    :param amplitude_dbm: Output amplitude in dBm (post-cal desired when ``calibration`` is set).

    :param sample_clock_hz: IQ sample clock rate in hertz.

    :param calibration: Key from :func:`colosseum_equipment.api.calibration.load_calibration`.
    """
    _logger.info(
        "Playing %s on VSG %s at %s Hz and %s dBm",
        filename,
        vsg_id,
        center_freq_hz,
        amplitude_dbm,
    )
    inst = get_cached_instrument("vsg", require_int_id(vsg_id, kind="vsg"))
    programmed = amplitude_dbm
    if calibration is not None:
        programmed = _cal.programmed_power_dbm(
            amplitude_dbm,
            key=calibration,
            frequency_hz=center_freq_hz,
        )
    inst.play_iq(filename, center_freq_hz, programmed, sample_clock_hz)
    _cal.bind_frequency(inst, center_freq_hz)
    _cal.remember_desired_power(inst, amplitude_dbm, key=calibration or "")


@command
@broadcastable("vsg", "vsg_id")
def set_pulsegen_output(*, vsg_id: EquipmentId, enabled: bool) -> None:
    """Enable or disable the internal pulse generator path (Keysight ``PULM:STAT``).

    :param vsg_id: Configured ``equipment.vsg`` ID.

    :param enabled: ``True`` to enable the pulse generator, ``False`` to disable.
    """
    _logger.info("%s pulse generator on VSG %s", "Enabling" if enabled else "Disabling", vsg_id)
    get_cached_instrument("vsg", require_int_id(vsg_id, kind="vsg")).set_pulsegen_output(enabled)


@command
@broadcastable("vsg", "vsg_id")
def set_pulsemod_output(*, vsg_id: EquipmentId, enabled: bool) -> None:
    """Enable or disable pulse modulation.

    :param vsg_id: Configured ``equipment.vsg`` ID.

    :param enabled: ``True`` to enable pulse modulation, ``False`` to disable.
    """
    _logger.info("%s pulse modulation on VSG %s", "Enabling" if enabled else "Disabling", vsg_id)
    get_cached_instrument("vsg", require_int_id(vsg_id, kind="vsg")).set_pulsemod_output(enabled)


@command
@broadcastable("vsg", "vsg_id")
def set_pulse_period(*, vsg_id: EquipmentId, period_s: float) -> None:
    """Set pulse period in seconds.

    :param vsg_id: Configured ``equipment.vsg`` ID.

    :param period_s: Pulse period in seconds.
    """
    _logger.info("Setting pulse period on VSG %s to %s s", vsg_id, period_s)
    get_cached_instrument("vsg", require_int_id(vsg_id, kind="vsg")).set_pulse_period(period_s)


@command
@broadcastable("vsg", "vsg_id")
def set_pulse_width(*, vsg_id: EquipmentId, width_s: float) -> None:
    """Set pulse width in seconds.

    :param vsg_id: Configured ``equipment.vsg`` ID.

    :param width_s: Pulse width in seconds.
    """
    _logger.info("Setting pulse width on VSG %s to %s s", vsg_id, width_s)
    get_cached_instrument("vsg", require_int_id(vsg_id, kind="vsg")).set_pulse_width(width_s)


@command
@broadcastable("vsg", "vsg_id")
def pulse_source(*, vsg_id: EquipmentId, source: str) -> None:
    """Set pulse source to ``PULSE``, ``SQUARE``, ``EXT1``, or ``EXT2``.

    :param vsg_id: Configured ``equipment.vsg`` ID.

    :param source: Pulse source string accepted by the configured model.
    """
    _logger.info("Setting pulse source on VSG %s to %s", vsg_id, source)
    get_cached_instrument("vsg", require_int_id(vsg_id, kind="vsg")).pulse_source(source)


@command
@broadcastable("vsg", "vsg_id")
def step_power(
    *,
    vsg_id: EquipmentId,
    start_dbm: float,
    stop_dbm: float,
    step_db: float,
    interval_s: float,
) -> None:
    """Run a stepped power sweep with the given start, stop, step size, and dwell interval.

    :param vsg_id: Configured ``equipment.vsg`` ID.

    :param start_dbm: Starting power in dBm.

    :param stop_dbm: Stopping power in dBm.

    :param step_db: Power step size in dB.

    :param interval_s: Dwell time at each step in seconds.
    """
    _logger.info(
        "Stepping power on VSG %s from %s dBm to %s dBm by %s dB",
        vsg_id,
        start_dbm,
        stop_dbm,
        step_db,
    )
    get_cached_instrument("vsg", require_int_id(vsg_id, kind="vsg")).step_power(
        start_dbm, stop_dbm, step_db, interval_s,
    )


@command
@broadcastable("vsg", "vsg_id")
def freq_sweep(
    *,
    vsg_id: EquipmentId,
    start_hz: float,
    stop_hz: float,
    points: int,
    dwell_s: float,
) -> None:
    """Run a stepped frequency sweep.

    :param vsg_id: Configured ``equipment.vsg`` ID.

    :param start_hz: Starting frequency in hertz.

    :param stop_hz: Stopping frequency in hertz.

    :param points: Number of frequency steps.

    :param dwell_s: Dwell time at each step in seconds.
    """
    _logger.info(
        "Sweeping frequency on VSG %s from %s Hz to %s Hz (%s points)",
        vsg_id,
        start_hz,
        stop_hz,
        points,
    )
    get_cached_instrument("vsg", require_int_id(vsg_id, kind="vsg")).freq_sweep(start_hz, stop_hz, points, dwell_s)


@command
@broadcastable("vsg", "vsg_id")
def amplitude_sweep(
    *,
    vsg_id: EquipmentId,
    start_dbm: float,
    stop_dbm: float,
    points: int,
    dwell_s: float,
) -> None:
    """Run a stepped amplitude sweep.

    :param vsg_id: Configured ``equipment.vsg`` ID.

    :param start_dbm: Starting amplitude in dBm.

    :param stop_dbm: Stopping amplitude in dBm.

    :param points: Number of amplitude steps.

    :param dwell_s: Dwell time at each step in seconds.
    """
    _logger.info(
        "Sweeping amplitude on VSG %s from %s dBm to %s dBm (%s points)",
        vsg_id,
        start_dbm,
        stop_dbm,
        points,
    )
    get_cached_instrument("vsg", require_int_id(vsg_id, kind="vsg")).amplitude_sweep(
        start_dbm, stop_dbm, points, dwell_s,
    )


@command
@broadcastable("vsg", "vsg_id")
def select_waveform(*, vsg_id: EquipmentId, remote_name: str) -> None:
    """Select a waveform previously stored on the instrument.

    :param vsg_id: Configured ``equipment.vsg`` ID.

    :param remote_name: Waveform filename on the instrument to select.
    """
    _logger.info("Selecting waveform %s on VSG %s", remote_name, vsg_id)
    get_cached_instrument("vsg", require_int_id(vsg_id, kind="vsg")).select_waveform(remote_name)


@command
@broadcastable("vsg", "vsg_id")
def set_arb_state(*, vsg_id: EquipmentId, enabled: bool) -> None:
    """Enable or disable arbitrary waveform generator playback.

    :param vsg_id: Configured ``equipment.vsg`` ID.

    :param enabled: ``True`` to enable arb playback, ``False`` to disable.
    """
    _logger.info("%s arb playback on VSG %s", "Enabling" if enabled else "Disabling", vsg_id)
    get_cached_instrument("vsg", require_int_id(vsg_id, kind="vsg")).set_arb_state(enabled)


@command
@broadcastable("vsg", "vsg_id")
def configure_list(
    *,
    vsg_id: EquipmentId,
    frequencies: list[float],
    powers: list[float] | None = None,
) -> None:
    """Program a frequency (and optional power) list sweep.

    :param vsg_id: Configured ``equipment.vsg`` ID.

    :param frequencies: List of sweep frequencies in hertz.

    :param powers: Optional list of output powers in dBm, one per frequency.
    """
    _logger.info("Configuring list sweep on VSG %s with %s frequencies", vsg_id, len(frequencies))
    get_cached_instrument("vsg", require_int_id(vsg_id, kind="vsg")).configure_list(frequencies, powers)


@command
@broadcastable("vsg", "vsg_id")
def set_modulation(*, vsg_id: EquipmentId, enabled: bool, modulation_type: str = "none") -> None:
    """Enable modulation and set modulation type (model-specific strings).

    :param vsg_id: Configured ``equipment.vsg`` ID.

    :param enabled: ``True`` to enable modulation, ``False`` to disable.

    :param modulation_type: Modulation type string accepted by the configured model.
    """
    _logger.info(
        "%s %s modulation on VSG %s",
        "Enabling" if enabled else "Disabling",
        modulation_type,
        vsg_id,
    )
    get_cached_instrument("vsg", require_int_id(vsg_id, kind="vsg")).set_modulation(enabled, modulation_type)


@measurement
def measure_output_state(*, vsg_id: int, key: str) -> float:
    """Read whether RF output is enabled.

    :param vsg_id: Configured ``equipment.vsg`` ID.

    :param key: Unique measurement key within domain ``equipment`` and this command name.
        Must not collide with another instrument's measurement using the same command name.

    :returns: Measured state as ``1.0`` (on) or ``0.0`` (off).
    :rtype: float
    """
    _logger.info("Reading RF output state from VSG %s", vsg_id)
    _ = key
    enabled = get_cached_instrument("vsg", require_int_id(vsg_id, kind="vsg")).measure_output_state()
    return 1.0 if enabled else 0.0


verify_output_state = tolerance_verifier(
    "measure_output_state", module=__name__,
    name="verify_output_state",
    default_tolerance=0.0,
)


@measurement
def measure_frequency(*, vsg_id: int, key: str) -> float:
    """Read CW output frequency.

    :param vsg_id: Configured ``equipment.vsg`` ID.

    :param key: Unique measurement key within domain ``equipment`` and this command name.
        Must not collide with another instrument's measurement using the same command name.

    :returns: Measured frequency in hertz.
    :rtype: float
    """
    _logger.info("Reading frequency from VSG %s", vsg_id)
    _ = key
    return float(get_cached_instrument("vsg", require_int_id(vsg_id, kind="vsg")).measure_frequency())


verify_frequency = tolerance_verifier(
    "measure_frequency", module=__name__,
    name="verify_frequency",
    default_tolerance=1.0,
)


@measurement
def measure_power_dbm(*, vsg_id: int, key: str, calibration: str | None = None) -> float:
    """Read output power.

    With ``calibration``, subtracts nearest-bin path loss at the last-set frequency
    so the returned value is the post-path level.

    :param vsg_id: Configured ``equipment.vsg`` ID.

    :param key: Unique measurement key within domain ``equipment`` and this command name.
        Must not collide with another instrument's measurement using the same command name.

    :param calibration: Key from :func:`colosseum_equipment.api.calibration.load_calibration`.

    :returns: Measured power in dBm.
    :rtype: float
    """
    _logger.info("Reading output power from VSG %s", vsg_id)
    _ = key
    inst = get_cached_instrument("vsg", require_int_id(vsg_id, kind="vsg"))
    raw = float(inst.measure_power_dbm())
    if calibration is None:
        return raw
    frequency = _cal.require_frequency(inst, what="measure_power_dbm")
    return _cal.correct_power_dbm(raw, key=calibration, frequency_hz=frequency)


verify_power_dbm = tolerance_verifier(
    "measure_power_dbm", module=__name__,
    name="verify_power_dbm",
    default_tolerance=0.5,
)


@command
@broadcastable("vsg", "vsg_id")
def set_arb_sample_clock(*, vsg_id: EquipmentId, sample_clock_hz: float) -> None:
    """Set arbitrary waveform sample clock rate in hertz.

    :param vsg_id: Configured ``equipment.vsg`` ID.

    :param sample_clock_hz: Sample clock in hertz.
    """
    _logger.info("Setting arb sample clock on VSG %s to %s Hz", vsg_id, sample_clock_hz)
    get_cached_instrument("vsg", require_int_id(vsg_id, kind="vsg")).set_arb_sample_clock(sample_clock_hz)


@command
@broadcastable("vsg", "vsg_id")
def set_arb_trigger_source(*, vsg_id: EquipmentId, source: str) -> None:
    """Set ARB playback trigger source.

    :param vsg_id: Configured ``equipment.vsg`` ID.

    :param source: Trigger source string accepted by the configured model.
    """
    _logger.info("Setting arb trigger source on VSG %s to %s", vsg_id, source)
    get_cached_instrument("vsg", require_int_id(vsg_id, kind="vsg")).set_arb_trigger_source(source)


@command
@broadcastable("vsg", "vsg_id")
def arm_arb_trigger(*, vsg_id: EquipmentId) -> None:
    """Arm or force an immediate ARB trigger.

    :param vsg_id: Configured ``equipment.vsg`` ID.
    """
    _logger.info("Arming arb trigger on VSG %s", vsg_id)
    get_cached_instrument("vsg", require_int_id(vsg_id, kind="vsg")).arm_arb_trigger()


@command
@broadcastable("vsg", "vsg_id")
def set_arb_marker_enable(*, vsg_id: EquipmentId, marker: int, enabled: bool) -> None:
    """Enable or disable an ARB marker.

    :param vsg_id: Configured ``equipment.vsg`` ID.

    :param marker: Marker index (1-based on most models).

    :param enabled: ``True`` to enable the marker.
    """
    _logger.info(
        "%s arb marker %s on VSG %s",
        "Enabling" if enabled else "Disabling",
        marker,
        vsg_id,
    )
    get_cached_instrument("vsg", require_int_id(vsg_id, kind="vsg")).set_arb_marker_enable(marker, enabled)


@command
@broadcastable("vsg", "vsg_id")
def set_arb_marker_position(*, vsg_id: EquipmentId, marker: int, sample_index: int) -> None:
    """Set ARB marker position in sample indices.

    :param vsg_id: Configured ``equipment.vsg`` ID.

    :param marker: Marker index.

    :param sample_index: Sample index within the waveform.
    """
    _logger.info("Setting arb marker %s on VSG %s to sample %s", marker, vsg_id, sample_index)
    get_cached_instrument("vsg", require_int_id(vsg_id, kind="vsg")).set_arb_marker_position(marker, sample_index)


@command
@broadcastable("vsg", "vsg_id")
def set_ref_source(*, vsg_id: EquipmentId, source: str) -> None:
    """Set reference oscillator source (for example ``INT`` or ``EXT``).

    :param vsg_id: Configured ``equipment.vsg`` ID.

    :param source: Reference source string accepted by the configured model.
    """
    _logger.info("Setting reference source on VSG %s to %s", vsg_id, source)
    get_cached_instrument("vsg", require_int_id(vsg_id, kind="vsg")).set_ref_source(source)


@measurement
def get_ref_locked(*, vsg_id: int, key: str) -> float:
    """Read whether the reference oscillator is locked.

    :param vsg_id: Configured ``equipment.vsg`` ID.

    :param key: Unique measurement key within domain ``equipment``.

    :returns: ``1.0`` when locked, ``0.0`` otherwise.
    :rtype: float
    """
    _logger.info("Reading reference lock from VSG %s", vsg_id)
    _ = key
    locked = get_cached_instrument("vsg", require_int_id(vsg_id, kind="vsg")).get_ref_locked()
    return 1.0 if locked else 0.0
