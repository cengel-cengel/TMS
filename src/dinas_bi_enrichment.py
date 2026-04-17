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
      sendungs_nr, rechnung_nr, netto_fracht, netto_total, n_rows,
      flag_gutschrift_solo  – True when only negative-fracht rows exist (no paired Rechnung)

    netto_total = sum(total_items): used for Komplettpreis comparison
    netto_fracht = sum(fracht):     used for non-Komplettpreis (BI has fracht breakdown)
    """
    grp = df_cache.groupby('sendungs_nr', as_index=False).agg(
        rechnung_nr= ('rechnung_nr',  'first'),
        netto_fracht=('fracht',       'sum'),
        netto_total= ('total_items',  'sum'),
        n_rows=      ('fracht',       'count'),
        max_fracht=  ('fracht',       'max'),
        min_fracht=  ('fracht',       'min'),
    )
    grp['flag_gutschrift_solo'] = (grp['max_fracht'] <= 0) & (grp['min_fracht'] < 0)
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
        dinas_net[['_snr', 'netto_fracht', 'netto_total', 'flag_gutschrift_solo']],
        on='_snr', how='left'
    )
    # Choose comparison basis: total for Komplettpreis, fracht otherwise
    merged['dinas_netto_compare'] = merged['netto_total'].where(
        merged['flag_komplettpreis'], merged['netto_fracht'])
    merged['dinas_vs_bi_diff_eur'] = merged['dinas_netto_compare'] - merged['erloese_fracht_effektiv']
    eff = merged['erloese_fracht_effektiv'].abs().replace(0, float('nan'))
    merged['dinas_vs_bi_diff_pct'] = (merged['dinas_vs_bi_diff_eur'] / eff * 100).round(2)

    sp = sammelposten_stats(bi_e)
    n_matched   = merged['dinas_netto_compare'].notna().sum()
    n_within_5  = (merged['dinas_vs_bi_diff_pct'].abs() <= 5).sum()
    n_solo_gut  = int(dinas_net['flag_gutschrift_solo'].sum())
    n_kp        = int(bi_e['flag_komplettpreis'].sum())

    stats = {
        **sp,
        'n_komplettpreis':   n_kp,
        'pct_komplettpreis': round(n_kp / len(bi_e) * 100, 1) if len(bi_e) else 0,
        'n_dinas_matched':   int(n_matched),
        'n_within_5pct':     int(n_within_5),
        'pct_within_5pct':   round(n_within_5 / n_matched * 100, 1) if n_matched else 0.0,
        'n_gutschrift_solo': n_solo_gut,
    }

    return merged, dinas_net, stats
