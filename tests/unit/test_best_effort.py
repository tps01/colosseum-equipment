"""Named models inherit generic SCPI and warn once; overrides stay quiet."""

from __future__ import annotations

import logging

import pytest
from colosseum_equipment.exceptions import EquipmentCapabilityError
from colosseum_equipment.instruments.factory import build_instrument
from colosseum_equipment.instruments.registry import instrument_model, reset_best_effort_warnings
from colosseum_equipment.instruments.rtsa.generic import GenericRtsa
from colosseum_equipment.instruments.vsg.generic import GenericVSG
from colosseum_equipment.instruments.vsg.keysight_esg import KeysightESGVSG

from tests.support.stubs import RfStubTransport, StubTransport


def test_inherited_generic_command_warns_once(caplog: pytest.LogCaptureFixture) -> None:
    reset_best_effort_warnings()

    @instrument_model("rtsa", "unit-test-rtsa")
    class _Inherited(GenericRtsa):
        """Manual: https://example.invalid/rtsa"""

    transport = RfStubTransport()
    instrument = _Inherited(transport, {"model": "unit-test-rtsa"})
    with caplog.at_level(logging.WARNING, logger="colosseum.equipment"):
        instrument.set_center_freq(1e9)
        instrument.set_center_freq(2e9)
    assert transport.written == ["FREQ:CENT 1000000000.000000", "FREQ:CENT 2000000000.000000"]
    warnings = [record for record in caplog.records if "unit-test-rtsa" in record.message]
    assert len(warnings) == 1
    assert "set_center_freq" in warnings[0].message


def test_override_and_super_do_not_warn(caplog: pytest.LogCaptureFixture) -> None:
    reset_best_effort_warnings()

    @instrument_model("rtsa", "unit-test-override")
    class _Override(GenericRtsa):
        def set_center_freq(self, frequency_hz: float) -> None:
            self._scpi.write(f"VENDOR {frequency_hz:.0f}")

    @instrument_model("rtsa", "unit-test-super")
    class _CallsSuper(GenericRtsa):
        def set_center_freq(self, frequency_hz: float) -> None:
            super().set_center_freq(frequency_hz)

    override_transport = RfStubTransport()
    super_transport = RfStubTransport()
    override = _Override(override_transport, {"model": "unit-test-override"})
    calls_super = _CallsSuper(super_transport, {"model": "unit-test-super"})
    with caplog.at_level(logging.WARNING, logger="colosseum.equipment"):
        override.set_center_freq(10.0)
        calls_super.set_center_freq(20.0)
    assert override_transport.written == ["VENDOR 10"]
    assert super_transport.written == ["FREQ:CENT 20.000000"]
    assert "using generic SCPI" not in caplog.text


def test_generic_vsg_multicarrier_stays_unsupported() -> None:
    instrument = GenericVSG(StubTransport(), {"model": "generic"})
    with pytest.raises(EquipmentCapabilityError):
        instrument.set_multicarrier(2, 1e6)


def test_esg_confirmed_sweep_stays_quiet_and_fallback_still_warns(caplog) -> None:
    reset_best_effort_warnings()
    transport = RfStubTransport({"*IDN?": "Agilent,E4438C,0,1"})
    instrument = KeysightESGVSG(transport, {"model": "keysight-esg"})
    with caplog.at_level(logging.WARNING, logger="colosseum.equipment"):
        instrument.freq_sweep(1e6, 2e6, 3, 0.1)
    assert transport.written == [
        "LIST:TYPE STEP",
        "FREQ:STAR 1000000.000000",
        "FREQ:STOP 2000000.000000",
        "SWE:POIN 3",
        "SWE:DWEL 0.100000000",
        "INIT:CONT ON",
    ]
    assert "using generic SCPI" not in caplog.text
    with caplog.at_level(logging.WARNING, logger="colosseum.equipment"):
        instrument.set_frequency(1e9)
        instrument.set_frequency(2e9)
    assert caplog.text.count("using generic SCPI") == 1


@pytest.mark.parametrize("model", [
    "keysight-n9000a", "keysight-n9010a", "keysight-n9010b",
    "keysight-n9020a", "keysight-n9020b", "keysight-n9030a", "keysight-e4440a",
    "rohde-fpc1500", "anritsu-ms2721b", "anritsu-ms2723b", "anritsu-ms2720t",
])
def test_documented_analyzer_setup_is_quiet_without_expanding_capabilities(model, caplog):
    reset_best_effort_warnings()
    transport = RfStubTransport({"INST:SEL?": "SPA"})
    with caplog.at_level(logging.WARNING, logger="colosseum.equipment"):
        analyzer = build_instrument("speca", 1, {"model": model, "center_freq": 1e9}, transport)
        analyzer.set_span(1e6)
        analyzer.set_continuous_sweep(False)
    assert transport.written == [
        "FREQ:CENT 1000000000.000000", "FREQ:SPAN 1000000.000000", "INIT:CONT 0",
    ]
    assert "using generic SCPI" not in caplog.text
    transport.written.clear()
    with pytest.raises(EquipmentCapabilityError, match="toggle_preamp"):
        analyzer.toggle_preamp(True)
    assert transport.written == []


@pytest.mark.parametrize("model", ["keysight-e8257c", "keysight-e8257d", "keysight-n5183a", "keysight-n5183b"])
def test_documented_cw_output_is_quiet_and_vector_operations_still_refuse(model, caplog):
    reset_best_effort_warnings()
    transport = RfStubTransport({"OUTP:STAT?": "0"})
    source = build_instrument("vsg", 1, {"model": model}, transport)
    with caplog.at_level(logging.WARNING, logger="colosseum.equipment"):
        source.set_output(False)
        assert source.measure_output_state() is False
    assert transport.written == ["OUTP OFF"]
    assert "using generic SCPI" not in caplog.text
    transport.written.clear()
    with pytest.raises(EquipmentCapabilityError, match="play_iq"):
        source.play_iq("wave.bin", 1e9, -10, 1e6)
    assert transport.written == []


@pytest.mark.parametrize(("model", "responses"), [
    ("rohde-hmp4040", {"INST?": "OUT2", "MEAS:VOLT?": "5"}),
    ("keysight-n6705a", {"MEAS:VOLT? (@1)": "5"}),
    ("tdk-genesys", {"MEAS:VOLT?": "5"}),
])
def test_documented_supply_host_wait_does_not_warn_or_enable_output(model, responses, caplog):
    reset_best_effort_warnings()
    transport = RfStubTransport(responses)
    supply = build_instrument("psu", 1, {"model": model}, transport)
    with caplog.at_level(logging.WARNING, logger="colosseum.equipment"):
        supply.wait_for_voltage(5, timeout_s=1)
    assert "using generic SCPI" not in caplog.text
    assert all("OUTP ON" not in command and "OUTP 1" not in command for command in transport.written)
    transport.written.clear()
    with pytest.raises(EquipmentCapabilityError, match="set_remote_sense"):
        supply.set_remote_sense(True)
    assert transport.written == []


@pytest.mark.parametrize("model", ["keysight-n5171b", "keysight-n5172b"])
def test_unverified_exg_catalog_commands_still_warn_once(model, caplog):
    reset_best_effort_warnings()
    transport = RfStubTransport()
    source = build_instrument("vsg", 1, {"model": model}, transport)
    with caplog.at_level(logging.WARNING, logger="colosseum.equipment"):
        source.set_output(False)
        source.set_output(False)
    assert transport.written == ["OUTP OFF", "OUTP OFF"]
    assert caplog.text.count("using generic SCPI") == 1
