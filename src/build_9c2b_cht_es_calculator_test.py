#!/usr/bin/env python3
"""Etappe 9c.2b — CHTSpainCalculator Integration Test.

Prüft CHTSpainCalculator gegen tatsächliche BI-Zeilen (KNR 486073, POST, ES).
Erfolgskriterium: ≥90 % der in_dlv_2026-Zeilen (exkl. t_zero + rn_adj + §8)
haben |Erlöse_Fracht − basispreis| ≤ 0,01 EUR.

Phasen-Abgrenzung:
  in_dlv_2026  : Leistungsdatum ≥ 2026-01-01  → Calculator-Check aktiv
  pre_dlv_2026 : Leistungsdatum < 2026-01-01   → unbeurteilbar, 2025-DLV fehlt

Gate-6 RN-Level-Faktor-Detection (§6b v1.7):
  rn_std < 0.0005 + abs(rn_factor) ≥ 0.0005 → rn_level_adjustment
  Excluded from pass-rate; listed in §8.

Maut: 0.39 EUR × billing_kg / 100  (DE-Maut only; ES-Maut inklusive in Rates)
Diesel: not_contracted → Erlöse_Diesel = 0 für alle ES-Zeilen (bestätigt).

AX-Raten-Präzision: 2dp (§6c v1.7.2, empirisch 9c.2b).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

BASE = Path('/home/user/TMS')
sys.path.insert(0, str(BASE / 'src'))
import pickle  # noqa: E402
from tms.tariff.calculators.cht_es import CHTSpainCalculator  # noqa: E402

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
DLV_START_2026   = pd.Timestamp('2026-01-01')
RN_STD_THRESH    = 0.0005
ES_SPLIT_FLAT    = 35.89   # Zone 1 bis-100 EUR (lowest per-Sendung floor for split detection)

# §8 position-level outliers — mixed billing mechanisms in same Sendung/RN
KNOWN_S8: set[tuple[str, str]] = {
    ('924029', '46890'),  # 5 Pos. rn_adj -1.94% + 2 Pos. extreme Gewichts-Anomalie
                          # (3832.55 kg fp=-36%, 12334.23 kg fp=-13%); Gate-6 per_position
    ('924029', '08310'),  # Zone-1-Pos. desselben RN; gleicher -1.94%-Mechanismus
    ('924040', '46890'),  # analoges Muster: 7 Pos. mit Anomalien (1344/6762/9076/1190/15166 kg)
    ('924145', '46890'),  # 4 Split-Positionen (0.20–11.70 kg) + 2 Begleit-Pos.
                          # (21729 Δ=-1.15, 7145 Δ=-0.30)
}

# ---------------------------------------------------------------------------
# Load CHT ES rows
# ---------------------------------------------------------------------------
with open(BASE / 'output/bi_top20_data.pkl', 'rb') as f:
    bi = pickle.load(f)['df']


def rn_valid(x: object) -> bool:
    try:
        return float(str(x).replace(',', '.')) > 5
    except Exception:
        return False


es = bi[
    (bi['Kunden Nr BK'] == 486073) &
    (bi['periode'] == 'POST') &
    bi['Rechnungsnummer'].apply(rn_valid) &
    (bi['Erlöse Fracht'].fillna(0) > 0) &
    (bi['Empfänger Land'] == 'ES')
].copy()

es['datum']   = pd.to_datetime(es['Leistungsdatum'], errors='coerce')
es['phase']   = es['datum'].apply(
    lambda d: 'in_dlv_2026' if pd.notna(d) and d >= DLV_START_2026 else 'pre_dlv_2026'
)
es['rn_str']  = es['Rechnungsnummer'].astype(str).str.strip()
es['plz_str'] = es['Empfänger PLZ'].astype(str).str.strip()
es['tonnage'] = es['Tonnage (eff.)'].fillna(0)
es['is_t0']    = es['tonnage'] <= 0
es['is_split'] = (
    (es['tonnage'] > 0) &
    (es['tonnage'] <= 100) &
    (es['Erlöse Fracht'] < ES_SPLIT_FLAT * 0.5)
)
es['is_s8']   = es.apply(lambda r: (r['rn_str'], r['plz_str']) in KNOWN_S8, axis=1)

# ---------------------------------------------------------------------------
# Run Calculator (tonnage > 0 only)
# ---------------------------------------------------------------------------
calc = CHTSpainCalculator()
es_pos = es[~es['is_t0']].copy()

bp_list, maut_list, ok_list, err_list = [], [], [], []
for _, row in es_pos.iterrows():
    try:
        res = calc.calculate(
            empf_plz=row['plz_str'],
            empf_land='ES',
            tonnage_kg=float(row['tonnage']),
        )
        bp_list.append(float(res.basispreis))
        maut_list.append(float(res.maut_surcharge))
        ok_list.append(True)
        err_list.append('')
    except Exception as e:
        bp_list.append(float('nan'))
        maut_list.append(float('nan'))
        ok_list.append(False)
        err_list.append(str(e))

es_pos = es_pos.copy()
es_pos['basispreis'] = bp_list
es_pos['maut_soll']  = maut_list
es_pos['calc_ok']    = ok_list
es_pos['calc_err']   = err_list

es_ok = es_pos[es_pos['calc_ok']].copy()
es_ok['delta_fracht'] = es_ok['Erlöse Fracht'] - es_ok['basispreis']
es_ok['delta_maut']   = es_ok['Erlöse Maut'] - es_ok['maut_soll']
es_ok['fp']           = es_ok['delta_fracht'] / es_ok['basispreis']
es_ok['match_01']     = es_ok['delta_fracht'].abs() <= 0.01
es_ok['is_s8']        = es_ok.apply(lambda r: (r['rn_str'], r['plz_str']) in KNOWN_S8, axis=1)

# ---------------------------------------------------------------------------
# Gate 6: RN-Level-Faktor-Detection (§6b v1.7)
# ---------------------------------------------------------------------------
rn_stats = (
    es_ok.groupby('rn_str')['fp']
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


es_ok['gate6_flag'] = es_ok['rn_str'].apply(_gate6_flag)
es_ok['is_rn_adj']  = es_ok['gate6_flag'] == 'rn_level_adjustment'
es_ok['is_split']   = es_ok.apply(
    lambda r: r['tonnage'] > 0 and r['tonnage'] <= 100 and r['Erlöse Fracht'] < ES_SPLIT_FLAT * 0.5,
    axis=1
)

# ---------------------------------------------------------------------------
# Print summary
# ---------------------------------------------------------------------------
print('=' * 74)
print('=== 9c.2b CHTSpainCalculator INTEGRATION TEST ===')
print('=' * 74)

n_total   = len(es)
n_t0      = es['is_t0'].sum()
n_split   = es['is_split'].sum()
n_s8      = es['is_s8'].sum()
n_calc_ok = len(es_ok)
n_rn_adj  = es_ok['is_rn_adj'].sum()
n_exact   = (es_ok['gate6_flag'] == 'exact_dlv').sum()

print(f"\nGesamt ES-Zeilen (KNR 486073, POST, Fracht>0): {n_total}")
print(f"  Tonnage=0 (t_zero):          {n_t0}")
print(f"  Split-Positionen (excl flag): {n_split}  "
      f"(0<t≤100, Fracht<{ES_SPLIT_FLAT*0.5:.2f})")
print(f"  §8-Ausreißer (KNOWN_S8):     {n_s8}  (exkl. von Erfolgsquote)")
print(f"  Calculator OK (tonnage>0):   {n_calc_ok}")
print(f"  Calculator FAIL:             {(~es_pos['calc_ok']).sum()}")
if (es_pos['calc_err'] != '').any():
    print("  Fehler:")
    for e in es_pos[es_pos['calc_err'] != '']['calc_err'].unique():
        print(f"    {e}")

print(f"\nGate-6 RN-Level-Faktor-Klassifikation:")
for rn in sorted(rn_stats.index):
    flag = _gate6_flag(rn)
    f = float(rn_stats.loc[rn, 'rn_factor'])
    s = float(rn_stats.loc[rn, 'rn_std'])
    n_rn = int((es_ok['rn_str'] == rn).sum())
    print(f"  RN {rn}: factor={f:+.6f}  std={s:.6f}  n={n_rn}  → {flag or 'per_position'}")
print(f"  rn_level_adjustment: {n_rn_adj} Positionen (exkl. von Erfolgsquote)")
print(f"  exact_dlv:           {n_exact} Positionen")

n_pre    = (es_ok['phase'] == 'pre_dlv_2026').sum()
n_in_dlv = (es_ok['phase'] == 'in_dlv_2026').sum()

print(f"\nPhasen-Split ({n_calc_ok} Zeilen mit Tonnage>0):")
print(f"  in_dlv_2026  : {n_in_dlv}   (Haupt-Test-Set)")
print(f"  pre_dlv_2026 : {n_pre}   (unbeurteilbar — 2025-DLV fehlt)")

# pre_dlv summary
pre = es_ok[es_ok['phase'] == 'pre_dlv_2026']
if len(pre) > 0:
    print(f"\nPre-DLV-2026 ({len(pre)} Zeilen, KEIN Calculator-Check):")
    print(f"  fp-Verteilung (ggü. 2026-DLV, informativ):")
    print(f"    mean={pre['fp'].mean():+.4f}  std={pre['fp'].std():.4f}  "
          f"p25={pre['fp'].quantile(0.25):+.4f}  p75={pre['fp'].quantile(0.75):+.4f}")

# Main test: in_dlv_2026, not split_pos, not §8, not rn_adj
in_dlv_all   = es_ok[es_ok['phase'] == 'in_dlv_2026']
in_dlv_test  = in_dlv_all[
    ~in_dlv_all['is_split'] & ~in_dlv_all['is_s8'] & ~in_dlv_all['is_rn_adj']
]
in_dlv_split  = in_dlv_all[in_dlv_all['is_split']]
in_dlv_s8     = in_dlv_all[in_dlv_all['is_s8'] & ~in_dlv_all['is_split']]
in_dlv_rnadj  = in_dlv_all[in_dlv_all['is_rn_adj']]

n_test    = len(in_dlv_test)
n_match   = in_dlv_test['match_01'].sum()
match_pct = n_match / n_test * 100 if n_test > 0 else 0.0
passed    = match_pct >= 90.0

print(f"\n{'='*74}")
print(f"Haupt-Test: in_dlv_2026 exkl. split_pos + §8 + rn_adj ({n_test} Zeilen)")
print(f"  Match (|Δ| ≤ 0,01 EUR): {n_match}/{n_test} = {match_pct:.1f} %")
print(f"  Erfolgskriterium ≥90 %: {'✓ BESTANDEN' if passed else '✗ NICHT BESTANDEN'}")
print(f"{'='*74}")

if len(in_dlv_split) > 0:
    print(f"\nSplit-Positionen in in_dlv_2026 ({len(in_dlv_split)} — exkludiert):")
    sc = ['Rechnungsnummer','plz_str','datum','tonnage','basispreis','Erlöse Fracht','delta_fracht','fp']
    print(in_dlv_split[[c for c in sc if c in in_dlv_split.columns]].to_string(index=False))

if len(in_dlv_s8) > 0:
    print(f"\n§8-Ausreißer in in_dlv_2026 ({len(in_dlv_s8)} — exkludiert, exkl. Splits):")
    sc = ['Rechnungsnummer','plz_str','datum','tonnage','basispreis','Erlöse Fracht','delta_fracht','fp']
    print(in_dlv_s8[[c for c in sc if c in in_dlv_s8.columns]].to_string(index=False))

if len(in_dlv_rnadj) > 0:
    print(f"\nRN-Level-Adjustment in in_dlv_2026 ({len(in_dlv_rnadj)} — Gate-6 exkludiert):")
    rc = ['Rechnungsnummer','plz_str','datum','tonnage','basispreis','Erlöse Fracht','delta_fracht','fp','gate6_flag']
    print(in_dlv_rnadj[[c for c in rc if c in in_dlv_rnadj.columns]].head(12).to_string(index=False))
    if len(in_dlv_rnadj) > 12:
        print(f"  ... (+{len(in_dlv_rnadj)-12} weitere)")

fails = in_dlv_test[~in_dlv_test['match_01']]
if len(fails) > 0:
    print(f"\nFAILURES ({len(fails)}):")
    fcols = ['Rechnungsnummer','plz_str','datum','tonnage',
             'basispreis','Erlöse Fracht','delta_fracht','fp']
    print(fails[[c for c in fcols if c in fails.columns]].to_string(index=False))

# Maut check
print(f"\nMaut-Delta (|Erlöse_Maut − maut_soll|) — in_dlv_2026 Testset:")
md = in_dlv_test['delta_maut'].abs()
if len(md) > 0:
    print(f"  mean={md.mean():.4f}  p50={md.median():.4f}  "
          f"p95={md.quantile(0.95):.4f}  max={md.max():.4f}")
    print(f"  |maut_delta| ≤ 0,01: {(md <= 0.01).sum()}/{n_test}")

# Diesel check (should be all zero)
print(f"\nDiesel-Check (not_contracted) — alle ES-Zeilen:")
diesel_nonzero = (es['Erlöse Diesel'].fillna(0) != 0).sum()
print(f"  Erlöse_Diesel ≠ 0: {diesel_nonzero}/{n_total}  ({'✓ BESTANDEN (alle zero)' if diesel_nonzero == 0 else '✗ Diesel-Buchungen gefunden — prüfen!'})")

print(f"\nDone.")
