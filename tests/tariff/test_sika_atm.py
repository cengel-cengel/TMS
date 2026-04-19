"""
Tests for SikaATMChCalculator and SikaATMDeCalculator.

Validation cases from _sika_atm_findings.md (all 0.00% deviation against
KNR 527406 Abrechnungsstrecken billing records):
  IT-10 Torino,   6 kg  → 51.65 EUR  (band 1–101 kg)
  IT-10 Torino, 530 kg  → 71.90 EUR  (band 502–601 kg)
  IT-10 Torino, 735 kg  → 96.05 EUR  (band 702–801 kg)
  IT-66 Atessa,  92 kg  → 79.75 EUR  (band 1–101 kg)
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from tms.tariff.calculators.sika_atm import SikaATMChCalculator, SikaATMDeCalculator


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def ch_calc():
    return SikaATMChCalculator()


@pytest.fixture(scope="module")
def de_calc():
    return SikaATMDeCalculator()


# ── 4 validated cases (0.00% deviation) ───────────────────────────────────────

def test_it10_band0_6kg(ch_calc):
    r = ch_calc.calculate("10123", "IT", tonnage_kg=6.0)
    assert r.basispreis == Decimal("51.65")


def test_it10_band5_530kg(ch_calc):
    r = ch_calc.calculate("10123", "IT", tonnage_kg=530.0)
    assert r.basispreis == Decimal("71.90")


def test_it10_band7_735kg(ch_calc):
    r = ch_calc.calculate("10123", "IT", tonnage_kg=735.0)
    assert r.basispreis == Decimal("96.05")


def test_it66_band0_92kg(ch_calc):
    r = ch_calc.calculate("66100", "IT", tonnage_kg=92.0)
    assert r.basispreis == Decimal("79.75")


# ── Same rates for De calculator (shared DLV) ────────────────────────────────

def test_de_calc_same_rates(de_calc):
    r = de_calc.calculate("10123", "IT", tonnage_kg=6.0)
    assert r.basispreis == Decimal("51.65")


# ── Tarifgruppe tracking ───────────────────────────────────────────────────────

def test_tarifgruppe_ch(ch_calc):
    r = ch_calc.calculate("10123", "IT", tonnage_kg=100.0)
    assert r.tarifgruppe == "sika_atm_ch"
    assert r.tariff_file_used != ""
    assert r.tariff_year_used == 2024


def test_tarifgruppe_de(de_calc):
    r = de_calc.calculate("10123", "IT", tonnage_kg=100.0)
    assert r.tarifgruppe == "sika_atm_de"
    assert r.tariff_year_used == 2024


# ── Zone lookup ───────────────────────────────────────────────────────────────

def test_zone_in_notes(ch_calc):
    r = ch_calc.calculate("10123", "IT", tonnage_kg=100.0)
    assert any("IT-10" in n for n in r.notes)


def test_gb_zone(ch_calc):
    r = ch_calc.calculate("LU5 2AE", "GB", tonnage_kg=200.0)
    assert any("GB-LU" in n for n in r.notes)
    assert r.basispreis > Decimal("0")


def test_es_zone(ch_calc):
    r = ch_calc.calculate("28001", "ES", tonnage_kg=300.0)
    assert any("ES-28" in n for n in r.notes)
    assert r.basispreis > Decimal("0")


def test_rs_zone(ch_calc):
    r = ch_calc.calculate("34000", "RS", tonnage_kg=100.0)
    assert any("RS-34" in n for n in r.notes)
    assert r.basispreis > Decimal("0")


def test_pt_zone(ch_calc):
    r = ch_calc.calculate("4409-516", "PT", tonnage_kg=500.0)
    assert any("PT-44" in n for n in r.notes)
    assert r.basispreis > Decimal("0")


# ── No maut / no diesel ───────────────────────────────────────────────────────

def test_no_maut_no_diesel(ch_calc):
    r = ch_calc.calculate("10123", "IT", tonnage_kg=300.0)
    assert r.maut_surcharge is None
    assert r.diesel_surcharge is None


# ── Validity period ───────────────────────────────────────────────────────────

def test_validity_dates(ch_calc):
    from datetime import date
    r = ch_calc.calculate("10123", "IT", tonnage_kg=100.0)
    assert r.tariff_valid_from == date(2024, 7, 1)
    assert r.tariff_valid_to == date(2026, 6, 30)


# ── Error cases ───────────────────────────────────────────────────────────────

def test_ch_not_nominated(ch_calc):
    with pytest.raises(LookupError, match="not nominated"):
        ch_calc.calculate("4000", "CH", tonnage_kg=100.0)


def test_de_not_nominated(ch_calc):
    with pytest.raises(LookupError, match="not nominated"):
        ch_calc.calculate("70499", "DE", tonnage_kg=100.0)


def test_zero_tonnage_raises(ch_calc):
    with pytest.raises(ValueError):
        ch_calc.calculate("10123", "IT", tonnage_kg=0.0)


def test_unknown_country_raises(ch_calc):
    with pytest.raises(LookupError):
        ch_calc.calculate("12345", "XX", tonnage_kg=100.0)
