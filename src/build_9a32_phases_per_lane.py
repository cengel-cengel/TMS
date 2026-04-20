#!/usr/bin/env python3
"""Etappe 9a.3.2 — Phase-aware calculator check across all Fischerwerke lanes.

Phases per DLV validity window:
  pre_dlv  = Leistungsdatum < validity_start
  in_dlv   = Leistungsdatum within validity
  post_dlv = Leistungsdatum > validity_end

Calculator check only on in_dlv rows.
Outputs:
  data/reports/9a32_phases_per_lane.csv
  data/reports/9a32_findings_raw.csv
"""
from __future__ import annotations
import math
import re
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path('/home/user/TMS')
OUT  = BASE / 'data/reports'
DLV  = BASE / 'Fischerwerke/DLVs & Tarife'
ABR  = BASE / 'data/extracted/abrechnungsstrecken/Abrechnungsstrecken/Fischerwerke.xlsx'

# ── Helpers ──────────────────────────────────────────────────────────────────

def _safe_float(v) -> float | None:
    try:
        f = float(str(v).replace(',', '.'))
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


def parse_validity(df: pd.DataFrame) -> tuple[date, date]:
    """Extract validity start/end from any sheet."""
    for _, row in df.iterrows():
        label = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ''
        if 'ltigkeit' not in label:
            continue
        # Search all cells in row for a date string
        full = ' '.join(str(v) for v in row if pd.notna(v))
        dates = re.findall(r'(\d{2}[.\-]\d{2}[.\-]\d{4})', full)
        if len(dates) >= 2:
            def p(s): return datetime.strptime(s.replace('-','.'), '%d.%m.%Y').date()
            return p(dates[0]), p(dates[1])
    return date(2026, 1, 1), date(2026, 12, 31)  # default


def parse_rates_two_col(df: pd.DataFrame, stpl_col: int, rate_col: int) -> dict[int, float]:
    """Parse a two-column (stpl_col, rate_col) rate table. Handles 'N-M' stpl ranges."""
    dlv: dict[int, float] = {}
    for _, row in df.iterrows():
        raw_s = str(row.iloc[stpl_col]).strip() if pd.notna(row.iloc[stpl_col]) else ''
        raw_r = row.iloc[rate_col]
        rate = _safe_float(raw_r)
        if rate is None or rate <= 0:
            continue
        # Handle range like "30-33"
        m = re.fullmatch(r'(\d+)[\-–](\d+)', raw_s)
        if m:
            for n in range(int(m.group(1)), int(m.group(2)) + 1):
                dlv[n] = rate
            continue
        try:
            n = int(float(raw_s.replace(',', '.')))
            if 1 <= n <= 50:
                dlv[n] = rate
        except (ValueError, TypeError):
            pass
    return dlv


def parse_dlv_auto(path: Path) -> tuple[dict[int, float], date, date]:
    """Universal DLV parser: detects column layout automatically.

    Supported layouts (all used by Fischerwerke):
      Layout A: stpl col 0, rate col 1  + optional right block col 4/5
      Layout B: stpl col 2, rate col 3  + optional right block col 7/8 or col 6/7
    """
    df = pd.read_excel(path, header=None)
    validity = parse_validity(df)
    ncols = df.shape[1]

    # Try Layout A first (col 0/1)
    dlv_a = parse_rates_two_col(df, 0, 1)
    if dlv_a:
        # Also pick up right block at col 4/5
        if ncols > 5:
            dlv_a.update(parse_rates_two_col(df, 4, 5))
        return dlv_a, *validity

    # Fall back to Layout B (col 2/3)
    dlv_b: dict[int, float] = {}
    dlv_b.update(parse_rates_two_col(df, 2, 3))
    if ncols > 8:
        dlv_b.update(parse_rates_two_col(df, 7, 8))
    elif ncols > 7:
        dlv_b.update(parse_rates_two_col(df, 6, 7))
    return dlv_b, *validity


def dlv_lookup(dlv: dict[int, float], stpl: float) -> float | None:
    if not dlv:
        return None
    n = round(stpl)
    n = max(1, min(n, max(dlv)))
    return dlv.get(n)


def classify_delta(betrag: float, expected: float | None) -> str:
    if expected is None:
        return 'no_dlv'
    delta = betrag - expected
    ratio = betrag / expected if expected != 0 else float('nan')
    if abs(delta) < 0.01:
        return 'exact_match'
    if 1.0695 <= ratio <= 1.0705:
        return 'muster_a_7pct'
    if delta < -10:
        return 'muster_b_under'
    if delta > 10:
        return 'muster_c_over'
    return 'other'


# ── Lane configuration ────────────────────────────────────────────────────────

LANES = [
    {
        'lane': 'IT-Padova',
        'nach_ort': ['Padova'],
        'dlv_path': DLV / '2026/20251219_Fischerwerke_DE-72 Waldachtal nach IT-35127 Padua_2026.xlsx',
        'parser': parse_dlv_auto,
    },
    {
        'lane': 'IT-Copiano',
        'nach_ort': ['Copiano'],
        'dlv_path': DLV / '2026/20260108_Fischerwerke_IT-27010 Copiano.xlsx',
        'parser': parse_dlv_auto,
    },
    {
        'lane': 'BE-Willebroek',
        'nach_ort': ['Willebroek'],
        'dlv_path': DLV / '2026/20251219_Fischerwerke_DE-72 Waldachtal nach BE-2830 Willebroek_2026.xlsx',
        'parser': parse_dlv_auto,
    },
    {
        'lane': 'DK-Koge',
        'nach_ort': ['Køge', 'Koge'],
        'dlv_path': DLV / '2026/20251219_Fischerwerke_DE-72 Waldachtal nach DK-4600 Koge_2026.xlsx',
        'parser': parse_dlv_auto,
    },
    {
        'lane': 'IE-Dublin',
        'nach_ort': ['Dublin (Saggart)', 'Dublin (Cherry Orchard)', 'Dublin'],
        'dlv_path': DLV / '2026/20251219_Fischerwerke_DE-72 Waldachtal nach IE-Dublin_2026.xlsx',
        'parser': parse_dlv_auto,
    },
    {
        'lane': 'ES-MontRoig',
        'nach_ort': ['Mont-Roig del Camp', 'Reus'],
        'dlv_path': DLV / '2026/20251219_Fischerwerke_DE-72 Waldachtal nach ES-43300 Mont Roig u. TKL nach ES-43206 Reus_2026.xlsx',
        'parser': parse_dlv_auto,
    },
    {
        'lane': 'GR-Athen',
        'nach_ort': None,  # all GR rows
        'nach_land': 'GR',
        'dlv_path': DLV / '2025/20250422_Fischerwerke_DE-72 Waldachtal nach GR-Athen.xlsx',
        'parser': parse_dlv_auto,
    },
    {
        'lane': 'GB-Wallingford',
        'nach_ort': ['Wallingford'],
        'dlv_path': DLV / '2025/20250422_Fischerwerke_DE-72 Waldachtal nach GB-OX Wallingford.xlsx',
        'parser': parse_dlv_auto,
    },
]

# ── Load Abrechnungsstrecken ──────────────────────────────────────────────────
print("Loading Abrechnungsstrecken …")
abr = pd.read_excel(ABR)
abr['auftragsnr'] = abr['Auftragsnummer'].astype(str).str.replace(r'\.0$', '', regex=True)
abr['leistdatum'] = pd.to_datetime(abr['Leistungsdatum']).dt.date
abr['stpl'] = pd.to_numeric(abr['Abrechnungsstellplätze'], errors='coerce')
abr['betrag'] = pd.to_numeric(abr['Betrag'], errors='coerce')
abr = abr[abr['betrag'] > 0].copy()  # drop Storno/zero
print(f"  {len(abr)} rows (Betrag>0)")

# ── Per-lane analysis ─────────────────────────────────────────────────────────
lane_summary: list[dict] = []
raw_findings: list[dict] = []

for cfg in LANES:
    lane = cfg['lane']
    dlv_path = cfg['dlv_path']

    if not dlv_path.exists():
        print(f"\n[{lane}] DLV file not found — skipping")
        continue

    # Parse DLV
    try:
        dlv, vstart, vend = cfg['parser'](dlv_path)
    except Exception as e:
        print(f"\n[{lane}] Parse error: {e} — skipping")
        continue

    if not dlv:
        print(f"\n[{lane}] Empty DLV table — skipping")
        continue

    # Filter Abrechnungsstrecken rows
    if cfg.get('nach_ort') is not None:
        mask = abr['Nach Ort'].isin(cfg['nach_ort'])
    else:
        mask = abr['Nach Land'].str.strip().str.upper() == cfg.get('nach_land', '')
    rows = abr[mask].copy()

    if rows.empty:
        print(f"\n[{lane}] No Abrechnungsstrecken rows — skipping")
        continue

    # Phase assignment
    rows['phase'] = rows['leistdatum'].apply(
        lambda d: 'pre_dlv' if d < vstart else ('post_dlv' if d > vend else 'in_dlv')
    )

    n_pre  = (rows['phase'] == 'pre_dlv').sum()
    n_in   = (rows['phase'] == 'in_dlv').sum()
    n_post = (rows['phase'] == 'post_dlv').sum()

    # Calculator check on in_dlv rows
    in_rows = rows[rows['phase'] == 'in_dlv'].copy()
    n_exact = n_muster_a = n_muster_b = 0
    eur_muster_a = eur_muster_b = 0.0

    for _, r in in_rows.iterrows():
        stpl = r['stpl']
        betrag = r['betrag']
        if pd.isna(stpl):
            cat = 'no_stpl'
            expected = None
        else:
            expected = dlv_lookup(dlv, float(stpl))
            cat = classify_delta(betrag, expected)

        delta = (betrag - expected) if expected is not None else float('nan')

        raw_findings.append({
            'lane':         lane,
            'auftragsnr':   r['auftragsnr'],
            'leistdatum':   r['leistdatum'],
            'nach_ort':     r['Nach Ort'],
            'ausgangsrel':  r['Ausgangsrelation'],
            'stpl':         stpl,
            'betrag':       betrag,
            'dlv_expected': expected,
            'delta':        delta,
            'ratio':        betrag / expected if expected else float('nan'),
            'category':     cat,
            'phase':        'in_dlv',
        })

        if cat == 'exact_match':  n_exact += 1
        elif cat == 'muster_a_7pct':
            n_muster_a += 1
            eur_muster_a += delta if not math.isnan(delta) else 0
        elif cat == 'muster_b_under':
            n_muster_b += 1
            eur_muster_b += delta if not math.isnan(delta) else 0

    print(f"\n[{lane}] validity={vstart}–{vend}  "
          f"pre={n_pre}  in={n_in}  post={n_post}")
    print(f"  in_dlv: exact={n_exact}  muster_a={n_muster_a}(+{eur_muster_a:.0f}€)  "
          f"muster_b={n_muster_b}({eur_muster_b:.0f}€)")

    lane_summary.append({
        'lane':          lane,
        'dlv_valid_from': str(vstart),
        'dlv_valid_to':   str(vend),
        'n_pre_dlv':     int(n_pre),
        'n_in_dlv':      int(n_in),
        'n_post_dlv':    int(n_post),
        'n_exact':       int(n_exact),
        'n_muster_a':    int(n_muster_a),
        'n_muster_b':    int(n_muster_b),
        'eur_muster_a':  round(eur_muster_a, 2),
        'eur_muster_b':  round(eur_muster_b, 2),
    })

# ── Write outputs ─────────────────────────────────────────────────────────────
df_summary = pd.DataFrame(lane_summary)
summary_path = OUT / '9a32_phases_per_lane.csv'
df_summary.to_csv(summary_path, index=False, float_format='%.2f')
print(f"\nWritten: {summary_path}")
print(df_summary.to_string(index=False))

df_raw = pd.DataFrame(raw_findings)
raw_path = OUT / '9a32_findings_raw.csv'
df_raw.to_csv(raw_path, index=False, float_format='%.4f')
print(f"\nWritten: {raw_path}  ({len(df_raw)} rows)")
print("\nDone.")
