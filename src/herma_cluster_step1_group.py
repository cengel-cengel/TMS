#!/usr/bin/env python3
"""
herma_cluster_step1_group.py
============================
Schritt 1: Lädt herma_vergleich_komplett.xlsx (PRE + POST),
bildet Cluster (Land + PLZ-Prefix + Gew.band), identifiziert
Unterfakturierung (Ø AX Gesamt < Ø Dinas Gesamt).

Ausgabe: output/herma_cluster_stats.csv
"""

from pathlib import Path
import numpy as np
import pandas as pd

KOMPLETT = Path('/home/user/TMS/output/herma_vergleich_komplett.xlsx')
OUT_CSV  = Path('/home/user/TMS/output/herma_cluster_stats.csv')

def plz_prefix(plz, n: int = 2) -> str:
    return str(plz).strip()[:n]

# ── Laden ─────────────────────────────────────────────────────────────────────
pre  = pd.read_excel(KOMPLETT, sheet_name='PRE Dinas Detail', header=0)
post = pd.read_excel(KOMPLETT, sheet_name='POST AX Detail',   header=0)

for df in (pre, post):
    df['Tonnage kg'] = pd.to_numeric(df['Tonnage kg'], errors='coerce')
    df['PLZ']        = df['PLZ'].astype(str).str.strip()
    df['Land']       = df['Land'].astype(str).str.strip()
    df['_plz_pre']   = df['PLZ'].apply(plz_prefix)
    df['_cluster']   = df['Land'] + '|' + df['_plz_pre'] + '|' + df['Gew.band'].astype(str)

pre['Dinas Gesamt'] = pd.to_numeric(pre['Dinas Gesamt'], errors='coerce')
pre['Dinas Fracht'] = pd.to_numeric(pre['Dinas Fracht'], errors='coerce')
pre['Diesel_pre']   = pd.to_numeric(pre['Diesel'],       errors='coerce')
pre['Maut_pre']     = pd.to_numeric(pre['Maut/SSD'],     errors='coerce')
pre['SOLL EUR']     = pd.to_numeric(pre['SOLL EUR'],     errors='coerce')

post['AX Gesamt']   = pd.to_numeric(post['AX Gesamt'],  errors='coerce')
post['AX Fracht']   = pd.to_numeric(post['AX Fracht'],  errors='coerce')
post['Diesel_post'] = pd.to_numeric(post['Diesel'],      errors='coerce')
post['Maut_post']   = pd.to_numeric(post['Maut'],        errors='coerce')
post['Neben_post']  = pd.to_numeric(post['Neben'],       errors='coerce')
post['SOLL EUR']    = pd.to_numeric(post['SOLL EUR'],    errors='coerce')

# ── Cluster-Statistiken ────────────────────────────────────────────────────────
pre_agg = pre.groupby('_cluster').agg(
    n_pre          =('Dinas Gesamt', 'count'),
    avg_dinas_ges  =('Dinas Gesamt', 'mean'),
    avg_dinas_fr   =('Dinas Fracht', 'mean'),
    avg_dinas_di   =('Diesel_pre',   'mean'),
    avg_dinas_maut =('Maut_pre',     'mean'),
    avg_soll_pre   =('SOLL EUR',     'mean'),
).reset_index()

post_agg = post.groupby('_cluster').agg(
    n_post       =('AX Gesamt',   'count'),
    avg_ax_ges   =('AX Gesamt',   'mean'),
    avg_ax_fr    =('AX Fracht',   'mean'),
    avg_ax_di    =('Diesel_post', 'mean'),
    avg_ax_maut  =('Maut_post',   'mean'),
    avg_ax_neben =('Neben_post',  'mean'),
    avg_soll_post=('SOLL EUR',    'mean'),
).reset_index()

stats = pre_agg.merge(post_agg, on='_cluster', how='inner')

# Nur Unterfakturierung
stats = stats[stats['avg_ax_ges'] < stats['avg_dinas_ges']].copy()

stats['delta_ges']      = stats['avg_ax_ges'] - stats['avg_dinas_ges']
stats['delta_pct']      = stats['delta_ges']  / stats['avg_dinas_ges'].replace(0, np.nan) * 100
stats['delta_fr']       = stats['avg_ax_fr']  - stats['avg_dinas_fr']
stats['delta_di']       = stats['avg_ax_di']  - stats['avg_dinas_di']
stats['delta_maut']     = stats['avg_ax_maut']- stats['avg_dinas_maut']
stats['total_loss_est'] = stats['delta_ges']  * stats['n_post']

def abw_grund(row):
    deltas = {'Fracht': row['delta_fr'],
              'Diesel': row['delta_di'],
              'Maut':   row['delta_maut']}
    neg = {k: v for k, v in deltas.items() if v < -0.5}
    if not neg:
        return 'n/a'
    total = sum(neg.values())
    parts = sorted(neg.items(), key=lambda x: x[1])
    return 'Hauptursache: ' + ', '.join(
        f'{k}: {v/total*100:+.0f}%' for k, v in parts[:2])

stats['abw_grund'] = stats.apply(abw_grund, axis=1)

parts = stats['_cluster'].str.split('|', expand=True)
stats['Land']     = parts[0]
stats['PLZ_pre']  = parts[1]
stats['Gew_band'] = parts[2]

stats = stats.sort_values('total_loss_est').reset_index(drop=True)

stats.to_csv(OUT_CSV, index=False, sep=';', float_format='%.4f')

print(f'Cluster mit Unterfakturierung: {len(stats)}')
print(f'Sigma geschätzter Verlust:     {stats["total_loss_est"].sum():,.0f} EUR')
print()
print(stats[['Land','PLZ_pre','Gew_band','n_pre','n_post',
             'avg_dinas_ges','avg_ax_ges','delta_pct','abw_grund']].round(2).to_string(index=False))
