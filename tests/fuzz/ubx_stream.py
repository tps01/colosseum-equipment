"""UBX stream fragmentation, recovery, and payload decoding invariants."""

from __future__ import annotations

import sys


def check_input(data: bytes) -> None:
    from colosseum_equipment.instruments.gnss import ubx

    def feed(stream: bytes, width: int) -> list[tuple[str, object]]:
        parser = ubx.UbxStreamParser()
        events = []
        for offset in range(0, len(stream), width):
            events.extend(parser.feed(stream[offset : offset + width]))
        return events

    width = 1 + (data[0] % 32 if data else 0)
    events = feed(data, max(1, len(data)))
    assert feed(data, width) == events
    payload = data[:4096]
    frame = ubx.build_ubx(1, 7, payload)
    expected = [("ubx", (1, 7, payload))]
    assert feed(frame, width) == expected
    corrupt = frame[:-1] + bytes([frame[-1] ^ 1])
    assert feed(corrupt + frame, width) == expected
    assert feed(corrupt + frame, len(corrupt + frame)) == expected
    assert feed(b"\xb5x" + frame, width) == expected

    # All payload decoders must safely handle short and arbitrary byte strings.
    for decoder in (
        ubx.parse_nav_pvt,
        ubx.parse_nav_dop,
        ubx.parse_nav_posecef,
        ubx.parse_nav_status,
        ubx.parse_nav_timegps,
        ubx.parse_nav_clock,
        ubx.parse_nav_sat,
        ubx.parse_rxm_rawx,
        ubx.parse_rxm_measx,
    ):
        decoder(payload)
    nav = ubx.parse_nav_pvt(payload)
    if nav is not None:
        assert isinstance(ubx.nav_pvt_fields(nav), dict)
    dop = ubx.parse_nav_dop(payload)
    if dop is not None:
        assert isinstance(ubx.nav_dop_fields(dop), dict)


def main() -> None:
    import atheris

    with atheris.instrument_imports():
        import colosseum_equipment.instruments.gnss.ubx  # noqa: F401
    atheris.Setup(sys.argv, atheris.instrument_func(check_input))
    atheris.Fuzz()


if __name__ == "__main__":
    main()
