"""AX sub-row classification and Dinas per-invoice aggregation (v1.9 §2e).

v1.9.5 adds aggregate_ax_per_cluster() which aggregates physical quantities
per ZGI cluster from Abrechnungsstrecken before DLV lookup, correcting the
degressive-rate bias when multiple shipments share one billing cluster.
"""
from __future__ import annotations

import logging
from typing import Sequence

import pandas as pd

logger = logging.getLogger(__name__)


def _nonempty(val: object) -> bool:
    """Return True if val is a non-empty, non-NaN string."""
    if val is None:
        return False
    s = str(val).strip()
    return s not in ("", "nan", "NaN", "None")


def _nonempty_numeric(val: object) -> bool:
    """Return True if val is a non-NaN, non-None number. Zero is valid."""
    if val is None:
        return False
    try:
        return not pd.isna(float(val))
    except (TypeError, ValueError):
        return False


def classify_ax_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Add boolean classification columns to an AX billing DataFrame.

    Columns added:
      - ``has_ms``       : Mastersendung field is non-empty
      - ``has_ua``       : Unterauftrag field is non-empty
      - ``is_sub``       : Sub-row  (has_ms AND NOT has_ua)
      - ``is_master``    : Master-row (has_ua)
      - ``is_standalone``: Standalone row (NOT has_ms AND NOT has_ua)

    The Mastersendung column ("zusammengefasst in") is the sole source of
    truth — no Tonnage proxy is used (v1.9 §2e Rule A).
    """
    df = df.copy()
    df["has_ms"] = df["Mastersendung"].apply(_nonempty)
    df["has_ua"] = df["Unterauftrag"].apply(_nonempty)
    df["is_sub"] = df["has_ms"] & ~df["has_ua"]
    df["is_master"] = df["has_ua"]
    df["is_standalone"] = ~df["has_ms"] & ~df["has_ua"]
    return df


def filter_comparison_set(df: pd.DataFrame) -> pd.DataFrame:
    """Return only master and standalone rows (drop sub-rows).

    Expects the classification columns added by :func:`classify_ax_rows`.
    Sub-rows carry partial revenue that is already accounted for in their
    master row, so they must not be compared in isolation (v1.9 §2e Rule A).
    """
    if "is_sub" not in df.columns:
        df = classify_ax_rows(df)
    return df[~df["is_sub"]].copy()


def aggregate_dinas_per_invoice(
    df: pd.DataFrame,
    *,
    rn_col: str = "Rechnungsnummer",
    sender_plz_col: str = "Sender_PLZ",
    empf_plz_col: str = "Empfänger_PLZ",
    date_col: str = "Ladedatum",
    agg_cols: Sequence[str] = (
        "Gewicht_kg",
        "Lademeter",
        "Stellplätze",
        "Erlöse_Fracht",
        "Erlöse_Diesel",
        "Erlöse_Maut",
    ),
) -> pd.DataFrame:
    """Aggregate Dinas positions per invoice, then per routing key.

    Groups by (Rechnungsnummer, Sender_PLZ, Empfänger_PLZ, Ladedatum).
    Positions from different invoices are **never** merged together
    (v1.9 §2e Rule B).

    Parameters
    ----------
    df:
        Raw Dinas positions DataFrame.
    rn_col, sender_plz_col, empf_plz_col, date_col:
        Column name overrides for the grouping key.
    agg_cols:
        Numeric columns to sum within each group.  Columns absent from
        *df* are silently skipped.

    Returns
    -------
    Aggregated DataFrame with an additional ``n_positionen`` counter column.
    """
    key = [rn_col, sender_plz_col, empf_plz_col, date_col]
    present_agg = [c for c in agg_cols if c in df.columns]
    agg_spec: dict = {"n_positionen": (rn_col, "count")}
    for c in present_agg:
        agg_spec[c] = (c, "sum")

    return (
        df.groupby(key, dropna=False)
        .agg(**agg_spec)
        .reset_index()
    )


def reconstruct_ax_master(
    master_row: pd.Series,
    sub_rows: pd.DataFrame,
    *,
    physical_cols: Sequence[str] = (
        "Tonnage (eff.)",
        "Lademeter",
        "Stellplätze",
        "Volumen",
        "Colli",
    ),
    erloes_cols: Sequence[str] = (
        "Erlöse Fracht",
        "Erlöse Diesel",
        "Erlöse Maut",
        "Erlöse Nebengebühr",
        "Erlöse Peak",
        "Erlöse Lademittel",
    ),
    rn_col: str = "Rechnungsnummer",
) -> dict:
    """Reconstruct effective values for a master row from its sub-rows.

    Rules (v1.9.2 §2e Rule E):
    - Physical parameters: master value if non-NaN/non-None; sum(subs) as
      fallback only when the master field is empty. Zero is a valid master value.
    - Revenue columns: always sum(sub_rows) — master carries no own revenues.
    - Invoice numbers: collected from sub_rows[rn_col], deduplicated and sorted.
    - Master vs sub-sum discrepancies in physical fields are data redundancy,
      not audit findings.

    Parameters
    ----------
    master_row:
        The single master row (pd.Series).
    sub_rows:
        DataFrame containing all sub-rows that belong to this master.
    physical_cols:
        Columns for which the master value leads (sub-sum is fallback only).
    erloes_cols:
        Revenue columns always taken from subs (master has no own revenues).
    rn_col:
        Column holding invoice numbers; deduplicated list returned as
        ``"rechnungsnummern"`` in the output dict.

    Returns
    -------
    dict mapping column names to reconstructed values, plus
    ``"rechnungsnummern"`` (sorted list of unique invoice numbers from subs).
    """
    result: dict = {}

    for col in physical_cols:
        master_val = master_row.get(col) if hasattr(master_row, "get") else (
            master_row[col] if col in master_row.index else None
        )
        if _nonempty_numeric(master_val):
            result[col] = float(master_val)
        elif col in sub_rows.columns:
            result[col] = pd.to_numeric(sub_rows[col], errors="coerce").fillna(0.0).sum()
        else:
            result[col] = 0.0

    for col in erloes_cols:
        if col in sub_rows.columns:
            result[col] = pd.to_numeric(sub_rows[col], errors="coerce").fillna(0.0).sum()
        else:
            result[col] = 0.0

    if rn_col in sub_rows.columns:
        rns = (
            sub_rows[rn_col]
            .dropna()
            .astype(str)
            .str.strip()
            .pipe(lambda s: s[s.str.len() > 0])
            .unique()
            .tolist()
        )
        result["rechnungsnummern"] = sorted(rns)
    else:
        result["rechnungsnummern"] = []

    return result


def aggregate_ax_per_cluster(
    ax_df: pd.DataFrame,
    abr_df: pd.DataFrame | None,
    *,
    ax_auftr_col: str = "Auftragsnummer",
    abr_auftr_col: str = "Auftragsnummer",
    abr_own_col: str = "Abrechnungsstrecke",
    abr_zgi_col: str = "Zusammengefasst in",
    ton_col: str = "Tonnage (eff.)",
    ldm_col: str = "Lademeter",
    vol_col: str = "Volumen",
    erloes_cols: Sequence[str] = ("Erlöse Fracht",),
) -> pd.DataFrame:
    """Aggregate AX rows per ZGI cluster from Abrechnungsstrecken (v1.9.5 §2f).

    When multiple AX shipments are billed together under one
    "Zusammengefasst in" cluster, the DLV lookup must use the cluster's
    total billing weight — not individual per-row weights.  Using individual
    weights with a degressive tariff inflates the DLV-Soll, producing
    systematic false-positive M2* findings.

    Parameters
    ----------
    ax_df:
        AX rows to aggregate.  Must contain *ax_auftr_col*.
    abr_df:
        Abrechnungsstrecken DataFrame with columns *abr_auftr_col*,
        *abr_own_col*, and *abr_zgi_col*.  Pass ``None`` to skip clustering
        (returns *ax_df* unchanged, with a warning).
    ax_auftr_col, abr_auftr_col:
        Column holding shipment order numbers in each DataFrame.
    abr_own_col:
        Column with the row's own Abrechnungsstrecke ID.
    abr_zgi_col:
        Column holding the cluster master reference ("Zusammengefasst in").
    ton_col, ldm_col, vol_col:
        Physical quantity column names to aggregate.
    erloes_cols:
        Revenue column names to aggregate.

    Returns
    -------
    DataFrame with one row per ZGI cluster for multi-row clusters, and
    unchanged rows for singletons.  Added columns:

    - ``_cluster_id``       : ZGI master Abrechnungsstrecke ID (str)
    - ``_n_cluster_rows``   : number of AX rows in this cluster
    - ``_auftr_nrs``        : sorted list of Auftragsnummern in the cluster

    For single-row clusters, ``_cluster_id`` equals the row's own
    Auftragsnummer and ``_n_cluster_rows`` is 1.

    Notes
    -----
    Clusters where rows span different CC+PLZ combinations are treated as
    singleton lookups per row (logged as a warning); this should not occur
    with HERMA data but is a defensive guard.
    """
    if abr_df is None:
        logger.warning(
            "aggregate_ax_per_cluster: abr_df is None — returning ax_df unchanged"
        )
        out = ax_df.copy()
        out["_cluster_id"] = out[ax_auftr_col].astype(str)
        out["_n_cluster_rows"] = 1
        out["_auftr_nrs"] = out[ax_auftr_col].apply(lambda v: [str(v)])
        return out

    if abr_zgi_col not in abr_df.columns or abr_own_col not in abr_df.columns:
        logger.warning(
            "aggregate_ax_per_cluster: ZGI column '%s' or own-col '%s' missing — "
            "returning ax_df unchanged",
            abr_zgi_col, abr_own_col,
        )
        out = ax_df.copy()
        out["_cluster_id"] = out[ax_auftr_col].astype(str)
        out["_n_cluster_rows"] = 1
        out["_auftr_nrs"] = out[ax_auftr_col].apply(lambda v: [str(v)])
        return out

    def _norm(v: object) -> str:
        try:
            return str(int(float(str(v).strip())))
        except (ValueError, TypeError):
            return ""

    # Build ZGI cluster mapping: each Abrechnungsstrecke → cluster master ID
    abr = abr_df.copy()
    abr["_own_n"] = abr[abr_own_col].apply(_norm)
    abr["_zgi_n"] = abr[abr_zgi_col].apply(lambda v: _norm(v) if pd.notna(v) else "")
    # Self-referential rows are masters; ZGI=="": standalone (own cluster)
    abr["_cluster_id"] = abr["_zgi_n"].where(abr["_zgi_n"] != "", abr["_own_n"])
    abr["_auftr_n"] = abr[abr_auftr_col].apply(_norm)

    auftr_to_cluster: dict[str, str] = (
        abr.set_index("_auftr_n")["_cluster_id"].to_dict()
    )

    # Assign cluster_id to each AX row
    ax = ax_df.copy()
    ax["_auftr_n"] = ax[ax_auftr_col].astype(str).str.strip().apply(_norm)
    ax["_cluster_id"] = ax["_auftr_n"].map(auftr_to_cluster)

    # Rows not found in Abrechnungsstrecken → own Auftragsnr as cluster
    missing_mask = ax["_cluster_id"].isna()
    if missing_mask.any():
        logger.debug(
            "aggregate_ax_per_cluster: %d AX rows not found in Abrechnungsstrecken "
            "— treated as singletons",
            missing_mask.sum(),
        )
    ax.loc[missing_mask, "_cluster_id"] = ax.loc[missing_mask, "_auftr_n"]

    # Identify multi-row clusters
    cluster_sizes = ax.groupby("_cluster_id")[ax_auftr_col].transform("count")
    multi_mask = cluster_sizes >= 2

    # ── Validate destination uniformity for multi-row clusters ──────────────
    empf_plz_col_candidates = ["Empfänger PLZ", "empf_plz", "plz"]
    cc_col_candidates = ["Empfänger Land", "cc", "Nach Land"]
    empf_col = next((c for c in empf_plz_col_candidates if c in ax.columns), None)
    cc_col   = next((c for c in cc_col_candidates if c in ax.columns), None)

    if empf_col and cc_col:
        mixed_clusters = (
            ax[multi_mask]
            .groupby("_cluster_id")
            .filter(lambda g: g[cc_col].nunique() > 1 or g[empf_col].nunique() > 1)
            ["_cluster_id"].unique()
        )
        if len(mixed_clusters):
            logger.warning(
                "aggregate_ax_per_cluster: %d clusters have mixed CC+PLZ — "
                "treated as singletons: %s",
                len(mixed_clusters), mixed_clusters[:5],
            )
            multi_mask = multi_mask & ~ax["_cluster_id"].isin(mixed_clusters)

    # ── Process singleton rows (pass-through) ───────────────────────────────
    singleton_rows = ax[~multi_mask].copy()
    singleton_rows["_n_cluster_rows"] = 1
    singleton_rows["_auftr_nrs"] = singleton_rows[ax_auftr_col].apply(lambda v: [str(v)])
    singleton_rows = singleton_rows.drop(columns=["_auftr_n"])

    # ── Aggregate multi-row clusters ─────────────────────────────────────────
    multi_rows = ax[multi_mask].copy()

    def _agg_cluster(grp: pd.DataFrame) -> pd.Series:
        out: dict = {}
        # Take first value for non-aggregated columns
        for col in ax.columns:
            if col not in (ton_col, ldm_col, vol_col, *erloes_cols, "_auftr_n", "_cluster_id"):
                out[col] = grp[col].iloc[0]
        # Sum physical quantities
        for col in (ton_col, ldm_col, vol_col):
            if col in grp.columns:
                out[col] = pd.to_numeric(grp[col], errors="coerce").fillna(0.0).sum()
        # Sum revenue columns
        for col in erloes_cols:
            if col in grp.columns:
                out[col] = pd.to_numeric(grp[col], errors="coerce").fillna(0.0).sum()
        out["_n_cluster_rows"] = len(grp)
        out["_auftr_nrs"] = sorted(grp[ax_auftr_col].astype(str).tolist())
        return pd.Series(out)

    if len(multi_rows):
        aggregated = (
            multi_rows.groupby("_cluster_id", sort=False)
            .apply(_agg_cluster)
            .reset_index()
        )
    else:
        aggregated = pd.DataFrame()

    # ── Combine and return ───────────────────────────────────────────────────
    parts = [p for p in (singleton_rows, aggregated) if len(p)]
    if not parts:
        return ax_df.iloc[:0].copy()

    result = pd.concat(parts, ignore_index=True)
    # Ensure canonical column order: _cluster_id, _n_cluster_rows, _auftr_nrs first
    meta_cols = ["_cluster_id", "_n_cluster_rows", "_auftr_nrs"]
    other_cols = [c for c in result.columns if c not in meta_cols]
    return result[meta_cols + other_cols]
