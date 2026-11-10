from __future__ import annotations

from typing import TYPE_CHECKING, Any

from colosseum_equipment.instruments._capabilities import unsupported
from colosseum_equipment.instruments.registry import _confirmed_generic_commands, instrument_model
from colosseum_equipment.instruments.vsg.generic import GenericVSG
from colosseum_equipment.instruments.vsg.waveform_upload import upload_waveform_file
from colosseum_equipment.protocols.scpi import wait_opc

if TYPE_CHECKING:
    from colosseum_equipment.transports.base import Transport


@instrument_model("vsg", "keysight-esg")
@_confirmed_generic_commands(
    "preset",
    "set_pulse_period",
    "set_pulse_width",
    "pulse_source",
    "step_power",
    "freq_sweep",
    "amplitude_sweep",
    "configure_list",
    "measure_frequency",
    "measure_power_dbm",
)
class KeysightESGVSG(GenericVSG):
    """Keysight / Agilent E4428C and E4438C ESG signal generators."""

    def __init__(self, transport: Transport, config: dict[str, Any]) -> None:
        super().__init__(transport, config)
        self._model = "keysight-esg"
        self._idn = self._scpi.query("*IDN?")
        self._is_vector = "E4438C" in self._idn.upper()

    def _require_vector(self, operation: str) -> None:
        if not self._is_vector:
            unsupported(self._model, operation, detail="requires E4438C vector arb")

    def set_alc(self, enabled: bool) -> None:
        self._scpi.write(f"POW:ALC {1 if enabled else 0}")

    def set_attenuation(self, attenuation_db: float) -> None:
        self._scpi.write(f"POW:ATT {attenuation_db}")

    def set_phase(self, phase_deg: float) -> None:
        self._scpi.write(f"PHASE {phase_deg}")

    def set_output_blanking(self, enabled: bool) -> None:
        self._scpi.write(f"OUTP:BLAN {1 if enabled else 0}")

    def upload_waveform(
        self,
        local_path: str,
        remote_name: str,
        *,
        first_last_blanking: bool = False,
        method: str = "auto",
    ) -> None:
        self._require_vector("upload_waveform")
        upload_waveform_file(
            self._scpi,
            self._scpi._transport,
            self._config,
            local_path,
            remote_name,
            first_last_blanking=first_last_blanking,
            method=method,
        )

    def delete_waveform(self, remote_name: str) -> None:
        self._require_vector("delete_waveform")
        self._scpi.write(f'MMEM:DEL "{remote_name}"')
        wait_opc(self._scpi)

    def delete_all_waveforms(self) -> None:
        self._require_vector("delete_all_waveforms")
        self._scpi.write("MMEM:DEL:WFM1")
        wait_opc(self._scpi)

    def set_multicarrier(self, num_tones: int, spacing_hz: float) -> None:
        self._require_vector("set_multicarrier")
        self._scpi.write(
            f"RAD:DMOD:ARB:SETup:MCARrier:TABLe INIT,CUSTom,{int(num_tones)},{spacing_hz:.6f}",
        )

    def toggle_multitone(self, enabled: bool) -> None:
        self._require_vector("toggle_multitone")
        self._scpi.write(f"RAD:MTONe:ARB:STAT {1 if enabled else 0}")

    def play_iq(
        self,
        filename: str,
        center_freq_hz: float,
        amplitude_dbm: float,
        sample_clock_hz: float,
    ) -> None:
        self._require_vector("play_iq")
        self._scpi.write(f'RAD:ARB:WAV "{filename}"')
        self._scpi.write(f"FREQ:CW {center_freq_hz:.6f}")
        self._scpi.write(f"POW:AMPL {amplitude_dbm:.3f}")
        self._scpi.write(f"RAD:ARB:SCLock:RATE {sample_clock_hz:.6f}")
        self._scpi.write("RAD:ARB:STAT 1")
        self._scpi.write("OUTP:MOD ON")

    def set_pulsegen_output(self, enabled: bool) -> None:
        self._scpi.write(f"PULM:STAT {1 if enabled else 0}")

    def set_pulsemod_output(self, enabled: bool) -> None:
        self._scpi.write(f"PULM:STAT {1 if enabled else 0}")

    def select_waveform(self, remote_name: str) -> None:
        self._require_vector("select_waveform")
        self._scpi.write(f'RAD:ARB:WAV "{remote_name}"')

    def set_arb_state(self, enabled: bool) -> None:
        self._require_vector("set_arb_state")
        self._scpi.write(f"RAD:ARB:STAT {1 if enabled else 0}")

    def set_output(self, enabled: bool) -> None:
        self._scpi.write(f"OUTP:STAT {1 if enabled else 0}")

    def set_modulation(self, enabled: bool, modulation_type: str = "none") -> None:
        if self._is_vector:
            kind = modulation_type.lower()
            # "am" stays accepted: vector boxes have always mapped that call to DM:STAT.
            if kind not in {"none", "off", "dm", "digital", "am"}:
                unsupported(
                    self._model,
                    "set_modulation",
                    detail=(
                        f"modulation type {modulation_type!r} is not programmed; " "vector path only toggles DM:STAT"
                    ),
                )
            self._scpi.write(f"DM:STAT {1 if enabled else 0}")
            return
        # Analog ESG: AM/FM/PM + OUTP:MOD (E4400-90622). DMODE is not AM/FM select.
        mod = modulation_type.strip().upper()
        if not enabled or mod in ("", "NONE", "OFF"):
            self._scpi.write("AM:STAT OFF")
            self._scpi.write("FM:STAT OFF")
            self._scpi.write("PM:STAT OFF")
            self._scpi.write("OUTP:MOD OFF")
            return
        if mod == "AM":
            self._scpi.write("AM:STAT ON")
        elif mod == "FM":
            self._scpi.write("FM:STAT ON")
        elif mod in ("PM", "PHAS", "PHASE"):
            self._scpi.write("PM:STAT ON")
        else:
            raise ValueError(f"unsupported analog modulation type: {modulation_type}")
        self._scpi.write("OUTP:MOD ON")
