"""Linux USBTMC character-device helpers."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from colosseum_equipment.transports.usbtmc import (
    UsbtmcTransport,
    list_usbtmc_devices,
    usbtmc_device_path,
)


def test_usbtmc_device_path_accepts_raw_and_asrl_forms() -> None:
    assert usbtmc_device_path("/dev/usbtmc0") == "/dev/usbtmc0"
    assert usbtmc_device_path("ASRL/dev/usbtmc2::INSTR") == "/dev/usbtmc2"
    assert usbtmc_device_path("GPIB0::1::INSTR") is None
    assert usbtmc_device_path("/dev/ttyUSB0") is None


def test_list_usbtmc_devices_returns_empty_without_dev(monkeypatch) -> None:
    class _MissingDev:
        def is_dir(self) -> bool:
            return False

        def glob(self, _pattern: str):  # noqa: ANN202
            return []

    monkeypatch.setattr(
        "colosseum_equipment.transports.usbtmc.Path",
        lambda *_args, **_kwargs: _MissingDev(),
    )
    assert list_usbtmc_devices() == []


def test_usbtmc_transport_query_roundtrip() -> None:
    reads = [b"BK PRECISION,9115,1,1\n"]

    def _read(_fd: int, _size: int) -> bytes:
        return reads.pop(0)

    with (
        patch("colosseum_equipment.transports.usbtmc.os.open", return_value=7),
        patch("colosseum_equipment.transports.usbtmc.os.write") as write,
        patch("colosseum_equipment.transports.usbtmc.os.read", side_effect=_read),
        patch("colosseum_equipment.transports.usbtmc.select.select", return_value=([7], [], [])),
        patch("colosseum_equipment.transports.usbtmc.os.close") as close,
    ):
        transport = UsbtmcTransport("/dev/usbtmc0", timeout=1.0)
        assert transport.query("*IDN?") == "BK PRECISION,9115,1,1"
        transport.close()
    write.assert_called_once_with(7, b"*IDN?\n")
    close.assert_called_once_with(7)


def test_usbtmc_transport_rejects_non_usbtmc_path() -> None:
    with pytest.raises(Exception, match="not a USBTMC"):
        UsbtmcTransport("/dev/ttyUSB0")
