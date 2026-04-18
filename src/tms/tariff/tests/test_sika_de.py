"""
Validation tests for SikaDeCalculator against real BI POST-period shipments.

Erlöse Fracht = DLV base rate (basispreis).
Erlöse Maut   = DE-Maut surcharge (maut_surcharge).
Diesel is separate/monthly-variable and NOT validated here.
Tolerance: ≤ 2% on basispreis.

Routes covered: IT-41049, GB-LU5 5UL (capped stpl), ES-19171, IE-D11, PT-4785.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

try:
    import pytest
    _HAVE_PYTEST = True
except ImportError:
    _HAVE_PYTEST = False

from tms.tariff.calculators.sika_de import SikaDeCalculator

TOLERANCE = Decimal("0.02")

# (empf_plz, empf_land, stellplaetze, shipment_date,
#  expected_fracht, expected_maut, label)
CASES = [
    # IT-41049 (IT-41 zone), 14 Stpl — maut = 14 × 2.00 = 28.00
    ("41049", "IT", 14.0, date(2025,  9, 29), Decimal("650.05"),  Decimal("28.00"),
     "IT-41049 14 Stpl"),
    # GB-LU5 5UL (GB-LU area), stpl=34 → capped at 33 — maut cap 30-33 = 68.00
    ("LU5 5UL", "GB", 34.0, date(2025,  9, 30), Decimal("2712.35"), Decimal("68.00"),
     "GB-LU 34→cap33 Stpl"),
    # ES-19171 (ES-19 zone), 33 Stpl — maut cap 30-33 = 45.00
    ("19171",   "ES", 33.0, date(2025,  9, 30), Decimal("2137.70"), Decimal("45.00"),
     "ES-19171 33 Stpl"),
    # IE-D11 (IE-D1 zone), 2 Stpl — maut = 2 × 2.40 = 4.80
    ("D11",     "IE",  2.0, date(2025,  9, 30), Decimal("307.80"),  Decimal("4.80"),
     "IE-D11 2 Stpl"),
    # PT-4785 (PT-4 zone), 2 Stpl — maut = 2 × 1.60 = 3.20
    ("4785",    "PT",  2.0, date(2025, 10,  6), Decimal("244.30"),  Decimal("3.20"),
     "PT-4785 2 Stpl"),
]


def _pct(calc: Decimal, expected: Decimal) -> Decimal:
    if expected == 0:
        return Decimal("0")
    return (calc - expected) / expected * Decimal("100")


if _HAVE_PYTEST:
    @pytest.mark.parametrize(
        "empf_plz,empf_land,stellplaetze,shipment_date,expected_fracht,expected_maut,label",
        CASES,
    )
    def test_sika_de_case(
        empf_plz, empf_land, stellplaetze, shipment_date,
        expected_fracht, expected_maut, label,
    ):
        calc = SikaDeCalculator()
        result = calc.calculate(
            empf_plz=empf_plz,
            empf_land=empf_land,
            stellplaetze=stellplaetze,
            shipment_date=shipment_date,
        )
        dev = _pct(result.basispreis, expected_fracht)
        assert abs(dev) <= TOLERANCE * 100, (
            f"{label}: basispreis={result.basispreis} expected={expected_fracht}"
            f" dev={dev:.2f}%"
        )
        assert result.maut_surcharge == expected_maut, (
            f"{label}: maut={result.maut_surcharge} expected={expected_maut}"
        )


def main() -> None:
    calc = SikaDeCalculator()

    print(
        f"\n{'Label':<30} {'PLZ':<10} {'Land':<4} {'Stpl':>5} "
        f"{'Fracht':>8} {'Exp':>8} {'Dev%':>7}  {'Maut':>6} {'ExpM':>6}  Status"
    )
    print("-" * 100)

    all_pass = True
    for empf_plz, empf_land, stellplaetze, shipment_date, expected_fracht, expected_maut, label in CASES:
        try:
            result = calc.calculate(
                empf_plz=empf_plz,
                empf_land=empf_land,
                stellplaetze=stellplaetze,
                shipment_date=shipment_date,
            )
            dev = _pct(result.basispreis, expected_fracht)
            maut_ok = result.maut_surcharge == expected_maut
            status = "OK" if abs(dev) <= TOLERANCE * 100 and maut_ok else "FAIL"
            if status == "FAIL":
                all_pass = False
            print(
                f"{label:<30} {empf_plz:<10} {empf_land:<4} {stellplaetze:>5.1f} "
                f"{result.basispreis:>8.2f} {expected_fracht:>8.2f} {dev:>+7.2f}%"
                f"  {result.maut_surcharge:>6.2f} {expected_maut:>6.2f}  {status}"
            )
        except Exception as e:
            all_pass = False
            print(f"{label:<30} ERROR: {e}")

    print()
    n = len(CASES)
    if all_pass:
        print(f"All {n}/{n} cases PASS (≤2% tolerance, exact maut)")
    else:
        print("SOME CASES FAILED")


if __name__ == "__main__":
    main()
