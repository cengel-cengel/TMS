#!/usr/bin/env python3
"""Etappe 9b.2 — GEZE POST Inventur + PLZ-Normalisierung.

Outputs:
  data/reports/9b2_geze_inventur.csv   — Zeilenweise Beurteilbarkeits-Flag
  Console-Summary                       — Lane-Übersicht

Beurteilbarkeits-Kategorien:
  beurteilbar         — DLV-Land, Tonnage>0, PLZ normalisierbar
  t_zero              — Tonnage=0, LDM=0 → kein Billing-Gewicht
  no_dlv              — Land nicht im Exporttarife-Block (GR/CY/DE)
  no_dlv_t_zero       — beides
"""
from __future__ import annotations

import math
import pickle
import re
import sys
from pathlib import Path

import pandas as pd

BASE = Path('/home/user/TMS')
OUT  = BASE / 'data/reports'
OUT.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(BASE / 'src'))
from tms.tariff.calculators.geze import _COUNTRY_LOOKUP  # noqa: E402

# ---------------------------------------------------------------------------
# Load + filter
# ---------------------------------------------------------------------------
with open(BASE / 'output/bi_top20_data.pkl', 'rb') as f:
    bi = pickle.load(f)['df']


def rn_valid(x: object) -> bool:
    try:
        return float(str(x).replace(',', '.')) > 5
    except Exception:
        return False


core = bi[
    (bi['Kunden Nr BK'] == 406035) &
    (bi['periode'] == 'POST') &
    bi['Rechnungsnummer'].apply(rn_valid) &
    (bi['Erlöse Fracht'].fillna(0) > 0)
].copy()

core['datum'] = pd.to_datetime(core['Leistungsdatum'], errors='coerce')

# ---------------------------------------------------------------------------
# Phase (kein separates 2026-DLV → 2025-Fallback bleibt aktiv)
# ---------------------------------------------------------------------------
VSTART = pd.Timestamp('2025-01-01')
VEND   = pd.Timestamp('2025-12-31')


def phase(d: pd.Timestamp) -> str:
    if pd.isna(d):
        return 'unknown'
    if d < VSTART:
        return 'pre_dlv'
    if d <= VEND:
        return 'in_dlv_2025'
    return 'in_dlv_2025_fallback'   # 2025-DLV aktiv bis neues DLV verfügbar


core['phase'] = core['datum'].apply(phase)

# ---------------------------------------------------------------------------
# PLZ normalisierung + Zone-Probe
# ---------------------------------------------------------------------------
DLV_LANDS = set(_COUNTRY_LOOKUP.keys())   # PT GB IE IT FR AT ES CH


def norm_plz(plz: object, land: str) -> str:
    """Strip to usable form for zone lookup."""
    s = str(plz).strip()
    if land == 'IE':
        # Extract first 3 chars (Eircode district code) — lookup always Zone 1 anyway
        return re.sub(r'\s.*', '', s)[:3]
    # Numeric: strip non-digits (handles "1500-417" → "1500417", "611 00" → "61100")
    return re.sub(r'[^0-9A-Z]', '', s.upper())


def plz_lookup_ok(plz: object, land: str) -> bool:
    """Returns True if the zone lookup succeeds for this PLZ/Land."""
    if land not in DLV_LANDS:
        return False
    fn = _COUNTRY_LOOKUP.get(land.upper())
    if fn is None:
        return False
    try:
        return fn(norm_plz(plz, land)) is not None
    except Exception:
        return False


core['plz_norm']  = core.apply(lambda r: norm_plz(r['Empfänger PLZ'], r['Empfänger Land']), axis=1)
core['plz_ok']    = core.apply(lambda r: plz_lookup_ok(r['Empfänger PLZ'], r['Empfänger Land']), axis=1)
core['in_dlv_land'] = core['Empfänger Land'].isin(DLV_LANDS)
core['tonnage_ok']  = core['Tonnage (eff.)'] > 0


def beurteilbar(row: pd.Series) -> str:
    if not row['in_dlv_land']:
        return 'no_dlv_t_zero' if not row['tonnage_ok'] else 'no_dlv'
    if not row['tonnage_ok']:
        return 't_zero'
    if not row['plz_ok']:
        return 'plz_no_match'
    return 'beurteilbar'


core['status'] = core.apply(beurteilbar, axis=1)

# ---------------------------------------------------------------------------
# Output CSV
# ---------------------------------------------------------------------------
OUT_COLS = [
    'Rechnungsnummer', 'datum', 'phase',
    'Empfänger Land', 'Empfänger PLZ', 'plz_norm', 'plz_ok',
    'Tonnage (eff.)', 'Lademeter',
    'Erlöse Fracht', 'Erlöse Diesel', 'Erlöse Maut',
    'status',
]
out_df = core[[c for c in OUT_COLS if c in core.columns]].copy()
out_df.to_csv(OUT / '9b2_geze_inventur.csv', index=False)
print(f"Written: 9b2_geze_inventur.csv  ({len(out_df)} rows)")

# ---------------------------------------------------------------------------
# Console summary
# ---------------------------------------------------------------------------
print('\n' + '=' * 70)
print('=== 9b.2 GEZE POST INVENTUR ===')
print('=' * 70)

total    = len(core)
b_count  = (core['status'] == 'beurteilbar').sum()
t0_count = (core['status'] == 't_zero').sum()
nd_count = core['status'].isin(['no_dlv', 'no_dlv_t_zero']).sum()
pm_count = (core['status'] == 'plz_no_match').sum()

print(f"\nGEZE POST Core (RN>5, Erlöse Fracht>0): {total}")
print(f"  Beurteilbar (DLV-Land + Tonnage>0 + PLZ-OK): {b_count:4d}  ({b_count/total*100:.1f}%)")
print(f"  Tonnage=0 (LDM=0, kein Billing-Gewicht):     {t0_count:4d}  ({t0_count/total*100:.1f}%)")
print(f"  No-DLV-Land (GR/CY/DE):                      {nd_count:4d}  ({nd_count/total*100:.1f}%)")
print(f"  PLZ-No-Match (DLV-Land, aber kein Zone-Hit):  {pm_count:4d}  ({pm_count/total*100:.1f}%)")

print(f"\nPhasen-Verteilung (alle {total} Zeilen):")
for ph, n in core['phase'].value_counts().items():
    print(f"  {ph:<28}: {n:4d}  ({n/total*100:.1f}%)")

print(f"\nLane-Übersicht (beurteilbare Zeilen: {b_count}):")
beurt = core[core['status'] == 'beurteilbar']
for land, grp in beurt.groupby('Empfänger Land'):
    n = len(grp)
    eur = grp['Erlöse Fracht'].sum()
    ch_note = '  ← CHF-Floater' if land == 'CH' else ''
    print(f"  {land:3s}: {n:4d} Zeilen  {eur:9.2f} EUR{ch_note}")

print(f"\nPLZ-Normalisierung:")
print(f"  PT 'X-Strich'-Format (z.B. 1500-417) → digit-strip → Zone-Lookup OK")
print(f"  IE Eircode (D22, D22 DE00) → first 3 chars → Zone 1 (immer)")
print(f"  GR Space-PLZ (611 00) → digit-strip → no_dlv (kein GR-Block im Exporttarife)")
print(f"  GB Postcode-Area (WS/G/BT) → alpha-lookup → Zones 1-4")

print(f"\nTonnage=0 Länder (1.109 in DLV-Ländern = unbeurteilbar):")
t0_dlv = core[core['status'] == 't_zero']
for land, n in t0_dlv['Empfänger Land'].value_counts().items():
    eur = t0_dlv[t0_dlv['Empfänger Land'] == land]['Erlöse Fracht'].sum()
    print(f"  {land:3s}: {n:4d} Zeilen  {eur:8.2f} EUR")

print(f"\nNo-DLV Länder:")
for land, n in core[core['status'].isin(['no_dlv','no_dlv_t_zero'])].groupby('Empfänger Land').size().items():
    eur = core[core['Empfänger Land'] == land]['Erlöse Fracht'].sum()
    note = ''
    if land == 'GR': note = ' (separate DLV-Datei 20250121_Export_Griechenland)'
    if land == 'CY': note = ' (separate DLV-Datei Zypern)'
    if land == 'DE': note = ' (Inland/intern, kein Exporttarife-Block)'
    print(f"  {land:3s}: {n:4d} Zeilen  {eur:8.2f} EUR{note}")

print('\nDone.')
