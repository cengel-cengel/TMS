#!/usr/bin/env python3
"""9c.2d CHTAustriaCalculator — Unit Tests.

Covers:
  a) Band-boundary semantics: actual_kg = 50.0001 → bis-100 band (not bis-50)
  b) Unknown PLZ zone: prefix 29 not in DLV zone table → LookupError
  c) Boundary exactness: actual_kg = 50.0 → bis-50 band (≤ is inclusive)
  d) Happy-path spot-checks against Schritt-1 validated BI values
  e) Maut uses ceil-rounding (not actual_kg), minimum 100 kg
  f) Non-AT destination → LookupError
  g) tonnage_kg = 0 → ValueError
"""
from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

BASE = Path('/home/user/TMS')
sys.path.insert(0, str(BASE / 'src'))
from tms.tariff.calculators.cht_at import CHTAustriaCalculator  # noqa: E402

_calc = CHTAustriaCalculator()

_PASS = 0
_FAIL = 0


def _check(label: str, got, expected, tol: float = 0.005) -> None:
    global _PASS, _FAIL
    diff = abs(float(got) - float(expected))
    if diff <= tol:
        print(f"  ✓ {label}  got={float(got):.4f}  exp={float(expected):.4f}")
        _PASS += 1
    else:
        print(f"  ✗ {label}  got={float(got):.4f}  exp={float(expected):.4f}  |Δ|={diff:.4f}")
        _FAIL += 1


def _expect_error(label: str, exc_type: type, fn) -> None:
    global _PASS, _FAIL
    try:
        fn()
        print(f"  ✗ {label}  expected {exc_type.__name__} but no exception raised")
        _FAIL += 1
    except exc_type as e:
        print(f"  ✓ {label}  raised {exc_type.__name__}: {e}")
        _PASS += 1
    except Exception as e:
        print(f"  ✗ {label}  wrong exception {type(e).__name__}: {e}")
        _FAIL += 1


print('=' * 68)
print('=== 9c.2d CHTAustriaCalculator UNIT TESTS ===')
print('=' * 68)

# ---------------------------------------------------------------------------
# Edge case a: Band-boundary semantics
# ---------------------------------------------------------------------------
print('\n[Edge case a] Band-boundary: actual_kg vs bis-threshold')
# 50.0 → bis-50 band (boundary is ≤)
r = _calc.calculate('6700', 'AT', tonnage_kg=50.0)
_check('actual_kg=50.00 → bis-50 Zone1 rate (28.71)', r.basispreis, 28.71)

# 50.0001 → bis-100 band (strictly greater than 50 → next band)
r = _calc.calculate('6700', 'AT', tonnage_kg=50.0001)
_check('actual_kg=50.0001 → bis-100 Zone1 rate (34.44)', r.basispreis, 34.44)

# 100.0 → bis-100 band
r = _calc.calculate('6700', 'AT', tonnage_kg=100.0)
_check('actual_kg=100.00 → bis-100 Zone1 rate (34.44)', r.basispreis, 34.44)

# 100.0001 → bis-150 band
r = _calc.calculate('6700', 'AT', tonnage_kg=100.0001)
_check('actual_kg=100.0001 → bis-150 Zone1 rate (37.35)', r.basispreis, 37.35)

# ---------------------------------------------------------------------------
# Edge case b: Unknown PLZ zone → LookupError
# ---------------------------------------------------------------------------
print('\n[Edge case b] Unknown PLZ prefix → LookupError')
# Prefix 29 is not covered by zones 1–6 (gap between Zone 5 hi=28 and Zone 6 lo=30)
_expect_error(
    'PLZ=2900 prefix=29 not in zone table',
    LookupError,
    lambda: _calc.calculate('2900', 'AT', tonnage_kg=100.0),
)
# Prefix 58 also a gap (Zone 3 ends at 57, Zone 1 starts at 67)
_expect_error(
    'PLZ=5800 prefix=58 not in zone table',
    LookupError,
    lambda: _calc.calculate('5800', 'AT', tonnage_kg=100.0),
)

# ---------------------------------------------------------------------------
# Edge case c: Maut uses ceil-rounding, not actual_kg
# ---------------------------------------------------------------------------
print('\n[Edge case c] Maut rounding: ceil(actual_kg/100)*100, min 100 kg')
# actual_kg=32.10 → maut_kg=100 → maut=0.56
r = _calc.calculate('9020', 'AT', tonnage_kg=32.10)
_check('actual_kg=32.10 → maut=0.56 EUR (maut_kg=100)', r.maut_surcharge, Decimal('0.56'))

# actual_kg=501.12 → maut_kg=600 → maut=3.36
r = _calc.calculate('4020', 'AT', tonnage_kg=501.12)
_check('actual_kg=501.12 → maut=3.36 EUR (maut_kg=600)', r.maut_surcharge, Decimal('3.36'))

# actual_kg=12144.0 → maut_kg=12200 → maut=68.32
r = _calc.calculate('3331', 'AT', tonnage_kg=12144.0)
_check('actual_kg=12144.0 → maut=68.32 EUR (maut_kg=12200)', r.maut_surcharge, Decimal('68.32'))

# ---------------------------------------------------------------------------
# Happy-path spot-checks — Schritt-1 validated BI values
# ---------------------------------------------------------------------------
print('\n[Happy path] Schritt-1 validated BI spot-checks (|Δ| ≤ 0.01 EUR)')

# RN 924061, PLZ 3331 (Zone 6), 12144 kg → bis-15000 → 1118.43
r = _calc.calculate('3331', 'AT', tonnage_kg=12144.0)
_check('PLZ 3331 Zone6 12144kg → 1118.43', r.basispreis, Decimal('1118.43'))

# RN 924061, PLZ 4020 (Zone 3), 501.12 kg → bis-600 → 110.08
r = _calc.calculate('4020', 'AT', tonnage_kg=501.12)
_check('PLZ 4020 Zone3 501.12kg → 110.08', r.basispreis, Decimal('110.08'), tol=0.01)

# RN 924097, PLZ 5400 (Zone 2), 1013.65 kg → bis-1250 → 200.80
r = _calc.calculate('5400', 'AT', tonnage_kg=1013.65)
_check('PLZ 5400 Zone2 1013.65kg → 200.80', r.basispreis, Decimal('200.80'), tol=0.01)

# RN 924097, PLZ 6832 (Zone 1), 262.16 kg → bis-300 → 51.70
r = _calc.calculate('6832', 'AT', tonnage_kg=262.16)
_check('PLZ 6832 Zone1 262.16kg → 51.70', r.basispreis, Decimal('51.70'), tol=0.01)

# RN 924223, PLZ 7561 (Zone 6), 5913.90 kg → bis-7000 → 797.26
r = _calc.calculate('7561', 'AT', tonnage_kg=5913.90)
_check('PLZ 7561 Zone6 5913.90kg → 797.26', r.basispreis, Decimal('797.26'), tol=0.01)

# RN 924232, PLZ 9020 (Zone 6), 32.10 kg → bis-50 → 40.16
r = _calc.calculate('9020', 'AT', tonnage_kg=32.10)
_check('PLZ 9020 Zone6 32.10kg → 40.16', r.basispreis, Decimal('40.16'), tol=0.01)

# RN 924232, PLZ 3382 (Zone 6), 89.72 kg → bis-100 → 51.70
r = _calc.calculate('3382', 'AT', tonnage_kg=89.72)
_check('PLZ 3382 Zone6 89.72kg → 51.70', r.basispreis, Decimal('51.70'), tol=0.01)

# RN 924232, PLZ 4020 (Zone 3), 3192.0 kg → bis-5000 → 516.14
r = _calc.calculate('4020', 'AT', tonnage_kg=3192.0)
_check('PLZ 4020 Zone3 3192.0kg → 516.14', r.basispreis, Decimal('516.14'), tol=0.01)

# ---------------------------------------------------------------------------
# Guard rails
# ---------------------------------------------------------------------------
print('\n[Guard rails] Invalid inputs')
_expect_error(
    'empf_land=DE → LookupError',
    LookupError,
    lambda: _calc.calculate('7000', 'DE', tonnage_kg=100.0),
)
_expect_error(
    'tonnage_kg=0 → ValueError',
    ValueError,
    lambda: _calc.calculate('4020', 'AT', tonnage_kg=0),
)
_expect_error(
    'tonnage_kg=-1 → ValueError',
    ValueError,
    lambda: _calc.calculate('4020', 'AT', tonnage_kg=-1.0),
)
_expect_error(
    'actual_kg>20000 → LookupError',
    LookupError,
    lambda: _calc.calculate('4020', 'AT', tonnage_kg=20001.0),
)

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
total = _PASS + _FAIL
print(f'\n{"="*68}')
print(f'Unit Tests: {_PASS}/{total} passed')
print(f'{"✓ ALL PASSED" if _FAIL == 0 else f"✗ {_FAIL} FAILED"}')
print(f'{"="*68}')

if _FAIL > 0:
    raise SystemExit(1)
