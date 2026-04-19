"""Unit tests for cluster_matcher.py — Etappe 8."""
from __future__ import annotations

import datetime
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from tms.matching.cluster_matcher import (
    _apply_cq_grauzone_filter,
    _hamming1,
    _normalize_ax_knr,
    _plz2,
    _safe_float,
    _tarifgruppe_for_knr,
)


# ---------------------------------------------------------------------------
# _plz2
# ---------------------------------------------------------------------------

def test_plz2_standard():
    assert _plz2("70439") == "70"

def test_plz2_short():
    assert _plz2("7") == "7"

def test_plz2_empty():
    assert _plz2("") == ""

def test_plz2_nan_string():
    assert _plz2("nan") == ""

def test_plz2_none():
    assert _plz2(None) == ""


# ---------------------------------------------------------------------------
# _safe_float
# ---------------------------------------------------------------------------

def test_safe_float_positive():
    assert _safe_float(3.14) == pytest.approx(3.14)

def test_safe_float_zero_returns_none():
    assert _safe_float(0) is None

def test_safe_float_negative_returns_none():
    assert _safe_float(-1) is None

def test_safe_float_none():
    assert _safe_float(None) is None

def test_safe_float_string():
    assert _safe_float("2.5") == pytest.approx(2.5)


# ---------------------------------------------------------------------------
# _normalize_ax_knr
# ---------------------------------------------------------------------------

def test_normalize_ara_ch():
    assert _normalize_ax_knr("ARA_Sika_DE+CH", "CH") == "511241"

def test_normalize_ara_de():
    assert _normalize_ax_knr("ARA_Sika_DE+CH", "DE") == "491063"

def test_normalize_ara_it():
    assert _normalize_ax_knr("ARA_Sika_DE+CH", "IT") == "491063"

def test_normalize_passthrough():
    assert _normalize_ax_knr("491063", "IT") == "491063"
    assert _normalize_ax_knr("511241", "CH") == "511241"

def test_normalize_ssc_export_ie():
    """SSC Von Name on non-CH destination → 511241 (SSC), not 491063."""
    assert _normalize_ax_knr("ARA_Sika_DE+CH", "IE", "Sika Supply Center AG") == "511241"

def test_normalize_ssc_export_es():
    assert _normalize_ax_knr("ARA_Sika_DE+CH", "ES", "Sika Supply Center AG") == "511241"

def test_normalize_ssc_export_gb():
    assert _normalize_ax_knr("ARA_Sika_DE+CH", "GB", "Sika Supply Center AG") == "511241"

def test_normalize_sika_de_export_it():
    """Sika DE Von Name on non-CH destination → 491063."""
    assert _normalize_ax_knr("ARA_Sika_DE+CH", "IT", "Sika Deutschland GmbH") == "491063"

def test_normalize_sika_de_export_ie():
    assert _normalize_ax_knr("ARA_Sika_DE+CH", "IE", "Sika Deutschland GmbH") == "491063"

def test_normalize_ssc_ch_always_511241():
    """CH destination always SSC, regardless of Von Name."""
    assert _normalize_ax_knr("ARA_Sika_DE+CH", "CH", "Sika Deutschland GmbH") == "511241"

def test_normalize_supply_center_case_insensitive():
    assert _normalize_ax_knr("ARA_Sika_DE+CH", "GB", "SIKA SUPPLY CENTER AG") == "511241"


# ---------------------------------------------------------------------------
# _tarifgruppe_for_knr
# ---------------------------------------------------------------------------

def test_tarifgruppe_sika_de():
    tg = _tarifgruppe_for_knr("491063")
    assert tg == "sika_de_stellplatz"

def test_tarifgruppe_ssc():
    tg = _tarifgruppe_for_knr("511241")
    assert tg == "ssc_stellplatz"

def test_tarifgruppe_atm_ch():
    tg = _tarifgruppe_for_knr("527406")
    assert tg == "sika_atm_ch"

def test_tarifgruppe_unknown():
    assert _tarifgruppe_for_knr("999999") == "unknown"


# ---------------------------------------------------------------------------
# _hamming1
# ---------------------------------------------------------------------------

def test_hamming1_identical_returns_false():
    assert _hamming1("70", "70") is False

def test_hamming1_one_diff():
    assert _hamming1("70", "71") is True

def test_hamming1_both_diff():
    assert _hamming1("70", "81") is False

def test_hamming1_alpha_codes():
    assert _hamming1("AB", "AC") is True
    assert _hamming1("LU", "LS") is True

def test_hamming1_different_lengths():
    assert _hamming1("70", "700") is False

def test_hamming1_empty():
    assert _hamming1("", "") is False


# ---------------------------------------------------------------------------
# match_clusters PLZ tolerance pass
# ---------------------------------------------------------------------------

def _make_plz_tolerance_frames():
    """
    Dinas: KNR 491063, abs=70, empf=47 (Portugal)
    AX:    KNR 491063, abs=70, empf=48 (one char off)
    → Should be merged via plz_tolerance_1
    """
    dinas_df = pd.DataFrame({
        "rechnung_nr":    [4700001],
        "erka_kundennr":  ["25607"],   # → KNR 491063
        "rechnung_date":  [pd.Timestamp("2025-08-01")],
        "leistung_date":  [pd.Timestamp("2025-08-15")],
        "template":       ["erka_standard"],
        "abs_plz":        ["70439"],
        "empf_plz":       ["4700"],    # empf_plz_2 = "47"
        "empf_land":      ["PT"],
        "gewicht_kg":     [800.0],
        "stp":            [4.0],
        "lm":             [1.6],
        "fracht":         [400.0],
        "diesel":         [20.0],
        "maut":           [10.0],
        "sonstige":       ["[]"],
        "bordero_nr":     ["B047"],
    })
    ax_df = pd.DataFrame({
        "Auftragsnummer":       [2002200220022001, 2002200220022002],
        "Kontonummer":          ["491063", "491063"],
        "Abrechnungsstrecke":   [9002, 9003],        # master=9002, sub=9003
        "Zusammengefasst in":  [9002.0, 9002.0],    # both point to master 9002
        "Betrag":               [420.0, 0.0],
        "Abrechnungsgewicht":   [800.0, 0.0],
        "Leistungsdatum":       [pd.Timestamp("2025-11-10")] * 2,
        "Von Ort":              ["Stuttgart"] * 2,
        "Nach Ort":             ["Lisbon"] * 2,
    })
    tb_df = pd.DataFrame({
        "Auftragsnummer":   ["2002200220022001", "2002200220022002"],
        "Kundenreferenz":   ["REF1", "REF2"],
        "Rechnungsnummer":  ["0", "0"],
        "Mastersendung":    [None, None],
        "Tonnage (eff.)":   [400.0, 400.0],
        "Stellplätze":      [2.0, 2.0],
        "Lademeter":        [0.8, 0.8],
        "Volumen":          [2.0, 2.0],
        "Versender PLZ":    ["70439", "70439"],
        "Empfänger PLZ":    ["4800", "4800"],  # empf_plz_2 = "48" ← one char off
        "Empfänger Land":   ["PT", "PT"],
    })
    return dinas_df, ax_df, tb_df


def test_plz_tolerance_merges_hamming1_family():
    """PLZ tolerance pass joins Dinas empf=47 with AX empf=48 into one family."""
    from tms.matching.cluster_matcher import match_clusters

    dinas_df, ax_df, tb_df = _make_plz_tolerance_frames()
    result = match_clusters(dinas_df, ax_df, tb_df)

    # Both DINAS and AX rows should share the same family_key
    dinas_rows = result[result["cluster_source"] == "DINAS"]
    ax_rows    = result[result["cluster_source"] == "AX"]

    assert len(dinas_rows) > 0
    assert len(ax_rows) > 0
    # After tolerance merge, AX row family_key == Dinas row family_key
    assert dinas_rows["family_key"].iloc[0] == ax_rows["family_key"].iloc[0]


def test_plz_tolerance_sets_merge_reason():
    """Merged AX rows carry merge_reason='plz_tolerance_1'."""
    from tms.matching.cluster_matcher import match_clusters

    dinas_df, ax_df, tb_df = _make_plz_tolerance_frames()
    result = match_clusters(dinas_df, ax_df, tb_df)

    ax_rows = result[result["cluster_source"] == "AX"]
    assert (ax_rows["merge_reason"] == "plz_tolerance_1").all()


# ---------------------------------------------------------------------------
# _apply_cq_grauzone_filter
# ---------------------------------------------------------------------------

def _make_tb(auftr_vals, kref_vals) -> pd.DataFrame:
    return pd.DataFrame({
        "Auftragsnummer": auftr_vals,
        "Kundenreferenz": kref_vals,
    })


def test_grauzone_removes_16digit_dinas_snr():
    tb = _make_tb(
        ["1234567890123456", "12345678", "1234567890123456"],
        ["32000000", "32000000", "99999999"],
    )
    filtered = _apply_cq_grauzone_filter(tb)
    assert len(filtered) == 2  # row 0 removed (16-digit + dinas SNR)


def test_grauzone_keeps_8digit_rows():
    tb = _make_tb(["12345678", "87654321"], ["28000000", "32999999"])
    filtered = _apply_cq_grauzone_filter(tb)
    assert len(filtered) == 2  # 8-digit rows kept regardless


def test_grauzone_boundary_snr():
    tb = _make_tb(
        ["1234567890123456", "1234567890123457"],
        ["21000000", "20999999"],  # at boundary and just below
    )
    filtered = _apply_cq_grauzone_filter(tb)
    assert len(filtered) == 1  # only row 1 kept (20999999 < 21000000)


# ---------------------------------------------------------------------------
# match_clusters — smoke test with minimal synthetic DataFrames
# ---------------------------------------------------------------------------

def _minimal_dinas_df() -> pd.DataFrame:
    """3 rows, 2 invoices for ERKA 25607 (→ KNR 491063 Sika DE)."""
    return pd.DataFrame({
        "rechnung_nr": [3000001, 3000001, 3000002],
        "erka_kundennr": ["25607", "25607", "25607"],
        "rechnung_date": [pd.Timestamp("2025-08-01")] * 3,
        "leistung_date": [pd.Timestamp("2025-08-01"),
                          pd.Timestamp("2025-08-02"),
                          pd.Timestamp("2025-08-15")],
        "template": ["erka_standard"] * 3,
        "abs_plz": ["70439", "70439", "70439"],
        "empf_plz": ["EC1A", "EC1A", "EC1A"],
        "empf_land": ["GB", "GB", "GB"],
        "gewicht_kg": [500.0, 600.0, 400.0],
        "stp": [2.0, 2.0, 1.0],
        "lm": [0.8, 0.8, 0.4],
        "fracht": [300.0, 350.0, 180.0],
        "diesel": [10.0, 12.0, 8.0],
        "maut": [5.0, 6.0, 3.0],
        "sonstige": ["[]", "[]", "[]"],
        "bordero_nr": ["B001", "B001", "B002"],
    })


def _minimal_ax_df() -> pd.DataFrame:
    """Minimal Sika.xlsx structure: 1 master + 1 sub = 1 cluster."""
    return pd.DataFrame({
        "Auftragsnummer": [1001100110011001, 1001100110011002],
        "Kontonummer":    ["491063", "491063"],
        "Abrechnungsstrecke": [9001, 9001],
        "Zusammengefasst in": [9001.0, 9001.0],
        "Betrag": [650.0, 0.0],
        "Abrechnungsgewicht": [1100.0, 0.0],
        "Leistungsdatum": [pd.Timestamp("2025-11-01"), pd.Timestamp("2025-11-01")],
        "Von Ort": ["Stuttgart", "Stuttgart"],
        "Nach Ort": ["London", "London"],
    })


def _minimal_tb_df() -> pd.DataFrame:
    """TB rows matching the AX cluster members."""
    return pd.DataFrame({
        "Auftragsnummer": ["1001100110011001", "1001100110011002"],
        "Kundenreferenz": ["REF1", "REF2"],
        "Rechnungsnummer": ["0", "0"],
        "Mastersendung": [None, None],
        "Tonnage (eff.)": [600.0, 500.0],
        "Stellplätze": [2.0, 2.0],
        "Lademeter": [0.8, 0.8],
        "Volumen": [2.0, 2.0],
        "Versender PLZ": ["70439", "70439"],
        "Empfänger PLZ": ["EC1A", "EC1A"],
        "Empfänger Land": ["GB", "GB"],
    })


def test_match_clusters_smoke():
    """Smoke test: match_clusters runs without error on minimal DataFrames."""
    from tms.matching.cluster_matcher import match_clusters

    dinas_df = _minimal_dinas_df()
    ax_df    = _minimal_ax_df()
    tb_df    = _minimal_tb_df()

    result = match_clusters(dinas_df, ax_df, tb_df)

    assert isinstance(result, pd.DataFrame)
    assert len(result) > 0
    assert "family_key" in result.columns
    assert "cluster_source" in result.columns
    assert set(result["cluster_source"]).issubset({"DINAS", "AX"})


def test_match_clusters_family_key_format():
    """family_key has format knr|abs_plz2|empf_plz2|tarifgruppe."""
    from tms.matching.cluster_matcher import match_clusters

    result = match_clusters(
        _minimal_dinas_df(),
        _minimal_ax_df(),
        _minimal_tb_df(),
    )
    for fkey in result["family_key"]:
        parts = fkey.split("|")
        assert len(parts) == 4, f"Bad family_key format: {fkey}"


def test_match_clusters_output_columns():
    """All _OUT_COLS present in result."""
    from tms.matching.cluster_matcher import match_clusters, _OUT_COLS

    result = match_clusters(
        _minimal_dinas_df(),
        _minimal_ax_df(),
        _minimal_tb_df(),
    )
    for col in _OUT_COLS:
        assert col in result.columns, f"Missing column: {col}"


def test_full_era_top_n_selection():
    """
    Top-N Dinas clusters chosen by eur_pro_einheit DESC regardless of date.
    Build a family with 10 clusters spanning Oct 2024–Sep 2025.
    The highest-EUR/unit cluster is the oldest (Oct 2024).
    It must appear in selected_as='dinas_sample' even though it is far from cutoff.
    """
    import math

    dates = [pd.Timestamp(f"2024-10-{d:02d}") for d in range(1, 11)]
    # eur_pro_einheit is fracht / stp; assign descending fracht so oldest = highest
    fracts = list(range(1000, 0, -100))   # 1000, 900, ..., 100

    dinas_df = pd.DataFrame({
        "rechnung_nr":   list(range(5000001, 5000011)),  # 10 distinct invoices
        "erka_kundennr": ["25607"] * 10,
        "rechnung_date": dates,
        "leistung_date": dates,
        "template":      ["erka_standard"] * 10,
        "abs_plz":       ["70439"] * 10,
        "empf_plz":      ["EC1A"] * 10,
        "empf_land":     ["GB"] * 10,
        "gewicht_kg":    [500.0] * 10,
        "stp":           [1.0] * 10,        # 1 Stpl each → eur_pe = fracht
        "lm":            [0.4] * 10,
        "fracht":        fracts,
        "diesel":        [0.0] * 10,
        "maut":          [0.0] * 10,
        "sonstige":      ["[]"] * 10,
        "bordero_nr":    [f"B{i}" for i in range(10)],
    })

    from tms.matching.cluster_matcher import match_clusters

    # Need AX + TB too; use minimal ones from above helpers
    result = match_clusters(dinas_df, _minimal_ax_df(), _minimal_tb_df())

    dinas_rows = result[result["cluster_source"] == "DINAS"]
    selected   = dinas_rows[dinas_rows["selected_as"] == "dinas_sample"]

    assert len(selected) > 0
    # All selected clusters should have eur_pro_einheit >= min of top-5 in the full era
    top5_min = dinas_rows["eur_pro_einheit"].nlargest(5).min()
    for _, row in selected.iterrows():
        if row["eur_pro_einheit"] is not None and not (isinstance(row["eur_pro_einheit"], float) and math.isnan(row["eur_pro_einheit"])):
            assert row["eur_pro_einheit"] >= top5_min - 0.01
