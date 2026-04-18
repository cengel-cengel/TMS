"""Unit tests for src/tms/dinas/knr_mapping.py"""
from datetime import date

import pytest

from tms.dinas.knr_mapping import (
    AX_UMSTELLUNG,
    ERKA_TO_KNR,
    NON_SIKA_ERKA,
    get_all_erka_for_dinas_knr,
    get_dinas_knr,
    get_mapping,
)


# ── get_dinas_knr — Basis ────────────────────────────────────────────────

def test_ssc_14466():
    assert get_dinas_knr("25607") == "491063"
    assert get_dinas_knr("14466") == "511241"
    assert get_dinas_knr("14464") == "511241"
    assert get_dinas_knr("14465") == "511241"
    assert get_dinas_knr("14468") == "511241"
    assert get_dinas_knr("13890") == "511241"
    assert get_dinas_knr("15550") == "511241"


def test_atm_ch():
    assert get_dinas_knr("18748") == "527406"


def test_unknown_returns_none():
    assert get_dinas_knr("99999") is None
    assert get_dinas_knr("unbekannt") is None
    assert get_dinas_knr("15607") is None   # ignoriert


# ── get_dinas_knr — Datum-Auflösung (18894 Dual-Mapping) ────────────────

def test_18894_dinas_era():
    assert get_dinas_knr("18894", date(2025, 7, 1)) == "413276"
    assert get_dinas_knr("18894", date(2024, 10, 1)) == "413276"
    assert get_dinas_knr("18894", date(2025, 9, 26)) == "413276"  # letzter Dinas-Tag


def test_18894_ax_era():
    assert get_dinas_knr("18894", date(2025, 9, 27)) == "ARA1802357"  # erster AX-Tag
    assert get_dinas_knr("18894", date(2025, 10, 15)) == "ARA1802357"
    assert get_dinas_knr("18894", date(2026, 1, 1)) == "ARA1802357"


def test_18894_no_date_returns_current():
    # Ohne Datum → aktuell gültiger (AX-Ära, kein gueltig_bis)
    assert get_dinas_knr("18894") == "ARA1802357"


def test_ax_umstellung_constant():
    assert AX_UMSTELLUNG == date(2025, 9, 27)


# ── get_all_erka_for_dinas_knr ───────────────────────────────────────────

def test_inverse_lookup_511241():
    result = get_all_erka_for_dinas_knr("511241")
    assert set(result) == {"14466", "14464", "14465", "14468", "13890", "15550"}


def test_inverse_lookup_491063():
    assert get_all_erka_for_dinas_knr("491063") == ["25607"]


def test_inverse_lookup_527406():
    assert get_all_erka_for_dinas_knr("527406") == ["18748"]


def test_inverse_lookup_413276():
    assert get_all_erka_for_dinas_knr("413276") == ["18894"]


def test_inverse_lookup_ara1802357():
    assert get_all_erka_for_dinas_knr("ARA1802357") == ["18894"]


def test_inverse_lookup_nonexistent():
    assert get_all_erka_for_dinas_knr("999999") == []


# ── get_mapping — Entitätsfelder ─────────────────────────────────────────

def test_mapping_25607_fields():
    m = get_mapping("25607")
    assert m is not None
    assert m.gesellschaft == "Sika Deutschland GmbH & Co. KG"
    assert m.land == "DE"
    assert m.ust_id == "DE326812378"
    assert m.fibu_konto == "15607"
    assert m.konfidenz == 0.99
    assert len(m.knr_history) == 1
    assert m.knr_history[0].dinas_knr == "491063"
    assert "493163" in m.knr_history[0].note  # Zahlendreher-Hinweis


def test_mapping_18748_fields():
    m = get_mapping("18748")
    assert m.gesellschaft == "Sika Automotive AG"
    assert m.land == "CH"
    assert m.ust_id == "CHE116323165"
    assert m.knr_history[0].dinas_knr == "527406"


def test_mapping_18894_dual():
    m = get_mapping("18894")
    assert len(m.knr_history) == 2
    dinas_knrs = [h.dinas_knr for h in m.knr_history]
    assert "413276" in dinas_knrs
    assert "ARA1802357" in dinas_knrs
    hist_413276 = next(h for h in m.knr_history if h.dinas_knr == "413276")
    assert hist_413276.gueltig_bis == date(2025, 9, 26)


def test_mapping_none_for_unknown():
    assert get_mapping("99999") is None
    assert get_mapping("15607") is None


# ── NON_SIKA_ERKA ─────────────────────────────────────────────────────────

def test_non_sika_documented():
    assert "15607" in NON_SIKA_ERKA
    assert "97501" in NON_SIKA_ERKA
    assert "25052" in NON_SIKA_ERKA


def test_no_overlap_sika_non_sika():
    assert set(ERKA_TO_KNR.keys()).isdisjoint(set(NON_SIKA_ERKA.keys()))
