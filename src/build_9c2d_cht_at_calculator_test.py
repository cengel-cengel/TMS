#!/usr/bin/env python3
"""Etappe 9c.2d — CHTAustriaCalculator Integration Test.

billing_scope = "position": jede Position isoliert bewertet.
  Fracht: flat per-band rate; actual_kg direkt gegen Schwellen (kein Rounding)
  Maut:   DE-Maut 0.56 EUR/100 kg auf ceil(actual_kg/100)*100
  AT-Maut: inklusive in Fracht
  Diesel: not_contracted (0/36 BI-Zeilen, bestätigt)

kg_rounding_rule (§2c v1.8.1):
  Fracht: "actual_kg_fracht_only" — kein billing_kg vor Band-Lookup
  Maut:   ceil(actual_kg/100)*100

Erfolgskriterium: ≥90 % der in_dlv_2026-Zeilen (exkl. t_zero + rn_adj)
haben |Erlöse_Fracht − basispreis| ≤ 0,01 EUR.

Zone 1 = PLZ 67-69; Zone 2 = 48-49, 50-54; Zone 3 = 40-47, 55-57, 60-66;
Zone 4 = 10-19, 22-25; Zone 5 = 20-21, 26-28; Zone 6 = 30-39, 70-75, 80-89, 90-99.
AX-Raten-Präzision: 2dp (§6c v1.8.1, |Δ|<0.004 EUR).
Diesel: not_contracted → Erlöse_Diesel = 0 für alle AT-Zeilen (check informativ).
"""
from __future__ import annotations

import sys
import pickle
from pathlib import Path

import pandas as pd

BASE = Path('/home/user/TMS')
sys.path.insert(0, str(BASE / 'src'))
from tms.tariff.calculators.cht_at import CHTAustriaCalculator  # noqa: E402

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
DLV_START_2026 = pd.Timestamp('2026-01-01')
RN_STD_THRESH  = 0.0005

# ---------------------------------------------------------------------------
# Load CHT AT rows
# ---------------------------------------------------------------------------
with open(BASE / 'output/bi_top20_data.pkl', 'rb') as f:
    bi = pickle.load(f)['df']


def rn_valid(x: object) -> bool:
    try:
        return float(str(x).replace(',', '.')) > 5
    except Exception:
        return False


at = bi[
    (bi['Kunden Nr BK'] == 486073) &
    (bi['periode'] == 'POST') &
    bi['Rechnungsnummer'].apply(rn_valid) &
    (bi['Erlöse Fracht'].fillna(0) > 0) &
    (bi['Empfänger Land'] == 'AT')
].copy()

at['datum']   = pd.to_datetime(at['Leistungsdatum'], errors='coerce')
at['phase']   = at['datum'].apply(
    lambda d: 'in_dlv_2026' if pd.notna(d) and d >= DLV_START_2026 else 'pre_dlv_2026'
)
at['rn_str']  = at['Rechnungsnummer'].astype(str).str.strip()
at['plz_str'] = at['Empfänger PLZ'].astype(str).str.strip().str.replace(' ', '').str.replace('-', '')
at['tonnage'] = at['Tonnage (eff.)'].fillna(0)
at['is_t0']   = at['tonnage'] <= 0

# ---------------------------------------------------------------------------
# Run Calculator (position-scope)
# ---------------------------------------------------------------------------
calc = CHTAustriaCalculator()
at_pos = at[~at['is_t0']].copy()

bp_list, maut_list, ok_list, err_list = (
    [None] * len(at_pos), [None] * len(at_pos),
    [False] * len(at_pos), [''] * len(at_pos),
)
idx_list = list(at_pos.index)

for i, (idx, row) in enumerate(at_pos.iterrows()):
    try:
        res = calc.calculate(
            row['plz_str'], 'AT', tonnage_kg=float(row['tonnage'])
        )
        bp_list[i]   = float(res.basispreis)
        maut_list[i] = float(res.maut_surcharge)
        ok_list[i]   = True
    except Exception as e:
        err_list[i] = str(e)

at_pos = at_pos.copy()
at_pos['basispreis'] = bp_list
at_pos['maut_soll']  = maut_list
at_pos['calc_ok']    = ok_list
at_pos['calc_err']   = err_list

at_ok = at_pos[at_pos['calc_ok']].copy()
at_ok['delta_fracht'] = at_ok['Erlöse Fracht'] - at_ok['basispreis']
at_ok['delta_maut']   = at_ok['Erlöse Maut']   - at_ok['maut_soll']
at_ok['fp']           = at_ok['delta_fracht']   / at_ok['basispreis']
at_ok['match_01']     = at_ok['delta_fracht'].abs() <= 0.01

# ---------------------------------------------------------------------------
# Gate 6: RN-Level-Faktor-Detection (residuals after position-scope calc)
# ---------------------------------------------------------------------------
rn_stats = (
    at_ok.groupby('rn_str')['fp']
    .agg(rn_factor='median', rn_std='std')
    .fillna({'rn_std': 0.0})
)


def _gate6_flag(rn: str) -> str:
    if rn not in rn_stats.index:
        return ''
    s = float(rn_stats.loc[rn, 'rn_std'])
    f = float(rn_stats.loc[rn, 'rn_factor'])
    if s < RN_STD_THRESH:
        return 'exact_dlv' if abs(f) < RN_STD_THRESH else 'rn_level_adjustment'
    return ''


at_ok['gate6_flag'] = at_ok['rn_str'].apply(_gate6_flag)
at_ok['is_rn_adj']  = at_ok['gate6_flag'] == 'rn_level_adjustment'

# ---------------------------------------------------------------------------
# Print summary
# ---------------------------------------------------------------------------
print('=' * 74)
print('=== 9c.2d CHTAustriaCalculator INTEGRATION TEST ===')
print('=' * 74)
print('  billing_scope = "position"  |  kg_rounding = actual_kg_fracht_only')
print('  Fracht: flat per band (actual_kg vs threshold, no rounding)')
print('  Maut: 0.56 EUR/100 kg × ceil(kg/100)*100')

n_total   = len(at)
n_t0      = at['is_t0'].sum()
n_calc_ok = len(at_ok)
n_rn_adj  = at_ok['is_rn_adj'].sum()
n_exact   = (at_ok['gate6_flag'] == 'exact_dlv').sum()

print(f"\nGesamt AT-Zeilen (KNR 486073, POST, Fracht>0): {n_total}")
print(f"  Tonnage=0 (t_zero):        {n_t0}")
print(f"  Calculator OK (tonnage>0): {n_calc_ok}")
print(f"  Calculator FAIL:           {(~at_pos['calc_ok']).sum()}")
if (at_pos['calc_err'] != '').any():
    print("  Fehler:")
    for e in at_pos[at_pos['calc_err'] != '']['calc_err'].unique():
        print(f"    {e}")

print(f"\nGate-6 RN-Level-Faktor-Klassifikation (Residuen nach Position-Calc):")
for rn in sorted(rn_stats.index):
    flag = _gate6_flag(rn)
    f    = float(rn_stats.loc[rn, 'rn_factor'])
    s    = float(rn_stats.loc[rn, 'rn_std'])
    n_rn = int((at_ok['rn_str'] == rn).sum())
    print(f"  RN {rn}: factor={f:+.6f}  std={s:.6f}  n={n_rn}  → {flag or 'per_position'}")
print(f"  rn_level_adjustment: {n_rn_adj} Positionen (exkl. von Erfolgsquote)")
print(f"  exact_dlv:           {n_exact} Positionen")

n_pre    = (at_ok['phase'] == 'pre_dlv_2026').sum()
n_in_dlv = (at_ok['phase'] == 'in_dlv_2026').sum()

print(f"\nPhasen-Split ({n_calc_ok} Zeilen mit Tonnage>0):")
print(f"  in_dlv_2026  : {n_in_dlv}   (Haupt-Test-Set)")
print(f"  pre_dlv_2026 : {n_pre}   (unbeurteilbar — 2025-DLV fehlt)")

pre = at_ok[at_ok['phase'] == 'pre_dlv_2026']
if len(pre) > 0:
    print(f"\nPre-DLV-2026 ({len(pre)} Zeilen, KEIN Calculator-Check):")
    print(f"  fp-Verteilung (ggü. 2026-DLV, informativ):")
    print(f"    mean={pre['fp'].mean():+.4f}  std={pre['fp'].std():.4f}  "
          f"p25={pre['fp'].quantile(0.25):+.4f}  p75={pre['fp'].quantile(0.75):+.4f}")

in_dlv_all  = at_ok[at_ok['phase'] == 'in_dlv_2026']
in_dlv_test = in_dlv_all[~in_dlv_all['is_rn_adj']]
in_dlv_radj = in_dlv_all[in_dlv_all['is_rn_adj']]

n_test    = len(in_dlv_test)
n_match   = in_dlv_test['match_01'].sum()
match_pct = n_match / n_test * 100 if n_test > 0 else 0.0
passed    = match_pct >= 90.0

print(f"\n{'='*74}")
print(f"Haupt-Test: in_dlv_2026 exkl. rn_adj ({n_test} Zeilen)")
print(f"  Match (|Δ| ≤ 0,01 EUR): {n_match}/{n_test} = {match_pct:.1f} %")
print(f"  Erfolgskriterium ≥90 %: {'✓ BESTANDEN' if passed else '✗ NICHT BESTANDEN'}")
print(f"{'='*74}")

if len(in_dlv_radj) > 0:
    print(f"\nRN-Level-Adjustment in in_dlv_2026 ({len(in_dlv_radj)} — Gate-6 exkludiert):")
    rc = ['rn_str', 'plz_str', 'datum', 'tonnage',
          'basispreis', 'Erlöse Fracht', 'delta_fracht', 'fp', 'gate6_flag']
    print(in_dlv_radj[[c for c in rc if c in in_dlv_radj.columns]].head(10).to_string(index=False))

fails = in_dlv_test[~in_dlv_test['match_01']]
if len(fails) > 0:
    print(f"\nFAILURES ({len(fails)}):")
    fcols = ['rn_str', 'plz_str', 'datum', 'tonnage',
             'basispreis', 'Erlöse Fracht', 'delta_fracht', 'fp']
    print(fails[[c for c in fcols if c in fails.columns]].to_string(index=False))

# Maut check
print(f"\nMaut-Delta (|Erlöse_Maut − maut_soll|) — in_dlv_2026 Testset:")
md = in_dlv_test['delta_maut'].abs()
if len(md) > 0:
    print(f"  mean={md.mean():.4f}  p50={md.median():.4f}  "
          f"p95={md.quantile(0.95):.4f}  max={md.max():.4f}")
    print(f"  |maut_delta| ≤ 0,01: {(md <= 0.01).sum()}/{n_test}")

# Diesel check (not_contracted — should be 0)
print(f"\nDiesel-Check (not_contracted) — alle AT-Zeilen:")
diesel_zero = (at['Erlöse Diesel'].fillna(0) == 0).sum()
print(f"  Erlöse_Diesel = 0: {diesel_zero}/{n_total}  "
      f"({'✓ not_contracted bestätigt' if diesel_zero == n_total else '⚠ Einige Zeilen Diesel≠0 — prüfen!'})")

# Per-RN spot-check
print(f"\nPer-RN Spot-Check (in_dlv_2026):")
in_dlv_rns = in_dlv_all['rn_str'].unique()
print(f"  {'RN':<14} {'n_pos':>5} {'total_kg':>10} {'Fracht_BI':>10} {'Fracht_calc':>11} {'delta':>8} {'gate6'}")
for rn_id in sorted(in_dlv_rns):
    rn_rows     = in_dlv_all[in_dlv_all['rn_str'] == rn_id]
    fracht_bi   = rn_rows['Erlöse Fracht'].sum()
    fracht_calc = rn_rows['basispreis'].sum()
    delta       = fracht_bi - fracht_calc
    flag        = _gate6_flag(rn_id)
    total_kg    = at_pos[at_pos['rn_str'] == rn_id]['tonnage'].sum()
    print(f"  {rn_id:<14} {len(rn_rows):>5} {total_kg:>10.2f} {fracht_bi:>10.4f} "
          f"{fracht_calc:>11.4f} {delta:>8.4f}  {flag or 'exact_dlv'}")

# Zone distribution
print(f"\nZonen-Verteilung (in_dlv_2026):")
at_ok['zone'] = at_ok['plz_str'].apply(
    lambda p: int(str(calc._zone_ranges and
                      next((z for z, rs in calc._zone_ranges.items()
                            if any(lo <= int(p[:2]) <= hi for lo, hi in rs)), 0)))
    if calc._zone_ranges else 0
)

print(f"\nDone.")

if not passed:
    raise SystemExit(1)
