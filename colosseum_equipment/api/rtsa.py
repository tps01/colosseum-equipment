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

from typing import Any

from colosseum.decorators import command
from colosseum.logging import get_logger

from colosseum_equipment.api._broadcast import EquipmentId, broadcastable, require_int_id
from colosseum_equipment.connections import get_cached_instrument

_logger = get_logger("colosseum.equipment")


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
def set_center_freq(*, rtsa_id: EquipmentId, frequency_hz: float) -> None:
    """Set spectrum center frequency in hertz.

    :param rtsa_id: Configured ``equipment.rtsa`` ID.

    :param frequency_hz: Center frequency in hertz.
    """
    _logger.info("Setting center frequency on RTSA %s to %s Hz", rtsa_id, frequency_hz)
    get_cached_instrument("rtsa", require_int_id(rtsa_id, kind="rtsa")).set_center_freq(frequency_hz)


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
def set_bandwidth(*, rtsa_id: EquipmentId, bandwidth_hz: float) -> None:
    """Set resolution bandwidth in hertz.

    :param rtsa_id: Configured ``equipment.rtsa`` ID.

    :param bandwidth_hz: Resolution bandwidth in hertz.
    """
    _logger.info("Setting bandwidth on RTSA %s to %s Hz", rtsa_id, bandwidth_hz)
    get_cached_instrument("rtsa", require_int_id(rtsa_id, kind="rtsa")).set_bandwidth(bandwidth_hz)


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
def set_continuous_run(*, rtsa_id: EquipmentId, enabled: bool) -> None:
    """Enable or disable continuous acquisition.

    :param rtsa_id: Configured ``equipment.rtsa`` ID.

    :param enabled: ``True`` for continuous run, ``False`` for single-shot.
    """
    _logger.info("%s continuous run on RTSA %s", "Enabling" if enabled else "Disabling", rtsa_id)
    get_cached_instrument("rtsa", require_int_id(rtsa_id, kind="rtsa")).set_continuous_run(enabled)


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
def get_num_samples(*, rtsa_id: int) -> int:
    """Read the configured IQ sample count.

    :param rtsa_id: Configured ``equipment.rtsa`` ID.

    :returns: Configured IQ sample count.
    :rtype: int
    """
    _logger.info("Reading sample count from RTSA %s", rtsa_id)
    return int(get_cached_instrument("rtsa", require_int_id(rtsa_id, kind="rtsa")).get_num_samples())


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
    """Set trigger position in dBm.

    :param rtsa_id: Configured ``equipment.rtsa`` ID.

    :param position_dbm: Trigger position in dBm.
    """
    _logger.info("Setting trigger position on RTSA %s to %s dBm", rtsa_id, position_dbm)
    get_cached_instrument("rtsa", require_int_id(rtsa_id, kind="rtsa")).set_trigger_position(position_dbm)


@command
@broadcastable("rtsa", "rtsa_id")
def run(*, rtsa_id: EquipmentId) -> None:
    """Start or arm a single acquisition (non-blocking on generic models).

    :param rtsa_id: Configured ``equipment.rtsa`` ID.
    """
    _logger.info("Running RTSA %s", rtsa_id)
    get_cached_instrument("rtsa", require_int_id(rtsa_id, kind="rtsa")).run()


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
def peak_search(*, rtsa_id: int, marker: int = 1) -> None:
    """Run a spectrum peak search (Tek RSA5100B and similar).

    :param rtsa_id: Configured ``equipment.rtsa`` ID.

    :param marker: Marker number (1-based).
    """
    _logger.info("Searching for peak on RTSA %s marker %s", rtsa_id, marker)
    get_cached_instrument("rtsa", require_int_id(rtsa_id, kind="rtsa")).peak_search(marker)


@command
def save_spectrum_trace_data(*, rtsa_id: int, path: str, trace: int = 1) -> None:
    """Export a non-IQ spectrum trace CSV (Tek RSA5100B workflow).

    :param rtsa_id: Configured ``equipment.rtsa`` ID.

    :param path: Relative path under the run output directory.

    :param trace: Trace number (1-based).
    """
    _logger.info("Saving trace data from RTSA %s to %s", rtsa_id, path)
    get_cached_instrument("rtsa", require_int_id(rtsa_id, kind="rtsa")).save_spectrum_trace_data(path, trace=trace)


@command
def save_IQ_data(*, rtsa_id: int, path: str, file_format: str = "bin", key: str = "") -> None:
    """Download IQ data as ``bin``, ``mat``, or ``iq.tar`` under the run directory.

    Writes the opaque instrument binary block (no sample reinterpretation).
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
    timeout_s: float = 120.0,
    key: str = "",
) -> dict[str, Any]:
    """Acquire one length-mode IQ record and write decoded samples to ``path``.

    ``bandwidth_hz`` is the IQ acquisition bandwidth, not spectrum resolution
    bandwidth. Supported models (for example ``tektronix-rsa5100b`` and
    ``tektronix-rsa5115b``) set up an IQ vs Time measurement, wait for
    completion, decode the wire samples, and export them.

    :param rtsa_id: Configured ``equipment.rtsa`` ID.

    :param center_hz: Center frequency in hertz.

    :param span_hz: Frequency span in hertz.

    :param bandwidth_hz: IQ acquisition bandwidth in hertz.

    :param seconds: Acquisition duration in seconds.

    :param path: Relative path under the active run output directory.

    :param file_format: Container: ``mat``, ``bin``, or ``iq.tar``.

    :param sample_format: Sample encoding: ``f32`` (default), ``i16``, or ``c64``.

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
            sample_format=sample_format,
            timeout_s=timeout_s,
            key=key,
        ),
    )
