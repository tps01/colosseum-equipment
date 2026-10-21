"""Unit tests for autoconfig *IDN? classification."""

from __future__ import annotations

from colosseum_equipment.autoconfig.idn_registry import classify_idn


def test_tier1_vendor_models() -> None:
    match = classify_idn("Keysight Technologies,EDU34450A,MY123,1.0.0")
    assert match is not None
    assert match.kind == "dmm"
    assert match.model == "keysight-edu34450a"

    match = classify_idn("TDK-Lambda,GENESYS-28-80,1,1.2")
    assert match is not None
    assert match.kind == "psu"
    assert match.model == "tdk-genesys"

    match = classify_idn("Agilent Technologies,E4438C,US0001,1.0")
    assert match is not None
    assert match.kind == "vsg"
    assert match.model == "keysight-esg"


def test_tier2_generic_heuristics() -> None:
    match = classify_idn("ACME,DMM-1000,1,1")
    assert match is not None
    assert match.kind == "dmm"
    assert match.model == "generic"


def test_unknown_idn_returns_none() -> None:
    assert classify_idn("UNKNOWN,WIDGET,1,1") is None
    assert classify_idn("") is None
    assert classify_idn("ACME,GEN30-50,1,1") is None


def test_lambda_gen_family_maps_to_genesys_scpi() -> None:
    identities = (
        "LAMBDA,GEN60-25-LAN,S/N:26M5470,REV:1U:4.0-AP17",
        "LAMBDA,GENH12.5-60-LAN,1,1",
        "LAMBDA_GEN30-50",
        "LAMBDA_GEN30-80",
        "LAMBDA_GEN40-38-IEEE",
        "LAMBDA_GENH40-19-IEMD",
        "LAMBDA, GEN30-50",
    )
    for identity in identities:
        match = classify_idn(identity)
        assert match is not None, identity
        assert (match.kind, match.model) == ("psu", "tdk-genesys")


def test_rohde_idn_fswp_before_fsw() -> None:
    fswp = classify_idn("Rohde&Schwarz,FSWP,100123,1.0")
    assert fswp is not None
    assert fswp.kind == "phasenoiseanalyzer"
    assert fswp.model == "rohde-fswp"
    fsw = classify_idn("Rohde&Schwarz,FSW-26,200123,1.0")
    assert fsw is not None
    assert fsw.kind == "speca"
    assert fsw.model == "rohde-fsw"
    smbv = classify_idn("Rohde&Schwarz,SMBV100B,300123,1.0")
    assert smbv is not None
    assert smbv.kind == "vsg"
    assert smbv.model == "rohde-smbv100b"


def test_catalog_idn_prefers_the_longer_model_token() -> None:
    dp832a = classify_idn("RIGOL TECHNOLOGIES,DP832A,DP8A0001,00.01.01")
    assert dp832a is not None
    assert dp832a.model == "rigol-dp832a"
    dp832 = classify_idn("RIGOL TECHNOLOGIES,DP832,DP800001,00.01.01")
    assert dp832 is not None
    assert dp832.model == "rigol-dp832"
    plus = classify_idn("Siglent Technologies,SSA3021X Plus,1,1")
    assert plus is not None
    assert plus.model == "siglent-ssa3021x-plus"
    plain = classify_idn("Siglent Technologies,SSA3021X,1,1")
    assert plain is not None
    assert plain.model == "siglent-ssa3021x"
    scope = classify_idn("TEKTRONIX,MDO3024,C0001,1.0")
    assert scope is not None
    assert scope.kind == "oscope"
    assert scope.model == "tektronix-mdo3024"


def test_classify_tek_rsa5115b() -> None:
    match = classify_idn("TEKTRONIX,RSA5115B,B010100,1.0.0")
    assert match is not None
    assert match.kind == "rtsa"
    assert match.model == "tektronix-rsa5115b"
    family = classify_idn("TEKTRONIX,RSA5103B,B010100,1.0.0")
    assert family is not None
    assert family.model == "tektronix-rsa5100b"


def test_inventory_exact_models_resolve_to_registered_builders() -> None:
    from colosseum_equipment.autoconfig.idn_registry import _INVENTORY_MODELS
    from colosseum_equipment.instruments.registry import registered_models
    manufacturers = {
        "anritsu": "ANRITSU", "gwinstek": "GW INSTEK", "ametek": "AMETEK",
        "keysight": "Agilent Technologies", "rohde": "Rohde&Schwarz",
        "keithley": "KEITHLEY INSTRUMENTS INC.", "tektronix": "TEKTRONIX",
        "chroma": "CHROMA", "srs": "Stanford Research Systems", "teledyne": "Teledyne LeCroy",
    }
    for token, (kind, model) in _INVENTORY_MODELS.items():
        vendor = manufacturers[model.split("-", 1)[0]]
        # Keithley uses MODEL prefixes; model identifiers cannot match serial numbers.
        field = f"MODEL {token}" if model.startswith("keithley-") else token
        match = classify_idn(f"{vendor},{field},123,1.0")
        assert match is not None, model
        assert (match.kind, match.model) == (kind, model)
        assert model in registered_models(kind)
        unknown = classify_idn(f"{vendor},UNKNOWN,{token},1.0")
        assert unknown is None or unknown.model != model
        unrelated = classify_idn(f"UNRELATED,{token},123,1.0")
        assert unrelated is None or unrelated.model != model


def test_inventory_suffixes_do_not_match_different_hardware() -> None:
    assert classify_idn("Keysight,N9010B-OTHER,1,1") is None
    assert classify_idn("Keysight,N5245B-UNKNOWN,1,1") is None
