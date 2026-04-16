#!/usr/bin/env python3
"""
cluster_step1_group.py
======================
Schritt 1: Lade geze_dinas_vergleich.xlsx, bilde Cluster,
speichere Cluster-Statistiken als CSV.

Ausgabe: output/geze_cluster_stats.csv
"""

import math
from pathlib import Path

import numpy as np
import pandas as pd

XLSX    = Path('/home/user/TMS/output/geze_dinas_vergleich.xlsx')
OUT_CSV = Path('/home/user/TMS/output/geze_cluster_stats.csv')

BANDS_KG = [50, 100, 150, 200, 250, 300, 500, 750, 1000, 2000, 3000]

def gew_band(kg) -> str:
    try:
        kg = float(kg)
    except (TypeError, ValueError):
        return '?'
    if math.isnan(kg) or kg <= 0:
        return '?'
    for b in BANDS_KG:
        if kg <= b:
            return f'bis {b}kg'
    return 'über 3000kg'

def plz_prefix(plz, n: int = 2) -> str:
    return str(plz).strip()[:n]

# ── Laden ─────────────────────────────────────────────────────────────────────
pre  = pd.read_excel(XLSX, sheet_name='PRE Dinas Detail',  header=2)
post = pd.read_excel(XLSX, sheet_name='POST AX Detail',    header=2)

for df in (pre, post):
    df['Tonnage (eff.)'] = pd.to_numeric(df['Tonnage (eff.)'], errors='coerce')
    df['Empfänger PLZ']  = df['Empfänger PLZ'].astype(str).str.strip()
    df['Empfänger Land'] = df['Empfänger Land'].astype(str).str.strip()
    df['_gew_band']      = df['Tonnage (eff.)'].apply(gew_band)
    df['_plz_pre']       = df['Empfänger PLZ'].apply(plz_prefix)
    df['_cluster']       = df['Empfänger Land'] + '|' + df['_plz_pre'] + '|' + df['_gew_band']

pre['Dinas Gesamt'] = pd.to_numeric(pre['Dinas Gesamt'], errors='coerce')
pre['Dinas Fracht'] = pd.to_numeric(pre['Dinas Fracht'], errors='coerce')
pre['Dinas Diesel'] = pd.to_numeric(pre.get('Dinas Diesel', 0), errors='coerce')
pre['Dinas Maut/SSD'] = pd.to_numeric(pre.get('Dinas Maut/SSD', 0), errors='coerce')

post['AX Gesamt']     = pd.to_numeric(post['AX Gesamt'],     errors='coerce')
post['AX Fracht']     = pd.to_numeric(post['AX Fracht'],     errors='coerce')
post['AX Diesel']     = pd.to_numeric(post['AX Diesel'],     errors='coerce')
post['AX Maut']       = pd.to_numeric(post['AX Maut'],       errors='coerce')
post['AX Nebengebühr']= pd.to_numeric(post['AX Nebengebühr'],errors='coerce')

# ── Cluster-Statistiken ────────────────────────────────────────────────────────
pre_agg = pre.groupby('_cluster').agg(
    n_pre         =('Dinas Gesamt', 'count'),
    avg_dinas_ges =('Dinas Gesamt', 'mean'),
    avg_dinas_fr  =('Dinas Fracht', 'mean'),
    avg_dinas_di  =('Dinas Diesel', 'mean'),
    avg_dinas_maut=('Dinas Maut/SSD', 'mean'),
).reset_index()

post_agg = post.groupby('_cluster').agg(
    n_post      =('AX Gesamt',     'count'),
    avg_ax_ges  =('AX Gesamt',     'mean'),
    avg_ax_fr   =('AX Fracht',     'mean'),
    avg_ax_di   =('AX Diesel',     'mean'),
    avg_ax_maut =('AX Maut',       'mean'),
    avg_ax_neben=('AX Nebengebühr','mean'),
).reset_index()

stats = pre_agg.merge(post_agg, on='_cluster', how='inner')

# Nur Unterfakturierung: Ø AX Gesamt < Ø Dinas Gesamt
stats = stats[stats['avg_ax_ges'] < stats['avg_dinas_ges']].copy()

stats['delta_ges']      = stats['avg_ax_ges']  - stats['avg_dinas_ges']
stats['delta_pct']      = stats['delta_ges']   / stats['avg_dinas_ges'].replace(0, np.nan) * 100
stats['delta_fr']       = stats['avg_ax_fr']   - stats['avg_dinas_fr']
stats['delta_di']       = stats['avg_ax_di']   - stats['avg_dinas_di']
stats['delta_maut']     = stats['avg_ax_maut'] - stats['avg_dinas_maut']
stats['total_loss_est'] = stats['delta_ges']   * stats['n_post']

# Abweichungsgrund: größte NK-Komponente der Differenz
def abw_grund(row):
    deltas = {
        'Fracht':   row['delta_fr'],
        'Diesel':   row['delta_di'],
        'Maut/SSD': row['delta_maut'],
    }
    # Nur negative Deltas (Unterfakturierung)
    neg = {k: v for k, v in deltas.items() if v < -0.5}
    if not neg:
        return 'n/a'
    total_neg = sum(neg.values())
    parts = sorted(neg.items(), key=lambda x: x[1])
    lines = [f'{k}: {v/total_neg*100:+.0f}%' for k, v in parts]
    return 'Hauptursache: ' + ', '.join(lines[:2])

stats['abw_grund'] = stats.apply(abw_grund, axis=1)

# Land + PLZ + Band aus Key
parts = stats['_cluster'].str.split('|', expand=True)
stats['Land']     = parts[0]
stats['PLZ_pre']  = parts[1]
stats['Gew_band'] = parts[2]

stats = stats.sort_values('total_loss_est').reset_index(drop=True)

# ── Speichern ─────────────────────────────────────────────────────────────────
out_cols = ['_cluster', 'Land', 'PLZ_pre', 'Gew_band',
            'n_pre', 'n_post',
            'avg_dinas_ges', 'avg_dinas_fr', 'avg_dinas_di', 'avg_dinas_maut',
            'avg_ax_ges',    'avg_ax_fr',    'avg_ax_di',    'avg_ax_maut', 'avg_ax_neben',
            'delta_ges', 'delta_pct', 'delta_fr', 'delta_di', 'delta_maut',
            'total_loss_est', 'abw_grund']

stats[out_cols].to_csv(OUT_CSV, index=False, sep=';', float_format='%.4f')

print(f'Cluster mit Unterfakturierung: {len(stats)}')
print(f'Sigma geschätzter Verlust:     {stats["total_loss_est"].sum():,.0f} EUR')
print(f'Gespeichert: {OUT_CSV}')
print()
print(stats[['Land','PLZ_pre','Gew_band','n_pre','n_post',
             'avg_dinas_ges','avg_ax_ges','delta_pct','abw_grund']].round(2).to_string(index=False))
