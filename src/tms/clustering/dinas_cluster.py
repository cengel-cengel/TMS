"""Dinas-seitige Cluster-Aggregation aus dinas_pdfs.parquet.

Etappe 7b: Baut pro Dinas-Rechnung (rechnung_nr = PDF) eine Zeile mit
aggregierten Versand-Dimensionen und separierten Nebenkosten.

Verifikation (aus Vorab-Analyse):
  - PDF ↔ rechnung_nr ist strikt 1:1 (496 PDFs = 496 rechnung_nr)
  - Alle Invoice-Level-Felder (erka_kundennr, rechnung_date, template)
    sind konstant innerhalb einer PDF
  - leistung_date variiert innerhalb der PDF → min() verwendet
  - bordero_nr: mehrere pro Rechnung möglich; als distinkte Liste erfasst
  - is_correction = True wenn template == 'erka_correction' (226/5533 Rows,
    alle aus 17 Rechnungen)
"""
from __future__ import annotations

import ast
import logging
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Sonstige-Nebenkosten Kategorisierung
# ---------------------------------------------------------------------------

_THERMO_KEYWORDS = ("THERMO", "KÜHL", "KUEHL", "THERMOZUSCHLAG")
_MAUT_KEYWORDS   = ("MAUT", "NEBENKOSTENPAUSCHALE MAUT", "D-MAUT")


def _parse_sonstige(raw: str) -> list[dict]:
    """Parse sonstige column (JSON-list string) into list of dicts."""
    if not raw or raw == "[]":
        return []
    try:
        return ast.literal_eval(raw)
    except Exception:
        return []


def _categorise_sonstige(items: list[dict]) -> tuple[float, float, float]:
    """Return (maut_extra, thermo, other) from parsed sonstige items.

    D-MAUT items in sonstige are folded into maut_extra so that maut_eur
    consolidates all toll charges regardless of which column they appear in.
    """
    maut_extra = thermo = other = 0.0
    for it in items:
        try:
            amt = float(it.get("amount") or 0)
        except (TypeError, ValueError):
            continue
        lbl = str(it.get("label") or "").upper()
        if any(k in lbl for k in _THERMO_KEYWORDS):
            thermo += amt
        elif any(k in lbl for k in _MAUT_KEYWORDS):
            maut_extra += amt
        else:
            other += amt
    return maut_extra, thermo, other


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_dinas_clusters(dinas_df: pd.DataFrame) -> pd.DataFrame:
    """Build one row per Dinas invoice (rechnung_nr = cluster_id).

    Parameters
    ----------
    dinas_df:
        Full dinas_pdfs.parquet DataFrame (all ERKA, all templates).

    Returns
    -------
    DataFrame with one row per distinct rechnung_nr. Rows are sorted by
    cluster_id. Both erka_standard and erka_correction invoices are included;
    the ``is_correction`` flag distinguishes them.
    """
    rows: list[dict] = []

    for rnr, grp in dinas_df.groupby("rechnung_nr", sort=True):
        # --- invoice-level fields (constant within group) ------------------
        erka_knr  = str(grp["erka_kundennr"].iloc[0])
        rech_date = grp["rechnung_date"].iloc[0]
        is_corr   = bool((grp["template"] == "erka_correction").any())

        # leistungsdatum: take earliest service date in the cluster
        ldt_series = pd.to_datetime(grp["leistung_date"], errors="coerce").dropna()
        leist_date = ldt_series.min() if len(ldt_series) else pd.NaT

        # --- sendungen count -----------------------------------------------
        n_send = len(grp)

        # --- physical aggregates -------------------------------------------
        agg_kg  = float(grp["gewicht_kg"].sum())   # NaN-safe
        agg_stp = float(grp["stp"].sum())
        agg_ldm = float(grp["lm"].sum())
        # volume not available in current parquet extract
        agg_vol = 0.0

        # --- PLZ 2-digit sets ----------------------------------------------
        sender_plzs = sorted({
            str(p).strip()[:2]
            for p in grp["abs_plz"].dropna()
            if str(p).strip()
        })
        empf_plzs = sorted({
            str(p).strip()[:2]
            for p in grp["empf_plz"].dropna()
            if str(p).strip()
        })

        # --- financial aggregates ------------------------------------------
        total_fracht = float(grp["fracht"].sum())     # NaN-safe (skipna=True)
        diesel_sum   = float(grp["diesel"].sum())
        maut_sum     = float(grp["maut"].sum())

        thermo_sum   = 0.0
        sonstige_nk  = 0.0
        maut_extra   = 0.0

        for raw in grp["sonstige"]:
            items = _parse_sonstige(raw)
            me, th, ot = _categorise_sonstige(items)
            maut_extra  += me
            thermo_sum  += th
            sonstige_nk += ot

        maut_total = maut_sum + maut_extra
        total_nk   = diesel_sum + maut_total + thermo_sum + sonstige_nk

        # --- bordero numbers -----------------------------------------------
        bordero_nrs = sorted({
            str(b) for b in grp["bordero_nr"].dropna()
        })

        if is_corr:
            logger.debug(
                "is_correction cluster: rechnung_nr=%s erka=%s n_send=%d",
                rnr, erka_knr, n_send,
            )

        rows.append({
            "cluster_id":             rnr,
            "erka_kundennr":          erka_knr,
            "rechnungsdatum":         rech_date,
            "leistungsdatum":         leist_date,
            "is_correction":          is_corr,
            "n_sendungen":            n_send,
            "aggregat_gewicht_kg":    agg_kg,
            "aggregat_stp":           agg_stp,
            "aggregat_ldm":           agg_ldm,
            "aggregat_volumen":       agg_vol,
            "sender_plz_distinct":    sender_plzs,
            "empfaenger_plz_distinct": empf_plzs,
            "total_fracht_eur":       total_fracht,
            "total_nebenkosten":      total_nk,
            "diesel_eur":             diesel_sum,
            "maut_eur":               maut_total,
            "thermo_eur":             thermo_sum,
            "sonstige_nk_eur":        sonstige_nk,
            "bordero_nrs":            bordero_nrs,
        })

    _COLS = [
        "cluster_id", "erka_kundennr", "rechnungsdatum", "leistungsdatum",
        "is_correction", "n_sendungen",
        "aggregat_gewicht_kg", "aggregat_stp", "aggregat_ldm", "aggregat_volumen",
        "sender_plz_distinct", "empfaenger_plz_distinct",
        "total_fracht_eur", "total_nebenkosten",
        "diesel_eur", "maut_eur", "thermo_eur", "sonstige_nk_eur",
        "bordero_nrs",
    ]
    if not rows:
        return pd.DataFrame(columns=_COLS)
    return pd.DataFrame(rows)
