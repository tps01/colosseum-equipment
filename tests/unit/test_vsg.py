"""VSG SCPI delegation, waveform upload transport selection, and sweep helpers."""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest
import pyvisa
from colosseum_equipment.exceptions import EquipmentCapabilityError, EquipmentResponseError
from colosseum_equipment.instruments.factory import build_instrument
from colosseum_equipment.instruments.vsg.generic import GenericVSG
from colosseum_equipment.instruments.vsg.keysight_esg import KeysightESGVSG
from colosseum_equipment.transports.visa import VISATransport

from tests.support.stubs import RfStubTransport


def test_generic_vsg_scpi_fallbacks_write_commands() -> None:
    transport = RfStubTransport({"*OPC?": "1"})
    inst = build_instrument("vsg", 1, {"model": "generic"}, transport)
    assert isinstance(inst, GenericVSG)

    inst.preset()
    inst.set_alc(True)
    inst.set_attenuation(10.0)
    inst.set_phase(45.0)
    inst.set_output_blanking(False)
    inst.delete_waveform("WFM1:test.bin")
    inst.play_iq("WFM1:test.bin", 1e9, -10.0, 100e6)
    inst.set_pulsegen_output(True)
    inst.pulse_source("EXT1")
    inst.freq_sweep(1e9, 2e9, 11, 0.5)
    inst.set_modulation(True, "AM")

    assert transport.written == [
        "*RST",
        "POW:ALC ON",
        "POW:ATT 10.000",
        "PHAS 45.000",
        "OUTP:BLAN OFF",
        'MMEM:DEL "WFM1:test.bin"',
        'RAD:ARB:WAV "WFM1:test.bin"',
        "FREQ:CW 1000000000.000000",
        "POW:AMPL -10.000",
        "RAD:ARB:SCLock:RATE 100000000.000000",
        "RAD:ARB:STAT ON",
        "OUTP:MOD ON",
        "PULM:STAT ON",
        "PULM:SOUR EXT1",
        "LIST:TYPE STEP",
        "FREQ:STAR 1000000000.000000",
        "FREQ:STOP 2000000000.000000",
        "SWE:POIN 11",
        "SWE:DWEL 0.500000000",
        "INIT:CONT ON",
        "SOUR:MOD:TYPE AM",
        "OUTP:MOD ON",
    ]


def test_keysight_vsg_control_commands_write_scpi() -> None:
    transport = RfStubTransport({"*IDN?": "Agilent Technologies,E4438C,1,1", "*OPC?": "1"})
    inst = build_instrument("vsg", 1, {"model": "keysight-esg"}, transport)
    assert isinstance(inst, KeysightESGVSG)

    inst.pulse_source("PULSE")
    inst.pulse_source("EXT2")
    inst.toggle_multitone(True)
    inst.delete_waveform("WFM1:IQ.bin")
    inst.delete_all_waveforms()
    inst.set_multicarrier(4, 1e6)
    inst.freq_sweep(1e9, 2e9, 11, 0.5)
    inst.step_power(-20.0, -10.0, 2.0, 0.25)
    inst.set_pulse_period(0.001)
    inst.set_pulse_width(0.0001)

    assert transport.written == [
        "PULM:SOUR INT",
        "PULM:INT:FUNC SHAP PULS",
        "PULM:SOUR EXT2",
        "RAD:MTONe:ARB:STAT 1",
        'MMEM:DEL "WFM1:IQ.bin"',
        "MMEM:DEL:WFM1",
        "RAD:DMOD:ARB:SETup:MCARrier:TABLe INIT,CUSTom,4,1000000.000000",
        "LIST:TYPE STEP",
        "FREQ:STAR 1000000000.000000",
        "FREQ:STOP 2000000000.000000",
        "SWE:POIN 11",
        "SWE:DWEL 0.500000000",
        "INIT:CONT ON",
        "LIST:TYPE STEP",
        "POW:STAR -20.000",
        "POW:STOP -10.000",
        "SWE:POIN 6",
        "SWE:DWEL 0.250000000",
        "LIST:TRIG:SOUR IMM",
        "INIT:CONT ON",
        "PULM:INT:PER 0.001000000",
        "PULM:INT:PWID 0.000100000",
    ]


def test_vector_esg_queries_frequency_and_power_without_a_leading_colon() -> None:
    transport = RfStubTransport(
        {
            "*IDN?": "Agilent Technologies,E4438C,1,1",
            "FREQ:CW?": "2437000000.000000",
            "POW:AMPL?": "-20.000",
        },
    )
    inst = build_instrument("vsg", 1, {"model": "keysight-esg"}, transport)
    assert isinstance(inst, KeysightESGVSG)
    assert inst.measure_frequency() == pytest.approx(2.437e9)
    assert inst.measure_power_dbm() == pytest.approx(-20.0)


def test_vector_esg_output_command_is_numeric() -> None:
    transport = RfStubTransport({"*IDN?": "Agilent Technologies,E4438C,1,1"})
    inst = build_instrument("vsg", 1, {"model": "keysight-esg"}, transport)
    assert isinstance(inst, KeysightESGVSG)
    inst.set_output(True)
    inst.set_output(False)
    assert transport.written == ["OUTP:STAT 1", "OUTP:STAT 0"]


def test_vector_esg_rejects_unprogrammed_modulation() -> None:
    transport = RfStubTransport({"*IDN?": "Agilent Technologies,E4438C,1,1"})
    inst = build_instrument("vsg", 1, {"model": "keysight-esg"}, transport)
    assert isinstance(inst, KeysightESGVSG)
    with pytest.raises(EquipmentCapabilityError, match="WLAN"):
        inst.set_modulation(True, "WLAN")
    assert transport.written == []


def test_vector_esg_digital_mod_toggles_dm_stat() -> None:
    transport = RfStubTransport({"*IDN?": "Agilent Technologies,E4438C,1,1"})
    inst = build_instrument("vsg", 1, {"model": "keysight-esg"}, transport)
    assert isinstance(inst, KeysightESGVSG)
    inst.set_modulation(True, "none")
    inst.set_modulation(False, "dm")
    assert transport.written == ["DM:STAT 1", "DM:STAT 0"]


def test_play_iq_writes_composite_scpi() -> None:
    transport = RfStubTransport({"*IDN?": "Agilent Technologies,E4438C,1,1"})
    inst = build_instrument("vsg", 1, {"model": "keysight-esg"}, transport)
    inst.play_iq("WFM1:IQ.bin", 1.5e9, -12.0, 100e6)
    assert transport.written == [
        'RAD:ARB:WAV "WFM1:IQ.bin"',
        "FREQ:CW 1500000000.000000",
        "POW:AMPL -12.000",
        "RAD:ARB:SCLock:RATE 100000000.000000",
        "RAD:ARB:STAT 1",
        "OUTP:MOD ON",
    ]


def test_keysight_esg_analog_modulation_uses_am_fm() -> None:
    transport = RfStubTransport({"*IDN?": "Agilent Technologies,E4428C,1,1"})
    inst = build_instrument("vsg", 1, {"model": "keysight-esg"}, transport)
    inst.set_modulation(True, "AM")
    inst.set_modulation(False)
    assert transport.written == [
        "AM:STAT ON",
        "OUTP:MOD ON",
        "AM:STAT OFF",
        "FM:STAT OFF",
        "PM:STAT OFF",
        "OUTP:MOD OFF",
    ]


def test_keysight_esg_vector_modulation_uses_dm_stat() -> None:
    transport = RfStubTransport({"*IDN?": "Agilent Technologies,E4438C,1,1"})
    inst = build_instrument("vsg", 1, {"model": "keysight-esg"}, transport)
    inst.set_modulation(True, "AM")
    assert transport.written == ["DM:STAT 1"]


def _waveform(tmp_path, payload: bytes):
    path = tmp_path / "iq.bin"
    path.write_bytes(payload)
    return path


def _esg(config: dict, transport: RfStubTransport | None = None):
    responses = {"*IDN?": "Agilent Technologies,E4438C,1,1", "*OPC?": "1"}
    inst_transport = transport or RfStubTransport(responses)
    if transport is not None and not transport._responses:
        transport._responses.update(responses)
    return build_instrument("vsg", 1, {"model": "keysight-esg", **config}, inst_transport), inst_transport


def _pump_ftp(store: dict):
    def _store(cmd, fp, blocksize=8192, callback=None, rest=None):
        sent = bytearray()
        while True:
            chunk = fp.read(blocksize)
            if not chunk:
                break
            sent.extend(chunk)
            if callback is not None:
                callback(chunk)
        store["cmd"] = cmd
        store["blocksize"] = blocksize
        store["sent"] = bytes(sent)

    mock_ftp = MagicMock()
    mock_ftp.__enter__.return_value = mock_ftp
    mock_ftp.storbinary.side_effect = _store
    return mock_ftp


def test_upload_waveform_tcp_binary_block(tmp_path) -> None:
    payload = b"\x00\x01\x02\x03" * 4
    waveform = _waveform(tmp_path, payload)
    transport = RfStubTransport()
    seen: dict[str, int] = {}

    @contextmanager
    def large_binary_write(nbytes: int):
        seen["nbytes"] = nbytes
        seen["chunk_size"] = nbytes
        yield

    transport.large_binary_write = large_binary_write  # type: ignore[method-assign]
    inst, transport = _esg(
        {"resource": "TCPIP0::192.168.0.10::inst0::INSTR"},
        transport,
    )
    inst.upload_waveform(str(waveform), "WFM1:IQ.bin", method="tcpip")
    assert len(transport.raw_written) == 1
    assert b'MMEM:DATA "WFM1:IQ.bin" ' in transport.raw_written[0]
    assert transport.raw_written[0].endswith(b"\n")
    assert seen["chunk_size"] == seen["nbytes"] == len(transport.raw_written[0])


def test_large_binary_write_sets_chunk_size_and_nodelay() -> None:
    transport = VISATransport.__new__(VISATransport)
    session = MagicMock()
    session.chunk_size = 20480
    session.get_visa_attribute.return_value = 0
    transport._inst = session
    transport._timeout = 5.0
    transport._resource = "TCPIP0::10.0.0.5::inst0::INSTR"
    with transport.large_binary_write(1_000_000):
        assert session.chunk_size == 1_000_000
        assert transport._timeout > 5.0
    assert session.chunk_size == 20480
    assert transport._timeout == 5.0
    session.set_visa_attribute.assert_any_call(
        pyvisa.constants.VI_ATTR_TCPIP_NODELAY,
        pyvisa.constants.VI_TRUE,
    )


def test_upload_waveform_auto_tcpip_uses_ftp(tmp_path) -> None:
    payload = b"\x00\x01\x02\x03" * 4
    waveform = _waveform(tmp_path, payload)
    inst, transport = _esg({"resource": "TCPIP0::192.168.0.10::inst0::INSTR"})
    store: dict = {}
    mock_ftp = _pump_ftp(store)
    with patch(
        "colosseum_equipment.instruments.vsg.waveform_upload.ftplib.FTP",
        return_value=mock_ftp,
    ):
        inst.upload_waveform(str(waveform), "WFM1:IQ.bin")
    assert transport.raw_written == []
    assert store["cmd"] == "STOR /USER/BBG1/WAVEFORM/IQ.bin"
    assert store["blocksize"] == 8192
    assert store["sent"] == payload
    mock_ftp.login.assert_called_once_with(user="anonymous", passwd="")


def test_upload_waveform_auto_without_ftp_host_uses_scpi(tmp_path) -> None:
    waveform = _waveform(tmp_path, b"\x00\x01\x02\x03" * 4)
    inst, transport = _esg({"resource": "GPIB::19::INSTR"})
    inst.upload_waveform(str(waveform), "WFM1:IQ.bin")
    assert len(transport.raw_written) == 1
    assert b"MMEM:DATA" in transport.raw_written[0]


def test_upload_waveform_ftp_fallback(tmp_path) -> None:
    payload = b"\x00\x01\x02\x03" * 4
    waveform = _waveform(tmp_path, payload)
    inst, _transport = _esg({"resource": "GPIB::19::INSTR", "ftp_host": "10.0.0.5"})
    store: dict = {}
    mock_ftp = _pump_ftp(store)
    with patch(
        "colosseum_equipment.instruments.vsg.waveform_upload.ftplib.FTP",
        return_value=mock_ftp,
    ):
        inst.upload_waveform(str(waveform), "WFM1:IQ.bin")
    assert store["cmd"] == "STOR /USER/BBG1/WAVEFORM/IQ.bin"
    assert store["blocksize"] == 8192
    assert store["sent"] == payload


def test_upload_method_config_selects_tcpip(tmp_path) -> None:
    waveform = _waveform(tmp_path, b"\x00\x01\x02\x03" * 4)
    inst, transport = _esg(
        {
            "resource": "TCPIP0::192.168.0.10::inst0::INSTR",
            "upload_method": "tcpip",
        },
    )
    inst.upload_waveform(str(waveform), "WFM1:IQ.bin")
    assert len(transport.raw_written) == 1
    assert b"MMEM:DATA" in transport.raw_written[0]


def test_upload_method_call_overrides_config(tmp_path) -> None:
    payload = b"\x00\x01\x02\x03" * 4
    waveform = _waveform(tmp_path, payload)
    inst, transport = _esg(
        {
            "resource": "GPIB::19::INSTR",
            "ftp_host": "10.0.0.5",
            "upload_method": "tcpip",
        },
    )
    store: dict = {}
    mock_ftp = _pump_ftp(store)
    with patch(
        "colosseum_equipment.instruments.vsg.waveform_upload.ftplib.FTP",
        return_value=mock_ftp,
    ):
        inst.upload_waveform(str(waveform), "WFM1:IQ.bin", method="ftp")
    assert transport.raw_written == []
    assert store["sent"] == payload
    assert store["blocksize"] == 8192


def test_upload_waveform_tcpip_without_write_raw_raises(tmp_path) -> None:
    waveform = _waveform(tmp_path, b"\x00\x01\x02\x03" * 4)

    class _TextOnly(RfStubTransport):
        write_raw = None  # type: ignore[assignment]

    inst, _transport = _esg({"resource": "GPIB::19::INSTR"}, _TextOnly())
    with pytest.raises(EquipmentResponseError, match="write_raw"):
        inst.upload_waveform(str(waveform), "WFM1:IQ.bin", method="tcpip")


def test_upload_waveform_first_last_blanking(tmp_path) -> None:
    waveform = _waveform(tmp_path, b"\x00\x01\x02\x03" * 5)
    inst, transport = _esg({"resource": "TCPIP0::192.168.0.10::inst0::INSTR"})
    inst.upload_waveform(str(waveform), "WFM1:IQ.bin", first_last_blanking=True, method="tcpip")
    assert 'RAD:ARB:MARK:CLEAR:ALL "WFM1:IQ.bin",1' in transport.written
    assert 'RAD:ARB:MARK:SET "WFM1:IQ.bin",1,1,1,1,0' in transport.written
    assert 'RAD:ARB:MARK:SET "WFM1:IQ.bin",1,5,1,1,0' in transport.written
    assert "RAD:ARB:MDEStination:PULSe M1" in transport.written
