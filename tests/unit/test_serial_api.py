"""Unit tests for col.equipment.serial API."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import colosseum_equipment.api.serial as serial_api


def test_write_delegates_to_channel(unit_runtime_context) -> None:
    channel = MagicMock()
    with patch.object(serial_api, "_channel", return_value=channel):
        serial_api.write(serial_id=1, data="PING", append_newline="\r\n")
    channel.write.assert_called_once_with("PING", append_newline="\r\n")


def test_read_applies_strip_ansi(unit_runtime_context) -> None:
    channel = MagicMock()
    channel.read_line.return_value = "\x1b[1mOK\x1b[0m"
    with patch.object(serial_api, "_channel", return_value=channel):
        value = serial_api.read(serial_id=1, key="line", strip_ansi=True)
    assert value == "OK"
