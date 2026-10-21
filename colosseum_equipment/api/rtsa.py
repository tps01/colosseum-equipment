"""Real-time spectrum analyzer APIs exposed as ``col.equipment.rtsa``.

Configure instruments with ``[equipment.rtsa]`` in bench TOML (``rtsa_id``, ``resource``,
optional ``model`` and ``driver``; default driver is VISA/SCPI). IQ capture files are written
under the active run output directory and registered as artifacts.
"""

from __future__ import annotations

from typing import Any

from colosseum.decorators import command

from colosseum_equipment.connections import get_cached_instrument


@command
def preset(*, rtsa_id: int) -> None:
    """Load the instrument preset (factory default state).

    :param rtsa_id: Configured ``equipment.rtsa`` id from bench TOML.
    :type rtsa_id: int

    :returns: None

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    get_cached_instrument("rtsa", rtsa_id).preset()


@command
def set_center_freq(*, rtsa_id: int, frequency_hz: float) -> None:
    """Set spectrum center frequency in hertz.

    :param rtsa_id: Configured ``equipment.rtsa`` id from bench TOML.
    :type rtsa_id: int
    :param frequency_hz: Center frequency in hertz.
    :type frequency_hz: float

    :returns: None

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    get_cached_instrument("rtsa", rtsa_id).set_center_freq(frequency_hz)


@command
def set_span(*, rtsa_id: int, span_hz: float) -> None:
    """Set frequency span in hertz.

    :param rtsa_id: Configured ``equipment.rtsa`` id from bench TOML.
    :type rtsa_id: int
    :param span_hz: Frequency span in hertz.
    :type span_hz: float

    :returns: None

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    get_cached_instrument("rtsa", rtsa_id).set_span(span_hz)


@command
def set_bandwidth(*, rtsa_id: int, bandwidth_hz: float) -> None:
    """Set resolution bandwidth in hertz.

    :param rtsa_id: Configured ``equipment.rtsa`` id from bench TOML.
    :type rtsa_id: int
    :param bandwidth_hz: Resolution bandwidth in hertz.
    :type bandwidth_hz: float

    :returns: None

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    get_cached_instrument("rtsa", rtsa_id).set_bandwidth(bandwidth_hz)


@command
def set_acq_time(*, rtsa_id: int, seconds: float) -> None:
    """Set acquisition time in seconds.

    :param rtsa_id: Configured ``equipment.rtsa`` id from bench TOML.
    :type rtsa_id: int
    :param seconds: Acquisition duration in seconds.
    :type seconds: float

    :returns: None

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    get_cached_instrument("rtsa", rtsa_id).set_acq_time(seconds)


@command
def set_continuous_run(*, rtsa_id: int, enabled: bool) -> None:
    """Enable or disable continuous acquisition.

    :param rtsa_id: Configured ``equipment.rtsa`` id from bench TOML.
    :type rtsa_id: int
    :param enabled: ``True`` for continuous run, ``False`` for single-shot.
    :type enabled: bool

    :returns: None

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    get_cached_instrument("rtsa", rtsa_id).set_continuous_run(enabled)


@command
def set_num_samples(*, rtsa_id: int, count: int) -> None:
    """Set the number of IQ samples to acquire.

    :param rtsa_id: Configured ``equipment.rtsa`` id from bench TOML.
    :type rtsa_id: int
    :param count: IQ sample count.
    :type count: int

    :returns: None

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    get_cached_instrument("rtsa", rtsa_id).set_num_samples(count)


@command
def get_num_samples(*, rtsa_id: int) -> int:
    """Read the configured IQ sample count.

    :param rtsa_id: Configured ``equipment.rtsa`` id from bench TOML.
    :type rtsa_id: int

    :returns: Configured IQ sample count.
    :rtype: int

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    return int(get_cached_instrument("rtsa", rtsa_id).get_num_samples())


@command
def set_trigger_source(*, rtsa_id: int, source: str) -> None:
    """Set trigger source (for example ``INPut``, ``EXTFront``, ``EXTRear``).

    Also supports ``EXTGated`` and ``LINe``.

    :param rtsa_id: Configured ``equipment.rtsa`` id from bench TOML.
    :type rtsa_id: int
    :param source: Trigger source identifier accepted by the instrument SCPI driver.
    :type source: str

    :returns: None

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    get_cached_instrument("rtsa", rtsa_id).set_trigger_source(source)


@command
def set_trigger_level(*, rtsa_id: int, level_dbm: float) -> None:
    """Set trigger level in dBm.

    :param rtsa_id: Configured ``equipment.rtsa`` id from bench TOML.
    :type rtsa_id: int
    :param level_dbm: Trigger level in dBm.
    :type level_dbm: float

    :returns: None

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    get_cached_instrument("rtsa", rtsa_id).set_trigger_level(level_dbm)


@command
def set_trigger_position(*, rtsa_id: int, position_dbm: float) -> None:
    """Set trigger position in dBm.

    :param rtsa_id: Configured ``equipment.rtsa`` id from bench TOML.
    :type rtsa_id: int
    :param position_dbm: Trigger position in dBm.
    :type position_dbm: float

    :returns: None

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    get_cached_instrument("rtsa", rtsa_id).set_trigger_position(position_dbm)


@command
def run(*, rtsa_id: int) -> None:
    """Start or arm a single acquisition (non-blocking on generic models).

    :param rtsa_id: Configured ``equipment.rtsa`` id from bench TOML.
    :type rtsa_id: int

    :returns: None

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    get_cached_instrument("rtsa", rtsa_id).run()


@command
def wait_complete(*, rtsa_id: int, timeout_s: float = 60.0) -> None:
    """Block until the current acquisition completes or ``timeout_s`` elapses.

    :param rtsa_id: Configured ``equipment.rtsa`` id from bench TOML.
    :type rtsa_id: int
    :param timeout_s: Maximum wait time in seconds.
    :type timeout_s: float, optional

    :returns: None

    :raises EquipmentTimeoutError: Acquisition did not complete in time.
    """
    get_cached_instrument("rtsa", rtsa_id).wait_complete(timeout_s=timeout_s)


@command
def abort(*, rtsa_id: int) -> None:
    """Cancel an in-progress acquisition.

    :param rtsa_id: Configured ``equipment.rtsa`` id from bench TOML.
    :type rtsa_id: int

    :returns: None
    """
    get_cached_instrument("rtsa", rtsa_id).abort()


@command
def acquire(*, rtsa_id: int, timeout_s: float = 60.0) -> str:
    """Run a single acquisition and wait; returns an acquisition id string.

    :param rtsa_id: Configured ``equipment.rtsa`` id from bench TOML.
    :type rtsa_id: int
    :param timeout_s: Maximum wait time in seconds.
    :type timeout_s: float, optional

    :returns: Acquisition id for correlation with saved artifacts.
    :rtype: str
    """
    return str(get_cached_instrument("rtsa", rtsa_id).acquire(timeout_s=timeout_s))


@command
def peak_search(*, rtsa_id: int, marker: int = 1) -> None:
    """Run a spectrum peak search (Tek RSA5100B and similar).

    :param rtsa_id: Configured ``equipment.rtsa`` id from bench TOML.
    :type rtsa_id: int
    :param marker: Marker number (1-based).
    :type marker: int, optional

    :returns: None

    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    get_cached_instrument("rtsa", rtsa_id).peak_search(marker)


@command
def save_spectrum_trace_data(*, rtsa_id: int, path: str, trace: int = 1) -> None:
    """Export a non-IQ spectrum trace CSV (Tek RSA5100B workflow).

    :param rtsa_id: Configured ``equipment.rtsa`` id from bench TOML.
    :type rtsa_id: int
    :param path: Relative path under the run output directory.
    :type path: str
    :param trace: Trace number (1-based).
    :type trace: int, optional

    :returns: None

    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    get_cached_instrument("rtsa", rtsa_id).save_spectrum_trace_data(path, trace=trace)


@command
def save_IQ_data(*, rtsa_id: int, path: str, file_format: str = "bin", key: str = "") -> None:
    """Download IQ data as ``bin``, ``mat``, or ``iq.tar`` under the run directory.

    Writes the opaque instrument binary block (no sample reinterpretation).
    For decoded length-mode IQ records with ``f32`` / ``i16`` / ``c64`` encodings,
    use :func:`capture_iq`.

    :param rtsa_id: Configured ``equipment.rtsa`` id from bench TOML.
    :type rtsa_id: int
    :param path: Relative path under the active run output directory.
    :type path: str
    :param file_format: Export format: ``bin``, ``mat``, or ``iq.tar``.
    :type file_format: str, optional
    :param key: Evidence key (default ``rtsa_iq_<run>``).
    :type key: str, optional

    :returns: None

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    """
    get_cached_instrument("rtsa", rtsa_id).save_IQ_data(
        path, file_format=file_format, key=key,
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

    :param rtsa_id: Configured ``equipment.rtsa`` id from bench TOML.
    :type rtsa_id: int
    :param center_hz: Center frequency in hertz.
    :type center_hz: float
    :param span_hz: Frequency span in hertz.
    :type span_hz: float
    :param bandwidth_hz: IQ acquisition bandwidth in hertz.
    :type bandwidth_hz: float
    :param seconds: Acquisition duration in seconds.
    :type seconds: float
    :param path: Relative path under the active run output directory.
    :type path: str
    :param file_format: Container: ``mat``, ``bin``, or ``iq.tar``.
    :type file_format: str, optional
    :param sample_format: Sample encoding: ``f32`` (default), ``i16``, or ``c64``.
    :type sample_format: str, optional
    :param timeout_s: Maximum wait for acquisition and transfer.
    :type timeout_s: float, optional
    :param key: Evidence key (default ``rtsa_capture_iq_<run>``).
    :type key: str, optional

    :returns: JSON-safe metadata including ``sample_rate_hz``, ``num_samples``,
        ``path``, ``sample_format``, and ``peak`` when ``sample_format`` is ``i16``.
    :rtype: dict

    :raises EquipmentConnectionError: Transport or instrument connection failed.
    :raises EquipmentCapabilityError: Operation not supported by the configured model.
    :raises EquipmentTimeoutError: Acquisition or transfer did not complete in time.
    :raises EquipmentResponseError: Unsupported ``sample_format`` or bad instrument reply.
    """
    return dict(
        get_cached_instrument("rtsa", rtsa_id).capture_iq(
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
