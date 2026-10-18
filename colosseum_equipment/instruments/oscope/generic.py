from __future__ import annotations

import contextlib
import csv
import time
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any

from colosseum_equipment._paths import resolve_artifact_path
from colosseum_equipment.evidence import record_artifact
from colosseum_equipment.exceptions import (
    EquipmentCapabilityError,
    EquipmentResponseError,
    EquipmentTimeoutError,
)
from colosseum_equipment.instruments._base import ScpiInstrumentMixin
from colosseum_equipment.instruments.registry import best_effort_commands, instrument_model
from colosseum_equipment.protocols.scpi import SCPIHelper, wait_opc

if TYPE_CHECKING:
    from colosseum_equipment.transports.base import Transport

_ACQUIRE_MODES = {
    "sample": "NORM",
    "peak": "PEAK",
    "average": "AVER",
    "hres": "HRES",
}


def _parse_ascii_waveform(raw: str, *, points_expected: int) -> list[float]:
    """Parse SCPI ASCII waveform payload, including definite-length ``#`` headers.

    A header like ``#14`` + 4 data digits may be glued to the first sample
    (``#1412341.0,2.0``). Strip the framing before splitting samples.
    """
    text = raw.strip()
    if text.startswith("#"):
        if len(text) < 2 or not text[1].isdigit():
            raise EquipmentResponseError(f"malformed waveform block header: {raw[:32]!r}")
        ndigits = int(text[1])
        header_len = 2 + ndigits
        if ndigits > 0:
            if len(text) < header_len:
                raise EquipmentResponseError(f"truncated waveform block header: {raw[:32]!r}")
            # Digits after ``#N`` are the byte/char count of the payload.
            text = text[header_len:]
        else:
            # ``#0`` means indefinite length until NL — drop the ``#0`` prefix.
            text = text[2:]
    tokens = [t for t in text.replace(",", " ").split() if t]
    values: list[float] = []
    bad: list[str] = []
    for token in tokens:
        try:
            values.append(float(token))
        except ValueError:
            bad.append(token)
            if len(bad) > 5:
                break
    if bad:
        raise EquipmentResponseError(
            f"malformed waveform sample token(s): {bad[:5]!r}",
        )
    if points_expected > 0 and len(values) != points_expected:
        # Allow minor preamble mismatch only when instrument under-reports; never
        # accept a truncated block that lost the first sample to header stripping.
        if len(values) < points_expected:
            raise EquipmentResponseError(
                f"waveform truncated: got {len(values)} points, preamble expected "
                f"{points_expected}",
            )
    return values


@instrument_model("oscope", "generic", extra_optional=("measurement_slot", "channels"))
@best_effort_commands
class GenericOscope(ScpiInstrumentMixin):
    """Generic SCPI oscilloscope (subset; vendor models extend).

    Acquisition contract (best-effort SCPI dialect):
    - ``run`` / ``single_acquire`` arm acquisition
    - ``wait_complete`` blocks until OPC / stopped state
    - ``abort`` / ``stop`` cancel
    - ``measure_*`` / ``save_*`` read the last completed capture (do not re-arm)
    """

    _model = "generic"

    def __init__(self, transport: Transport, config: dict[str, Any]) -> None:
        self._scpi = SCPIHelper(transport)
        self._config = config
        self._model = str(config.get("model", "generic")).lower()
        self._channel_count = int(config.get("channels") or config.get("channel_count") or 4)
        self._capture_id = ""
        self._capture_mono = 0.0

    def _require_channel(self, channel: int) -> int:
        ch = int(channel)
        if ch < 1 or ch > self._channel_count:
            raise EquipmentCapabilityError(
                f"oscope model `{self._model}` does not support channel {ch} "
                f"(valid 1..{self._channel_count})",
            )
        return ch

    def _mark_capture(self) -> str:
        self._capture_id = uuid.uuid4().hex[:12]
        self._capture_mono = time.monotonic()
        return self._capture_id

    def preset(self) -> None:
        self._scpi.write("*RST")
        wait_opc(self._scpi)

    # --- Channel -----------------------------------------------------------

    def set_channel_display(self, channel: int, enabled: bool) -> None:
        ch = self._require_channel(channel)
        self._scpi.write(f"CHAN{ch}:DISP {'ON' if enabled else 'OFF'}")

    def get_channel_display(self, channel: int) -> bool:
        ch = self._require_channel(channel)
        return bool(int(float(self._scpi.query(f"CHAN{ch}:DISP?"))))

    def set_channel_scale_v(self, channel: int, volts_per_div: float) -> None:
        ch = self._require_channel(channel)
        self._scpi.write(f"CHAN{ch}:SCAL {volts_per_div}")

    def get_channel_scale_v(self, channel: int) -> float:
        ch = self._require_channel(channel)
        return self._scpi.query_float(f"CHAN{ch}:SCAL?")

    def set_channel_offset_v(self, channel: int, offset_v: float) -> None:
        ch = self._require_channel(channel)
        self._scpi.write(f"CHAN{ch}:OFFS {offset_v}")

    def get_channel_offset_v(self, channel: int) -> float:
        ch = self._require_channel(channel)
        return self._scpi.query_float(f"CHAN{ch}:OFFS?")

    def set_channel_coupling(self, channel: int, coupling: str) -> None:
        ch = self._require_channel(channel)
        mode = coupling.strip().upper()
        if mode not in {"AC", "DC", "GND"}:
            raise EquipmentCapabilityError(f"unsupported coupling `{coupling}`")
        self._scpi.write(f"CHAN{ch}:COUP {mode}")

    def get_channel_coupling(self, channel: int) -> str:
        ch = self._require_channel(channel)
        return self._scpi.query(f"CHAN{ch}:COUP?").strip().upper()

    def set_channel_probe_attenuation(self, channel: int, attenuation: float) -> None:
        ch = self._require_channel(channel)
        self._scpi.write(f"CHAN{ch}:PROB {attenuation}")

    def get_channel_probe_attenuation(self, channel: int) -> float:
        ch = self._require_channel(channel)
        return self._scpi.query_float(f"CHAN{ch}:PROB?")

    def set_channel_bandwidth_limit(self, channel: int, enabled: bool) -> None:
        ch = self._require_channel(channel)
        self._scpi.write(f"CHAN{ch}:BWL {'ON' if enabled else 'OFF'}")

    def get_channel_bandwidth_limit(self, channel: int) -> bool:
        ch = self._require_channel(channel)
        raw = self._scpi.query(f"CHAN{ch}:BWL?").strip().upper()
        return raw in {"1", "ON", "20M", "TRUE"}

    def set_channel_impedance(self, channel: int, ohms: float) -> None:
        ch = self._require_channel(channel)
        if abs(ohms - 50.0) < 1e-6:
            self._scpi.write(f"CHAN{ch}:IMP FIFT")
        elif abs(ohms - 1e6) < 1.0:
            self._scpi.write(f"CHAN{ch}:IMP ONEM")
        else:
            raise EquipmentCapabilityError(
                f"oscope model `{self._model}` impedance must be 50 or 1e6 ohm",
            )

    def get_channel_impedance(self, channel: int) -> float:
        ch = self._require_channel(channel)
        raw = self._scpi.query(f"CHAN{ch}:IMP?").strip().upper()
        if "FIF" in raw or raw in {"50", "FIFT"}:
            return 50.0
        return 1e6

    # --- Timebase ----------------------------------------------------------

    def set_timebase_scale(self, seconds_per_div: float) -> None:
        self._scpi.write(f"TIM:SCAL {seconds_per_div}")

    def set_timebase_position_s(self, position_s: float) -> None:
        self._scpi.write(f"TIM:OFFS {position_s}")

    def set_record_length(self, points: int) -> None:
        self._scpi.write(f"ACQ:MDEP {int(points)}")

    def get_record_length(self) -> int:
        return int(float(self._scpi.query("ACQ:MDEP?")))

    # --- Trigger -----------------------------------------------------------

    def set_trigger_mode(self, mode: str) -> None:
        normalized = mode.strip().lower()
        mapping = {"auto": "AUTO", "normal": "NORM", "single": "SING", "stop": "STOP"}
        if normalized not in mapping:
            raise EquipmentCapabilityError(f"unsupported trigger mode `{mode}`")
        self._scpi.write(f"TRIG:MODE {mapping[normalized]}")

    def set_trigger_source(self, source: str) -> None:
        self._scpi.write(f"TRIG:EDGE:SOUR {source}")

    def set_trigger_level_v(self, level_v: float) -> None:
        self._scpi.write(f"TRIG:EDGE:LEV {level_v}")

    def set_trigger_slope(self, slope: str) -> None:
        normalized = slope.strip().lower()
        mapping = {"rising": "POS", "falling": "NEG", "pos": "POS", "neg": "NEG"}
        if normalized not in mapping:
            raise EquipmentCapabilityError(f"unsupported trigger slope `{slope}`")
        self._scpi.write(f"TRIG:EDGE:SLOP {mapping[normalized]}")

    def set_trigger_holdoff_s(self, holdoff_s: float) -> None:
        self._scpi.write(f"TRIG:HOLD {holdoff_s}")

    def force_trigger(self) -> None:
        self._scpi.write("TRIG:FORC")

    def wait_for_trigger(self, *, timeout_s: float) -> None:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            state = self.get_acquire_state().upper()
            if any(token in state for token in ("TRIG", "STOP", "COMP", "TD")):
                return
            time.sleep(0.05)
        raise EquipmentTimeoutError(
            f"oscope model `{self._model}` did not trigger within {timeout_s}s",
        )

    # --- Acquisition -------------------------------------------------------

    def set_acquire_mode(self, mode: str) -> None:
        key = mode.strip().lower()
        if key not in _ACQUIRE_MODES:
            raise EquipmentCapabilityError(f"unsupported acquire mode `{mode}`")
        self._scpi.write(f"ACQ:TYPE {_ACQUIRE_MODES[key]}")

    def set_acquire_averages(self, count: int) -> None:
        self._scpi.write(f"ACQ:AVER {int(count)}")

    def run(self) -> None:
        self._mark_capture()
        self._scpi.write("RUN")

    def stop(self) -> None:
        self._scpi.write("STOP")

    def arm_single(self) -> None:
        """Arm one acquisition without waiting for an external event."""
        self._mark_capture()
        self._scpi.write("SING")

    def single_acquire(self) -> None:
        """Arm a single acquisition and wait for completion (OPC)."""
        self.arm_single()
        wait_opc(self._scpi)

    def abort(self) -> None:
        self._scpi.write("STOP")

    def get_acquire_state(self) -> str:
        return self._scpi.query("TRIG:STAT?").strip()

    def wait_complete(self, *, timeout_s: float) -> None:
        deadline = time.monotonic() + timeout_s
        transport = getattr(self._scpi, "_transport", None)
        setter = getattr(transport, "set_timeout_s", None) if transport is not None else None
        prev_timeout = getattr(transport, "_timeout", None) if transport is not None else None
        try:
            while time.monotonic() < deadline:
                remaining = max(0.05, deadline - time.monotonic())
                if callable(setter):
                    with contextlib.suppress(Exception):
                        setter(min(remaining, 1.0))
                try:
                    done = self._scpi.query("*OPC?").strip()
                    if done.startswith("1"):
                        return
                except Exception:
                    state = self.get_acquire_state().upper()
                    if any(token in state for token in ("STOP", "COMP", "IDLE")):
                        return
                time.sleep(0.05)
        finally:
            if callable(setter) and prev_timeout is not None:
                with contextlib.suppress(Exception):
                    setter(float(prev_timeout))
        raise EquipmentTimeoutError(
            f"oscope model `{self._model}` acquisition did not complete within {timeout_s}s",
        )

    def acquire(self, *, timeout_s: float = 10.0) -> str:
        """Arm single, wait, return capture id."""
        self.arm_single()
        self.wait_complete(timeout_s=timeout_s)
        return self._capture_id

    # --- Measurements (fetch last capture; do not re-arm) ------------------

    def measure_vpp(self, channel: int = 1) -> float:
        ch = self._require_channel(channel)
        return self._scpi.query_float(f"MEAS:VPP? CHAN{ch}")

    def measure_vmax(self, channel: int = 1) -> float:
        ch = self._require_channel(channel)
        return self._scpi.query_float(f"MEAS:VMAX? CHAN{ch}")

    def measure_vmin(self, channel: int = 1) -> float:
        ch = self._require_channel(channel)
        return self._scpi.query_float(f"MEAS:VMIN? CHAN{ch}")

    def measure_vrms(self, channel: int = 1) -> float:
        ch = self._require_channel(channel)
        return self._scpi.query_float(f"MEAS:VRMS? CHAN{ch}")

    def measure_frequency_hz(self, channel: int = 1) -> float:
        ch = self._require_channel(channel)
        return self._scpi.query_float(f"MEAS:FREQ? CHAN{ch}")

    def measure_period_s(self, channel: int = 1) -> float:
        ch = self._require_channel(channel)
        return self._scpi.query_float(f"MEAS:PER? CHAN{ch}")

    def measure_rise_time_s(self, channel: int = 1) -> float:
        ch = self._require_channel(channel)
        return self._scpi.query_float(f"MEAS:RIS? CHAN{ch}")

    def measure_fall_time_s(self, channel: int = 1) -> float:
        ch = self._require_channel(channel)
        return self._scpi.query_float(f"MEAS:FALL? CHAN{ch}")

    # --- Waveform / screenshot ---------------------------------------------

    def _read_waveform_points(self, channel: int) -> tuple[list[float], dict[str, Any]]:
        ch = self._require_channel(channel)
        self._scpi.write(f"WAV:SOUR CHAN{ch}")
        self._scpi.write("WAV:FORM ASC")
        self._scpi.write("WAV:MODE NORM")
        xinc = self._scpi.query_float("WAV:XINC?")
        xorigin = self._scpi.query_float("WAV:XOR?")
        yinc = self._scpi.query_float("WAV:YINC?")
        yorigin = self._scpi.query_float("WAV:YOR?")
        yref = self._scpi.query_float("WAV:YREF?")
        points_expected = int(float(self._scpi.query("WAV:POIN?")))
        raw = self._scpi.query("WAV:DATA?")
        values = _parse_ascii_waveform(raw, points_expected=points_expected)
        volts = [(v - yref) * yinc + yorigin for v in values] if values else values
        meta = {
            "channel": ch,
            "points": len(volts),
            "points_expected": points_expected,
            "xinc_s": xinc,
            "xorigin_s": xorigin,
            "yinc_v": yinc,
            "yorigin_v": yorigin,
            "yref": yref,
            "vertical_units": "V",
            "encoding": "ascii",
            "capture_id": self._capture_id,
        }
        return volts, meta

    def save_waveform(self, *, channel: int, path: str, key: str = "") -> Path:
        volts, meta = self._read_waveform_points(channel)
        artifact_path = resolve_artifact_path(path)
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        xinc = float(meta["xinc_s"])
        xorigin = float(meta["xorigin_s"])
        with artifact_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["time_s", "voltage_v"])
            for index, voltage in enumerate(volts):
                writer.writerow([xorigin + index * xinc, voltage])
        evidence_key = key or f"oscope_wave_ch{channel}_{self._capture_id or 'last'}"
        record_artifact(
            domain="equipment",
            command="save_waveform",
            key=evidence_key,
            path=artifact_path,
            value=meta,
        )
        return artifact_path

    def save_screenshot(self, path: str, *, key: str = "") -> Path:
        payload = self._scpi.read_binary_block("HCOP:SDUM:DATA?")
        artifact_path = resolve_artifact_path(path)
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_bytes(payload)
        evidence_key = key or f"oscope_screenshot_{self._capture_id or 'last'}"
        record_artifact(
            domain="equipment",
            command="save_screenshot",
            key=evidence_key,
            path=artifact_path,
            value={"capture_id": self._capture_id, "bytes": len(payload)},
        )
        return artifact_path
