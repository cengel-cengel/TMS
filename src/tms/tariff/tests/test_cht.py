"""
Validation tests for CHTItalyCalculator against 5 real 2026 POST shipments.

Sourced from bi_top20_data.pkl (Kunden Nr BK=486073, Empfänger Land=IT,
periode=POST, Leistungsdatum >= 2026-01-01, Erlöse Fracht > 0).
DLV: 20260112_CHT_Export und Import Italien.xlsx (valid 2026-01-01 to 2026-12-31).

Coverage:
  Case 1: per-Sendung, Zone 3 (actual 845.6 kg → bis-900 band)
  Case 2: per-Sendung, Zone 2 (actual 876 kg → bis-900 band)
  Case 3: per-100kg, Zone 1 (billing 1200 kg → bis-1500 band)
  Case 4: per-100kg, Zone 3 (billing 5100 kg → bis-6000 band)
  Case 5: special PLZ 20098 (billing 3500 kg → bis-3500 band, special DLV)
"""
from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from tms.tariff.calculators.cht import CHTItalyCalculator

CALC = CHTItalyCalculator()

# (empf_plz, empf_land, actual_kg, exp_fracht, exp_maut, label)
CASES = [
    ("12089", "IT", 845.6,   Decimal("221.61"), Decimal("5.04"),  "per-Sendung Zone 3"),
    ("28069", "IT", 876.0,   Decimal("173.95"), Decimal("5.04"),  "per-Sendung Zone 2"),
    ("22063", "IT", 1138.93, Decimal("164.76"), Decimal("6.72"),  "per-100kg Zone 1"),
    ("59100", "IT", 5082.31, Decimal("567.63"), Decimal("28.56"), "per-100kg Zone 3"),
    ("20098", "IT", 3405.14, Decimal("345.80"), Decimal("19.60"), "special PLZ 20098"),
]

TOLERANCE = Decimal("0.02")


def _check(plz, land, actual_kg, exp_fracht, exp_maut, label):
    result = CALC.calculate(plz, land, tonnage_kg=actual_kg)
    expected_total = exp_fracht + exp_maut
    actual_total = result.basispreis + (result.maut_surcharge or Decimal("0"))
    if expected_total > 0:
        pct_diff = abs(actual_total - expected_total) / expected_total
        assert pct_diff <= TOLERANCE, (
            f"{label}: DLV={actual_total:.4f} vs actual={expected_total:.4f} "
            f"({pct_diff*100:.2f}% off)"
        )


def test_all_cases():
    for case in CASES:
        _check(*case)


def print_comparison_table():
    import math

    print(f"\n{'Label':<24} {'actual_kg':>10} {'bill_kg':>8} "
          f"{'DLV_frt':>9} {'DLV_maut':>9} {'DLV_tot':>9} "
          f"{'Act_tot':>9} {'Diff%':>7}")
    print("-" * 95)
    for plz, land, actual_kg, exp_fracht, exp_maut, label in CASES:
        billing_kg = max(100, math.ceil(actual_kg / 100) * 100)
        try:
            result = CALC.calculate(plz, land, tonnage_kg=actual_kg)
            dlv_frt  = result.basispreis
            dlv_maut = result.maut_surcharge or Decimal("0")
            dlv_tot  = dlv_frt + dlv_maut
            act_tot  = exp_fracht + exp_maut
            pct = float(dlv_tot - act_tot) / float(act_tot) * 100 if act_tot else 0
            status = "OK" if abs(pct) <= 2 else "FAIL"
            print(
                "%-24s %10.2f %8d %9.2f %9.2f %9.2f %9.2f %+6.1f%%  %s"
                % (label, actual_kg, billing_kg,
                   float(dlv_frt), float(dlv_maut), float(dlv_tot),
                   float(act_tot), pct, status)
            )
        except Exception as e:
            print("%-24s %10.2f %8d  ERROR: %s" % (label, actual_kg, billing_kg, e))


if __name__ == "__main__":
    print_comparison_table()
