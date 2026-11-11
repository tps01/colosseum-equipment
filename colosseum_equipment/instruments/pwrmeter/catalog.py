"""Catalog models from the programming-manual spreadsheet.

Each class inherits the generic driver. Inherited commands are sent as
generic SCPI and log one warning per model and command. The class
docstring is the manual link.
"""

from __future__ import annotations

from colosseum_equipment.instruments.pwrmeter.generic import GenericPwrMeter
from colosseum_equipment.instruments.registry import instrument_model

# TODO: Validate keysight-e4418b inherited commands against its vendor manual and hardware.

@instrument_model("pwrmeter", "keysight-e4418b")
class KeysightE4418b(GenericPwrMeter):
    """Manual: https://www.keysight.com/us/en/assets/9018-01176/programming-guides/9018-01176.pdf"""

# TODO: Validate keysight-e4419b inherited commands against its vendor manual and hardware.

@instrument_model("pwrmeter", "keysight-e4419b")
class KeysightE4419b(GenericPwrMeter):
    """Manual: https://www.keysight.com/us/en/assets/9018-01176/programming-guides/9018-01176.pdf"""

# TODO: Validate keysight-n1913a inherited commands against its vendor manual and hardware.

@instrument_model("pwrmeter", "keysight-n1913a")
class KeysightN1913a(GenericPwrMeter):
    """Manual: https://www.keysight.com/be/en/support/N1913A/epm-series-single-channel-power-meter.html"""

# TODO: Validate keysight-n1914a inherited commands against its vendor manual and hardware.

@instrument_model("pwrmeter", "keysight-n1914a")
class KeysightN1914a(GenericPwrMeter):
    """Manual: https://www.keysight.com/be/en/support/N1913A/epm-series-single-channel-power-meter.html"""
