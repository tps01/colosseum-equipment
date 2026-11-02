"""Unit tests for autoconfig VISA resource sorting."""

from __future__ import annotations

from colosseum_equipment.autoconfig.sort import sort_resources


def test_tcpip_before_gpib() -> None:
    resources = [
        "GPIB0::1::INSTR",
        "TCPIP0::192.168.1.29::5025::SOCKET",
    ]
    assert sort_resources(resources) == [
        "TCPIP0::192.168.1.29::5025::SOCKET",
        "GPIB0::1::INSTR",
    ]


def test_gpib_address_ordering() -> None:
    resources = [
        "GPIB0::5::INSTR",
        "GPIB0::1::INSTR",
        "GPIB0::3::INSTR",
    ]
    assert sort_resources(resources) == [
        "GPIB0::1::INSTR",
        "GPIB0::3::INSTR",
        "GPIB0::5::INSTR",
    ]


def test_mixed_kinds_keep_global_order() -> None:
    ordered = sort_resources(
        [
            "GPIB0::2::INSTR",
            "TCPIP0::192.168.1.10::INSTR",
            "USB0::0x2A8D::0x8F01::INSTR",
            "GPIB0::1::INSTR",
        ],
    )
    assert ordered[0].startswith("TCPIP")
    assert ordered[1].startswith("USB")
    assert ordered[2:] == ["GPIB0::1::INSTR", "GPIB0::2::INSTR"]


def test_nonzero_board_indexes_keep_interface_rank() -> None:
    ordered = sort_resources(
        [
            "ASRL15::INSTR",
            "GPIB1::2::INSTR",
            "USB1::0x2A8D::0x8F01::INSTR",
            "TCPIP0::10.0.0.1::INSTR",
        ],
    )
    assert ordered[0].startswith("TCPIP")
    assert ordered[1].startswith("USB")
    assert ordered[2].startswith("GPIB")
    assert ordered[3].startswith("ASRL")


def test_pxi_ranks_after_asrl() -> None:
    ordered = sort_resources(
        [
            "PXI0::INSTR",
            "ASRL1::INSTR",
            "USB0::0x1234::0x5678::INSTR",
            "GPIB0::1::INSTR",
        ],
    )
    assert [interface_prefix(item) for item in ordered] == ["USB", "GPIB", "ASRL", "PXI"]


def test_asrl_numeric_board_order() -> None:
    assert sort_resources(["ASRL15::INSTR", "ASRL2::INSTR", "ASRL1::INSTR"]) == [
        "ASRL1::INSTR",
        "ASRL2::INSTR",
        "ASRL15::INSTR",
    ]


def test_usb_within_kind_board_vid_pid_serial_order() -> None:
    ordered = sort_resources(
        [
            "USB1::0x2A8D::0x8F01::SN-B::INSTR",
            "USB0::0x2A8D::0x8F02::SN-A::INSTR",
            "USB0::0x2A8D::0x8F01::SN-C::INSTR",
            "USB0::0x1234::0x0001::INSTR",
        ],
    )
    assert ordered == [
        "USB0::0x1234::0x0001::INSTR",
        "USB0::0x2A8D::0x8F01::SN-C::INSTR",
        "USB0::0x2A8D::0x8F02::SN-A::INSTR",
        "USB1::0x2A8D::0x8F01::SN-B::INSTR",
    ]


def test_pxi_numeric_board_order() -> None:
    assert sort_resources(["PXI10::CH1", "PXI2::CH1", "PXI1::CH1"]) == [
        "PXI1::CH1",
        "PXI2::CH1",
        "PXI10::CH1",
    ]


def interface_prefix(resource: str) -> str:
    prefix = resource.split("::", 1)[0].upper()
    return prefix.rstrip("0123456789") or prefix
