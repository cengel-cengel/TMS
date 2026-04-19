"""AX-seitige Cluster-Aggregation aus Sika.xlsx + Tagesbericht.

Etappe 7a: Baut pro Cluster (Zusammengefasst-in-Gruppe) eine Zeile mit
Master-Billing-Werten aus Sika.xlsx und physikalischen Aggregaten aus dem
Tagesbericht.

Struktur-Fakten (aus sika_cluster_zusammengefasst_in_final.md):
  - MASTER  : ZGI == eigene Abrechnungsstrecke (Selbstreferenz, trägt Betrag)
  - SUB     : ZGI != eigene Abrechnungsstrecke (zeigt auf Master-Abrechnungsstrecke)
  - STANDALONE: ZGI ist NaN
Join-Key: Sika.Auftragsnummer <-> TB.Auftragsnummer (16-stelliges AX-Format)
TB-Coverage innerhalb TB-Fenster: 98.6% (9 genuine Lücken).
"""
from __future__ import annotations

import logging
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

_TB_MAX_DATE = pd.Timestamp("2026-03-31")

_TB_PHYSICAL_COLS = ["Tonnage (eff.)", "Stellplätze", "Lademeter", "Volumen",
                     "Versender PLZ", "Empfänger PLZ"]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _classify(df: pd.DataFrame) -> pd.DataFrame:
    """Add '_row_type' column: MASTER | SUB | STANDALONE."""
    df = df.copy()
    zgi = df["Zusammengefasst in"]
    own = df["Abrechnungsstrecke"]
    df["_row_type"] = "STANDALONE"
    has_zgi = zgi.notna()
    df.loc[has_zgi & (zgi == own), "_row_type"] = "MASTER"
    df.loc[has_zgi & (zgi != own), "_row_type"] = "SUB"
    return df


def _plz2(plz_val) -> str:
    """First 2 chars of a PLZ string; empty string if missing."""
    if pd.isna(plz_val):
        return ""
    return str(plz_val).strip()[:2]


def _gap_reason(sub_row: pd.Series) -> str:
    """Heuristic gap-reason for a sub row that had no TB match."""
    ldt = pd.Timestamp(sub_row.get("Leistungsdatum", pd.NaT))
    if pd.isna(ldt):
        return "unknown"
    if ldt > _TB_MAX_DATE:
        return "april_2026_beyond_tb"
    von = str(sub_row.get("Von Ort", "")).lower()
    nach = str(sub_row.get("Nach Ort", "")).lower()
    if ldt == _TB_MAX_DATE:
        return "cutoff_2026-03-31"
    if "alcobendas" in von:
        return "import_route_alcobendas_stuttgart"
    if "dublin" in nach:
        return "dublin_jan_2026"
    if "cerano" in von:
        return "import_route_alcobendas_stuttgart"
    return "unknown"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_ax_clusters(
    ax_df: pd.DataFrame,
    tb_df: pd.DataFrame,
    excluded_knrs: set[str] | None = None,
) -> pd.DataFrame:
    """Build one row per AX cluster (master + ≥1 subs) with physical aggregates.

    Parameters
    ----------
    ax_df:
        Full Sika.xlsx DataFrame (all KNRs).
    tb_df:
        Full Tagesbericht DataFrame.
    excluded_knrs:
        KNR strings to exclude before clustering. Defaults to {"413276"}
        (Spiegelkonto / shadow account, all Betrag=0).

    Returns
    -------
    DataFrame with one row per cluster (n_subs >= 1), columns as documented
    in the Etappe-7 spec.  Solo masters (n_subs == 0) are not included.
    """
    if excluded_knrs is None:
        excluded_knrs = {"413276"}

    # --- filter ----------------------------------------------------------------
    df = ax_df[~ax_df["Kontonummer"].astype(str).isin(excluded_knrs)].copy()

    # --- classify --------------------------------------------------------------
    df = _classify(df)

    standalone = df[df["_row_type"] == "STANDALONE"]
    if len(standalone):
        for _, r in standalone.iterrows():
            logger.info(
                "STANDALONE row excluded from clusters: "
                "AX=%s KNR=%s Betrag=%.2f",
                r["Auftragsnummer"], r["Kontonummer"], r.get("Betrag", 0) or 0,
            )

    masters = df[df["_row_type"] == "MASTER"].set_index("Abrechnungsstrecke")
    subs    = df[df["_row_type"] == "SUB"]

    # --- TB lookup -------------------------------------------------------------
    tb_idx = tb_df.copy()
    tb_idx["_auftr_key"] = tb_idx["Auftragsnummer"].astype(str).str.strip()
    tb_lookup = tb_idx.set_index("_auftr_key")

    # --- only clusters that actually have subs ---------------------------------
    cluster_ids = subs["Zusammengefasst in"].unique()

    rows: list[dict] = []

    for cid in cluster_ids:
        if cid not in masters.index:
            logger.warning("cluster_id=%s has no master row — skipped", cid)
            continue

        master = masters.loc[cid]
        sub_set = subs[subs["Zusammengefasst in"] == cid]

        # --- TB join for each cluster member (master + subs) ------------------
        # Physical aggregate spans ALL members: master's own shipment AND
        # all sub-shipments.  Master.Abrechnungsgewicht == sum(all TB tonnages).
        tb_matched_rows: list[pd.Series] = []   # all members, for physical aggregation
        tb_missing_subs: list[pd.Series] = []   # sub misses only, for coverage metrics
        sub_tb_hit_count: int = 0               # subs with TB match, for coverage ratio

        for is_master, ax_row in [(True, master)] + [(False, s) for _, s in sub_set.iterrows()]:
            key = str(ax_row["Auftragsnummer"])
            if key in tb_lookup.index:
                hit = tb_lookup.loc[key]
                if isinstance(hit, pd.DataFrame):
                    hit = hit.iloc[0]
                tb_matched_rows.append(hit)
                if not is_master:
                    sub_tb_hit_count += 1
            elif not is_master:
                tb_missing_subs.append(ax_row)

        # --- physical aggregates (from TB matches, all members) ---------------
        def _sum(col: str) -> float:
            return sum(float(r.get(col) or 0) for r in tb_matched_rows)

        agg_kg  = _sum("Tonnage (eff.)")
        agg_stp = _sum("Stellplätze")
        agg_ldm = _sum("Lademeter")
        agg_vol = _sum("Volumen")

        # --- PLZ 2-digit sets + Länder ----------------------------------------
        sender_plzs = sorted({
            p for r in tb_matched_rows
            if (p := _plz2(r.get("Versender PLZ")))
        })
        empf_plzs = sorted({
            p for r in tb_matched_rows
            if (p := _plz2(r.get("Empfänger PLZ")))
        })
        empf_laender = sorted({
            str(r.get("Empfänger Land") or "").strip().upper()
            for r in tb_matched_rows
            if r.get("Empfänger Land")
        })

        if len(sender_plzs) > 1:
            logger.info(
                "cluster_id=%s has %d distinct sender-PLZ prefixes: %s",
                int(cid), len(sender_plzs), sender_plzs,
            )
        if len(empf_plzs) > 1:
            logger.info(
                "cluster_id=%s has %d distinct empfaenger-PLZ prefixes: %s",
                int(cid), len(empf_plzs), empf_plzs,
            )

        # --- coverage & gap reason --------------------------------------------
        n_subs   = len(sub_set)
        coverage = sub_tb_hit_count / n_subs if n_subs else 0.0

        gap_reason: Optional[str] = None
        if tb_missing_subs:
            reasons = sorted({_gap_reason(s) for s in tb_missing_subs})
            gap_reason = "; ".join(reasons)
            missing_ax = [str(s["Auftragsnummer"]) for s in tb_missing_subs]
            logger.info(
                "tb_gap: cluster_id=%s missing_subs=%s reason=%s",
                int(cid), missing_ax, gap_reason,
            )

        # --- consistency check ------------------------------------------------
        billing_kg = float(master.get("Abrechnungsgewicht") or 0)
        ok = abs(agg_kg - billing_kg) <= 1.0

        if not ok:
            logger.warning(
                "consistency_check FAIL: cluster_id=%s "
                "master_billing_kg=%.2f aggregat_gewicht_kg=%.2f diff=%.2f",
                int(cid), billing_kg, agg_kg, agg_kg - billing_kg,
            )

        rows.append({
            "cluster_id":             int(cid),
            "master_auftragsnr":      int(master["Auftragsnummer"]),
            "master_knr":             str(master["Kontonummer"]),
            "master_billing_kg":      billing_kg,
            "master_fracht_eur":      float(master.get("Betrag") or 0),
            "n_subs":                 n_subs,
            "aggregat_gewicht_kg":    agg_kg,
            "aggregat_stp":           agg_stp,
            "aggregat_ldm":           agg_ldm,
            "aggregat_volumen":       agg_vol,
            "sender_plz_distinct":    sender_plzs,
            "empfaenger_plz_distinct": empf_plzs,
            "empfaenger_land_distinct": empf_laender,
            "leistungsdatum":         pd.Timestamp(master.get("Leistungsdatum", pd.NaT)),
            "tb_coverage_subs":       coverage,
            "tb_gap_reason":          gap_reason,
            "consistency_check":      ok,
        })

    _COLS = [
        "cluster_id", "master_auftragsnr", "master_knr",
        "master_billing_kg", "master_fracht_eur", "n_subs",
        "aggregat_gewicht_kg", "aggregat_stp", "aggregat_ldm", "aggregat_volumen",
        "sender_plz_distinct", "empfaenger_plz_distinct", "empfaenger_land_distinct",
        "leistungsdatum", "tb_coverage_subs", "tb_gap_reason", "consistency_check",
    ]
    if not rows:
        return pd.DataFrame(columns=_COLS)
    return pd.DataFrame(rows).sort_values("cluster_id").reset_index(drop=True)
