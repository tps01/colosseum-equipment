from __future__ import annotations

from typing import TYPE_CHECKING, Any

from colosseum_equipment.instruments._base import ScpiInstrumentMixin
from colosseum_equipment.instruments._capabilities import unsupported
from colosseum_equipment.instruments.vsg.waveform_upload import upload_waveform_file
from colosseum_equipment.protocols.scpi import SCPIHelper, wait_opc

if TYPE_CHECKING:
    from colosseum_equipment.transports.base import Transport


class GenericVSG(ScpiInstrumentMixin):
    """Generic SCPI vector/signal generator (IEEE 488.2 + SCPI-99 mnemonics)."""

    _model = "generic"

    def __init__(self, transport: Transport, config: dict[str, Any]) -> None:
        self._scpi = SCPIHelper(transport)
        self._config = config
        self._model = str(config.get("model", "generic")).lower()
        if "frequency" in config:
            self.set_frequency(float(config["frequency"]))
        if "power_dbm" in config:
            self.set_power(float(config["power_dbm"]))
        if config.get("output"):
            self.set_output(True)

    def set_frequency(self, frequency: float) -> None:
        self._scpi.write(f"FREQ:CW {frequency:.6f}")

    def set_power(self, power_dbm: float) -> None:
        self._scpi.write(f"POW:AMPL {power_dbm:.3f}")

    def set_output(self, enabled: bool) -> None:
        self._scpi.write("OUTP ON" if enabled else "OUTP OFF")

    def preset(self) -> None:
        self._scpi.write("*RST")
        wait_opc(self._scpi)

    def wait_complete(self) -> None:
        wait_opc(self._scpi)

    def set_alc(self, enabled: bool) -> None:
        self._scpi.write("POW:ALC ON" if enabled else "POW:ALC OFF")

    def set_attenuation(self, attenuation_db: float) -> None:
        self._scpi.write(f"POW:ATT {attenuation_db:.3f}")

    def set_phase(self, phase_deg: float) -> None:
        self._scpi.write(f"PHAS {phase_deg:.3f}")

    def set_output_blanking(self, enabled: bool) -> None:
        self._scpi.write("OUTP:BLAN ON" if enabled else "OUTP:BLAN OFF")

    def upload_waveform(
        self,
        local_path: str,
        remote_name: str,
        *,
        first_last_blanking: bool = False,
    ) -> None:
        upload_waveform_file(
            self._scpi,
            self._scpi._transport,
            self._config,
            local_path,
            remote_name,
            first_last_blanking=first_last_blanking,
        )

    def delete_waveform(self, remote_name: str) -> None:
        self._scpi.write(f'MMEM:DEL "{remote_name}"')
        wait_opc(self._scpi)

    def delete_all_waveforms(self) -> None:
        self._scpi.write("MMEM:DEL:WFM1")
        wait_opc(self._scpi)

    def set_multicarrier(self, _num_tones: int, _spacing_hz: float) -> None:
        unsupported(self._model, "set_multicarrier")

    def toggle_multitone(self, _enabled: bool) -> None:
        unsupported(self._model, "toggle_multitone")

    def play_iq(
        self,
        filename: str,
        center_freq_hz: float,
        amplitude_dbm: float,
        sample_clock_hz: float,
    ) -> None:
        self.select_waveform(filename)
        self.set_frequency(center_freq_hz)
        self.set_power(amplitude_dbm)
        self._scpi.write(f"RAD:ARB:SCLock:RATE {sample_clock_hz:.6f}")
        self.set_arb_state(True)
        self._scpi.write("OUTP:MOD ON")

    def set_pulsegen_output(self, enabled: bool) -> None:
        self._scpi.write("PULM:STAT ON" if enabled else "PULM:STAT OFF")

    def set_pulsemod_output(self, enabled: bool) -> None:
        self._scpi.write("PULM:STAT ON" if enabled else "PULM:STAT OFF")

    def set_pulse_period(self, period_s: float) -> None:
        self._scpi.write(f"PULM:INT:PER {period_s:.9f}")

    def set_pulse_width(self, width_s: float) -> None:
        self._scpi.write(f"PULM:INT:PWID {width_s:.9f}")

    def pulse_source(self, source: str) -> None:
        normalized = source.upper()
        if normalized == "PULSE":
            self._scpi.write("PULM:SOUR INT")
            self._scpi.write("PULM:INT:FUNC SHAP PULS")
        elif normalized == "SQUARE":
            self._scpi.write("PULM:SOUR INT")
            self._scpi.write("PULM:INT:FUNC SHAP SQU")
        elif normalized == "EXT1":
            self._scpi.write("PULM:SOUR EXT1")
        elif normalized == "EXT2":
            self._scpi.write("PULM:SOUR EXT2")
        else:
            raise ValueError(f"unsupported pulse source: {source}")

    def step_power(
        self,
        start_dbm: float,
        stop_dbm: float,
        step_db: float,
        interval_s: float,
    ) -> None:
        if step_db <= 0:
            raise ValueError("step_db must be positive")
        points = max(2, int(abs(stop_dbm - start_dbm) / step_db) + 1)
        self._scpi.write("LIST:TYPE STEP")
        self._scpi.write(f"POW:STAR {start_dbm:.3f}")
        self._scpi.write(f"POW:STOP {stop_dbm:.3f}")
        self._scpi.write(f"SWE:POIN {points}")
        self._scpi.write(f"SWE:DWEL {interval_s:.9f}")
        self._scpi.write("LIST:TRIG:SOUR IMM")
        self._scpi.write("INIT:CONT ON")

    def freq_sweep(
        self,
        start_hz: float,
        stop_hz: float,
        points: int,
        dwell_s: float,
    ) -> None:
        self._scpi.write("LIST:TYPE STEP")
        self._scpi.write(f"FREQ:STAR {start_hz:.6f}")
        self._scpi.write(f"FREQ:STOP {stop_hz:.6f}")
        self._scpi.write(f"SWE:POIN {int(points)}")
        self._scpi.write(f"SWE:DWEL {dwell_s:.9f}")
        self._scpi.write("INIT:CONT ON")

    def amplitude_sweep(
        self,
        start_dbm: float,
        stop_dbm: float,
        points: int,
        dwell_s: float,
    ) -> None:
        self._scpi.write("LIST:TYPE STEP")
        self._scpi.write(f"POW:STAR {start_dbm:.3f}")
        self._scpi.write(f"POW:STOP {stop_dbm:.3f}")
        self._scpi.write(f"SWE:POIN {int(points)}")
        self._scpi.write(f"SWE:DWEL {dwell_s:.9f}")
        self._scpi.write("INIT:CONT ON")

    def select_waveform(self, remote_name: str) -> None:
        self._scpi.write(f'RAD:ARB:WAV "{remote_name}"')

    def set_arb_state(self, enabled: bool) -> None:
        self._scpi.write("RAD:ARB:STAT ON" if enabled else "RAD:ARB:STAT OFF")

    def configure_list(self, frequencies: list[float], powers: list[float] | None = None) -> None:
        self._scpi.write("LIST:MODE LIST")
        freq_values = ",".join(str(value) for value in frequencies)
        self._scpi.write(f"LIST:FREQ {freq_values}")
        if powers is not None:
            power_values = ",".join(str(value) for value in powers)
            self._scpi.write(f"LIST:POW {power_values}")

    def set_modulation(self, enabled: bool, modulation_type: str = "none") -> None:
        if enabled and modulation_type.lower() != "none":
            self._scpi.write(f"SOUR:MOD:TYPE {modulation_type.upper()}")
            self._scpi.write("OUTP:MOD ON")
            return
        self._scpi.write("OUTP:MOD ON" if enabled else "OUTP:MOD OFF")

    def measure_output_state(self) -> bool:
        return bool(int(float(self._scpi.query("OUTP:STAT?"))))

    def measure_frequency(self) -> float:
        return self._scpi.query_float("FREQ:CW?")

    def measure_power_dbm(self) -> float:
        return self._scpi.query_float("POW:AMPL?")
