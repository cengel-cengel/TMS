"""Tests for tms.clustering.ax_cluster.build_ax_clusters.

Unit tests use minimal synthetic DataFrames so they run without the real files.
The integration test loads the actual Sika.xlsx + Tagesbericht.
"""
from __future__ import annotations

import math
import os
from pathlib import Path

import pandas as pd
import pytest

from tms.clustering.ax_cluster import build_ax_clusters

# ---------------------------------------------------------------------------
# Synthetic helpers
# ---------------------------------------------------------------------------

def _ax_row(abr_strecke, auftragsnr, zgi, knr="ARA1802357",
            betrag=0.0, abr_gew=None, ldatum="2025-09-29",
            von_ort="Stuttgart", nach_ort="Dublin"):
    return {
        "Abrechnungsstrecke": abr_strecke,
        "Auftragsnummer":     auftragsnr,
        "Zusammengefasst in": zgi,
        "Kontonummer":        knr,
        "Betrag":             betrag,
        "Abrechnungsgewicht": abr_gew,
        "Abrechnungsstellplätze": None,
        "Abrechnungslademeter": None,
        "Leistungsdatum":     pd.Timestamp(ldatum),
        "Von Ort":            von_ort,
        "Nach Ort":           nach_ort,
    }


def _tb_row(auftragsnr, tonnage, stp=1.0, ldm=0.4, vol=1.0,
            sender_plz="70499", empf_plz="28065"):
    return {
        "Auftragsnummer": str(auftragsnr),
        "Leistungsdatum": pd.Timestamp("2025-09-29"),
        "Tonnage (eff.)": tonnage,
        "Stellplätze":    stp,
        "Lademeter":      ldm,
        "Volumen":        vol,
        "Versender PLZ":  sender_plz,
        "Empfänger PLZ":  empf_plz,
    }


# ---------------------------------------------------------------------------
# Unit test: cluster 4484 analogue (3 rows, tonnage sums to master billing)
# ---------------------------------------------------------------------------

class TestCluster4484Analogue:
    """3-member cluster: 1 master + 2 subs, tonnage matches billing weight."""

    @pytest.fixture
    def ax_df(self):
        return pd.DataFrame([
            _ax_row(4484, 7092010000673005, 4484, knr="511241",
                    betrag=4977.43, abr_gew=58733.0),
            _ax_row(4485, 7092010000674002, 4484, knr="511241",
                    betrag=0.0, abr_gew=None),
            _ax_row(4486, 7092010000706000, 4484, knr="511241",
                    betrag=0.0, abr_gew=None),
        ])

    @pytest.fixture
    def tb_df(self):
        return pd.DataFrame([
            _tb_row(7092010000673005, tonnage=19040.0, stp=33.0,
                    sender_plz="28065", empf_plz="70499"),
            _tb_row(7092010000674002, tonnage=19464.0, stp=33.0,
                    sender_plz="28065", empf_plz="70499"),
            _tb_row(7092010000706000, tonnage=20229.0, stp=33.0,
                    sender_plz="28065", empf_plz="70499"),
        ])

    def test_single_cluster_returned(self, ax_df, tb_df):
        result = build_ax_clusters(ax_df, tb_df, excluded_knrs=set())
        assert len(result) == 1

    def test_cluster_id(self, ax_df, tb_df):
        result = build_ax_clusters(ax_df, tb_df, excluded_knrs=set())
        assert result.iloc[0]["cluster_id"] == 4484

    def test_n_subs(self, ax_df, tb_df):
        result = build_ax_clusters(ax_df, tb_df, excluded_knrs=set())
        assert result.iloc[0]["n_subs"] == 2

    def test_master_billing_kg(self, ax_df, tb_df):
        result = build_ax_clusters(ax_df, tb_df, excluded_knrs=set())
        assert result.iloc[0]["master_billing_kg"] == 58733.0

    def test_aggregat_gewicht_matches_billing(self, ax_df, tb_df):
        result = build_ax_clusters(ax_df, tb_df, excluded_knrs=set())
        row = result.iloc[0]
        # 19040 + 19464 + 20229 = 58733
        assert row["aggregat_gewicht_kg"] == pytest.approx(58733.0, abs=1.0)

    def test_consistency_check_true(self, ax_df, tb_df):
        result = build_ax_clusters(ax_df, tb_df, excluded_knrs=set())
        assert result.iloc[0]["consistency_check"] == True  # noqa: E712

    def test_tb_coverage_full(self, ax_df, tb_df):
        result = build_ax_clusters(ax_df, tb_df, excluded_knrs=set())
        assert result.iloc[0]["tb_coverage_subs"] == pytest.approx(1.0)

    def test_tb_gap_reason_none(self, ax_df, tb_df):
        result = build_ax_clusters(ax_df, tb_df, excluded_knrs=set())
        assert result.iloc[0]["tb_gap_reason"] is None

    def test_aggregat_stp(self, ax_df, tb_df):
        result = build_ax_clusters(ax_df, tb_df, excluded_knrs=set())
        # All 3 members (master + 2 subs): 33 + 33 + 33 = 99
        assert result.iloc[0]["aggregat_stp"] == pytest.approx(99.0)

    def test_sender_plz_distinct(self, ax_df, tb_df):
        result = build_ax_clusters(ax_df, tb_df, excluded_knrs=set())
        assert result.iloc[0]["sender_plz_distinct"] == ["28"]

    def test_empfaenger_plz_distinct(self, ax_df, tb_df):
        result = build_ax_clusters(ax_df, tb_df, excluded_knrs=set())
        assert result.iloc[0]["empfaenger_plz_distinct"] == ["70"]

    def test_master_fracht_eur(self, ax_df, tb_df):
        result = build_ax_clusters(ax_df, tb_df, excluded_knrs=set())
        assert result.iloc[0]["master_fracht_eur"] == pytest.approx(4977.43)


# ---------------------------------------------------------------------------
# Unit test: cluster with TB gap (April 2026 sub beyond TB cutoff)
# ---------------------------------------------------------------------------

class TestClusterWithTbGap:
    """1 sub is in April 2026 (beyond TB cutoff), 1 sub matches."""

    @pytest.fixture
    def ax_df(self):
        return pd.DataFrame([
            _ax_row(9001, 7092010099001000, 9001, knr="ARA_Sika_DE+CH",
                    betrag=500.0, abr_gew=600.0, ldatum="2026-04-07"),
            _ax_row(9002, 7092010099002000, 9001, knr="ARA_Sika_DE+CH",
                    betrag=0.0, abr_gew=None, ldatum="2026-03-15"),
            _ax_row(9003, 7092010099003000, 9001, knr="ARA_Sika_DE+CH",
                    betrag=0.0, abr_gew=None, ldatum="2026-04-07"),
        ])

    @pytest.fixture
    def tb_df(self):
        # Only sub 9002 exists in TB; sub 9003 (April 2026) is absent
        return pd.DataFrame([
            _tb_row(7092010099002000, tonnage=300.0, stp=2.0),
        ])

    def test_tb_coverage_partial(self, ax_df, tb_df):
        result = build_ax_clusters(ax_df, tb_df, excluded_knrs=set())
        row = result.iloc[0]
        assert row["tb_coverage_subs"] == pytest.approx(0.5)

    def test_tb_gap_reason_april(self, ax_df, tb_df):
        result = build_ax_clusters(ax_df, tb_df, excluded_knrs=set())
        assert result.iloc[0]["tb_gap_reason"] == "april_2026_beyond_tb"

    def test_coverage_below_1(self, ax_df, tb_df):
        result = build_ax_clusters(ax_df, tb_df, excluded_knrs=set())
        assert result.iloc[0]["tb_coverage_subs"] < 1.0


# ---------------------------------------------------------------------------
# Unit test: excluded KNR rows are dropped
# ---------------------------------------------------------------------------

def test_excluded_knr_413276_not_in_output():
    ax_df = pd.DataFrame([
        _ax_row(100, 7090000000100001, 100, knr="413276", betrag=0.0, abr_gew=50.0),
        _ax_row(101, 7090000000101000, 100, knr="413276", betrag=0.0),
    ])
    tb_df = pd.DataFrame([_tb_row(7090000000101000, tonnage=50.0)])
    result = build_ax_clusters(ax_df, tb_df)  # default excludes 413276
    assert len(result) == 0


# ---------------------------------------------------------------------------
# Unit test: standalone row is not in output
# ---------------------------------------------------------------------------

def test_standalone_not_in_output():
    ax_df = pd.DataFrame([
        _ax_row(200, 7090000000200001, None, knr="491063", betrag=100.0, abr_gew=200.0),
    ])
    tb_df = pd.DataFrame([_tb_row(7090000000200001, tonnage=200.0)])
    result = build_ax_clusters(ax_df, tb_df, excluded_knrs=set())
    assert len(result) == 0


# ---------------------------------------------------------------------------
# Unit test: consistency_check=False when tonnage deviates by >1 kg
# ---------------------------------------------------------------------------

def test_consistency_check_false_on_deviation():
    ax_df = pd.DataFrame([
        _ax_row(300, 7090000000300001, 300, knr="511241",
                betrag=200.0, abr_gew=500.0),
        _ax_row(301, 7090000000301000, 300, knr="511241",
                betrag=0.0, abr_gew=None),
    ])
    # master has no TB row, sub has 100 kg → total = 100, billing = 500 → FAIL
    tb_df = pd.DataFrame([_tb_row(7090000000301000, tonnage=100.0)])
    result = build_ax_clusters(ax_df, tb_df, excluded_knrs=set())
    assert result.iloc[0]["consistency_check"] == False  # noqa: E712


# ---------------------------------------------------------------------------
# Integration test: real files
# ---------------------------------------------------------------------------

_SIKA_PATH = Path(__file__).parents[4] / "data/extracted/abrechnungsstrecken/Abrechnungsstrecken/Sika.xlsx"
_TB_PATH   = Path(__file__).parents[4] / "data/bi_report/Tagesbericht.Einzeldaten.alle.VKA.5.xlsx"

@pytest.mark.skipif(
    not (_SIKA_PATH.exists() and _TB_PATH.exists()),
    reason="Real data files not present",
)
class TestIntegration:
    @pytest.fixture(scope="class")
    def clusters(self):
        ax = pd.read_excel(_SIKA_PATH)
        tb = pd.read_excel(_TB_PATH)
        return build_ax_clusters(ax, tb)

    def test_cluster_count(self, clusters):
        # Expected: 517 total clusters; with KNR 413276 excluded some are dropped
        # Accept range 450–517
        assert 450 <= len(clusters) <= 520, f"Got {len(clusters)} clusters"

    def test_no_413276_in_output(self, clusters):
        assert (clusters["master_knr"] == "413276").sum() == 0

    def test_aggregated_tb_coverage(self, clusters):
        # Within TB date range, sub coverage should be ≥95%
        tb_window = clusters[clusters["leistungsdatum"] <= pd.Timestamp("2026-03-31")]
        if len(tb_window) == 0:
            pytest.skip("no clusters in TB window")
        total_subs   = (tb_window["n_subs"]).sum()
        matched_subs = (tb_window["n_subs"] * tb_window["tb_coverage_subs"]).sum()
        coverage_pct = matched_subs / total_subs * 100
        assert coverage_pct >= 95.0, f"TB coverage = {coverage_pct:.1f}%"

    def test_cluster_4484_present(self, clusters):
        assert 4484 in clusters["cluster_id"].values

    def test_cluster_4484_values(self, clusters):
        row = clusters[clusters["cluster_id"] == 4484].iloc[0]
        assert row["n_subs"] == 2
        assert row["master_billing_kg"] == pytest.approx(58733.0, abs=1.0)
        assert row["aggregat_gewicht_kg"] == pytest.approx(58733.0, abs=1.0)
        assert row["consistency_check"] == True  # noqa: E712
        assert row["tb_coverage_subs"] == pytest.approx(1.0)

    def test_all_required_columns_present(self, clusters):
        required = {
            "cluster_id", "master_auftragsnr", "master_knr",
            "master_billing_kg", "master_fracht_eur", "n_subs",
            "aggregat_gewicht_kg", "aggregat_stp", "aggregat_ldm",
            "aggregat_volumen", "sender_plz_distinct", "empfaenger_plz_distinct",
            "leistungsdatum", "tb_coverage_subs", "tb_gap_reason",
            "consistency_check",
        }
        assert required.issubset(set(clusters.columns))

    def test_n_subs_all_positive(self, clusters):
        assert (clusters["n_subs"] >= 1).all()
