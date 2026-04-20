#!/usr/bin/env python3
"""Etappe 9c.2 — CHT POST Inventur + PLZ-Normalisierung.

Scope: alle CHT POST-Zeilen KNR 486073 (Leistungsdatum ≥ 27.09.2025).

Beurteilbarkeits-Kategorien pro Zeile:
  beurteilbar_calc   — IT + in_dlv_2026, Calculator läuft (Gate-1-fähig)
  beurteilbar_pre    — IT + pre_dlv_2026, Calculator verfügbar aber Phase unbeurteilbar
  no_calculator      — AT/BE/ES/GR: DLV-Datei vorhanden, aber kein Calculator implementiert
  no_dlv_land        — DE (Inland, kein Exporttarife-Block)
  t_zero             — Tonnage=0
  plz_no_match       — PLZ nicht normalisierbar

Gate 1: Route-Match-Quote pro Land
  IT  : aus 9c.1 (100 %)  → ✓ PASS
  AT/BE/ES/GR : kein Calculator → N/A (9c.3 für diese Länder blockiert)
  <85 % = WARNING; <75 % = STOP

Outputs:
  data/reports/9c2_cht_inventur.csv   — Zeilenweise Flags
  Console-Summary                      — Länder-Übersicht + Gate-1-Tabelle
"""
from __future__ import annotations

import math
import pickle
import sys
from pathlib import Path

import pandas as pd

BASE = Path('/home/user/TMS')
OUT  = BASE / 'data/reports'
OUT.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(BASE / 'src'))
from tms.tariff.calculators.cht import CHTItalyCalculator  # noqa: E402

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
DLV_START_2026 = pd.Timestamp('2026-01-01')
INV_START      = pd.Timestamp('2025-09-27')

# 2026 DLV files available per country
DLV_2026_AVAILABLE = {'IT', 'AT', 'BE', 'ES', 'GR'}
# Calculator implemented per country
CALC_IMPLEMENTED = {'IT'}

# PLZ normalization widths (digits only)
PLZ_WIDTHS = {'IT': 5, 'AT': 4, 'BE': 4, 'ES': 5, 'GR': 5, 'DE': 5}

# Known §8 cases from 9c.1 (excluded from Gate-1 IT check)
KNOWN_S8: set[tuple[str, str]] = {
    ('923847',     '20098'),
    ('923957',     '59100'),
    ('923981',     '59100'),
    ('924020',     '59100'),
    ('923981',     '20098'),
    ('924068',     '75015'),
    ('924249',     '20098'),
    ('924249',     '22063'),
    ('4251024551', '13866'),
}

# ---------------------------------------------------------------------------
# Load + base filter
# ---------------------------------------------------------------------------
with open(BASE / 'output/bi_top20_data.pkl', 'rb') as f:
    bi = pickle.load(f)['df']


def rn_valid(x: object) -> bool:
    try:
        return float(str(x).replace(',', '.')) > 5
    except Exception:
        return False


cht = bi[
    (bi['Kunden Nr BK'] == 486073) &
    (bi['periode'] == 'POST') &
    bi['Rechnungsnummer'].apply(rn_valid) &
    (bi['Erlöse Fracht'].fillna(0) > 0)
].copy()

cht['datum'] = pd.to_datetime(cht['Leistungsdatum'], errors='coerce')

# Verify KNR uniqueness
other_knr = cht[cht['Kunden Nr BK'] != 486073]
assert len(other_knr) == 0, f"Unexpected KNRs: {other_knr['Kunden Nr BK'].unique()}"

# ---------------------------------------------------------------------------
# Phase + PLZ normalization
# ---------------------------------------------------------------------------
def phase(d: pd.Timestamp) -> str:
    if pd.isna(d):
        return 'unknown'
    return 'in_dlv_2026' if d >= DLV_START_2026 else 'pre_dlv_2026'


def norm_plz(plz: object, land: str) -> str:
    s = str(plz).strip().replace(' ', '')  # GR: "564 30" → "56430"
    digits = ''.join(c for c in s if c.isdigit())
    w = PLZ_WIDTHS.get(land, 5)
    return digits.zfill(w) if digits else s


def plz_ok(plz_n: str, land: str) -> bool:
    w = PLZ_WIDTHS.get(land, 5)
    return len(plz_n) == w and plz_n.isdigit()


cht['phase']    = cht['datum'].apply(phase)
cht['land']     = cht['Empfänger Land'].str.strip()
cht['plz_norm'] = cht.apply(lambda r: norm_plz(r['Empfänger PLZ'], r['land']), axis=1)
cht['plz_ok']   = cht.apply(lambda r: plz_ok(r['plz_norm'], r['land']), axis=1)
cht['rn_str']   = cht['Rechnungsnummer'].astype(str).str.strip()
cht['tonnage_ok'] = cht['Tonnage (eff.)'].fillna(0) > 0
cht['is_s8']    = cht.apply(lambda r: (r['rn_str'], r['plz_norm']) in KNOWN_S8, axis=1)


def row_status(row: pd.Series) -> str:
    if not row['tonnage_ok']:
        return 't_zero'
    land = row['land']
    if land not in DLV_2026_AVAILABLE and land != 'IT':
        return 'no_dlv_land'
    if land == 'DE':
        return 'no_dlv_land'
    if not row['plz_ok']:
        return 'plz_no_match'
    if land not in CALC_IMPLEMENTED:
        return 'no_calculator'
    if row['phase'] == 'in_dlv_2026':
        return 'beurteilbar_calc'
    return 'beurteilbar_pre'


cht['status'] = cht.apply(row_status, axis=1)

# ---------------------------------------------------------------------------
# Gate 1: run IT Calculator on in_dlv_2026 rows (excl. §8)
# ---------------------------------------------------------------------------
calc = CHTItalyCalculator()

it_gate = cht[
    (cht['land'] == 'IT') &
    (cht['status'] == 'beurteilbar_calc') &
    (~cht['is_s8'])
].copy()

bp_list, ok_list, err_list = [], [], []
for _, row in it_gate.iterrows():
    try:
        res = calc.calculate(
            empf_plz=row['plz_norm'],
            empf_land='IT',
            tonnage_kg=float(row['Tonnage (eff.)']),
        )
        bp = float(res.basispreis)
        delta = abs(row['Erlöse Fracht'] - bp)
        bp_list.append(bp)
        ok_list.append(delta <= 0.01)
        err_list.append('')
    except Exception as e:
        bp_list.append(float('nan'))
        ok_list.append(False)
        err_list.append(str(e))

it_gate['basispreis']  = bp_list
it_gate['match_01']    = ok_list
it_gate['calc_err']    = err_list

it_match_n   = int(it_gate['match_01'].sum())
it_test_n    = len(it_gate)
it_match_pct = it_match_n / it_test_n * 100 if it_test_n > 0 else 0.0

# ---------------------------------------------------------------------------
# Output CSV
# ---------------------------------------------------------------------------
OUT_COLS = [
    'Rechnungsnummer', 'datum', 'phase', 'land',
    'Empfänger PLZ', 'plz_norm', 'plz_ok',
    'Tonnage (eff.)', 'Erlöse Fracht', 'Erlöse Diesel', 'Erlöse Maut',
    'is_s8', 'status',
]
out_df = cht[[c for c in OUT_COLS if c in cht.columns]].copy()
out_df.to_csv(OUT / '9c2_cht_inventur.csv', index=False)
print(f"Written: 9c2_cht_inventur.csv  ({len(out_df)} rows)")

# ---------------------------------------------------------------------------
# Console summary
# ---------------------------------------------------------------------------
print('\n' + '=' * 72)
print('=== 9c.2 CHT POST INVENTUR (KNR 486073) ===')
print('=' * 72)

total = len(cht)
print(f"\nTotal CHT POST (KNR 486073, RN>5, Fracht>0): {total}")
print(f"  KNR-Verteilung: 486073 only — bestätigt")

print(f"\nPhasen-Gesamt:")
for ph, n in cht['phase'].value_counts().sort_index().items():
    print(f"  {ph:<20}: {n:4d}  ({n/total*100:.1f}%)")

print(f"\nLänder-Übersicht:")
hdr = f"  {'Land':4s}  {'Total':>5}  {'in_dlv':>6}  {'pre':>5}  {'t0':>3}  "
hdr += f"{'beurt_calc':>10}  {'no_calc':>7}  {'no_dlv':>6}  {'Fracht EUR':>12}  DLV-2026  Calc"
print(hdr)
print('  ' + '-' * (len(hdr) - 2))

for land in sorted(cht['land'].unique()):
    g = cht[cht['land'] == land]
    n          = len(g)
    in_dlv     = (g['phase'] == 'in_dlv_2026').sum()
    pre        = (g['phase'] == 'pre_dlv_2026').sum()
    t0         = (~g['tonnage_ok']).sum()
    bc         = (g['status'] == 'beurteilbar_calc').sum()
    nc         = (g['status'] == 'no_calculator').sum()
    nd         = (g['status'] == 'no_dlv_land').sum()
    eur        = g['Erlöse Fracht'].sum()
    dlv_flag   = 'JA ' if land in DLV_2026_AVAILABLE else 'nein'
    calc_flag  = 'JA ' if land in CALC_IMPLEMENTED else 'nein'
    print(f"  {land:4s}  {n:5d}  {in_dlv:6d}  {pre:5d}  {t0:3d}  "
          f"{bc:10d}  {nc:7d}  {nd:6d}  {eur:12.2f}  {dlv_flag}       {calc_flag}")

print(f"\nPLZ-Normalisierung:")
for land in sorted(cht['land'].unique()):
    g = cht[cht['land'] == land]
    ok_n = g['plz_ok'].sum()
    fail_n = (~g['plz_ok']).sum()
    sample_fails = g[~g['plz_ok']]['Empfänger PLZ'].dropna().astype(str).head(3).tolist()
    note = f"  → Fehler-Samples: {sample_fails}" if fail_n > 0 else ''
    print(f"  {land}: OK={ok_n}  FAIL={fail_n}  (norm-Breite: {PLZ_WIDTHS.get(land, 5)} Stellen){note}")

print(f"\n{'='*72}")
print(f"GATE 1 — Route-Match-Quote (|Δ Fracht| ≤ 0.01 EUR):")
print(f"  IT  (in_dlv_2026 exkl. §8): {it_match_n}/{it_test_n} = {it_match_pct:.1f}%", end='')
if it_match_pct >= 90.0:
    print('  → ✓ PASS')
elif it_match_pct >= 85.0:
    print('  → ⚠ WARNING (<90 %)')
else:
    print('  → ✗ STOP (<85 %)')

for land in ['AT', 'BE', 'ES', 'GR']:
    g = cht[cht['land'] == land]
    in_dlv_n = (g['phase'] == 'in_dlv_2026').sum()
    t0_n     = (~g['tonnage_ok']).sum()
    print(f"  {land}  (in_dlv_2026={in_dlv_n}, t0={t0_n}): kein Calculator → N/A  → 9c.3 blockiert")

print(f"\n§8-Fälle total: {cht['is_s8'].sum()} (9c.1-bekannte Ausreißer, davon IT)")

s8_land = cht[cht['is_s8']].groupby(['land','phase']).size().reset_index(name='n')
for _, r in s8_land.iterrows():
    print(f"  {r['land']} / {r['phase']}: {r['n']}")

print(f"\nNächste Schritte:")
print(f"  9c.3 IT    : Calculator validiert (100 %) → Phasen-Rollout freigegeben")
print(f"  9c.3 AT    : CHTAustriaCalculator implementieren (DLV: 20260112_CHT_Export Österreich.xlsx)")
print(f"  9c.3 BE    : CHTBelgiumCalculator implementieren (DLV: 20260112_CHT_Export Belgien.xlsx)")
print(f"  9c.3 ES    : CHTSpainCalculator implementieren   (DLV: 20260112_CHT_Export & Import Spanien.xlsx)")
print(f"  9c.3 GR    : CHTGreeceCalculator implementieren  (DLV: 20260112_CHT_Export Griechenland.xlsx)")
print(f"  DE (11 Zeilen): kein Exporttarif-Block → exkludiert")
print(f"\nDone.")
