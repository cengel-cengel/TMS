#!/usr/bin/env python3
"""Etappe 9a.1.F.2b — EBM + Dinas taxonomy decomposition + identity check.

Outputs:
  data/reports/9a1f2b_dinas_taxonomy.csv
  data/reports/9a1f2b_ax_ebm_taxonomy.csv

Identity-check columns per row:
  sum_kategorien    = sum of all 11 taxonomy keys
  identitaet_delta  = GESAMT − sum_kategorien
  identitaet_ok     = |delta| < 0.01 EUR
  coverage_flag     = 'full'  (fracht non-null)
                    | 'partial' (only sendungssumme, no component breakdown)
                    | 'gesamt_zero' (sendungssumme=0, line-item entry)
"""
from __future__ import annotations
import pickle
import sys
from pathlib import Path

import pandas as pd

BASE = Path('/home/user/TMS')
sys.path.insert(0, str(BASE / 'src'))

from tms.normalize.normalize_position import (  # noqa: E402
    ALL_TAXONOMY_KEYS,
    build_ax_taxonomy_row,
    build_dinas_taxonomy_row,
)

OUT = BASE / 'data/reports'

# ---------------------------------------------------------------------------
# Schritt 1 — Dinas taxonomy (all 5533 rows)
# ---------------------------------------------------------------------------
print("Loading dinas_pdfs.parquet …")
dinas = pd.read_parquet(BASE / 'data/parsed/dinas_pdfs.parquet')
print(f"Rows: {len(dinas)}")

dinas_rows = []
for _, row in dinas.iterrows():
    tax = build_dinas_taxonomy_row(row)
    sum_kat = sum(tax[k] for k in ALL_TAXONOMY_KEYS)
    gesamt  = tax['GESAMT']
    delta   = (gesamt - sum_kat) if (gesamt == gesamt) else float('nan')
    ok      = (abs(delta) < 0.01) if (delta == delta) else False

    # Coverage flag — explains WHY identity might fail
    fracht_null = row['fracht'] != row['fracht']  # isnan
    if gesamt == 0.0:
        flag = 'gesamt_zero'
    elif fracht_null:
        flag = 'partial'    # parser captured sendungssumme only
    else:
        flag = 'full'       # all components extracted

    dinas_rows.append({
        'rechnung_nr':    row.get('rechnung_nr', ''),
        'sendungsnummer': row.get('sendungsnummer', ''),
        'abs_name':       row.get('abs_name', ''),
        'leistung_date':  row.get('leistung_date', ''),
        'empf_land':      row.get('empf_land', ''),
        'empf_plz':       row.get('empf_plz', ''),
        **{k: tax[k] for k in ALL_TAXONOMY_KEYS},
        'GESAMT':             gesamt,
        'sum_kategorien':     sum_kat,
        'identitaet_delta':   delta,
        'identitaet_ok':      ok,
        'coverage_flag':      flag,
    })

df_dinas = pd.DataFrame(dinas_rows)
dinas_path = OUT / '9a1f2b_dinas_taxonomy.csv'
df_dinas.to_csv(dinas_path, index=False, float_format='%.4f')
print(f"Written: {dinas_path}")

# Sanity breakdown
n_total_d    = len(df_dinas)
n_full       = (df_dinas['coverage_flag'] == 'full').sum()
n_partial    = (df_dinas['coverage_flag'] == 'partial').sum()
n_gzero      = (df_dinas['coverage_flag'] == 'gesamt_zero').sum()
n_ok_full    = int(df_dinas[df_dinas['coverage_flag'] == 'full']['identitaet_ok'].sum())
n_broken_full= n_full - n_ok_full
max_delta_d  = df_dinas[df_dinas['coverage_flag'] == 'full']['identitaet_delta'].abs().max()

print(f"\n=== Dinas Sanity ===")
print(f"total={n_total_d}  full={n_full}  partial={n_partial}  gesamt_zero={n_gzero}")
print(f"[full rows] ok={n_ok_full}  broken={n_broken_full}  max|delta|={max_delta_d:.4f}")
if n_broken_full > 0:
    broken = df_dinas[
        (df_dinas['coverage_flag'] == 'full') & ~df_dinas['identitaet_ok']
    ].nlargest(3, 'identitaet_delta')
    print("Top-3 broken (full coverage):")
    print(broken[['rechnung_nr','empf_land','GESAMT','sum_kategorien','identitaet_delta']].to_string(index=False))

# ---------------------------------------------------------------------------
# Schritt 2 — AX-EBM taxonomy (POST rows)
# ---------------------------------------------------------------------------
print("\nLoading bi_top20_data.pkl …")
with open(BASE / 'output/bi_top20_data.pkl', 'rb') as f:
    bi = pickle.load(f)['df']

ebm_post = bi[(bi['Kunden Nr BK'] == 410844) & (bi['periode'] == 'POST')].copy()
print(f"EBM POST rows: {len(ebm_post)}")

ax_rows = []
for _, row in ebm_post.iterrows():
    tax = build_ax_taxonomy_row(row)
    sum_kat = sum(tax[k] for k in ALL_TAXONOMY_KEYS)
    gesamt  = tax['GESAMT']
    delta   = (gesamt - sum_kat) if (gesamt == gesamt) else float('nan')
    ok      = (abs(delta) < 0.01) if (delta == delta) else False
    ax_rows.append({
        'leistungsdatum': row.get('Leistungsdatum', ''),
        'auftragsnummer': row.get('Auftragsnummer', ''),
        'kunde':          row.get('Kunden Name', ''),
        'empf_land':      row.get('Empfänger Land', ''),
        'empf_plz':       row.get('Empfänger PLZ', ''),
        **{k: tax[k] for k in ALL_TAXONOMY_KEYS},
        'GESAMT':           gesamt,
        'sum_kategorien':   sum_kat,
        'identitaet_delta': delta,
        'identitaet_ok':    ok,
    })

df_ax = pd.DataFrame(ax_rows)
ax_path = OUT / '9a1f2b_ax_ebm_taxonomy.csv'
df_ax.to_csv(ax_path, index=False, float_format='%.4f')
print(f"Written: {ax_path}")

n_total_a  = len(df_ax)
n_ok_a     = int(df_ax['identitaet_ok'].sum())
n_broken_a = n_total_a - n_ok_a
max_delta_a = df_ax['identitaet_delta'].abs().max()

print(f"\n=== AX-EBM Sanity ===")
print(f"n_total={n_total_a}  n_ok={n_ok_a}  n_broken={n_broken_a}  max|delta|={max_delta_a:.4f}")
if n_broken_a > 0:
    broken_a = df_ax[~df_ax['identitaet_ok']].nlargest(3, 'identitaet_delta')
    print("Top-3 broken:")
    print(broken_a[['auftragsnummer','empf_land','GESAMT','sum_kategorien','identitaet_delta']].to_string(index=False))

print("\nDone.")
