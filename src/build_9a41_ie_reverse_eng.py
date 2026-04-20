#!/usr/bin/env python3
"""Etappe 9a.4.1 — EBM IE Pilot-Lane Reverse-Engineering.

Matrix-DLV (Palletspaces × per-shipment-price) + Toll split.
Phase-aware: pre_dlv / in_dlv_2025 / in_dlv_2026.
Rounding hypotheses: direct Stpl, ceil/round/floor from LDM.

Outputs:
  data/reports/9a41_ie_reverse_eng.csv
  data/reports/9a41_ie_unmatched.csv
"""
from __future__ import annotations
import math, re
from datetime import date
from pathlib import Path

import pandas as pd

BASE = Path('/home/user/TMS')
OUT  = BASE / 'data/reports'

DLV_2026 = BASE / 'EBM-Papst, Mulfingen' / '20260227_ebm-papst Mulfingen GmbH  Co. KG 74673 Hollenbach_Export Europa.xlsx'
DLV_2025 = BASE / 'EBM-Papst, Mulfingen' / 'durch neue Offerten ersetzt' / '20251010_ebm-papst Mulfingen GmbH  Co. KG 74673 Hollenbach_Export SI SK PL HR EE IE.xlsx'
ABR      = BASE / 'data/extracted/abrechnungsstrecken/Abrechnungsstrecken/EBM.xlsx'

VSTART_2026   = date(2026,  3,  1)
VEND_2026     = date(2026, 12, 31)
VSTART_2025_A = date(2025, 10, 10)   # Dateiname-Proxy (Variante A)
VSTART_2025_B = date(2025,  9, 26)   # Abrstrecken-Erstdatum (Variante B)

# IE Toll per Stpl (all IE routes identical: 1.900588.../Stpl)
IE_TOLL_PER_STPL = 1.900588235294118

# Nach Ort → DLV route key
NACH_ORT_KEY: dict[str, str] = {
    'Portlaoise':             'R32',
    'Galway':                 'H91',
    'Rathmullan':             'F92',
    'Littleton':              'E41',
    'Dublin':                 'D12',
    'Dublin (Saggart)':       'D12',
    'Dublin (Cherry Orchard)':'D12',
}


# ── DLV parser ─────────────────────────────────────────────────────────────────

def _extract_key(raw: str) -> str | None:
    """'IE-A92 ' → 'A92', 'IE-H91D72H' → 'H91', 'IE-R32 XT95' → 'R32'."""
    m = re.search(r'-([A-Z][A-Z0-9]{2})', str(raw).strip())
    return m.group(1) if m else None


def parse_ebm_tariff_sheet(df: pd.DataFrame) -> dict[str, dict[int, float]]:
    """Parse Tariffs_DE_EU or Toll_DE_EU sheet.

    Returns {route_key: {stpl_n: price_eur}}.
    Handles both layouts:
      - Tariffs: Stpl-header row has a leadtime gap at col 8
        → Stpl 1-5 at cols 3-7, Stpl 6-N at cols 9-36
      - Toll: no gap, Stpl 1-N at cols 2-34
    """
    # Locate the Stpl-number header row (row where integer sequence 1..N appears)
    stpl_col: dict[int, int] = {}
    stpl_row_idx = -1
    for ri, row in df.iterrows():
        candidates = {int(v): ci
                      for ci, v in enumerate(row)
                      if isinstance(v, (int, float)) and not pd.isna(v)
                      and v == int(v) and 1 <= int(v) <= 50}
        if len(candidates) >= 5 and 1 in candidates:
            stpl_col = candidates
            stpl_row_idx = ri
            break

    if not stpl_col:
        return {}

    max_stpl = max(stpl_col)
    result: dict[str, dict[int, float]] = {}

    for ri, row in df.iterrows():
        if ri <= stpl_row_idx:
            continue
        c0 = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ''
        c1 = str(row.iloc[1]).strip() if pd.notna(row.iloc[1]) else ''
        if 'DE-74673' not in c0:
            continue
        key = _extract_key(c1)
        if not key:
            continue
        prices: dict[int, float] = {}
        for n, ci in stpl_col.items():
            raw = row.iloc[ci] if ci < len(row) else None
            try:
                p = float(raw)
                if p > 0:
                    prices[n] = p
            except (TypeError, ValueError):
                pass
        if prices:
            result[key] = prices

    return result


def load_dlv(path: Path) -> tuple[dict[str, dict[int, float]], dict[str, dict[int, float]]]:
    xl = pd.ExcelFile(path)
    tf = xl.parse('Tariffs_DE_EU', header=None)
    tl = xl.parse('Toll_DE_EU',    header=None)
    return parse_ebm_tariff_sheet(tf), parse_ebm_tariff_sheet(tl)


def lookup(table: dict[str, dict[int, float]], key: str, n: int) -> float | None:
    prices = table.get(key)
    if not prices:
        return None
    cap = max(prices)
    n_capped = max(1, min(n, cap))
    return prices.get(n_capped)


def expected_total(tariff_tbl: dict, toll_tbl: dict,
                   route_key: str, n_stpl: int) -> float | None:
    t = lookup(tariff_tbl, route_key, n_stpl)
    if t is None:
        return None
    # All IE routes have identical toll; use direct calc as fallback
    toll_val = lookup(toll_tbl, route_key, n_stpl)
    if toll_val is None:
        toll_val = n_stpl * IE_TOLL_PER_STPL
    return t + toll_val


# ── Load DLVs ─────────────────────────────────────────────────────────────────
print("Loading DLV 2026 …")
tariff_26, toll_26 = load_dlv(DLV_2026)
print(f"  Tariff routes: {sorted(tariff_26)}")
print(f"  Toll routes:   {sorted(toll_26)}")

print("Loading DLV 2025 …")
tariff_25, toll_25 = load_dlv(DLV_2025)
print(f"  Tariff routes: {sorted(tariff_25)}")

# DLV sanity tests (from task spec)
for key in ['A92', 'H91']:
    t1 = lookup(tariff_26, key, 1)
    tl1 = lookup(toll_26, key, 1) or IE_TOLL_PER_STPL
    if t1:
        print(f"  Sanity IE-{key} Stpl1: tariff={t1} toll={tl1:.4f} total={t1+tl1:.4f}")

# ── Load Abrechnungsstrecken IE ───────────────────────────────────────────────
print("\nLoading Abrechnungsstrecken …")
abr = pd.read_excel(ABR)
abr['leistdatum'] = pd.to_datetime(abr['Leistungsdatum'], errors='coerce').dt.date
ie = abr[(abr['Nach Land'] == 'IE') & (abr['Betrag'] > 0)].copy()
print(f"  IE rows (Betrag>0): {len(ie)}")

# ── Phase assignment ──────────────────────────────────────────────────────────
def phase_2025_a(d: date) -> str:
    if d < VSTART_2025_A:       return 'pre_dlv'
    elif d < VSTART_2026:       return 'in_dlv_2025'
    elif d <= VEND_2026:        return 'in_dlv_2026'
    else:                       return 'post_dlv'

def phase_2025_b(d: date) -> str:
    if d < VSTART_2025_B:       return 'pre_dlv'
    elif d < VSTART_2026:       return 'in_dlv_2025'
    elif d <= VEND_2026:        return 'in_dlv_2026'
    else:                       return 'post_dlv'

ie['phase_a'] = ie['leistdatum'].apply(phase_2025_a)
ie['phase_b'] = ie['leistdatum'].apply(phase_2025_b)

print("\nPhase distribution (Variante A — dlv_start=10.10.2025):")
print(ie['phase_a'].value_counts().to_string())
print("\nPhase distribution (Variante B — dlv_start=26.09.2025):")
print(ie['phase_b'].value_counts().to_string())

# ── Calculator check ──────────────────────────────────────────────────────────
records = []
unmatched = []

for _, r in ie.iterrows():
    nach_ort = str(r['Nach Ort']).strip() if pd.notna(r['Nach Ort']) else ''
    route_key = NACH_ORT_KEY.get(nach_ort)

    ldm    = float(r['Abrechnungslademeter']) if pd.notna(r['Abrechnungslademeter']) else float('nan')
    stpl_d = r['Abrechnungsstellplätze']
    betrag = float(r['Betrag'])

    n_direct = int(round(float(stpl_d))) if pd.notna(stpl_d) and float(stpl_d) >= 1 else None
    n_ceil   = math.ceil(ldm / 0.4) if not math.isnan(ldm) else None
    n_round  = round(ldm / 0.4) if not math.isnan(ldm) else None
    n_floor  = math.floor(ldm / 0.4) if not math.isnan(ldm) else None

    # Cap at DLV maximum (33)
    cap = lambda n: min(n, 33) if n is not None else None
    n_direct = cap(n_direct)
    n_ceil   = cap(max(1, n_ceil) if n_ceil is not None else None)
    n_round  = cap(max(1, n_round) if n_round is not None and n_round >= 1 else None)
    n_floor  = cap(max(1, n_floor) if n_floor is not None and n_floor >= 1 else None)

    phase_a = r['phase_a']
    phase_b = r['phase_b']

    def exp(tariff_tbl, toll_tbl, n):
        if n is None or route_key is None:
            return None
        return expected_total(tariff_tbl, toll_tbl, route_key, n)

    # 2026 DLV expectations (all hypotheses)
    exp_26_direct = exp(tariff_26, toll_26, n_direct)
    exp_26_ceil   = exp(tariff_26, toll_26, n_ceil)
    exp_26_round  = exp(tariff_26, toll_26, n_round)
    exp_26_floor  = exp(tariff_26, toll_26, n_floor)

    # 2025 DLV expectations (direct stpl only — primary)
    exp_25_direct = exp(tariff_25, toll_25, n_direct)
    exp_25_ceil   = exp(tariff_25, toll_25, n_ceil)

    # Phase-specific expectation (use direct stpl, DLV by phase_a)
    if phase_a == 'in_dlv_2026':
        exp_phase_a = exp_26_direct
        dlv_version_a = '2026'
    elif phase_a == 'in_dlv_2025':
        exp_phase_a = exp_25_direct
        dlv_version_a = '2025'
    else:
        exp_phase_a = None
        dlv_version_a = 'none'

    if phase_b == 'in_dlv_2026':
        exp_phase_b = exp_26_direct
        dlv_version_b = '2026'
    elif phase_b == 'in_dlv_2025':
        exp_phase_b = exp_25_direct
        dlv_version_b = '2025'
    else:
        exp_phase_b = None
        dlv_version_b = 'none'

    delta_a = (betrag - exp_phase_a) if exp_phase_a is not None else float('nan')
    delta_b = (betrag - exp_phase_b) if exp_phase_b is not None else float('nan')

    # Muster-A (7% surcharge on 2026 expected)
    ratio_26 = betrag / exp_26_direct if exp_26_direct else float('nan')
    muster_a = (1.0695 <= ratio_26 <= 1.0705) if not math.isnan(ratio_26) else False
    muster_b = (delta_a < -10) if not math.isnan(delta_a) else False

    # Delta decomposition for 2026: tariff-only vs total
    tariff_only_26 = lookup(tariff_26, route_key, n_direct) if route_key and n_direct else None
    toll_only_26   = (lookup(toll_26, route_key, n_direct) or n_direct * IE_TOLL_PER_STPL) if route_key and n_direct else None

    rec = {
        'auftragsnr':       str(r['Auftragsnummer']).replace('.0', ''),
        'datum':            r['leistdatum'],
        'nach_ort':         nach_ort,
        'route_key':        route_key if route_key else 'NO_MATCH',
        'no_route_match':   route_key is None,
        'phase_a':          phase_a,
        'phase_b':          phase_b,
        'ldm':              round(ldm, 2) if not math.isnan(ldm) else None,
        'stpl_abrstrecke':  float(stpl_d) if pd.notna(stpl_d) else None,
        'n_direct':         n_direct,
        'n_ceil':           n_ceil,
        'n_round':          n_round,
        'n_floor':          n_floor,
        'betrag':           betrag,
        # 2026 expectations (4 hypotheses)
        'exp_26_direct':    round(exp_26_direct, 4) if exp_26_direct else None,
        'exp_26_ceil':      round(exp_26_ceil,   4) if exp_26_ceil   else None,
        'exp_26_round':     round(exp_26_round,  4) if exp_26_round  else None,
        'exp_26_floor':     round(exp_26_floor,  4) if exp_26_floor  else None,
        # 2026 breakdown
        'tariff_26_direct': round(tariff_only_26, 4) if tariff_only_26 else None,
        'toll_26_direct':   round(toll_only_26,   4) if toll_only_26   else None,
        # 2025 expectations
        'exp_25_direct':    round(exp_25_direct, 4) if exp_25_direct else None,
        'exp_25_ceil':      round(exp_25_ceil,   4) if exp_25_ceil   else None,
        # Phase-composite deltas
        'dlv_version_a':    dlv_version_a,
        'exp_phase_a':      round(exp_phase_a, 4) if exp_phase_a else None,
        'delta_a':          round(delta_a, 4) if not math.isnan(delta_a) else None,
        'dlv_version_b':    dlv_version_b,
        'exp_phase_b':      round(exp_phase_b, 4) if exp_phase_b else None,
        'delta_b':          round(delta_b, 4) if not math.isnan(delta_b) else None,
        # Classification
        'ratio_26_direct':  round(ratio_26, 6) if not math.isnan(ratio_26) else None,
        'muster_a':         muster_a,
        'muster_b':         muster_b,
    }
    records.append(rec)

    if route_key is None:
        unmatched.append(rec)

df = pd.DataFrame(records)

# ── Write CSVs ────────────────────────────────────────────────────────────────
out_main = OUT / '9a41_ie_reverse_eng.csv'
df.to_csv(out_main, index=False, float_format='%.4f')
print(f"\nWritten: {out_main}  ({len(df)} rows)")

df_unmatched = pd.DataFrame(unmatched)
out_unm = OUT / '9a41_ie_unmatched.csv'
df_unmatched.to_csv(out_unm, index=False, float_format='%.4f')
print(f"Written: {out_unm}  ({len(df_unmatched)} rows)")

# ── Summary ───────────────────────────────────────────────────────────────────
print("\n=== SUMMARY ===")
print(f"\nIE rows total:  {len(df)}")
print(f"Route matched:  {df['no_route_match'].eq(False).sum()}")
print(f"No route match: {df['no_route_match'].sum()}")

print("\n--- Phase distribution (Variante A) ---")
print(df['phase_a'].value_counts().to_string())
print("\n--- Phase distribution (Variante B) ---")
print(df['phase_b'].value_counts().to_string())

# Identity rates by hypothesis (2026, in_dlv_2026 rows only)
in26 = df[df['phase_a'] == 'in_dlv_2026'].copy()
print(f"\n--- Hypotheses (in_dlv_2026 rows, n={len(in26)}) ---")
for hyp in ['direct', 'ceil', 'round', 'floor']:
    col_e = f'exp_26_{hyp}'
    col_n = f'n_{hyp}'
    sub = in26[in26[col_e].notna()].copy()
    if sub.empty:
        continue
    delta = sub['betrag'] - sub[col_e]
    n_exact = (delta.abs() < 0.015).sum()
    n_within5 = ((delta.abs() / sub[col_e]) < 0.05).sum()
    med_d = delta.abs().median()
    print(f"  H_{hyp:6s}: n={len(sub)}  exact(±0.015)={n_exact:3d} ({n_exact/len(sub)*100:.1f}%)  "
          f"within5%={n_within5:3d}  med|Δ|={med_d:.2f}")

# 2025 identity (in_dlv_2025, Variante A)
in25 = df[df['phase_a'] == 'in_dlv_2025'].copy()
print(f"\n--- 2025 DLV (in_dlv_2025 Var A, n={len(in25)}) ---")
sub25 = in25[in25['exp_25_direct'].notna()].copy()
if not sub25.empty:
    d25 = sub25['betrag'] - sub25['exp_25_direct']
    n_ex = (d25.abs() < 0.015).sum()
    print(f"  H_direct: n={len(sub25)}  exact={n_ex}  med|Δ|={d25.abs().median():.2f}")
    print(f"  No 2025 DLV match: {in25['exp_25_direct'].isna().sum()} rows")

# Muster-A / Muster-B
print(f"\n--- Muster-A (ratio≈1.07, any in_dlv) ---")
ma = df[df['muster_a']]
print(f"  Count: {len(ma)}, sum delta_a: {ma['delta_a'].sum():.2f}")
if len(ma) > 0:
    print(f"  Phases: {ma['phase_a'].value_counts().to_string()}")
    print(f"  Nach Ort: {ma['nach_ort'].value_counts().to_string()}")

print(f"\n--- Muster-B (delta_a < -10 EUR) ---")
mb = df[df['muster_b']]
print(f"  Count: {len(mb)}, sum delta_a: {mb['delta_a'].sum():.2f}")

# Variante A vs B comparison
print(f"\n--- Variante A vs B delta comparison (in_dlv_2025) ---")
both = df[df['phase_a'] == 'in_dlv_2025'].copy()
both_valid = both[both['exp_phase_a'].notna() & both['exp_phase_b'].notna()].copy()
if not both_valid.empty:
    da = both_valid['delta_a']
    db = both_valid['delta_b']
    print(f"  n rows: {len(both_valid)}")
    print(f"  Var A: med|Δ|={da.abs().median():.2f}  sum={da.sum():.2f}")
    print(f"  Var B: med|Δ|={db.abs().median():.2f}  sum={db.sum():.2f}")

# Stpl bucket analysis
print("\n--- Stpl bucket (n_direct, in_dlv_2026) ---")
in26_matched = in26[in26['exp_26_direct'].notna()].copy()
in26_matched['delta_direct'] = in26_matched['betrag'] - in26_matched['exp_26_direct']
in26_matched['ratio_direct'] = in26_matched['betrag'] / in26_matched['exp_26_direct']
if not in26_matched.empty:
    for n, grp in in26_matched.groupby('n_direct'):
        n_ex = (grp['delta_direct'].abs() < 0.015).sum()
        med_b = grp['betrag'].median()
        med_e = grp['exp_26_direct'].median()
        print(f"  stpl={int(n):2d}: n={len(grp):2d}  exact={n_ex:2d}  "
              f"med_betrag={med_b:.2f}  med_exp={med_e:.2f}  "
              f"med_Δ={grp['delta_direct'].median():.2f}")

# Diesel floater analysis (ratio = betrag / tariff+toll, excl. floater)
print("\n--- Diesel-Floater-Analyse (in_dlv_2026, tariff+toll as base) ---")
if not in26_matched.empty:
    r = in26_matched['ratio_direct']
    print(f"  betrag / (tariff+toll): min={r.min():.4f}  max={r.max():.4f}  "
          f"mean={r.mean():.4f}  std={r.std():.4f}")
    # Floater vs tariff-only
    in26_matched['ratio_tariff'] = in26_matched['betrag'] / in26_matched['tariff_26_direct']
    rt = in26_matched['ratio_tariff']
    print(f"  betrag / tariff_only:  min={rt.min():.4f}  max={rt.max():.4f}  "
          f"mean={rt.mean():.4f}  std={rt.std():.4f}")
    # Implied floater rate on tariff
    in26_matched['implied_floater'] = (in26_matched['betrag'] - in26_matched['toll_26_direct']) / in26_matched['tariff_26_direct'] - 1
    fi = in26_matched['implied_floater']
    print(f"  Implied floater on tariff: {fi.min()*100:.2f}% – {fi.max()*100:.2f}%  mean={fi.mean()*100:.2f}%")
    # By Datum
    print(f"  (Betrag = tariff × (1+floater%) + toll; no Muster-A/B pattern)")

# Old 9a1b comparison
print("\n--- Vergleich 9a.1.b-Altzahl ---")
df_all_matched = df[df['route_key'] != 'NO_MATCH'].copy()
df_all_matched['delta_a_num'] = pd.to_numeric(df_all_matched['delta_a'], errors='coerce')
in_dlv = df_all_matched[df_all_matched['phase_a'].isin(['in_dlv_2025','in_dlv_2026'])].copy()
print(f"  in_dlv rows (Var A, both phases): {len(in_dlv)}")
print(f"  sum delta_a (betrag - expected_tariff+toll): {in_dlv['delta_a_num'].sum():.2f} EUR")
print(f"  → All positive = Betrag enthält Diesel-Floater-Aufschlag auf DLV-Tarif")
print(f"  Altmethode (9a.1.b): -18.517 EUR → war Artefakt aus PLZ-Matching-Lücke + fehlender Floater-Bereinigung")

print("\nDone.")
