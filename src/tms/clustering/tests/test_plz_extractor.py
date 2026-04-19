"""Unit tests for tms.clustering.plz_extractor."""
from __future__ import annotations

import pytest

from tms.clustering.plz_extractor import (
    extract_plz_from_nach_ort,
    normalize_empf_plz,
)


# ---------------------------------------------------------------------------
# normalize_empf_plz — non-IE countries (pass-through)
# ---------------------------------------------------------------------------

def test_normalize_de_plz():
    assert normalize_empf_plz("70499", "DE") == "70"

def test_normalize_es_plz():
    assert normalize_empf_plz("19171", "ES") == "19"

def test_normalize_gb_plz():
    assert normalize_empf_plz("IP32", "GB") == "IP"

def test_normalize_pt_plz():
    assert normalize_empf_plz("4785-13", "PT") == "47"

def test_normalize_lu_plz():
    assert normalize_empf_plz("LU5", "LU") == "LU"

def test_normalize_empty():
    assert normalize_empf_plz("", "DE") == ""

def test_normalize_nan_string():
    assert normalize_empf_plz("nan", "DE") == ""


# ---------------------------------------------------------------------------
# normalize_empf_plz — IE: Dublin Eircode normalization
# ---------------------------------------------------------------------------

def test_ie_dub_gives_du():
    """Legacy 'DUB' code → 'DU'."""
    assert normalize_empf_plz("DUB", "IE") == "DU"

def test_ie_d11_gives_du():
    """Eircode D11 (Dublin 11) → 'DU'."""
    assert normalize_empf_plz("D11", "IE") == "DU"

def test_ie_d24_gives_du():
    assert normalize_empf_plz("D24", "IE") == "DU"

def test_ie_d12_gives_du():
    assert normalize_empf_plz("D12", "IE") == "DU"

def test_ie_cor_gives_co():
    assert normalize_empf_plz("COR", "IE") == "CO"

def test_ie_lim_gives_li():
    assert normalize_empf_plz("LIM", "IE") == "LI"

def test_ie_gal_gives_ga():
    assert normalize_empf_plz("GAL", "IE") == "GA"

def test_ie_empty_gives_empty():
    assert normalize_empf_plz("", "IE") == ""

def test_ie_full_eircode_gives_2char():
    """Full Eircode "A65 B2CD" → first 2 chars 'A6'."""
    assert normalize_empf_plz("A65 B2CD", "IE") == "A6"


# ---------------------------------------------------------------------------
# extract_plz_from_nach_ort
# ---------------------------------------------------------------------------

def test_nach_ort_ie_dublin_17():
    assert extract_plz_from_nach_ort("Dublin 17", "IE") == "17"

def test_nach_ort_ie_dublin_ip():
    assert extract_plz_from_nach_ort("Dublin IP", "IE") == "IP"

def test_nach_ort_ie_dublin_ls():
    assert extract_plz_from_nach_ort("Dublin LS", "IE") == "LS"

def test_nach_ort_ie_no_match():
    # City name without embedded PLZ
    assert extract_plz_from_nach_ort("Dublin (Ballymun)", "IE") is None

def test_nach_ort_es_5digit():
    assert extract_plz_from_nach_ort("Barcelona 08021", "ES") == "08"

def test_nach_ort_es_city_only():
    # No 5-digit PLZ present
    assert extract_plz_from_nach_ort("Alcobendas", "ES") is None

def test_nach_ort_lu():
    assert extract_plz_from_nach_ort("LU-1471 Luxembourg", "LU") == "14"

def test_nach_ort_at():
    assert extract_plz_from_nach_ort("Wien 1010", "AT") == "10"

def test_nach_ort_gb():
    assert extract_plz_from_nach_ort("London EC1A 1BB", "GB") == "EC"

def test_nach_ort_gb_ls():
    assert extract_plz_from_nach_ort("Leeds LS1 2AB", "GB") == "LS"

def test_nach_ort_empty():
    assert extract_plz_from_nach_ort("", "DE") is None

def test_nach_ort_unknown_country():
    assert extract_plz_from_nach_ort("SomeCity 12345", "XX") is None


# ---------------------------------------------------------------------------
# build_ax_clusters: plz_source and master_von_name fields
# ---------------------------------------------------------------------------

import pandas as pd
from tms.clustering.ax_cluster import build_ax_clusters


def _make_ssc_ie_cluster():
    """Minimal SSC (ARA_Sika_DE+CH) cluster going to Dublin IE."""
    ax_df = pd.DataFrame([
        {
            "Abrechnungsstrecke": 15548, "Auftragsnummer": 7092010003885009,
            "Zusammengefasst in": 15548, "Kontonummer": "ARA_Sika_DE+CH",
            "Betrag": 500.0, "Abrechnungsgewicht": 5000.0,
            "Abrechnungsstellplätze": None, "Abrechnungslademeter": None,
            "Leistungsdatum": pd.Timestamp("2025-10-07"),
            "Von Ort": "Stuttgart (Weilimdorf)", "Nach Ort": "Dublin (Ballymun)",
            "Von Name": "Sika Supply Center AG", "Nach Land": "IE",
        },
        {
            "Abrechnungsstrecke": 15821, "Auftragsnummer": 7092010004743001,
            "Zusammengefasst in": 15548, "Kontonummer": "ARA_Sika_DE+CH",
            "Betrag": 0.0, "Abrechnungsgewicht": None,
            "Abrechnungsstellplätze": None, "Abrechnungslademeter": None,
            "Leistungsdatum": pd.Timestamp("2025-10-07"),
            "Von Ort": "Stuttgart (Weilimdorf)", "Nach Ort": "Dublin (Ballymun)",
            "Von Name": "Sika Supply Center AG", "Nach Land": "IE",
        },
    ])
    tb_df = pd.DataFrame([
        {
            "Auftragsnummer": "7092010004743001",
            "Leistungsdatum": pd.Timestamp("2025-10-07"),
            "Tonnage (eff.)": 2000.0, "Stellplätze": 3.0,
            "Lademeter": 1.2, "Volumen": 3.0,
            "Versender PLZ": "70499", "Empfänger PLZ": "D11",
            "Empfänger Land": "IE",
        },
    ])
    return ax_df, tb_df


def test_ssc_ie_plz_normalized_to_du():
    """Dublin TB PLZ 'D11' must normalize to 'DU' for IE destination."""
    ax_df, tb_df = _make_ssc_ie_cluster()
    result = build_ax_clusters(ax_df, tb_df, excluded_knrs=set())
    assert len(result) == 1
    assert result.iloc[0]["empfaenger_plz_distinct"] == ["DU"]


def test_ssc_ie_plz_source_is_field():
    ax_df, tb_df = _make_ssc_ie_cluster()
    result = build_ax_clusters(ax_df, tb_df, excluded_knrs=set())
    assert result.iloc[0]["plz_source"] == "field"


def test_master_von_name_captured():
    ax_df, tb_df = _make_ssc_ie_cluster()
    result = build_ax_clusters(ax_df, tb_df, excluded_knrs=set())
    assert result.iloc[0]["master_von_name"] == "Sika Supply Center AG"


def test_plz_source_missing_when_no_tb_match():
    """Cluster where all subs miss TB and Nach Ort has no parseable PLZ."""
    ax_df = pd.DataFrame([
        {
            "Abrechnungsstrecke": 9900, "Auftragsnummer": 7099990000001000,
            "Zusammengefasst in": 9900, "Kontonummer": "491063",
            "Betrag": 200.0, "Abrechnungsgewicht": 100.0,
            "Abrechnungsstellplätze": None, "Abrechnungslademeter": None,
            "Leistungsdatum": pd.Timestamp("2026-04-10"),
            "Von Ort": "Stuttgart", "Nach Ort": "Dublin (Ballymun)",
            "Von Name": "Sika Deutschland GmbH", "Nach Land": "IE",
        },
        {
            "Abrechnungsstrecke": 9901, "Auftragsnummer": 7099990000002000,
            "Zusammengefasst in": 9900, "Kontonummer": "491063",
            "Betrag": 0.0, "Abrechnungsgewicht": None,
            "Abrechnungsstellplätze": None, "Abrechnungslademeter": None,
            "Leistungsdatum": pd.Timestamp("2026-04-10"),
            "Von Ort": "Stuttgart", "Nach Ort": "Dublin (Ballymun)",
            "Von Name": "Sika Deutschland GmbH", "Nach Land": "IE",
        },
    ])
    tb_df = pd.DataFrame(columns=[
        "Auftragsnummer", "Leistungsdatum", "Tonnage (eff.)", "Stellplätze",
        "Lademeter", "Volumen", "Versender PLZ", "Empfänger PLZ", "Empfänger Land",
    ])
    result = build_ax_clusters(ax_df, tb_df, excluded_knrs=set())
    assert len(result) == 1
    assert result.iloc[0]["plz_source"] == "missing"
