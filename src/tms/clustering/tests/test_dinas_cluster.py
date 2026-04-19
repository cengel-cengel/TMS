"""Tests for tms.clustering.dinas_cluster.build_dinas_clusters."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from tms.clustering.dinas_cluster import build_dinas_clusters

# ---------------------------------------------------------------------------
# Synthetic helpers
# ---------------------------------------------------------------------------

def _row(rnr="1000001", erka="18894", template="erka_standard",
         rechnung_date="2025-09-01", leistung_date="2025-09-01",
         bordero_nr="75000001", abs_plz="70499", empf_plz="10121",
         gewicht_kg=None, stp=None, lm=None,
         fracht=None, diesel=None, maut=None, sonstige="[]"):
    return {
        "rechnung_nr":    rnr,
        "erka_kundennr":  erka,
        "template":       template,
        "rechnung_date":  rechnung_date,
        "leistung_date":  leistung_date,
        "bordero_nr":     bordero_nr,
        "abs_plz":        abs_plz,
        "empf_plz":       empf_plz,
        "gewicht_kg":     gewicht_kg,
        "stp":            stp,
        "lm":             lm,
        "fracht":         fracht,
        "diesel":         diesel,
        "maut":           maut,
        "sonstige":       sonstige,
        "sendungssumme":  None,
    }


# ---------------------------------------------------------------------------
# Unit test: 11-sendung cluster
# ---------------------------------------------------------------------------

class TestElevenSendungen:
    """One invoice with 11 sendungen; aggregat matches sum of rows."""

    @pytest.fixture
    def df(self):
        rows = [
            _row(rnr="9000001", gewicht_kg=100.0 * (i + 1), stp=2.0,
                 fracht=50.0 * (i + 1), leistung_date=f"2025-10-{i+1:02d}")
            for i in range(11)
        ]
        return pd.DataFrame(rows)

    def test_one_cluster(self, df):
        result = build_dinas_clusters(df)
        assert len(result) == 1

    def test_n_sendungen(self, df):
        result = build_dinas_clusters(df)
        assert result.iloc[0]["n_sendungen"] == 11

    def test_aggregat_gewicht(self, df):
        result = build_dinas_clusters(df)
        expected = sum(100.0 * (i + 1) for i in range(11))   # 100+200+...+1100 = 6600
        assert result.iloc[0]["aggregat_gewicht_kg"] == pytest.approx(expected)

    def test_aggregat_stp(self, df):
        result = build_dinas_clusters(df)
        assert result.iloc[0]["aggregat_stp"] == pytest.approx(22.0)

    def test_total_fracht(self, df):
        result = build_dinas_clusters(df)
        expected = sum(50.0 * (i + 1) for i in range(11))    # 50+100+...+550 = 3300
        assert result.iloc[0]["total_fracht_eur"] == pytest.approx(expected)

    def test_leistungsdatum_is_min(self, df):
        result = build_dinas_clusters(df)
        # earliest date is 2025-10-01
        assert result.iloc[0]["leistungsdatum"] == pd.Timestamp("2025-10-01")

    def test_cluster_id(self, df):
        result = build_dinas_clusters(df)
        assert result.iloc[0]["cluster_id"] == "9000001"

    def test_is_correction_false(self, df):
        result = build_dinas_clusters(df)
        assert result.iloc[0]["is_correction"] == False  # noqa: E712


# ---------------------------------------------------------------------------
# Unit test: Nebenkosten separation
# ---------------------------------------------------------------------------

class TestNebenkostenSeparation:
    """Invoice with diesel, maut, D-MAUT in sonstige, thermo, and other NK."""

    @pytest.fixture
    def df(self):
        return pd.DataFrame([
            _row(rnr="9000002", fracht=500.0, diesel=20.0, maut=15.0,
                 sonstige="[{'label': 'THERMOZUSCHLAG 37 THERMOZUSCHLAG', 'amount': '30.00', 'currency': 'EUR', 'detail': None}]"),
            _row(rnr="9000002", fracht=400.0, diesel=16.0, maut=12.0,
                 sonstige="[{'label': 'D-MAUT STANDARD', 'amount': '5.00', 'currency': 'EUR', 'detail': None}, "
                           "{'label': 'AVISGEBÜHR', 'amount': '8.50', 'currency': 'EUR', 'detail': None}]"),
            _row(rnr="9000002", fracht=300.0, diesel=12.0, maut=0.0,
                 sonstige="[{'label': 'GEFAHRGUTZUSCHLAG 17 Gefahrgutzuschl', 'amount': '50.00', 'currency': 'EUR', 'detail': None}]"),
        ])

    def test_diesel(self, df):
        r = build_dinas_clusters(df).iloc[0]
        assert r["diesel_eur"] == pytest.approx(48.0)   # 20+16+12

    def test_maut_includes_sonstige_dmaut(self, df):
        r = build_dinas_clusters(df).iloc[0]
        # maut col: 15+12+0 = 27; D-MAUT in sonstige: 5 → total 32
        assert r["maut_eur"] == pytest.approx(32.0)

    def test_thermo(self, df):
        r = build_dinas_clusters(df).iloc[0]
        assert r["thermo_eur"] == pytest.approx(30.0)

    def test_sonstige_nk(self, df):
        r = build_dinas_clusters(df).iloc[0]
        # AVISGEBÜHR 8.50 + GEFAHRGUTZUSCHLAG 50.00 = 58.50
        assert r["sonstige_nk_eur"] == pytest.approx(58.5)

    def test_total_nebenkosten(self, df):
        r = build_dinas_clusters(df).iloc[0]
        # diesel=48 + maut=32 + thermo=30 + sonstige_nk=58.5 = 168.5
        assert r["total_nebenkosten"] == pytest.approx(168.5)

    def test_total_fracht(self, df):
        r = build_dinas_clusters(df).iloc[0]
        assert r["total_fracht_eur"] == pytest.approx(1200.0)


# ---------------------------------------------------------------------------
# Unit test: is_correction flag
# ---------------------------------------------------------------------------

def test_is_correction_flag():
    df = pd.DataFrame([
        _row(rnr="9000003", template="erka_correction", fracht=None),
        _row(rnr="9000004", template="erka_standard",   fracht=100.0),
    ])
    result = build_dinas_clusters(df)
    assert len(result) == 2
    corr  = result[result["cluster_id"] == "9000003"].iloc[0]
    stand = result[result["cluster_id"] == "9000004"].iloc[0]
    assert corr["is_correction"]  == True   # noqa: E712
    assert stand["is_correction"] == False  # noqa: E712


# ---------------------------------------------------------------------------
# Unit test: bordero_nrs
# ---------------------------------------------------------------------------

def test_bordero_nrs_distinct_sorted():
    df = pd.DataFrame([
        _row(rnr="9000005", bordero_nr="75000003"),
        _row(rnr="9000005", bordero_nr="75000001"),
        _row(rnr="9000005", bordero_nr="75000001"),  # duplicate
        _row(rnr="9000005", bordero_nr="75000002"),
    ])
    result = build_dinas_clusters(df)
    assert result.iloc[0]["bordero_nrs"] == ["75000001", "75000002", "75000003"]


# ---------------------------------------------------------------------------
# Unit test: PLZ 2-digit
# ---------------------------------------------------------------------------

def test_plz_distinct_2digit():
    df = pd.DataFrame([
        _row(rnr="9000006", abs_plz="70499", empf_plz="10121"),
        _row(rnr="9000006", abs_plz="70499", empf_plz="20095"),  # same sender, diff empf
        _row(rnr="9000006", abs_plz="70499", empf_plz="10200"),  # same 2-prefix as first
    ])
    result = build_dinas_clusters(df)
    row = result.iloc[0]
    assert row["sender_plz_distinct"] == ["70"]
    assert row["empfaenger_plz_distinct"] == ["10", "20"]


# ---------------------------------------------------------------------------
# Unit test: empty input
# ---------------------------------------------------------------------------

def test_empty_input():
    df = pd.DataFrame(columns=[
        "rechnung_nr", "erka_kundennr", "template", "rechnung_date",
        "leistung_date", "bordero_nr", "abs_plz", "empf_plz",
        "gewicht_kg", "stp", "lm", "fracht", "diesel", "maut",
        "sonstige", "sendungssumme",
    ])
    result = build_dinas_clusters(df)
    assert len(result) == 0
    assert "cluster_id" in result.columns


# ---------------------------------------------------------------------------
# Integration test: real parquet
# ---------------------------------------------------------------------------

_PARQUET_PATH = Path(__file__).parents[4] / "data/parsed/dinas_pdfs.parquet"


@pytest.mark.skipif(
    not _PARQUET_PATH.exists(),
    reason="dinas_pdfs.parquet not present",
)
class TestIntegration:
    @pytest.fixture(scope="class")
    def clusters(self):
        df = pd.read_parquet(_PARQUET_PATH)
        return build_dinas_clusters(df)

    def test_cluster_count_equals_distinct_rechnung_nr(self, clusters):
        df = pd.read_parquet(_PARQUET_PATH)
        expected = df["rechnung_nr"].nunique()
        assert len(clusters) == expected   # expect 496

    def test_all_required_columns(self, clusters):
        required = {
            "cluster_id", "erka_kundennr", "rechnungsdatum", "leistungsdatum",
            "is_correction", "n_sendungen",
            "aggregat_gewicht_kg", "aggregat_stp", "aggregat_ldm", "aggregat_volumen",
            "sender_plz_distinct", "empfaenger_plz_distinct",
            "total_fracht_eur", "total_nebenkosten",
            "diesel_eur", "maut_eur", "thermo_eur", "sonstige_nk_eur",
            "bordero_nrs",
        }
        assert required.issubset(set(clusters.columns))

    def test_correction_count(self, clusters):
        # 226 erka_correction rows across some invoices
        n_corr = clusters["is_correction"].sum()
        assert 10 <= n_corr <= 30   # known: ~17 correction invoices

    def test_n_sendungen_all_positive(self, clusters):
        assert (clusters["n_sendungen"] >= 1).all()

    def test_max_sendungen(self, clusters):
        # Known: max = 157 (rechnung_nr 3773104)
        assert clusters["n_sendungen"].max() == 157

    def test_total_sendungen_sum(self, clusters):
        # Sum of n_sendungen must equal total rows in parquet
        df = pd.read_parquet(_PARQUET_PATH)
        assert clusters["n_sendungen"].sum() == len(df)

    def test_cluster_3773104_values(self, clusters):
        row = clusters[clusters["cluster_id"] == "3773104"].iloc[0]
        assert row["n_sendungen"] == 157
        assert row["erka_kundennr"] == "97505"

    def test_leistungsdatum_is_timestamp(self, clusters):
        non_nat = clusters["leistungsdatum"].dropna()
        assert len(non_nat) > 0
        assert pd.api.types.is_datetime64_any_dtype(clusters["leistungsdatum"])
