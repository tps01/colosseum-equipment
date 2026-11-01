"""Map instrument *IDN? responses to equipment kind and model."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class IdnMatch:
    """Classification result for a probed instrument."""

    kind: str
    model: str


@dataclass(frozen=True)
class _PatternRule:
    substring: str
    kind: str
    model: str


# Tier 1: vendor-specific patterns (most specific first).
_TIER1_RULES: tuple[_PatternRule, ...] = (
    _PatternRule("SSA3021X PLUS", "speca", "siglent-ssa3021x-plus"),
    _PatternRule("SSA3032X PLUS", "speca", "siglent-ssa3032x-plus"),
    _PatternRule("SSA3075X PLUS", "speca", "siglent-ssa3075x-plus"),
    _PatternRule("TDK-LAMBDA", "psu", "tdk-genesys"),
    _PatternRule("2260B", "psu", "keithley-2260b"),
    _PatternRule("LDA-302P-1", "attn", "vaunix-lda-302p-1"),
    _PatternRule("LDA-302P-H", "attn", "vaunix-lda-302p-h"),
    _PatternRule("SDL1020X-E", "eload", "siglent-sdl1020x-e"),
    _PatternRule("SDL1030X-E", "eload", "siglent-sdl1030x-e"),
    _PatternRule("SDS1102X-E", "oscope", "siglent-sds1102x-e"),
    _PatternRule("SDS1104X-E", "oscope", "siglent-sds1104x-e"),
    _PatternRule("SDS1202X-E", "oscope", "siglent-sds1202x-e"),
    _PatternRule("SDS1204X-E", "oscope", "siglent-sds1204x-e"),
    _PatternRule("SPD3303X-E", "psu", "siglent-spd3303x-e"),
    _PatternRule("LSW-802PDT", "rfswitch", "vaunix-lsw-802pdt"),
    _PatternRule("LSW-203PDT", "rfswitch", "vaunix-lsw-203pdt"),
    _PatternRule("SSA3032X-R", "rtsa", "siglent-ssa3032x-r"),
    _PatternRule("SSA3075X-R", "rtsa", "siglent-ssa3075x-r"),
    _PatternRule("EDU34450A", "dmm", "keysight-edu34450a"),
    _PatternRule("DSA815-TG", "speca", "rigol-dsa815-tg"),
    _PatternRule("SSA3021X+", "speca", "siglent-ssa3021x-plus"),
    _PatternRule("SSA3032X+", "speca", "siglent-ssa3032x-plus"),
    _PatternRule("SSA3075X+", "speca", "siglent-ssa3075x-plus"),
    _PatternRule("RSA5103B", "rtsa", "tektronix-rsa5100b"),
    _PatternRule("RSA5106B", "rtsa", "tektronix-rsa5100b"),
    _PatternRule("SDG1032X", "asg", "siglent-sdg1032x"),
    _PatternRule("SDG1062X", "asg", "siglent-sdg1062x"),
    _PatternRule("SDG2042X", "asg", "siglent-sdg2042x"),
    _PatternRule("SDG2082X", "asg", "siglent-sdg2082x"),
    _PatternRule("SDG2122X", "asg", "siglent-sdg2122x"),
    _PatternRule("SDG6052X", "asg", "siglent-sdg6052x"),
    _PatternRule("SDG6032X", "asg", "siglent-sdg6032x"),
    _PatternRule("SDM3045X", "dmm", "siglent-sdm3045x"),
    _PatternRule("SDM3065X", "dmm", "siglent-sdm3065x"),
    _PatternRule("SDL1020X", "eload", "siglent-sdl1020x"),
    _PatternRule("SDL1030X", "eload", "siglent-sdl1030x"),
    _PatternRule("MSO1074Z", "oscope", "rigol-mso1074z"),
    _PatternRule("MSO1104Z", "oscope", "rigol-mso1104z"),
    _PatternRule("MSO4104B", "oscope", "tektronix-mso4104b"),
    _PatternRule("MSO4054B", "oscope", "tektronix-mso4054b"),
    _PatternRule("DPO4034B", "oscope", "tektronix-dpo4034b"),
    _PatternRule("DPO4104B", "oscope", "tektronix-dpo4104b"),
    _PatternRule("MDO4104C", "oscope", "tektronix-mdo4104c"),
    _PatternRule("SPD3303X", "psu", "siglent-spd3303x"),
    _PatternRule("SPD3303C", "psu", "siglent-spd3303c"),
    _PatternRule("SPD1168X", "psu", "siglent-spd1168x"),
    _PatternRule("SPD1305X", "psu", "siglent-spd1305x"),
    _PatternRule("SSA3021X", "speca", "siglent-ssa3021x"),
    _PatternRule("SSA3032X", "speca", "siglent-ssa3032x"),
    _PatternRule("DSG3060B", "vsg", "rigol-dsg3060b"),
    _PatternRule("DSG3136B", "vsg", "rigol-dsg3136b"),
    _PatternRule("GENESYS", "psu", "tdk-genesys"),
    _PatternRule("RSA5100", "rtsa", "tektronix-rsa5100b"),
    _PatternRule("FCA3000", "freqcounter", "tektronix-fca3000"),
    _PatternRule("FCA3100", "freqcounter", "tektronix-fca3100"),
    _PatternRule("MCA3000", "freqcounter", "tektronix-mca3000"),
    _PatternRule("DG1022Z", "asg", "rigol-dg1022z"),
    _PatternRule("DG1032Z", "asg", "rigol-dg1032z"),
    _PatternRule("DG1062Z", "asg", "rigol-dg1062z"),
    _PatternRule("SDM3055", "dmm", "siglent-sdm3055"),
    _PatternRule("DMM6500", "dmm", "keithley-dmm6500"),
    _PatternRule("DMM7510", "dmm", "keithley-dmm7510"),
    _PatternRule("DL3021A", "eload", "rigol-dl3021a"),
    _PatternRule("DL3031A", "eload", "rigol-dl3031a"),
    _PatternRule("FCA3003", "freqcounter", "tektronix-fca3003"),
    _PatternRule("FCA3020", "freqcounter", "tektronix-fca3020"),
    _PatternRule("FCA3103", "freqcounter", "tektronix-fca3103"),
    _PatternRule("FCA3120", "freqcounter", "tektronix-fca3120"),
    _PatternRule("MCA3027", "freqcounter", "tektronix-mca3027"),
    _PatternRule("MCA3040", "freqcounter", "tektronix-mca3040"),
    _PatternRule("DS1054Z", "oscope", "rigol-ds1054z"),
    _PatternRule("DS1074Z", "oscope", "rigol-ds1074z"),
    _PatternRule("DS1104Z", "oscope", "rigol-ds1104z"),
    _PatternRule("DHO1074", "oscope", "rigol-dho1074"),
    _PatternRule("DHO1104", "oscope", "rigol-dho1104"),
    _PatternRule("MDO3012", "oscope", "tektronix-mdo3012"),
    _PatternRule("MDO3014", "oscope", "tektronix-mdo3014"),
    _PatternRule("MDO3022", "oscope", "tektronix-mdo3022"),
    _PatternRule("MDO3024", "oscope", "tektronix-mdo3024"),
    _PatternRule("MDO3032", "oscope", "tektronix-mdo3032"),
    _PatternRule("MDO3034", "oscope", "tektronix-mdo3034"),
    _PatternRule("MDO3052", "oscope", "tektronix-mdo3052"),
    _PatternRule("MDO3054", "oscope", "tektronix-mdo3054"),
    _PatternRule("MDO3102", "oscope", "tektronix-mdo3102"),
    _PatternRule("MDO3104", "oscope", "tektronix-mdo3104"),
    _PatternRule("DP1116A", "psu", "rigol-dp1116a"),
    _PatternRule("RSA3030", "rtsa", "rigol-rsa3030"),
    _PatternRule("RSA3045", "rtsa", "rigol-rsa3045"),
    _PatternRule("RSA3065", "rtsa", "rigol-rsa3065"),
    _PatternRule("RSA5032", "rtsa", "rigol-rsa5032"),
    _PatternRule("RSA5065", "rtsa", "rigol-rsa5065"),
    _PatternRule("RSA306B", "rtsa", "tektronix-rsa306b"),
    _PatternRule("RSA503A", "rtsa", "tektronix-rsa503a"),
    _PatternRule("RSA507A", "rtsa", "tektronix-rsa507a"),
    _PatternRule("RSA603A", "rtsa", "tektronix-rsa603a"),
    _PatternRule("RSA607A", "rtsa", "tektronix-rsa607a"),
    _PatternRule("DSG3030", "vsg", "rigol-dsg3030"),
    _PatternRule("DSG3060", "vsg", "rigol-dsg3060"),
    _PatternRule("34450A", "dmm", "keysight-edu34450a"),
    _PatternRule("E4438C", "vsg", "keysight-esg"),
    _PatternRule("E4428C", "vsg", "keysight-esg"),
    _PatternRule("E4407B", "speca", "keysight-e4407b"),
    _PatternRule("U2001A", "pwrmeter", "keysight-u2001a"),
    _PatternRule("U2000A", "pwrmeter", "keysight-u2000a"),
    _PatternRule("53220A", "freqcounter", "keysight-53220a"),
    _PatternRule("53230A", "freqcounter", "keysight-53230a"),
    _PatternRule("IT8600", "eload", "itech-it8600"),
    _PatternRule("TTR500", "vna", "tektronix-ttr500"),
    _PatternRule("ADAURA", "attn", "adaura-r3"),
    _PatternRule("R3 ATT", "attn", "adaura-r3"),
    _PatternRule("DG4062", "asg", "rigol-dg4062"),
    _PatternRule("DG4102", "asg", "rigol-dg4102"),
    _PatternRule("DG4162", "asg", "rigol-dg4162"),
    _PatternRule("DG4202", "asg", "rigol-dg4202"),
    _PatternRule("DM3058", "dmm", "rigol-dm3058"),
    _PatternRule("DM3068", "dmm", "rigol-dm3068"),
    _PatternRule("34401A", "dmm", "keysight-34401a"),
    _PatternRule("34460A", "dmm", "keysight-34460a"),
    _PatternRule("34461A", "dmm", "keysight-34461a"),
    _PatternRule("34465A", "dmm", "keysight-34465a"),
    _PatternRule("34470A", "dmm", "keysight-34470a"),
    _PatternRule("DL3021", "eload", "rigol-dl3021"),
    _PatternRule("DL3031", "eload", "rigol-dl3031"),
    _PatternRule("DHO802", "oscope", "rigol-dho802"),
    _PatternRule("DHO804", "oscope", "rigol-dho804"),
    _PatternRule("DHO914", "oscope", "rigol-dho914"),
    _PatternRule("DHO924", "oscope", "rigol-dho924"),
    _PatternRule("DP821A", "psu", "rigol-dp821a"),
    _PatternRule("DP832A", "psu", "rigol-dp832a"),
    _PatternRule("DP932U", "psu", "rigol-dp932u"),
    _PatternRule("DP932A", "psu", "rigol-dp932a"),
    _PatternRule("N6705C", "psu", "keysight-n6705c"),
    _PatternRule("E4418B", "pwrmeter", "keysight-e4418b"),
    _PatternRule("E4419B", "pwrmeter", "keysight-e4419b"),
    _PatternRule("N1913A", "pwrmeter", "keysight-n1913a"),
    _PatternRule("N1914A", "pwrmeter", "keysight-n1914a"),
    _PatternRule("U2002A", "pwrmeter", "keysight-u2002a"),
    _PatternRule("U2004A", "pwrmeter", "keysight-u2004a"),
    _PatternRule("RSA306", "rtsa", "tektronix-rsa306"),
    _PatternRule("DSA815", "speca", "rigol-dsa815"),
    _PatternRule("DSA832", "speca", "rigol-dsa832"),
    _PatternRule("DSA875", "speca", "rigol-dsa875"),
    _PatternRule("E5071C", "vna", "keysight-e5071c"),
    _PatternRule("N5166B", "vsg", "keysight-n5166b"),
    _PatternRule("N5171B", "vsg", "keysight-n5171b"),
    _PatternRule("N5172B", "vsg", "keysight-n5172b"),
    _PatternRule("N5181B", "vsg", "keysight-n5181b"),
    _PatternRule("N5182B", "vsg", "keysight-n5182b"),
    _PatternRule("U2000", "pwrmeter", "keysight-u2000"),
    _PatternRule("IT851", "eload", "itech-it8600"),
    _PatternRule("T3DSO", "oscope", "tektronix-t3dso2000"),
    _PatternRule("541XX", "vna", "anritsu-541xx"),
    _PatternRule("54110", "vna", "anritsu-541xx"),
    _PatternRule("DG811", "asg", "rigol-dg811"),
    _PatternRule("DG812", "asg", "rigol-dg812"),
    _PatternRule("DG821", "asg", "rigol-dg821"),
    _PatternRule("DG822", "asg", "rigol-dg822"),
    _PatternRule("DG952", "asg", "rigol-dg952"),
    _PatternRule("DG972", "asg", "rigol-dg972"),
    _PatternRule("DP811", "psu", "rigol-dp811"),
    _PatternRule("DP813", "psu", "rigol-dp813"),
    _PatternRule("DP821", "psu", "rigol-dp821"),
    _PatternRule("DP822", "psu", "rigol-dp822"),
    _PatternRule("DP831", "psu", "rigol-dp831"),
    _PatternRule("DP832", "psu", "rigol-dp832"),
    _PatternRule("DP711", "psu", "rigol-dp711"),
    _PatternRule("DP712", "psu", "rigol-dp712"),
    _PatternRule("8600", "eload", "chroma-8600"),
    _PatternRule("6050", "eload", "agilent-6050"),
    _PatternRule("MDO4", "oscope", "tektronix-mdo4000"),
    _PatternRule(",ZNB", "vna", "rohde-znb"),
    _PatternRule("ZNB", "vna", "rohde-znb"),
    _PatternRule("SMBV100B", "vsg", "rohde-smbv100b"),
    # FSWP before FSW — ``,FSW`` is a substring of ``,FSWP``.
    _PatternRule("FSWP", "phasenoiseanalyzer", "rohde-fswp"),
    _PatternRule(",FSW,", "speca", "rohde-fsw"),
    _PatternRule(",FSW", "speca", "rohde-fsw"),
)

# Tier 2: conservative keyword heuristics (generic model only).
_TIER2_RULES: tuple[_PatternRule, ...] = (
    _PatternRule("MULTIMETER", "dmm", "generic"),
    _PatternRule("DMM", "dmm", "generic"),
    _PatternRule("POWER SUPPLY", "psu", "generic"),
    _PatternRule("E363", "psu", "generic"),
    _PatternRule("SIGNAL GENERATOR", "vsg", "generic"),
    _PatternRule("N5182", "vsg", "generic"),
    _PatternRule("N5172", "vsg", "generic"),
    _PatternRule("SPECTRUM ANALYZER", "speca", "generic"),
    _PatternRule(",ESA", "speca", "generic"),
    _PatternRule("E440", "speca", "generic"),
    _PatternRule("REAL-TIME", "rtsa", "generic"),
    _PatternRule("RTSA", "rtsa", "generic"),
    _PatternRule("NETWORK ANALYZER", "vna", "generic"),
    _PatternRule("VNA", "vna", "generic"),
    _PatternRule("OSCILLOSCOPE", "oscope", "generic"),
    _PatternRule("DSO", "oscope", "generic"),
    _PatternRule("ELECTRONIC LOAD", "eload", "generic"),
    _PatternRule("E-LOAD", "eload", "generic"),
    _PatternRule("FREQ COUNTER", "freqcounter", "generic"),
    _PatternRule("FREQUENCY COUNTER", "freqcounter", "generic"),
    _PatternRule("POWER METER", "pwrmeter", "generic"),
    _PatternRule("ATTENUATOR", "attn", "generic"),
    _PatternRule("RF SWITCH", "rfswitch", "generic"),
    _PatternRule("ARBITRARY", "asg", "generic"),
    _PatternRule("SMU", "psu", "generic"),
)


# Inventory additions match the model field exactly, including manufacturer.
# Numeric model names must never match a serial number or another vendor.
_INVENTORY_MODELS: dict[str, tuple[str, str]] = {
    "AFG3032": ("asg", "gwinstek-afg3032"),
    "SMIQ04B": ("vsg", "rohde-smiq04b"),
    "8648C": ("vsg", "keysight-8648c"),
    "83650L": ("vsg", "keysight-83650l"),
    "MG3692C": ("vsg", "anritsu-mg3692c"),
    "TSG4106A": ("vsg", "tektronix-tsg4106a"),
    "MSO58": ("oscope", "tektronix-mso58"),
    "MSO64": ("oscope", "tektronix-mso64"),
    "TBS2204B": ("oscope", "tektronix-tbs2204b"),
    "MSO4104": ("oscope", "tektronix-mso4104"),
    "TDS7704B": ("oscope", "tektronix-tds7704b"),
    "ML2495A": ("pwrmeter", "anritsu-ml2495a"),
    "NRX": ("pwrmeter", "rohde-nrx"),
    "FPC1500": ("speca", "rohde-fpc1500"),
    "MS2721B": ("speca", "anritsu-ms2721b"),
    "MS2723B": ("speca", "anritsu-ms2723b"),
    "MS2720T": ("speca", "anritsu-ms2720t"),
    "8593E": ("speca", "keysight-8593e"),
    "8563EC": ("speca", "keysight-8563ec"),
    "PLA4K600240": ("eload", "ametek-pla4k-600-240"),
    "RSA5115B": ("rtsa", "tektronix-rsa5115b"),
    "RSA5126B": ("rtsa", "tektronix-rsa5126b"),
    "RSA6114A": ("rtsa", "tektronix-rsa6114a"),
    "33250A": ("asg", "keysight-33250a"),
    "CG635": ("asg", "srs-cg635"),
    "2001": ("dmm", "keithley-2001"),
    "2100": ("dmm", "keithley-2100"),
    "34410A": ("dmm", "keysight-34410a"),
    "34411A": ("dmm", "keysight-34411a"),
    "U1252A": ("dmm", "keysight-u1252a"),
    "U1272A": ("dmm", "keysight-u1272a"),
    "636005": ("eload", "chroma-63600-5"),
    "T3EL150303P": ("eload", "teledyne-t3el150303p"),
    "53150A": ("freqcounter", "keysight-53150a"),
    "DSA71254": ("oscope", "keysight-dsa71254"),
    "DSAZ204A": ("oscope", "keysight-dsaz204a"),
    "RTE1204": ("oscope", "rohde-rte1204"),
    "RTP164": ("oscope", "rohde-rtp164"),
    "RTB2004": ("oscope", "rohde-rtb2004"),
    "RTM3004": ("oscope", "rohde-rtm3004"),
    "TDS2014": ("oscope", "tektronix-tds2014"),
    "TDS2024C": ("oscope", "tektronix-tds2024c"),
    "TDS3032B": ("oscope", "tektronix-tds3032b"),
    "TDS3034B": ("oscope", "tektronix-tds3034b"),
    "E5052B": ("phasenoiseanalyzer", "keysight-e5052b"),
    "9115": ("psu", "bk-9115"),
    "9115AT": ("psu", "bk-9115"),
    "E3644A": ("psu", "keysight-e3644a"),
    "N6705A": ("psu", "keysight-n6705a"),
    "HMP4040": ("psu", "rohde-hmp4040"),
    "E4417A": ("pwrmeter", "keysight-e4417a"),
    "N1912A": ("pwrmeter", "keysight-n1912a"),
    "U8487A": ("pwrmeter", "keysight-u8487a"),
    "U8488A": ("pwrmeter", "keysight-u8488a"),
    "NRP18S": ("pwrmeter", "rohde-nrp18s"),
    "NRP33SN": ("pwrmeter", "rohde-nrp33sn"),
    "E4440A": ("speca", "keysight-e4440a"),
    "N9000A": ("speca", "keysight-n9000a"),
    "N9010A": ("speca", "keysight-n9010a"),
    "N9010B": ("speca", "keysight-n9010b"),
    "N9020A": ("speca", "keysight-n9020a"),
    "N9020B": ("speca", "keysight-n9020b"),
    "N9030A": ("speca", "keysight-n9030a"),
    "E5062A": ("vna", "keysight-e5062a"),
    "E5071B": ("vna", "keysight-e5071b"),
    "E8362B": ("vna", "keysight-e8362b"),
    "N5222B": ("vna", "keysight-n5222b"),
    "N5245B": ("vna", "keysight-n5245b"),
    "N5247B": ("vna", "keysight-n5247b"),
    "N9915A": ("vna", "keysight-n9915a"),
    "N9917B": ("vna", "keysight-n9917b"),
    "ZNLE6": ("vna", "rohde-znle6"),
    "E4422B": ("vsg", "keysight-e4422b"),
    "E8241A": ("vsg", "keysight-e8241a"),
    "E8257C": ("vsg", "keysight-e8257c"),
    "E8257D": ("vsg", "keysight-e8257d"),
    "N5183A": ("vsg", "keysight-n5183a"),
    "N5183B": ("vsg", "keysight-n5183b"),
    "SMA100B": ("vsg", "rohde-sma100b"),
    "SMB100A": ("vsg", "rohde-smb100a"),
}

_INVENTORY_VENDORS = {
    "keysight": ("KEYSIGHT", "AGILENT", "HEWLETTPACKARD", "HP"),
    "keithley": ("KEITHLEY",),
    "rohde": ("ROHDESCHWARZ", "RS", "HAMEG"),
    "tektronix": ("TEKTRONIX",),
    "teledyne": ("TELEDYNE", "LECROY"),
    "chroma": ("CHROMA",),
    "srs": ("STANFORDRESEARCH", "SRS"),
    "anritsu": ("ANRITSU",),
    "gwinstek": ("GWINSTEK", "GOODWILL"),
    "ametek": ("AMETEK", "SORENSEN", "AMREL"),
    "bk": ("BKPRECISION",),
}

_LAMBDA_VENDOR = re.compile(r"(?:^|[^A-Z0-9])LAMBDA(?:[^A-Z0-9]|$)")
# A digit is required so the word GENESYS is not a GEN rating.
_LAMBDA_GEN_MODEL = re.compile(
    r"(?:^|[^A-Z0-9])GENH?\d+(?:\.\d+)?-\d+(?:\.\d+)?(?:-[A-Z0-9]+)*",
)


def lambda_gen_identity(idn: str) -> bool:
    """Return whether ``idn`` is a Lambda ``GEN``/``GENH`` rating.

    Comma, space, and underscore are separators, so ``LAMBDA,GEN60-25-LAN`` and
    ``LAMBDA_GENH40-19-IEMD`` both match. The word ``GENESYS`` does not.
    """
    normalized = idn.strip().upper()
    return (
        _LAMBDA_VENDOR.search(normalized) is not None
        and _LAMBDA_GEN_MODEL.search(normalized) is not None
    )


def classify_idn(idn: str) -> IdnMatch | None:
    """Classify a raw *IDN? response into equipment kind and model."""
    normalized = idn.strip().upper()
    if not normalized:
        return None
    fields = normalized.split(",")
    if len(fields) >= 2:
        vendor = "".join(c for c in fields[0] if c.isalnum())
        token = "".join(c for c in fields[1].removeprefix("MODEL ") if c.isalnum())
        exact = _INVENTORY_MODELS.get(token)
        if exact:
            kind, model = exact
            vendors = _INVENTORY_VENDORS[model.split("-", 1)[0]]
            if vendor.startswith(vendors):
                return IdnMatch(kind=kind, model=model)
    for rule in _TIER1_RULES:
        if rule.substring.upper() in normalized:
            return IdnMatch(kind=rule.kind, model=rule.model)
    if lambda_gen_identity(normalized):
        return IdnMatch(kind="psu", model="tdk-genesys")
    for rule in _TIER2_RULES:
        if rule.substring.upper() in normalized:
            return IdnMatch(kind=rule.kind, model=rule.model)
    return None


KIND_SECTIONS: dict[str, tuple[str, str]] = {
    "psu": ("equipment.psu", "psu_id"),
    "dmm": ("equipment.dmm", "dmm_id"),
    "vsg": ("equipment.vsg", "vsg_id"),
    "asg": ("equipment.asg", "asg_id"),
    "speca": ("equipment.speca", "speca_id"),
    "rtsa": ("equipment.rtsa", "rtsa_id"),
    "attn": ("equipment.attn", "attn_id"),
    "pwrmeter": ("equipment.pwrmeter", "pwrmeter_id"),
    "rfswitch": ("equipment.rfswitch", "rfswitch_id"),
    "oscope": ("equipment.oscope", "oscope_id"),
    "eload": ("equipment.eload", "eload_id"),
    "freqcounter": ("equipment.freqcounter", "freqcounter_id"),
    "vna": ("equipment.vna", "vna_id"),
    "phasenoiseanalyzer": ("equipment.phasenoiseanalyzer", "phasenoiseanalyzer_id"),
}
