"""
Validation tests for GrozBeckertCalculator against 5 real Abrechnungsstrecken cases.

DLV: 20250408_Erka_Groz Beckert_Templates_LKW Ausschreibung_01.05.25 - 30.06.26.xlsx
DLV valid: 2025-05-01 – 2026-06-30

Coverage:
  Case 1: Albstadt → PT  (LTL-FTL, LDM=2.5,  lane 72458→PT)
  Case 2: Albstadt → PT  (LTL-FTL, LDM=4.0,  lane 72458→PT)
  Case 3: Leinfelden → IT (GC, 935.9 kg, zone 20-25,30-43)
  Case 4: Albstadt → BE  (GC, 100.0 kg, zone 10-29,70-99)
  Case 5: Leinfelden → CH (LTL-FTL, LDM=1.4→rounded 1.5, lane 70794→CH)

Validation formula:
  result_total = basispreis + maut_surcharge
  betrag       = actual invoice amount (includes Diesel-Floater ~0.6-1.6%)
  error        = |result_total - betrag| / betrag ≤ 2%

Expected error range: ~1.35-1.4% (diesel floater exclusion accounts for the gap).
"""
from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from tms.tariff.calculators.groz_beckert import GrozBeckertCalculator

CALC = GrozBeckertCalculator()

# (origin_plz, empf_plz, empf_land, tonnage_kg, lademeter, betrag, label)
CASES = [
    ("72458", "4409-516", "PT", 1524.0,  2.5,  Decimal("621.24"),  "Albstadt PT LDM=2.5"),
    ("72458", "4409-516", "PT", 3210.0,  4.0,  Decimal("900.88"),  "Albstadt PT LDM=4.0"),
    ("70771", "24040",    "IT",  935.9,  1.1,  Decimal("170.16"),  "Leinfelden IT zone1 935kg"),
    ("72458", "8530",     "BE",  100.0,  None, Decimal("38.91"),   "Albstadt BE zone1 100kg"),
    ("70771", "4528",     "CH",  603.0,  1.4,  Decimal("258.03"),  "Leinfelden CH LDM=1.4"),
]

TOLERANCE = Decimal("0.02")  # 2% max


def _check(origin_plz, empf_plz, empf_land, tonnage_kg, lademeter, betrag, label):
    result = CALC.calculate(
        empf_plz=empf_plz,
        empf_land=empf_land,
        tonnage_kg=tonnage_kg,
        lademeter=lademeter,
        origin_plz=origin_plz,
    )
    total = result.basispreis + (result.maut_surcharge or Decimal("0"))
    pct = abs(total - betrag) / betrag
    assert pct <= TOLERANCE, (
        f"{label}: total={total:.2f} vs betrag={betrag:.2f} "
        f"({float(pct)*100:.2f}% off, limit={float(TOLERANCE)*100:.0f}%). "
        f"basis={result.basispreis:.2f}, maut={result.maut_surcharge}. "
        f"Notes: {result.notes}"
    )


def test_all_cases():
    for case in CASES:
        _check(*case)


def print_comparison_table():
    print(
        f"\n{'Label':<30} {'orig':>6} {'dest':>10} "
        f"{'basis':>8} {'maut':>7} {'total':>8} {'betrag':>8} "
        f"{'Diff%':>7} {'status':>6}"
    )
    print("-" * 110)

    for origin_plz, empf_plz, empf_land, tonnage_kg, lademeter, betrag, label in CASES:
        try:
            result = CALC.calculate(
                empf_plz=empf_plz,
                empf_land=empf_land,
                tonnage_kg=tonnage_kg,
                lademeter=lademeter,
                origin_plz=origin_plz,
            )
            maut  = result.maut_surcharge or Decimal("0")
            total = result.basispreis + maut
            pct   = float(total - betrag) / float(betrag) * 100
            ok    = "OK" if abs(pct) <= 2.0 else "FAIL"
            print(
                "%-30s %6s %10s %8.2f %7.2f %8.2f %8.2f %+6.2f%%  %s"
                % (
                    label,
                    origin_plz,
                    f"{empf_land} {empf_plz}",
                    float(result.basispreis),
                    float(maut),
                    float(total),
                    float(betrag),
                    pct,
                    ok,
                )
            )
            # Print mode/zone from notes
            mode_note = next((n for n in result.notes if n.startswith("mode=")), "")
            zone_note = next(
                (n for n in result.notes if n.startswith("dest_zone=") or n.startswith("billing_ldm=")),
                "",
            )
            print(f"  → {mode_note}  {zone_note}")
        except Exception as exc:
            print("%-30s  ERROR: %s" % (label, exc))


if __name__ == "__main__":
    print_comparison_table()
    print()
    # Also run assertions
    failures = []
    for case in CASES:
        try:
            _check(*case)
        except AssertionError as e:
            failures.append(str(e))
    if failures:
        print("FAILURES:")
        for f in failures:
            print(" ", f)
    else:
        print("All 5 cases PASSED within 2% tolerance.")
