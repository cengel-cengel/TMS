#!/usr/bin/env python3
"""Etappe 9a.3.1 — Padova DLV Calculator Reverse-Engineering.

Tests 4 rounding hypotheses against Abrechnungsstrecken Betrag.
Output: data/reports/9a3_padova_reverse_eng.csv
"""
from __future__ import annotations
import math
from pathlib import Path
import numpy as np
import pandas as pd

BASE = Path('/home/user/TMS')
OUT  = BASE / 'data/reports'

# ── 1. Parse DLV tariff table ────────────────────────────────────────────────
dlv_path = (BASE / 'Fischerwerke/DLVs & Tarife/2026'
            '/20251219_Fischerwerke_DE-72 Waldachtal nach IT-35127 Padua_2026.xlsx')
raw = pd.read_excel(dlv_path, sheet_name='Tarifblatt DE-72->IT-35127', header=None)

dlv: dict[int, float] = {}
for _, row in raw.iterrows():
    try:
        stpl = int(float(row[0]))
        rate = float(row[1])
        if 1 <= stpl <= 40 and rate > 0:
            dlv[stpl] = rate
    except (TypeError, ValueError):
        continue

max_stpl = max(dlv)
cap_rate = dlv[max_stpl]

def dlv_lookup(n: int) -> float:
    n = max(1, min(n, max_stpl))
    return dlv.get(n, cap_rate)

def interp(stpl: float) -> float:
    lo = max(1, math.floor(stpl))
    hi = min(max_stpl, math.ceil(stpl))
    if lo == hi:
        return dlv_lookup(lo)
    frac = stpl - lo
    return dlv_lookup(lo) * (1 - frac) + dlv_lookup(hi) * frac

# ── 2. Load Padova rows (Betrag > 0) ────────────────────────────────────────
abr = pd.read_excel(BASE / 'data/extracted/abrechnungsstrecken'
                    '/Abrechnungsstrecken/Fischerwerke.xlsx')
padova = abr[(abr['Nach Ort'] == 'Padova') & (abr['Betrag'] > 0)].copy()
print(f"Padova rows (Betrag>0): {len(padova)}")

# ── 3. Compute hypotheses ────────────────────────────────────────────────────
records = []
for _, r in padova.iterrows():
    stpl    = r['Abrechnungsstellplätze']
    betrag  = float(r['Betrag'])
    auftrnr = r['Auftragsnummer']

    if pd.isna(stpl):
        h1 = h2 = h3 = h4 = float('nan')
    else:
        s = float(stpl)
        h1 = dlv_lookup(round(s))
        h2 = dlv_lookup(math.ceil(s))
        h3 = dlv_lookup(max(1, math.floor(s)))
        h4 = interp(s)

    records.append({
        'auftragsnr':   auftrnr,
        'nach_ort':     r['Nach Ort'],
        'ausgangsrel':  r['Ausgangsrelation'],
        'stpl':         stpl,
        'betrag':       betrag,
        'h1_round':     h1,
        'h2_ceil':      h2,
        'h3_floor':     h3,
        'h4_interp':    h4,
        'delta_round':  betrag - h1 if not math.isnan(h1) else float('nan'),
        'delta_ceil':   betrag - h2 if not math.isnan(h2) else float('nan'),
        'delta_floor':  betrag - h3 if not math.isnan(h3) else float('nan'),
        'delta_interp': betrag - h4 if not math.isnan(h4) else float('nan'),
    })

df = pd.DataFrame(records)
out_path = OUT / '9a3_padova_reverse_eng.csv'
df.to_csv(out_path, index=False, float_format='%.4f')
print(f"Written: {out_path}  ({len(df)} rows)")

# ── 4. Identity rates ────────────────────────────────────────────────────────
print("\n=== Identity Rates ===")
for hyp in ['round', 'ceil', 'floor', 'interp']:
    col_d = f'delta_{hyp}'
    col_h = f'h{["round","ceil","floor","interp"].index(hyp)+1}_{hyp}'
    sub = df[df[col_d].notna()]
    n = len(sub)
    n_ok     = (sub[col_d].abs() < 0.01).sum()
    n_ok_5   = ((sub[col_d].abs() / sub[f'h{["round","ceil","floor","interp"].index(hyp)+1}_{hyp}'].abs()) < 0.05).sum()
    max_d    = sub[col_d].abs().max()
    med_d    = sub[col_d].abs().median()
    print(f"  H_{hyp:6s}: n={n}  exact(±0.01)={n_ok:3d} ({n_ok/n*100:.1f}%)  "
          f"within5%={n_ok_5:3d} ({n_ok_5/n*100:.1f}%)  "
          f"max|Δ|={max_d:.2f}  med|Δ|={med_d:.2f}")

# ── 5. Stpl-Bucket analysis ──────────────────────────────────────────────────
print("\n=== Stpl-Bucket Analysis (H1_round) ===")
df['stpl_bucket'] = df['stpl'].apply(
    lambda s: round(float(s)) if pd.notna(s) else None)
bucket_rows = []
for bucket, grp in df[df['stpl_bucket'].notna()].groupby('stpl_bucket'):
    bucket = int(bucket)
    dlv_rate = dlv.get(bucket, float('nan'))
    med_betrag = grp['betrag'].median()
    med_delta  = grp['delta_round'].median()
    n_ok       = (grp['delta_round'].abs() < 0.01).sum()
    bucket_rows.append({
        'stpl_bucket': bucket,
        'dlv_rate':    dlv_rate,
        'n':           len(grp),
        'med_betrag':  round(med_betrag, 2),
        'med_delta':   round(med_delta, 3),
        'n_exact':     int(n_ok),
    })
bdf = pd.DataFrame(bucket_rows).sort_values('stpl_bucket')
print(bdf.to_string(index=False))

# ── 6. Teillasten (<1 Stpl) ──────────────────────────────────────────────────
print("\n=== Teillasten (Stpl < 1) ===")
teil = df[df['stpl'] < 1][['auftragsnr','stpl','betrag','h2_ceil']].copy()
teil['ratio_betrag_per_stpl'] = teil['betrag'] / teil['stpl']
print(teil.to_string(index=False))

# ── 7. Betrag=315.00 with Stpl in {8,9} ──────────────────────────────────────
print("\n=== Betrag=315.00, Stpl in {8,9} ===")
special = df[(df['betrag'] == 315.00) & (df['stpl'].isin([8.0, 9.0]))]
print(f"Count: {len(special)}")
print(special[['auftragsnr','stpl','betrag','h1_round','delta_round']].to_string(index=False))
print(f"\nNote: DLV[8]={dlv[8]:.3f}, DLV[9]={dlv[9]:.3f}, Betrag=315.00")
print(f"  → delta_round for stpl=8: {315.0 - dlv[8]:.3f}")
print(f"  → delta_round for stpl=9: {315.0 - dlv[9]:.3f}")

# ── Rows matching no hypothesis within 5% ─────────────────────────────────────
print("\n=== Rows matching NO hypothesis within 5% ===")
no_match = df[
    df[['delta_round','delta_ceil','delta_floor','delta_interp']].notna().all(axis=1)
].copy()
# compute pct for each
for hyp, hi in [('round','h1_round'),('ceil','h2_ceil'),('floor','h3_floor'),('interp','h4_interp')]:
    no_match[f'pct_{hyp}'] = (no_match[f'delta_{hyp}'].abs() / no_match[hi].abs())
no_match['min_pct'] = no_match[['pct_round','pct_ceil','pct_floor','pct_interp']].min(axis=1)
unmatched = no_match[no_match['min_pct'] >= 0.05]
print(f"Unmatched (all hyp >5%): {len(unmatched)} rows")
if len(unmatched) > 0:
    print(unmatched[['auftragsnr','stpl','betrag','h1_round','min_pct']].to_string(index=False))

print("\nDone.")
