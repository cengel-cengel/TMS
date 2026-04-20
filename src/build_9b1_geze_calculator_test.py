#!/usr/bin/env python3
"""Etappe 9b.1 — GEZE Calculator Integration Test.

Prüft GEZECalculator gegen manuell aus der DLV berechnete Sollwerte.
Toleranz: ≤ 0.01 EUR (Rundungsgrenze Decimal).

CHF-Floater-Testkurs: 0.94 CHF/EUR
  → Band 0.9372–0.9469 in CH-Währungsfloater-Sheet
  → Stückgut (≤3000 kg): sg=11.050 %
  → Komplett  (>3000 kg): ko= 6.000 %
  → Testkurs liegt in der Mitte des aktiven Bandes (Bandbreite 1.021–0.8882;
    0.94 entspricht ca. 2/3 der Bandbreite von oben, typischer CH-Kursbereich 2025/26)

Bug fixed before this test: _parse_chf_floater read cols 0-3 instead of 2-5;
table was always empty → chf_amount=0 for all CH rows (silent wrong result).
"""
from __future__ import annotations

import math
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from tms.tariff.calculators.geze import GEZECalculator

# ---------------------------------------------------------------------------
# Test cases
# Format: (empf_plz, empf_land, tonnage_kg, chf_eur_rate, exp_basis, exp_chf, label)
#   exp_basis : expected basispreis in EUR (DLV base, Maut included)
#   exp_chf   : expected chf_floater surcharge in EUR (0 for non-CH or neutral band)
# ---------------------------------------------------------------------------
CHF_TEST_RATE = 0.94   # → band 0.9372–0.9469, sg=11.050%, ko=6.000%

CASES: list[tuple[str, str, float, float | None, Decimal, Decimal, str]] = [
    # ── AT — 8 Zonen, PLZ-Präfix 2-stellig ─────────────────────────────────
    # Zone 1 (PLZ 67-69): min=35.60, ≤300=26.13, ≤500=25.67, ≤1000=25.10
    ("6700",    "AT", 250.0, None,
     Decimal("78.39"),  Decimal("0"),
     "AT-Z1 rate PLZ 6700, t=250→billing=300, 26.13×3=78.39"),
    # Zone 3 (PLZ 10-28): min=30.33, ≤300=26.08
    ("1010",    "AT",  38.0, None,
     Decimal("30.33"),  Decimal("0"),
     "AT-Z3 min PLZ 1010, t=38→billing=100, min 30.33"),
    # Zone 5 (PLZ 50-57): min=31.05, ≤300=27.79, ≤500=24.32, ≤1000=23.44, ≤2000=22.67
    ("5020",    "AT", 900.0, None,
     Decimal("211.08"), Decimal("0"),
     "AT-Z5 rate PLZ 5020, t=900→billing=900, 23.44×9=211.08... wait"),
    # Zone 8 (PLZ 90-99): min=57.70, ≤300=42.59, ≤2000=31.46
    ("9020",    "AT", 1500.0, None,
     Decimal("471.90"), Decimal("0"),
     "AT-Z8 rate PLZ 9020, t=1500→billing=1500, 31.46×15=471.90"),

    # ── IT — 6 Zonen ────────────────────────────────────────────────────────
    # Zone 1 (PLZ 39): min=26.06, ≤300=24.67
    ("39100",   "IT", 200.0, None,
     Decimal("49.34"),  Decimal("0"),
     "IT-Z1 rate PLZ 39100, t=200→billing=200, 24.67×2=49.34"),
    # Zone 3 (PLZ 10-19): min=53.87, ≤1000=42.23
    ("10100",   "IT", 600.0, None,
     Decimal("253.38"), Decimal("0"),
     "IT-Z3 rate PLZ 10100, t=600→billing=600, 42.23×6=253.38"),
    # Zone 6 (PLZ 07-09, 90-98): min=58.09, ≤300=51.86
    ("07100",   "IT", 100.0, None,
     Decimal("58.09"),  Decimal("0"),
     "IT-Z6 min PLZ 07100, t=100→billing=100, min 58.09"),

    # ── FR — 7 Zonen (Zone 7 via PLZ-Whitelist) ────────────────────────────
    # Zone 1 (PLZ 67): min=52.45, ≤1000=32.07
    ("67000",   "FR", 1000.0, None,
     Decimal("320.70"), Decimal("0"),
     "FR-Z1 rate PLZ 67000, t=1000→billing=1000, 32.07×10=320.70"),
    # Zone 6 (PLZ 04): min=123.24, ≤300=90.16
    ("04000",   "FR", 100.0,  None,
     Decimal("123.24"), Decimal("0"),
     "FR-Z6 min PLZ 04000, t=100→billing=100, min 123.24"),
    # Zone 7 (PLZ whitelist 77127): min=77.09, ≤300=62.89
    ("77127",   "FR", 200.0,  None,
     Decimal("125.78"), Decimal("0"),
     "FR-Z7 rate PLZ 77127, t=200→billing=200, 62.89×2=125.78"),

    # ── GB — 4 Zonen (Postcode-Area-basiert) ────────────────────────────────
    # Zone 1 (WS=Walsall/West Midlands): min=83.29, ≤300=50.05
    ("WS10 1AB", "GB", 300.0, None,
     Decimal("150.15"), Decimal("0"),
     "GB-Z1 rate PLZ WS10 1AB, t=300→billing=300, 50.05×3=150.15"),
    # Zone 3 (G=Glasgow): min=108.81, ≤300=85.35
    ("G11 1AA",  "GB",  70.0, None,
     Decimal("108.81"), Decimal("0"),
     "GB-Z3 min PLZ G11 1AA, t=70→billing=100, min 108.81"),

    # ── ES — 8 Zonen ────────────────────────────────────────────────────────
    # Zone 1 (PLZ 08=Barcelona): min=53.63, ≤2000=29.18
    ("08001",   "ES", 1500.0, None,
     Decimal("437.70"), Decimal("0"),
     "ES-Z1 rate PLZ 08001, t=1500→billing=1500, 29.18×15=437.70"),
    # Zone 7 (PLZ 35=Las Palmas): min=165.61, ≤300=69.00
    ("35001",   "ES", 300.0,  None,
     Decimal("207.00"), Decimal("0"),
     "ES-Z7 rate PLZ 35001, t=300→billing=300, 69.00×3=207.00"),

    # ── PT — 4 Zonen ────────────────────────────────────────────────────────
    # Zone 1 (PLZ 10-19): min=58.96, ≤300=41.23
    ("1000",    "PT",  52.0, None,
     Decimal("58.96"),  Decimal("0"),
     "PT-Z1 min PLZ 1000, t=52→billing=100, min 58.96"),
    # Zone 4 (PLZ 50-69): min=78.23, ≤300=49.63
    ("5000",    "PT", 150.0,  None,
     Decimal("99.26"),  Decimal("0"),
     "PT-Z4 rate PLZ 5000, t=150→billing=200, 49.63×2=99.26"),

    # ── IE — 1 Zone ─────────────────────────────────────────────────────────
    # Zone 1 (alle IE-PLZ): min=106.65, ≤300=90.39
    ("D02",     "IE",  35.0, None,
     Decimal("106.65"), Decimal("0"),
     "IE-Z1 min PLZ D02, t=35→billing=100, min 106.65"),
    # Zone 1, größere Sendung
    ("A92",     "IE", 600.0, None,
     Decimal("514.26"), Decimal("0"),
     "IE-Z1 rate PLZ A92, t=600→billing=600, 85.71×6=514.26"),

    # ── CH — 9 Zonen + CHF-Floater ─────────────────────────────────────────
    # Zone 1 (PLZ 40-44), kein Floater (neutral-Band ≥1.021)
    ("4001",    "CH", 200.0, 1.065,
     Decimal("71.66"),  Decimal("0"),
     "CH-Z1 PLZ 4001, CHF=1.065 (neutral-Band→sg=0%), basispreis=max(51.41,35.83×2)=71.66"),
    # Zone 1, CHF=0.94 (sg=11.050%): basispreis=71.66, chf=71.66×0.1105=7.92
    ("4001",    "CH", 200.0, CHF_TEST_RATE,
     Decimal("71.66"),  Decimal("7.92"),
     "CH-Z1 PLZ 4001, CHF=0.94 (sg=11.050%), chf=71.66×0.1105=7.92"),
    # Zone 9 (PLZ 19=Sion/Sierre VS), CHF=0.94: basispreis=max(98.09,68.38×4)=273.52, chf=30.22
    ("1900",    "CH", 400.0, CHF_TEST_RATE,
     Decimal("273.52"), Decimal("30.22"),
     "CH-Z9 PLZ 1900, CHF=0.94, basispreis=max(98.09,68.38×4)=273.52, chf=273.52×0.1105=30.22"),
]


# ---------------------------------------------------------------------------
# Fix AT Zone 5 expected value (compute correctly)
# Zone 5 (PLZ 50-57): min=31.05, ≤300=27.79, ≤500=24.32, ≤1000=23.44
# t=900 → billing=900 → band ≤1000 → rate=23.44 → soll=max(31.05, 23.44×9)=max(31.05, 210.96)=210.96
# ---------------------------------------------------------------------------
_CORRECTED: dict[str, Decimal] = {
    "AT-Z5 rate PLZ 5020, t=900→billing=900, 23.44×9=211.08... wait": Decimal("210.96"),
}


def run() -> None:
    calc = GEZECalculator()
    hdr = (f"{'Label':<62} {'PLZ':<10} {'Land':<4} {'t_kg':>7} "
           f"{'basis':>7} {'chf':>6} {'exp_b':>7} {'exp_c':>6} {'Dev':>6}  Status")
    print(f"\n{hdr}")
    print("-" * 130)

    n_pass = n_fail = 0
    for empf_plz, empf_land, tonnage_kg, chf_rate, exp_basis, exp_chf, label in CASES:
        exp_basis_final = _CORRECTED.get(label, exp_basis)
        try:
            result = calc.calculate(
                empf_plz=empf_plz,
                empf_land=empf_land,
                tonnage_kg=tonnage_kg,
                chf_eur_rate=chf_rate,
            )
            got_basis = result.basispreis
            got_chf   = result.other_surcharges.get("chf_floater", Decimal("0"))
            dev_b = got_basis - exp_basis_final
            dev_c = got_chf  - exp_chf
            ok = abs(dev_b) <= Decimal("0.01") and abs(dev_c) <= Decimal("0.01")
            status = "OK" if ok else "FAIL"
            if ok:
                n_pass += 1
            else:
                n_fail += 1
            zone_note = next((n for n in result.notes if n.startswith("zone=")), "")
            print(
                f"{label[:62]:<62} {empf_plz:<10} {empf_land:<4} {tonnage_kg:>7.0f} "
                f"{got_basis:>7.2f} {got_chf:>6.2f} "
                f"{exp_basis_final:>7.2f} {exp_chf:>6.2f} "
                f"{float(dev_b):>+5.2f}  {status}  [{zone_note}]"
            )
        except Exception as e:
            n_fail += 1
            print(f"{label[:62]:<62} {empf_plz:<10} {empf_land:<4}  ERROR: {e}")

    print()
    total = n_pass + n_fail
    if n_fail == 0:
        print(f"All {total}/{total} cases PASS (≤0.01 EUR tolerance)")
    else:
        print(f"{n_fail} FAIL / {n_pass} PASS  ({total} total)")
    return n_fail


if __name__ == "__main__":
    sys.exit(run())
