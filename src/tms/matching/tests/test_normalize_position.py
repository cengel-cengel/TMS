"""Unit tests for tms.normalize.normalize_position."""
import math
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[4]))  # repo/src on path

from tms.normalize.normalize_position import (
    ALL_TAXONOMY_KEYS,
    build_ax_taxonomy_row,
    build_dinas_taxonomy_row,
    decompose_dinas_sonstige,
    route_dinas_label,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _all_zero_except(d: dict, *keys: str) -> bool:
    """Return True iff all keys NOT in `keys` are 0.0."""
    for k, v in d.items():
        if k == "GESAMT":
            continue
        if k not in keys and v != 0.0:
            return False
    return True


# ---------------------------------------------------------------------------
# route_dinas_label tests
# ---------------------------------------------------------------------------

class TestRouteDinasLabel:

    def test_route_basic_maut(self):
        assert route_dinas_label("D-MAUT STANDARD") == "maut"

    def test_route_maut_variants(self):
        assert route_dinas_label("MAUT AT") == "maut"
        assert route_dinas_label("maut de 2025") == "maut"        # case-insensitive
        assert route_dinas_label("D-MAUT INLAND") == "maut"

    def test_route_gefahrgut_variants(self):
        """4 label variants from the 29-label inventory → all 'gefahrgut'."""
        labels = [
            "GEFAHRGUTZUSCHLAG 17 Gefahrgutzuschl",
            "GEFAHRGUTZUSCHLAG ADR FÄHRKOSTEN",
            "GEFAHRGUTZUSCHLAG ADR + ADR FÄHRZUSC",
            "GEFAHRGUTZUSCHLAG",
        ]
        for lbl in labels:
            assert route_dinas_label(lbl) == "gefahrgut", f"failed for {lbl!r}"

    def test_route_maut_not_in_gefahrgut_label(self):
        """GEFAHRGUTZUSCHLAG ADR FÄHRE has no MAUT → must be 'gefahrgut', not 'maut'."""
        result = route_dinas_label("GEFAHRGUTZUSCHLAG ADR FÄHRE")
        assert result == "gefahrgut"
        assert result != "maut"

    def test_route_terminzuschlag_to_sonstige(self):
        assert route_dinas_label("TERMINZUSCHLAG F. FIXSENDUNGEN") == "sonstige_nebengeb"
        assert route_dinas_label("TERMINZUSCHLAG F. FIXSENDUNGEN NEXT DAY") == "sonstige_nebengeb"

    def test_route_nebenkostenpauschale_variants(self):
        """NEBENKOSTENPAUSCHALE MAUT must NOT be 'maut' — NEBENKOSTENPAUSCHALE
        is checked first in the routing tree to prevent MAUT substring hijack."""
        assert route_dinas_label("NEBENKOSTENPAUSCHALE MAUT AT 2025") == "sonstige_nebengeb"
        assert route_dinas_label("NEBENKOSTENPAUSCHALE DK MAUT") == "sonstige_nebengeb"
        assert route_dinas_label("NEBENKOSTENPAUSCHALE") == "sonstige_nebengeb"

    def test_route_ssd_gb(self):
        assert route_dinas_label("SSD F. GB / MAUT 2025 ANDERE LÄNDER SAFETY+SECURITY") == "gb_safety_ssd"
        assert route_dinas_label("SSD F. GB / MAUT 2025 ANDERE LÄNDER") == "gb_safety_ssd"

    def test_route_avis(self):
        assert route_dinas_label("AVISGEBÜHR") == "avisgebuehr"
        assert route_dinas_label("AVISGEBÜHR TA Avis Gebühren") == "avisgebuehr"
        assert route_dinas_label("AVIS") == "avisgebuehr"

    def test_route_lademittel(self):
        assert route_dinas_label("TAUSCHGEBÜHREN/EUROPAL/GITTERPAL") == "lademittel"
        assert route_dinas_label("EUROPAL TAUSCH") == "lademittel"

    def test_route_langgutzuschlag(self):
        assert route_dinas_label("LANGGUTZUSCHLAG AB 241 CM 20%") == "langgutzuschlag"
        assert route_dinas_label("LANGGUTZUSCHLAG") == "langgutzuschlag"

    def test_route_express(self):
        assert route_dinas_label("MEHRKOSTEN F. EXPRESS-SENDUNGEN") == "sonstige_nebengeb"
        assert route_dinas_label("EXPRESS DELIVERY SURCHARGE") == "sonstige_nebengeb"

    def test_route_unknown_fallback(self):
        assert route_dinas_label("ZUS. KOSTEN/GEBÜHREN NOFR") == "sonstige_nebengeb"
        assert route_dinas_label("") == "sonstige_nebengeb"
        assert route_dinas_label("SOMETHING COMPLETELY UNKNOWN") == "sonstige_nebengeb"


# ---------------------------------------------------------------------------
# decompose_dinas_sonstige tests
# ---------------------------------------------------------------------------

class TestDecomposeDinasSonstige:

    def _check_has_all_keys(self, result: dict) -> None:
        from tms.normalize.normalize_position import _SONSTIGE_KEYS
        assert set(result.keys()) == _SONSTIGE_KEYS

    def test_decompose_nan(self):
        """None, NaN, and empty string all return all-zero dict."""
        for bad in (None, float("nan"), "", "[]", "nan", "None"):
            result = decompose_dinas_sonstige(bad)
            self._check_has_all_keys(result)
            assert all(v == 0.0 for v in result.values()), f"failed for {bad!r}"

    def test_decompose_corrupted(self):
        """Unparseable strings return all-zero dict without raising."""
        for bad in ("[{broken json", "not a list at all", "{}"):
            result = decompose_dinas_sonstige(bad)
            self._check_has_all_keys(result)
            assert all(v == 0.0 for v in result.values()), f"failed for {bad!r}"

    def test_decompose_dict_format(self):
        """Parquet-native format: list of dicts with label/amount."""
        raw = str([
            {"label": "D-MAUT STANDARD", "amount": "2.00", "currency": "EUR", "detail": None},
            {"label": "AVISGEBÜHR", "amount": "15.50", "currency": "EUR", "detail": None},
        ])
        result = decompose_dinas_sonstige(raw)
        self._check_has_all_keys(result)
        assert result["maut"] == pytest.approx(2.00)
        assert result["avisgebuehr"] == pytest.approx(15.50)
        assert result["gefahrgut"] == 0.0

    def test_decompose_tuple_format(self):
        """List-of-tuples accepted (used in synthetic test rows)."""
        items = [("GEFAHRGUTZUSCHLAG", 8.0), ("AVISGEBÜHR", 5.0)]
        result = decompose_dinas_sonstige(items)
        self._check_has_all_keys(result)
        assert result["gefahrgut"] == pytest.approx(8.0)
        assert result["avisgebuehr"] == pytest.approx(5.0)

    def test_decompose_cumulates_same_category(self):
        """Two items that map to the same category are summed."""
        items = [
            {"label": "GEFAHRGUTZUSCHLAG", "amount": "10.00"},
            {"label": "GEFAHRGUTZUSCHLAG ADR FÄHRKOSTEN", "amount": "20.00"},
        ]
        result = decompose_dinas_sonstige(items)
        assert result["gefahrgut"] == pytest.approx(30.0)

    def test_decompose_nebenkostenpauschale_maut_goes_to_sonstige(self):
        """NEBENKOSTENPAUSCHALE MAUT must land in sonstige_nebengeb, not maut."""
        items = [{"label": "NEBENKOSTENPAUSCHALE MAUT AT 2025", "amount": "16.90"}]
        result = decompose_dinas_sonstige(items)
        assert result["sonstige_nebengeb"] == pytest.approx(16.90)
        assert result["maut"] == 0.0


# ---------------------------------------------------------------------------
# build_dinas_taxonomy_row tests
# ---------------------------------------------------------------------------

class TestBuildDinasTaxonomyRow:

    def test_build_dinas_row_basic(self):
        """Synthetic row with known values checks end-to-end decomposition."""
        row = {
            "fracht": 100.0,
            "maut": 10.0,
            "diesel": 5.0,
            "sonstige": [("GEFAHRGUTZUSCHLAG", 8.0), ("AVISGEBÜHR", 5.0)],
            "sendungssumme": 128.0,
        }
        result = build_dinas_taxonomy_row(row)
        assert set(result.keys()) == set(ALL_TAXONOMY_KEYS) | {"GESAMT"}
        assert result["fracht"] == pytest.approx(100.0)
        assert result["diesel"] == pytest.approx(5.0)
        assert result["maut"] == pytest.approx(10.0)   # sonstige GEFAHRGUT adds no maut
        assert result["gefahrgut"] == pytest.approx(8.0)
        assert result["avisgebuehr"] == pytest.approx(5.0)
        assert result["transportversicherung"] == 0.0
        assert result["verzollung"] == 0.0
        assert result["GESAMT"] == pytest.approx(128.0)

    def test_build_dinas_row_maut_from_sonstige(self):
        """D-MAUT in sonstige adds to the maut column value."""
        row = {
            "fracht": 50.0,
            "maut": 3.0,
            "diesel": 0.0,
            "sonstige": [{"label": "D-MAUT STANDARD", "amount": "2.00",
                          "currency": "EUR", "detail": None}],
            "sendungssumme": 55.0,
        }
        result = build_dinas_taxonomy_row(row)
        assert result["maut"] == pytest.approx(5.0)   # 3.0 + 2.0

    def test_build_dinas_row_all_nan(self):
        """All NaN/None values produce all-zero taxonomy (no exception)."""
        row = {
            "fracht": None,
            "maut": float("nan"),
            "diesel": None,
            "sonstige": None,
            "sendungssumme": None,
        }
        result = build_dinas_taxonomy_row(row)
        for k, v in result.items():
            assert v == 0.0, f"key {k!r} should be 0.0, got {v}"


# ---------------------------------------------------------------------------
# build_ax_taxonomy_row tests
# ---------------------------------------------------------------------------

class TestBuildAxTaxonomyRow:

    def test_build_ax_row_basic(self):
        row = {
            "Erlöse Fracht": 200.0,
            "Erlöse Diesel": 12.0,
            "Erlöse Maut": 8.0,
            "Erlöse Transportversicherung": 3.0,
            "Erlöse EUST Zoll": 0.0,
            "Erlöse Lademittel": 0.0,
            "Erlöse Nebengebühr": 25.0,
            "Erlöse Peak": 0.0,
            "Erloese": 248.0,
        }
        result = build_ax_taxonomy_row(row)
        assert set(result.keys()) == set(ALL_TAXONOMY_KEYS) | {"GESAMT"}
        assert result["fracht"] == pytest.approx(200.0)
        assert result["diesel"] == pytest.approx(12.0)
        assert result["maut"] == pytest.approx(8.0)
        assert result["transportversicherung"] == pytest.approx(3.0)
        assert result["sonstige_nebengeb"] == pytest.approx(25.0)
        assert result["gefahrgut"] == 0.0
        assert result["GESAMT"] == pytest.approx(248.0)

    def test_build_ax_row_peak_added_to_sonstige(self):
        """Erlöse Peak folds into sonstige_nebengeb."""
        row = {
            "Erlöse Fracht": 100.0,
            "Erlöse Diesel": 0.0,
            "Erlöse Maut": 0.0,
            "Erlöse Transportversicherung": 0.0,
            "Erlöse EUST Zoll": 0.0,
            "Erlöse Lademittel": 0.0,
            "Erlöse Nebengebühr": 10.0,
            "Erlöse Peak": 5.0,
            "Erloese": 115.0,
        }
        result = build_ax_taxonomy_row(row)
        assert result["sonstige_nebengeb"] == pytest.approx(15.0)

    def test_build_ax_row_nan_safety(self):
        """All Erlöse columns None → all taxonomy values 0.0, no exception."""
        row = {
            "Erlöse Fracht": None,
            "Erlöse Diesel": None,
            "Erlöse Maut": None,
            "Erlöse Transportversicherung": None,
            "Erlöse EUST Zoll": None,
            "Erlöse Lademittel": None,
            "Erlöse Nebengebühr": None,
            "Erlöse Peak": None,
            "Erloese": None,
        }
        result = build_ax_taxonomy_row(row)
        for k, v in result.items():
            assert v == 0.0, f"key {k!r} should be 0.0, got {v}"

    def test_build_ax_row_missing_keys(self):
        """Missing keys (e.g. sparse row) return 0.0, not KeyError."""
        result = build_ax_taxonomy_row({})
        assert all(v == 0.0 for v in result.values())
