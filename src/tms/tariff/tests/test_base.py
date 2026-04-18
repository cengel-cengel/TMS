"""Unit tests for TariffResult dataclass."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from tms.tariff.base import TariffResult


def test_total_all_components():
    r = TariffResult(
        basispreis=Decimal("100.00"),
        diesel_surcharge=Decimal("10.00"),
        maut_surcharge=Decimal("5.00"),
        other_surcharges={"peak": Decimal("2.50")},
    )
    assert r.total == Decimal("117.50")


def test_total_no_optional():
    r = TariffResult(
        basispreis=Decimal("200.00"),
        diesel_surcharge=None,
        maut_surcharge=None,
    )
    assert r.total == Decimal("200.00")


def test_defaults():
    r = TariffResult(
        basispreis=Decimal("1.00"),
        diesel_surcharge=None,
        maut_surcharge=None,
    )
    assert r.currency == "EUR"
    assert r.tariff_file == ""
    assert r.tariff_valid_from == date(1970, 1, 1)
    assert r.tariff_valid_to is None
    assert r.notes == []
    assert r.other_surcharges == {}
