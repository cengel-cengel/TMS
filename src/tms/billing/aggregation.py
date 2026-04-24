"""AX sub-row classification and Dinas per-invoice aggregation (v1.9 §2e)."""
from __future__ import annotations

from typing import Sequence

import pandas as pd


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
