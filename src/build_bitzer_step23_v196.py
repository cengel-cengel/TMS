#!/usr/bin/env python3
"""
Bitzer Kühlmaschinenbau GmbH — Step 2+3 Pipeline v1.9.6
=========================================================
Outputs output/bitzer_step23_results_v196.pkl

Step 2: Pool-Aufbau
  - BI filter: KNR=406345, Erlöse Fracht > 0
  - ZGI sub-row Tonnage-Substitution (18 Rows mit Tonnage=0)
  - BitzCalculator auf alle beurteilbaren Rows
  - DE Inbound + sonstige scope-out-Rows dokumentieren

Step 3: 4-Muster-Klassifikation
  fp = (Erlöse_Fracht - DLV_Soll) / DLV_Soll
  M1:     |fp| <= 5%
  M2:     fp < -5%   (Erlöse unter DLV = Bitzer günstiger)
  M_over: fp > +5%   (Erlöse über DLV = Bitzer teuerer)
"""
from __future__ import annotations

import math
import pickle
import sys
from decimal import Decimal
from pathlib import Path

import pandas as pd

BASE = Path('/home/user/TMS')
sys.path.insert(0, str(BASE / 'src'))

from tms.tariff.calculators.bitzer import BitzCalculator

BI_PKL  = BASE / 'output/bi_top20_data.pkl'
OUT_PKL = BASE / 'output/bitzer_step23_results_v196.pkl'
KNR     = 406345

# ---------------------------------------------------------------------------
# Load BI
# ---------------------------------------------------------------------------
with open(BI_PKL, 'rb') as f:
    bi_raw = pickle.load(f)['df']

all_bitz = bi_raw[bi_raw['Kunden Nr BK'] == KNR].copy()
print(f"All Bitzer rows: {len(all_bitz)}")

# Cross-system P4: Erlöse Fracht = 0 (administrative / zero-revenue)
p4_rows = all_bitz[all_bitz['Erlöse Fracht'].fillna(0) == 0]
print(f"Cross-System P4 (ef=0): {len(p4_rows)}")

# Working set: Erlöse > 0
core = all_bitz[all_bitz['Erlöse Fracht'] > 0].copy()
print(f"Core (ef>0): {len(core)}")

# ---------------------------------------------------------------------------
# ZGI Sub-Row Tonnage Substitution
# ---------------------------------------------------------------------------
# Sub-rows: Mastersendung set, Unterauftrag not set, Tonnage=0
has_ms = core['Mastersendung'].notna()
has_ua = core['Unterauftrag'].notna() & (core['Unterauftrag'].astype(str).str.strip() != 'nan')
core['_is_sub'] = has_ms & ~has_ua

# Master rows in full data (ef=0, Tonnage>0, Unterauftrag set)
masters = all_bitz[
    (all_bitz['Erlöse Fracht'].fillna(0) == 0) &
    (all_bitz['Tonnage (frpfl.)'] > 0) &
    all_bitz['Unterauftrag'].notna()
].copy()
p9_rows = masters
print(f"Sub-Master P9 (ef=0, Tonnage>0, ZGI master): {len(masters)}")

# Build ZGI tonnage map: Mastersendung numeric → sum of Tonnage on master rows
def _norm_ms(v):
    try:
        return int(float(str(v).strip()))
    except (ValueError, TypeError):
        return None

masters['_ms_int'] = masters['Mastersendung'].apply(_norm_ms)
masters_ms_ton = masters.set_index('_ms_int')[['Tonnage (eff.)','Tonnage (frpfl.)']].to_dict('index')

# For sub-rows: substitute tonnage from ZGI master
sub_mask = core['_is_sub'] & (core['Tonnage (frpfl.)'] <= 0)
print(f"Sub-rows needing Tonnage substitution: {sub_mask.sum()}")

core['_ton_eff']  = core['Tonnage (eff.)']
core['_ton_frpfl'] = core['Tonnage (frpfl.)']

for idx in core[sub_mask].index:
    ms_val = _norm_ms(core.at[idx, 'Mastersendung'])
    if ms_val and ms_val in masters_ms_ton:
        mt = masters_ms_ton[ms_val]
        core.at[idx, '_ton_frpfl'] = mt.get('Tonnage (frpfl.)', 0)
        core.at[idx, '_ton_eff']   = mt.get('Tonnage (eff.)', 0)

# Remaining zero-tonnage sub-rows without identified master
unresolved = core[sub_mask & (core['_ton_frpfl'] <= 0)]
print(f"Unresolved sub-rows (no master found): {len(unresolved)}")

# ---------------------------------------------------------------------------
# BitzCalculator Run
# ---------------------------------------------------------------------------
calc = BitzCalculator()

results = []
for idx, row in core.iterrows():
    plz    = str(row['Empfänger PLZ']).strip()
    land   = str(row['Empfänger Land']).strip()
    origin = str(row['Versender PLZ']).strip()
    ef     = float(row['Erlöse Fracht'])

    # Tonnage: prefer frpfl, fallback to eff, fallback to 1 (→ min rate)
    ton = float(row['_ton_frpfl'])
    if ton <= 0:
        ton = float(row['_ton_eff'])
    if ton <= 0:
        ton = 1.0  # minimum → billing_kg = 100

    billing_kg = max(100, math.ceil(ton / 100) * 100)

    try:
        r = calc.calculate(plz, land, tonnage_kg=ton, origin_plz=origin)
        dlv = float(r.basispreis)
        tarifgruppe = r.tarifgruppe
        per_sendung = any('per_sendung' in str(n) for n in r.notes)
        status = 'ok'
    except ValueError as e:
        dlv = 0.0; tarifgruppe = ''; per_sendung = False
        status = f'scope_out:{str(e)[:60]}'
    except LookupError as e:
        dlv = 0.0; tarifgruppe = ''; per_sendung = False
        status = f'no_dlv:{str(e)[:60]}'
    except Exception as e:
        dlv = 0.0; tarifgruppe = ''; per_sendung = False
        status = f'error:{str(e)[:60]}'

    fp = (ef - dlv) / dlv if dlv > 0 else None

    results.append({
        'idx':           idx,
        'land':          land,
        'plz':           plz,
        'origin_plz':    origin,
        'tonnage_kg':    ton,
        'billing_kg':    billing_kg,
        'ef':            ef,
        'dlv':           dlv,
        'delta':         ef - dlv if dlv > 0 else None,
        'fp':            fp,
        'tarifgruppe':   tarifgruppe,
        'per_sendung':   per_sendung,
        'status':        status,
        'is_sub':        bool(row['_is_sub']),
    })

df_res = pd.DataFrame(results)

# ---------------------------------------------------------------------------
# Step 3: M-Klassifikation
# ---------------------------------------------------------------------------
ok = df_res[df_res['status'] == 'ok'].copy()

def muster(fp):
    if fp is None:
        return 'error'
    if abs(fp) <= 0.05:
        return 'M1'
    if fp < -0.05:
        return 'M2'
    return 'M_over'

ok['muster'] = ok['fp'].apply(muster)

# Origin classification
ok['plant'] = ok['origin_plz'].map({'71126': 'Rottenburg', '72108': 'Rottenburg', '04435': 'Schkeuditz'}).fillna('unknown')

# Summary
m_counts = ok['muster'].value_counts()
m1   = ok[ok['muster']=='M1']
m2   = ok[ok['muster']=='M2']
mover= ok[ok['muster']=='M_over']

total_core   = len(core)
total_ok     = len(ok)
total_not_ok = total_core - total_ok

not_ok_df = df_res[df_res['status'] != 'ok']
scope_out = not_ok_df[not_ok_df['status'].str.startswith('scope_out')]
no_dlv    = not_ok_df[not_ok_df['status'].str.startswith('no_dlv')]
errors    = not_ok_df[not_ok_df['status'].str.startswith('error')]

# Land-level breakdown
land_summary = ok.groupby('land').agg(
    rows      = ('ef', 'count'),
    sum_ef    = ('ef', 'sum'),
    sum_dlv   = ('dlv', 'sum'),
    sum_delta = ('delta', 'sum'),
    m1        = ('muster', lambda x: (x=='M1').sum()),
    m2        = ('muster', lambda x: (x=='M2').sum()),
    mover     = ('muster', lambda x: (x=='M_over').sum()),
).reset_index()
land_summary['fp_net'] = land_summary['sum_delta'] / land_summary['sum_dlv']

# Tarifgruppe breakdown (lane-level)
lane_summary = ok.groupby('tarifgruppe').agg(
    rows      = ('ef', 'count'),
    sum_ef    = ('ef', 'sum'),
    sum_dlv   = ('dlv', 'sum'),
    sum_delta = ('delta', 'sum'),
    fp_mean   = ('fp', 'mean'),
    fp_std    = ('fp', 'std'),
    m1        = ('muster', lambda x: (x=='M1').sum()),
    m2        = ('muster', lambda x: (x=='M2').sum()),
    mover     = ('muster', lambda x: (x=='M_over').sum()),
).reset_index()
lane_summary['fp_net'] = lane_summary['sum_delta'] / lane_summary['sum_dlv']
lane_summary = lane_summary.sort_values('sum_delta')

# Origin breakdown
origin_summary = ok.groupby('plant').agg(
    rows=('ef','count'), sum_ef=('ef','sum'), sum_dlv=('dlv','sum'),
    sum_delta=('delta','sum'),
    m1=('muster', lambda x: (x=='M1').sum()),
).reset_index()

# Print summary
print("\n" + "="*60)
print("BITZER STEP 2+3 — v1.9.6 SUMMARY")
print("="*60)
print(f"\nPool (ef>0):         {total_core:6d}")
print(f"Beurteilbar (ok):    {total_ok:6d}  ({100*total_ok/total_core:.1f}%)")
print(f"Nicht beurteilbar:   {total_not_ok:6d}  ({100*total_not_ok/total_core:.1f}%)")
print(f"  scope_out (DE):    {len(scope_out):6d}")
print(f"  no_dlv:            {len(no_dlv):6d}")
print(f"  errors:            {len(errors):6d}")
print()
print(f"M1   |fp|<=5%:  {len(m1):6d}  ({100*len(m1)/total_ok:.1f}%)")
print(f"M2   fp<-5%:    {len(m2):6d}  ({100*len(m2)/total_ok:.1f}%)")
print(f"M_over fp>+5%:  {len(mover):6d}  ({100*len(mover)/total_ok:.1f}%)")
print()
print(f"Σ ef  (beurteilbar):  {ok['ef'].sum():12,.2f} EUR")
print(f"Σ dlv (beurteilbar):  {ok['dlv'].sum():12,.2f} EUR")
print(f"Net Δ:                {ok['delta'].sum():12,.2f} EUR")
print(f"Net Δ %:              {100*ok['delta'].sum()/ok['dlv'].sum():+.2f}%")
print()
print("Land-Breakdown:")
print(land_summary[['land','rows','sum_ef','sum_dlv','sum_delta','fp_net','m1','m2','mover']].to_string(index=False))
print()
print("Cross-System P4 (ef=0):", len(p4_rows))
print("Sub-Master P9 (ef=0, ZGI master):", len(p9_rows))

# Save
out = {
    'df_res':         df_res,
    'ok':             ok,
    'm1':             m1,
    'm2':             m2,
    'mover':          mover,
    'land_summary':   land_summary,
    'lane_summary':   lane_summary,
    'origin_summary': origin_summary,
    'p4_rows':        p4_rows,
    'p9_rows':        p9_rows,
    'scope_out':      scope_out,
    'no_dlv':         no_dlv,
    'unresolved_subs': unresolved,
    'stats': {
        'total_core':   total_core,
        'total_ok':     total_ok,
        'total_not_ok': total_not_ok,
        'n_m1':         len(m1),
        'n_m2':         len(m2),
        'n_mover':      len(mover),
        'sum_ef':       ok['ef'].sum(),
        'sum_dlv':      ok['dlv'].sum(),
        'net_delta':    ok['delta'].sum(),
        'n_p4':         len(p4_rows),
        'n_p9':         len(p9_rows),
        'n_scope_out':  len(scope_out),
        'n_no_dlv':     len(no_dlv),
    },
}

with open(OUT_PKL, 'wb') as f:
    pickle.dump(out, f)

print(f"\nSaved: {OUT_PKL}")
