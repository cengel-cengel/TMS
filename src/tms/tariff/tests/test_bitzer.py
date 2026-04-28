"""
Regression tests for BitzCalculator.

After P16 fix (2026-04-28):
  IT uses date-based dispatch: shipment_date < 2026-02-01 → 2025-STD DLV,
                                shipment_date >= 2026-02-01 → 2026-STD DLV.
  No-date default → 2025-STD (safe conservative fallback).
  PLZ 32010 is Zone 2 in BOTH standard DLVs (Upload DLV reclassification not applied in billing).

  FR-13400 Aubagne: special per-Sendung FTL DLV removed; LTL shipments use general FR Zone 9.

IT cases: 2025-STD DLV (default, no shipment_date)
AT, Benelux cases: 2025 DLVs.

Coverage:
  Case 1: Rottenburg → IT Zone 1, per-100kg (PLZ 40013, billing 700 kg) [2025-STD]
  Case 2: Rottenburg → IT Zone 2, per-100kg heavy (PLZ 32010, billing 11800 kg) [2025-STD, was Zone4 Upload]
  Case 3: Schkeuditz → IT Zone 1, per-100kg (PLZ 35040, billing 400 kg) [2025-STD]
  Case 4: Schkeuditz → IT Zone 4 minimum (PLZ 00134, billing 100 kg) [2025-STD]
  Case 5: Schkeuditz → AT Zone 3, per-100kg (PLZ 4113, billing 1700 kg)
  Case 6: Rottenburg → BE Zone 1 minimum (PLZ 9160, billing 100 kg)
  Case 7: Rottenburg → NL Zone 1, per-100kg (PLZ 3115, billing 500 kg)
  Case 8: Rottenburg → NL Zone 1, per-100kg heavy (PLZ 3751, billing 4500 kg)
  Case 9: Rottenburg → LU Zone 2 minimum (PLZ 5280, billing 100 kg)
  Case 10: Schkeuditz → LU Zone 2, per-100kg (PLZ 9809, billing 700 kg)
  Case 11: Rottenburg → IT Zone 2, 2026-STD (PLZ 32010, billing 11800 kg, date 2026-03-01)
  Case 12: FR-13400 Aubagne LTL → FR Zone 9 (billing 100 kg, min 46.3 EUR)
  Case 13: FR-13400 Aubagne LTL → FR Zone 9 (billing 500 kg)

Expected = DLV-computed basispreis (Maut included; Diesel separate).
"""
from __future__ import annotations

import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from tms.tariff.calculators.bitzer import BitzCalculator

CALC = BitzCalculator()

# (empf_plz, empf_land, tonnage_kg, origin_plz, exp_fracht, label, shipment_date)
CASES = [
    # IT 2025-STD (no date → default 2025-STD)
    ("40013", "IT", 617.6,   "71126", Decimal("108.5"),  "Rottenburg IT Zone1 700kg",          None),
    ("32010", "IT", 11783.3, "71126", Decimal("767.0"),  "Rottenburg IT Zone2 11800kg",         None),  # was Zone4 Upload
    ("35040", "IT", 317.5,   "04435", Decimal("71.2"),   "Schkeuditz IT Zone1 400kg",           None),
    ("00134", "IT", 80.7,    "04435", Decimal("53.2"),   "Schkeuditz IT Zone4 min",             None),
    # AT
    ("4113",  "AT", 1625.5,  "04435", Decimal("299.2"),  "Schkeuditz AT Zone3 1700kg",          None),
    # Benelux: Zone 1 = BE + NL (col 2), Zone 2 = LU (col 3)
    ("9160",  "BE", 35.0,    "71126", Decimal("40.9"),   "Rottenburg BE Zone1 min",             None),
    ("3115",  "NL", 472.0,   "71126", Decimal("114.5"),  "Rottenburg NL Zone1 500kg",           None),
    ("3751",  "NL", 4402.0,  "71126", Decimal("630.0"),  "Rottenburg NL Zone1 4500kg",          None),
    ("5280",  "LU", 14.9,    "71126", Decimal("64.3"),   "Rottenburg LU Zone2 min",             None),
    ("9809",  "LU", 649.7,   "04435", Decimal("204.4"),  "Schkeuditz LU Zone2 700kg",           None),
    # IT 2026-STD (explicit date)
    ("32010", "IT", 11783.3, "71126", Decimal("782.34"), "Rottenburg IT Zone2 11800kg 2026-STD", date(2026, 3, 1)),
    # FR-13400 Aubagne → Zone 9 (LTL, not per-Sendung FTL DLV)
    ("13400", "FR", 80.0,    "71126", Decimal("46.3"),   "FR-13400 Zone9 min",                  None),
    ("13400", "FR", 500.0,   "71126", Decimal("142.0"),  "FR-13400 Zone9 500kg",                None),
]

TOLERANCE = Decimal("0.01")   # 1% max


def _check(plz, land, tonnage_kg, origin_plz, exp_fracht, label, shipment_date):
    kwargs = dict(tonnage_kg=tonnage_kg, origin_plz=origin_plz)
    if shipment_date is not None:
        kwargs["shipment_date"] = shipment_date
    result = CALC.calculate(plz, land, **kwargs)
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

    print(f"\n{'Label':<38} {'t_kg':>8} {'bill_kg':>8} "
          f"{'DLV_frt':>9} {'Act_frt':>9} {'Diff%':>7} {'Zone':>5} {'Notes'}")
    print("-" * 120)
    for plz, land, tonnage_kg, origin_plz, exp_fracht, label, shipment_date in CASES:
        billing_kg = max(100, math.ceil(tonnage_kg / 100) * 100)
        try:
            kwargs = dict(tonnage_kg=tonnage_kg, origin_plz=origin_plz)
            if shipment_date is not None:
                kwargs["shipment_date"] = shipment_date
            result = CALC.calculate(plz, land, **kwargs)
            pct = float(result.basispreis - exp_fracht) / float(exp_fracht) * 100
            zone = next((n.split("=")[1] for n in result.notes if n.startswith("zone=")), "?")
            status = "OK" if abs(pct) <= 1 else "FAIL"
            print(
                "%-38s %8.1f %8d %9.2f %9.2f %+6.1f%%  %4s  %s"
                % (label, tonnage_kg, billing_kg,
                   float(result.basispreis), float(exp_fracht), pct, zone, status)
            )
        except Exception as e:
            print("%-38s %8.1f %8d  ERROR: %s" % (label, tonnage_kg, billing_kg, e))


if __name__ == "__main__":
    print_comparison_table()
