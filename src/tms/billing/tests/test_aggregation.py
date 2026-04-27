"""Unit tests for v1.9/v1.9.5 AX sub-row classification and aggregation."""
from __future__ import annotations

import pandas as pd
import pytest

from tms.billing.aggregation import (
    aggregate_ax_per_cluster,
    aggregate_dinas_per_invoice,
    classify_ax_rows,
    filter_comparison_set,
    reconstruct_ax_master,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def ax_sample() -> pd.DataFrame:
    """Minimal AX DataFrame with sub, master, and standalone rows."""
    return pd.DataFrame(
        {
            "Auftragsnummer": [1001, 1002, 1003, 1004],
            "Mastersendung": [None, "1003", "1003", None],
            "Unterauftrag": [None, None, "1001,1002", None],
            "Erlöse Fracht": [150.0, 75.0, 0.0, 200.0],
            "Tonnage": [500.0, 0.0, 800.0, 300.0],
        }
    )


@pytest.fixture()
def dinas_sample() -> pd.DataFrame:
    """Dinas positions spanning two invoices with shared routing keys."""
    return pd.DataFrame(
        {
            "Rechnungsnummer": ["RN-1", "RN-1", "RN-1", "RN-2", "RN-2"],
            "Sender_PLZ": ["72072", "72072", "72072", "72072", "72072"],
            "Empfänger_PLZ": ["8790", "8790", "9140", "8790", "8790"],
            "Ladedatum": [
                "2026-01-13",
                "2026-01-13",
                "2026-01-13",
                "2026-01-13",
                "2026-01-13",
            ],
            "Gewicht_kg": [100.0, 200.0, 150.0, 120.0, 80.0],
            "Erlöse_Fracht": [317.17, 307.26, 34.64, 200.00, 180.00],
            "Erlöse_Diesel": [10.0, 12.0, 5.0, 8.0, 6.0],
            "Erlöse_Maut": [3.0, 4.0, 2.0, 2.5, 1.5],
        }
    )


# ---------------------------------------------------------------------------
# classify_ax_rows — three row types
# ---------------------------------------------------------------------------

class TestClassifyAxRows:
    def test_standalone_row(self, ax_sample):
        result = classify_ax_rows(ax_sample)
        row = result[result["Auftragsnummer"] == 1001].iloc[0]
        assert not row["has_ms"]
        assert not row["has_ua"]
        assert not row["is_sub"]
        assert not row["is_master"]
        assert row["is_standalone"]

    def test_sub_row(self, ax_sample):
        result = classify_ax_rows(ax_sample)
        row = result[result["Auftragsnummer"] == 1002].iloc[0]
        assert row["has_ms"]
        assert not row["has_ua"]
        assert row["is_sub"]
        assert not row["is_master"]
        assert not row["is_standalone"]

    def test_master_row(self, ax_sample):
        result = classify_ax_rows(ax_sample)
        row = result[result["Auftragsnummer"] == 1003].iloc[0]
        # Master has Mastersendung AND Unterauftrag set
        assert row["has_ms"]
        assert row["has_ua"]
        assert not row["is_sub"]
        assert row["is_master"]
        assert not row["is_standalone"]

    def test_second_standalone(self, ax_sample):
        result = classify_ax_rows(ax_sample)
        row = result[result["Auftragsnummer"] == 1004].iloc[0]
        assert row["is_standalone"]

    def test_classifications_are_mutually_exclusive(self, ax_sample):
        result = classify_ax_rows(ax_sample)
        overlap = result[["is_sub", "is_master", "is_standalone"]].sum(axis=1)
        assert (overlap == 1).all(), "Each row must belong to exactly one class"

    def test_nan_string_treated_as_empty(self):
        df = pd.DataFrame(
            {
                "Mastersendung": ["nan", "NaN", "", "  ", None],
                "Unterauftrag": [None, None, None, None, None],
            }
        )
        result = classify_ax_rows(df)
        assert result["has_ms"].sum() == 0
        assert result["is_standalone"].sum() == 5

    def test_does_not_modify_original(self, ax_sample):
        original_cols = set(ax_sample.columns)
        classify_ax_rows(ax_sample)
        assert set(ax_sample.columns) == original_cols


# ---------------------------------------------------------------------------
# filter_comparison_set
# ---------------------------------------------------------------------------

class TestFilterComparisonSet:
    def test_sub_rows_are_excluded(self, ax_sample):
        result = filter_comparison_set(ax_sample)
        assert 1002 not in result["Auftragsnummer"].values

    def test_master_and_standalone_are_kept(self, ax_sample):
        result = filter_comparison_set(ax_sample)
        assert set(result["Auftragsnummer"].values) == {1001, 1003, 1004}

    def test_works_without_pre_classification(self, ax_sample):
        assert "is_sub" not in ax_sample.columns
        result = filter_comparison_set(ax_sample)
        assert 1002 not in result["Auftragsnummer"].values

    def test_all_standalone_unchanged(self):
        df = pd.DataFrame(
            {
                "Auftragsnummer": [1, 2],
                "Mastersendung": [None, None],
                "Unterauftrag": [None, None],
                "Erlöse Fracht": [100.0, 200.0],
            }
        )
        result = filter_comparison_set(df)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# aggregate_dinas_per_invoice
# ---------------------------------------------------------------------------

class TestAggregateDinasPerInvoice:
    def test_same_routing_key_in_same_invoice_merged(self, dinas_sample):
        result = aggregate_dinas_per_invoice(dinas_sample)
        rn1_8790 = result[
            (result["Rechnungsnummer"] == "RN-1") & (result["Empfänger_PLZ"] == "8790")
        ]
        assert len(rn1_8790) == 1
        assert rn1_8790.iloc[0]["n_positionen"] == 2
        assert abs(rn1_8790.iloc[0]["Erlöse_Fracht"] - (317.17 + 307.26)) < 0.01

    def test_different_invoices_never_merged(self, dinas_sample):
        result = aggregate_dinas_per_invoice(dinas_sample)
        rows_8790 = result[result["Empfänger_PLZ"] == "8790"]
        # RN-1 and RN-2 both have 72072→8790 on same date — must stay separate
        assert len(rows_8790) == 2
        rn_values = set(rows_8790["Rechnungsnummer"].values)
        assert rn_values == {"RN-1", "RN-2"}

    def test_singleton_routing_key_unchanged(self, dinas_sample):
        result = aggregate_dinas_per_invoice(dinas_sample)
        rn1_9140 = result[
            (result["Rechnungsnummer"] == "RN-1") & (result["Empfänger_PLZ"] == "9140")
        ]
        assert len(rn1_9140) == 1
        assert rn1_9140.iloc[0]["n_positionen"] == 1
        assert abs(rn1_9140.iloc[0]["Gewicht_kg"] - 150.0) < 0.001

    def test_output_row_count(self, dinas_sample):
        result = aggregate_dinas_per_invoice(dinas_sample)
        # RN-1: 8790 (2→1), 9140 (1→1) = 2 rows
        # RN-2: 8790 (2→1)              = 1 row
        assert len(result) == 3

    def test_missing_agg_cols_skipped(self, dinas_sample):
        df = dinas_sample.drop(columns=["Erlöse_Diesel", "Erlöse_Maut"])
        result = aggregate_dinas_per_invoice(df)
        assert "Erlöse_Fracht" in result.columns
        assert "Erlöse_Diesel" not in result.columns

    def test_column_name_overrides(self, dinas_sample):
        df = dinas_sample.rename(
            columns={
                "Rechnungsnummer": "rn",
                "Sender_PLZ": "s_plz",
                "Empfänger_PLZ": "e_plz",
                "Ladedatum": "date",
            }
        )
        result = aggregate_dinas_per_invoice(
            df,
            rn_col="rn",
            sender_plz_col="s_plz",
            empf_plz_col="e_plz",
            date_col="date",
        )
        assert "rn" in result.columns
        assert len(result) == 3


# ---------------------------------------------------------------------------
# reconstruct_ax_master — v1.9.2 §2e Rule E
# ---------------------------------------------------------------------------

@pytest.fixture()
def master_sub_group():
    """Real-world-shaped master + 3 sub rows (physical on master, revenues on subs)."""
    master = pd.Series(
        {
            "Auftragsnummer": "7092010001835006",
            "Mastersendung": 7092010001835006.0,
            "Unterauftrag": "7091200280103007, 7091200280104004, 7091200280107005",
            "Tonnage (eff.)": 361.9,
            "Lademeter": 0.0,
            "Stellplätze": 0.0,
            "Volumen": 0.0,
            "Colli": 4.0,
            "Erlöse Fracht": 0.0,
            "Erlöse Diesel": 0.0,
            "Rechnungsnummer": "0",
        }
    )
    subs = pd.DataFrame(
        {
            "Auftragsnummer": [
                "7091200280104004",
                "7091200280107005",
                "7091200280103007",
            ],
            "Tonnage (eff.)": [0.0, 0.0, 0.0],
            "Lademeter": [0.0, 0.0, 0.0],
            "Stellplätze": [0.0, 0.0, 0.0],
            "Volumen": [0.0, 0.0, 0.0],
            "Colli": [0.0, 0.0, 0.0],
            "Erlöse Fracht": [70.1578, 9.6501, 17.4723],
            "Erlöse Diesel": [0.0, 0.0, 0.0],
            "Rechnungsnummer": ["2557006-2", "2557006-2", "2557006-2"],
        }
    )
    return master, subs


class TestReconstructAxMaster:
    def test_physical_master_leads(self, master_sub_group):
        master, subs = master_sub_group
        result = reconstruct_ax_master(master, subs)
        # Master has Tonnage=361.9; subs sum to 0 → master wins
        assert abs(result["Tonnage (eff.)"] - 361.9) < 0.001

    def test_revenue_always_from_subs(self, master_sub_group):
        master, subs = master_sub_group
        result = reconstruct_ax_master(master, subs)
        expected = 70.1578 + 9.6501 + 17.4723
        assert abs(result["Erlöse Fracht"] - expected) < 0.001

    def test_rechnungsnummern_from_subs(self, master_sub_group):
        master, subs = master_sub_group
        result = reconstruct_ax_master(master, subs)
        assert result["rechnungsnummern"] == ["2557006-2"]

    def test_master_zero_physical_is_valid(self):
        """Explicit zero on master is a valid value — not a fallback trigger."""
        master = pd.Series({"Tonnage (eff.)": 0.0, "Erlöse Fracht": 0.0, "Rechnungsnummer": "X"})
        subs = pd.DataFrame({"Tonnage (eff.)": [100.0, 200.0], "Erlöse Fracht": [50.0, 60.0], "Rechnungsnummer": ["RN-A", "RN-B"]})
        result = reconstruct_ax_master(master, subs, physical_cols=("Tonnage (eff.)",), erloes_cols=("Erlöse Fracht",))
        # Master is 0.0 (valid, non-NaN) → use master, not subs sum
        assert result["Tonnage (eff.)"] == 0.0

    def test_nan_master_falls_back_to_sub_sum(self):
        """NaN master field triggers sub-sum fallback."""
        master = pd.Series({"Tonnage (eff.)": float("nan"), "Erlöse Fracht": 0.0, "Rechnungsnummer": "X"})
        subs = pd.DataFrame({"Tonnage (eff.)": [120.0, 80.0], "Erlöse Fracht": [30.0, 40.0], "Rechnungsnummer": ["RN-1", "RN-1"]})
        result = reconstruct_ax_master(master, subs, physical_cols=("Tonnage (eff.)",), erloes_cols=("Erlöse Fracht",))
        assert abs(result["Tonnage (eff.)"] - 200.0) < 0.001

    def test_revenue_ignores_master_value(self):
        """Master Erlöse Fracht is non-zero but revenues still come from subs."""
        master = pd.Series({"Erlöse Fracht": 999.0, "Tonnage (eff.)": 100.0, "Rechnungsnummer": "X"})
        subs = pd.DataFrame({"Erlöse Fracht": [50.0, 25.0], "Tonnage (eff.)": [0.0, 0.0], "Rechnungsnummer": ["RN-1", "RN-1"]})
        result = reconstruct_ax_master(master, subs, physical_cols=("Tonnage (eff.)",), erloes_cols=("Erlöse Fracht",))
        # Revenue always from subs, even if master has a value
        assert abs(result["Erlöse Fracht"] - 75.0) < 0.001

    def test_multiple_rn_deduplicated_and_sorted(self):
        """Multiple unique invoice numbers in subs are deduplicated and sorted."""
        master = pd.Series({"Tonnage (eff.)": 100.0, "Erlöse Fracht": 0.0})
        subs = pd.DataFrame({
            "Tonnage (eff.)": [0.0, 0.0, 0.0],
            "Erlöse Fracht": [10.0, 20.0, 30.0],
            "Rechnungsnummer": ["RN-3", "RN-1", "RN-3"],
        })
        result = reconstruct_ax_master(master, subs, physical_cols=("Tonnage (eff.)",), erloes_cols=("Erlöse Fracht",))
        assert result["rechnungsnummern"] == ["RN-1", "RN-3"]

    def test_empty_subs_returns_master_physical(self):
        """Empty sub DataFrame: physical from master, revenues = 0."""
        master = pd.Series({"Tonnage (eff.)": 500.0, "Erlöse Fracht": 0.0})
        subs = pd.DataFrame(columns=["Tonnage (eff.)", "Erlöse Fracht", "Rechnungsnummer"])
        result = reconstruct_ax_master(master, subs, physical_cols=("Tonnage (eff.)",), erloes_cols=("Erlöse Fracht",))
        assert abs(result["Tonnage (eff.)"] - 500.0) < 0.001
        assert result["Erlöse Fracht"] == 0.0


# ---------------------------------------------------------------------------
# aggregate_ax_per_cluster — v1.9.5 §2f
# ---------------------------------------------------------------------------

@pytest.fixture()
def herma_abr_cluster():
    """Mini Abrechnungsstrecken with one 3-row cluster + one singleton."""
    return pd.DataFrame({
        "Abrechnungsstrecke": [380298, 380299, 380300, 380400],
        "Auftragsnummer":     [7091200055046, 7091200055033, 7091200055079, 7091200099000],
        "Zusammengefasst in": [380298.0, 380298.0, 380298.0, float("nan")],
    })


@pytest.fixture()
def herma_ax_rows():
    """AX billing rows corresponding to herma_abr_cluster."""
    return pd.DataFrame({
        "Auftragsnummer": [7091200055046, 7091200055033, 7091200055079, 7091200099000],
        "Tonnage (eff.)": [500.0, 300.0, 200.0, 800.0],
        "Lademeter":      [1.0, 0.6, 0.4, 2.0],
        "Volumen":        [2.0, 1.2, 0.8, 3.5],
        "Erlöse Fracht":  [120.0, 80.0, 60.0, 200.0],
        "Empfänger Land": ["ES", "ES", "ES", "FR"],
        "Empfänger PLZ":  ["08830", "08830", "08830", "67100"],
    })


class TestAggregateAxPerCluster:
    def test_multi_row_cluster_aggregates_physical(self, herma_abr_cluster, herma_ax_rows):
        result = aggregate_ax_per_cluster(herma_ax_rows, herma_abr_cluster)
        cluster = result[result["_n_cluster_rows"] == 3]
        assert len(cluster) == 1
        assert abs(cluster.iloc[0]["Tonnage (eff.)"] - 1000.0) < 0.001
        assert abs(cluster.iloc[0]["Lademeter"] - 2.0) < 0.001
        assert abs(cluster.iloc[0]["Erlöse Fracht"] - 260.0) < 0.001

    def test_singleton_row_unchanged(self, herma_abr_cluster, herma_ax_rows):
        result = aggregate_ax_per_cluster(herma_ax_rows, herma_abr_cluster)
        singleton = result[result["_n_cluster_rows"] == 1]
        assert len(singleton) == 1
        assert abs(singleton.iloc[0]["Erlöse Fracht"] - 200.0) < 0.001
        assert singleton.iloc[0]["_n_cluster_rows"] == 1

    def test_output_row_count(self, herma_abr_cluster, herma_ax_rows):
        # 3 rows → 1 cluster + 1 singleton = 2 output rows
        result = aggregate_ax_per_cluster(herma_ax_rows, herma_abr_cluster)
        assert len(result) == 2

    def test_auftr_nrs_list_correct(self, herma_abr_cluster, herma_ax_rows):
        result = aggregate_ax_per_cluster(herma_ax_rows, herma_abr_cluster)
        cluster = result[result["_n_cluster_rows"] == 3].iloc[0]
        auftr_strs = [str(v) for v in [7091200055046, 7091200055033, 7091200055079]]
        assert set(cluster["_auftr_nrs"]) == set(auftr_strs)

    def test_fallback_when_abr_df_none(self, herma_ax_rows):
        result = aggregate_ax_per_cluster(herma_ax_rows, None)
        assert len(result) == len(herma_ax_rows)
        assert (result["_n_cluster_rows"] == 1).all()

    def test_fallback_when_zgi_column_missing(self, herma_ax_rows):
        abr_no_zgi = pd.DataFrame({
            "Abrechnungsstrecke": [1, 2],
            "Auftragsnummer": [7091200055046, 7091200099000],
        })
        result = aggregate_ax_per_cluster(herma_ax_rows, abr_no_zgi)
        assert len(result) == len(herma_ax_rows)
        assert (result["_n_cluster_rows"] == 1).all()

    def test_does_not_modify_input(self, herma_abr_cluster, herma_ax_rows):
        original_len = len(herma_ax_rows)
        aggregate_ax_per_cluster(herma_ax_rows, herma_abr_cluster)
        assert len(herma_ax_rows) == original_len
        assert "_cluster_id" not in herma_ax_rows.columns
