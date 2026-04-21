#!/usr/bin/env python3
"""Etappe 9c.2c — CHTGreeceCalculator Integration Test.

billing_scope = "rn": Alle Positionen einer RN als Aggregat.
  HL: einmalig pro RN (total_kg → billing_kg → rate × bk/100, min 46.63)
  NL: pro Empfänger-Gruppe = (RN, Empfänger_Name) (group_kg → zone → rate)
  Maut: 0.56 EUR × RN_billing_kg / 100 (DE-Maut only)
  Alle Beträge pro-rated by actual_kg auf Positions-Ebene.

Erfolgskriterium: ≥90 % der in_dlv_2026-Zeilen (exkl. t_zero + rn_adj)
haben |Erlöse_Fracht − basispreis_prorated| ≤ 0,01 EUR.

DLV-QA-Finding:
  Sheet heißt "Export Österreich" — Inhalt ist Griechenland.
  Klärungsfrage an Operations (§8-Doku-Hinweis).

Zone 1 = "bis 50 km" (Default); Zonen 2-4 per Explicit-PLZ-Liste.
AX-Raten-Präzision: 2dp (§6c v1.7.2, empirisch 9c.2c — |Δ|<0,001 EUR).
Diesel: contracted → Erlöse_Diesel ≠ 0 für alle GR-Zeilen (check informativ).
"""
from __future__ import annotations

import sys
import pickle
from pathlib import Path

import pandas as pd

BASE = Path('/home/user/TMS')
sys.path.insert(0, str(BASE / 'src'))
from tms.tariff.calculators.cht_gr import CHTGreeceCalculator  # noqa: E402
from tms.tariff.base import RNPosition                          # noqa: E402

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
DLV_START_2026  = pd.Timestamp('2026-01-01')
RN_STD_THRESH   = 0.0005

# ---------------------------------------------------------------------------
# Load CHT GR rows
# ---------------------------------------------------------------------------
with open(BASE / 'output/bi_top20_data.pkl', 'rb') as f:
    bi = pickle.load(f)['df']


def rn_valid(x: object) -> bool:
    try:
        return float(str(x).replace(',', '.')) > 5
    except Exception:
        return False


gr = bi[
    (bi['Kunden Nr BK'] == 486073) &
    (bi['periode'] == 'POST') &
    bi['Rechnungsnummer'].apply(rn_valid) &
    (bi['Erlöse Fracht'].fillna(0) > 0) &
    (bi['Empfänger Land'] == 'GR')
].copy()

gr['datum']    = pd.to_datetime(gr['Leistungsdatum'], errors='coerce')
gr['phase']    = gr['datum'].apply(
    lambda d: 'in_dlv_2026' if pd.notna(d) and d >= DLV_START_2026 else 'pre_dlv_2026'
)
gr['rn_str']   = gr['Rechnungsnummer'].astype(str).str.strip()
gr['plz_str']  = gr['Empfänger PLZ'].astype(str).str.strip().str.replace(' ', '').str.replace('-', '')
gr['tonnage']  = gr['Tonnage (eff.)'].fillna(0)
gr['is_t0']    = gr['tonnage'] <= 0
gr['empf_name'] = gr['Empfänger Name'].astype(str).str.strip()

# ---------------------------------------------------------------------------
# Run Calculator (all positions; grouped by RN)
# ---------------------------------------------------------------------------
calc = CHTGreeceCalculator()
gr_pos = gr[~gr['is_t0']].copy()

# Build per-position result dicts
bp_list, maut_list, ok_list, err_list = (
    [None] * len(gr_pos), [None] * len(gr_pos),
    [False] * len(gr_pos), [''] * len(gr_pos)
)
idx_list = list(gr_pos.index)

for rn_id, rn_group in gr_pos.groupby('rn_str'):
    positions = [
        RNPosition(
            position_id=idx,
            empf_plz=row['plz_str'],
            empf_land='GR',
            empfaenger_name=row['empf_name'],
            actual_kg=float(row['tonnage']),
        )
        for idx, row in rn_group.iterrows()
    ]
    try:
        results = calc.calc_rn(positions)
        for pos in positions:
            res = results[pos.position_id]
            i   = idx_list.index(pos.position_id)
            bp_list[i]   = float(res.basispreis)
            maut_list[i] = float(res.maut_surcharge)
            ok_list[i]   = True
    except Exception as e:
        err = str(e)
        for pos in positions:
            i = idx_list.index(pos.position_id)
            err_list[i] = err

gr_pos = gr_pos.copy()
gr_pos['basispreis'] = bp_list
gr_pos['maut_soll']  = maut_list
gr_pos['calc_ok']    = ok_list
gr_pos['calc_err']   = err_list

gr_ok = gr_pos[gr_pos['calc_ok']].copy()
gr_ok['delta_fracht'] = gr_ok['Erlöse Fracht'] - gr_ok['basispreis']
gr_ok['delta_maut']   = gr_ok['Erlöse Maut']   - gr_ok['maut_soll']
gr_ok['fp']           = gr_ok['delta_fracht']   / gr_ok['basispreis']
gr_ok['match_01']     = gr_ok['delta_fracht'].abs() <= 0.01

# ---------------------------------------------------------------------------
# Gate 6: RN-Level-Faktor-Detection (§6b v1.7)
# Note: For billing_scope="rn" the calculator already handles RN-level
# aggregation. Gate 6 here catches any residual systematic per-RN adjustment
# (e.g. quarterly pricing factor applied on top of the two-stage rates).
# ---------------------------------------------------------------------------
rn_stats = (
    gr_ok.groupby('rn_str')['fp']
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


gr_ok['gate6_flag'] = gr_ok['rn_str'].apply(_gate6_flag)
gr_ok['is_rn_adj']  = gr_ok['gate6_flag'] == 'rn_level_adjustment'

# ---------------------------------------------------------------------------
# Print summary
# ---------------------------------------------------------------------------
print('=' * 74)
print('=== 9c.2c CHTGreeceCalculator INTEGRATION TEST ===')
print('=' * 74)
print('  billing_scope = "rn"  |  HL einmalig / NL pro Empfänger-Gruppe')
print('  Prorating by actual_kg  |  AX-Präzision 2dp')

n_total    = len(gr)
n_t0       = gr['is_t0'].sum()
n_calc_ok  = len(gr_ok)
n_rn_adj   = gr_ok['is_rn_adj'].sum()
n_exact    = (gr_ok['gate6_flag'] == 'exact_dlv').sum()

print(f"\nGesamt GR-Zeilen (KNR 486073, POST, Fracht>0): {n_total}")
print(f"  Tonnage=0 (t_zero):        {n_t0}")
print(f"  Calculator OK (tonnage>0): {n_calc_ok}")
print(f"  Calculator FAIL:           {(~gr_pos['calc_ok']).sum()}")
if (gr_pos['calc_err'] != '').any():
    print("  Fehler:")
    for e in gr_pos[gr_pos['calc_err'] != '']['calc_err'].unique():
        print(f"    {e}")

print(f"\nGate-6 RN-Level-Faktor-Klassifikation (Residuen nach RN-Level-Calc):")
for rn in sorted(rn_stats.index):
    flag = _gate6_flag(rn)
    f = float(rn_stats.loc[rn, 'rn_factor'])
    s = float(rn_stats.loc[rn, 'rn_std'])
    n_rn = int((gr_ok['rn_str'] == rn).sum())
    print(f"  RN {rn}: factor={f:+.6f}  std={s:.6f}  n={n_rn}  → {flag or 'per_position'}")
print(f"  rn_level_adjustment: {n_rn_adj} Positionen (exkl. von Erfolgsquote)")
print(f"  exact_dlv:           {n_exact} Positionen")

n_pre    = (gr_ok['phase'] == 'pre_dlv_2026').sum()
n_in_dlv = (gr_ok['phase'] == 'in_dlv_2026').sum()

print(f"\nPhasen-Split ({n_calc_ok} Zeilen mit Tonnage>0):")
print(f"  in_dlv_2026  : {n_in_dlv}   (Haupt-Test-Set)")
print(f"  pre_dlv_2026 : {n_pre}   (unbeurteilbar — 2025-DLV fehlt)")

# pre_dlv summary (informational)
pre = gr_ok[gr_ok['phase'] == 'pre_dlv_2026']
if len(pre) > 0:
    print(f"\nPre-DLV-2026 ({len(pre)} Zeilen, KEIN Calculator-Check):")
    print(f"  fp-Verteilung (ggü. 2026-DLV, informativ):")
    print(f"    mean={pre['fp'].mean():+.4f}  std={pre['fp'].std():.4f}  "
          f"p25={pre['fp'].quantile(0.25):+.4f}  p75={pre['fp'].quantile(0.75):+.4f}")

# Main test
in_dlv_all  = gr_ok[gr_ok['phase'] == 'in_dlv_2026']
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
    rc = ['rn_str', 'plz_str', 'empf_name', 'datum', 'tonnage',
          'basispreis', 'Erlöse Fracht', 'delta_fracht', 'fp', 'gate6_flag']
    print(in_dlv_radj[[c for c in rc if c in in_dlv_radj.columns]].head(10).to_string(index=False))

fails = in_dlv_test[~in_dlv_test['match_01']]
if len(fails) > 0:
    print(f"\nFAILURES ({len(fails)}):")
    fcols = ['rn_str', 'plz_str', 'empf_name', 'datum', 'tonnage',
             'basispreis', 'Erlöse Fracht', 'delta_fracht', 'fp']
    print(fails[[c for c in fcols if c in fails.columns]].to_string(index=False))

# Maut check
print(f"\nMaut-Delta (|Erlöse_Maut − maut_prorated|) — in_dlv_2026 Testset:")
md = in_dlv_test['delta_maut'].abs()
if len(md) > 0:
    print(f"  mean={md.mean():.4f}  p50={md.median():.4f}  "
          f"p95={md.quantile(0.95):.4f}  max={md.max():.4f}")
    print(f"  |maut_delta| ≤ 0,01: {(md <= 0.01).sum()}/{n_test}")

# Diesel check (contracted — should be non-zero)
print(f"\nDiesel-Check (contracted) — alle GR-Zeilen:")
diesel_nonzero = (gr['Erlöse Diesel'].fillna(0) != 0).sum()
print(f"  Erlöse_Diesel ≠ 0: {diesel_nonzero}/{n_total}  "
      f"({'✓ contracted bestätigt' if diesel_nonzero == n_total else '⚠ Einige Zeilen Diesel=0 — prüfen!'})")

# Per-RN spot-check table (all in_dlv RNs)
print(f"\nPer-RN Spot-Check (in_dlv_2026):")
in_dlv_rns = in_dlv_all['rn_str'].unique()
print(f"  {'RN':<14} {'n_pos':>5} {'total_kg':>10} {'Fracht_BI':>10} {'Fracht_calc':>11} {'delta':>8} {'gate6'}")
for rn_id in sorted(in_dlv_rns):
    rn_rows = in_dlv_all[in_dlv_all['rn_str'] == rn_id]
    fracht_bi   = rn_rows['Erlöse Fracht'].sum()
    fracht_calc = rn_rows['basispreis'].sum()
    delta       = fracht_bi - fracht_calc
    flag        = _gate6_flag(rn_id)
    total_kg    = gr_pos[gr_pos['rn_str'] == rn_id]['tonnage'].sum()
    print(f"  {rn_id:<14} {len(rn_rows):>5} {total_kg:>10.2f} {fracht_bi:>10.4f} "
          f"{fracht_calc:>11.4f} {delta:>8.4f}  {flag or 'exact_dlv'}")

print(f"\nDone.")
