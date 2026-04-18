"""
Validation tests for EBMCalculator against 5 real March-2026 POST shipments.

Shipments sourced from bi_top20_data.pkl (Kunden Nr BK=410844, periode=POST,
Leistungsdatum >= 2026-03-01). Expected = Erlöse Fracht + Erlöse Maut.
DLV file: 20260227_ebm-papst ... Export Europa.xlsx (valid 2026-03-01 to 2026-12-31).
"""
from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from tms.tariff.calculators.ebm import EBMCalculator

CALC = EBMCalculator()

# (empf_plz, empf_land, lademeter, expected_fracht, expected_maut, label)
CASES = [
    ("75306", "EE", 2.4, Decimal("660.00"), Decimal("0.00"),   "EE-75306 n=6"),
    ("913 11", "SK", 0.4, Decimal("174.00"), Decimal("1.11"),  "SK-913 11 n=1"),
    ("1370",  "SI", 1.2, Decimal("305.00"), Decimal("5.12"),   "SI-1370 n=3"),
    ("R32 PN8W", "IE", 5.2, Decimal("1871.90"), Decimal("24.71"), "IE-R32 n=13"),
    ("59-241", "PL", 0.4, Decimal("79.00"), Decimal("2.48"),   "PL-59-241 n=1"),
]

TOLERANCE = Decimal("0.02")  # 2%


@pytest.mark.parametrize("plz,land,ldm,exp_fracht,exp_maut,label", CASES)
def test_ebm_rate(plz, land, ldm, exp_fracht, exp_maut, label):
    result = CALC.calculate(plz, land, lademeter=ldm)
    expected_total = exp_fracht + exp_maut
    actual_total = result.basispreis + (result.maut_surcharge or Decimal("0"))

    if expected_total > 0:
        pct_diff = abs(actual_total - expected_total) / expected_total
        assert pct_diff <= TOLERANCE, (
            f"{label}: DLV={actual_total:.2f} vs actual={expected_total:.2f} "
            f"({pct_diff*100:.1f}% off)"
        )
    else:
        assert actual_total == Decimal("0"), f"{label}: expected 0, got {actual_total}"


def print_comparison_table():
    """Print a comparison table of DLV vs actual rates (for manual review)."""
    print(f"\n{'Label':<20} {'LDM':>5} {'n_ps':>5} "
          f"{'DLV_fracht':>12} {'DLV_maut':>10} {'DLV_total':>11} "
          f"{'Act_total':>11} {'Diff%':>7}")
    print("-" * 90)

    import math

    for plz, land, ldm, exp_fracht, exp_maut, label in CASES:
        n_ps = max(1, math.ceil(ldm / 0.4))
        try:
            result = CALC.calculate(plz, land, lademeter=ldm)
            dlv_fracht = result.basispreis
            dlv_maut = result.maut_surcharge or Decimal("0")
            dlv_total = dlv_fracht + dlv_maut
            act_total = exp_fracht + exp_maut
            pct = (dlv_total - act_total) / act_total * 100 if act_total else 0
            status = "OK" if abs(pct) <= 2 else "FAIL"
            print(f"{label:<20} {ldm:>5.1f} {n_ps:>5} "
                  f"{dlv_fracht:>12.2f} {dlv_maut:>10.2f} {dlv_total:>11.2f} "
                  f"{act_total:>11.2f} {pct:>+6.1f}%  {status}")
        except Exception as e:
            print(f"{label:<20} {ldm:>5.1f} {n_ps:>5}  ERROR: {e}")


if __name__ == "__main__":
    print_comparison_table()
