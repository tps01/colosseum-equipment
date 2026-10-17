from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import colosseum as col
import pytest
from colosseum.config import ConfigError, load_config
from colosseum_equipment.connections import close_all
from colosseum_equipment.io.exceptions import IoConfigError

if TYPE_CHECKING:
    from colosseum.context import RuntimeContext


def test_io_write_pin_without_config_records_command_error(io_runtime_context: RuntimeContext) -> None:
    ctx = io_runtime_context
    with pytest.raises(ConfigError, match="Configuration is not loaded"):
        col.io.dio.write_pin(dio_id=1, line=0, value=True)
    row = ctx.db.fetch_table_rows("commands")[-1]
    assert row["status"] == "ERROR"
    assert ctx.result_aggregator.overall_pass() is False


def test_io_write_pin_without_resource_records_command_error(
    io_runtime_context: RuntimeContext,
    io_bench,
) -> None:
    ctx = io_runtime_context
    load_config(
        io_bench(
            """
            [[io.dio]]
            dio_id = 1
            """,
        ),
    )
    with pytest.raises(IoConfigError, match="requires resource="):
        col.io.dio.write_pin(dio_id=1, line=0, value=True)
    row = ctx.db.fetch_table_rows("commands")[-1]
    assert row["status"] == "ERROR"
    assert "requires resource=" in (row["message"] or "")


def test_io_dio_sim_read_write_port(io_runtime_context: RuntimeContext, io_bench) -> None:
    load_config(
        io_bench(
            """
            [[io.dio]]
            dio_id = 1
            driver = sim
            port_lines = 8
            direction = 0xFF
            """,
        ),
    )
    col.io.dio.write_port(dio_id=1, value=0b1010)
    assert col.io.dio.read_port(dio_id=1, key="port_a") == 0b1010
    col.io.dio.write_pin(dio_id=1, line=0, value=True)
    assert col.io.dio.read_pin(dio_id=1, line=0, key="line0") is True


def test_io_dio_sim_measurement_domain_equipment(io_runtime_context: RuntimeContext, io_bench) -> None:
    ctx = io_runtime_context
    load_config(
        io_bench(
            """
            [[io.dio]]
            dio_id = 1
            driver = sim
            port_lines = 8
            direction = 0xFF
            """,
        ),
    )
    col.io.dio.write_port(dio_id=1, value=3)
    col.io.dio.read_port(dio_id=1, key="p1")
    rows = ctx.db.list_measurements(domain="equipment", command="io.dio.read_port", key="p1")
    assert len(rows) == 1
    assert rows[0].value == 3


def test_io_connections_close_all(io_runtime_context: RuntimeContext, io_bench) -> None:
    ctx = io_runtime_context
    load_config(
        io_bench(
            """
            [[io.dio]]
            dio_id = 1
            driver = sim
            port_lines = 8
            direction = 0xFF
            """,
        ),
    )
    col.io.dio.write_port(dio_id=1, value=1)
    assert "io:backend:dio:1" in ctx.resource_cache
    close_all()
    assert "io:backend:dio:1" not in ctx.resource_cache


def test_io_dio_scpi_fallback_write_read(
    io_runtime_context: RuntimeContext,
    io_bench,
    monkeypatch,
) -> None:
    from tests.support.stubs import RfStubTransport

    _ = io_runtime_context
    transport = RfStubTransport({"SENS:DIG:DATA?": "10"})
    monkeypatch.setattr(
        "colosseum_equipment.io.backends.scpi.dio.open_transport",
        lambda *_args, **_kwargs: transport,
    )
    load_config(
        io_bench(
            """
            [[io.dio]]
            dio_id = 1
            resource = "TCPIP0::127.0.0.1::inst0::INSTR"
            direction = 255
            """,
        ),
    )
    col.io.dio.write_port(dio_id=1, value=0b1010)
    assert col.io.dio.read_port(dio_id=1, key="scpi_port") == 10
    assert "DIG:DIR 255" in transport.written
    assert "SOUR:DIG:DATA 10" in transport.written


def test_dio_generic_driver_opens_scpi_and_warns_once(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from colosseum_equipment.io.backends import factory as dio_factory
    from colosseum_equipment.io.backends.scpi.dio import ScpiDioBackend

    from tests.support.stubs import StubTransport

    dio_factory._alias_warned.clear()
    monkeypatch.setattr(
        "colosseum_equipment.io.backends.scpi.dio.open_transport",
        lambda *_args, **_kwargs: StubTransport(),
    )
    config = {"driver": "generic", "resource": "GPIB::1::INSTR"}
    with caplog.at_level(logging.WARNING, logger="colosseum.io"):
        first = dio_factory.open_dio_backend(1, config)
        second = dio_factory.open_dio_backend(1, config)
    assert isinstance(first, ScpiDioBackend)
    assert isinstance(second, ScpiDioBackend)
    assert caplog.text.count("prefer driver") == 1


def test_dio_canonical_drivers_do_not_warn(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    unit_runtime_context,
) -> None:
    _ = unit_runtime_context
    from colosseum_equipment.io.backends import factory as dio_factory
    from colosseum_equipment.io.backends.ftdi import dio as ftdi_dio

    from tests.support.stubs import StubTransport

    class _FakeFtdi:
        def __init__(self, **_kwargs: object) -> None:
            pass

    monkeypatch.setattr(ftdi_dio, "FtdiFt232hDioBackend", _FakeFtdi)
    monkeypatch.setattr(
        "colosseum_equipment.io.backends.scpi.dio.open_transport",
        lambda *_args, **_kwargs: StubTransport(),
    )
    with caplog.at_level(logging.WARNING, logger="colosseum.io"):
        assert dio_factory.open_dio_backend(1, {"driver": "sim"}).__class__.__name__ == "SimDioBackend"
        dio_factory.open_dio_backend(2, {"driver": "ftdi-ft232h", "resource": "ftdi://0"})
        dio_factory.open_dio_backend(3, {"driver": "scpi", "resource": "GPIB::2::INSTR"})
    assert "prefer driver" not in caplog.text


def test_dio_unknown_driver_raises() -> None:
    from colosseum_equipment.io.backends.factory import open_dio_backend

    with pytest.raises(IoConfigError, match="unsupported driver"):
        open_dio_backend(1, {"driver": "nope"})
