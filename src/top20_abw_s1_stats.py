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

# ── Save ─────────────────────────────────────────────────────────────────────
with open(OUT / 'top20_abw_stats.pkl', 'wb') as f:
    pickle.dump({'stats': stats, 'top20_deviations': cands_sorted, 'top20_meta': top20_meta}, f)

with open(OUT / 'top20_abw_samples.pkl', 'wb') as f:
    pickle.dump(samples_df, f)

print("Done. Saved top20_abw_stats.pkl and top20_abw_samples.pkl")
