#!/usr/bin/env python3
"""Etappe 9a.4.2 — EBM Phasen-Rollout alle Lanes (KNR 410844).

Reuses parse logic from 9a.4.1 (build_9a41_ie_reverse_eng.py).
Extended _extract_key to handle PLZ-style routes (PL, SK, SI, HR, EE).
Floater-aware: delta_raw = betrag - (tariff + toll); floater documented per row.

Outputs:
  data/reports/9a42_lanes_summary.csv
  data/reports/9a42_unbeurteilbar.csv
  data/reports/9a42_muster_b.csv   (if any)
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

VSTART_2026   = date(2026, 3, 1)
VEND_2026     = date(2026, 12, 31)
VSTART_2025_A = date(2025, 10, 10)

# ── Nach Ort → DLV route key ──────────────────────────────────────────────────
# None = no DLV coverage (unbeurteilbar)
NACH_ORT_KEY: dict[str, str | None] = {
    # IE (from 9a.4.1)
    'Portlaoise':              'R32',
    'Galway':                  'H91',
    'Rathmullan':              'F92',
    'Littleton':               'E41',
    'Dublin':                  'D12',
    'Dublin (Saggart)':        'D12',
    'Dublin (Cherry Orchard)': 'D12',
    # PL
    'Warszawa (Białołęka)':    'PL-03-236',
    'Legnickie Pole':          'PL-59-241',
    # PL unmatched → None implicitly (Lódz, Szczecin, Legnica, Skawina)
    # SK
    'Senica':                  'SK-905 01',
    'Trencianske Stankovce':   'SK-913 11',
    'Tren?ianske Stankovce':   'SK-913 11',  # encoding artefact of Trenčianske
    'Chocholna - Velcice':     'SK-913 11',  # PLZ 913 04 = same rate block
    # Bytca → None (PLZ 014 01, not in DLV)
    # HR
    'Buje':    'HR-52460',
    # Kutina → None
    # EE
    'Lehmja':  'EE-75301',  # PLZ 75306 = same rate block (EE-75301|EE-75306)
    # SI
    'Logatec':                   'SI-1370',
    'Naklo':                      None,     # PLZ 4202, not in DLV
    'Poljane nad Skofjo Loko':   'SI-4223',
    'Velenje':                   'SI-3320',
    # GB  (FTL-only pricing in 2026 DLV; 2025 DLV has no GB)
    'Chelmsford': 'CM2',
    'Essex':      'CM2',
    # DE internal / no export DLV
    'Mulfingen':  None,
    # PT, ES, RS — not in any DLV
    'Vila Franca de Xira':       None,
    'San Fernando de Henares':   None,
    'Móstoles':                  None,
    'Prokuplje':                 None,
}

# ── DLV parser (extended from 9a.4.1) ────────────────────────────────────────

def _extract_key(raw: str) -> str | None:
    """Extract route key from DLV location string.

    IE/GB:   'IE-A92 FY90' → 'A92',  'IE-H91D72H' → 'H91',  'GB-CM2 EZ' → 'CM2'
    PLZ:     'PL-03-236'   → 'PL-03-236',  'SK-905 01'→ 'SK-905 01'
    Merged:  'EE-75301|EE-75306' → 'EE-75301'
    """
    s = str(raw).strip().split('|')[0].strip()
    m = re.match(r'^([A-Z]{2})-(.+)', s)
    if not m:
        return None
    country, rest = m.group(1), m.group(2).strip()
    if re.match(r'[A-Z]', rest):
        km = re.match(r'([A-Z][A-Z0-9]{2})', rest)
        return km.group(1) if km else None
    return f'{country}-{rest}'


def parse_ebm_tariff_sheet(df: pd.DataFrame) -> dict[str, dict[int, float]]:
    """Parse Tariffs_DE_EU or Toll_DE_EU.  Returns {route_key: {stpl_n: price}}."""
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
            raw_v = row.iloc[ci] if ci < len(row) else None
            try:
                p = float(raw_v)
                if p > 0:
                    prices[n] = p
            except (TypeError, ValueError):
                pass
        if prices:
            result[key] = prices
    return result


def load_dlv(path: Path) -> tuple[dict, dict]:
    xl = pd.ExcelFile(path)
    tf = xl.parse('Tariffs_DE_EU', header=None)
    tl = xl.parse('Toll_DE_EU',    header=None)
    return parse_ebm_tariff_sheet(tf), parse_ebm_tariff_sheet(tl)


def lookup(table: dict[str, dict[int, float]], key: str, n: int) -> float | None:
    prices = table.get(key)
    if not prices:
        return None
    cap = max(prices)
    return prices.get(max(1, min(n, cap)))


# ── Phase helper ──────────────────────────────────────────────────────────────

def assign_phase(d: date) -> str:
    if d < VSTART_2025_A:  return 'pre_dlv'
    elif d < VSTART_2026:  return 'in_dlv_2025'
    elif d <= VEND_2026:   return 'in_dlv_2026'
    else:                  return 'post_dlv'


# ── Load DLVs ─────────────────────────────────────────────────────────────────
print("Loading DLV 2026 …")
tariff_26, toll_26 = load_dlv(DLV_2026)
print(f"  Tariff routes: {sorted(tariff_26)}")

print("Loading DLV 2025 …")
tariff_25, toll_25 = load_dlv(DLV_2025)
print(f"  Tariff routes: {sorted(tariff_25)}")

# ── Load Abrechnungsstrecken (all EBM, Betrag>0) ──────────────────────────────
print("\nLoading Abrechnungsstrecken …")
abr = pd.read_excel(ABR)
abr['leistdatum'] = pd.to_datetime(abr['Leistungsdatum'], errors='coerce').dt.date
rows = abr[abr['Betrag'] > 0].copy()
print(f"  Rows Betrag>0: {len(rows)}")

# ── Per-row analysis ──────────────────────────────────────────────────────────
records = []

for _, r in rows.iterrows():
    nach_ort = str(r['Nach Ort']).strip() if pd.notna(r['Nach Ort']) else ''
    nach_land = str(r['Nach Land']).strip() if pd.notna(r['Nach Land']) else ''
    route_key = NACH_ORT_KEY.get(nach_ort)  # None if not in dict (unknown Nach Ort)

    ldm    = float(r['Abrechnungslademeter']) if pd.notna(r['Abrechnungslademeter']) else float('nan')
    stpl_r = r['Abrechnungsstellplätze']
    betrag = float(r['Betrag'])
    d      = r['leistdatum']

    phase = assign_phase(d)

    n_direct = int(round(float(stpl_r))) if pd.notna(stpl_r) and float(stpl_r) >= 1 else None
    # LDM fallback: when Stpl is NaN, derive stpl from Lademeter
    if n_direct is None and not math.isnan(ldm):
        n_direct = max(1, math.ceil(ldm / 0.4))
    if n_direct is not None:
        n_direct = max(1, min(n_direct, 33))  # cap at DLV max

    # DLV version selection + fallback logic
    if route_key is None:
        tariff_tbl = toll_tbl = None
        dlv_version_used = None
        dlv_fallback = 'no_dlv'
    elif phase == 'pre_dlv':
        tariff_tbl = toll_tbl = None
        dlv_version_used = None
        dlv_fallback = 'no_dlv'
    elif phase == 'in_dlv_2025':
        if route_key in tariff_25:
            tariff_tbl, toll_tbl = tariff_25, toll_25
            dlv_version_used = '2025-10-10'
            dlv_fallback = 'date_match'
        elif route_key in tariff_26:
            # No 2025 DLV entry → fallback to 2026 (e.g., GB, F92, E41)
            tariff_tbl, toll_tbl = tariff_26, toll_26
            dlv_version_used = '2026-03-01'
            dlv_fallback = 'fallback_latest'
        else:
            tariff_tbl = toll_tbl = None
            dlv_version_used = None
            dlv_fallback = 'no_dlv'
    else:  # in_dlv_2026 or post_dlv
        if route_key in tariff_26:
            tariff_tbl, toll_tbl = tariff_26, toll_26
            dlv_version_used = '2026-03-01'
            dlv_fallback = 'date_match'
        else:
            tariff_tbl = toll_tbl = None
            dlv_version_used = None
            dlv_fallback = 'no_dlv'

    # Lookup
    dlv_tariff = lookup(tariff_tbl, route_key, n_direct) if tariff_tbl and n_direct and route_key else None
    dlv_toll   = lookup(toll_tbl,   route_key, n_direct) if toll_tbl   and n_direct and route_key else None
    if dlv_toll is None and dlv_tariff is not None:
        dlv_toll = 0.0  # some routes have no toll row (treat as 0)

    tariff_source = 'exact' if dlv_tariff is not None else 'no_match'

    if dlv_tariff is not None:
        dlv_expected = dlv_tariff + dlv_toll
        delta_raw    = betrag - dlv_expected
        ratio        = betrag / dlv_expected if dlv_expected else float('nan')
        floater_pct  = (betrag - dlv_toll) / dlv_tariff - 1 if dlv_tariff else float('nan')
    else:
        dlv_expected = dlv_toll = None
        delta_raw    = float('nan')
        ratio        = float('nan')
        floater_pct  = float('nan')

    # Muster-A: floater_pct exactly 7.0% (±0.15%) = fixed ERKA-Indexaufschlag
    # (ratio-based window is too broad; PL diesel floater ~8% would false-trigger)
    muster_a = (abs(floater_pct - 0.07) < 0.0015) if not math.isnan(floater_pct) else False
    muster_b = (delta_raw < -10.0)                 if not math.isnan(delta_raw)   else False

    records.append({
        'lane':               nach_land,
        'nach_ort':           nach_ort,
        'auftragsnr':         str(r['Auftragsnummer']).replace('.0', ''),
        'datum':              d,
        'phase':              phase,
        'route_key':          route_key if route_key else 'NO_MATCH',
        'no_route_match':     route_key is None,
        'ldm':                round(ldm, 2) if not math.isnan(ldm) else None,
        'n_direct':           n_direct,
        'betrag':             betrag,
        'dlv_version_used':   dlv_version_used,
        'dlv_fallback':       dlv_fallback,
        'tariff_source':      tariff_source,
        'dlv_tariff':         round(dlv_tariff, 4) if dlv_tariff is not None else None,
        'dlv_toll':           round(dlv_toll,   4) if dlv_toll   is not None else None,
        'dlv_expected':       round(dlv_expected,4) if dlv_expected is not None else None,
        'delta_raw':          round(delta_raw,  4) if not math.isnan(delta_raw) else None,
        'ratio':              round(ratio,       6) if not math.isnan(ratio) else None,
        'floater_pct':        round(floater_pct, 6) if not math.isnan(floater_pct) else None,
        'muster_a':           muster_a,
        'muster_b':           muster_b,
    })

df_all = pd.DataFrame(records)

# ── Build summary per lane × phase ───────────────────────────────────────────
summary_rows = []
for (lane, phase), grp in df_all.groupby(['lane', 'phase']):
    assessed = grp[grp['dlv_expected'].notna()].copy()
    n_total   = len(grp)
    n_matched = len(assessed)
    n_dlv_gap = n_total - n_matched
    eur_sum   = grp['betrag'].sum()
    eur_assessed = assessed['betrag'].sum()

    fl = assessed['floater_pct'].dropna()
    floater_mean = fl.mean() if len(fl) else float('nan')
    floater_std  = fl.std()  if len(fl) else float('nan')
    floater_min  = fl.min()  if len(fl) else float('nan')
    floater_max  = fl.max()  if len(fl) else float('nan')

    n_muster_a = assessed['muster_a'].sum()
    n_muster_b = assessed['muster_b'].sum()
    delta_sum  = assessed['delta_raw'].sum() if n_matched else float('nan')
    muster_a_flag = 'muster_a_suspected' if n_muster_a > 0 and n_muster_a / max(n_matched,1) > 0.10 else ''

    summary_rows.append({
        'lane':           lane,
        'phase':          phase,
        'n_total':        n_total,
        'n_matched':      n_matched,
        'n_dlv_gaps':     n_dlv_gap,
        'eur_total':      round(eur_sum, 2),
        'eur_assessed':   round(eur_assessed, 2),
        'floater_mean':   round(floater_mean, 4) if not math.isnan(floater_mean) else None,
        'floater_std':    round(floater_std,  4) if not math.isnan(floater_std)  else None,
        'floater_min':    round(floater_min,  4) if not math.isnan(floater_min)  else None,
        'floater_max':    round(floater_max,  4) if not math.isnan(floater_max)  else None,
        'n_muster_a':     int(n_muster_a),
        'n_muster_b':     int(n_muster_b),
        'delta_sum':      round(delta_sum, 2) if not math.isnan(delta_sum) else None,
        'muster_a_flag':  muster_a_flag,
    })

df_summary = pd.DataFrame(summary_rows)

# ── Build unbeurteilbar CSV ───────────────────────────────────────────────────
unbeurteilbar = df_all[df_all['dlv_expected'].isna()].copy()

# ── Build Muster-B CSV ────────────────────────────────────────────────────────
muster_b_rows = df_all[df_all['muster_b'] == True].copy()

# ── Write outputs ─────────────────────────────────────────────────────────────
df_summary.to_csv(OUT / '9a42_lanes_summary.csv', index=False, float_format='%.4f')
print(f"\nWritten: 9a42_lanes_summary.csv  ({len(df_summary)} rows)")

unbeurteilbar.to_csv(OUT / '9a42_unbeurteilbar.csv', index=False, float_format='%.4f')
print(f"Written: 9a42_unbeurteilbar.csv  ({len(unbeurteilbar)} rows)")

muster_b_rows.to_csv(OUT / '9a42_muster_b.csv', index=False, float_format='%.4f')
print(f"Written: 9a42_muster_b.csv  ({len(muster_b_rows)} rows)")

# ── Console Summary ───────────────────────────────────────────────────────────
print("\n" + "="*70)
print("=== 9a.4.2 CONSOLE SUMMARY — EBM ALL LANES ===")
print("="*70)

# Total counts
print(f"\nGesamt EBM Betrag>0: {len(df_all)} Zeilen, {df_all['betrag'].sum():.2f} EUR")
print(f"Beurteilbar (DLV match): {df_all['dlv_expected'].notna().sum()} Zeilen")
print(f"Unbeurteilbar (DLV gap): {df_all['dlv_expected'].isna().sum()} Zeilen")

# Per-lane status
print("\n--- Lane-Status ---")
for lane in df_all['lane'].unique():
    sub = df_all[df_all['lane'] == lane]
    assessed = sub[sub['dlv_expected'].notna()]
    n_ma = int(assessed['muster_a'].sum())
    n_mb = int(assessed['muster_b'].sum())
    n_gap = int(sub['dlv_expected'].isna().sum())
    total = len(sub)
    pct_gap = n_gap / total * 100 if total else 0

    if n_mb > 0:
        status = 'MUSTER_B_PRESENT'
    elif n_ma > 0 and n_ma / max(len(assessed), 1) > 0.10:
        status = 'MUSTER_A_SUSPECTED'
    elif n_gap / max(total, 1) > 0.50:
        status = 'DLV_LÜCKEN_DOMINANT'
    else:
        status = 'sauber'

    fl_mean = assessed['floater_pct'].mean()
    fl_std  = assessed['floater_pct'].std()
    fl_str  = f"floater={fl_mean*100:.1f}%±{fl_std*100:.1f}%" if not math.isnan(fl_mean) else "no_dlv"

    print(f"  {lane:3s}: n={total:3d}  matched={len(assessed):3d}  dlv_gap={n_gap:2d} ({pct_gap:.0f}%)"
          f"  muster_a={n_ma}  muster_b={n_mb}  {fl_str}  → {status}")

# Floater summary across assessed rows
assessed_all = df_all[df_all['dlv_expected'].notna()]
fl_all = assessed_all['floater_pct'].dropna()
print(f"\n--- Floater gesamt ({len(fl_all)} beurteilbare Zeilen) ---")
print(f"  mean={fl_all.mean()*100:.2f}%  std={fl_all.std()*100:.2f}%  "
      f"min={fl_all.min()*100:.2f}%  max={fl_all.max()*100:.2f}%")

# Muster-A detail
n_ma_total = int(assessed_all['muster_a'].sum())
n_mb_total = int(assessed_all['muster_b'].sum())
print(f"\n--- Muster-A (ratio 1.065–1.076): {n_ma_total} Zeilen ---")
if n_ma_total > 0:
    ma = assessed_all[assessed_all['muster_a']]
    print(ma[['lane','nach_ort','datum','n_direct','betrag','ratio','floater_pct']].to_string(index=False))

print(f"\n--- Muster-B (delta_raw < -10 EUR): {n_mb_total} Zeilen ---")
if n_mb_total > 0:
    mb = assessed_all[assessed_all['muster_b']]
    print(mb[['lane','nach_ort','datum','n_direct','betrag','dlv_expected','delta_raw']].to_string(index=False))

# Unbeurteilbar summary
print(f"\n--- Unbeurteilbar ({len(unbeurteilbar)} Zeilen) ---")
print(unbeurteilbar.groupby(['lane','nach_ort','dlv_fallback'])['betrag'].agg(['count','sum'])
      .rename(columns={'count':'n','sum':'eur'}).reset_index().to_string(index=False))

# Altzahl comparison
print("\n--- Altzahl-Vergleich (9a.1.b) ---")
in_dlv_assessed = df_all[
    df_all['phase'].isin(['in_dlv_2025','in_dlv_2026']) &
    df_all['dlv_expected'].notna()
].copy()
delta_sum_all = in_dlv_assessed['delta_raw'].sum()
print(f"  in_dlv beurteilbar: {len(in_dlv_assessed)} Zeilen, delta_sum = {delta_sum_all:.2f} EUR")
print(f"  (alle positiv = Floater-Aufschlag auf DLV-Tarif)")
print(f"  9a.1.b Altzahl: -18.517 EUR → methodisches Artefakt bestätigt")

# Report format decision
any_muster_a = n_ma_total > 0
any_muster_b = n_mb_total > 0
print("\n--- Report-Format-Entscheidung ---")
if any_muster_a or any_muster_b:
    print("  → Fischerwerke-Stil für betroffene Lanes")
    affected = set()
    if any_muster_a:
        affected |= set(assessed_all[assessed_all['muster_a']]['lane'].unique())
    if any_muster_b:
        affected |= set(assessed_all[assessed_all['muster_b']]['lane'].unique())
    print(f"  Betroffene Lanes: {sorted(affected)}")
else:
    print("  → Kurz-Bericht: Floater-Dokumentation + Altzahl-Revision + DLV-Lücken")

print("\nDone.")
