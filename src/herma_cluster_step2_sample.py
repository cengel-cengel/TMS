#!/usr/bin/env python3
"""
herma_cluster_step2_sample.py
==============================
Schritt 2: Samplet 5 PRE + 5 POST Sendungen pro Cluster,
sucht Kontroll-Sendung (gleiche PLZ + ähnliches Gewicht).

Eingabe:  output/herma_cluster_stats.csv
          output/herma_vergleich_komplett.xlsx
Ausgabe:  output/herma_cluster_samples.csv
"""

from pathlib import Path
import numpy as np
import pandas as pd

KOMPLETT    = Path('/home/user/TMS/output/herma_vergleich_komplett.xlsx')
CLUSTER_CSV = Path('/home/user/TMS/output/herma_cluster_stats.csv')
OUT_CSV     = Path('/home/user/TMS/output/herma_cluster_samples.csv')

def plz_prefix(plz, n: int = 2) -> str:
    return str(plz).strip()[:n]

# ── Laden ─────────────────────────────────────────────────────────────────────
clusters = pd.read_csv(CLUSTER_CSV, sep=';')

pre  = pd.read_excel(KOMPLETT, sheet_name='PRE Dinas Detail', header=0)
post = pd.read_excel(KOMPLETT, sheet_name='POST AX Detail',   header=0)

for df in (pre, post):
    df['Tonnage kg'] = pd.to_numeric(df['Tonnage kg'], errors='coerce')
    df['PLZ']        = df['PLZ'].astype(str).str.strip()
    df['Land']       = df['Land'].astype(str).str.strip()
    df['_plz_pre']   = df['PLZ'].apply(plz_prefix)
    df['_cluster']   = df['Land'] + '|' + df['_plz_pre'] + '|' + df['Gew.band'].astype(str)

# NK-Spalten numerisch
PRE_NK  = ['Dinas Fracht', 'Diesel', 'Maut/SSD', 'Ausfuhr',
           'Verzoll.', 'Zoll Bet.', 'Sulphur', 'NK Pausch',
           'Sonstige', 'Dinas Gesamt']
POST_NK = ['AX Fracht', 'Diesel', 'Maut', 'Neben', 'Versich.', 'AX Gesamt']

for c in PRE_NK:
    if c in pre.columns:
        pre[c] = pd.to_numeric(pre[c], errors='coerce')
for c in POST_NK:
    if c in post.columns:
        post[c] = pd.to_numeric(post[c], errors='coerce')

for df in (pre, post):
    df['SOLL EUR'] = pd.to_numeric(df['SOLL EUR'], errors='coerce')

# ── Kontroll-Sendung ──────────────────────────────────────────────────────────
def find_kontroll(pre_rows, post_rows):
    """Bestes PRE-POST-Paar: gleiche PLZ (Prefix) + min. Tonnage-Differenz."""
    if pre_rows.empty or post_rows.empty:
        return None, None
    best_pi, best_oi, best_diff = None, None, float('inf')
    for pi, pr in pre_rows.iterrows():
        pr_plz = str(pr.get('PLZ', ''))[:3]
        pr_kg  = pr.get('Tonnage kg')
        if pd.isna(pr_kg):
            continue
        same_plz = post_rows[post_rows['PLZ'].astype(str).str[:3] == pr_plz]
        cands    = same_plz if not same_plz.empty else post_rows
        for oi, po in cands.iterrows():
            po_kg = po.get('Tonnage kg')
            if pd.isna(po_kg):
                continue
            diff = abs(float(pr_kg) - float(po_kg))
            if diff < best_diff:
                best_diff, best_pi, best_oi = diff, pi, oi
    return best_pi, best_oi

# ── Sampling ──────────────────────────────────────────────────────────────────
PRE_META  = ['RN', 'Auftrag', 'Leistungsdatum', 'Land', 'PLZ', 'Zone',
             'Gew.band', 'Tonnage kg', 'LDM', 'SOLL EUR']
POST_META = ['RN', 'Auftrag', 'Land', 'PLZ', 'Zone',
             'Gew.band', 'Tonnage kg', 'LDM', 'SOLL EUR']

rows_out = []

for _, cl in clusters.iterrows():
    ckey = cl['_cluster']
    abw  = cl.get('abw_grund', '')

    pre_all  = pre[pre['_cluster']   == ckey]
    post_all = post[post['_cluster'] == ckey]
    pre_s    = pre_all.head(5)
    post_s   = post_all.head(5)

    ctrl_pi, ctrl_oi = find_kontroll(pre_all, post_all)

    def make_row(system, src, meta_cols, nk_cols, is_kontroll=0):
        row = {'_cluster': ckey, '_system': system,
               '_is_kontroll': is_kontroll, '_abw_grund': abw}
        for c in meta_cols:
            row[c] = src.get(c)
        for c in nk_cols:
            row[c] = src.get(c) if c in src.index else np.nan
        return row

    for _, pr in pre_s.iterrows():
        rows_out.append(make_row('PRE',  pr, PRE_META,  PRE_NK))
    for _, po in post_s.iterrows():
        rows_out.append(make_row('POST', po, POST_META, POST_NK))
    if ctrl_pi is not None:
        rows_out.append(make_row('KONTROLL_PRE',  pre.loc[ctrl_pi],
                                 PRE_META, PRE_NK,  is_kontroll=1))
    if ctrl_oi is not None:
        rows_out.append(make_row('KONTROLL_POST', post.loc[ctrl_oi],
                                 POST_META, POST_NK, is_kontroll=1))

out_df = pd.DataFrame(rows_out)
out_df.to_csv(OUT_CSV, index=False, sep=';', float_format='%.4f')

print(f'Samples: {len(out_df)} Zeilen')
print(f'  PRE:           {(out_df["_system"]=="PRE").sum()}')
print(f'  POST:          {(out_df["_system"]=="POST").sum()}')
print(f'  Kontroll PRE:  {(out_df["_system"]=="KONTROLL_PRE").sum()}')
print(f'  Kontroll POST: {(out_df["_system"]=="KONTROLL_POST").sum()}')
print(f'Gespeichert: {OUT_CSV}')
