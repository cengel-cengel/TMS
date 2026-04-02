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

# ── Abrechnungsbasis per customer (min. Korrelation 0.90 erforderlich) ────────
# Für jeden Kunden: bilateralste Dimension wählen.  Erreicht keine Dimension
# r ≥ 0.90, wird keine PPU-Analyse durchgeführt (basis_col = None).
# Kein Fallback auf schwächere Dimensionen – Qualität > Abdeckung.
MIN_CORR = 0.90
BILLING_COLS = [c for c in ['Stellplätze', 'Lademeter', 'Tonnage (eff.)', 'Volumen', 'Colli']
                if c in df20.columns]

def infer_abrechnungsbasis(cust_df):
    """
    Return (best_col, corr).  best_col is None if no dimension reaches MIN_CORR.
    Correlation computed only on rows where billing column > 0 (>= 10 rows required).
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
    if best_corr < MIN_CORR:
        return None, best_corr   # unterhalb Schwelle → keine PPU-Analyse
    return best_col, best_corr

basis_map = {}   # knr → (basis_col_or_None, corr)
for knr in top20_nrs:
    cust = df20[df20['Kunden Nr BK'] == knr]
    col, corr = infer_abrechnungsbasis(cust)
    basis_map[knr] = (col, round(float(corr), 3) if (corr is not None and not np.isnan(corr)) else corr)

print(f"\nAbrechnungsbasis per customer (Schwelle: r ≥ {MIN_CORR}):")
for knr, (col, corr) in basis_map.items():
    name = top20_meta.loc[top20_meta['kunden_nr'] == knr, 'kunden_name'].values
    name = name[0][:35] if len(name) else str(knr)
    status = f"→ {col:18s}  (corr={corr})" if col else f"→ [übersprungen]         (best corr={corr})"
    print(f"  {name:35s} {status}")

# ── Route-Risiko-Analyse: Top-5 Relationen je Kunde mit höchstem Ertragsrisiko ─
# Nur Unterfakturierung (POST-Rate < PRE-Rate) wird ausgewertet.
# VA-Trennung wird bewusst NICHT vorgenommen: SA/Export/Charter war in Dinas
# nicht zuverlässig unterschieden, weshalb alle Sendungen einer Relation zusammen
# verglichen werden.
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
        if basis_col is None:
            continue   # Korrelation zu schwach – keine PPU-Analyse möglich

        cust  = df20[df20['Kunden Nr BK'] == knr]
        pre   = cust[cust['periode'] == 'PRE'].dropna(subset=['route_key'])
        post  = cust[cust['periode'] == 'POST'].dropna(subset=['route_key'])

        if len(pre) == 0 or len(post) == 0:
            continue

        shared_routes = set(pre['route_key'].unique()) & set(post['route_key'].unique())
        route_candidates = {}   # route → (pre_ref_df, outs_df, total_loss, ppu_pre_median)

        for route in shared_routes:
            pre_r  = pre[pre['route_key']   == route].copy()
            post_r = post[post['route_key'] == route].copy()

            # Nur Zeilen mit gültigem Abrechnungswert (> 0)
            pre_r  = pre_r[pre_r[basis_col].notna()   & (pre_r[basis_col]   > 0)]
            post_r = post_r[post_r[basis_col].notna() & (post_r[basis_col] > 0)]
            if len(pre_r) < 3 or len(post_r) == 0:
                continue

            pre_r  = pre_r.copy()
            post_r = post_r.copy()
            pre_r['_ppu']   = pre_r['Erloese']  / pre_r[basis_col]
            ppu_pre_median  = pre_r['_ppu'].median()
            if pd.isna(ppu_pre_median) or ppu_pre_median == 0:
                continue

            post_r['_ppu']         = post_r['Erloese'] / post_r[basis_col]
            post_r['_deviation_pct'] = (post_r['_ppu'] - ppu_pre_median) / abs(ppu_pre_median) * 100

            # Nur Unterfakturierung: POST < PRE um mehr als 7 %
            outs = post_r[post_r['_deviation_pct'] < -7.0].copy()
            if len(outs) == 0:
                continue

            # Erwarteter Verlust je Sendung: (PRE-Rate − POST-Rate) × Einheiten
            outs['_expected_loss'] = (ppu_pre_median - outs['_ppu']) * outs[basis_col]
            total_route_loss = outs['_expected_loss'].sum()

            # PRE-Referenz: größenbasiert (ähnliche Einheitenmenge wie typischer POST-Ausreißer)
            target_abr = outs[basis_col].median()
            pre_s = pre_r[[c for c in SAMPLE_COLS if c in pre_r.columns]].copy()
            pre_s['_dist'] = (pre_s[basis_col] - target_abr).abs()
            pre_ref = pre_s.sort_values('_dist').head(1).drop(columns=['_dist']).copy()
            pre_ref['_ppu']            = pre_ref['Erloese'] / pre_ref[basis_col]
            pre_ref['_expected_loss']  = 0.0
            pre_ref['_row_type']       = 'PRE_REF'
            pre_ref['_ppu_pre_route']  = ppu_pre_median
            pre_ref['_abr_basis']      = basis_col
            pre_ref['_abr_wert']       = pre_ref[basis_col]
            pre_ref['_deviation_pct']  = np.nan
            pre_ref['_kunden_nr']      = knr
            pre_ref['_route']          = route
            pre_ref['_total_route_loss'] = total_route_loss

            outs['_row_type']          = 'POST_OUTLIER'
            outs['_ppu_pre_route']     = ppu_pre_median
            outs['_abr_basis']         = basis_col
            outs['_abr_wert']          = outs[basis_col]
            outs['_kunden_nr']         = knr
            outs['_route']             = route
            outs['_total_route_loss']  = total_route_loss
            keep  = [c for c in SAMPLE_COLS if c in outs.columns]
            extra = ['_ppu','_deviation_pct','_expected_loss','_row_type',
                     '_ppu_pre_route','_abr_basis','_abr_wert',
                     '_kunden_nr','_route','_total_route_loss']
            outs  = outs[keep + extra]

            route_candidates[route] = (pre_ref, outs, total_route_loss, ppu_pre_median)

        if not route_candidates:
            continue

        # Top-5 Relationen nach erwartetem Gesamtverlust (absteigend)
        top5_routes = sorted(route_candidates,
                             key=lambda r: route_candidates[r][2],
                             reverse=True)[:5]

        for route in top5_routes:
            pre_ref, outs, total_loss, _ = route_candidates[route]
            outs_top5 = outs.sort_values('_expected_loss', ascending=False).head(5)
            outlier_parts.append(pd.concat([pre_ref, outs_top5], ignore_index=True))

    route_outliers = (pd.concat(outlier_parts, ignore_index=True)
                      if outlier_parts else pd.DataFrame())
    n_cust = route_outliers['_kunden_nr'].nunique() if len(route_outliers) else 0
    print(f"\nRoute-Risiko-Analyse: {len(route_outliers)} Zeilen, "
          f"{len(outlier_parts)} Relationen, {n_cust} Kunden")
else:
    print("[WARN] 'Versender PLZ' / 'Empfänger PLZ' nicht in df20 — Route-Analyse übersprungen")
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

print("Done. Saved top20_abw_stats.pkl, top20_abw_samples.pkl und top20_abw_route_outliers.pkl")
