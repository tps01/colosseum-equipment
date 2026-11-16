"""IEEE 488.2 definite-length block helpers."""

from __future__ import annotations

from pathlib import Path

import pytest
from colosseum_equipment.exceptions import EquipmentResponseError
from colosseum_equipment.protocols.scpi import (
    SCPIHelper,
    format_definite_length_block,
    parse_definite_length_block,
)

from tests.support.stubs import RfStubTransport


def test_format_definite_length_block() -> None:
    payload = b"hello"
    assert format_definite_length_block(payload) == b"#15hello"


def test_parse_definite_length_block() -> None:
    data = b"#15hello"
    assert parse_definite_length_block(data) == b"hello"


def test_read_binary_block_reassembles_split_reads() -> None:
    payload = b"0123456789abcdef"
    full = format_definite_length_block(payload)
    assert full.startswith(b"#216")
    transport = RfStubTransport(
        {
            "__raw_chunks__": [
                full[:5],
                full[5:12],
                full[12:],
            ],
        },
    )
    scpi = SCPIHelper(transport)
    assert scpi.read_binary_block("FETCH:DATA?") == payload
    assert transport.written == ["FETCH:DATA?"]


def test_read_binary_block_empty_read_raises_truncated() -> None:
    transport = RfStubTransport(
        {
            "__raw_chunks__": [b"#15ab", b"", b"", b""],
        },
    )
    scpi = SCPIHelper(transport)
    with pytest.raises(EquipmentResponseError, match="expected 5 payload bytes, got 2"):
        scpi.read_binary_block("DATA?")


@pytest.mark.parametrize(
    "seed",
    sorted((Path(__file__).parents[1] / "fixtures/fuzz/corpus").iterdir()),
    ids=lambda path: path.name,
)
def test_fuzz_seed_invariants(seed) -> None:
    from tests.fuzz.scpi_binary import check_input

    check_input(seed.read_bytes())


@pytest.mark.parametrize("target", ["ubx_stream", "mask_validation"])
def test_additional_fuzz_seed_invariants(target) -> None:
    from importlib import import_module

    check = import_module(f"tests.fuzz.{target}").check_input
    for seed in (Path(__file__).parents[1] / "fixtures/fuzz" / target).iterdir():
        check(seed.read_bytes())


@pytest.mark.parametrize('failure', ['none', 'transfer', 'write'])
def test_transfer_settings_restore_exact_state_on_success_or_partial_failure(failure):
    from colosseum_equipment.protocols.scpi import SCPIHelper

    class StatefulTransport:
        def __init__(self):
            self.settings = {'FORM': 'REAL,64', 'SOURCE': 'CH2'}
            self.events = []

        def query(self, command):
            return self.settings[command[:-1]]

        def write(self, command):
            self.events.append(command)
            key, value = command.split(' ', 1)
            self.settings[key] = value
            if failure == 'write' and command == 'SOURCE CH1':
                raise OSError('write failed after changing setting')

    transport = StatefulTransport()
    scpi = SCPIHelper(transport)
    expected = {'FORM': 'REAL,64', 'SOURCE': 'CH2'}
    try:
        with scpi.temporary_settings(('FORM', 'ASC'), ('SOURCE', 'CH1')):
            assert transport.settings == {'FORM': 'ASC', 'SOURCE': 'CH1'}
            if failure == 'transfer':
                raise OSError('malformed data or artifact write failed')
    except OSError:
        assert failure != 'none'
    else:
        assert failure == 'none'
    assert transport.settings == expected
    assert transport.events[-2:] == ['SOURCE CH2', 'FORM REAL,64']


def test_transfer_snapshot_failure_changes_nothing():
    from colosseum_equipment.exceptions import EquipmentCapabilityError
    from colosseum_equipment.protocols.scpi import SCPIHelper
    from unittest.mock import Mock

    transport = Mock()
    transport.query.side_effect = ['REAL,64', OSError('unsupported source query')]
    with pytest.raises(EquipmentCapabilityError, match='snapshot'):
        with SCPIHelper(transport).temporary_settings(('FORM', 'ASC'), ('SOURCE', 'CH1')):
            pytest.fail('transfer ran without a restorable snapshot')
    transport.write.assert_not_called()


def test_restore_failure_is_reported_and_other_settings_still_restore():
    from colosseum_equipment.exceptions import EquipmentResponseError
    from colosseum_equipment.protocols.scpi import SCPIHelper
    from unittest.mock import Mock

    transport = Mock()
    transport.query.side_effect = ['REAL,64', 'CH2']

    def write(command):
        if command == 'SOURCE CH2':
            raise OSError('disconnected during restoration')

    transport.write.side_effect = write
    with pytest.raises(EquipmentResponseError, match='restore'):
        with SCPIHelper(transport).temporary_settings(('FORM', 'ASC'), ('SOURCE', 'CH1')):
            pass
    assert transport.write.call_args.args == ('FORM REAL,64',)


def test_transfer_restores_scope_settings_when_responses_include_headers():
    from colosseum_equipment.protocols.scpi import SCPIHelper
    from unittest.mock import Mock, call

    transport = Mock()
    transport.query.side_effect = [':HEADER 1', ':DATA:SOURCE CH2']
    with SCPIHelper(transport).temporary_settings(('HEADER', 'OFF'), ('DATA:SOU', 'CH1')):
        pass
    assert transport.write.call_args_list == [
        call('HEADER OFF'), call('DATA:SOU CH1'), call('DATA:SOU CH2'), call('HEADER 1'),
    ]


def test_numeric_read_does_not_mistake_channel_in_echoed_header_for_value():
    from colosseum_equipment.protocols.scpi import SCPIHelper
    from unittest.mock import Mock

    transport = Mock()
    transport.query.return_value = ':CH1:SCALE 2.5'
    assert SCPIHelper(transport).query_float('CH1:SCAle?') == 2.5
