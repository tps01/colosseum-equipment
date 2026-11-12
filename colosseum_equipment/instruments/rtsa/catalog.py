"""Catalog models from the programming-manual spreadsheet.

Unverified SCPI classes retain generic warning-and-send behavior. USB RSA
models use the direct RSA API finite-acquisition adapter instead of SCPI.
"""

from __future__ import annotations

from colosseum_equipment.instruments.registry import instrument_model
from colosseum_equipment.instruments.rtsa.generic import GenericRtsa
from colosseum_equipment.instruments.rtsa.tektronix_usb import TekUsbRsa

# TODO: Validate rigol-rsa3030 inherited commands against its vendor manual and hardware.

@instrument_model("rtsa", "rigol-rsa3030")
class RigolRsa3030(GenericRtsa):
    """Manual: https://www.rigolna.com/support/downloads/"""

# TODO: Validate rigol-rsa3045 inherited commands against its vendor manual and hardware.

@instrument_model("rtsa", "rigol-rsa3045")
class RigolRsa3045(GenericRtsa):
    """Manual: https://www.rigolna.com/support/downloads/"""

# TODO: Validate rigol-rsa3065 inherited commands against its vendor manual and hardware.

@instrument_model("rtsa", "rigol-rsa3065")
class RigolRsa3065(GenericRtsa):
    """Manual: https://www.rigolna.com/support/downloads/"""

# TODO: Validate rigol-rsa5032 inherited commands against its vendor manual and hardware.

@instrument_model("rtsa", "rigol-rsa5032")
class RigolRsa5032(GenericRtsa):
    """Manual: https://www.rigolna.com/support/downloads/"""

# TODO: Validate rigol-rsa5065 inherited commands against its vendor manual and hardware.

@instrument_model("rtsa", "rigol-rsa5065")
class RigolRsa5065(GenericRtsa):
    """Manual: https://www.rigolna.com/support/downloads/"""

# TODO: Validate rigol-rsa800 inherited commands against its vendor manual and hardware.

@instrument_model("rtsa", "rigol-rsa800")
class RigolRsa800(GenericRtsa):
    """Manual: https://www.rigolna.com/support/downloads/"""

# TODO: Validate rigol-rsa6000 inherited commands against its vendor manual and hardware.

@instrument_model("rtsa", "rigol-rsa6000")
class RigolRsa6000(GenericRtsa):
    """Manual: https://www.rigolna.com/support/downloads/"""

# TODO: Validate siglent-ssa3032x-r inherited commands against its vendor manual and hardware.

@instrument_model("rtsa", "siglent-ssa3032x-r")
class SiglentSsa3032xR(GenericRtsa):
    """Manual: https://siglentna.com/resources/documents/spectrum-analyzers/"""

# TODO: Validate siglent-ssa3075x-r inherited commands against its vendor manual and hardware.

@instrument_model("rtsa", "siglent-ssa3075x-r")
class SiglentSsa3075xR(GenericRtsa):
    """Manual: https://siglentna.com/resources/documents/spectrum-analyzers/"""

# Direct RSA API finite acquisition subset; hardware qualification remains outstanding.

@instrument_model("rtsa", "tektronix-rsa306")
class TektronixRsa306(TekUsbRsa):
    """Manual: https://www.tek.com/en/spectrum-analyzer/rsa306-manual/rsa306-rsa306b-and-rsa500a-600a-0"""

# Direct RSA API; see the transport guide for runtime and serial selection.

@instrument_model("rtsa", "tektronix-rsa306b")
class TektronixRsa306b(TekUsbRsa):
    """Manual: https://www.tek.com/en/spectrum-analyzer/rsa306-manual/rsa306-rsa306b-and-rsa500a-600a-0"""

# Direct RSA API; hardware qualification remains outstanding.

@instrument_model("rtsa", "tektronix-rsa503a")
class TektronixRsa503a(TekUsbRsa):
    """Manual: https://www.tek.com/en/spectrum-analyzer/rsa306-manual/rsa306-rsa306b-and-rsa500a-600a-0"""

# Direct RSA API; hardware qualification remains outstanding.

@instrument_model("rtsa", "tektronix-rsa507a")
class TektronixRsa507a(TekUsbRsa):
    """Manual: https://www.tek.com/en/spectrum-analyzer/rsa306-manual/rsa306-rsa306b-and-rsa500a-600a-0"""

# Direct RSA API; hardware qualification remains outstanding.

@instrument_model("rtsa", "tektronix-rsa603a")
class TektronixRsa603a(TekUsbRsa):
    """Manual: https://www.tek.com/en/spectrum-analyzer/rsa306-manual/rsa306-rsa306b-and-rsa500a-600a-0"""

# Direct RSA API; hardware qualification remains outstanding.

@instrument_model("rtsa", "tektronix-rsa607a")
class TektronixRsa607a(TekUsbRsa):
    """Manual: https://www.tek.com/en/spectrum-analyzer/rsa306-manual/rsa306-rsa306b-and-rsa500a-600a-0"""
