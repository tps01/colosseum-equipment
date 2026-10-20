"""Inventory drivers must preserve command dialect, acquisition and capability boundaries."""
from __future__ import annotations

import pytest
from colosseum_equipment.exceptions import EquipmentCapabilityError, EquipmentResponseError
from colosseum_equipment.instruments.factory import build_instrument


class RecordingTransport:
    def __init__(self, responses=None):
        self.events = []
        self.responses = responses or {}

    def write(self, command):
        self.events.append(command)

    def query(self, command):
        self.events.append(command)
        if command not in self.responses:
            raise AssertionError(f"unexpected query: {command}")
        result = self.responses[command]
        if isinstance(result, list):
            return result.pop(0)
        return result

    def close(self):
        self.events.append("close")


def instrument(kind, model, responses=None, **config):
    transport = RecordingTransport(responses)
    driver = build_instrument(kind, 1, {"model": model, **config}, transport)
    return driver, transport


def test_dmm_range_follows_actual_function_and_fetch_does_not_rearm():
    dmm, io = instrument("dmm", "keysight-34411a", {
        "CONF?": '"CURR:DC +1.0E-1,+1.0E-7"', "FETC?": "0.025",
    })
    dmm.set_range(0.1)
    assert io.events == ["CONF?", "SENS:CURR:DC:RANG 0.1"]
    io.events.clear()
    assert dmm.fetch() == 0.025
    assert io.events == ["FETC?"]


@pytest.mark.parametrize("raw", ["9.9e37", "nan", "inf", "1,2", "overload", "1VDC"])
def test_dmm_does_not_accept_overload_arrays_or_units_as_scalar(raw):
    dmm, _ = instrument("dmm", "keysight-34410a", {"FETC?": raw})
    with pytest.raises(EquipmentResponseError):
        dmm.fetch()


def test_dmm_oneshot_does_not_inherit_external_trigger():
    dmm, io = instrument("dmm", "keithley-2100", {"READ?": "1.25"})
    assert dmm.measure_voltage() == 1.25
    assert io.events == ["CONF:VOLT:DC", "TRIG:SOUR IMM", "TRIG:COUN 1", "SAMP:COUN 1", "READ?"]


def test_2001_fetch_uses_scpi_format_instead_of_poweron_fresh_mode():
    dmm, io = instrument("dmm", "keithley-2001", {"FETC?": "1.5"})
    assert io.events == ["SYST:FETC:FORM SCPI", "FORM:DATA ASC", "FORM:ELEM READ"]
    io.events.clear()
    assert dmm.fetch() == 1.5
    assert io.events == ["FETC?"]


def test_dmm_unsupported_features_do_not_send_generic_commands():
    dmm, io = instrument("dmm", "keithley-2100")
    with pytest.raises(EquipmentCapabilityError):
        dmm.set_input_z(50)
    assert io.events == []


@pytest.mark.parametrize("channel", [1, 3, 4, 2])
def test_n6705a_addresses_every_operation_with_channel_list(channel):
    psu, io = instrument("psu", "keysight-n6705a", {f"MEAS:VOLT? (@{channel})": "3.3"})
    psu.set_voltage(3.3, channel=channel)
    psu.set_output(False, channel=channel)
    assert psu.measure_voltage(channel=channel) == 3.3
    assert io.events == [f"VOLT 3.300000,(@{channel})", f"OUTP 0,(@{channel})", f"MEAS:VOLT? (@{channel})"]


def test_hmp_channel_control_does_not_enable_other_selected_outputs():
    psu, io = instrument("psu", "rohde-hmp4040")
    psu.set_output(True, channel=3)
    psu.set_output(False, channel=1)
    assert io.events == ["INST OUT3", "OUTP ON", "INST OUT1", "OUTP OFF"]


def test_psu_rejects_invalid_channel_before_any_write():
    psu, io = instrument("psu", "keysight-n6705a")
    with pytest.raises(EquipmentCapabilityError):
        psu.set_voltage(5, channel=5)
    assert io.events == []


@pytest.mark.parametrize("model", ["keysight-e8257d", "keysight-n5183b", "rohde-sma100b"])
def test_analog_generator_refuses_vector_operations_without_io(model):
    source, io = instrument("vsg", model)
    with pytest.raises(EquipmentCapabilityError):
        source.play_iq("test.bin", 1e9, -10, 1e6)
    assert io.events == []
    source.set_power(-10)
    assert io.events == ["UNIT:POW DBM", "POW -10.000000"]


def test_53150a_selects_input_in_measurement_not_sticky_routing():
    counter, io = instrument("freqcounter", "keysight-53150a", {"MEAS:FREQ? (@2)": "1e9"})
    assert counter.measure_frequency(channel=2) == 1e9
    assert io.events == ["MEAS:FREQ? (@2)"]
    with pytest.raises(EquipmentCapabilityError):
        counter.set_gate_time(1)
    assert io.events == ["MEAS:FREQ? (@2)"]


def test_xseries_selects_application_before_initial_configuration_and_validates_trace():
    analyzer, io = instrument("speca", "keysight-n9020a", {
        "*OPC?": "1", "FREQ:CENT?": "1e9", "FREQ:SPAN?": "2e6",
        "TRAC:DATA? TRACE1": "-70,-10,-70", "SWE:POIN?": "3",
    }, center_freq=1e9)
    assert io.events[:2] == ["INST:SEL SA", "FREQ:CENT 1000000000.000000"]
    axis, values = analyzer._fetch_trace(1)
    assert axis == [999e6, 1e9, 1001e6]
    assert values == [-70, -10, -70]
    assert io.events.index("INIT:IMM") < io.events.index("TRAC:DATA? TRACE1")
    io.responses["SWE:POIN?"] = "4"
    with pytest.raises(EquipmentResponseError):
        analyzer._fetch_trace(1)


def test_vna_averages_selected_measurement_channel_and_keeps_actual_axis(tmp_path, monkeypatch):
    from pathlib import Path
    monkeypatch.setattr("colosseum_equipment.instruments.vna.inventory.resolve_artifact_path", Path)
    monkeypatch.setattr("colosseum_equipment.instruments.vna.inventory.record_artifact", lambda **kw: None)
    vna, io = instrument("vna", "keysight-n5245b", {
        "SENS2:AVER?": "1", "SENS2:AVER:COUN?": "2", "*OPC?": "1",
        "CALC2:DATA? FDATA": "-10,-20,-30", "SENS2:X?": "1e6,2e6,10e6",
    }, channel=2)
    path = vna.save_trace_data(str(tmp_path / "trace.csv"), parameter="S21")
    assert io.events.count("SENS2:SWE:MODE SING") == 2
    assert "INIT2:CONT OFF" not in io.events
    assert 'CALC2:PAR:MOD:EXT "S21"' in io.events
    assert path.read_text().splitlines()[-1].startswith("10000000.000000,-30")
    assert io.events.count("SENS2:AVER:CLE") == 1


def test_vna_rejects_mismatched_axis_and_fake_touchstone(tmp_path):
    vna, io = instrument("vna", "keysight-e5071b", {
        "SENS1:AVER?": "0", "*OPC?": "1",
        "CALC1:DATA:FDAT?": "-10,0,-20,0", "SENS1:FREQ:DATA?": "1,2,3",
    })
    with pytest.raises(EquipmentCapabilityError):
        vna.save_trace_data(str(tmp_path / "trace.s2p"))
    assert io.events == []
    with pytest.raises(EquipmentResponseError):
        vna.save_trace_data(str(tmp_path / "trace.csv"))
    assert not (tmp_path / "trace.csv").exists()


def test_power_body_routes_physical_inputs_and_fetches_without_rearming():
    meter, io = instrument("pwrmeter", "keysight-n1912a", {"FETC2?": "-30", "*OPC?": "1"})
    assert 'CALC2:MATH:EXPR "(SENS2)"' in io.events
    io.events.clear()
    meter.acquire(channel=2)
    assert io.events == ["INIT2:CONT OFF", "TRIG2:SOUR IMM", "INIT2:IMM", "*OPC?"]
    io.events.clear()
    assert meter.measure_power_avg_dbm(channel=2) == -30
    assert io.events == ["FETC2?"]
    with pytest.raises(EquipmentCapabilityError):
        meter.measure_power_peak_dbm(channel=2)
    assert io.events == ["FETC2?"]


def test_nrp_watt_results_are_not_mislabeled_dbm():
    meter, io = instrument("pwrmeter", "rohde-nrp18s", {"FETC?": "0.001"})
    assert meter.measure_power_avg_dbm() == pytest.approx(0)
    io.responses["FETC?"] = "0"
    with pytest.raises(EquipmentResponseError):
        meter.measure_power_avg_dbm()


def test_chroma_selects_logical_channel_and_converts_slew_units():
    load, io = instrument("eload", "chroma-63600-5", channels=6)
    load.set_mode("CC", channel=5)
    load.set_current(1.5, channel=5)
    load.set_slew_rate(2e6, channel=5)
    assert io.events == ["CHAN 5", "MODE CCH", "CHAN 5", "CURR:STAT:L1 1.5",
                         "CHAN 5", "CURR:STAT:RISE 2.0", "CURR:STAT:FALL 2.0"]
    with pytest.raises(EquipmentCapabilityError):
        load.toggle_transient(True)
    assert "INP ON" not in io.events


def test_tds_waveform_decodes_signed_bytes_and_trigger_offset():
    scope, io = instrument("oscope", "tektronix-tds3032b", {
        "ACQuire:STATE?": "0", "WFMPRE:NR_PT?": "3", "WFMPRE:XINCR?": "0.1",
        "WFMPRE:XZERO?": "1", "WFMPRE:PT_OFF?": "2", "WFMPRE:YMULT?": "0.5",
        "WFMPRE:YOFF?": "1", "WFMPRE:YZERO?": "-1", "WFMPRE:XUNIT?": '"s"',
        "WFMPRE:YUNIT?": '"Volts"',
    })
    io.read_raw = lambda: b"#13\x80\x00\x7f\n"
    volts, meta = scope._read_waveform_points(1)
    assert volts == [-65.5, -1.5, 62]
    assert meta["xorigin_s"] == pytest.approx(0.8)
    with pytest.raises(EquipmentCapabilityError):
        scope.set_channel_display(3, True)


def test_infiniium_clears_stale_ader_then_latches_new_completion():
    scope, io = instrument("oscope", "keysight-dsa71254", {"ADER?": ["1", "0", "1"], "CHAN1:UNIT?": "VOLT", "MEAS:VPP? CHAN1": "2"})
    scope.arm_single()
    assert io.events == ["STOP", "ADER?", "SING"]
    assert scope.get_acquire_state() == "RUN"
    assert scope.get_acquire_state() == "STOP"
    assert scope.measure_vpp() == 2
    assert io.events.count("ADER?") == 3  # completed state is cached, not read-cleared again
    scope.abort()
    with pytest.raises(EquipmentCapabilityError):
        scope.measure_vpp()


def test_rohde_interrupted_acquisition_is_not_success():
    scope, _ = instrument("oscope", "rohde-rtb2004", {"ACQ:STAT?": "BREAK"})
    with pytest.raises(EquipmentResponseError):
        scope.wait_complete(timeout_s=1)


def test_fieldfox_uses_na_mode_and_sweep_averages_without_ena_pair_decoding():
    vna, io = instrument("vna", "keysight-n9917b", {
        "*OPC?": "1", "SENS:AVER:COUN?": "2", "CALC:DATA:FDAT?": "-10,-20,-30",
    })
    assert io.events == ['INST:SEL "NA"', "*OPC?"]
    vna.single_sweep()
    assert io.events.count("INIT:IMM") == 2
    assert "SENS:AVER?" not in io.events
    assert vna._trace_values(1) == [-10, -20, -30]
    vna.set_averaging_count(3)
    vna.toggle_averaging(False)
    vna.toggle_averaging(True)
    assert io.events[-3:] == ["SENS:AVER:COUN 3", "SENS:AVER:COUN 1", "SENS:AVER:COUN 3"]


def test_teledyne_load_uses_native_function_and_short_commands():
    load, io = instrument("eload", "teledyne-t3el150303p")
    load.set_mode("CC")
    load.set_current(2)
    load.toggle_short(False)
    assert io.events == ["FUNC CURR", "CURR 2", "SHOR OFF"]
    with pytest.raises(EquipmentCapabilityError):
        load.toggle_list(True)
    assert len(io.events) == 3


def test_cg635_output_stops_global_clock_and_refuses_voltage_waveforms():
    clock, io = instrument("asg", "srs-cg635")
    clock.set_frequency(10e6)
    clock.set_output(False)
    assert io.events == ["FREQ 10000000.000000000000", "RUNS 0"]
    with pytest.raises(EquipmentCapabilityError):
        clock.set_amplitude_vpp(1)
    assert len(io.events) == 2


def test_33250a_uses_voltage_amplitude_and_real_high_impedance_load():
    generator, io = instrument("asg", "keysight-33250a")
    generator.set_amplitude_vpp(2)
    generator.set_load_ohms(float("inf"))
    assert io.events == ["VOLT:UNIT VPP", "VOLT 2.000000", "OUTP:LOAD INF"]
    with pytest.raises(EquipmentCapabilityError):
        generator.set_power(0)
    assert len(io.events) == 3


def test_handheld_keeps_mode_descriptor_and_does_not_configure_or_rearm():
    dmm, io = instrument("dmm", "keysight-u1272a", {"CONF?": '"V,0,DC"', "FETC?": "1.25"})
    assert dmm.get_function() == "V,0,DC"
    assert dmm.fetch() == 1.25
    with pytest.raises(EquipmentCapabilityError):
        dmm.measure_voltage()
    assert io.events == ["CONF?", "FETC?"]


def test_phase_noise_uses_actual_grid_and_log_offset_interpolation():
    pn, io = instrument("phasenoiseanalyzer", "keysight-e5052b", {
        "CALC:PN1:DATA:XDAT?": "10,1000", "CALC:PN1:TRAC1:DATA:PDAT?": "-80,-120",
    })
    assert pn.measure_spot_noise_dbc_hz(100) == pytest.approx(-100)
    assert "INIT:PN1:IMM" not in io.events
    with pytest.raises(EquipmentCapabilityError):
        pn.measure_spot_noise_dbc_hz(1)
    io.responses["CALC:PN1:DATA:XDAT?"] = "10,10"
    with pytest.raises(EquipmentResponseError):
        pn.measure_spot_noise_dbc_hz(10)


@pytest.mark.parametrize("file_format", ["bin", "mat", "iq.tar"])
def test_spike_iq_exports_interleaved_samples_with_consistent_scaling(tmp_path, monkeypatch, file_format):
    import json
    import struct
    import tarfile
    from pathlib import Path

    from scipy.io import loadmat
    monkeypatch.setattr("colosseum_equipment.instruments.rtsa.signalhound.resolve_artifact_path", Path)
    monkeypatch.setattr("colosseum_equipment.instruments.rtsa.signalhound.record_artifact", lambda **kw: None)
    rtsa, io = instrument("rtsa", "signalhound-bb60c-spike", {
        "FETC:ZS? 2": "2", "FETC:ZS? 1": "1,2,-3,-4",
        "SENS:ZS:CAP:SRAT?": "1000", "SENS:ZS:CAP:CENT?": "1e9",
    })
    path = rtsa.save_IQ_data(str(tmp_path / f"nested/capture.{file_format}"), file_format=file_format)
    if file_format == "bin":
        assert struct.unpack("<4d", path.read_bytes()) == (1, 2, -3, -4)
    elif file_format == "mat":
        assert loadmat(path)["iq"].ravel().tolist() == [1+2j, -3-4j]
    else:
        with tarfile.open(path) as archive:
            assert struct.unpack("<4d", archive.extractfile("iq.bin").read()) == (1, 2, -3, -4)
            metadata = json.load(archive.extractfile("metadata.json"))
        assert metadata["sample_rate_hz"] == 1000
        assert metadata["iq_units"] == "sqrt(mW)"
        assert metadata["iq_dtype"] == "float64"
    assert "INIT:IMM" not in io.events


def test_spike_rejects_incomplete_iq_before_creating_artifact(tmp_path):
    rtsa, _ = instrument("rtsa", "signalhound-sm200c-spike", {
        "FETC:ZS? 2": "2", "FETC:ZS? 1": "1,2,3",
    })
    with pytest.raises(EquipmentResponseError):
        rtsa.save_IQ_data(str(tmp_path / "bad.bin"))
    assert not (tmp_path / "bad.bin").exists()


@pytest.mark.parametrize("block", [b"#", b"#0abc", b"#Aabc", b"#21", b"#2xxabc", b"#15abc", b"#15helloJUNK", b"#131,2,3"])
def test_binary_block_rejects_malformed_or_truncated_records(block):
    from colosseum_equipment.protocols.scpi import parse_definite_length_block
    with pytest.raises(EquipmentResponseError):
        parse_definite_length_block(block)


def test_spike_spectrum_uses_reported_axis_and_single_detector_values():
    analyzer, io = instrument("speca", "signalhound-bb60c-spike", {
        "SENS:POW:RF:RLEV:UNIT?": "DBM", "*OPC?": "1", "TRAC:POIN?": "3",
        "TRAC:DATA?": "-80,-40,-70", "TRAC:XSTAR?": "100", "TRAC:XINC?": "2.5",
    })
    assert analyzer._fetch_trace(1) == ([100, 102.5, 105], [-80, -40, -70])
    assert "SENS:SWE:DET:FUNC MAX" in io.events
    io.responses["SENS:POW:RF:RLEV:UNIT?"] = "MV"
    with pytest.raises(EquipmentCapabilityError):
        analyzer._fetch_trace(1)


def test_rohde_waveform_keeps_native_scaled_voltage_and_rejects_current_probe():
    scope, io = instrument("oscope", "rohde-rtb2004", {
        "ACQ:STAT?": "COMP", "PROB1:SET:ATT:UNIT?": "V", "CHAN1:DATA:HEAD?": "-1,1,3,1",
        "CHAN1:DATA:XINC?": "0.5", "CHAN1:DATA:XOR?": "-1", "CHAN1:DATA?": "1,2,3",
    })
    values, meta = scope._read_waveform_points(1)
    assert values == [1, 2, 3]
    assert meta["xorigin_s"] == -1
    scope.set_record_length(10000)
    assert io.events[-1] == "ACQ:POIN 10000"
    io.responses["PROB1:SET:ATT:UNIT?"] = "A"
    with pytest.raises(EquipmentCapabilityError):
        scope._read_waveform_points(1)


def test_infiniium_word_waveform_uses_signed_little_endian_and_actual_origin():
    scope, io = instrument("oscope", "keysight-dsaz204a", {
        "ADER?": ["0", "1"], "CHAN1:UNIT?": "VOLT", "WAV:POIN?": "3",
        "WAV:XINC?": "0.25", "WAV:XOR?": "-1", "WAV:YINC?": "0.5", "WAV:YOR?": "1",
    })
    io.read_raw = lambda: b"#16\x00\x80\x00\x00\xff\x7f\n"
    scope.arm_single()
    values, meta = scope._read_waveform_points(1)
    assert values == [-16383, 1, 16384.5]
    assert meta["xorigin_s"] == -1
    assert meta["xinc_s"] == 0.25
    io.responses["CHAN1:UNIT?"] = "AMP"
    with pytest.raises(EquipmentCapabilityError):
        scope._read_waveform_points(1)


@pytest.mark.parametrize("state,expected", [("ON", True), ("OFF", False), ("1", True), ("0", False)])
def test_chroma_native_input_state_tokens(state, expected):
    load, _ = instrument("eload", "chroma-63600-5", {"LOAD?": state})
    assert load.measure_input_state() is expected


def test_chroma_voltage_and_power_require_static_subsystem():
    load, io = instrument("eload", "chroma-63600-5")
    load.set_voltage(5)
    load.set_power(10)
    assert io.events == ["CHAN 1", "VOLT:STAT:L1 5", "CHAN 1", "POW:STAT:L1 10"]


@pytest.mark.parametrize("model,commands", [
    ("tektronix-tsg4106a", ["FREQ 1000000000.000000", "AMPR -10.000000 DBM", "ENBR 0"]),
    ("anritsu-mg3692c", ["FREQ:MODE FIX", "FREQ 1000000000.000000HZ", "POW:MODE FIX", "POW -10.000000DBM", "OUTP OFF"]),
    ("keysight-8648c", ["FREQ:CW 1000000000.000000", "POW -10.000000DBM", "OUTP OFF"]),
])
def test_native_rf_dialects_do_not_enable_output_or_inherit_vector_commands(model, commands):
    source, io = instrument("vsg", model)
    source.set_frequency(1e9)
    source.set_power(-10)
    source.set_output(False)
    assert io.events == commands
    with pytest.raises(EquipmentCapabilityError):
        source.play_iq("test.bin", 1e9, -10, 1e6)
    assert io.events == commands


def test_afg_uses_native_amplitude_without_apply_output_side_effect():
    source, io = instrument("asg", "gwinstek-afg3032")
    source.set_amplitude_vpp(2, channel=2)
    source.set_output(False, channel=2)
    assert io.events == ["SOUR2:AMPL 2.000000VPP", "OUTP2 OFF"]
    with pytest.raises(EquipmentCapabilityError):
        source.set_waveform("sine", channel=2)
    assert not any("APPL" in event for event in io.events)


def test_genesys_serial_requires_address_and_uses_cr_acknowledgements():
    class NativeSerial(RecordingTransport):
        def write_bytes(self, data):
            self.events.append(data)

        def read_until(self, terminator):
            assert terminator == b"\r"
            return self.responses[self.events[-1].decode().strip()]

    io = NativeSerial({"ADR 3": "OK\r", "PV 5.000000": "OK\r", "OUT?": "OFF\r", "OUT 1": "E07\r"})
    config = {"model": "tdk-gen300-5-serial", "driver": "serial", "baudrate": 9600, "device_address": 3, "voltage": 5}
    psu = build_instrument("psu", 1, config, io)
    assert io.events == [b"ADR 3\r", b"PV 5.000000\r"]
    assert psu.get_output() is False
    with pytest.raises(EquipmentResponseError, match="E07"):
        psu.set_output(True)
    assert all(b"\n" not in command for command in io.events)
    with pytest.raises(EquipmentCapabilityError):
        build_instrument("psu", 1, {k: v for k, v in config.items() if k != "device_address"}, io)


@pytest.mark.parametrize("raw", ["CWO1,-25.1", "CWO 1,-25.1"])
def test_ml2495a_parses_native_labelled_cw_result(raw):
    meter, io = instrument("pwrmeter", "anritsu-ml2495a", {"CWO 1": raw})
    assert io.events == ["CHCFG 1,A", "CHMODE 1,CW", "CWREL 1,OFF", "CHUNIT 1,DBM"]
    assert meter.measure_power_dbm() == -25.1
    with pytest.raises(EquipmentCapabilityError):
        meter.acquire()


@pytest.mark.parametrize("raw", ["CWO2,-25", "CWO1,nan", "CWO1,1e", "CWO1,1,2", "CWO1,9.9e37"])
def test_ml2495a_rejects_other_channels_arrays_and_invalid_readings(raw):
    meter, _ = instrument("pwrmeter", "anritsu-ml2495a", {"CWO 1": raw})
    with pytest.raises(EquipmentResponseError):
        meter.measure_power_dbm()


def test_nrx_owns_sensor_mapping_and_fresh_bus_trigger_but_fetch_does_not_rearm():
    meter, io = instrument("pwrmeter", "rohde-nrx", {"*OPC?": "1", "FETC2?": "-15"}, channels=2)
    assert 'CALC2:MATH:EXPR "(SENS2)"' in io.events
    assert 'CALC2:TYPE CONTAV' in io.events
    assert 'CALC2:FEED1 "POW:AVER"' in io.events
    assert "CALC2:SENS:IND 2" in io.events
    io.events.clear()
    meter.acquire(channel=2)
    assert io.events == ["INIT2:CONT OFF", "TRIG2:SOUR BUS", "INIT2:IMM", "TRIG2:IMM", "*OPC?"]
    io.events.clear()
    assert meter.measure_power_avg_dbm(channel=2) == -15
    assert io.events == ["FETC2?"]


def test_modern_tek_word_waveform_checks_preamble_and_scales_big_endian():
    import struct
    scope, io = instrument("oscope", "tektronix-mso58", {
        "ACQuire:STATE?": "0", "WFMO:NR_PT?": "3", "WFMO:PT_FMT?": "YT",
        "WFMO:XUNIT?": '"s"', "WFMO:YUNIT?": '"V"', "WFMO:XINCR?": "0.25",
        "WFMO:XZERO?": "-1", "WFMO:PT_OFF?": "2", "WFMO:YMULT?": "0.5",
        "WFMO:YOFF?": "1", "WFMO:YZERO?": "2",
    })
    io.read_raw = lambda: b"#16" + struct.pack(">3h", -32768, 0, 32767)
    values, meta = scope._read_waveform_points(8)
    assert values == [-16382.5, 1.5, 16385]
    assert meta["xorigin_s"] == -1.5
    assert "DATA:SOU CH8" in io.events
    scope.set_channel_display(8, True)
    assert io.events[-1] == "DISP:WAVEV1:CH8:STATE 1"
    io.responses["WFMO:PT_FMT?"] = "ENV"
    with pytest.raises(EquipmentCapabilityError):
        scope._read_waveform_points(8)
    io.responses["WFMO:PT_FMT?"] = "YT"
    io.read_raw = lambda: b"#14abcd"
    with pytest.raises(EquipmentResponseError):
        scope._read_waveform_points(8)


def test_anritsu_binary_trace_uses_operation_bit8_and_little_endian():
    import struct
    analyzer, io = instrument("speca", "anritsu-ms2721b", {
        "INST:SEL?": "SPA", "STAT:OPER?": ["0", "256"], "FREQ:STAR?": "100", "FREQ:STOP?": "200",
    })
    io.read_raw = lambda: b"#212" + struct.pack("<3f", -80, -20, -60)
    assert analyzer._fetch_trace(1) == ([100, 150, 200], [-80, -20, -60])
    assert "*OPC?" not in io.events
    assert "TRAC:DATA? 1" in io.events
    assert io.events.count("STAT:OPER?") == 2
    with pytest.raises(EquipmentCapabilityError):
        instrument("speca", "anritsu-ms2720t", {"INST:SEL?": "VNA"})


def test_fpc_spectrum_uses_actual_trace_length_instead_of_vna_point_query():
    analyzer, io = instrument("speca", "rohde-fpc1500", {
        "*OPC?": "1", "TRAC:DATA? TRACE2": "-80,-20,-70", "FREQ:STAR?": "1", "FREQ:STOP?": "5",
    })
    assert io.events == ["INST:SEL SPEC"]
    assert analyzer._fetch_trace(2) == ([1, 3, 5], [-80, -20, -70])
    assert "DISP:TRAC2:MODE WRIT" in io.events
    assert not any("POIN" in event for event in io.events)


def test_hp_legacy_trace_restores_clear_write_before_every_sweep():
    analyzer, io = instrument("speca", "keysight-8563ec", {
        "TRA?;": ",".join(["-40"] * 601), "FA?;": "100", "FB?;": "700",
    })
    axis, values = analyzer._fetch_trace(1)
    assert axis == list(range(100, 701))
    assert len(values) == 601
    assert io.events[:4] == ["AUNITS DBM;", "CLRW TRA;", "SNGLS;TS;", "TDF P;"]
    analyzer.set_marker_frequency(1, 123)
    assert io.events[-1] == "MKN 123.000000HZ;"
    with pytest.raises(EquipmentCapabilityError):
        analyzer.measure_marker_power()


def test_pla_does_not_reuse_generic_slew_rate_as_native_slew_time():
    load, io = instrument("eload", "ametek-pla4k-600-240")
    load.set_mode("CC")
    load.set_current(1)
    load.disengage()
    assert io.events == ["MODE CC", "CURR 1", "INP OFF"]
    with pytest.raises(EquipmentCapabilityError):
        load.set_slew_rate(100)


@pytest.mark.parametrize("file_format", ["bin", "mat", "iq.tar"])
def test_native_rsa_iq_uses_last_record_header_and_float32_not_digital_scale(tmp_path, monkeypatch, file_format):
    import json
    import struct
    import tarfile
    from pathlib import Path

    from scipy.io import loadmat
    monkeypatch.setattr("colosseum_equipment.instruments.rtsa.tektronix_native.resolve_artifact_path", Path)
    monkeypatch.setattr("colosseum_equipment.instruments.rtsa.tektronix_native.record_artifact", lambda **kw: None)
    analyzer, io = instrument("rtsa", "tektronix-rsa5126b", {
        "FETC:RFIN:REC:IDS?": "10,12",
        "FETC:RFIN:IQ:HEAD? 12": '1000,2000,2,1e9,800,-10,0.001,"2026-10-20T12:00:00",-1',
    })
    io.read_raw = lambda: b"#216" + struct.pack("<4f", 1, 2, -3, -4)
    path = analyzer.save_IQ_data(str(tmp_path / f"nested/native.{file_format}"), file_format=file_format)
    if file_format == "bin":
        assert struct.unpack("<4d", path.read_bytes()) == (1, 2, -3, -4)
    elif file_format == "mat":
        assert loadmat(path)["iq"].ravel().tolist() == [1+2j, -3-4j]
    else:
        with tarfile.open(path) as archive:
            assert struct.unpack("<4d", archive.extractfile("iq.bin").read()) == (1, 2, -3, -4)
            meta = json.load(archive.extractfile("metadata.json"))
        assert meta["sample_rate_hz"] == 2000
        assert meta["record_id"] == 12
        assert meta["num_samples"] == 2
        assert meta["iq_units"] == "native floating IQ"
    assert "FETC:RFIN:IQ? 12" in io.events
    assert not any("SCAL" in event or "INIT" in event for event in io.events)
    io.responses["FETC:RFIN:IQ:HEAD? 12"] = '1000,2000,2,1e9,800,-10,0.001,"time",0'
    with pytest.raises(EquipmentCapabilityError, match="FastFrame"):
        analyzer.get_num_samples()


def test_native_rsa_spectrum_uses_rf_sense_commands_and_rejects_log_axis(tmp_path, monkeypatch):
    import struct
    from pathlib import Path
    monkeypatch.setattr("colosseum_equipment.instruments.rtsa.tektronix_native.resolve_artifact_path", Path)
    monkeypatch.setattr("colosseum_equipment.instruments.rtsa.tektronix_native.record_artifact", lambda **kw: None)
    analyzer, io = instrument("rtsa", "tektronix-rsa6114a", {
        "SENS:POW:UNIT?": "DBM", "DISP:SPEC:SCAL:LOG:STAT?": "0",
        "SENS:SPEC:FREQ:STAR?": "100", "SENS:SPEC:FREQ:STOP?": "200",
    })
    io.read_raw = lambda: b"#18" + struct.pack("<2f", -40, -60)
    analyzer.set_center_freq(150)
    assert io.events[-1] == "SENS:SPEC:FREQ:CENT 150.000000"
    result = analyzer.save_spectrum_trace_data(str(tmp_path / "spectrum.csv"))
    assert "100" in result.read_text() and "200" in result.read_text()
    io.responses["DISP:SPEC:SCAL:LOG:STAT?"] = "1"
    with pytest.raises(EquipmentCapabilityError):
        analyzer.save_spectrum_trace_data(str(tmp_path / "log.csv"))
    assert not (tmp_path / "log.csv").exists()
    with pytest.raises(EquipmentCapabilityError):
        analyzer.save_IQ_data(str(tmp_path / "unsupported.bin"))


@pytest.mark.parametrize("header,payload,error", [
    ('1000,2000,2,1e9,800,-10,0,"time",-1', b"#18abcdefgh", EquipmentResponseError),
    ('1000,0,2,1e9,800,-10,0,"time",-1', b"", EquipmentResponseError),
    ('1000,2000,2.5,1e9,800,-10,0,"time",-1', b"", EquipmentResponseError),
    ('1000,2000,2,1e9,800,-10,0,"time",0', b"", EquipmentCapabilityError),
])
def test_native_rsa_rejects_incomplete_or_invalid_iq_before_export(tmp_path, header, payload, error):
    analyzer, io = instrument("rtsa", "tektronix-rsa5115b", {
        "FETC:RFIN:REC:IDS?": "10,12", "FETC:RFIN:IQ:HEAD? 12": header,
    })
    io.read_raw = lambda: payload
    with pytest.raises(error):
        analyzer.save_IQ_data(str(tmp_path / "bad.bin"))
    assert not (tmp_path / "bad.bin").exists()


class FlukeSerialTransport(RecordingTransport):
    def __init__(self, frames):
        super().__init__()
        self.frames = list(frames)

    def write_bytes(self, payload):
        self.events.append(payload)

    def read_until(self, terminator):
        assert terminator == b"\r"
        return self.frames.pop(0)


def fluke(model, frames):
    io = FlukeSerialTransport(frames)
    driver = build_instrument("dmm", 1, {
        "model": model, "driver": "serial", "baudrate": 9600 if model == "fluke-189" else 115200,
    }, io)
    return driver, io


@pytest.mark.parametrize("model,reply,expected,unit", [
    ("fluke-289", "-0.023E-3,VDC,NORMAL,NONE\r", -0.000023, "VDC"),
    ("fluke-189", "QM,+47.66 KOhms\r", 47660, "OHM"),
    ("fluke-189", "QM,-121.43 mV DC\r", -0.12143, "VDC"),
    ("fluke-189", "QM,+0.95 uFarads\r", 0.95e-6, "F"),
    ("fluke-189", "QM,+10.00 MOhms\r", 1e7, "OHM"),
])
def test_fluke_qm_ack_data_framing_and_legacy_display_prefixes(model, reply, expected, unit):
    meter, io = fluke(model, ["0\r", reply, "0\r", reply])
    assert io.events == []
    assert meter.fetch() == pytest.approx(expected)
    assert meter.get_function() == unit
    assert io.events == [b"QM\r", b"QM\r"]
    with pytest.raises(EquipmentCapabilityError):
        meter.initiate()
    with pytest.raises(EquipmentCapabilityError):
        meter.set_function("VOLT:DC")
    assert io.events == [b"QM\r", b"QM\r"]


@pytest.mark.parametrize("model,frames", [
    ("fluke-289", ["5\r"]),
    ("fluke-289", ["2\r"]),
    ("fluke-289", ["0"]),
    ("fluke-289", ["0\r", "1,VDC,NORMAL,NONE"]),
    ("fluke-289", ["0\r", "9.99999999e37,VDC,OL,NONE\r"]),
    ("fluke-289", ["0\r", "nan,VDC,NORMAL,NONE\r"]),
    ("fluke-289", ["0\r", "1,VDC,BLANK,NONE\r"]),
    ("fluke-189", ["0\r", "QM,Out of Range mVDC\r"]),
    ("fluke-189", ["0\r", "1,VDC,NORMAL,NONE\r"]),
])
def test_fluke_rejects_ack_errors_incomplete_frames_and_unavailable_values(model, frames):
    meter, io = fluke(model, frames)
    with pytest.raises(EquipmentResponseError):
        meter.fetch()
    assert io.events == [b"QM\r"]


def test_fluke_requires_native_serial_configuration_and_refuses_other_channels_before_io():
    with pytest.raises(EquipmentCapabilityError):
        instrument("dmm", "fluke-189", driver="serial", baudrate=115200)
    meter, io = fluke("fluke-289", [])
    with pytest.raises(EquipmentCapabilityError):
        meter.fetch(channel=2)
    assert io.events == []


def rte(responses=None, model="rohde-rte1204"):
    return instrument("oscope", model, {
        "ACQ:SEGM:STAT?": "0", "*ESR?": ["1", "0", "1"], "ACQ:CURR?": "1",
        "CHAN2:WAV1:HIST:STAT?": "0", "PROB2:SET:ATT:MODE?": "MAN", "PROB2:SET:ATT:UNIT?": "V",
        "CHAN2:WAV1:DATA:HEAD?": "-0.5,0.5,3,1", "CHAN2:WAV1:DATA?": "-1,0,2",
        **(responses or {}),
    })


@pytest.mark.parametrize("model", ["rohde-rte1204", "rohde-rtp164"])
def test_rte_rtp_clear_stale_opc_then_wait_for_new_acquisition_and_native_waveform(model):
    scope, io = rte(model=model)
    with pytest.raises(EquipmentCapabilityError):
        scope._read_waveform_points(2)
    scope.arm_single()
    assert io.events == ["ACQ:SEGM:STAT?", "STOP", "*ESR?", "ACQ:COUN 1", "RUNS", "*OPC"]
    scope.wait_complete(timeout_s=1)
    assert io.events[-3:] == ["*ESR?", "*ESR?", "ACQ:CURR?"]
    before_fetch = len(io.events)
    values, meta = scope._read_waveform_points(2)
    assert values == [-1, 0, 2]
    assert (meta["xorigin_s"], meta["xinc_s"]) == (-0.5, 0.5)
    assert io.events[before_fetch:] == [
        "CHAN2:WAV1:HIST:STAT?", "PROB2:SET:ATT:MODE?", "PROB2:SET:ATT:UNIT?", "EXP:WAV:MULT OFF",
        "EXP:WAV:INCX OFF", "EXP:WAV:RAW OFF", "EXP:WAV:SCOP WFM", "FORM ASC",
        "CHAN2:WAV1:DATA:HEAD?", "CHAN2:WAV1:DATA?",
    ]
    scope.stop()
    with pytest.raises(EquipmentCapabilityError):
        scope._read_waveform_points(2)


@pytest.mark.parametrize("responses,error", [
    ({"CHAN2:WAV1:HIST:STAT?": "1"}, EquipmentCapabilityError),
    ({"PROB2:SET:ATT:UNIT?": "A"}, EquipmentCapabilityError),
    ({"PROB2:SET:ATT:MODE?": "AUTO"}, EquipmentCapabilityError),
    ({"CHAN2:WAV1:DATA:HEAD?": "-1,1,3,2"}, EquipmentCapabilityError),
    ({"CHAN2:WAV1:DATA:HEAD?": "-1,1,3.5,1"}, EquipmentResponseError),
    ({"CHAN2:WAV1:DATA:HEAD?": "-1,nan,3,1"}, EquipmentResponseError),
    ({"CHAN2:WAV1:DATA:HEAD?": "-1,1,3"}, EquipmentResponseError),
    ({"CHAN2:WAV1:DATA?": "1,2"}, EquipmentResponseError),
    ({"CHAN2:WAV1:DATA?": "1,2,3,4"}, EquipmentResponseError),
    ({"CHAN2:WAV1:DATA?": "1,nan,3"}, EquipmentResponseError),
])
def test_rte_rtp_rejects_ambiguous_axes_units_and_non_scalar_or_incomplete_data(responses, error):
    scope, _ = rte(responses)
    scope.acquire(timeout_s=1)
    with pytest.raises(error):
        scope._read_waveform_points(2)


def test_rte_rtp_cannot_promote_interrupted_or_errored_acquisition_to_complete():
    for responses in ({"ACQ:CURR?": "0"}, {"*ESR?": ["0", "32"]}):
        scope, _ = rte(responses)
        scope.arm_single()
        with pytest.raises(EquipmentResponseError):
            scope.wait_complete(timeout_s=1)
        with pytest.raises(EquipmentCapabilityError):
            scope._read_waveform_points(2)
    scope, io = rte({"ACQ:SEGM:STAT?": "1"})
    with pytest.raises(EquipmentCapabilityError):
        scope.arm_single()
    assert io.events == ["ACQ:SEGM:STAT?"]


def test_rte_rtp_absent_trigger_times_out_without_exporting_old_data():
    from colosseum_equipment.exceptions import EquipmentTimeoutError
    scope, io = rte({"*ESR?": "0"})
    scope.arm_single()
    with pytest.raises(EquipmentTimeoutError):
        scope.wait_complete(timeout_s=0)
    with pytest.raises(EquipmentCapabilityError):
        scope._read_waveform_points(2)
    scope.abort()
    assert io.events[-1] == "STOP"


@pytest.mark.parametrize("model,trace", [("keysight-n9020a", 6), ("keysight-e4440a", 3)])
def test_keysight_spectrum_fetch_unfreezes_requested_trace_before_immediate_sweep(model, trace):
    analyzer, io = instrument("speca", model, {
        "*OPC?": "1", "FREQ:CENT?": "100", "FREQ:SPAN?": "10",
        f"TRAC:DATA? TRACE{trace}": "-30,-10,-40", "SWE:POIN?": "3",
    })
    analyzer._fetch_trace(trace)
    unfreeze = io.events.index(f"TRAC{trace}:MODE WRIT")
    trigger = io.events.index("TRIG:SOUR IMM")
    sweep = io.events.index("INIT:IMM")
    fetch = io.events.index(f"TRAC:DATA? TRACE{trace}")
    assert unfreeze < trigger < sweep < fetch
    analyzer.set_detector("POS")
    assert io.events[-1] == ("DET POS" if model == "keysight-e4440a" else "DET:TRAC1 POS")
    if model == "keysight-e4440a":
        io.events.clear()
        with pytest.raises(ValueError):
            analyzer._fetch_trace(4)
        assert io.events == []


@pytest.mark.parametrize("model,channel", [
    ("keysight-e4417a", 2), ("keysight-n1912a", 2),
    ("keysight-u8487a", 1), ("keysight-u8488a", 1), ("rohde-nrp18s", 1),
])
def test_average_power_acquisition_cannot_inherit_external_or_bus_trigger(model, channel):
    meter, io = instrument("pwrmeter", model, {"*OPC?": "1"})
    io.events.clear()
    meter.acquire(channel=channel)
    suffix = str(channel) if model in {"keysight-e4417a", "keysight-n1912a"} else ""
    assert io.events.index(f"INIT{suffix}:CONT OFF") < io.events.index(f"TRIG{suffix}:SOUR IMM")
    assert io.events.index(f"TRIG{suffix}:SOUR IMM") < io.events.index(f"INIT{suffix}:IMM")
    assert io.events[-1] == "*OPC?"


@pytest.mark.parametrize("model", ["keysight-n5245b", "keysight-e8362b"])
def test_pna_sweep_addresses_channel_without_indexing_global_continuous_command(model):
    vna, io = instrument("vna", model, {"SENS2:AVER?": "0", "*OPC?": "1"}, channel=2)
    vna.single_sweep()
    assert io.events == ["SENS2:AVER?", "TRIG:SOUR IMM", "SENS2:SWE:MODE SING", "*OPC?"]


@pytest.mark.parametrize("frames", [["OK"], ["OK\r", "5.00"]])
def test_native_genesys_rejects_unterminated_ack_or_measurement(frames):
    io = FlukeSerialTransport(frames)
    config = {"model": "tdk-gen300-5-serial", "driver": "serial", "baudrate": 9600, "device_address": 3}
    with pytest.raises(EquipmentResponseError, match="incomplete"):
        psu = build_instrument("psu", 1, config, io)
        psu.get_voltage()


@pytest.mark.parametrize("raw", ["#2131.0,2.0,3.0", "#x11.0,2.0,3.0", "#211.0,2.0,3.0", "#151,2,3,4,5"])
def test_ascii_waveform_parser_checks_declared_block_length_even_when_sample_count_matches(raw):
    from colosseum_equipment.instruments.oscope.generic import _parse_ascii_waveform
    with pytest.raises(EquipmentResponseError):
        _parse_ascii_waveform(raw, points_expected=3)


def test_ascii_waveform_block_preserves_payload_whitespace_and_legacy_indefinite_format():
    from colosseum_equipment.instruments.oscope.generic import _parse_ascii_waveform
    # Eight payload bytes: leading/trailing blanks are included in the length.
    assert _parse_ascii_waveform("#18 1,2,3  \n", points_expected=3) == [1, 2, 3]
    assert _parse_ascii_waveform("#01,2,3\n", points_expected=3) == [1, 2, 3]


@pytest.mark.parametrize("address", [3.5, True, "3.5", float("nan")])
def test_genesys_address_is_never_truncated_to_a_different_device(address):
    io = FlukeSerialTransport(["OK\r"])
    with pytest.raises(ValueError, match="address"):
        build_instrument("psu", 1, {
            "model": "tdk-gen300-5-serial", "driver": "serial", "baudrate": 9600,
            "device_address": address,
        }, io)
    assert io.events == []


def test_case_insensitive_tds_model_still_enforces_two_physical_channels():
    scope, io = instrument("oscope", "TEKTRONIX-TDS3032B")
    io.events.clear()
    with pytest.raises(EquipmentCapabilityError):
        scope.set_channel_display(3, True)
    assert io.events == []
