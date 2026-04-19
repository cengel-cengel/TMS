#!/usr/bin/env python3
"""Etappe 9a.1.C — Option A retry with IE county→Eircode mapping."""
from __future__ import annotations
import math
import pickle
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

BASE     = Path('/home/user/TMS')
DLV_PATH = BASE / 'EBM-Papst, Mulfingen' / (
    '20260227_ebm-papst Mulfingen GmbH  Co. KG 74673 Hollenbach_Export Europa.xlsx'
)
OUT = BASE / 'data/reports'
sys.path.insert(0, str(BASE / 'src'))

from tms.matching.normalize_plz import normalize_ie_county_for_dlv

# ---------------------------------------------------------------------------
# DLV loader (same as 9a.1.A)
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
            result.setdefault(dk, {})
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
        if n_use in prices:
            fracht = prices[n_use]
        else:
            higher = {k: v for k, v in prices.items() if k >= n_use}
            fracht = prices[min(higher)] if higher else prices[mx]
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


def _normalize_plz_for_dlv(land: str, plz_raw: str) -> str:
    """Normalize PLZ for DLV lookup. For IE county codes apply mapping."""
    plz = str(plz_raw).strip().upper()
    if land == 'IE':
        mapped = normalize_ie_county_for_dlv(plz)
        if mapped is not None:
            return mapped
        # If mapping returned None (ambiguous/no coverage) keep original
        # so the lookup will also return None.
        return plz
    return plz


def _grund(dlv_soll, delta, delta_pct, plz_mapped: bool) -> str:
    if dlv_soll is None or (isinstance(dlv_soll, float) and math.isnan(dlv_soll)):
        return 'kein DLV-Match (PLZ-Format inkompatibel)'
    if not plz_mapped:
        return 'kein DLV-Match (County ambiguous/kein DLV-Ziel)'
    if abs(delta) < 0.01:
        return 'exakt'
    if isinstance(delta_pct, float) and -10.0 <= delta_pct <= -3.0:
        return 'Diesel vermutet'
    if isinstance(delta_pct, float) and delta_pct < -10.0:
        return 'Calculator-Prüfung (Dinas > DLV + Diesel)'
    if delta > 0.01:
        return 'Calculator-Prüfung (Dinas unter DLV)'
    return 'Calculator-Prüfung'


print("Loading DLV …")
freight_rates = _load_sheet(DLV_PATH, 'Tariffs_DE_EU')
toll_rates    = _load_sheet(DLV_PATH, 'Toll_DE_EU')

print("Loading BI data …")
with open(BASE / 'output/bi_top20_data.pkl', 'rb') as f:
    bi = pickle.load(f)['df']
ebm = bi[bi['Kunden Nr BK'] == 410844]
pre = ebm[ebm['periode'] == 'PRE'].copy()
pre_ldm = pre[pre['Lademeter'].notna() & (pre['Lademeter'] > 0)].copy()
print(f"PRE rows with LDM: {len(pre_ldm)}")

rows = []
for _, row in pre_ldm.iterrows():
    land    = str(row.get('Empfänger Land', '') or '').strip().upper()
    plz_raw = str(row.get('Empfänger PLZ',  '') or '').strip()
    ldm     = float(row['Lademeter'])
    erloese = float(row.get('Erloese', 0) or 0)
    gewicht = row.get('Tonnage (eff.)', None)

    plz_norm  = _normalize_plz_for_dlv(land, plz_raw)
    plz_was_mapped = (land == 'IE' and plz_norm != plz_raw.upper())
    route = f"{land}-{plz_raw}"

    dlv_soll = lookup(land, plz_norm, ldm, freight_rates, toll_rates)

    if dlv_soll is not None and erloese > 0:
        delta     = dlv_soll - erloese
        delta_pct = delta / erloese * 100
    else:
        delta = delta_pct = float('nan')

    rows.append({
        'route':             route,
        'plz_dinas':         plz_raw,
        'plz_dlv_mapped':    plz_norm,
        'gewicht':           gewicht,
        'ldm':               ldm,
        'dinas_erloese':     erloese if erloese > 0 else float('nan'),
        'dlv_soll':          dlv_soll,
        'delta':             delta,
        'delta_pct':         delta_pct,
        'vermuteter_grund':  _grund(dlv_soll, delta, delta_pct, plz_was_mapped),
    })

df = pd.DataFrame(rows)
out_path = OUT / '9a1_option_a_raw_v2.csv'
df.to_csv(out_path, index=False, float_format='%.4f')
print(f"Written: {out_path} ({len(df)} rows)")

print("\n=== Summary ===")
print("vermuteter_grund distribution:")
print(df['vermuteter_grund'].value_counts())
print()

matched = df[df['dlv_soll'].notna()]
print(f"DLV matched: {len(matched)}/{len(df)}")
if len(matched):
    valid = matched[matched['delta'].notna()]
    print(f"delta stats:\n{valid['delta'].describe()}")
    print()
    print("Top-3 by |delta|:")
    top3 = valid.nlargest(3, 'delta').append(valid.nsmallest(3, 'delta')).drop_duplicates()
    top3 = valid.reindex(valid['delta'].abs().nlargest(3).index)
    print(top3[['route','plz_dlv_mapped','ldm','dinas_erloese','dlv_soll','delta','delta_pct','vermuteter_grund']].to_string())
