#!/usr/bin/env python3
"""
cluster_step2_sample.py
=======================
Schritt 2: Lade Cluster-CSV (Schritt 1) + geze_dinas_vergleich.xlsx,
sample 5 PRE + 5 POST Sendungen pro Cluster,
suche Kontroll-Sendung (gleicher Empfänger, ähnliches Gewicht).

Eingabe:  output/geze_cluster_stats.csv
          output/geze_dinas_vergleich.xlsx  (PRE + POST Sheets)
Ausgabe:  output/geze_cluster_samples.csv
"""

import math
from pathlib import Path

import numpy as np
import pandas as pd

XLSX        = Path('/home/user/TMS/output/geze_dinas_vergleich.xlsx')
CLUSTER_CSV = Path('/home/user/TMS/output/geze_cluster_stats.csv')
OUT_CSV     = Path('/home/user/TMS/output/geze_cluster_samples.csv')

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

def norm_id(v) -> str:
    try:
        return str(int(float(str(v))))
    except (TypeError, ValueError):
        return str(v).strip()

# ── Cluster-CSV laden ─────────────────────────────────────────────────────────
clusters = pd.read_csv(CLUSTER_CSV, sep=';')
print(f'Cluster geladen: {len(clusters)}')

# ── PRE + POST laden ──────────────────────────────────────────────────────────
pre  = pd.read_excel(XLSX, sheet_name='PRE Dinas Detail',  header=2)
post = pd.read_excel(XLSX, sheet_name='POST AX Detail',    header=2)

for df in (pre, post):
    df['Tonnage (eff.)'] = pd.to_numeric(df['Tonnage (eff.)'], errors='coerce')
    df['Empfänger PLZ']  = df['Empfänger PLZ'].astype(str).str.strip()
    df['Empfänger Land'] = df['Empfänger Land'].astype(str).str.strip()
    df['_gew_band']      = df['Tonnage (eff.)'].apply(gew_band)
    df['_plz_pre']       = df['Empfänger PLZ'].apply(plz_prefix)
    df['_cluster']       = df['Empfänger Land'] + '|' + df['_plz_pre'] + '|' + df['_gew_band']

# ── Soll EUR joinen (über Auftragsnummer ↔ cluster-Excel Auftrags-Nr) ─────────
try:
    cluster_xl = pd.read_excel(
        '/home/user/TMS/output/cluster_vergleich/406035_Geze_GmbH_cluster.xlsx',
        sheet_name='Geze GmbH'
    )
    alt_xl = cluster_xl[cluster_xl['System'] == 'alt'][['Auftrags-Nr', 'Soll EUR']].copy()
    alt_xl['_aid']   = alt_xl['Auftrags-Nr'].apply(norm_id)
    alt_xl['Soll EUR'] = pd.to_numeric(alt_xl['Soll EUR'], errors='coerce')
    soll_map = alt_xl.dropna(subset=['Soll EUR']).set_index('_aid')['Soll EUR'].to_dict()
    pre['_aid']     = pre['Auftragsnummer'].apply(norm_id)
    pre['Soll EUR'] = pre['_aid'].map(soll_map)
    post_xl = cluster_xl[cluster_xl['System'] == 'neu'][['Auftrags-Nr', 'Soll EUR']].copy()
    post_xl['_aid']    = post_xl['Auftrags-Nr'].apply(norm_id)
    post_xl['Soll EUR'] = pd.to_numeric(post_xl['Soll EUR'], errors='coerce')
    soll_map_post = post_xl.dropna(subset=['Soll EUR']).set_index('_aid')['Soll EUR'].to_dict()
    post['_aid']     = post['Auftragsnummer'].apply(norm_id)
    post['Soll EUR'] = post['_aid'].map(soll_map_post)
    print(f'Soll EUR gematcht: PRE {pre["Soll EUR"].notna().sum()}/{len(pre)}, '
          f'POST {post["Soll EUR"].notna().sum()}/{len(post)}')
except Exception as e:
    print(f'Soll EUR Join fehlgeschlagen: {e}')
    pre['Soll EUR']  = np.nan
    post['Soll EUR'] = np.nan

# ── Numerische NK-Spalten sichern ─────────────────────────────────────────────
PRE_NK  = ['Dinas Fracht', 'Dinas Diesel', 'Dinas Maut/SSD', 'Dinas Ausfuhr',
           'Dinas Verzollung', 'Dinas Zoll Duty', 'Dinas Zollbetrag',
           'Dinas Sulphur', 'Dinas Nebenkostenpausch.', 'Dinas Redebit',
           'Dinas Sonstige', 'Dinas Gesamt']
POST_NK = ['AX Fracht', 'AX Diesel', 'AX Maut', 'AX Nebengebühr',
           'AX Lademittel', 'AX Peak', 'AX EUST/Zoll', 'AX Versicherung',
           'AX Gesamt']

for col in PRE_NK:
    if col in pre.columns:
        pre[col] = pd.to_numeric(pre[col], errors='coerce')
for col in POST_NK:
    if col in post.columns:
        post[col] = pd.to_numeric(post[col], errors='coerce')

# ── Kontroll-Sendung finden ────────────────────────────────────────────────────
def find_kontroll(pre_rows: pd.DataFrame,
                  post_rows: pd.DataFrame) -> tuple[int | None, int | None]:
    """
    Gibt (pre_idx, post_idx) des besten PRE-POST-Paars zurück
    (gleicher Empfänger-Name-Prefix + minimale Tonnage-Differenz).
    Gibt (None, None) zurück wenn kein Paar gefunden.
    """
    if pre_rows.empty or post_rows.empty:
        return None, None

    best_pre_idx, best_post_idx, best_diff = None, None, float('inf')

    for pi, pr in pre_rows.iterrows():
        pr_name = str(pr.get('Empfänger Name', ''))[:12]
        pr_kg   = pr.get('Tonnage (eff.)')
        if pd.isna(pr_kg):
            continue

        # Bevorzuge gleichen Empfänger, fallback auf alle POST-Zeilen
        same = post_rows[
            post_rows['Empfänger Name'].astype(str).str[:12] == pr_name
        ]
        candidates = same if not same.empty else post_rows

        for oi, po in candidates.iterrows():
            po_kg = po.get('Tonnage (eff.)')
            if pd.isna(po_kg):
                continue
            diff = abs(float(pr_kg) - float(po_kg))
            if diff < best_diff:
                best_diff          = diff
                best_pre_idx       = pi
                best_post_idx      = oi

    return best_pre_idx, best_post_idx

# ── Sampling pro Cluster ───────────────────────────────────────────────────────
rows_out = []

PRE_META  = ['Rechnungsnummer', 'Auftragsnummer', 'Leistungsdatum',
             'Empfänger Name', 'Empfänger PLZ', 'Empfänger Land',
             'Tonnage (eff.)', 'Soll EUR']
POST_META = ['Rechnungsnummer', 'Auftragsnummer', 'Leistungsdatum',
             'Empfänger Name', 'Empfänger PLZ', 'Empfänger Land',
             'Tonnage (eff.)', 'Soll EUR']

for _, cl in clusters.iterrows():
    ckey = cl['_cluster']

    pre_rows  = pre[pre['_cluster']   == ckey].head(5)
    post_rows = post[post['_cluster'] == ckey].head(5)

    ctrl_pre_idx, ctrl_post_idx = find_kontroll(
        pre[pre['_cluster'] == ckey],
        post[post['_cluster'] == ckey]
    )

    # PRE rows
    for _, pr in pre_rows.iterrows():
        row = {'_cluster': ckey, '_system': 'PRE', '_is_kontroll': 0}
        row['_abw_grund'] = cl.get('abw_grund', '')
        for c in PRE_META:
            row[c] = pr.get(c)
        for c in PRE_NK:
            row[c] = pr.get(c) if c in pre.columns else np.nan
        rows_out.append(row)

    # POST rows
    for _, po in post_rows.iterrows():
        row = {'_cluster': ckey, '_system': 'POST', '_is_kontroll': 0}
        row['_abw_grund'] = cl.get('abw_grund', '')
        for c in POST_META:
            row[c] = po.get(c)
        for c in POST_NK:
            row[c] = po.get(c) if c in post.columns else np.nan
        rows_out.append(row)

    # Kontroll-Sendung (PRE + POST, separat markiert)
    if ctrl_pre_idx is not None:
        pr = pre.loc[ctrl_pre_idx]
        row = {'_cluster': ckey, '_system': 'KONTROLL_PRE', '_is_kontroll': 1}
        row['_abw_grund'] = cl.get('abw_grund', '')
        for c in PRE_META:
            row[c] = pr.get(c)
        for c in PRE_NK:
            row[c] = pr.get(c) if c in pre.columns else np.nan
        rows_out.append(row)

    if ctrl_post_idx is not None:
        po = post.loc[ctrl_post_idx]
        row = {'_cluster': ckey, '_system': 'KONTROLL_POST', '_is_kontroll': 1}
        row['_abw_grund'] = cl.get('abw_grund', '')
        for c in POST_META:
            row[c] = po.get(c)
        for c in POST_NK:
            row[c] = po.get(c) if c in post.columns else np.nan
        rows_out.append(row)

# ── Speichern ─────────────────────────────────────────────────────────────────
out_df = pd.DataFrame(rows_out)
out_df.to_csv(OUT_CSV, index=False, sep=';', float_format='%.4f')

print(f'\nSamples gespeichert: {len(out_df)} Zeilen in {OUT_CSV}')
print(f'  PRE-Zeilen:           {(out_df["_system"] == "PRE").sum()}')
print(f'  POST-Zeilen:          {(out_df["_system"] == "POST").sum()}')
print(f'  Kontroll-PRE-Zeilen:  {(out_df["_system"] == "KONTROLL_PRE").sum()}')
print(f'  Kontroll-POST-Zeilen: {(out_df["_system"] == "KONTROLL_POST").sum()}')
