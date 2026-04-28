#!/usr/bin/env python3
"""
Groz-Beckert KG / Groz-Beckert EU — Step 2+3 Pipeline v1.9.6
=============================================================
KNRs: 490527 (Groz-Beckert Europe GmbH), 410912 (Groz-Beckert KG),
      527373 (Groz Beckert Portuguessa Lda)
      527410 (Groz Beckert Carding Belgium) → alle DE → scope_out

Output: output/groz_beckert_step23_results_v196.pkl

Dual-Mode: LDM-basiert für Sonder-Lanes (PT-Porto, CH-Zuchwil);
           Gewicht-basiert (GC) für alle anderen Lanes.
           Tarifgruppe codiert den Mode: groz_beckert_gc_XX vs. groz_beckert_lane_ORIG_CC.

ZGI-Cluster: bi_cache_groz_beckert.pkl enthält keine Abrechnungsstrecke/ZGI-Spalten.
             Pre-Flight: 0 Mastersendung in Scope → ZGI-Aggregation ist No-Op.
"""
from __future__ import annotations

import math
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path('/home/user/TMS')
sys.path.insert(0, str(BASE / 'src'))

from tms.tariff.calculators.groz_beckert import GrozBeckertCalculator

BI_PKL  = BASE / 'output/bi_cache_groz_beckert.pkl'
OUT_PKL = BASE / 'output/groz_beckert_step23_results_v196.pkl'

SCOPE_KNR = {490527, 410912, 527373}
OOS_LAND  = {'DE', 'HR', 'NO', 'SE'}

# ---------------------------------------------------------------------------
# Load BI
# ---------------------------------------------------------------------------
with open(BI_PKL, 'rb') as f:
    bi_raw = pickle.load(f)

print(f"Total rows in cache: {len(bi_raw)}")
print(f"KNRs: {bi_raw['Kunden Nr BK'].value_counts().to_dict()}")

# ---------------------------------------------------------------------------
# Split: scope vs. scope-out
# ---------------------------------------------------------------------------
p_knr_oos = bi_raw[~bi_raw['Kunden Nr BK'].isin(SCOPE_KNR)]
print(f"\nKNR 527410 scope-out: {len(p_knr_oos)} rows")
print(f"  ef>0: {(p_knr_oos['Erlöse Fracht'].fillna(0)>0).sum()}")

active = bi_raw[bi_raw['Kunden Nr BK'].isin(SCOPE_KNR)].copy()

# P4: ef=0
p4_rows = active[active['Erlöse Fracht'].fillna(0) == 0]
core    = active[active['Erlöse Fracht'] > 0].copy()
print(f"\nActive KNRs pool: {len(active)}")
print(f"P4 (ef=0): {len(p4_rows)}")
print(f"Core (ef>0): {len(core)}")

# ---------------------------------------------------------------------------
# Sub-Row classification
# ---------------------------------------------------------------------------
def _nonempty(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return False
    return str(v).strip() not in ('', 'nan', 'None')

core['_has_ms'] = core['Mastersendung'].apply(_nonempty)
core['_has_ua'] = core['Unterauftrag'].apply(_nonempty)
core['_is_sub'] = core['_has_ms'] & ~core['_has_ua']

sub_rows = core[core['_is_sub']].copy()
print(f"Sub-Rows (is_sub, ef>0): {len(sub_rows)}")

# ---------------------------------------------------------------------------
# Physical fields
# ---------------------------------------------------------------------------
core['_ton'] = pd.to_numeric(core['Tonnage (eff.)'], errors='coerce').fillna(0)
core['_ldm'] = pd.to_numeric(core['Lademeter'],      errors='coerce').fillna(0)

# Rows with no billing input (ton=ldm=0) — overlaps with sub-rows
no_input = core[(core['_ton'] <= 0) & (core['_ldm'] <= 0)]
print(f"No billing input (ton=ldm=0): {len(no_input)}")

# ---------------------------------------------------------------------------
# In-scope filter
# ---------------------------------------------------------------------------
in_scope = core[
    ~core['Empfänger Land'].isin(OOS_LAND) &
    ~core['_is_sub'] &
    ~((core['_ton'] <= 0) & (core['_ldm'] <= 0))
].copy()

oos_land = core[core['Empfänger Land'].isin(OOS_LAND)]
print(f"\nScope-out (OOS land): {len(oos_land)}")
print(f"In-scope: {len(in_scope)}")
print(f"Länder: {in_scope['Empfänger Land'].value_counts().to_dict()}")

# ---------------------------------------------------------------------------
# Calculator run
# ---------------------------------------------------------------------------
calc = GrozBeckertCalculator()

results = []
for idx, row in in_scope.iterrows():
    plz    = str(row['Empfänger PLZ']).strip()
    land   = str(row['Empfänger Land']).strip()
    origin = str(row.get('Versender PLZ', '72458')).strip()
    ef     = float(row['Erlöse Fracht'])
    ton    = float(row['_ton'])
    ldm    = float(row['_ldm'])
    knr    = int(row['Kunden Nr BK'])
    vname  = str(row.get('Versender Name', '')).strip()

    try:
        r = calc.calculate(
            plz, land,
            tonnage_kg=ton if ton > 0 else None,
            lademeter=ldm  if ldm > 0 else None,
            origin_plz=origin,
        )
        dlv = float(r.basispreis)
        tarifgruppe = r.tarifgruppe
        mode = next((n.split('=')[1] for n in r.notes if n.startswith('mode=')), 'GC')
        zone = next(
            (n.split('=')[1] for n in r.notes if n.startswith('dest_zone=') or n.startswith('lane=')),
            ''
        )
        status = 'ok'
    except (ValueError, LookupError) as e:
        dlv = 0.0; tarifgruppe = ''; mode = ''; zone = ''
        status = f'no_dlv:{str(e)[:60]}'
    except Exception as e:
        dlv = 0.0; tarifgruppe = ''; mode = ''; zone = ''
        status = f'error:{str(e)[:60]}'

    fp = (ef - dlv) / dlv if dlv > 0 else None

    results.append({
        'idx':         idx,
        'knr':         knr,
        'versender':   vname,
        'land':        land,
        'plz':         plz,
        'origin_plz':  origin,
        'ton':         ton,
        'ldm':         ldm,
        'ef':          ef,
        'dlv':         dlv,
        'delta':       ef - dlv if dlv > 0 else None,
        'fp':          fp,
        'tarifgruppe': tarifgruppe,
        'mode':        mode,
        'zone':        zone,
        'status':      status,
    })

df_res = pd.DataFrame(results)

# ---------------------------------------------------------------------------
# Step 3: M-Klassifikation
# ---------------------------------------------------------------------------
ok = df_res[df_res['status'] == 'ok'].copy()
no_dlv = df_res[df_res['status'].str.startswith('no_dlv', na=False)]

def muster(fp):
    if fp is None: return 'error'
    if abs(fp) <= 0.05: return 'M1'
    if fp < -0.05: return 'M2'
    return 'M_over'

ok['muster'] = ok['fp'].apply(muster)
m1    = ok[ok['muster'] == 'M1']
m2    = ok[ok['muster'] == 'M2']
mover = ok[ok['muster'] == 'M_over']

# Summaries
land_summary = ok.groupby('land').agg(
    rows=('ef','count'), sum_ef=('ef','sum'), sum_dlv=('dlv','sum'),
    sum_delta=('delta','sum'),
    m1=('muster', lambda x:(x=='M1').sum()),
    m2=('muster', lambda x:(x=='M2').sum()),
    mover=('muster', lambda x:(x=='M_over').sum()),
).reset_index()
land_summary['fp_net'] = land_summary['sum_delta'] / land_summary['sum_dlv']

mode_summary = ok.groupby('mode').agg(
    rows=('ef','count'), sum_ef=('ef','sum'), sum_dlv=('dlv','sum'),
    sum_delta=('delta','sum'),
    m1=('muster', lambda x:(x=='M1').sum()),
    m2=('muster', lambda x:(x=='M2').sum()),
    mover=('muster', lambda x:(x=='M_over').sum()),
).reset_index()
mode_summary['fp_net'] = mode_summary['sum_delta'] / mode_summary['sum_dlv']

knr_summary = ok.groupby('knr').agg(
    rows=('ef','count'), sum_ef=('ef','sum'), sum_dlv=('dlv','sum'),
    sum_delta=('delta','sum'),
    m1=('muster', lambda x:(x=='M1').sum()),
    m2=('muster', lambda x:(x=='M2').sum()),
    mover=('muster', lambda x:(x=='M_over').sum()),
).reset_index()
knr_summary['fp_net'] = knr_summary['sum_delta'] / knr_summary['sum_dlv']

tg_summary = ok.groupby('tarifgruppe').agg(
    rows=('ef','count'), sum_ef=('ef','sum'), sum_dlv=('dlv','sum'),
    sum_delta=('delta','sum'),
    fp_mean=('fp','mean'), fp_std=('fp','std'),
    m1=('muster', lambda x:(x=='M1').sum()),
    m2=('muster', lambda x:(x=='M2').sum()),
    mover=('muster', lambda x:(x=='M_over').sum()),
).reset_index()
tg_summary['fp_net'] = tg_summary['sum_delta'] / tg_summary['sum_dlv']
tg_summary = tg_summary.sort_values('sum_delta')

# Print summary
print("\n" + "="*60)
print("GROZ-BECKERT STEP 2+3 — v1.9.6 SUMMARY")
print("="*60)
print(f"\nPool (ef>0, active KNRs):    {len(core)}")
print(f"Scope-out (DE/HR/NO/SE):     {len(oos_land)}")
print(f"Sub-Rows (ton=ldm=0):        {len(sub_rows)}")
print(f"In-scope:                    {len(in_scope)}")
print(f"  DLV-Lücke:                 {len(no_dlv)}")
print(f"  Beurteilbar (ok):          {len(ok)}")
print()
print(f"M1  |fp|<=5%:  {len(m1):5d}  ({100*len(m1)/len(ok):.1f}%)")
print(f"M2  fp<-5%:    {len(m2):5d}  ({100*len(m2)/len(ok):.1f}%)")
print(f"M_over fp>+5%: {len(mover):5d}  ({100*len(mover)/len(ok):.1f}%)")
print()
print(f"Σ ef:   {ok['ef'].sum():12,.2f} EUR")
print(f"Σ dlv:  {ok['dlv'].sum():12,.2f} EUR")
print(f"Net Δ:  {ok['delta'].sum():12,.2f} EUR  ({100*ok['delta'].sum()/ok['dlv'].sum():+.2f}%)")
print()
print("Mode-Breakdown:")
print(mode_summary.to_string(index=False))
print()
print("Land-Breakdown:")
print(land_summary[['land','rows','sum_ef','sum_dlv','sum_delta','fp_net','m1','m2','mover']].to_string(index=False))
print()
print("KNR-Breakdown:")
print(knr_summary.to_string(index=False))
print()
print("Tarifgruppe-Breakdown (sortiert nach sum_delta):")
print(tg_summary[['tarifgruppe','rows','sum_ef','sum_dlv','sum_delta','fp_net','m1','m2','mover']].to_string(index=False))

# Save
out = {
    'df_res':       df_res,
    'ok':           ok,
    'm1':           m1,
    'm2':           m2,
    'mover':        mover,
    'land_summary': land_summary,
    'mode_summary': mode_summary,
    'knr_summary':  knr_summary,
    'tg_summary':   tg_summary,
    'p4_rows':      p4_rows,
    'oos_land':     oos_land,
    'oos_knr':      p_knr_oos,
    'sub_rows':     sub_rows,
    'no_dlv':       no_dlv,
    'stats': {
        'total_core':    len(core),
        'total_oos':     len(oos_land),
        'total_subs':    len(sub_rows),
        'total_in_scope':len(in_scope),
        'total_ok':      len(ok),
        'total_no_dlv':  len(no_dlv),
        'n_m1':          len(m1),
        'n_m2':          len(m2),
        'n_mover':       len(mover),
        'sum_ef':        ok['ef'].sum(),
        'sum_dlv':       ok['dlv'].sum(),
        'net_delta':     ok['delta'].sum(),
        'n_p4':          len(p4_rows),
        'n_knr_oos':     len(p_knr_oos),
    },
}

with open(OUT_PKL, 'wb') as f:
    pickle.dump(out, f)
print(f"\nSaved: {OUT_PKL}")
