"""Manual-backed family dialects, passive reads and capability boundaries."""
from __future__ import annotations

import logging

import pytest

from colosseum_equipment.exceptions import EquipmentCapabilityError, EquipmentResponseError
from colosseum_equipment.instruments.factory import build_instrument
from colosseum_equipment.instruments.registry import reset_best_effort_warnings


class RecordingTransport:
    def __init__(self, replies=None):
        self.events = []
        self.replies = {"INST:SEL?": "SPA", "UNIT:POW?": "DBM", "*OPC?": "1", **(replies or {})}

    def write(self, command):
        self.events.append(command)

    def query(self, command):
        self.events.append(command)
        return self.replies[command]

    def write_raw(self, payload):
        self.events.append(payload)

    def write_bytes(self, payload):
        self.events.append(payload)

    def read_until(self, terminator):
        assert terminator == b"\r"
        return self.replies[self.events[-1]]

    def close(self):
        pass


def driver(kind, model, replies=None, **config):
    io = RecordingTransport(replies)
    inst = build_instrument(kind, 1, {"model": model, **config}, io)
    io.events.clear()
    return inst, io


@pytest.mark.parametrize("model", ["anritsu-ms2721b", "anritsu-ms2723b", "anritsu-ms2720t"])
def test_anritsu_marker_dialect_and_passive_delta_read(model, caplog):
    reset_best_effort_warnings()
    inst, io = driver("speca", model, {"CALC:MARK3:DELT:X?": "1000", "CALC:MARK3:DELT:Y?": "-12"})
    with caplog.at_level(logging.WARNING, logger="colosseum.equipment"):
        inst.toggle_marker(3, True)
        inst.next_peak_left(3)
        inst.next_peak_right(3)
        inst.toggle_delta_marker(3, True)
        assert inst.measure_marker_delta_frequency(3) == 1000
        assert inst.measure_marker_delta_power(3) == -12
    assert io.events == [
        "CALC:MARK3:STAT ON", "CALC:MARK3:MAX:LEFT", "CALC:MARK3:MAX:RIGH", "CALC:MARK3:DELT:STAT ON",
        "CALC:MARK3:DELT:X?", "UNIT:POW?", "CALC:MARK3:DELT:Y?",
    ]
    assert "using generic SCPI" not in caplog.text


def test_fpc_uses_separate_delta_subsystem_and_fixed_reference():
    inst, io = driver("speca", "rohde-fpc1500", {"CALC:DELT3:X:REL?": "2000", "CALC:DELT3:Y?": "-6"})
    inst.toggle_delta_marker(3, True)
    assert inst.measure_marker_delta_frequency(3) == 2000
    assert inst.measure_marker_delta_power(3) == -6
    inst.toggle_delta_marker(3, False)
    inst.next_highest_peak(3)
    assert io.events == [
        "CALC:DELT3:STAT ON", "CALC:DELT3:X:REL?", "UNIT:POW?", "CALC:DELT3:Y?",
        "CALC:MARK3:STAT ON", "CALC:MARK3:MAX:NEXT",
    ]
    io.events.clear()
    with pytest.raises(ValueError):
        inst.toggle_delta_marker(1, True)
    with pytest.raises(EquipmentCapabilityError):
        inst.set_marker_delta_reference(3, 2)
    assert io.events == []


@pytest.mark.parametrize("model", ["keysight-n9000a", "keysight-n9010a", "keysight-n9010b", "keysight-n9020a", "keysight-n9020b", "keysight-n9030a"])
def test_xseries_delta_mode_and_next_peak_directions(model):
    inst, io = driver("speca", model, {"CALC:MARK2:MODE?": "DELT", "CALC:MARK2:X?": "3000", "CALC:MARK2:Y?": "-9"})
    inst.toggle_delta_marker(2, True)
    inst.next_peak_right(2)
    inst.next_peak_left(2)
    inst.next_highest_peak(2)
    assert inst.measure_marker_delta_frequency(2) == 3000
    assert inst.measure_marker_delta_power(2) == -9
    assert io.events == [
        "CALC:MARK2:MODE DELT", "CALC:MARK2:MAX:RIGH", "CALC:MARK2:MAX:LEFT", "CALC:MARK2:MAX:NEXT",
        "CALC:MARK2:MODE?", "CALC:MARK2:X?", "UNIT:POW?", "CALC:MARK2:MODE?", "CALC:MARK2:Y?",
    ]


def test_xseries_rejects_absolute_read_as_delta_and_leaves_psa_extensions_guarded():
    inst, io = driver("speca", "keysight-n9010b", {"CALC:MARK2:MODE?": "POS"})
    with pytest.raises(EquipmentCapabilityError):
        inst.measure_marker_delta_frequency(2)
    assert io.events == ["CALC:MARK2:MODE?"]
    psa, io = driver("speca", "keysight-e4440a")
    with pytest.raises(EquipmentCapabilityError):
        psa.next_highest_peak()
    assert io.events == []


@pytest.mark.parametrize(("model", "commands"), [
    ("rohde-fpc1500", ["DISP:TRAC2:MODE AVER", "SWE:COUN 10"]),
    ("keysight-n9010b", ["TRAC2:MODE AVER", "AVER:COUN 10"]),
])
def test_trace_averaging_uses_family_commands_without_rearming(model, commands):
    inst, io = driver("speca", model)
    inst.set_trace_mode(2, "average")
    inst.set_averaging_count(10)
    assert io.events == commands


@pytest.mark.parametrize(("model", "marker"), [("rohde-fpc1500", 7), ("anritsu-ms2721b", 7), ("keysight-n9010b", 13), ("rohde-fpc1500", True)])
def test_invalid_marker_is_rejected_before_io(model, marker):
    inst, io = driver("speca", model)
    operations = [inst.set_marker_to_center]
    if model in {"anritsu-ms2721b", "rohde-fpc1500"}:
        operations.extend([inst.peak_search, inst.measure_marker_frequency])
    for operation in operations:
        with pytest.raises(ValueError):
            operation(marker)
    assert io.events == []


@pytest.mark.parametrize("model", ["keysight-e8257c", "keysight-e8257d", "keysight-n5183a", "keysight-n5183b", "keysight-n5181b", "keysight-n5182b"])
def test_keysight_sweeps_leave_rf_state_alone_and_restore_modes(model, caplog):
    reset_best_effort_warnings()
    inst, io = driver("vsg", model)
    with caplog.at_level(logging.WARNING, logger="colosseum.equipment"):
        inst.freq_sweep(2e9, 1e9, 3, 0.01)
    expected = [
        "INIT:CONT OFF", "LIST:TYPE STEP", "LIST:MODE AUTO", "SWE:SPAC LIN", "FREQ:STAR 1000000000.000000",
        "FREQ:STOP 2000000000.000000", "LIST:DIR DOWN", "SWE:POIN 3", "SWE:DWEL 0.010000000",
        "POW:MODE FIX", "FREQ:MODE LIST", "LIST:TRIG:SOUR IMM", "TRIG:SOUR IMM", "INIT:CONT ON",
    ]
    if model.startswith("keysight-e8257"):
        expected.remove("SWE:SPAC LIN")
    assert io.events == expected
    assert "using generic SCPI" not in caplog.text
    io.events.clear()
    inst.set_frequency(1.5e9)
    inst.set_power(-20)
    assert io.events == ["FREQ:MODE CW", "FREQ:CW 1500000000.000000", "UNIT:POW DBM", "POW:MODE FIX", "POW:AMPL -20.000DBM"]


@pytest.mark.parametrize(("frequencies", "powers"), [([], None), ([1e9, 2e9], [-10]), ([float("nan")], None), ([1e9], [float("inf")])])
def test_invalid_lists_do_not_modify_instrument(frequencies, powers):
    inst, io = driver("vsg", "keysight-n5181b")
    with pytest.raises(ValueError):
        inst.configure_list(frequencies, powers)
    assert io.events == []


def test_list_configuration_stops_previous_sweep_but_does_not_start_or_enable_rf():
    inst, io = driver("vsg", "keysight-n5181b")
    inst.configure_list([1e9, 2e9], [-20, -10])
    assert io.events == [
        "INIT:CONT OFF", "LIST:TYPE LIST", "LIST:MODE AUTO", "LIST:DIR UP", "UNIT:POW DBM",
        "LIST:FREQ 1000000000.000000,2000000000.000000", "LIST:POW -20.000,-10.000", "FREQ:MODE LIST", "POW:MODE LIST",
    ]


@pytest.mark.parametrize("model", ["keysight-e8257d", "keysight-n5183b", "keysight-n5181b"])
def test_analog_models_refuse_arb_before_any_io(model):
    inst, io = driver("vsg", model)
    with pytest.raises(EquipmentCapabilityError):
        inst.play_iq("WFM1:test", 1e9, -20, 1e6)
    assert io.events == []


def test_vector_arb_requires_installed_baseband_and_uses_native_trigger():
    inst, io = driver("vsg", "keysight-n5182b", {"*OPT?": '"503,656"'})
    inst.set_arb_sample_clock(10e6)
    inst.set_arb_trigger_source("BUS")
    inst.arm_arb_trigger()
    assert io.events == ["*OPT?", "RAD:ARB:SCL:RATE 10000000.000000", "*OPT?", "RAD:ARB:TRIG:SOUR BUS", "*OPT?", "*TRG"]
    inst, io = driver("vsg", "keysight-n5182b", {"*OPT?": "503"})
    with pytest.raises(EquipmentCapabilityError):
        inst.set_arb_state(True)
    assert io.events == ["*OPT?"]


def test_vector_playback_checks_the_baseband_option_once():
    inst, io = driver("vsg", "keysight-n5182b", {"*OPT?": "503,656"})
    inst.play_iq("WFM1:test", 1e9, -20, 1e6)
    assert io.events == [
        "*OPT?", 'RAD:ARB:WAV "WFM1:test"', "FREQ:MODE CW", "FREQ:CW 1000000000.000000",
        "UNIT:POW DBM", "POW:MODE FIX", "POW:AMPL -20.000DBM",
        "RAD:ARB:SCL:RATE 1000000.000000", "RAD:ARB:STAT ON", "OUTP:MOD ON",
    ]


def test_option_dependent_modulation_checks_capability_before_writes():
    inst, io = driver("vsg", "keysight-n5181b", {"*OPT?": "503"})
    with pytest.raises(EquipmentCapabilityError):
        inst.set_modulation(True, "AM")
    assert io.events == ["*OPT?"]
    inst, io = driver("vsg", "keysight-n5181b", {"*OPT?": "503,UNT,UNW"})
    inst.set_modulation(True, "AM")
    inst.pulse_source("SQUARE")
    assert io.events == ["*OPT?", "AM:STAT ON", "OUTP:MOD ON", "*OPT?", "PULM:SOUR INT", "PULM:SOUR:INT SQU"]


def test_smbv_multicarrier_and_arb_use_rs_dialect_without_enabling_rf():
    inst, io = driver("vsg", "rohde-smbv100b", {"SOUR:POW?": "-30"})
    inst.set_multicarrier(5, 1e6)
    inst.toggle_multitone(True)
    inst.set_arb_sample_clock(10e6)
    inst.set_arb_trigger_source("EGT1")
    inst.arm_arb_trigger()
    assert inst.measure_power_dbm() == -30
    assert io.events == [
        "SOUR:BB:MCCW:CARR:COUN 5", "SOUR:BB:MCCW:CARR:SPAC 1000000.000000", "SOUR:BB:MCCW:STAT ON",
        "SOUR:BB:ARB:CLOCK 10000000.000000", "SOUR:BB:ARB:TRIG:SOUR EGT1", "SOUR:BB:ARB:TRIG:EXEC", "SOUR:POW?",
    ]


def test_smbv_upload_preserves_native_file_and_binary_framing(tmp_path):
    path = tmp_path / "test.wv"
    payload = b"{TYPE: SMU-WV,0}{WAVEFORM-4:#\x00\x01\x02\x03}"
    path.write_bytes(payload)
    inst, io = driver("vsg", "rohde-smbv100b")
    inst.upload_waveform(str(path), "/var/user/test.wv")
    count = str(len(payload)).encode()
    assert io.events == [b'MMEM:DATA "/var/user/test.wv", #' + str(len(count)).encode() + count + payload + b"\n", "*OPC?"]
    io.events.clear()
    with pytest.raises(ValueError):
        inst.upload_waveform(str(path), 'bad"\nOUTP ON.wv')
    assert io.events == []


def test_hmp_fuse_and_ovp_clear_preserve_channel_and_output_state():
    inst, io = driver("psu", "rohde-hmp4040", {"INST?": "OUT2", "FUSE?": "1", "VOLT:PROT:TRIP?": "1", "FUSE:TRIP?": "0"})
    inst.toggle_ocp(True, channel=3)
    assert inst.get_ocp_enabled(channel=3) is True
    assert inst.get_fault_status(channel=3) == "ovp=1,fuse=0"
    inst.clear_protection(channel=3)
    assert io.events == [
        "INST OUT3", "FUSE ON", "INST?", "INST OUT3", "FUSE?", "INST OUT2",
        "INST?", "INST OUT3", "VOLT:PROT:TRIP?", "FUSE:TRIP?", "INST OUT2", "INST OUT3", "VOLT:PROT:CLE",
    ]


@pytest.mark.parametrize("model", ["keysight-n6705a", "keysight-n6705c"])
def test_n6705_channel_list_and_passive_fault_status(model):
    inst, io = driver("psu", model, {"STAT:QUES:COND? (@3)": "16", "CURR:PROT:STAT? (@3)": "1"})
    inst.set_voltage(3.3, channel=3)
    inst.toggle_ocp(True, channel=3)
    assert inst.get_ocp_enabled(channel=3) is True
    assert inst.get_fault_status(channel=3) == "16"
    inst.clear_protection(channel=3)
    assert io.events == ["VOLT 3.300000,(@3)", "CURR:PROT:STAT 1,(@3)", "CURR:PROT:STAT? (@3)", "STAT:QUES:COND? (@3)", "OUTP:PROT:CLE (@3)"]
    io.events.clear()
    with pytest.raises(EquipmentCapabilityError):
        inst.set_voltage(1, channel=5)
    assert io.events == []


def test_genesys_fault_queries_do_not_clear_fault_or_enable_output():
    inst, io = driver("psu", "tdk-genesys", {"STAT:QUES:COND?": "16"})
    assert inst.get_fault_status() == "16"
    assert io.events == ["STAT:QUES:COND?"]
    io.events.clear()
    with pytest.raises(EquipmentCapabilityError):
        inst.clear_protection()
    assert io.events == []


@pytest.mark.parametrize(("status", "mode"), [("01\r", "cv"), ("02\r", "cc"), ("00\r", "unknown")])
def test_native_genesys_foldback_and_hex_status(status, mode):
    inst, io = driver("psu", "tdk-genesys-serial", {
        b"FLD 1\r": "OK\r", b"FLD?\r": "ON\r", b"FLT?\r": "10\r", b"STAT?\r": status,
    }, driver="serial", baudrate=9600)
    inst.toggle_ocp(True)
    assert inst.get_ocp_enabled() is True
    assert inst.get_fault_status() == "10"
    assert inst.get_regulation_mode() == mode
    assert io.events == [b"FLD 1\r", b"FLD?\r", b"FLT?\r", b"STAT?\r"]


@pytest.mark.parametrize("reply", ["MAYBE", "nan", "65536", "-1"])
def test_n6705_rejects_malformed_fault_register(reply):
    inst, _ = driver("psu", "keysight-n6705c", {"STAT:QUES:COND? (@1)": reply})
    with pytest.raises(EquipmentResponseError):
        inst.get_fault_status()


def test_broadcast_trace_setup_reaches_both_vendor_drivers(unit_runtime_context, monkeypatch):
    from colosseum_equipment.api import _broadcast, speca

    first, first_io = driver("speca", "keysight-n9010b")
    second, second_io = driver("speca", "rohde-fpc1500")
    monkeypatch.setattr(_broadcast, "resolve_equipment_ids", lambda *args: [1, 2])
    monkeypatch.setattr(speca, "get_cached_instrument", lambda kind, identifier: {1: first, 2: second}[identifier])
    speca.set_trace_mode(speca_id="all", trace=2, mode="AVER")
    assert first_io.events == ["TRAC2:MODE AVER"]
    assert second_io.events == ["DISP:TRAC2:MODE AVER"]


def test_public_measurements_use_new_family_implementations(unit_runtime_context, monkeypatch):
    from colosseum_equipment.api import psu, speca, vsg

    analyzer, analyzer_io = driver("speca", "rohde-fpc1500", {"CALC:DELT2:X:REL?": "1000"})
    generator, generator_io = driver("vsg", "rohde-smbv100b", {"SOUR:POW?": "-20"})
    supply, supply_io = driver("psu", "keysight-n6705c", {"STAT:QUES:COND? (@2)": "16"})
    monkeypatch.setattr(speca, "get_cached_instrument", lambda *args: analyzer)
    monkeypatch.setattr(vsg, "get_cached_instrument", lambda *args: generator)
    monkeypatch.setattr(psu, "get_cached_instrument", lambda *args: supply)
    assert speca.measure_marker_delta_frequency(speca_id=1, marker=2, key="offset") == 1000
    assert vsg.measure_power_dbm(vsg_id=1, key="power") == -20
    assert psu.get_fault_status(psu_id=1, channel=2, key="fault") == "16"
    assert analyzer_io.events == ["CALC:DELT2:X:REL?"]
    assert generator_io.events == ["SOUR:POW?"]
    assert supply_io.events == ["STAT:QUES:COND? (@2)"]


@pytest.mark.parametrize(("model", "args"), [
    ("keysight-e8257d", (1e9, 2e9, 3, 0.0001)),
    ("keysight-e8257c", (1e9, 2e9, 3, 0.0015)),
    ("keysight-n5183b", (1e9, 2e9, True, 0.01)),
    ("keysight-n5181b", (float("nan"), 2e9, 3, 0.01)),
])
def test_invalid_sweeps_refuse_before_changing_modes(model, args):
    inst, io = driver("vsg", model)
    with pytest.raises(ValueError):
        inst.freq_sweep(*args)
    assert io.events == []


def test_phase_and_amplitude_sweep_are_explicit_about_units():
    inst, io = driver("vsg", "keysight-n5181b")
    inst.set_phase(30)
    inst.amplitude_sweep(-20, -10, 3, 0.01)
    assert io.events[0] == "PHAS 30.000DEG"
    assert "UNIT:POW DBM" in io.events
    assert "POW:STAR -20.000000" in io.events
    assert "POW:STOP -10.000000" in io.events
    assert "FREQ:MODE CW" in io.events
    assert "POW:MODE LIST" in io.events
    assert not any(command.startswith("OUTP") for command in io.events)


def test_fpc_abort_synchronizes_without_initiating_again():
    inst, io = driver("speca", "rohde-fpc1500")
    inst.abort()
    assert io.events == ["ABOR;*WAI"]


@pytest.mark.parametrize("reply", ["0\r", "GG\r", "100\r", "E07\r"])
def test_native_genesys_invalid_register_is_not_a_valid_measurement(reply):
    inst, io = driver("psu", "tdk-genesys-serial", {b"FLT?\r": reply}, driver="serial", baudrate=9600)
    with pytest.raises(EquipmentResponseError):
        inst.get_fault_status()
    assert io.events == [b"FLT?\r"]


def test_mxg_deletes_volatile_waveforms_using_documented_memory_command():
    inst, io = driver("vsg", "keysight-n5182b", {"*OPT?": "503,656"})
    inst.delete_all_waveforms()
    assert io.events == ["*OPT?", "MMEM:DEL:WFM", "*OPC?"]


def test_mxg_binary_upload_separates_file_and_block_arguments(tmp_path):
    path = tmp_path / "test.bin"
    payload = b"\x00\x01\x02\x03" * 4
    path.write_bytes(payload)
    inst, io = driver("vsg", "keysight-n5182b", {"*OPT?": "503,656"})
    inst.upload_waveform(str(path), "WFM1:test.bin", method="tcpip")
    assert io.events == ["*OPT?", b'MMEM:DATA "WFM1:test.bin", #216' + payload + b"\n", "*OPC?"]


def test_mxg_output_blanking_has_explicit_state_keyword():
    inst, io = driver("vsg", "keysight-n5181b")
    inst.set_output_blanking(True)
    assert io.events == ["OUTP:BLAN:STAT ON"]


def test_fpc_csv_refuses_non_dbm_trace_before_changing_transfer_settings(unit_runtime_context):
    inst, io = driver("speca", "rohde-fpc1500", {
        "UNIT:POW?": "W", "FORM?": "ASC", "TRAC:DATA? TRACE1": "0.01,0.02",
        "FREQ:STAR?": "1", "FREQ:STOP?": "2",
    })
    with pytest.raises(EquipmentCapabilityError):
        inst.save_trace_data("traces/watts.csv")
    assert io.events == ["UNIT:POW?"]
