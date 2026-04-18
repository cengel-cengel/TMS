"""
Validation tests for FischerwerkeCalculator against real BI shipment data.

All cases are POST-period shipments from DE-72178 Waldachtal where
Erlöse Maut = 0 and Erlöse Diesel = 0 (both included in DLV base rate).
Expected values = Erlöse Fracht from BI, confirmed as exact DLV matches.
Tolerance: ≤ 2% (target: 0%).

Routes covered: IT-35127 Padua, DK-4600 Køge, GB-OX Wallingford (3 routes).
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

try:
    import pytest
    _HAVE_PYTEST = True
except ImportError:
    _HAVE_PYTEST = False

from tms.tariff.calculators.fischerwerke import FischerwerkeCalculator

TOLERANCE = Decimal("0.02")

# (origin_plz, empf_plz, empf_land, stellplaetze, shipment_date, expected_fracht, label)
CASES = [
    # IT-35127 Padua — DLV (20250422) valid 01.05.2025–31.12.2025
    ("72178", "35127",  "IT", 9.0,  date(2025, 9, 29), Decimal("375.00"),  "IT-35127 Padua, 9 Stpl"),
    ("72178", "35127",  "IT", 3.0,  date(2025, 9, 30), Decimal("125.00"),  "IT-35127 Padua, 3 Stpl"),
    # DK-4600 Køge — DLV (20250422) valid 01.05.2025–31.12.2025
    ("72178", "4600",   "DK", 22.0, date(2025, 9, 30), Decimal("1450.00"), "DK-4600 Koge, 22 Stpl"),
    ("72178", "4600",   "DK", 1.0,  date(2025, 9, 30), Decimal("250.00"),  "DK-4600 Koge, 1 Stpl"),
    # GB-OX Wallingford — DLV (20250422) valid 01.05.2025–31.12.2025
    ("72178", "OX10 0", "GB", 24.0, date(2025,10,  1), Decimal("1965.00"), "GB-OX Wallingford, 24 Stpl"),
]


def _pct(calc: Decimal, expected: Decimal) -> Decimal:
    if expected == 0:
        return Decimal("0")
    return (calc - expected) / expected * Decimal("100")


if _HAVE_PYTEST:
    @pytest.mark.parametrize(
        "origin_plz,empf_plz,empf_land,stellplaetze,shipment_date,expected,label",
        CASES,
    )
    def test_fischerwerke_case(
        origin_plz, empf_plz, empf_land, stellplaetze, shipment_date, expected, label
    ):
        calc = FischerwerkeCalculator()
        result = calc.calculate(
            empf_plz=empf_plz,
            empf_land=empf_land,
            stellplaetze=stellplaetze,
            shipment_date=shipment_date,
        )
        dev = _pct(result.basispreis, expected)
        assert abs(dev) <= TOLERANCE * 100, (
            f"{label}: basispreis={result.basispreis} expected={expected} dev={dev:.2f}%"
        )


def main() -> None:
    calc = FischerwerkeCalculator()

    print(
        f"\n{'Label':<35} {'PLZ':<10} {'Land':<4} {'Stpl':>6} "
        f"{'Soll':>8} {'Exp':>8} {'Dev%':>7}  Status"
    )
    print("-" * 95)

    all_pass = True
    for origin_plz, empf_plz, empf_land, stellplaetze, shipment_date, expected, label in CASES:
        try:
            result = calc.calculate(
                empf_plz=empf_plz,
                empf_land=empf_land,
                stellplaetze=stellplaetze,
                shipment_date=shipment_date,
            )
            dev = _pct(result.basispreis, expected)
            status = "OK" if abs(dev) <= TOLERANCE * 100 else "FAIL"
            if status == "FAIL":
                all_pass = False
            route_note = next((n for n in result.notes if n.startswith("route=")), "")
            stpl_note = next((n for n in result.notes if n.startswith("stpl_int=")), "")
            print(
                f"{label:<35} {empf_plz:<10} {empf_land:<4} {stellplaetze:>6.1f} "
                f"{result.basispreis:>8.2f} {expected:>8.2f} {dev:>+7.2f}%  {status}"
                f"  [{route_note}  {stpl_note}]"
            )
        except Exception as e:
            all_pass = False
            print(f"{label:<35} ERROR: {e}")

    print()
    n = len(CASES)
    if all_pass:
        print(f"All {n}/{n} cases PASS (≤2% tolerance)")
    else:
        print("SOME CASES FAILED")


if __name__ == "__main__":
    main()
