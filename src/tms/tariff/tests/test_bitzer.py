"""
Validation tests for BitzCalculator against 5 real POST shipments.

Sourced from bi_top20_data.pkl (Kunden Nr BK=406345, periode=POST,
Erlöse Fracht > 0, Tonnage eff. == Tonnage frpfl. to eliminate billing-basis
ambiguity). DLV: 2025 files (valid 2025-01-01 – 2025-12-31).

Coverage:
  Case 1: Rottenburg → IT Zone 1, per-100kg (PLZ 40013, billing 700 kg)
  Case 2: Rottenburg → IT Zone 2, per-100kg heavy (PLZ 32010, billing 11800 kg)
  Case 3: Schkeuditz → IT Zone 1 minimum (PLZ 35040, billing 400 kg)
  Case 4: Schkeuditz → IT Zone 4 minimum (PLZ 00134, billing 100 kg)
  Case 5: Schkeuditz → AT Zone 3, per-100kg (PLZ 4113, billing 1700 kg)

Expected = Erlöse Fracht only (Maut included in DLV base; Diesel separate ~4%).
"""
from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from tms.tariff.calculators.bitzer import BitzCalculator

CALC = BitzCalculator()

# (empf_plz, empf_land, tonnage_kg, origin_plz, exp_fracht, label)
CASES = [
    ("40013", "IT", 617.6,   "71126", Decimal("108.5"),  "Rottenburg IT Zone1 700kg"),
    ("32010", "IT", 11783.3, "71126", Decimal("767.0"),  "Rottenburg IT Zone2 11800kg"),
    ("35040", "IT", 317.5,   "04435", Decimal("71.2"),   "Schkeuditz IT Zone1 400kg"),
    ("00134", "IT", 80.7,    "04435", Decimal("53.2"),   "Schkeuditz IT Zone4 min"),
    ("4113",  "AT", 1625.5,  "04435", Decimal("299.2"),  "Schkeuditz AT Zone3 1700kg"),
]

TOLERANCE = Decimal("0.01")   # 1% max — target 0%


def _check(plz, land, tonnage_kg, origin_plz, exp_fracht, label):
    result = CALC.calculate(plz, land, tonnage_kg=tonnage_kg, origin_plz=origin_plz)
    pct = abs(result.basispreis - exp_fracht) / exp_fracht if exp_fracht else Decimal("0")
    assert pct <= TOLERANCE, (
        f"{label}: DLV={result.basispreis:.2f} vs actual={exp_fracht:.2f} "
        f"({float(pct)*100:.2f}% off). Notes: {result.notes}"
    )


def test_all_cases():
    for case in CASES:
        _check(*case)


def print_comparison_table():
    import math

    print(f"\n{'Label':<30} {'t_kg':>8} {'bill_kg':>8} "
          f"{'DLV_frt':>9} {'Act_frt':>9} {'Diff%':>7} {'Zone':>5} {'Notes'}")
    print("-" * 110)
    for plz, land, tonnage_kg, origin_plz, exp_fracht, label in CASES:
        billing_kg = max(100, math.ceil(tonnage_kg / 100) * 100)
        try:
            result = CALC.calculate(plz, land, tonnage_kg=tonnage_kg, origin_plz=origin_plz)
            pct = float(result.basispreis - exp_fracht) / float(exp_fracht) * 100
            zone = next((n.split("=")[1] for n in result.notes if n.startswith("zone=")), "?")
            status = "OK" if abs(pct) <= 1 else "FAIL"
            print(
                "%-30s %8.1f %8d %9.2f %9.2f %+6.1f%%  %4s  %s"
                % (label, tonnage_kg, billing_kg,
                   float(result.basispreis), float(exp_fracht), pct, zone, status)
            )
        except Exception as e:
            print("%-30s %8.1f %8d  ERROR: %s" % (label, tonnage_kg, billing_kg, e))


if __name__ == "__main__":
    print_comparison_table()
