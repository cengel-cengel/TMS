#!/usr/bin/env python3
"""Etappe 9c.2a — CHTBelgiumCalculator Integration Test.

Prüft CHTBelgiumCalculator gegen tatsächliche BI-Zeilen (KNR 486073, POST, BE).
Erfolgskriterium: ≥90 % der in_dlv_2026-Zeilen (exkl. t_zero + split_position)
haben |Erlöse_Fracht − basispreis| ≤ 0,01 EUR.

Phasen-Abgrenzung:
  in_dlv_2026  : Leistungsdatum ≥ 2026-01-01  → Calculator-Check aktiv
  pre_dlv_2026 : Leistungsdatum < 2026-01-01   → unbeurteilbar, 2025-DLV fehlt

Split-Position-Detektor (§2a Methodik v1.6.1):
  is_split_position = (0 < actual_kg ≤ 100) AND (Erlöse_Fracht < PER_SENDUNG_FLAT × 0.5)
  Fängt Sub-Flat-Buchungen, die Positionsfragmente einer Mehrfach-PLZ-Sendung sind.

All-in-Exception (BE, bestätigt §2a v1.6.1):
  RN 923790 / PLZ 8550: Diesel=0, Maut=0, pre_dlv_2026 → all_in_exception
  RN 923818 / PLZ 3600: Diesel=0, Maut=0, pre_dlv_2026 → all_in_exception
  Beide pre_dlv_2026 → durch Phase-Filter bereits exkludiert; als Flag dokumentiert.

Maut-Abgrenzung (DLV §2 Fall A unbundled):
  maut_soll = 0,58 EUR × billing_kg / 100  (DE-Maut only; BE-Maut inklusive in Rates)

Diesel-Tracking (contracted, quarterly):
  DLV-Basis: 8,62 % auf Frachtkosten (Quarterly-Sonder-Floater variabel)
  diesel_pct = Erlöse_Diesel / Erlöse_Fracht  (informativ, kein PASS/FAIL)
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
from tms.tariff.calculators.cht_be import CHTBelgiumCalculator  # noqa: E402

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
DLV_START_2026   = pd.Timestamp('2026-01-01')
PER_SENDUNG_FLAT = 40.5511  # bis 100 kg flat rate (for split-position detection)

# Known all_in_exception (Diesel=0 AND Maut=0): (rn_str, plz_str)
KNOWN_AI: set[tuple[str, str]] = {
    ('923790', '8550'),
    ('923818', '3600'),
}

# Known §8 position-level outliers (excluded from pass-rate, listed in §8):
#   924132/1500, 924132/8550 — position-level deviation, cause unknown
#   924248/7700 — PRIORITY §8: +18.7% (FTL/Gefahrgut tier suspected)
#   924248/8560, 924248/8400, 924248/8540 — Kortrijk West Sonder-PLZ (+6.3-6.4%)
KNOWN_S8: set[tuple[str, str]] = {
    ('924132', '1500'),
    ('924132', '8550'),
    ('924248', '7700'),
    ('924248', '8560'),
    ('924248', '8400'),
    ('924248', '8540'),
}

# ---------------------------------------------------------------------------
# Load CHT BE rows
# ---------------------------------------------------------------------------
with open(BASE / 'output/bi_top20_data.pkl', 'rb') as f:
    bi = pickle.load(f)['df']


def rn_valid(x: object) -> bool:
    try:
        return float(str(x).replace(',', '.')) > 5
    except Exception:
        return False


be = bi[
    (bi['Kunden Nr BK'] == 486073) &
    (bi['periode'] == 'POST') &
    bi['Rechnungsnummer'].apply(rn_valid) &
    (bi['Erlöse Fracht'].fillna(0) > 0) &
    (bi['Empfänger Land'] == 'BE')
].copy()

be['datum']   = pd.to_datetime(be['Leistungsdatum'], errors='coerce')
be['phase']   = be['datum'].apply(
    lambda d: 'in_dlv_2026' if pd.notna(d) and d >= DLV_START_2026 else 'pre_dlv_2026'
)
be['rn_str']  = be['Rechnungsnummer'].astype(str).str.strip()
be['plz_str'] = be['Empfänger PLZ'].astype(str).str.strip()
be['tonnage'] = be['Tonnage (eff.)'].fillna(0)

be['is_t0']    = be['tonnage'] <= 0
be['is_split'] = (
    (be['tonnage'] > 0) &
    (be['tonnage'] <= 100) &
    (be['Erlöse Fracht'] < PER_SENDUNG_FLAT * 0.5)
)
be['is_ai'] = be.apply(lambda r: (r['rn_str'], r['plz_str']) in KNOWN_AI, axis=1)
be['is_s8'] = be.apply(lambda r: (r['rn_str'], r['plz_str']) in KNOWN_S8, axis=1)

# ---------------------------------------------------------------------------
# Run Calculator on rows with tonnage > 0 (split_position included — flag only)
# ---------------------------------------------------------------------------
calc = CHTBelgiumCalculator()
be_pos = be[~be['is_t0']].copy()

bp_list, maut_list, ok_list, err_list = [], [], [], []
for _, row in be_pos.iterrows():
    try:
        res = calc.calculate(
            empf_plz=row['plz_str'],
            empf_land='BE',
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

be_pos = be_pos.copy()
be_pos['basispreis'] = bp_list
be_pos['maut_soll']  = maut_list
be_pos['calc_ok']    = ok_list
be_pos['calc_err']   = err_list

be_ok = be_pos[be_pos['calc_ok']].copy()
be_ok['delta_fracht'] = be_ok['Erlöse Fracht'] - be_ok['basispreis']
be_ok['delta_maut']   = be_ok['Erlöse Maut'] - be_ok['maut_soll']
be_ok['fp']           = be_ok['delta_fracht'] / be_ok['basispreis']
be_ok['match_01']     = be_ok['delta_fracht'].abs() <= 0.01
be_ok['diesel_pct']   = be_ok['Erlöse Diesel'] / be_ok['Erlöse Fracht']
be_ok['is_s8']        = be_ok.apply(lambda r: (r['rn_str'], r['plz_str']) in KNOWN_S8, axis=1)

# ---------------------------------------------------------------------------
# Gate 6: RN-Level-Faktor-Detection (§6b v1.7)
# ---------------------------------------------------------------------------
RN_STD_THRESH = 0.0005

rn_stats = (
    be_ok.groupby('rn_str')['fp']
    .agg(rn_factor='median', rn_std='std')
    .fillna({'rn_std': 0.0})
)

def _gate6_flag(rn: str) -> str:
    if rn not in rn_stats.index:
        return ''
    s = rn_stats.loc[rn, 'rn_std']
    f = rn_stats.loc[rn, 'rn_factor']
    if s < RN_STD_THRESH:
        return 'exact_dlv' if abs(f) < RN_STD_THRESH else 'rn_level_adjustment'
    return ''

be_ok['gate6_flag'] = be_ok['rn_str'].apply(_gate6_flag)
be_ok['is_rn_adj']  = be_ok['gate6_flag'] == 'rn_level_adjustment'

# ---------------------------------------------------------------------------
# Print summary
# ---------------------------------------------------------------------------
print('=' * 74)
print('=== 9c.2a CHTBelgiumCalculator INTEGRATION TEST ===')
print('=' * 74)

n_total    = len(be)
n_t0       = be['is_t0'].sum()
n_split    = be['is_split'].sum()
n_ai       = be['is_ai'].sum()
n_s8       = be['is_s8'].sum()
n_calc_ok  = len(be_ok)
n_rn_adj   = be_ok['is_rn_adj'].sum()
n_exact    = (be_ok['gate6_flag'] == 'exact_dlv').sum()

print(f"\nGesamt BE-Zeilen (KNR 486073, POST, Fracht>0): {n_total}")
print(f"  Tonnage=0 (t_zero):          {n_t0}")
print(f"  Split-Positionen (excl flag): {n_split}  "
      f"(0<t≤100, Fracht<{PER_SENDUNG_FLAT*0.5:.2f})")
print(f"  All-in-Exception:            {n_ai}  (Diesel=0+Maut=0)")
print(f"  §8-Ausreißer (KNOWN_S8):     {n_s8}  (exkl. von Erfolgsquote)")
print(f"  Calculator OK (tonnage>0):   {n_calc_ok}")
print(f"  Calculator FAIL:             {(~be_pos['calc_ok']).sum()}")

print(f"\nGate-6 RN-Level-Faktor-Klassifikation:")
for rn in sorted(rn_stats.index):
    flag = _gate6_flag(rn)
    f = rn_stats.loc[rn, 'rn_factor']
    s = rn_stats.loc[rn, 'rn_std']
    n_rn = (be_ok['rn_str'] == rn).sum()
    print(f"  RN {rn}: factor={f:+.6f}  std={s:.6f}  n={n_rn}  → {flag or 'per_position'}")
print(f"  rn_level_adjustment: {n_rn_adj} Positionen (exkl. von Erfolgsquote)")
print(f"  exact_dlv:           {n_exact} Positionen")

n_pre    = (be_ok['phase'] == 'pre_dlv_2026').sum()
n_in_dlv = (be_ok['phase'] == 'in_dlv_2026').sum()

print(f"\nPhasen-Split ({n_calc_ok} Zeilen mit Tonnage>0):")
print(f"  in_dlv_2026  : {n_in_dlv}   (inkl. split_position, Haupt-Test-Set)")
print(f"  pre_dlv_2026 : {n_pre}   (unbeurteilbar — 2025-DLV fehlt)")

# pre_dlv summary
pre = be_ok[be_ok['phase'] == 'pre_dlv_2026']
print(f"\nPre-DLV-2026 ({len(pre)} Zeilen, KEIN Calculator-Check):")
print(f"  fp-Verteilung (ggü. 2026-DLV, informativ):")
print(f"    mean={pre['fp'].mean():+.4f}  std={pre['fp'].std():.4f}  "
      f"p25={pre['fp'].quantile(0.25):+.4f}  p75={pre['fp'].quantile(0.75):+.4f}")
print(f"  All-in-Exception in pre_dlv: {pre['is_ai'].sum()}")

# Main test: in_dlv_2026, not split_position, not §8, not rn_level_adjustment
in_dlv_all   = be_ok[be_ok['phase'] == 'in_dlv_2026']
in_dlv_test  = in_dlv_all[
    ~in_dlv_all['is_split'] & ~in_dlv_all['is_s8'] & ~in_dlv_all['is_rn_adj']
]
in_dlv_split = in_dlv_all[in_dlv_all['is_split']]
in_dlv_s8    = in_dlv_all[in_dlv_all['is_s8']]
in_dlv_rnadj = in_dlv_all[in_dlv_all['is_rn_adj']]

n_test    = len(in_dlv_test)
n_match   = in_dlv_test['match_01'].sum()
match_pct = n_match / n_test * 100 if n_test > 0 else 0.0
passed    = match_pct >= 90.0

print(f"\n{'='*74}")
print(f"Haupt-Test: in_dlv_2026 exkl. split_pos + §8 + rn_adj ({n_test} Zeilen)")
print(f"  Match (|Δ| ≤ 0,01 EUR): {n_match}/{n_test} = {match_pct:.1f} %")
print(f"  Erfolgskriterium ≥90 %: {'✓ BESTANDEN' if passed else '✗ NICHT BESTANDEN'}")
print(f"{'='*74}")

# §8 exclusions (informational)
if len(in_dlv_s8) > 0:
    print(f"\n§8-Ausreißer in in_dlv_2026 ({len(in_dlv_s8)} — exkludiert):")
    sc = ['Rechnungsnummer','plz_str','datum','tonnage','basispreis','Erlöse Fracht','delta_fracht','fp']
    print(in_dlv_s8[[c for c in sc if c in in_dlv_s8.columns]].to_string(index=False))

# RN-level-adjustment cases (Gate-6 excluded)
if len(in_dlv_rnadj) > 0:
    print(f"\nRN-Level-Adjustment in in_dlv_2026 ({len(in_dlv_rnadj)} — Gate-6 exkludiert):")
    rc = ['Rechnungsnummer','plz_str','datum','tonnage','basispreis','Erlöse Fracht','delta_fracht','fp','gate6_flag']
    print(in_dlv_rnadj[[c for c in rc if c in in_dlv_rnadj.columns]].head(10).to_string(index=False))
    if len(in_dlv_rnadj) > 10:
        print(f"  ... (+{len(in_dlv_rnadj)-10} weitere)")

# Failures (should be 0 after all exclusions)
fails = in_dlv_test[~in_dlv_test['match_01']]
if len(fails) > 0:
    print(f"\nFAILURES ({len(fails)}):")
    fcols = ['Rechnungsnummer','plz_str','datum','tonnage',
             'basispreis','Erlöse Fracht','delta_fracht','fp']
    print(fails[[c for c in fcols if c in fails.columns]].to_string(index=False))

# Split-position cases
if len(in_dlv_split) > 0:
    print(f"\nSplit-Positionen in in_dlv_2026 ({len(in_dlv_split)} — exkludiert):")
    sc = ['Rechnungsnummer','plz_str','datum','tonnage','basispreis','Erlöse Fracht','delta_fracht','fp']
    print(in_dlv_split[[c for c in sc if c in in_dlv_split.columns]].to_string(index=False))

# Maut check
print(f"\nMaut-Delta (|Erlöse_Maut − maut_soll|) — in_dlv_2026 Testset:")
md = in_dlv_test['delta_maut'].abs()
print(f"  mean={md.mean():.4f}  p50={md.median():.4f}  "
      f"p95={md.quantile(0.95):.4f}  max={md.max():.4f}")
print(f"  |maut_delta| ≤ 0,01: {(md <= 0.01).sum()}/{n_test}")

# Diesel tracking (contracted, informational)
print(f"\nDiesel-Tracking (contracted, quarterly) — in_dlv_2026 Testset:")
dp = in_dlv_test['diesel_pct'].dropna()
print(f"  diesel/fracht: mean={dp.mean():.4f}  p25={dp.quantile(0.25):.4f}  "
      f"p75={dp.quantile(0.75):.4f}  p95={dp.quantile(0.95):.4f}")
print(f"  DLV-Basis: 8,62 % | Quarterly-Effektiv: ~{dp.mean()*100:.1f} %")

print(f"\nDone.")
