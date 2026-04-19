#!/usr/bin/env python3
"""Etappe 9a.1.A — EBM raw analysis CSVs (no report)."""
from __future__ import annotations
import math
import pickle
import re
from pathlib import Path

import numpy as np
import pandas as pd

BASE      = Path('/home/user/TMS')
DLV_PATH  = BASE / 'EBM-Papst, Mulfingen' / (
    '20260227_ebm-papst Mulfingen GmbH  Co. KG 74673 Hollenbach_Export Europa.xlsx'
)
OUT       = BASE / 'data/reports'
OUT.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# DLV loader  (same logic as s5)
# ---------------------------------------------------------------------------

def _load_sheet(fp: Path, sheetname: str) -> dict:
    raw = pd.read_excel(fp, sheet_name=sheetname, header=None)
    stpl_row = raw.iloc[5]
    col_to_stpl: dict[int, int] = {}
    for ci in range(len(stpl_row)):
        v = stpl_row.iloc[ci]
        try:
            s = int(float(str(v)))
            if 1 <= s <= 50:
                col_to_stpl[ci] = s
        except Exception:
            pass

    result: dict[str, dict[int, float]] = {}
    for idx in range(9, len(raw)):
        row = raw.iloc[idx]
        dest_raw = str(row.iloc[1]).strip() if pd.notna(row.iloc[1]) else ''
        if not dest_raw or dest_raw == 'nan':
            continue
        for part in dest_raw.split('|'):
            dk = part.strip()
            if not dk or dk == 'nan':
                continue
            if dk not in result:
                result[dk] = {}
            for ci, stpl in col_to_stpl.items():
                v = row.iloc[ci] if ci < len(row) else np.nan
                vs = str(v).strip() if pd.notna(v) else ''
                if vs in ('nan', '-', ''):
                    continue
                try:
                    price = float(vs)
                    if price > 0:
                        result[dk][stpl] = price
                except Exception:
                    pass
    return result


def _dest_match(dest_key: str, land: str, plz_norm: str) -> bool:
    for part in dest_key.split('|'):
        part = part.strip()
        m = re.match(r'^([A-Z]{2})-(.+)$', part, re.I)
        if not m:
            continue
        if m.group(1).upper() != land:
            continue
        dk_plz = re.sub(r'[\s\-]', '', m.group(2)).upper()
        min_len = min(len(plz_norm), len(dk_plz))
        if min_len >= 2 and plz_norm[:min_len] == dk_plz[:min_len]:
            return True
    return False


def lookup(land: str, plz_raw: str, ldm: float,
           freight: dict, toll: dict) -> float | None:
    if not land or pd.isna(ldm) or float(ldm) <= 0:
        return None
    plz = re.sub(r'[\s\-]', '', str(plz_raw)).upper()
    if not plz or plz == 'NAN':
        return None
    n_stpl = max(1, math.ceil(float(ldm) / 0.4))

    for dk, prices in freight.items():
        if not _dest_match(dk, land, plz):
            continue
        if not prices:
            continue
        mx = max(prices)
        n_use = min(n_stpl, mx)
        fracht = prices.get(n_use) or prices[min(k for k in prices if k >= n_use)]

        # toll: prefix match on first segment of dest_key (strip trailing space-PLZ)
        toll_amt = 0.0
        dk_prefix = dk.split(' ')[0].upper()
        for tk, tprices in toll.items():
            tk_prefix = tk.split(' ')[0].upper()
            if tk_prefix == dk_prefix or tk_prefix.startswith(dk_prefix[:6]):
                nt = min(n_use, max(tprices)) if tprices else n_use
                toll_amt = tprices.get(nt, 0.0)
                break
        return fracht + toll_amt
    return None


print("Loading DLV …")
freight_rates = _load_sheet(DLV_PATH, 'Tariffs_DE_EU')
toll_rates    = _load_sheet(DLV_PATH, 'Toll_DE_EU')
print(f"  freight dest-keys: {len(freight_rates)}, toll dest-keys: {len(toll_rates)}")

# ---------------------------------------------------------------------------
# CSV 1 — parquet coverage
# ---------------------------------------------------------------------------

print("\nCSV 1: parquet coverage …")
parquet = pd.read_parquet(BASE / 'data/parsed/dinas_pdfs.parquet')

CUSTOMERS = {
    'Sika':         r'sika',
    'EBM-Papst':    r'ebm|papst|mulfingen',
    'GEZE':         r'geze',
    'CHT':          r'cht',
    'HERMA':        r'herma',
    'Fischerwerke': r'fischer',
}

coverage_rows = []
for kunde, pat in CUSTOMERS.items():
    mask = parquet['abs_name'].str.lower().str.contains(pat, na=False)
    n = int(mask.sum())
    coverage_rows.append({'kunde': kunde, 'rows_in_parquet': n})
    print(f"  {kunde:15s}: {n:5d}")

pd.DataFrame(coverage_rows).to_csv(OUT / '9a1_parquet_coverage.csv', index=False)
print("  → 9a1_parquet_coverage.csv written")

# ---------------------------------------------------------------------------
# BI data
# ---------------------------------------------------------------------------

print("\nLoading BI data …")
with open(BASE / 'output/bi_top20_data.pkl', 'rb') as f:
    bi = pickle.load(f)['df']

ebm = bi[bi['Kunden Nr BK'] == 410844].copy()
pre = ebm[ebm['periode'] == 'PRE'].copy()
post = ebm[
    (ebm['periode'] == 'POST') &
    (ebm['Auftragsnummer'].astype(str).str.len() == 16)
].copy()

print(f"  EBM PRE rows: {len(pre)}, POST 16-digit rows: {len(post)}")

# ---------------------------------------------------------------------------
# Heuristic helper
# ---------------------------------------------------------------------------

def _grund(dlv_soll, delta, delta_pct) -> str:
    if dlv_soll is None or (isinstance(dlv_soll, float) and math.isnan(dlv_soll)):
        return 'kein DLV-Match (PLZ-Format inkompatibel)'
    if abs(delta) < 0.01:
        return 'exakt'
    if isinstance(delta_pct, float) and 3.0 <= delta_pct <= 10.0:
        return 'Diesel vermutet'
    if isinstance(delta_pct, float) and delta_pct > 10.0:
        return 'Calculator-Prüfung'
    if delta < -0.01:
        return 'Calculator-Prüfung (Dinas > DLV)'
    return 'Calculator-Prüfung'


# ---------------------------------------------------------------------------
# CSV 2 — Option A: PRE × DLV
# ---------------------------------------------------------------------------

print("\nCSV 2: Option A (PRE × DLV) …")
pre_ldm = pre[pre['Lademeter'].notna() & (pre['Lademeter'] > 0)].copy()
print(f"  PRE rows with LDM: {len(pre_ldm)}")

rows_a = []
for _, row in pre_ldm.iterrows():
    land    = str(row.get('Empfänger Land', '') or '').strip().upper()
    plz_raw = str(row.get('Empfänger PLZ',  '') or '').strip()
    ldm     = float(row['Lademeter'])
    erloese = float(row.get('Erloese', 0) or 0)
    gewicht = row.get('Tonnage (eff.)', None)
    route   = f"{land}-{plz_raw}" if plz_raw else land

    dlv_soll = lookup(land, plz_raw, ldm, freight_rates, toll_rates)

    if dlv_soll is not None and erloese > 0:
        delta     = dlv_soll - erloese
        delta_pct = delta / erloese * 100
    else:
        delta     = float('nan')
        delta_pct = float('nan')

    rows_a.append({
        'route':           route,
        'gewicht':         gewicht,
        'ldm':             ldm,
        'dinas_erloese':   erloese if erloese > 0 else float('nan'),
        'dlv_soll':        dlv_soll,
        'delta':           delta,
        'delta_pct':       delta_pct,
        'vermuteter_grund': _grund(dlv_soll, delta, delta_pct),
    })

df_a = pd.DataFrame(rows_a)
df_a.to_csv(OUT / '9a1_option_a_raw.csv', index=False, float_format='%.4f')
print(f"  → 9a1_option_a_raw.csv written ({len(df_a)} rows)")

# ---------------------------------------------------------------------------
# CSV 3 — Option B: POST × DLV
# ---------------------------------------------------------------------------

print("\nCSV 3: Option B (POST × DLV) …")
rows_b = []
for _, row in post.iterrows():
    land      = str(row.get('Empfänger Land', '') or '').strip().upper()
    plz_raw   = str(row.get('Empfänger PLZ',  '') or '').strip()
    ldm       = row.get('Lademeter', None)
    fracht    = row.get('Erlöse Fracht', None)
    gewicht   = row.get('Tonnage (eff.)', None)
    route     = str(row.get('Ausgangsrelation Business Key', '') or f"{land}-{plz_raw}").strip()

    if pd.isna(ldm) or float(ldm) <= 0:
        dlv_soll = None
    else:
        dlv_soll = lookup(land, plz_raw, float(ldm), freight_rates, toll_rates)

    fracht_f = float(fracht) if pd.notna(fracht) else float('nan')

    if dlv_soll is not None and not math.isnan(fracht_f):
        delta = fracht_f - dlv_soll
    else:
        delta = float('nan')

    rows_b.append({
        'route':             route,
        'gewicht':           gewicht,
        'ldm':               float(ldm) if pd.notna(ldm) else float('nan'),
        'ax_erloese_fracht': fracht_f,
        'dlv_soll':          dlv_soll,
        'delta':             delta,
    })

df_b = pd.DataFrame(rows_b)
df_b.to_csv(OUT / '9a1_option_b_raw.csv', index=False, float_format='%.4f')
print(f"  → 9a1_option_b_raw.csv written ({len(df_b)} rows)")

# Quick summary to stdout
print("\n=== Quick summary ===")
print("Option A:")
print(f"  rows total: {len(df_a)}")
if 'dlv_soll' in df_a.columns:
    matched = df_a['dlv_soll'].notna().sum()
    print(f"  DLV match: {matched}/{len(df_a)}")
    if matched > 0:
        valid = df_a[df_a['dlv_soll'].notna() & df_a['delta'].notna()]
        print(f"  delta stats:\n{valid['delta'].describe()}")
        print(f"  vermuteter_grund:\n{df_a['vermuteter_grund'].value_counts()}")

print("\nOption B:")
print(f"  rows total: {len(df_b)}")
matched_b = df_b['dlv_soll'].notna().sum()
print(f"  DLV match: {matched_b}/{len(df_b)}")
valid_b = df_b[df_b['delta'].notna()]
print(f"  delta < -0.01: {(valid_b['delta'] < -0.01).sum()}")
print(f"  |delta| < 0.01: {(valid_b['delta'].abs() < 0.01).sum()}")
print(f"  delta > 0.01: {(valid_b['delta'] > 0.01).sum()}")
if matched_b > 0:
    print(f"  delta stats:\n{valid_b['delta'].describe()}")

print("\nDone.")
