"""
Etappe 6e: Test that all 10 calculators correctly populate tarifgruppe,
tariff_file_used, and tariff_year_used on TariffResult.

These are smoke tests using minimal inputs — they verify the tracking fields
are set, not the exact rate values (covered by separate validation reports).
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from tms.tariff.base import TariffResult


# ── TariffResult defaults ─────────────────────────────────────────────────────

def test_tariff_result_new_field_defaults():
    """New Etappe 6e fields default to empty/zero/None."""
    r = TariffResult(
        basispreis=Decimal("100"),
        diesel_surcharge=None,
        maut_surcharge=None,
    )
    assert r.tarifgruppe == ""
    assert r.tariff_file_used == ""
    assert r.tariff_year_used == 0
    assert r.tariff_fallback_note is None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _assert_tracking(result: TariffResult, *, tarifgruppe_prefix: str, year: int) -> None:
    assert result.tarifgruppe.startswith(tarifgruppe_prefix), (
        f"tarifgruppe={result.tarifgruppe!r} does not start with {tarifgruppe_prefix!r}"
    )
    assert result.tariff_file_used != "", "tariff_file_used should not be empty"
    assert result.tariff_year_used == year, (
        f"tariff_year_used={result.tariff_year_used} != {year}"
    )


# ── SikaDeCalculator ──────────────────────────────────────────────────────────

def test_tarifgruppe_gesetzt_sika_de():
    from tms.tariff.calculators.sika_de import SikaDeCalculator
    calc = SikaDeCalculator()
    result = calc.calculate(
        "20155", "IT",
        stellplaetze=5,
        shipment_date=date(2025, 6, 1),
    )
    _assert_tracking(result, tarifgruppe_prefix="sika_de_stellplatz", year=2025)
    assert result.tarifgruppe == "sika_de_stellplatz"


# ── SSCCalculator ─────────────────────────────────────────────────────────────

def test_tarifgruppe_gesetzt_ssc():
    from tms.tariff.calculators.sika_de import SSCCalculator
    calc = SSCCalculator()
    result = calc.calculate(
        "20155", "IT",
        stellplaetze=5,
        shipment_date=date(2025, 6, 1),
    )
    _assert_tracking(result, tarifgruppe_prefix="ssc_stellplatz", year=2025)
    assert result.tarifgruppe == "ssc_stellplatz"


# ── GrozBeckertCalculator ─────────────────────────────────────────────────────

def test_tarifgruppe_gesetzt_groz_beckert_gc():
    from tms.tariff.calculators.groz_beckert import GrozBeckertCalculator
    calc = GrozBeckertCalculator()
    result = calc.calculate(
        "20155", "IT",
        tonnage_kg=500.0,
        origin_plz="72458",
    )
    _assert_tracking(result, tarifgruppe_prefix="groz_beckert_gc_it", year=2025)


def test_tarifgruppe_gesetzt_groz_beckert_ltl():
    from tms.tariff.calculators.groz_beckert import GrozBeckertCalculator
    calc = GrozBeckertCalculator()
    result = calc.calculate(
        "4409-516", "PT",
        tonnage_kg=800.0,
        lademeter=2.5,
        origin_plz="72458",
    )
    _assert_tracking(result, tarifgruppe_prefix="groz_beckert_lane_72458_pt", year=2025)


# ── BitzCalculator ────────────────────────────────────────────────────────────

def test_tarifgruppe_gesetzt_bitzer():
    from tms.tariff.calculators.bitzer import BitzCalculator
    calc = BitzCalculator()
    result = calc.calculate(
        "40013", "IT",
        tonnage_kg=617.6,
        origin_plz="71126",
    )
    _assert_tracking(result, tarifgruppe_prefix="bitzer_it_", year=2025)
    assert "rottenburg" in result.tarifgruppe


# ── GEZECalculator ────────────────────────────────────────────────────────────

def test_tarifgruppe_gesetzt_geze():
    from tms.tariff.calculators.geze import GEZECalculator
    calc = GEZECalculator()
    result = calc.calculate(
        "20155", "IT",
        tonnage_kg=500.0,
    )
    _assert_tracking(result, tarifgruppe_prefix="geze_it_zone", year=2025)


# ── CHTItalyCalculator ────────────────────────────────────────────────────────

def test_tarifgruppe_gesetzt_cht_main():
    from tms.tariff.calculators.cht import CHTItalyCalculator
    calc = CHTItalyCalculator()
    result = calc.calculate(
        "20155", "IT",
        tonnage_kg=500.0,
    )
    assert result.tarifgruppe == "cht_it_main"
    assert result.tariff_year_used == 2026
    assert result.tariff_file_used != ""


def test_tarifgruppe_gesetzt_cht_special():
    from tms.tariff.calculators.cht import CHTItalyCalculator
    calc = CHTItalyCalculator()
    result = calc.calculate(
        "20052", "IT",
        tonnage_kg=300.0,
    )
    assert result.tarifgruppe == "cht_it_special"
    assert result.tariff_year_used == 2026


# ── EBMCalculator ─────────────────────────────────────────────────────────────

def test_tarifgruppe_gesetzt_ebm():
    from tms.tariff.calculators.ebm import EBMCalculator
    calc = EBMCalculator()
    result = calc.calculate(
        "H91", "IE",
        lademeter=1.2,
    )
    assert result.tarifgruppe == "ebm_papst_stellplaetze"
    assert result.tariff_year_used == 2026
    assert result.tariff_file_used != ""


# ── FischerwerkeCalculator ────────────────────────────────────────────────────

def test_tarifgruppe_gesetzt_fischerwerke():
    from tms.tariff.calculators.fischerwerke import FischerwerkeCalculator
    calc = FischerwerkeCalculator()
    result = calc.calculate(
        "35127", "IT",
        stellplaetze=4,
        shipment_date=date(2025, 6, 1),
    )
    _assert_tracking(result, tarifgruppe_prefix="fischerwerke_it_", year=2025)


# ── HermaCalculator ───────────────────────────────────────────────────────────

def test_tarifgruppe_gesetzt_herma_ohne_vl():
    from tms.tariff.calculators.herma import HermaCalculator
    calc = HermaCalculator()
    result = calc.calculate(
        "20155", "IT",
        tonnage_kg=800.0,
        lademeter=0.5,
    )
    assert result.tarifgruppe in ("herma_ohne_vl", "herma_mit_vl")
    assert result.tariff_file_used != ""
    assert result.tariff_year_used > 0


def test_tarifgruppe_gesetzt_herma_mit_vl():
    from tms.tariff.calculators.herma import HermaCalculator
    calc = HermaCalculator()
    # billing_weight > 3000 → mit VL path
    result = calc.calculate(
        "20155", "IT",
        tonnage_kg=4000.0,
        lademeter=0.5,
    )
    assert result.tarifgruppe == "herma_mit_vl"


# ── HeluCalculator ────────────────────────────────────────────────────────────

def test_tarifgruppe_gesetzt_helu():
    from tms.tariff.calculators.helu import HeluCalculator
    calc = HeluCalculator()
    result = calc.calculate(
        "20155", "IT",
        tonnage_kg=500.0,
    )
    _assert_tracking(result, tarifgruppe_prefix="helu_it_zone", year=2023)


# ── HornschuchCalculator ──────────────────────────────────────────────────────

def test_tarifgruppe_gesetzt_hornschuch():
    from tms.tariff.calculators.hornschuch import HornschuchCalculator
    calc = HornschuchCalculator()
    result = calc.calculate(
        "20155", "IT",
        tonnage_kg=300.0,
    )
    _assert_tracking(result, tarifgruppe_prefix="hornschuch_it_zone", year=2024)


def test_tarifgruppe_gesetzt_hornschuch_pl():
    from tms.tariff.calculators.hornschuch import HornschuchCalculator
    calc = HornschuchCalculator()
    result = calc.calculate(
        "00-001", "PL",
        tonnage_kg=300.0,
    )
    assert result.tarifgruppe == "hornschuch_pl_na"
    assert result.tariff_file_used == "20250129_Erka_ContiTech Megatrans Deutsc.xlsx"
    assert result.tariff_year_used == 2024
