"""Real-time spectrum analyzer APIs exposed as ``col.equipment.rtsa``.

Configure instruments with ``[equipment.rtsa]`` in bench TOML (``rtsa_id``, ``resource``,
optional ``model`` and ``driver``; default driver is VISA/SCPI). IQ capture files are written
under the active run output directory and registered as artifacts.

Configured IDs select bench TOML rows. Core records command and measurement
outcomes and applies its standard optional-failure handling. Unsupported model
operations raise ``EquipmentCapabilityError``; transport failures raise
``EquipmentConnectionError``.
Operation-specific validation and acquisition constraints are described below.

Commands with an ``EquipmentId`` parameter also accept ``"all"``: targets run
sequentially and failures aggregate. Measurements require numeric IDs.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any
from uuid import uuid4

from colosseum.decorators import command, measurement
from colosseum.logging import get_logger

from colosseum_equipment import calibration as _cal
from colosseum_equipment._paths import resolve_artifact_path
from colosseum_equipment.api._broadcast import EquipmentId, broadcastable, require_int_id
from colosseum_equipment.connections import get_cached_instrument
from colosseum_equipment.evidence import record_artifact
from colosseum_equipment.exceptions import EquipmentResponseError
from colosseum_equipment.instruments.speca.bandwidth import BandwidthMethod, RefPowerMethod, bandwidth_edges_hz
from colosseum_equipment.instruments.speca.trace_csv import read_trace_power_at_frequency
from colosseum_equipment.instruments.speca.trace_plot import _write_trace_plot, read_trace_csv, write_trace_plot

_logger = get_logger("colosseum.equipment")


def _band_edges(
    *, rtsa_id: int, start_hz: float, stop_hz: float, key: str,
    threshold_db: float | None, smoothing_order: int, trace: int, trace_path: str | None,
    method: BandwidthMethod | None, occupied_power_pct: float | None,
    save_plot: bool, ref_pwr_meas_method: RefPowerMethod, center: bool,
) -> tuple[float, float]:
    path = _spectrum_path(rtsa_id, trace, trace_path)
    frequencies, amplitudes = read_trace_csv(path)
    left, right = bandwidth_edges_hz(
        frequencies, amplitudes, start_hz=start_hz, stop_hz=stop_hz,
        threshold_db=threshold_db, smoothing_order=smoothing_order, method=method,
        occupied_power_pct=occupied_power_pct, ref_pwr_meas_method=ref_pwr_meas_method,
    )
    if save_plot:
        kind = "center_frequency" if center else "bandwidth"
        token = uuid4().hex
        png = resolve_artifact_path(f"plots/rtsa_{kind}_{token}.png")
        _write_trace_plot(
            frequencies, amplitudes, png,
            center_hz=(left + right) / 2 if center else None,
            edges_hz=None if center else (left, right),
        )
        record_artifact(
            domain="equipment", command=f"rtsa_{kind}_plot", key=f"{key}_plot_{token}", path=png,
            value={"source_key": key, "source_trace": str(path), "method": method or "threshold",
                   "left_hz": left, "right_hz": right},
        )
    return left, right


def _spectrum_path(rtsa_id: int, trace: int, trace_path: str | None) -> Path:
    require_int_id(rtsa_id, kind="rtsa")
    if trace_path is not None:
        return resolve_artifact_path(trace_path)
    inst = get_cached_instrument("rtsa", rtsa_id)
    return Path(inst._acquire_spectrum_trace(f"traces/rtsa_{rtsa_id}_{uuid4().hex}.csv", trace=trace))


@command
@broadcastable("rtsa", "rtsa_id")
def abort(*, rtsa_id: EquipmentId) -> None:
    """Cancel an in-progress acquisition.

    :param rtsa_id: Configured ``equipment.rtsa`` ID.
    """
    _logger.info("Aborting acquisition on RTSA %s", rtsa_id)
    get_cached_instrument("rtsa", require_int_id(rtsa_id, kind="rtsa")).abort()


@command
def acquire(*, rtsa_id: int, timeout_s: float = 60.0) -> str:
    """Run a single acquisition and wait; returns an acquisition id string.

    :param rtsa_id: Configured ``equipment.rtsa`` ID.

    :param timeout_s: Maximum wait time in seconds.

    :returns: Acquisition id for correlation with saved artifacts.
    :rtype: str
    """
    _logger.info("Acquiring spectrum on RTSA %s", rtsa_id)
    return str(get_cached_instrument("rtsa", require_int_id(rtsa_id, kind="rtsa")).acquire(timeout_s=timeout_s))


@command
@broadcastable("rtsa", "rtsa_id")
def align_all(*, rtsa_id: EquipmentId) -> None:
    """Run internal self-alignment on a supported analyzer and wait for its result.

    :param rtsa_id: Configured ``equipment.rtsa`` ID or ``"all"``.
    """
    _logger.info("Running internal alignment on RTSA %s", rtsa_id)
    get_cached_instrument("rtsa", require_int_id(rtsa_id, kind="rtsa")).align_all()


@command
def capture_iq(
    *,
    rtsa_id: int,
    center_hz: float,
    span_hz: float,
    bandwidth_hz: float,
    seconds: float,
    path: str,
    file_format: str = "mat",
    sample_format: str = "f32",
    endianness: str = "little",
    timeout_s: float = 120.0,
    key: str = "",
) -> dict[str, Any]:
    """Acquire one length-mode IQ record and write decoded samples to ``path``.

    ``bandwidth_hz`` is the IQ acquisition bandwidth, not spectrum resolution
    bandwidth. Supported models (for example ``tektronix-rsa5100b`` and
    ``tektronix-rsa5115b``) set up an IQ vs Time measurement, wait for
    completion, decode the wire samples, and export them. USB RSA306/500A/600A
    models acquire a finite block through the direct RSA API. Their sample rate
    follows the requested IQ bandwidth; spectrum span is configured separately.

    :param rtsa_id: Configured ``equipment.rtsa`` ID.

    :param center_hz: Center frequency in hertz.

    :param span_hz: Frequency span in hertz.

    :param bandwidth_hz: IQ acquisition bandwidth in hertz.

    :param seconds: Acquisition duration in seconds.

    :param path: Relative path under the active run output directory.

    :param file_format: Container: ``mat``, ``bin``, or ``iq.tar``.

    :param sample_format: Sample encoding: ``f32`` (default), ``i16``, or ``c64``.

    :param endianness: Binary payload byte order, ``little`` (default) or ``big``.
        Big-endian applies to ``bin`` and ``iq.tar``; MATLAB stores complex samples.

    :param timeout_s: Maximum wait for acquisition and transfer.

    :param key: Evidence key (default ``rtsa_capture_iq_<run>``).

    :returns: JSON-safe metadata including ``sample_rate_hz``, ``num_samples``,
        ``path``, ``sample_format``, and ``peak`` when ``sample_format`` is ``i16``.
    :rtype: dict

    :raises EquipmentTimeoutError: Acquisition or transfer did not complete in time.
    :raises EquipmentResponseError: Unsupported ``sample_format`` or bad instrument reply.
    """
    _logger.info(
        "Capturing IQ on RTSA %s at %s Hz span %s Hz for %s s to %s",
        rtsa_id,
        center_hz,
        span_hz,
        seconds,
        path,
    )
    return dict(
        get_cached_instrument("rtsa", require_int_id(rtsa_id, kind="rtsa")).capture_iq(
            center_hz=center_hz,
            span_hz=span_hz,
            bandwidth_hz=bandwidth_hz,
            seconds=seconds,
            path=path,
            file_format=file_format,
            sample_format=sample_format, endianness=endianness,
            timeout_s=timeout_s,
            key=key,
        ),
    )


@command
def get_num_samples(*, rtsa_id: int) -> int:
    """Read the configured IQ sample count.

    :param rtsa_id: Configured ``equipment.rtsa`` ID.

    :returns: Configured IQ sample count.
    :rtype: int
    """
    _logger.info("Reading sample count from RTSA %s", rtsa_id)
    return int(get_cached_instrument("rtsa", require_int_id(rtsa_id, kind="rtsa")).get_num_samples())


@measurement
def measure_bw(
    *, rtsa_id: int, start_hz: float, stop_hz: float, key: str,
    threshold_db: float | None = None, smoothing_order: int = 0, trace: int = 1,
    trace_path: str | None = None, method: BandwidthMethod | None = None,
    occupied_power_pct: float | None = None, save_plot: bool = False,
    ref_pwr_meas_method: RefPowerMethod = "max",
) -> float:
    """Measure spectrum bandwidth in hertz using the same analysis as ``speca.measure_bw``.

    :param rtsa_id: Configured RTSA ID.
    :param start_hz: Lower analysis bound in hertz.
    :param stop_hz: Upper analysis bound in hertz.
    :param key: Measurement key for parameter overrides and result recording.
    :param threshold_db: Drop below the reference; default 3 dB. Exclusive with method.
    :param smoothing_order: Moving-average half-window, default zero.
    :param trace: Live spectrum trace, default 1.
    :param trace_path: Prior run-relative CSV; bypasses all hardware access.
    :param method: FWHM, occupied_power, or half_prominence (lowercase names).
    :param occupied_power_pct: Enclosed power percentage, default 99 for occupied_power.
    :param save_plot: Save an annotated plot of the analyzed data, marking both edges.
    :param ref_pwr_meas_method: max, mean, or median reference for threshold analysis.
    """
    _logger.info("Measuring bandwidth on RTSA %s", rtsa_id)
    left, right = _band_edges(
        rtsa_id=rtsa_id, start_hz=start_hz, stop_hz=stop_hz, key=key,
        threshold_db=threshold_db, smoothing_order=smoothing_order, trace=trace, trace_path=trace_path,
        method=method, occupied_power_pct=occupied_power_pct, save_plot=save_plot,
        ref_pwr_meas_method=ref_pwr_meas_method, center=False,
    )
    return right - left


@measurement
def measure_center_frequency_hz(
    *, rtsa_id: int, start_hz: float, stop_hz: float, key: str,
    threshold_db: float | None = None, smoothing_order: int = 0, trace: int = 1,
    trace_path: str | None = None, method: BandwidthMethod | None = None,
    occupied_power_pct: float | None = None, save_plot: bool = False,
    ref_pwr_meas_method: RefPowerMethod = "max",
) -> float:
    """Measure the midpoint of spectrum band edges in hertz.

    Arguments and defaults match :func:`measure_bw`. ``save_plot`` marks the
    identified center on the analyzed trace. A supplied CSV avoids hardware access;
    otherwise one spectrum is acquired for analysis and plotting together.

    :param rtsa_id: Configured RTSA ID.
    :param start_hz: Lower analysis bound in hertz.
    :param stop_hz: Upper analysis bound in hertz.
    :param key: Measurement key for parameter overrides and result recording.
    :param threshold_db: Drop below the reference; default 3 dB. Exclusive with method.
    :param smoothing_order: Moving-average half-window, default zero.
    :param trace: Live spectrum trace, default 1.
    :param trace_path: Prior run-relative CSV; bypasses all hardware access.
    :param method: FWHM, occupied_power, or half_prominence (lowercase names).
    :param occupied_power_pct: Enclosed power percentage, default 99 for occupied_power.
    :param save_plot: Save an annotated plot of the analyzed data, marking the center on the source trace.
    :param ref_pwr_meas_method: max, mean, or median reference for threshold analysis.
    """
    _logger.info("Measuring center frequency on RTSA %s", rtsa_id)
    left, right = _band_edges(
        rtsa_id=rtsa_id, start_hz=start_hz, stop_hz=stop_hz, key=key,
        threshold_db=threshold_db, smoothing_order=smoothing_order, trace=trace, trace_path=trace_path,
        method=method, occupied_power_pct=occupied_power_pct, save_plot=save_plot,
        ref_pwr_meas_method=ref_pwr_meas_method, center=True,
    )
    return (left + right) / 2


@measurement
def measure_sample_rate(*, rtsa_id: int, key: str) -> float:
    """Read and record the instrument's IQ sample rate in samples per second.

    Tek SCPI reads the first record of a completed acquisition, as
    :func:`capture_iq` does. Tek USB and Spike read the IQ sample rate from
    the instrument. For replaying a previously saved waveform, use the rate
    stored in that capture's metadata.

    :param rtsa_id: Configured RTSA ID.
    :param key: Measurement key for result recording.
    :returns: IQ sample rate in samples per second.
    :raises EquipmentCapabilityError: Model does not support IQ rate readback.
    :raises EquipmentResponseError: Instrument reported an invalid rate or no IQ record.
    """
    _ = key
    inst = get_cached_instrument("rtsa", require_int_id(rtsa_id, kind="rtsa"))
    rate = float(inst.measure_sample_rate())
    if not math.isfinite(rate) or rate <= 0:
        raise EquipmentResponseError("Invalid IQ sample rate")
    _logger.info("RTSA %s IQ sample rate: %s samples/s", rtsa_id, rate)
    return rate


@measurement
def measure_trace_power_at_frequency(
    *, rtsa_id: int, frequency_hz: float, key: str, trace_path: str | None = None,
    calibration: str | None = None, trace: int = 1,
) -> float:
    """Measure power in dBm at the nearest spectrum bin, optionally path-corrected.

    :param rtsa_id: Configured RTSA ID.
    :param frequency_hz: Requested frequency in hertz.
    :param key: Measurement key for recording and parameter overrides.
    :param trace_path: Prior run-relative CSV; otherwise acquire one spectrum.
    :param calibration: Loaded calibration key; evaluated at the selected bin.
    :param trace: Live trace number, default 1.
    """
    _logger.info("Measuring RTSA %s trace power at %s Hz", rtsa_id, frequency_hz)
    _ = key
    path = _spectrum_path(rtsa_id, trace, trace_path)
    power, actual_hz = read_trace_power_at_frequency(path, frequency_hz)
    return power if calibration is None else _cal.correct_power_dbm(power, key=calibration, frequency_hz=actual_hz)


@command
def peak_search(*, rtsa_id: int, marker: int = 1) -> None:
    """Run a spectrum peak search (Tek RSA5100B and similar).

    :param rtsa_id: Configured ``equipment.rtsa`` ID.

    :param marker: Marker number (1-based).
    """
    _logger.info("Searching for peak on RTSA %s marker %s", rtsa_id, marker)
    get_cached_instrument("rtsa", require_int_id(rtsa_id, kind="rtsa")).peak_search(marker)


@command
@broadcastable("rtsa", "rtsa_id")
def preset(*, rtsa_id: EquipmentId) -> None:
    """Load the instrument preset (factory default state).

    :param rtsa_id: Configured ``equipment.rtsa`` ID.
    """
    _logger.info("Presetting RTSA %s", rtsa_id)
    get_cached_instrument("rtsa", require_int_id(rtsa_id, kind="rtsa")).preset()


@command
@broadcastable("rtsa", "rtsa_id")
def run(*, rtsa_id: EquipmentId) -> None:
    """Start or arm a single acquisition (non-blocking on generic models).

    :param rtsa_id: Configured ``equipment.rtsa`` ID.
    """
    _logger.info("Running RTSA %s", rtsa_id)
    get_cached_instrument("rtsa", require_int_id(rtsa_id, kind="rtsa")).run()


@command
def save_IQ_data(*, rtsa_id: int, path: str, file_format: str = "bin", key: str = "") -> None:
    """Download IQ data as ``bin``, ``mat``, or ``iq.tar`` under the run directory.

    Generic drivers write an opaque instrument binary block. Native adapters
    may decode samples; USB RSA writes interleaved little-endian float64 IQ.
    For decoded length-mode IQ records with ``f32`` / ``i16`` / ``c64`` encodings,
    use :func:`capture_iq`.

    :param rtsa_id: Configured ``equipment.rtsa`` ID.

    :param path: Relative path under the active run output directory.

    :param file_format: Export format: ``bin``, ``mat``, or ``iq.tar``.

    :param key: Evidence key (default ``rtsa_iq_<run>``).
    """
    _logger.info("Saving IQ data from RTSA %s to %s", rtsa_id, path)
    get_cached_instrument("rtsa", require_int_id(rtsa_id, kind="rtsa")).save_IQ_data(
        path,
        file_format=file_format,
        key=key,
    )


@command
def save_spectrum_trace_data(
    *, rtsa_id: int, path: str, trace: int = 1, save_plot: bool = False, key: str = "",
) -> None:
    """Export a non-IQ spectrum trace CSV (Tek RSA5100B workflow).

    :param rtsa_id: Configured ``equipment.rtsa`` ID.

    :param path: Relative path under the run output directory.

    :param trace: Trace number (1-based).
    :param key: Artifact evidence key.
    :param save_plot: Save a PNG of the exported CSV without another acquisition.

    Exports the current spectrum. Acquire it first using the appropriate RTSA command.
    Live measurements explicitly acquire one spectrum before analysis.
    """
    _logger.info("Saving trace data from RTSA %s to %s", rtsa_id, path)
    artifact = get_cached_instrument("rtsa", require_int_id(rtsa_id, kind="rtsa")).save_spectrum_trace_data(
        path, trace=trace, key=key,
    )
    if save_plot:
        png = Path(artifact).with_suffix(".png")
        write_trace_plot(Path(artifact), png)
        record_artifact(domain="equipment", command="rtsa_spectrum_plot", key=key or f"rtsa_trace_{trace}", path=png)


@command
@broadcastable("rtsa", "rtsa_id")
def set_acq_time(*, rtsa_id: EquipmentId, seconds: float) -> None:
    """Set acquisition time in seconds.

    :param rtsa_id: Configured ``equipment.rtsa`` ID.

    :param seconds: Acquisition duration in seconds.
    """
    _logger.info("Setting acquisition time on RTSA %s to %s s", rtsa_id, seconds)
    get_cached_instrument("rtsa", require_int_id(rtsa_id, kind="rtsa")).set_acq_time(seconds)


@command
@broadcastable("rtsa", "rtsa_id")
def set_attenuation_db(*, rtsa_id: EquipmentId, attenuation_db: float) -> None:
    """Set input attenuation in dB; disable automatic attenuation first.

    :param rtsa_id: Configured RTSA ID, or ``"all"``.
    :param attenuation_db: Requested setting.
    """
    _logger.info("RTSA %s: set_attenuation_db %s", rtsa_id, attenuation_db)
    get_cached_instrument("rtsa", require_int_id(rtsa_id, kind="rtsa")).set_attenuation_db(attenuation_db)


@command
@broadcastable("rtsa", "rtsa_id")
def set_auto_attenuation(*, rtsa_id: EquipmentId, enabled: bool) -> None:
    """Enable or disable automatic input attenuation.

    :param rtsa_id: Configured RTSA ID, or ``"all"``.
    :param enabled: Requested setting.
    """
    _logger.info("RTSA %s: set_auto_attenuation %s", rtsa_id, enabled)
    get_cached_instrument("rtsa", require_int_id(rtsa_id, kind="rtsa")).set_auto_attenuation(enabled)


@command
@broadcastable("rtsa", "rtsa_id")
def set_bandwidth(*, rtsa_id: EquipmentId, bandwidth_hz: float) -> None:
    """Legacy model-dependent bandwidth setting in hertz.

    Tek and generic drivers set spectrum RBW; Spike sets IQ IF bandwidth.
    Prefer :func:`set_rbw` or :func:`set_iq_bandwidth` in new scripts.

    :param rtsa_id: Configured ``equipment.rtsa`` ID.

    :param bandwidth_hz: Bandwidth in hertz, with the legacy model-specific meaning.
    """
    _logger.info("Setting bandwidth on RTSA %s to %s Hz", rtsa_id, bandwidth_hz)
    get_cached_instrument("rtsa", require_int_id(rtsa_id, kind="rtsa")).set_bandwidth(bandwidth_hz)


@command
@broadcastable("rtsa", "rtsa_id")
def set_center_freq(*, rtsa_id: EquipmentId, frequency_hz: float) -> None:
    """Set spectrum center frequency in hertz.

    :param rtsa_id: Configured ``equipment.rtsa`` ID.

    :param frequency_hz: Center frequency in hertz.
    """
    _logger.info("Setting center frequency on RTSA %s to %s Hz", rtsa_id, frequency_hz)
    get_cached_instrument("rtsa", require_int_id(rtsa_id, kind="rtsa")).set_center_freq(frequency_hz)


@command
@broadcastable("rtsa", "rtsa_id")
def set_continuous_run(*, rtsa_id: EquipmentId, enabled: bool) -> None:
    """Enable or disable continuous acquisition.

    :param rtsa_id: Configured ``equipment.rtsa`` ID.

    :param enabled: ``True`` for continuous run, ``False`` for single-shot.
    """
    _logger.info("%s continuous run on RTSA %s", "Enabling" if enabled else "Disabling", rtsa_id)
    get_cached_instrument("rtsa", require_int_id(rtsa_id, kind="rtsa")).set_continuous_run(enabled)


@command
@broadcastable("rtsa", "rtsa_id")
def set_iq_bandwidth(*, rtsa_id: EquipmentId, bandwidth_hz: float) -> None:
    """Set IQ acquisition bandwidth in hertz; this may also select the IQ sample rate.

    :param rtsa_id: Configured RTSA ID, or ``"all"``.
    :param bandwidth_hz: Requested setting.
    """
    _logger.info("RTSA %s: set_iq_bandwidth %s", rtsa_id, bandwidth_hz)
    get_cached_instrument("rtsa", require_int_id(rtsa_id, kind="rtsa")).set_iq_bandwidth(bandwidth_hz)


@command
@broadcastable("rtsa", "rtsa_id")
def set_num_samples(*, rtsa_id: EquipmentId, count: int) -> None:
    """Set the number of IQ samples to acquire.

    :param rtsa_id: Configured ``equipment.rtsa`` ID.

    :param count: IQ sample count.
    """
    _logger.info("Setting sample count on RTSA %s to %s", rtsa_id, count)
    get_cached_instrument("rtsa", require_int_id(rtsa_id, kind="rtsa")).set_num_samples(count)


@command
@broadcastable("rtsa", "rtsa_id")
def set_rbw(*, rtsa_id: EquipmentId, rbw: float) -> None:
    """Set spectrum resolution bandwidth in hertz, independently of IQ bandwidth.

    :param rtsa_id: Configured RTSA ID, or ``"all"``.
    :param rbw: Requested setting.
    """
    _logger.info("RTSA %s: set_rbw %s", rtsa_id, rbw)
    get_cached_instrument("rtsa", require_int_id(rtsa_id, kind="rtsa")).set_rbw(rbw)


@command
@broadcastable("rtsa", "rtsa_id")
def set_reference_level(*, rtsa_id: EquipmentId, level_dbm: float) -> None:
    """Set the RF reference level in dBm.

    :param rtsa_id: Configured RTSA ID, or ``"all"``.
    :param level_dbm: Requested setting.
    """
    _logger.info("RTSA %s: set_reference_level %s", rtsa_id, level_dbm)
    get_cached_instrument("rtsa", require_int_id(rtsa_id, kind="rtsa")).set_reference_level(level_dbm)


@command
@broadcastable("rtsa", "rtsa_id")
def set_sample_rate(*, rtsa_id: EquipmentId, sample_rate_hz: float) -> None:
    """Set the IQ sample rate in samples per second where independently supported.

    :param rtsa_id: Configured ``equipment.rtsa`` ID, or ``"all"``.
    :param sample_rate_hz: Finite, positive IQ sample rate in samples per second.
    :raises EquipmentCapabilityError: Independent sample-rate setting is unsupported.

    Spike supports this command. Tektronix IQ rates follow acquisition bandwidth;
    this command does not change bandwidth or resample captured data.
    """
    if not math.isfinite(sample_rate_hz) or sample_rate_hz <= 0:
        raise ValueError("sample rate must be finite and positive")
    _logger.info("Setting IQ sample rate on RTSA %s to %s samples/s", rtsa_id, sample_rate_hz)
    get_cached_instrument("rtsa", require_int_id(rtsa_id, kind="rtsa")).set_sample_rate(sample_rate_hz)


@command
@broadcastable("rtsa", "rtsa_id")
def set_span(*, rtsa_id: EquipmentId, span_hz: float) -> None:
    """Set frequency span in hertz.

    :param rtsa_id: Configured ``equipment.rtsa`` ID.

    :param span_hz: Frequency span in hertz.
    """
    _logger.info("Setting span on RTSA %s to %s Hz", rtsa_id, span_hz)
    get_cached_instrument("rtsa", require_int_id(rtsa_id, kind="rtsa")).set_span(span_hz)


@command
@broadcastable("rtsa", "rtsa_id")
def set_trigger_level(*, rtsa_id: EquipmentId, level_dbm: float) -> None:
    """Set trigger level in dBm.

    :param rtsa_id: Configured ``equipment.rtsa`` ID.

    :param level_dbm: Trigger level in dBm.
    """
    _logger.info("Setting trigger level on RTSA %s to %s dBm", rtsa_id, level_dbm)
    get_cached_instrument("rtsa", require_int_id(rtsa_id, kind="rtsa")).set_trigger_level(level_dbm)


@command
@broadcastable("rtsa", "rtsa_id")
def set_trigger_position(*, rtsa_id: EquipmentId, position_dbm: float) -> None:
    """Set trigger position using the model's native units.

    :param rtsa_id: Configured ``equipment.rtsa`` ID.

    :param position_dbm: Legacy name: percent on USB RSA and Spike; native units on other models.
    """
    _logger.info("Setting trigger position on RTSA %s to %s (native units)", rtsa_id, position_dbm)
    get_cached_instrument("rtsa", require_int_id(rtsa_id, kind="rtsa")).set_trigger_position(position_dbm)


@command
@broadcastable("rtsa", "rtsa_id")
def set_trigger_source(*, rtsa_id: EquipmentId, source: str) -> None:
    """Set trigger source (for example ``INPut``, ``EXTFront``, ``EXTRear``).

    Also supports ``EXTGated`` and ``LINe``.

    :param rtsa_id: Configured ``equipment.rtsa`` ID.

    :param source: Trigger source identifier accepted by the instrument SCPI driver.
    """
    _logger.info("Setting trigger source on RTSA %s to %s", rtsa_id, source)
    get_cached_instrument("rtsa", require_int_id(rtsa_id, kind="rtsa")).set_trigger_source(source)


@command
@broadcastable("rtsa", "rtsa_id")
def toggle_preamp(*, rtsa_id: EquipmentId, enabled: bool) -> None:
    """Enable or disable the RF preamplifier when installed.

    :param rtsa_id: Configured RTSA ID, or ``"all"``.
    :param enabled: Requested setting.
    """
    _logger.info("RTSA %s: toggle_preamp %s", rtsa_id, enabled)
    get_cached_instrument("rtsa", require_int_id(rtsa_id, kind="rtsa")).toggle_preamp(enabled)


@command
def wait_complete(*, rtsa_id: int, timeout_s: float = 60.0) -> None:
    """Block until the current acquisition completes or ``timeout_s`` elapses.

    :param rtsa_id: Configured ``equipment.rtsa`` ID.

    :param timeout_s: Maximum wait time in seconds.

    :raises EquipmentTimeoutError: Acquisition did not complete in time.
    """
    _logger.info("Waiting for RTSA %s acquisition to complete", rtsa_id)
    get_cached_instrument("rtsa", require_int_id(rtsa_id, kind="rtsa")).wait_complete(timeout_s=timeout_s)


@command
@broadcastable("rtsa", "rtsa_id")
def configure_spectrum(*, rtsa_id: EquipmentId) -> None:
    """Explicitly initialize native USB RSA spectrum processing with vendor defaults.

    :param rtsa_id: Configured equipment.rtsa ID; broadcast commands also accept "all".
    """
    from colosseum_equipment.exceptions import EquipmentCapabilityError

    inst = get_cached_instrument("rtsa", require_int_id(rtsa_id, kind="rtsa"))
    configure = getattr(inst, "configure_spectrum", None)
    if not callable(configure):
        raise EquipmentCapabilityError("configure_spectrum is only available for native USB RSA")
    configure()


@command
def acquire_spectrum(*, rtsa_id: int, timeout_s: float = 60.0) -> None:
    """Acquire a native USB RSA spectrum before exporting it.

    :param rtsa_id: Configured equipment.rtsa ID; broadcast commands also accept "all".
    :param timeout_s: Positive acquisition timeout in seconds.
    """
    from colosseum_equipment.exceptions import EquipmentCapabilityError

    inst = get_cached_instrument("rtsa", require_int_id(rtsa_id, kind="rtsa"))
    acquire = getattr(inst, "acquire_spectrum", None)
    if not callable(acquire):
        raise EquipmentCapabilityError("use run/acquire for SCPI spectrum instruments")
    acquire(timeout_s=timeout_s)
