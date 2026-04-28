#!/usr/bin/env python3
"""
EBM-Papst Mulfingen GmbH — Step 2+3 Pipeline v1.9.6
=====================================================
Outputs output/ebm_step23_results_v196.pkl

Step 2: Pool-Aufbau
  - BI filter: KNR=410844, Erlöse Fracht > 0
  - E1 (Cross-System P4): alle ef=0 Rows sind Dinas-Format (< 16-stellige Auftragsnr.)
    → bereits durch ef>0-Filter entfernt
  - E3: stp_eff = 0 (kein Stellplatz-Äquivalent ableitbar)
  - Sub-Row-Filter: is_sub = has_ms AND NOT has_ua (0 in diesem Datensatz)
  - Out-of-Scope: DE (inland), GB (kein EBM-DLV), RS (kein EBM-DLV)
  - DLV-Lücke: Calculator-Lookup schlägt fehl (unbekannte PLZ/Land)

Step 3: 4-Muster-Klassifikation
  fp = (Erlöse_Fracht - DLV_Soll) / DLV_Soll
  M1:     |fp| <= 5%
  M2*:    fp < -5%
  M_over: fp > +5%

ZGI-Cluster-Aggregation: nicht anwendbar.
  bi_top20_data.pkl enthält keine Abrechnungsstrecke/Zusammengefasst-in Spalten.
  EBM hat 0 is_sub-Rows im ef>0-Pool → kein Cluster-Bias.
"""
from __future__ import annotations

import math
import pickle
import sys
from decimal import Decimal
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path('/home/user/TMS')
sys.path.insert(0, str(BASE / 'src'))

from tms.tariff.calculators.ebm import EBMCalculator

BI_PKL  = BASE / 'output/bi_top20_data.pkl'
OUT_PKL = BASE / 'output/ebm_step23_results_v196.pkl'
KNR     = 410844

# ---------------------------------------------------------------------------
# Load BI
# ---------------------------------------------------------------------------
with open(BI_PKL, 'rb') as f:
    bi_raw = pickle.load(f)['df']

all_ebm = bi_raw[bi_raw['Kunden Nr BK'] == KNR].copy()
print(f"All EBM rows: {len(all_ebm)}")

# P4: ef=0 (alle cross-system + administrative)
p4_rows = all_ebm[all_ebm['Erlöse Fracht'].fillna(0) == 0]
print(f"P4 (ef=0): {len(p4_rows)}")

# Core: ef>0
core = all_ebm[all_ebm['Erlöse Fracht'] > 0].copy()
print(f"Core (ef>0): {len(core)}")

# ---------------------------------------------------------------------------
# stp_eff = Stellplätze wenn >0; sonst ceil(LDM/0.4)
# ---------------------------------------------------------------------------
def _stp_eff(stp, ldm) -> int:
    try:
        s = float(stp)
        if s > 0:
            return max(1, math.ceil(s))
    except (TypeError, ValueError):
        pass
    try:
        l = float(ldm)
        if l > 0:
            return max(1, math.ceil(l / 0.4))
    except (TypeError, ValueError):
        pass
    return 0

core['_stp_eff'] = core.apply(
    lambda r: _stp_eff(r.get('Stellplätze'), r.get('Lademeter')), axis=1
)

e3_rows = core[core['_stp_eff'] == 0]
print(f"E3 (stp_eff=0): {len(e3_rows)}")
core = core[core['_stp_eff'] > 0].copy()
print(f"After E3: {len(core)}")

# ---------------------------------------------------------------------------
# Sub-Row-Filter (v1.9.6 §2e)
# ---------------------------------------------------------------------------
def _nonempty(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return False
    return str(v).strip() not in ('', 'nan', 'None')

core['_has_ms'] = core['Mastersendung'].apply(_nonempty)
core['_has_ua'] = core['Unterauftrag'].apply(_nonempty)
core['_is_sub'] = core['_has_ms'] & ~core['_has_ua']
sub_count = core['_is_sub'].sum()
print(f"Sub-Rows (is_sub): {sub_count} → kein Ausschluss nötig (alle ef>0 Pool)")

# ---------------------------------------------------------------------------
# Out-of-Scope: DE, GB, RS
# ---------------------------------------------------------------------------
OOS_LANDS = {'DE', 'GB', 'RS'}
oos = core[core['Empfänger Land'].isin(OOS_LANDS)]
in_scope = core[~core['Empfänger Land'].isin(OOS_LANDS)].copy()
print(f"Out-of-Scope ({OOS_LANDS}): {len(oos)}")
print(f"In-Scope: {len(in_scope)}")
print(f"Länder (in-scope): {in_scope['Empfänger Land'].value_counts().to_dict()}")

# ---------------------------------------------------------------------------
# EBM Calculator Run
# ---------------------------------------------------------------------------
calc = EBMCalculator()

results = []

for idx, row in in_scope.iterrows():
    plz    = str(row['Empfänger PLZ']).strip()
    land   = str(row['Empfänger Land']).strip()
    origin = str(row.get('Versender PLZ', '74673')).strip()
    ef     = float(row['Erlöse Fracht'])
    stp    = int(row['_stp_eff'])

    try:
        r = calc.calculate(plz, land, stellplaetze=stp)
        dlv = float(r.basispreis)
        tarifgruppe = r.tarifgruppe
        status = 'ok'
    except (ValueError, LookupError) as e:
        dlv = 0.0
        tarifgruppe = ''
        status = f'no_dlv:{str(e)[:60]}'
    except Exception as e:
        dlv = 0.0
        tarifgruppe = ''
        status = f'error:{str(e)[:60]}'

    fp = (ef - dlv) / dlv if dlv > 0 else None

    results.append({
        'idx':         idx,
        'land':        land,
        'plz':         plz,
        'origin_plz':  origin,
        'stp_eff':     stp,
        'ef':          ef,
        'dlv':         dlv,
        'delta':       ef - dlv if dlv > 0 else None,
        'fp':          fp,
        'tarifgruppe': tarifgruppe,
        'status':      status,
        'is_sub':      bool(row['_is_sub']),
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

no_dlv = df_res[df_res['status'].str.startswith('no_dlv', na=False)]
errors  = df_res[df_res['status'].str.startswith('error', na=False)]

m1    = ok[ok['muster'] == 'M1']
m2    = ok[ok['muster'] == 'M2']
mover = ok[ok['muster'] == 'M_over']

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

# Tarifgruppe breakdown
lane_summary = ok.groupby('tarifgruppe').agg(
    rows      = ('ef', 'count'),
    sum_ef    = ('ef', 'sum'),
    sum_dlv   = ('dlv', 'sum'),
    sum_delta = ('delta', 'sum'),
    fp_mean   = ('fp', 'mean'),
    m1        = ('muster', lambda x: (x=='M1').sum()),
    m2        = ('muster', lambda x: (x=='M2').sum()),
    mover     = ('muster', lambda x: (x=='M_over').sum()),
).reset_index()
lane_summary['fp_net'] = lane_summary['sum_delta'] / lane_summary['sum_dlv']
lane_summary = lane_summary.sort_values('sum_delta')

# Print summary
print("\n" + "="*60)
print("EBM-PAPST STEP 2+3 — v1.9.6 SUMMARY")
print("="*60)
print(f"\nPool (ef>0):           {len(core) + len(e3_rows)}")
print(f"E3 (stp_eff=0):        {len(e3_rows)}")
print(f"Out-of-scope (DE/GB/RS): {len(oos)}")
print(f"In-scope:              {len(in_scope)}")
print(f"  DLV-Lücke (no_dlv): {len(no_dlv)}")
print(f"  Beurteilbar (ok):    {len(ok)}")
print()
print(f"M1   |fp|<=5%:  {len(m1):6d}  ({100*len(m1)/len(ok):.1f}%)")
print(f"M2   fp<-5%:    {len(m2):6d}  ({100*len(m2)/len(ok):.1f}%)")
print(f"M_over fp>+5%:  {len(mover):6d}  ({100*len(mover)/len(ok):.1f}%)")
print()
print(f"Σ ef  (beurteilbar):  {ok['ef'].sum():12,.2f} EUR")
print(f"Σ dlv (beurteilbar):  {ok['dlv'].sum():12,.2f} EUR")
print(f"Net Δ:                {ok['delta'].sum():12,.2f} EUR")
print(f"Net Δ %:              {100*ok['delta'].sum()/ok['dlv'].sum():+.2f}%")
print()
print("Land-Breakdown:")
print(land_summary[['land','rows','sum_ef','sum_dlv','sum_delta','fp_net','m1','m2','mover']].to_string(index=False))
print()
print(f"P4 (ef=0):  {len(p4_rows)}")
print(f"  davon cross-system: {len(p4_rows)}")

# Save
out = {
    'df_res':       df_res,
    'ok':           ok,
    'm1':           m1,
    'm2':           m2,
    'mover':        mover,
    'land_summary': land_summary,
    'lane_summary': lane_summary,
    'p4_rows':      p4_rows,
    'oos_rows':     oos,
    'e3_rows':      e3_rows,
    'no_dlv':       no_dlv,
    'errors':       errors,
    'stats': {
        'total_core':    len(core) + len(e3_rows),
        'total_e3':      len(e3_rows),
        'total_oos':     len(oos),
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
    },
}

with open(OUT_PKL, 'wb') as f:
    pickle.dump(out, f)

print(f"\nSaved: {OUT_PKL}")
