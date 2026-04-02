"""
Script 1: Load data, normalise Verkehrsart, compute PRE/POST stats, sample shipments.
Output: output/top20_abw_stats.pkl, output/top20_abw_samples.pkl
"""
import pickle, pandas as pd, numpy as np
from pathlib import Path

OUT = Path('/home/user/TMS/output')

# ── Load ─────────────────────────────────────────────────────────────────────
with open(OUT / 'bi_top20_data.pkl', 'rb') as f:
    d = pickle.load(f)
df = d['df'].copy()
top20_meta = d['top20']  # kunden_nr, kunden_name, gesamt_erloes
print(f"Loaded {len(df):,} rows")

# ── Invoiced only ─────────────────────────────────────────────────────────────
mask = df['Rechnungsnummer'].notna() & (df['Rechnungsnummer'].astype(str).str.strip().isin(['', 'nan']) == False)
df = df[mask].copy()
print(f"After invoice filter: {len(df):,} rows")

# ── va_norm ───────────────────────────────────────────────────────────────────
def va_norm(row):
    va = str(row.get('Verkehrsart', '') or '').strip()
    det = str(row.get('Verkehrsart Detail', '') or '').strip()
    if va == 'SA':
        return 'SA'
    if va == 'SE':
        return 'SE'
    if va == 'Belog':
        return 'Belog SE'
    if va == 'Export':
        return 'Export'
    if va == 'Charter International':
        return 'Charter'
    if va == 'Charter National':
        return 'Charter National'
    return va if va else 'Sonstige'

df['va_norm'] = df.apply(va_norm, axis=1)
print("va_norm counts:", df['va_norm'].value_counts().to_dict())

# ── Top-20 customer list ──────────────────────────────────────────────────────
top20_nrs = top20_meta['kunden_nr'].tolist()
df20 = df[df['Kunden Nr BK'].isin(top20_nrs)].copy()
print(f"Top-20 rows: {len(df20):,}")

# ── Per-customer × va_norm stats ──────────────────────────────────────────────
def compute_stats(grp):
    pre = grp[grp['periode'] == 'PRE']['Erloese']
    post = grp[grp['periode'] == 'POST']['Erloese']
    avg_pre = pre.mean() if len(pre) > 0 else np.nan
    avg_post = post.mean() if len(post) > 0 else np.nan
    delta_eur = avg_post - avg_pre if (not np.isnan(avg_pre) and not np.isnan(avg_post)) else np.nan
    delta_pct = (delta_eur / abs(avg_pre) * 100) if (not np.isnan(delta_eur) and avg_pre != 0) else np.nan
    return pd.Series({
        'n_pre': len(pre),
        'n_post': len(post),
        'avg_pre': avg_pre,
        'avg_post': avg_post,
        'sum_pre': pre.sum(),
        'sum_post': post.sum(),
        'delta_eur': delta_eur,
        'delta_pct': delta_pct,
        'avg_pre_dbii': grp[grp['periode'] == 'PRE']['DB II'].mean() if len(pre) > 0 else np.nan,
        'avg_post_dbii': grp[grp['periode'] == 'POST']['DB II'].mean() if len(post) > 0 else np.nan,
    })

stats_va = (df20
    .groupby(['Kunden Nr BK', 'Kunden Name', 'va_norm'], dropna=False)
    .apply(compute_stats)
    .reset_index())

# also totals per customer (all va_norm combined)
stats_tot = (df20
    .groupby(['Kunden Nr BK', 'Kunden Name'], dropna=False)
    .apply(compute_stats)
    .reset_index())
stats_tot['va_norm'] = '(Gesamt)'

stats = pd.concat([stats_va, stats_tot], ignore_index=True)
print(f"Stats rows: {len(stats)}")

# ── Severity score = |delta_eur| * max(n_pre, n_post) ────────────────────────
stats['severity'] = stats.apply(
    lambda r: abs(r['delta_eur']) * max(r['n_pre'], r['n_post'])
              if not np.isnan(r['delta_eur']) else 0,
    axis=1)

# ── Top-20 deviations across all customers × va_norm (excl. Gesamt) ──────────
cands = stats[(stats['va_norm'] != '(Gesamt)') & (stats['n_pre'] > 0)].copy()
cands_sorted = cands.sort_values('severity', ascending=False).head(20)
print("Top-20 deviations:")
print(cands_sorted[['Kunden Name', 'va_norm', 'avg_pre', 'avg_post', 'delta_pct', 'n_pre', 'n_post']].to_string())

# ── Sample 5 PRE + 5 POST per customer (all va_norm combined) ────────────────
SAMPLE_COLS = [
    'Leistungsdatum', 'Rechnungsnummer', 'Ausgangsbordero', 'va_norm',
    'Verkehrsart', 'Verkehrsart Detail', 'Versender PLZ', 'Versender Land',
    'Empfänger Land', 'Empfänger PLZ', 'route_2',
    'Colli', 'Tonnage (eff.)', 'Lademeter', 'Volumen',
    'Erlöse Fracht', 'Erlöse Diesel', 'Erlöse Maut', 'Erlöse Nebengebühr',
    'Erloese', 'Kosten Gesamt', 'DB II', 'DB II%',
    'Kunden Nr BK', 'Kunden Name', 'periode'
]
# Keep only existing cols
SAMPLE_COLS = [c for c in SAMPLE_COLS if c in df20.columns]

def pick_representative(grp, n=5):
    """Pick n rows closest to the median Erloese."""
    if len(grp) == 0:
        return grp
    med = grp['Erloese'].median()
    grp = grp.copy()
    grp['_dist'] = (grp['Erloese'] - med).abs()
    return grp.sort_values('_dist').head(n).drop(columns=['_dist'])

samples = []
for knr in top20_nrs:
    sub = df20[df20['Kunden Nr BK'] == knr]
    for per in ['PRE', 'POST']:
        s = sub[sub['periode'] == per]
        rep = pick_representative(s[SAMPLE_COLS], n=5)
        samples.append(rep)

samples_df = pd.concat(samples, ignore_index=True)
print(f"Samples: {len(samples_df)} rows")

# ── Abrechnungsbasis per customer (inferred via correlation with Erlöse) ───────
# Priority order: correlations determine the best billing dimension per customer.
# Fallback chain if too few valid rows: Lademeter → Tonnage (eff.) → Volumen → Colli
BILLING_COLS = [c for c in ['Stellplätze', 'Lademeter', 'Tonnage (eff.)', 'Volumen', 'Colli']
                if c in df20.columns]
BILLING_FALLBACK = [c for c in ['Lademeter', 'Tonnage (eff.)', 'Volumen', 'Colli']
                    if c in df20.columns]

def infer_abrechnungsbasis(cust_df):
    """
    Return (best_col, corr) by finding the billing dimension most correlated
    with Erlöse.  Requires >= 10 rows with billing_col > 0.
    Falls back through BILLING_FALLBACK if no dimension qualifies.
    """
    best_col, best_corr = None, -1.0
    for col in BILLING_COLS:
        sub = cust_df[['Erloese', col]].dropna()
        sub = sub[sub[col] > 0]
        if len(sub) < 10:
            continue
        corr = sub[col].corr(sub['Erloese'])
        if corr > best_corr:
            best_corr, best_col = corr, col
    if best_col is None:
        best_col = BILLING_FALLBACK[0] if BILLING_FALLBACK else 'Lademeter'
        best_corr = np.nan
    return best_col, best_corr

basis_map = {}   # knr → (basis_col, corr)
for knr in top20_nrs:
    cust = df20[df20['Kunden Nr BK'] == knr]
    col, corr = infer_abrechnungsbasis(cust)
    basis_map[knr] = (col, round(float(corr), 3) if not np.isnan(corr) else None)

print("\nAbrechnungsbasis per customer:")
for knr, (col, corr) in basis_map.items():
    name = top20_meta.loc[top20_meta['kunden_nr'] == knr, 'kunden_name'].values
    name = name[0][:35] if len(name) else str(knr)
    print(f"  {name:35s} → {col:18s}  (corr={corr})")

# ── Route-level outlier analysis (|Δ €/unit| > 7 %, top-5 per Relation) ──────
# Key improvement over naive Erlöse comparison:
#   Deviation is computed as price-per-unit (PPU = Erlöse / billing_dim), so a
#   POST shipment with more pallets/LDM than the PRE baseline is correctly handled.
#   PRE reference is matched by similar billing-dimension size, not just raw Erlöse.
if all(c in df20.columns for c in ['Versender PLZ', 'Empfänger PLZ']):
    df20 = df20.copy()
    df20['route_key'] = np.where(
        df20['Versender PLZ'].notna() & df20['Empfänger PLZ'].notna(),
        df20['Versender PLZ'].astype(str).str.strip() + '→' +
        df20['Empfänger PLZ'].astype(str).str.strip(),
        np.nan
    )

    outlier_parts = []

    for knr in top20_nrs:
        basis_col, _ = basis_map[knr]
        cust = df20[df20['Kunden Nr BK'] == knr]
        pre  = cust[cust['periode'] == 'PRE'].dropna(subset=['route_key'])
        post = cust[cust['periode'] == 'POST'].dropna(subset=['route_key'])

        if len(pre) == 0 or len(post) == 0:
            continue

        shared_routes = set(pre['route_key'].unique()) & set(post['route_key'].unique())

        # Fallback order for per-route dimension: customer basis first, then others
        route_fallback = [basis_col] + [c for c in BILLING_FALLBACK if c != basis_col]

        for route in shared_routes:
            pre_all  = pre[pre['route_key'] == route].copy()
            post_all = post[post['route_key'] == route].copy()

            # Try billing dimensions in priority order until we have ≥ 3 PRE rows
            pre_r = post_r = used_col = None
            for try_col in route_fallback:
                if try_col not in pre_all.columns:
                    continue
                _pre  = pre_all[pre_all[try_col].notna()  & (pre_all[try_col]  > 0)].copy()
                _post = post_all[post_all[try_col].notna() & (post_all[try_col] > 0)].copy()
                if len(_pre) >= 3 and len(_post) >= 1:
                    pre_r, post_r, used_col = _pre, _post, try_col
                    break
            if pre_r is None:
                continue

            pre_r['_ppu']  = pre_r['Erloese']  / pre_r[used_col]
            ppu_pre_median = pre_r['_ppu'].median()
            if pd.isna(ppu_pre_median) or ppu_pre_median == 0:
                continue

            post_r['_ppu'] = post_r['Erloese'] / post_r[used_col]
            post_r['_deviation_pct'] = (post_r['_ppu'] - ppu_pre_median) / abs(ppu_pre_median) * 100

            # Filter: |Δ €/unit| > 7 %
            outs = post_r[post_r['_deviation_pct'].abs() > 7.0].copy()
            if len(outs) == 0:
                continue

            # Top 5 by |Δ%| descending
            outs = (outs
                    .assign(_abs=outs['_deviation_pct'].abs())
                    .sort_values('_abs', ascending=False)
                    .drop(columns=['_abs'])
                    .head(5))
            outs['_row_type']      = 'POST_OUTLIER'
            outs['_ppu_pre_route'] = ppu_pre_median
            outs['_abr_basis']     = used_col
            outs['_abr_wert']      = outs[used_col]
            outs['_kunden_nr']     = knr
            outs['_route']         = route
            keep  = [c for c in SAMPLE_COLS if c in outs.columns]
            extra = ['_ppu','_deviation_pct','_row_type','_ppu_pre_route',
                     '_abr_basis','_abr_wert','_kunden_nr','_route']
            outs = outs[keep + extra]

            # ── PRE reference: size-matched to typical POST outlier ───────────
            target_abr = outs[used_col].median()
            pre_s = pre_r[[c for c in SAMPLE_COLS if c in pre_r.columns]].copy()
            pre_s['_dist'] = (pre_s[used_col] - target_abr).abs()
            pre_ref = pre_s.sort_values('_dist').head(1).drop(columns=['_dist']).copy()
            pre_ref['_ppu']          = pre_ref['Erloese'] / pre_ref[used_col]
            pre_ref['_row_type']     = 'PRE_REF'
            pre_ref['_ppu_pre_route']= ppu_pre_median
            pre_ref['_abr_basis']    = used_col
            pre_ref['_abr_wert']     = pre_ref[used_col]
            pre_ref['_deviation_pct']= np.nan
            pre_ref['_kunden_nr']    = knr
            pre_ref['_route']        = route

            outlier_parts.append(pd.concat([pre_ref, outs], ignore_index=True))

    route_outliers = (pd.concat(outlier_parts, ignore_index=True)
                      if outlier_parts else pd.DataFrame())
    print(f"\nRoute outliers: {len(route_outliers)} rows across {len(outlier_parts)} relations")
else:
    print("[WARN] 'Versender PLZ' / 'Empfänger PLZ' nicht in df20 — Route-Ausreißer übersprungen")
    route_outliers = pd.DataFrame()

with open(OUT / 'top20_abw_route_outliers.pkl', 'wb') as f:
    pickle.dump(route_outliers, f)
print("Saved top20_abw_route_outliers.pkl")

# ── Save ─────────────────────────────────────────────────────────────────────
with open(OUT / 'top20_abw_stats.pkl', 'wb') as f:
    pickle.dump({'stats': stats, 'top20_deviations': cands_sorted,
                 'top20_meta': top20_meta, 'basis_map': basis_map}, f)

with open(OUT / 'top20_abw_samples.pkl', 'wb') as f:
    pickle.dump(samples_df, f)

print("Done. Saved top20_abw_stats.pkl, top20_abw_samples.pkl and top20_abw_route_outliers.pkl")
