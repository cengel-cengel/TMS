#!/usr/bin/env python3
"""Etappe 9a.1.D — Calculator validation across all 5 DLV customers (PRE period).

Computes dlv_soll per PRE shipment and aggregates delta% by route to check
whether the calculator engine is aligned with contracted rates before rollout.

Output: data/reports/9a1d_routes_validation.csv
"""
from __future__ import annotations
import math
import pickle
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path('/home/user/TMS')
sys.path.insert(0, str(BASE / 'src'))

# Import lookup functions from s5 (safe — guarded by if __name__ == '__main__')
from top20_abw_s5_tariff_check import (  # noqa: E402
    lookup_geze,
    lookup_cht,
    lookup_fischer,
    lookup_ebm,
    lookup_herma,
)
from tms.matching.normalize_plz import normalize_ie_county_for_dlv  # noqa: E402

OUT = BASE / 'data/reports'
OUT.mkdir(parents=True, exist_ok=True)

CUSTOMERS = {
    406035: ('GEZE GmbH',           'weight_100kg'),
    409480: ('Fischerwerke GmbH',   'stellplatz'),
    410844: ('EBM-Papst Mulfingen', 'ldm_stpl'),
    423650: ('HERMA GmbH',          'weight_herma'),
    486073: ('CHT Germany GmbH',    'weight_100kg'),
}

LOOKUP_FNS = {
    406035: lookup_geze,
    409480: lookup_fischer,
    410844: lookup_ebm,
    423650: lookup_herma,
    486073: lookup_cht,
}


def _normalize_row_for_ebm(row: pd.Series) -> pd.Series | None:
    """For EBM IE rows: map county code → Eircode. Returns None if unmappable."""
    land = str(row.get('Empfänger Land', '') or '').strip().upper()
    if land != 'IE':
        return row
    plz_raw = str(row.get('Empfänger PLZ', '') or '').strip()
    mapped = normalize_ie_county_for_dlv(plz_raw)
    if mapped is None:
        return None
    row_copy = row.copy()
    row_copy['Empfänger PLZ'] = mapped
    return row_copy


def _interpret(n: int, median_pct: float, spread: float) -> str:
    if n < 3:
        return 'zu wenig Daten'
    if spread > 5.0:
        return 'streut, prüfen'
    if -10.0 <= median_pct <= -3.0:
        return 'Diesel-konsistent'
    if median_pct > 1.0 or median_pct < -15.0:
        return 'Calculator-Prüfung'
    return 'atypisch'


print("Loading BI data …")
with open(BASE / 'output/bi_top20_data.pkl', 'rb') as f:
    bi = pickle.load(f)['df']

rows_out = []

for knr, (kname, tarifgruppe) in CUSTOMERS.items():
    pre = bi[(bi['Kunden Nr BK'] == knr) & (bi['periode'] == 'PRE')].copy()
    print(f"\n{kname} (KNR {knr}): {len(pre)} PRE rows")

    lookup_fn = LOOKUP_FNS[knr]
    row_deltas: list[dict] = []

    for _, row in pre.iterrows():
        erloese = float(row.get('Erloese', 0) or 0)
        if erloese <= 0:
            continue

        if knr == 410844:
            row_for_lookup = _normalize_row_for_ebm(row)
            if row_for_lookup is None:
                continue
        else:
            row_for_lookup = row

        try:
            dlv_soll = lookup_fn(row_for_lookup)
        except Exception:
            dlv_soll = None

        if dlv_soll is None:
            continue

        delta = dlv_soll - erloese
        delta_pct = delta / erloese * 100

        land    = str(row.get('Empfänger Land', '') or '').strip().upper()
        plz_raw = str(row.get('Empfänger PLZ',  '') or '').strip()
        plz2    = re.sub(r'[^A-Z0-9]', '', plz_raw.upper())[:2]
        route   = f"{land}-{plz2}" if plz2 else land

        row_deltas.append({
            'route':      route,
            'delta_pct':  delta_pct,
        })

    print(f"  → {len(row_deltas)} rows with DLV match")

    # Aggregate by route
    if not row_deltas:
        continue

    df_r = pd.DataFrame(row_deltas)
    for route, grp in df_r.groupby('route'):
        pcts = grp['delta_pct'].dropna().tolist()
        n = len(pcts)
        if n == 0:
            continue
        median_pct = float(np.median(pcts))
        min_pct    = float(np.min(pcts))
        max_pct    = float(np.max(pcts))
        spread     = max_pct - min_pct

        rows_out.append({
            'kunde':          kname,
            'route':          route,
            'tarifgruppe':    tarifgruppe,
            'n':              n,
            'median_pct':     round(median_pct, 2),
            'min_pct':        round(min_pct, 2),
            'max_pct':        round(max_pct, 2),
            'spread':         round(spread, 2),
            'interpretation': _interpret(n, median_pct, spread),
        })

df_out = pd.DataFrame(rows_out)
out_path = OUT / '9a1d_routes_validation.csv'
df_out.to_csv(out_path, index=False, float_format='%.2f')
print(f"\nWritten: {out_path} ({len(df_out)} routes)")

print("\n=== Summary ===")
if not df_out.empty:
    print(df_out['interpretation'].value_counts().to_string())
    flagged = df_out[df_out['interpretation'].isin(['Calculator-Prüfung', 'atypisch'])]
    if not flagged.empty:
        print("\nFlagged routes (Calculator-Prüfung / atypisch):")
        print(flagged[['kunde','route','tarifgruppe','n','median_pct','min_pct','max_pct','spread','interpretation']].to_string(index=False))
