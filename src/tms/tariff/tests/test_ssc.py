"""
Validation tests for SSCCalculator (KNR 511241) against real BI POST-period shipments.

Same DLV and rate structure as SikaDeCalculator — see test_sika_de.py for details.
Tolerance: ≤ 2% on basispreis; exact maut_surcharge.

Routes covered: GB-LU5 5UL, IT-41049, ES-28108, IT-20068 (×2).
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

try:
    import pytest
    _HAVE_PYTEST = True
except ImportError:
    _HAVE_PYTEST = False

from tms.tariff.calculators.ssc import SSCCalculator

TOLERANCE = Decimal("0.02")

# (empf_plz, empf_land, stellplaetze, shipment_date,
#  expected_fracht, expected_maut, label)
CASES = [
    # GB-LU5 5UL (GB-LU area), 1 Stpl — maut = 1 × 2.40 = 2.40
    ("LU5 5UL", "GB",  1.0, date(2025, 11,  7), Decimal("193.95"),  Decimal("2.40"),
     "GB-LU 1 Stpl"),
    # IT-41049 (IT-41 zone), 33 Stpl — maut cap 30-33 = 56.00
    ("41049",   "IT", 33.0, date(2025, 11, 19), Decimal("1154.60"), Decimal("56.00"),
     "IT-41049 33 Stpl"),
    # ES-28108 (ES-28xxx zone), 33 Stpl — maut cap 30-33 = 45.00
    ("28108",   "ES", 33.0, date(2025,  9, 30), Decimal("2137.70"), Decimal("45.00"),
     "ES-28108 33 Stpl"),
    # IT-20068 (IT-20 zone), 1 Stpl — maut = 1 × 2.00 = 2.00
    ("20068",   "IT",  1.0, date(2025, 10, 20), Decimal("110.40"),  Decimal("2.00"),
     "IT-20068 1 Stpl"),
    # IT-20068 (IT-20 zone), 4 Stpl — maut = 4 × 2.00 = 8.00
    ("20068",   "IT",  4.0, date(2025, 11,  3), Decimal("266.45"),  Decimal("8.00"),
     "IT-20068 4 Stpl"),
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
    def test_ssc_case(
        empf_plz, empf_land, stellplaetze, shipment_date,
        expected_fracht, expected_maut, label,
    ):
        calc = SSCCalculator()
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
    calc = SSCCalculator()

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
