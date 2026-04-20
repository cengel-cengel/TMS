#!/usr/bin/env python3
"""Etappe 9b.3 — GEZE Phasen-Rollout + floater_pct + Muster-A/B + CHF-Reverse-Engineer.

Aggregiert BI-Positionen zu Sendungs-Gruppen (Rechnungsnummer × Land × PLZ),
wendet GEZECalculator auf die aggregierte Tonnage an und berechnet floater_pct.

Muster-A : abs(floater_pct - 0.07) < 0.0015  → systemischer 7%-Floater (alle Lanes)
Muster-B : delta_raw < -10 EUR                → Unter-Billing
CHF-RE   : Implizierter floater_pct → CHF-Floater-Band (CH-Gruppen only)

Gate-1 : Tonnage=0-Anteil > 20% (Audit-Schwelle §5.0 Methodik v1.3)

Outputs:
  data/reports/9b3_geze_lanes_summary.csv   — Lane+Zone+Phase Aggregation
  data/reports/9b3_geze_unbeurteilbar.csv   — alle nicht-beurteilbaren Positionen
  data/reports/9b3_geze_muster_b.csv        — Gruppen mit delta_raw < -10 EUR
"""
from __future__ import annotations

import math
import pickle
import re
import sys
from decimal import Decimal
from pathlib import Path

import pandas as pd

BASE = Path('/home/user/TMS')
OUT  = BASE / 'data/reports'
OUT.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(BASE / 'src'))
from tms.tariff.calculators.geze import (  # noqa: E402
    GEZECalculator, _COUNTRY_LOOKUP, _get_chf_table,
)

# ---------------------------------------------------------------------------
# Load + filter (identical filter to 9b.2)
# ---------------------------------------------------------------------------
with open(BASE / 'output/bi_top20_data.pkl', 'rb') as f:
    bi = pickle.load(f)['df']


def rn_valid(x: object) -> bool:
    try:
        return float(str(x).replace(',', '.')) > 5
    except Exception:
        return False


core = bi[
    (bi['Kunden Nr BK'] == 406035) &
    (bi['periode'] == 'POST') &
    bi['Rechnungsnummer'].apply(rn_valid) &
    (bi['Erlöse Fracht'].fillna(0) > 0)
].copy()

core['datum'] = pd.to_datetime(core['Leistungsdatum'], errors='coerce')

VSTART = pd.Timestamp('2025-01-01')
VEND   = pd.Timestamp('2025-12-31')


def phase(d: pd.Timestamp) -> str:
    if pd.isna(d):
        return 'unknown'
    if d < VSTART:
        return 'pre_dlv'
    if d <= VEND:
        return 'in_dlv_2025'
    return 'in_dlv_2025_fallback'


core['phase'] = core['datum'].apply(phase)

DLV_LANDS = set(_COUNTRY_LOOKUP.keys())


def norm_plz(plz: object, land: str) -> str:
    s = str(plz).strip()
    if land == 'IE':
        return re.sub(r'\s.*', '', s)[:3]
    return re.sub(r'[^0-9A-Z]', '', s.upper())


def plz_lookup_ok(plz: object, land: str) -> bool:
    if land not in DLV_LANDS:
        return False
    fn = _COUNTRY_LOOKUP.get(land.upper())
    if fn is None:
        return False
    try:
        return fn(norm_plz(plz, land)) is not None
    except Exception:
        return False


core['plz_norm']    = core.apply(lambda r: norm_plz(r['Empfänger PLZ'], r['Empfänger Land']), axis=1)
core['plz_ok']      = core.apply(lambda r: plz_lookup_ok(r['Empfänger PLZ'], r['Empfänger Land']), axis=1)
core['in_dlv_land'] = core['Empfänger Land'].isin(DLV_LANDS)
core['tonnage_ok']  = core['Tonnage (eff.)'] > 0


def beurteilbar_status(row: pd.Series) -> str:
    if not row['in_dlv_land']:
        return 'no_dlv_t_zero' if not row['tonnage_ok'] else 'no_dlv'
    if not row['tonnage_ok']:
        return 't_zero'
    if not row['plz_ok']:
        return 'plz_no_match'
    return 'beurteilbar'


core['status'] = core.apply(beurteilbar_status, axis=1)

# Gate-1 check
total_core   = len(core)
t_zero_count = (core['status'] == 't_zero').sum()
t_zero_pct   = t_zero_count / total_core * 100

beurt  = core[core['status'] == 'beurteilbar'].copy()
unbeurt = core[core['status'] != 'beurteilbar'].copy()

# ---------------------------------------------------------------------------
# Aggregation: Rechnungsnummer × Empfänger Land × plz_norm  → Sendungs-Gruppe
# ---------------------------------------------------------------------------
AGG_KEY = ['Rechnungsnummer', 'Empfänger Land', 'plz_norm']

grp = beurt.groupby(AGG_KEY).agg(
    n_pos       = ('Tonnage (eff.)', 'count'),
    tonnage_sum = ('Tonnage (eff.)', 'sum'),
    fracht_sum  = ('Erlöse Fracht',  'sum'),
    diesel_sum  = ('Erlöse Diesel',  'sum'),
    maut_sum    = ('Erlöse Maut',    'sum'),
    datum_min   = ('datum',          'min'),
).reset_index()

grp['phase']          = grp['datum_min'].apply(phase)
grp['tonnage_source'] = 'direct'  # §5.0: all beurteilbar rows have Tonnage>0

# ---------------------------------------------------------------------------
# GEZECalculator per group
# ---------------------------------------------------------------------------
calc = GEZECalculator()

basispreis_list: list[float]  = []
zone_list:       list[int]    = []
billing_kg_list: list[int]    = []
calc_ok_list:    list[bool]   = []

for _, row in grp.iterrows():
    try:
        res = calc.calculate(
            empf_plz=row['plz_norm'],
            empf_land=row['Empfänger Land'],
            tonnage_kg=float(row['tonnage_sum']),
        )
        basispreis_list.append(float(res.basispreis))
        zone_note = next((n for n in res.notes if n.startswith('zone=')), 'zone=0')
        zone_list.append(int(zone_note.split('=')[1]))
        bk_note = next((n for n in res.notes if n.startswith('billing_kg=')), 'billing_kg=0')
        billing_kg_list.append(int(bk_note.split('=')[1]))
        calc_ok_list.append(True)
    except Exception:
        basispreis_list.append(float('nan'))
        zone_list.append(-1)
        billing_kg_list.append(-1)
        calc_ok_list.append(False)

grp['basispreis'] = basispreis_list
grp['zone']       = zone_list
grp['billing_kg'] = billing_kg_list
grp['calc_ok']    = calc_ok_list

calc_fail = (~grp['calc_ok']).sum()
grp_ok = grp[grp['calc_ok']].copy()

# ---------------------------------------------------------------------------
# floater_pct + Muster-A / B
# ---------------------------------------------------------------------------
grp_ok['floater_pct'] = grp_ok['fracht_sum'] / grp_ok['basispreis'] - 1
grp_ok['delta_raw']   = grp_ok['fracht_sum'] - grp_ok['basispreis']

MUSTER_A_TARGET = 0.07
MUSTER_A_TOL    = 0.0015
MUSTER_B_THRESH = -10.0

grp_ok['muster_a'] = (grp_ok['floater_pct'] - MUSTER_A_TARGET).abs() < MUSTER_A_TOL
grp_ok['muster_b'] = grp_ok['delta_raw'] < MUSTER_B_THRESH

# ---------------------------------------------------------------------------
# CHF Reverse-Engineer (CH-Gruppen only)
# ---------------------------------------------------------------------------
CHF_TABLE = _get_chf_table()


def chf_band_lookup(fp_val: float, bk: int) -> tuple[float, float, str] | None:
    """Map implied floater_pct to CHF band (tolerance 0.003)."""
    is_stgut = bk <= 3000
    for lo, hi, sg_frac, ko_frac in CHF_TABLE:
        frac = float(sg_frac) if is_stgut else float(ko_frac)
        if abs(fp_val - frac) < 0.003:
            return (lo, hi, 'sg' if is_stgut else 'ko')
    return None


grp_ok['chf_band_lo']  = None
grp_ok['chf_band_hi']  = None
grp_ok['chf_band_typ'] = None

ch_idx = grp_ok[grp_ok['Empfänger Land'] == 'CH'].index
for idx in ch_idx:
    hit = chf_band_lookup(grp_ok.at[idx, 'floater_pct'], grp_ok.at[idx, 'billing_kg'])
    if hit:
        grp_ok.at[idx, 'chf_band_lo']  = hit[0]
        grp_ok.at[idx, 'chf_band_hi']  = hit[1]
        grp_ok.at[idx, 'chf_band_typ'] = hit[2]

# ---------------------------------------------------------------------------
# Lane summary CSV (Land × Zone × Phase)
# ---------------------------------------------------------------------------
lane_agg = grp_ok.groupby(['Empfänger Land', 'zone', 'phase']).agg(
    n_groups       = ('fracht_sum',   'count'),
    n_positions    = ('n_pos',        'sum'),
    basispreis_sum = ('basispreis',   'sum'),
    fracht_sum     = ('fracht_sum',   'sum'),
    delta_sum      = ('delta_raw',    'sum'),
    fp_mean        = ('floater_pct',  'mean'),
    fp_std         = ('floater_pct',  'std'),
    fp_min         = ('floater_pct',  'min'),
    fp_max         = ('floater_pct',  'max'),
    n_muster_a     = ('muster_a',     'sum'),
    n_muster_b     = ('muster_b',     'sum'),
    tonnage_sum    = ('tonnage_sum',  'sum'),
    billing_kg_sum = ('billing_kg',   'sum'),
).reset_index()

lane_agg.to_csv(OUT / '9b3_geze_lanes_summary.csv', index=False)
print(f"Written: 9b3_geze_lanes_summary.csv  ({len(lane_agg)} Lane-Phase Zeilen)")

# ---------------------------------------------------------------------------
# Unbeurteilbar CSV
# ---------------------------------------------------------------------------
UNBEURT_COLS = [c for c in [
    'Rechnungsnummer', 'datum', 'phase',
    'Empfänger Land', 'Empfänger PLZ', 'plz_norm',
    'Tonnage (eff.)', 'Lademeter',
    'Erlöse Fracht', 'Erlöse Diesel', 'Erlöse Maut',
    'status',
] if c in unbeurt.columns]
unbeurt[UNBEURT_COLS].to_csv(OUT / '9b3_geze_unbeurteilbar.csv', index=False)
print(f"Written: 9b3_geze_unbeurteilbar.csv  ({len(unbeurt)} Positionen)")

# ---------------------------------------------------------------------------
# Muster-B CSV
# ---------------------------------------------------------------------------
mb = grp_ok[grp_ok['muster_b']].copy()
MB_COLS = [c for c in [
    'Rechnungsnummer', 'Empfänger Land', 'plz_norm', 'zone', 'phase',
    'tonnage_sum', 'billing_kg', 'n_pos',
    'fracht_sum', 'basispreis', 'delta_raw', 'floater_pct',
    'muster_a',
] if c in mb.columns]
mb[MB_COLS].to_csv(OUT / '9b3_geze_muster_b.csv', index=False)
print(f"Written: 9b3_geze_muster_b.csv        ({len(mb)} Gruppen)")

# ---------------------------------------------------------------------------
# Console summary
# ---------------------------------------------------------------------------
n_beurt = len(beurt)
n_grps  = len(grp_ok)
n_ma    = int(grp_ok['muster_a'].sum())
n_mb    = int(grp_ok['muster_b'].sum())

print('\n' + '=' * 74)
print('=== 9b.3 GEZE PHASEN-ROLLOUT ===')
print('=' * 74)

if t_zero_pct > 20.0:
    print(f"\n[GATE-1 WARNING] Tonnage=0: {t_zero_count}/{total_core} = {t_zero_pct:.1f}% > 20%-Audit-Schwelle")

if calc_fail:
    print(f"[WARN] Calculator-Fehler (LookupError): {calc_fail} Gruppen ausgeschlossen")

print(f"\nGesamt-Core   : {total_core} Positionen  (KNR 406035, POST, RN>5, Fracht>0)")
print(f"Beurteilbar   : {n_beurt} Positionen → {n_grps} Gruppen (RN × Land × PLZ-norm)")
print(f"Unbeurteilbar : {len(unbeurt)} Positionen  ({t_zero_count} t_zero, {(unbeurt['status'].isin(['no_dlv','no_dlv_t_zero'])).sum()} no_dlv)")

print(f"\nPhasen-Verteilung ({n_grps} Gruppen):")
for ph, n in grp_ok['phase'].value_counts().items():
    print(f"  {ph:<28}: {n:4d}  ({n/n_grps*100:.1f}%)")

print(f"\nMuster-A (|fp − 0.07| < 0.0015)   : {n_ma:4d} Gruppen")
print(f"Muster-B (delta_raw < −10 EUR)     : {n_mb:4d} Gruppen")

# Per-Land overview
by_land = grp_ok.groupby('Empfänger Land').agg(
    n_g  = ('fracht_sum',  'count'),
    n_p  = ('n_pos',       'sum'),
    soll = ('basispreis',  'sum'),
    ist  = ('fracht_sum',  'sum'),
    dlt  = ('delta_raw',   'sum'),
    fpm  = ('floater_pct', 'mean'),
    fps  = ('floater_pct', 'std'),
    ma   = ('muster_a',    'sum'),
    mb   = ('muster_b',    'sum'),
).reset_index()

print(f"\nLane-Übersicht (per Empfänger Land, {n_grps} Gruppen):")
hdr = f"  {'Land':<5} {'nGrp':>5} {'nPos':>5} {'Soll €':>10} {'Ist €':>10} {'Δ €':>10} {'fp_mean':>8} {'fp_std':>7} {'MA':>4} {'MB':>4}"
print(hdr)
print(f"  {'-'*4} {'-'*5} {'-'*5} {'-'*10} {'-'*10} {'-'*10} {'-'*8} {'-'*7} {'-'*4} {'-'*4}")
for _, lr in by_land.iterrows():
    fps = f"{lr['fps']:>7.4f}" if not pd.isna(lr['fps']) else '     NA'
    print(
        f"  {lr['Empfänger Land']:<5} {int(lr['n_g']):>5} {int(lr['n_p']):>5} "
        f"{lr['soll']:>10.2f} {lr['ist']:>10.2f} {lr['dlt']:>+10.2f} "
        f"{lr['fpm']:>+8.4f} {fps} "
        f"{int(lr['ma']):>4} {int(lr['mb']):>4}"
    )
tot_soll  = by_land['soll'].sum()
tot_ist   = by_land['ist'].sum()
tot_delta = by_land['dlt'].sum()
print(
    f"  {'Gesamt':<5} {n_grps:>5} {n_beurt:>5} "
    f"{tot_soll:>10.2f} {tot_ist:>10.2f} {tot_delta:>+10.2f}"
)

# CHF reverse-engineer summary
ch_grps = grp_ok[grp_ok['Empfänger Land'] == 'CH']
if len(ch_grps) > 0:
    n_ch_matched   = ch_grps['chf_band_lo'].notna().sum()
    n_ch_unmatched = len(ch_grps) - n_ch_matched
    print(f"\nCHF-Reverse-Engineer ({len(ch_grps)} CH-Gruppen):")
    print(f"  Band-Match   : {n_ch_matched}")
    print(f"  Kein Match   : {n_ch_unmatched}  (ggf. Neutralband ≥1.021 oder Diesel-Überlagerung)")
    if n_ch_matched > 0:
        matched = ch_grps.dropna(subset=['chf_band_lo'])
        band_dist = matched.groupby(
            ['chf_band_lo', 'chf_band_hi', 'chf_band_typ']
        ).size().reset_index(name='n')
        for _, bd in band_dist.iterrows():
            print(f"  Band {bd['chf_band_lo']:.4f}–{bd['chf_band_hi']:.4f} ({bd['chf_band_typ']}): {int(bd['n'])} Gruppen")
    # fp distribution for CH
    fp_q = ch_grps['floater_pct'].describe(percentiles=[0.25, 0.50, 0.75])
    print(f"  fp Stats: mean={fp_q['mean']:+.4f}  p25={fp_q['25%']:+.4f}  p50={fp_q['50%']:+.4f}  p75={fp_q['75%']:+.4f}  std={fp_q['std']:.4f}")

# Muster-A details
if n_ma > 0:
    print(f"\nMuster-A Details (fp ≈ 0.07):")
    for _, mr in grp_ok[grp_ok['muster_a']].iterrows():
        print(f"  {mr['Empfänger Land']:3s} PLZ={mr['plz_norm']:<8} Zone={mr['zone']} "
              f"fp={mr['floater_pct']:+.4f}  nPos={int(mr['n_pos'])}  RN={mr['Rechnungsnummer']}")
else:
    print(f"\nMuster-A: 0 Treffer (kein systemischer 7%-Floater in dieser Stichprobe)")

# Muster-B details (top 10 by |delta_raw|)
if n_mb > 0:
    print(f"\nMuster-B Top-10 (delta_raw < −10 EUR):")
    for _, mr in mb.nsmallest(10, 'delta_raw').iterrows():
        print(f"  {mr['Empfänger Land']:3s} PLZ={mr['plz_norm']:<8} Zone={mr['zone']} "
              f"delta={mr['delta_raw']:>+8.2f} EUR  fp={mr['floater_pct']:+.4f}  RN={mr['Rechnungsnummer']}")

print('\nDone.')
