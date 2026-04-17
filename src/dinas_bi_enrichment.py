"""
dinas_bi_enrichment.py — three BI-data enrichments for billing accuracy reports.

A) enrich_bi()         — Komplettpreis flag + erloese_fracht_effektiv
B) add_bi_split_flag() — Sammelposten flag (same RN → multiple SNRs)
C) net_dinas_fracht()  — Gutschrift netting to SNR-level net fracht
"""
import pandas as pd


# ── A: Komplettpreis-Erkennung ────────────────────────────────────────────────
def enrich_bi(df: pd.DataFrame) -> pd.DataFrame:
    """
    For rows where Erlöse Fracht == 0 AND Erloese > 0 (Komplettpreis invoices):
      - erloese_fracht_effektiv = Erloese (use total as effective fracht)
      - flag_komplettpreis = True
    Otherwise erloese_fracht_effektiv = Erlöse Fracht (raw).
    Applies to PRE and POST; caller should filter by periode if needed.
    """
    df = df.copy()
    ef = df['Erlöse Fracht'].fillna(0)
    er = df['Erloese'].fillna(0)
    kp = (ef == 0) & (er > 0)
    df['flag_komplettpreis'] = kp
    df['erloese_fracht_effektiv'] = ef.astype(float)
    df.loc[kp, 'erloese_fracht_effektiv'] = df.loc[kp, 'Erloese'].astype(float)
    return df


# ── B: Sammelposten-Detektor ─────────────────────────────────────────────────
def add_bi_split_flag(df: pd.DataFrame) -> pd.DataFrame:
    """
    Flags rows whose Rechnungsnummer is shared by ≥ 2 distinct Auftragsnummern.
    Adds:
      n_snrs_per_rn  – count of SNRs under this RN
      flag_bi_split  – True when n_snrs_per_rn > 1
    """
    df = df.copy()
    cnt = df.groupby('Rechnungsnummer')['Auftragsnummer'].transform('count')
    df['n_snrs_per_rn'] = cnt.fillna(0).astype(int)
    df['flag_bi_split']  = cnt > 1
    return df


def sammelposten_stats(df: pd.DataFrame) -> dict:
    """Return a summary dict for logging. Calls add_bi_split_flag if needed."""
    if 'flag_bi_split' not in df.columns:
        df = add_bi_split_flag(df)
    n_total = len(df)
    n_split = int(df['flag_bi_split'].sum())
    n_rns   = int(df[df['flag_bi_split']]['Rechnungsnummer'].nunique())
    return {
        'n_snrs':       n_total,
        'n_split_snrs': n_split,
        'pct_split':    round(n_split / n_total * 100, 1) if n_total else 0.0,
        'n_split_rns':  n_rns,
    }


# ── C: Gutschriften-Nettierung ────────────────────────────────────────────────
def net_dinas_fracht(df_cache: pd.DataFrame) -> pd.DataFrame:
    """
    Collapses DINAS cache to one row per sendungs_nr.
    Sums fracht AND total_items (all categories) per SNR.

    Returns DataFrame with columns:
      sendungs_nr, rechnung_nr, netto_fracht, netto_total, n_rows, n_distinct_rn,
      flag_gutschrift_solo  – True when only negative-fracht rows exist (no paired Rechnung)
      flag_multi_rn_dinas   – True when n_rows > 1 (re-invoicing / supplemental artifact)

    netto_total = sum(total_items): used for Komplettpreis comparison
    netto_fracht = sum(fracht):     used for non-Komplettpreis (BI has fracht breakdown)
    flag_multi_rn_dinas rows are shown in reports but excluded from ±5% accuracy counts.
    """
    grp = df_cache.groupby('sendungs_nr', as_index=False).agg(
        rechnung_nr=   ('rechnung_nr',  'first'),
        netto_fracht=  ('fracht',       'sum'),
        netto_total=   ('total_items',  'sum'),
        n_rows=        ('fracht',       'count'),
        n_distinct_rn= ('rechnung_nr',  'nunique'),
        max_fracht=    ('fracht',       'max'),
        min_fracht=    ('fracht',       'min'),
    )
    grp['flag_gutschrift_solo'] = (grp['max_fracht'] <= 0) & (grp['min_fracht'] < 0)
    grp['flag_multi_rn_dinas']  = grp['n_rows'] > 1
    grp['netto_fracht'] = grp['netto_fracht'].round(4)
    grp['netto_total']  = grp['netto_total'].round(4)
    return grp


# ── Convenience: full enrichment pipeline for one customer ──────────────────
def enrich_customer_bi(df_bi: pd.DataFrame, df_dinas: pd.DataFrame,
                       norm_fn=None) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """
    Applies all three enrichments and returns:
      (bi_enriched, dinas_net, stats_dict)

    Comparison logic:
      Komplettpreis rows  → compare DINAS netto_total  vs BI erloese_fracht_effektiv
      Non-Komplettpreis   → compare DINAS netto_fracht vs BI erloese_fracht_effektiv
    """
    import re

    def _default_norm(v):
        s = re.sub(r'\D', '', str(v)).lstrip('0')
        return s if s else str(v).strip()

    norm = norm_fn or _default_norm

    # A + B on BI
    bi_e = enrich_bi(df_bi)
    bi_e = add_bi_split_flag(bi_e)
    bi_e['_snr'] = bi_e['Auftragsnummer'].astype(str).apply(norm)

    # C on DINAS cache
    dinas_net = net_dinas_fracht(df_dinas)
    dinas_net['_snr'] = dinas_net['sendungs_nr'].astype(str).apply(norm)

    # Merge to compute per-row accuracy
    merged = bi_e.merge(
        dinas_net[['_snr', 'netto_fracht', 'netto_total',
                   'flag_gutschrift_solo', 'flag_multi_rn_dinas']],
        on='_snr', how='left'
    )
    merged['flag_multi_rn_dinas'] = merged['flag_multi_rn_dinas'].fillna(False).astype(bool)
    # Choose comparison basis: total for Komplettpreis, fracht otherwise
    merged['dinas_netto_compare'] = merged['netto_total'].where(
        merged['flag_komplettpreis'], merged['netto_fracht'])
    merged['dinas_vs_bi_diff_eur'] = merged['dinas_netto_compare'] - merged['erloese_fracht_effektiv']
    eff = merged['erloese_fracht_effektiv'].abs().replace(0, float('nan'))
    merged['dinas_vs_bi_diff_pct'] = (merged['dinas_vs_bi_diff_eur'] / eff * 100).round(2)

    sp = sammelposten_stats(bi_e)
    _has_match  = merged['dinas_netto_compare'].notna()
    _is_multi   = merged['flag_multi_rn_dinas']
    n_matched   = int(_has_match.sum())
    n_multi_rn  = int((_has_match & _is_multi).sum())
    _acc_base   = _has_match & ~_is_multi
    n_acc_base  = int(_acc_base.sum())
    n_within_5  = int((merged.loc[_acc_base, 'dinas_vs_bi_diff_pct'].abs() <= 5).sum())
    n_solo_gut  = int(dinas_net['flag_gutschrift_solo'].sum())
    n_kp        = int(bi_e['flag_komplettpreis'].sum())

    stats = {
        **sp,
        'n_komplettpreis':   n_kp,
        'pct_komplettpreis': round(n_kp / len(bi_e) * 100, 1) if len(bi_e) else 0,
        'n_dinas_matched':   n_matched,
        'n_multi_rn_dinas':  n_multi_rn,
        'n_acc_base':        n_acc_base,
        'n_within_5pct':     n_within_5,
        'pct_within_5pct':   round(n_within_5 / n_acc_base * 100, 1) if n_acc_base else 0.0,
        'n_gutschrift_solo': n_solo_gut,
    }

    return merged, dinas_net, stats


# ── AX-side cluster consolidation (POST) ─────────────────────────────────────
# STRICTLY SEPARATE from the DINAS PRE-side master logic above.
# DINAS uses 'Mastersendung' from the DINAS transport system.
# AX uses 'Zusammengefasst in' + 'Hauptabrechnungsstrecke' from the AX billing system.
# These two keys are numerically and semantically incompatible — do not mix them.

_AX_FIN_COLS = [
    'AX Fracht', 'AX Diesel', 'AX Maut', 'AX Nebengebühr',
    'AX Lademittel', 'AX Peak', 'AX EUST/Zoll', 'AX Versicherung', 'AX Gesamt',
]

# BI revenue columns summed across all cluster rows (master + subs) onto master.
_BI_ERLOES_COLS = [
    'Erlöse Fracht', 'Erlöse Diesel', 'Erlöse Maut', 'Erlöse Nebengebühr',
    'Erlöse Lademittel', 'Erlöse Peak', 'Erlöse EUST Zoll',
    'Erlöse Transportversicherung', 'Erloese',
]

# Physical shipment dimensions summed across cluster rows.
# Gewicht excluded: Master.Abrechnungsgewicht is ERKA-authoritative (Regel A, 99.76%).
_BI_PHYS_COLS = ['Lademeter', 'Stellplätze', 'Volumen']


def consolidate_clusters_ax(ax_df):
    """
    Reduce a raw Abrechnungsstrecken DataFrame to one row per billing cluster.

    Keeps only Hauptabrechnungsstrecke == 'Ja' rows (the master/Hauptabrechnung).
    Master.AbrGew == sum(all physical Gewicht in cluster) in 99.8 % of cases;
    the rare exception is a contractual minimum weight (e.g. Cyprus route).

    Returns (masters_df, stats_dict).
    """
    ZI  = 'Zusammengefasst in'
    HAB = 'Hauptabrechnungsstrecke'

    n_total    = len(ax_df)
    n_clusters = ax_df[ZI].nunique()

    masters    = ax_df[ax_df[HAB] == 'Ja'].copy()
    master_keys = set(masters[ZI].dropna())
    all_keys    = set(ax_df[ZI].dropna())
    no_master   = all_keys - master_keys

    if no_master:
        print(f'  ⚠ {len(no_master)} Cluster ohne Hauptabrechnungsstrecke=Ja → gedroppt')

    assert len(masters) == n_clusters - len(no_master), (
        f'Sanity: {len(masters)} master rows != {n_clusters - len(no_master)} expected'
    )

    stats = {
        'n_rows_total':         n_total,
        'n_clusters':           n_clusters,
        'n_masters':            len(masters),
        'n_subs':               n_total - len(masters),
        'n_clusters_no_master': len(no_master),
    }
    return masters, stats


def enrich_post_ax_clusters(post_df, ax_df, fin_cols=None):
    """
    Consolidate AX billing sub-shipments in post_df using Abrechnungsstrecken cluster keys.

    For each cluster in ax_df:
      - Master row (Hauptabrechnungsstrecke == 'Ja'): keeps its row, receives summed
        financials from all sub-rows in the same cluster.
      - Sub rows: financial columns accumulated onto master, then dropped.
      - Singleton clusters (no subs): pass through unchanged.

    Adds to each remaining post row:
      _master_nr   – own Auftragsnummer if AX-master, else None
      _sub_nrs     – comma-separated sub Auftragsnummern (master only)
      _n_subs      – count of accumulated sub rows
      _ist_master  – 'Ja' if AX-master, '' otherwise

    Returns (enriched_post_df, stats_dict).

    Weight note (ERKA-UI verified, Cluster 00194384):
      Master.Abrechnungsgewicht (col V) already contains the sum of all physical
      weights in the cluster (Sub 213 kg + Master 9952 kg = AbrGew 10165 kg).
      Master.Gewicht (col U) is only the master shipment's own physical weight.
      → Use tonnage_ax = master_row['Abrechnungsgewicht'] for rate lookups.
    """
    _base = list(fin_cols or _AX_FIN_COLS)
    _FIN  = _base + [c for c in _BI_ERLOES_COLS + _BI_PHYS_COLS if c not in _base]

    def _sid(v):
        try:
            return str(int(float(str(v).strip())))
        except Exception:
            return str(v).strip()

    ax = ax_df[['Zusammengefasst in', 'Hauptabrechnungsstrecke',
                'Auftragsnummer', 'Abrechnungsgewicht']].copy()
    ax['_auftr']   = ax['Auftragsnummer'].apply(_sid)
    ax['_cluster'] = ax['Zusammengefasst in'].apply(_sid)
    ax['_is_mstr'] = ax['Hauptabrechnungsstrecke'] == 'Ja'

    mstr_rows = ax[ax['_is_mstr']]
    sub_rows  = ax[~ax['_is_mstr']]

    # Set-based: an auftr is a master if it EVER appears with Haupt=Ja.
    # This handles the edge case where the same auftr appears in multiple AX rows.
    master_auftrs = set(mstr_rows['_auftr'])

    # Cluster lookups: master's auftr → cluster (used to accumulate sub sums onto master).
    # Sub's auftr → cluster (used to group sub financials for summation).
    master_auftr_to_cluster = dict(zip(mstr_rows['_auftr'], mstr_rows['_cluster']))
    sub_auftr_to_cluster    = dict(zip(sub_rows['_auftr'],  sub_rows['_cluster']))
    cluster_to_abrg         = dict(zip(mstr_rows['_cluster'], mstr_rows['Abrechnungsgewicht']))

    cluster_to_sub_auftr = (
        sub_rows.groupby('_cluster')['_auftr'].apply(list).to_dict()
    )

    post = post_df.copy()
    post['_auftr_s'] = post['Auftragsnummer'].apply(_sid)
    post['_ax_mstr'] = post['_auftr_s'].isin(master_auftrs)
    post['_sub_cl']  = post['_auftr_s'].map(sub_auftr_to_cluster)
    # Only drop a sub row if its cluster master is also present in post_df.
    # Orphan subs (master missing from filtered BI data) are kept as standalone rows.
    _master_clusters_in_post = {
        master_auftr_to_cluster[a]
        for a in post.loc[post['_ax_mstr'], '_auftr_s']
        if a in master_auftr_to_cluster
    }
    post['_ax_sub']  = post['_sub_cl'].isin(_master_clusters_in_post) & ~post['_ax_mstr']
    # Cluster for masters comes from master lookup; for subs from sub lookup
    post['_ax_cl']   = post['_auftr_s'].map(master_auftr_to_cluster).where(
        post['_ax_mstr'], post['_sub_cl']
    )

    n_subs_removed = int(post['_ax_sub'].sum())
    n_masters_found = int(post['_ax_mstr'].sum())
    n_unmatched     = int(post['_ax_cl'].isna().sum())

    present = [c for c in _FIN if c in post.columns]
    for c in present:
        post[c] = pd.to_numeric(post[c], errors='coerce')

    if n_subs_removed > 0 and present:
        # Identify dup-master clusters: clusters where >1 BI row has _ax_mstr=True.
        # These arise when the source system assigned the same Auftragsnummer to
        # distinct real shipments (data-quality artifact). Both rows must stay in
        # output and each must carry its own value — not a shared cluster sum.
        mstr_bi        = post[post['_ax_mstr']]
        _dup_cl_mask   = mstr_bi['_ax_cl'].duplicated(keep=False)
        _dup_clusters  = set(mstr_bi.loc[_dup_cl_mask, '_ax_cl'].dropna())

        # Hard sanity: dup-master clusters must have zero subs. If a dup-master
        # cluster had subs, additive fallback would add the sub sum to EVERY
        # duplicate master row (double-counting) — a bug the global sum test
        # would NOT catch (it's an intra-cluster redistribution error).
        if _dup_clusters:
            _sub_cl_counts = post[post['_ax_sub']].groupby('_sub_cl').size()
            _dup_with_subs = {cl: int(_sub_cl_counts[cl])
                              for cl in _dup_clusters if cl in _sub_cl_counts.index}
            if _dup_with_subs:
                raise AssertionError(
                    f'STOP: dup-master cluster(s) have subs > 0 — '
                    f'additive fallback would double-count sub contributions. '
                    f'Clusters: {_dup_with_subs}'
                )

        _clean_clusters = ~post['_ax_cl'].isin(_dup_clusters)
        _in_cluster     = (post['_ax_mstr'] | post['_ax_sub']) & _clean_clusters
        msk             = post['_ax_mstr']

        # Symmetric path: master[col] = sum(master + all subs in cluster, min_count=1).
        # min_count=1 returns NaN if every value is NaN, rather than 0.
        if _in_cluster.any():
            cluster_sums = post[_in_cluster].groupby('_ax_cl')[present].sum(min_count=1)
            msk_clean    = msk & _clean_clusters
            for c in present:
                post.loc[msk_clean, c] = post.loc[msk_clean, '_ax_cl'].map(cluster_sums[c])

        # Additive fallback for dup-master clusters: master[col] += subs.sum().
        # Verified safe only because subs == 0 for all dup-master clusters (see above).
        if _dup_clusters:
            msk_dup  = msk & post['_ax_cl'].isin(_dup_clusters)
            sub_sums = post[post['_ax_sub'] & post['_ax_cl'].isin(_dup_clusters)
                           ].groupby('_sub_cl')[present].sum(min_count=1)
            for c in present:
                added = post.loc[msk_dup, '_ax_cl'].map(sub_sums[c]).fillna(0)
                post.loc[msk_dup, c] = post.loc[msk_dup, c].fillna(0) + added

    post['_master_nr']  = post.apply(
        lambda r: r['_auftr_s'] if r['_ax_mstr'] else None, axis=1)
    post['_sub_nrs']    = post.apply(
        lambda r: ', '.join(cluster_to_sub_auftr.get(str(r['_ax_cl']), []))
        if r['_ax_mstr'] else None, axis=1)
    post['_n_subs']     = post['_sub_nrs'].apply(
        lambda v: len(v.split(',')) if isinstance(v, str) and v else 0)
    post['_ist_master'] = post['_ax_mstr'].map({True: 'Ja', False: ''})
    post['_ax_abrg']    = post['_ax_cl'].map(cluster_to_abrg)

    post = post[~post['_ax_sub']].copy()
    post.drop(columns=['_auftr_s', '_ax_cl', '_ax_mstr', '_ax_sub', '_sub_cl'],
              errors='ignore', inplace=True)

    n_ax_clusters    = ax['_cluster'].nunique()
    n_dup_master_cl  = len(_dup_clusters) if n_subs_removed > 0 and present else 0
    _dup_note        = f', {n_dup_master_cl} Dup-Master-Cluster (additiv)' if n_dup_master_cl else ''
    print(f'  AX-Cluster: {n_ax_clusters} Cluster, '
          f'{n_subs_removed} Subs entfernt → {len(post)} Rows verbleiben '
          f'({n_unmatched} Post-Rows nicht in AX-Datei{_dup_note})')

    return post, {
        'n_ax_clusters':        n_ax_clusters,
        'n_ax_subs':            n_subs_removed,
        'n_ax_masters':         n_masters_found,
        'n_post_unmatched':     n_unmatched,
        'n_dup_master_clusters': n_dup_master_cl,
    }
