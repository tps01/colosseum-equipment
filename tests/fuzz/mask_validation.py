"""JSON mask validation, normalization stability, and input preservation."""

from __future__ import annotations

import json
import sys


def check_input(data: bytes) -> None:
    from colosseum_equipment.tools.mask_schema import MaskSchemaError, validate_mask

    try:
        value = json.loads(data)
    except (ValueError, UnicodeError, RecursionError):
        return
    before = json.dumps(value, sort_keys=True)
    try:
        result = validate_mask(value)
    except MaskSchemaError:
        pass
    else:
        assert isinstance(result, dict)
        assert json.dumps(validate_mask(result), sort_keys=True) == json.dumps(result, sort_keys=True)
        for region in result["regions"]:
            assert not region["x0"] > region["x1"]
            assert not region["y0"] > region["y1"]
    assert json.dumps(value, sort_keys=True) == before


def main() -> None:
    import atheris

    with atheris.instrument_imports():
        import colosseum_equipment.tools.mask_schema  # noqa: F401
    atheris.Setup(sys.argv, atheris.instrument_func(check_input))
    atheris.Fuzz()


if __name__ == "__main__":
    main()
