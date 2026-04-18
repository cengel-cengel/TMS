"""Validation tests for GEZECalculator against real BI shipment data.

All cases are POST-period Leonberg shipments where Erlöse Maut = 0 (Maut included
in base rate) and Erlöse Diesel is separate. Expected values = Erlöse Fracht from BI.
Tolerance: ≤ 2% relative deviation (target: 0% for minimum/exact-rate cases).
"""
from __future__ import annotations

from decimal import Decimal

try:
    import pytest
    _HAVE_PYTEST = True
except ImportError:
    _HAVE_PYTEST = False

from tms.tariff.calculators.geze import GEZECalculator

TOLERANCE = Decimal("0.02")

# (origin_plz, empf_plz, empf_land, tonnage_kg, chf_eur_rate, expected_fracht, label)
CASES = [
    # AT Zone 6, PLZ 4020, t=37 kg → billing_kg=100, min=32.14 (rate×1=29.03 < min)
    ("71229", "4020",     "AT", 37.0,   None,  Decimal("32.14"),  "AT-Z6 min PLZ 4020"),
    # AT Zone 6, PLZ 4902, t=822.91 kg → billing_kg=900, 24.53×9=220.77
    ("71229", "4902",     "AT", 822.91, None,  Decimal("220.77"), "AT-Z6 rate PLZ 4902"),
    # IT Zone 2, PLZ 30175, t=90 kg → billing_kg=100, min=44.96
    ("71229", "30175",    "IT", 90.0,   None,  Decimal("44.96"),  "IT-Z2 min PLZ 30175"),
    # PT Zone 2, PLZ 3750-726, t=52.11 kg → billing_kg=100, min=58.96
    ("71229", "3750-726", "PT", 52.11,  None,  Decimal("58.96"),  "PT-Z2 min PLZ 3750-726"),
    # FR Zone 5, PLZ 12000, t=93 kg → billing_kg=100, min=92.17
    ("71229", "12000",    "FR", 93.0,   None,  Decimal("92.17"),  "FR-Z5 min PLZ 12000"),
    # CH Zone 2, PLZ 5436, t=16.23 kg → billing_kg=100, min=54.25; CHF floater 0% (rate~1.06)
    ("71229", "5436",     "CH", 16.23,  1.065, Decimal("54.25"),  "CH-Z2 min PLZ 5436 CHF-floater-0%"),
]


def _pct(calc: Decimal, expected: Decimal) -> Decimal:
    if expected == 0:
        return Decimal("0")
    return (calc - expected) / expected * Decimal("100")


if _HAVE_PYTEST:
    @pytest.mark.parametrize("origin_plz,empf_plz,empf_land,tonnage_kg,chf_eur_rate,expected,label", CASES)
    def test_geze_case(origin_plz, empf_plz, empf_land, tonnage_kg, chf_eur_rate, expected, label):
        calc = GEZECalculator()
        result = calc.calculate(
            empf_plz=empf_plz,
            empf_land=empf_land,
            tonnage_kg=tonnage_kg,
            chf_eur_rate=chf_eur_rate,
        )
        dev = _pct(result.basispreis, expected)
        assert abs(dev) <= TOLERANCE * 100, (
            f"{label}: basispreis={result.basispreis} expected={expected} dev={dev:.2f}%"
        )


def main() -> None:
    calc = GEZECalculator()
    print(f"\n{'Label':<35} {'PLZ':<12} {'Land':<4} {'t_kg':>8} {'billing':>8} "
          f"{'Soll':>8} {'Exp':>8} {'Dev%':>7}  {'Status'}")
    print("-" * 105)

    all_pass = True
    for origin_plz, empf_plz, empf_land, tonnage_kg, chf_eur_rate, expected, label in CASES:
        try:
            result = calc.calculate(
                empf_plz=empf_plz,
                empf_land=empf_land,
                tonnage_kg=tonnage_kg,
                chf_eur_rate=chf_eur_rate,
            )
            billing_kg_note = next(
                (n for n in result.notes if n.startswith("billing_kg=")), ""
            )
            billing_kg = billing_kg_note.split("=")[1] if billing_kg_note else "?"
            dev = _pct(result.basispreis, expected)
            status = "OK" if abs(dev) <= TOLERANCE * 100 else "FAIL"
            if status == "FAIL":
                all_pass = False
            zone_note = next((n for n in result.notes if n.startswith("zone=")), "")
            print(
                f"{label:<35} {empf_plz:<12} {empf_land:<4} {tonnage_kg:>8.2f} {billing_kg:>8} "
                f"{result.basispreis:>8.2f} {expected:>8.2f} {dev:>+7.2f}%  {status}"
                f"  [{zone_note}]"
            )
        except Exception as e:
            all_pass = False
            print(f"{label:<35} ERROR: {e}")

    print()
    if all_pass:
        print(f"All {len(CASES)}/{ len(CASES)} cases PASS (≤2% tolerance)")
    else:
        print("SOME CASES FAILED")


if __name__ == "__main__":
    main()
