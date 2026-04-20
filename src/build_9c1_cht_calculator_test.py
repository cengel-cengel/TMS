#!/usr/bin/env python3
"""Etappe 9c.1 — CHT Italy Calculator Integration Test.

Prüft CHTItalyCalculator gegen tatsächliche BI-Zeilen (KNR 486073, POST, IT).
Erfolgskriterium: ≥90 % der in_dlv_2026-Zeilen (exkl. bekannte §8-Fälle)
haben |Erlöse_Fracht − basispreis| ≤ 0,01 EUR.

Phasen-Abgrenzung:
  in_dlv_2026     : Leistungsdatum ≥ 2026-01-01  → Calculator-Check aktiv
  pre_dlv_2026    : Leistungsdatum < 2026-01-01   → unbeurteilbar, 2025-DLV fehlt

§8-Bekannte-Fälle (aus Ausreißer-Analyse 9c.0 B-Check):
  Werden im Test separat ausgewiesen, gehen nicht in die Match-Quote ein.
  RN 4251024551 (fp=+1,325): KNR-verifiziert in BI, bleibt §8-Klärungsfrage.

Maut-Abgrenzung (§2 v1.5 Fall A unbundled):
  maut_soll = 0,56 EUR × billing_kg / 100
  maut_delta = Erlöse_Maut − maut_soll  (separat; nicht in fp)
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
from tms.tariff.calculators.cht import CHTItalyCalculator  # noqa: E402

# ---------------------------------------------------------------------------
# §8 bekannte Ausreißer — (rn, plz, tonnage_approx) Tupel
# Matching: RN + PLZ, bei Duplikaten (gleiche RN+PLZ) alle
# ---------------------------------------------------------------------------
KNOWN_S8: set[tuple[str, str]] = {
    ('923847',      '20098'),   # 11,2 kg Fast-Null-Buchung
    ('923957',      '59100'),   # 1013 kg + 4355 kg Dual-Mode-Grenzfall
    ('923981',      '59100'),   # 1012 kg + 6353 kg
    ('924020',      '59100'),   # 250 kg + 9297 kg
    ('923981',      '20098'),   # 1548 kg + 5928 kg Sonder-PLZ pre_dlv
    ('924068',      '75015'),   # +0,006 mild
    ('924249',      '20098'),   # +0,061 Sonder-PLZ in_dlv
    ('924249',      '22063'),   # +0,063 Zone1 in_dlv
    ('4251024551',  '13866'),   # +1,325 Fremd-RN-Format
}

DLV_START_2026 = pd.Timestamp('2026-01-01')

# ---------------------------------------------------------------------------
# Load CHT IT rows
# ---------------------------------------------------------------------------
with open(BASE / 'output/bi_top20_data.pkl', 'rb') as f:
    bi = pickle.load(f)['df']


def rn_valid(x: object) -> bool:
    try:
        return float(str(x).replace(',', '.')) > 5
    except Exception:
        return False


it = bi[
    (bi['Kunden Nr BK'] == 486073) &
    (bi['periode'] == 'POST') &
    bi['Rechnungsnummer'].apply(rn_valid) &
    (bi['Erlöse Fracht'].fillna(0) > 0) &
    (bi['Empfänger Land'] == 'IT')
].copy()
it['datum'] = pd.to_datetime(it['Leistungsdatum'], errors='coerce')

it['phase'] = it['datum'].apply(
    lambda d: 'in_dlv_2026' if pd.notna(d) and d >= DLV_START_2026 else 'pre_dlv_2026'
)
it['rn_str']  = it['Rechnungsnummer'].astype(str).str.strip()
it['plz_str'] = it['Empfänger PLZ'].astype(str).str.strip()
it['is_s8']   = it.apply(lambda r: (r['rn_str'], r['plz_str']) in KNOWN_S8, axis=1)

# ---------------------------------------------------------------------------
# Run Calculator on all rows
# ---------------------------------------------------------------------------
calc = CHTItalyCalculator()

bp_list, maut_list, bk_list, ok_list, err_list = [], [], [], [], []
for _, row in it.iterrows():
    try:
        res = calc.calculate(
            empf_plz=row['plz_str'],
            empf_land='IT',
            tonnage_kg=float(row['Tonnage (eff.)']),
        )
        bp_list.append(float(res.basispreis))
        maut_list.append(float(res.maut_surcharge) if res.maut_surcharge else 0.0)
        bk_note = next((n for n in res.notes if 'billing_kg=' in n), 'billing_kg=?')
        bk_list.append(bk_note)
        ok_list.append(True)
        err_list.append('')
    except Exception as e:
        bp_list.append(float('nan'))
        maut_list.append(float('nan'))
        bk_list.append('?')
        ok_list.append(False)
        err_list.append(str(e))

it['basispreis'] = bp_list
it['maut_soll']  = maut_list
it['bk_note']    = bk_list
it['calc_ok']    = ok_list
it['calc_err']   = err_list

it_ok = it[it['calc_ok']].copy()
it_ok['delta_fracht']  = it_ok['Erlöse Fracht'] - it_ok['basispreis']
it_ok['delta_maut']    = it_ok['Erlöse Maut'] - it_ok['maut_soll']
it_ok['fp']            = it_ok['delta_fracht'] / it_ok['basispreis']
it_ok['match_01']      = it_ok['delta_fracht'].abs() <= 0.01

# ---------------------------------------------------------------------------
# Print summary
# ---------------------------------------------------------------------------
print('=' * 74)
print('=== 9c.1 CHT ITALY CALCULATOR INTEGRATION TEST ===')
print('=' * 74)

n_total    = len(it)
n_calc_ok  = len(it_ok)
n_pre      = (it_ok['phase'] == 'pre_dlv_2026').sum()
n_in_dlv   = (it_ok['phase'] == 'in_dlv_2026').sum()
n_s8_total = it_ok['is_s8'].sum()

print(f"\nGesamt IT-Zeilen (KNR 486073, POST, Fracht>0): {n_total}")
print(f"  Calculator OK   : {n_calc_ok}")
print(f"  Calculator FAIL : {(~it['calc_ok']).sum()}")

print(f"\nPhasen-Split ({n_calc_ok} Zeilen):")
print(f"  in_dlv_2026   : {n_in_dlv}   (Haupttest-Set)")
print(f"  pre_dlv_2026  : {n_pre}   (unbeurteilbar — 2025-DLV fehlt)")
print(f"  §8-Fälle total: {n_s8_total}   (exkl. aus Match-Quote)")

# pre_dlv summary
pre = it_ok[it_ok['phase'] == 'pre_dlv_2026']
print(f"\nPre-DLV-2026 Zusammenfassung ({len(pre)} Zeilen, KEIN Calculator-Check):")
print(f"  fp-Verteilung (ggü. 2026-DLV, informativ):")
print(f"    mean={pre['fp'].mean():+.4f}  std={pre['fp'].std():.4f}  "
      f"p25={pre['fp'].quantile(0.25):+.4f}  p75={pre['fp'].quantile(0.75):+.4f}")
print(f"  fp ≈ -2% (Okt-Dez 2025, Hauptcluster): "
      f"{((pre['fp'] > -0.022) & (pre['fp'] < -0.018)).sum()}")
print(f"  §8-Fälle (bekannte Ausreißer): {pre['is_s8'].sum()}")

# Main test: in_dlv_2026, not §8
in_dlv_all  = it_ok[it_ok['phase'] == 'in_dlv_2026']
in_dlv_test = in_dlv_all[~in_dlv_all['is_s8']]
in_dlv_s8   = in_dlv_all[in_dlv_all['is_s8']]

n_test    = len(in_dlv_test)
n_match   = in_dlv_test['match_01'].sum()
match_pct = n_match / n_test * 100 if n_test > 0 else 0.0
passed    = match_pct >= 90.0

print(f"\n{'='*74}")
print(f"Haupt-Test: in_dlv_2026 exkl. §8-Fälle ({n_test} Zeilen)")
print(f"  Match (|Δ| ≤ 0,01 EUR): {n_match}/{n_test} = {match_pct:.1f} %")
print(f"  Erfolgskriterium ≥90 %: {'✓ BESTANDEN' if passed else '✗ NICHT BESTANDEN'}")
print(f"{'='*74}")

# Failures in main test
fails = in_dlv_test[~in_dlv_test['match_01']]
if len(fails) > 0:
    print(f"\nFAILURES ({len(fails)}):")
    fcols = ['Rechnungsnummer','plz_str','datum','Tonnage (eff.)',
             'basispreis','Erlöse Fracht','delta_fracht','fp']
    print(fails[[c for c in fcols if c in fails.columns]].to_string(index=False))

# §8 in_dlv summary
print(f"\n§8-Fälle in in_dlv_2026 ({len(in_dlv_s8)} Zeilen — exkludiert):")
s8cols = ['Rechnungsnummer','plz_str','datum','Tonnage (eff.)',
          'basispreis','Erlöse Fracht','delta_fracht','fp']
print(in_dlv_s8[[c for c in s8cols if c in in_dlv_s8.columns]].to_string(index=False))

# Maut check on in_dlv_test
print(f"\nMaut-Delta (|Erlöse_Maut − maut_soll|) — in_dlv_2026 Testset:")
md = in_dlv_test['delta_maut'].abs()
print(f"  mean={md.mean():.4f}  p50={md.median():.4f}  p95={md.quantile(0.95):.4f}  max={md.max():.4f}")
print(f"  |maut_delta| ≤ 0,01: {(md <= 0.01).sum()}/{n_test}")

print(f"\nDone.")
