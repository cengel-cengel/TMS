"""
Etappe 8: Cluster-Matching-Engine.

Verknüpft Dinas-Cluster (PRE/historisch) mit AX-Cluster (POST/aktuell)
zu Cluster-Familien und berechnet EUR/Einheit-Kennzahlen inkl. DLV-Soll-Referenz.

Join-Logik (family_key):
  (kunde_normalisiert, abs_plz_2, empf_plz_2, tarifgruppe)

Dinas-Seite: dinas_pdfs.parquet → ERKA→KNR (knr_mapping) → Calculator → tarifgruppe
AX-Seite:    Sika.xlsx + Tagesbericht → KNR → Calculator → tarifgruppe

DLV-Soll: Pro Sendung im Dinas-Cluster bzw. pro Cluster-Mitglied im AX-Cluster
wird der Calculator aufgerufen; TariffResult.basispreis wird summiert.
"""
from __future__ import annotations

import logging
import math
from datetime import date
from decimal import Decimal
from typing import Optional

import pandas as pd

from tms.clustering.ax_cluster import build_ax_clusters
from tms.clustering.basiseinheit import get_basiseinheit_name, get_basiseinheit_wert
from tms.clustering.dinas_cluster import build_dinas_clusters
from tms.dinas.knr_mapping import get_dinas_knr
from tms.tariff.base import TariffCalculator, TariffResult
from tms.tariff.calculators.sika_atm import SikaATMChCalculator, SikaATMDeCalculator
from tms.tariff.calculators.sika_de import SikaDeCalculator, SSCCalculator

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_TOP_N = 5   # max Dinas-Referenz-Cluster (nach EUR/Einheit DESC) und AX-Cluster pro Familie

# KNR → Calculator-Klasse (nur Sika-Kunden im aktuellen Scope)
_KNR_CALC_MAP: dict[str, type[TariffCalculator]] = {
    "511241":         SSCCalculator,
    "491063":         SikaDeCalculator,
    "527406":         SikaATMChCalculator,
    "ARA1802357":     SikaATMDeCalculator,
    "ARA_Sika_DE+CH": SSCCalculator,    # Kombiniertes AX-Konto → SSC-Tarif
}

# Grauzone: Dinas-SNR-Range in TB.Kundenreferenz (Migrations-Umbuchungen)
_CQ_SNR_MIN = 21_000_000
_CQ_SNR_MAX = 32_999_999

# PLZ-Toleranz-Pass: Hamming-Distanz auf 2-stellige Empfänger-PLZ
_PLZ2_LEN = 2


def _hamming1(a: str, b: str) -> bool:
    """True wenn a und b gleich lang und in genau einer Zeichenposition verschieden."""
    if len(a) != len(b) or len(a) == 0:
        return False
    return sum(x != y for x, y in zip(a, b)) == 1

# AX combined accounts → canonical KNR for family matching.
# ARA_Sika_DE+CH covers routes to CH (→ SSC 511241) and non-CH (→ Sika DE 491063).
_AX_KNR_NORMALIZE: dict[str, tuple[str, str]] = {
    "ARA_Sika_DE+CH": ("511241", "491063"),  # (if CH, if non-CH)
}


def _normalize_ax_knr(knr: str, empf_land: str, von_name: str = "") -> str:
    """Resolve combined AX accounts to the canonical Dinas KNR for family_key matching.

    For ARA_Sika_DE+CH:
      - CH destination → always SSC (511241)
      - non-CH + Von Name contains "Supply Center" → SSC (511241, export routes)
      - non-CH otherwise → Sika DE (491063)
    """
    if knr == "ARA_Sika_DE+CH":
        if str(empf_land).strip().upper() == "CH":
            return "511241"
        if "supply center" in str(von_name).strip().lower():
            return "511241"
        return "491063"
    if knr in _AX_KNR_NORMALIZE:
        ch_knr, de_knr = _AX_KNR_NORMALIZE[knr]
        return ch_knr if str(empf_land).strip().upper() == "CH" else de_knr
    return knr

# ---------------------------------------------------------------------------
# Calculator registry (lazy singletons)
# ---------------------------------------------------------------------------

_calc_instances: dict[str, TariffCalculator] = {}


def _get_calc(knr: str) -> Optional[TariffCalculator]:
    cls = _KNR_CALC_MAP.get(str(knr).strip())
    if cls is None:
        return None
    if knr not in _calc_instances:
        _calc_instances[knr] = cls()
    return _calc_instances[knr]


def _tarifgruppe_for_knr(knr: str) -> str:
    calc = _get_calc(knr)
    if calc is None:
        return "unknown"
    return getattr(calc, "_tarifgruppe", "unknown")


# ---------------------------------------------------------------------------
# DLV-Soll per Sendung (cached)
# ---------------------------------------------------------------------------

_dlv_cache: dict[tuple, Optional[TariffResult]] = {}


def _dlv_soll_sendung(
    knr: str,
    empf_plz: str,
    empf_land: str,
    tonnage_kg: Optional[float],
    stellplaetze: Optional[float],
    lademeter: Optional[float],
    leistung_date: Optional[date],
) -> Optional[TariffResult]:
    """Berechnet DLV-Soll für eine Sendung; Ergebnis ist gecacht."""
    month = (leistung_date.year, leistung_date.month) if leistung_date else (0, 0)
    key = (
        str(knr),
        str(empf_plz).strip()[:10],
        str(empf_land).strip().upper()[:2],
        int(round(tonnage_kg or 0)),
        int(round(stellplaetze or 0)),
        int(round((lademeter or 0) * 10)),
        month,
    )
    if key in _dlv_cache:
        return _dlv_cache[key]

    calc = _get_calc(knr)
    if calc is None:
        _dlv_cache[key] = None
        return None

    try:
        kwargs: dict = {
            "tonnage_kg":   tonnage_kg,
            "stellplaetze": stellplaetze,
            "lademeter":    lademeter,
        }
        # SikaDeCalculator/SSCCalculator accept shipment_date
        if hasattr(calc, "calculate") and leistung_date is not None:
            try:
                result = calc.calculate(str(empf_plz), str(empf_land),
                                        shipment_date=leistung_date, **kwargs)
            except TypeError:
                result = calc.calculate(str(empf_plz), str(empf_land), **kwargs)
        else:
            result = calc.calculate(str(empf_plz), str(empf_land), **kwargs)
        _dlv_cache[key] = result
        return result
    except Exception as exc:
        logger.debug(
            "DLV lookup failed knr=%s plz=%s land=%s: %s",
            knr, empf_plz, empf_land, exc,
        )
        _dlv_cache[key] = None
        return None


def _aggregate_dlv(results: list[Optional[TariffResult]], basiseinheit_wert: Optional[float]) -> dict:
    """Aggregiert eine Liste von TariffResults zu DLV-Soll-Spalten eines Clusters."""
    n_total = len(results)
    valid   = [r for r in results if r is not None]
    n_ok    = len(valid)

    if n_ok == 0:
        return {
            "dlv_soll_fracht_ohne_diesel": None,
            "dlv_soll_eur_pro_einheit":    None,
            "dlv_soll_calculator":         None,
            "dlv_soll_tarif_file_used":    None,
            "dlv_soll_tarif_year_used":    None,
            "dlv_soll_fallback_note":      "no_rate_found",
            "dlv_soll_coverage":           0.0,
        }

    soll_fracht = float(sum(r.basispreis for r in valid))
    first       = valid[0]
    coverage    = n_ok / n_total if n_total else 0.0

    notes: list[str] = []
    if any(r.tariff_fallback_note for r in valid):
        fallback_notes = {r.tariff_fallback_note for r in valid if r.tariff_fallback_note}
        notes.extend(sorted(fallback_notes))
    if coverage < 0.8:
        notes.append(f"dlv_partial({n_ok}/{n_total})")

    soll_per_einheit: Optional[float] = None
    if basiseinheit_wert and basiseinheit_wert > 0:
        soll_per_einheit = soll_fracht / basiseinheit_wert

    return {
        "dlv_soll_fracht_ohne_diesel": soll_fracht,
        "dlv_soll_eur_pro_einheit":    soll_per_einheit,
        "dlv_soll_calculator":         type(valid[0] and _get_calc).__name__ if False else first.tarifgruppe,
        "dlv_soll_tarif_file_used":    first.tariff_file_used,
        "dlv_soll_tarif_year_used":    first.tariff_year_used or None,
        "dlv_soll_fallback_note":      "; ".join(notes) if notes else None,
        "dlv_soll_coverage":           coverage,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _plz2(plz) -> str:
    s = str(plz).strip() if plz is not None else ""
    return s[:2] if s and s != "nan" else ""


def _safe_float(v) -> Optional[float]:
    if v is None:
        return None
    try:
        f = float(v)
        return f if math.isfinite(f) and f > 0 else None
    except (TypeError, ValueError):
        return None


def _safe_date(v) -> Optional[date]:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    try:
        return pd.Timestamp(v).date()
    except Exception:
        return None


def _apply_cq_grauzone_filter(tb_df: pd.DataFrame) -> pd.DataFrame:
    """
    Entfernt TB-Rows, bei denen Kundenreferenz eine 8-stellige Dinas-SNR
    (21000000–32999999) enthält UND Auftragsnummer 16-stellig ist.
    Diese Rows sind Migrations-Umbuchungen (physisch AX, ursprünglich Dinas-gebucht).
    """
    auftr_str = tb_df["Auftragsnummer"].astype(str).str.strip()
    is_16dig  = auftr_str.str.len() == 16

    def _is_dinas_snr(v) -> bool:
        try:
            n = int(str(v).strip())
            return _CQ_SNR_MIN <= n <= _CQ_SNR_MAX
        except (ValueError, TypeError):
            return False

    kref_is_dinas = tb_df["Kundenreferenz"].apply(_is_dinas_snr)
    grauzone_mask = is_16dig & kref_is_dinas
    n_removed = int(grauzone_mask.sum())
    if n_removed:
        logger.info("Grauzone-Filter: %d TB-Rows entfernt (Migrations-Umbuchungen)", n_removed)
    return tb_df[~grauzone_mask].copy()


# ---------------------------------------------------------------------------
# Per-cluster sendungen extraction
# ---------------------------------------------------------------------------

def _dinas_sendungen(grp: pd.DataFrame) -> list[dict]:
    """Liefert pro Dinas-Sendung (Parquet-Row) die DLV-relevanten Felder."""
    out = []
    for _, row in grp.iterrows():
        out.append({
            "empf_plz":    str(row.get("empf_plz") or "").strip(),
            "empf_land":   str(row.get("empf_land") or "").strip().upper(),
            "tonnage_kg":  _safe_float(row.get("gewicht_kg")),
            "stellplaetze": _safe_float(row.get("stp")),
            "lademeter":   _safe_float(row.get("lm")),
            "leistung_date": _safe_date(row.get("leistung_date")),
        })
    return out


def _ax_cluster_sendungen(
    cluster_id: int,
    ax_df: pd.DataFrame,
    tb_lookup: pd.DataFrame,
) -> list[dict]:
    """
    Liefert per-Mitglied DLV-Felder für einen AX-Cluster.
    Repliziert die Logik aus build_ax_clusters() für DLV-Zwecke.
    """
    # Find master: Abrechnungsstrecke == cluster_id
    master_rows = ax_df[ax_df["Abrechnungsstrecke"] == cluster_id]
    sub_rows    = ax_df[ax_df["Zusammengefasst in"] == cluster_id]
    all_members = pd.concat([master_rows, sub_rows], ignore_index=True).drop_duplicates("Auftragsnummer")

    out = []
    for _, ax_row in all_members.iterrows():
        key = str(ax_row["Auftragsnummer"]).strip()
        if key not in tb_lookup.index:
            continue
        tb_row = tb_lookup.loc[key]
        if isinstance(tb_row, pd.DataFrame):
            tb_row = tb_row.iloc[0]
        out.append({
            "empf_plz":    str(tb_row.get("Empfänger PLZ") or "").strip(),
            "empf_land":   str(tb_row.get("Empfänger Land") or "").strip().upper(),
            "tonnage_kg":  _safe_float(tb_row.get("Tonnage (eff.)")),
            "stellplaetze": _safe_float(tb_row.get("Stellplätze")),
            "lademeter":   _safe_float(tb_row.get("Lademeter")),
            "leistung_date": _safe_date(ax_row.get("Leistungsdatum")),
        })
    return out


# ---------------------------------------------------------------------------
# Output schema
# ---------------------------------------------------------------------------

_OUT_COLS = [
    "family_key",
    "cluster_source",       # "DINAS" | "AX"
    "cluster_id",
    "kunde_normalisiert",
    "erka_kundennr",        # Dinas only, None for AX
    "abs_plz_2",
    "empf_plz_2",
    "empf_land",
    "tarifgruppe",
    "leistungsdatum",
    "n_sendungen",
    "basiseinheit_name",
    "basiseinheit_wert",
    "fracht_ohne_diesel_eur",
    "eur_pro_einheit",
    # Cross-system comparison (AX rows get Dinas reference; Dinas rows: None)
    "dinas_mean_eur_pro_einheit",
    "abweichung_vs_dinas_mean",
    # DLV Soll
    "dlv_soll_fracht_ohne_diesel",
    "dlv_soll_eur_pro_einheit",
    "dlv_soll_calculator",
    "dlv_soll_tarif_file_used",
    "dlv_soll_tarif_year_used",
    "dlv_soll_fallback_note",
    "dlv_soll_coverage",
    # Per-system abweichung vs DLV
    "abweichung_dinas_vs_dlv",
    "abweichung_ax_vs_dlv",
    # Family meta
    "is_orphan_dinas",
    "is_orphan_ax",
    "selected_as",          # "dinas_sample" | "ax_underbilling" | "ax_neutral"
    "merge_reason",         # None | "plz_tolerance_1" | "plz_tolerance_ambiguous"
]


# ---------------------------------------------------------------------------
# Main function
# ---------------------------------------------------------------------------

def match_clusters(
    dinas_df: pd.DataFrame,
    ax_df: pd.DataFrame,
    tb_df: pd.DataFrame,
    *,
    excluded_knrs: frozenset[str] = frozenset({"413276"}),
    cq_filter: bool = True,
    top_n: int = _TOP_N,
) -> pd.DataFrame:
    """
    Verknüpft Dinas- und AX-Cluster zu Familien und berechnet EUR/Einheit + DLV-Soll.

    Parameters
    ----------
    dinas_df:
        Raw dinas_pdfs.parquet DataFrame.
    ax_df:
        Sika.xlsx DataFrame.
    tb_df:
        Tagesbericht DataFrame (Einzeldaten).
    excluded_knrs:
        KNRs excluded from AX side (default: {"413276"} Spiegelkonto).
    cq_filter:
        Apply Grauzone-Filter on TB (remove Migrations-Umbuchungen).
    top_n:
        Max Dinas-Referenz-Cluster pro Familie (nach EUR/Einheit DESC, gesamte Ära).

    Returns
    -------
    DataFrame with one row per (family, cluster), columns as in _OUT_COLS.
    """

    # ── 1. Grauzone filter ──────────────────────────────────────────────────
    if cq_filter:
        tb_filtered = _apply_cq_grauzone_filter(tb_df)
    else:
        tb_filtered = tb_df.copy()

    # ── 2. Build cluster DataFrames ─────────────────────────────────────────
    logger.info("Building Dinas clusters…")
    dinas_clusters = build_dinas_clusters(dinas_df)
    logger.info("Building AX clusters…")
    ax_clusters = build_ax_clusters(ax_df, tb_filtered, excluded_knrs=set(excluded_knrs))

    # ── 3. TB lookup index (for AX DLV per-member computation) ──────────────
    tb_idx = tb_filtered.copy()
    tb_idx["_auftr_key"] = tb_idx["Auftragsnummer"].astype(str).str.strip()
    tb_lookup = tb_idx.set_index("_auftr_key")

    # ── 4. Normalize Dinas ERKA → KNR ───────────────────────────────────────
    dinas_df_copy = dinas_df.copy()
    dinas_df_copy["leistung_date"] = pd.to_datetime(dinas_df_copy["leistung_date"], errors="coerce")

    # ── 5. Build Dinas cluster records ──────────────────────────────────────
    dinas_records: list[dict] = []

    for _, dc in dinas_clusters.iterrows():
        rnr       = str(dc["cluster_id"])
        erka      = str(dc["erka_kundennr"])
        ldt       = _safe_date(dc.get("leistungsdatum"))

        knr = get_dinas_knr(erka, ldt)
        if knr is None:
            logger.debug("Dinas ERKA=%s hat kein KNR-Mapping — übersprungen", erka)
            continue
        if knr in excluded_knrs:
            continue

        tarifgruppe = _tarifgruppe_for_knr(knr)
        abs_plz_2   = dc["sender_plz_distinct"][0] if dc["sender_plz_distinct"] else ""
        empf_plz_2  = dc["empfaenger_plz_distinct"][0] if dc["empfaenger_plz_distinct"] else ""

        # empf_land: derive from raw dinas_df group
        grp = dinas_df_copy[dinas_df_copy["rechnung_nr"].astype(str) == rnr]
        empf_land_vals = grp["empf_land"].dropna().unique()
        empf_land = str(empf_land_vals[0]).strip().upper() if len(empf_land_vals) else ""

        # Basiseinheit
        agg_stp = _safe_float(dc.get("aggregat_stp"))
        agg_kg  = _safe_float(dc.get("aggregat_gewicht_kg"))
        agg_ldm = _safe_float(dc.get("aggregat_ldm"))
        basis_wert = get_basiseinheit_wert(tarifgruppe, agg_kg, agg_stp, agg_ldm)
        basis_name = get_basiseinheit_name(tarifgruppe)

        # Fracht (without diesel — total_fracht_eur in dinas_cluster excludes diesel)
        fracht = _safe_float(dc.get("total_fracht_eur")) or 0.0
        eur_pe: Optional[float] = None
        if basis_wert and basis_wert > 0 and fracht > 0:
            eur_pe = fracht / basis_wert

        # DLV Soll — per sendung
        sendungen = _dinas_sendungen(grp)
        dlv_results = [
            _dlv_soll_sendung(
                knr,
                s["empf_plz"], s["empf_land"],
                s["tonnage_kg"], s["stellplaetze"], s["lademeter"],
                s["leistung_date"],
            )
            for s in sendungen
        ]
        dlv = _aggregate_dlv(dlv_results, basis_wert)

        abw_dinas_vs_dlv: Optional[float] = None
        if eur_pe is not None and dlv["dlv_soll_eur_pro_einheit"] is not None:
            abw_dinas_vs_dlv = dlv["dlv_soll_eur_pro_einheit"] - eur_pe  # positive = DLV>Dinas = underbilling

        # Groupage-Flag: stp=1 aber mehrere Sendungen
        if dc.get("n_sendungen", 0) > 1 and (agg_stp or 0) <= 1.0:
            existing = dlv.get("dlv_soll_fallback_note") or ""
            dlv["dlv_soll_fallback_note"] = "; ".join(filter(None, [existing, "groupage_single_stp"]))

        family_key = f"{knr}|{abs_plz_2}|{empf_plz_2}|{tarifgruppe}"

        dinas_records.append({
            "family_key":              family_key,
            "cluster_source":          "DINAS",
            "cluster_id":              rnr,
            "kunde_normalisiert":      knr,
            "erka_kundennr":           erka,
            "abs_plz_2":               abs_plz_2,
            "empf_plz_2":              empf_plz_2,
            "empf_land":               empf_land,
            "tarifgruppe":             tarifgruppe,
            "leistungsdatum":          ldt,
            "n_sendungen":             int(dc.get("n_sendungen", 0)),
            "basiseinheit_name":       basis_name,
            "basiseinheit_wert":       basis_wert,
            "fracht_ohne_diesel_eur":  fracht,
            "eur_pro_einheit":         eur_pe,
            "dinas_mean_eur_pro_einheit": None,
            "abweichung_vs_dinas_mean": None,
            **dlv,
            "abweichung_dinas_vs_dlv": abw_dinas_vs_dlv,
            "abweichung_ax_vs_dlv":    None,
            "is_orphan_dinas":         False,
            "is_orphan_ax":            False,
            "selected_as":             None,
            "merge_reason":            None,
        })

    # ── 6. Build AX cluster records ──────────────────────────────────────────
    ax_records: list[dict] = []

    for _, ac in ax_clusters.iterrows():
        master_knr  = str(ac["master_knr"]).strip()
        if master_knr in excluded_knrs:
            continue

        abs_plz_2  = ac["sender_plz_distinct"][0] if ac["sender_plz_distinct"] else ""
        empf_plz_2 = ac["empfaenger_plz_distinct"][0] if ac["empfaenger_plz_distinct"] else ""
        empf_land  = (
            ac["empfaenger_land_distinct"][0]
            if ac.get("empfaenger_land_distinct") and ac["empfaenger_land_distinct"]
            else ""
        )

        # Normalize combined AX accounts to canonical Dinas KNR for family matching
        von_name = str(ac.get("master_von_name") or "")
        knr = _normalize_ax_knr(master_knr, empf_land, von_name)
        tarifgruppe = _tarifgruppe_for_knr(knr)

        agg_stp = _safe_float(ac.get("aggregat_stp"))
        agg_kg  = _safe_float(ac.get("aggregat_gewicht_kg"))
        agg_ldm = _safe_float(ac.get("aggregat_ldm"))
        basis_wert = get_basiseinheit_wert(tarifgruppe, agg_kg, agg_stp, agg_ldm)
        basis_name = get_basiseinheit_name(tarifgruppe)

        fracht = _safe_float(ac.get("master_fracht_eur")) or 0.0
        eur_pe: Optional[float] = None
        if basis_wert and basis_wert > 0 and fracht > 0:
            eur_pe = fracht / basis_wert

        ldt = _safe_date(ac.get("leistungsdatum"))

        # DLV Soll — per cluster member (via TB)
        cid = int(ac["cluster_id"])
        sendungen = _ax_cluster_sendungen(cid, ax_df, tb_lookup)
        if not sendungen:
            # Fallback: single pseudo-sendung from aggregate
            sendungen = [{
                "empf_plz": empf_plz_2,
                "empf_land": empf_land,
                "tonnage_kg": agg_kg,
                "stellplaetze": agg_stp,
                "lademeter": agg_ldm,
                "leistung_date": ldt,
            }]

        dlv_results = [
            _dlv_soll_sendung(
                knr,
                s["empf_plz"], s["empf_land"],
                s["tonnage_kg"], s["stellplaetze"], s["lademeter"],
                s["leistung_date"],
            )
            for s in sendungen
        ]
        dlv = _aggregate_dlv(dlv_results, basis_wert)

        abw_ax_vs_dlv: Optional[float] = None
        if eur_pe is not None and dlv["dlv_soll_eur_pro_einheit"] is not None:
            abw_ax_vs_dlv = dlv["dlv_soll_eur_pro_einheit"] - eur_pe  # positive = DLV>AX = underbilling

        family_key = f"{knr}|{abs_plz_2}|{empf_plz_2}|{tarifgruppe}"

        ax_records.append({
            "family_key":              family_key,
            "cluster_source":          "AX",
            "cluster_id":              str(cid),
            "kunde_normalisiert":      knr,
            "erka_kundennr":           None,
            "abs_plz_2":               abs_plz_2,
            "empf_plz_2":              empf_plz_2,
            "empf_land":               empf_land,
            "tarifgruppe":             tarifgruppe,
            "leistungsdatum":          ldt,
            "n_sendungen":             int(ac.get("n_subs", 0)) + 1,
            "basiseinheit_name":       basis_name,
            "basiseinheit_wert":       basis_wert,
            "fracht_ohne_diesel_eur":  fracht,
            "eur_pro_einheit":         eur_pe,
            "dinas_mean_eur_pro_einheit": None,  # filled in step 7
            "abweichung_vs_dinas_mean": None,
            **dlv,
            "abweichung_dinas_vs_dlv": None,
            "abweichung_ax_vs_dlv":    abw_ax_vs_dlv,
            "is_orphan_dinas":         False,
            "is_orphan_ax":            False,
            "selected_as":             None,
            "merge_reason":            None,
        })

    # ── 7. Match families & compute abweichung ───────────────────────────────
    dinas_df_out = pd.DataFrame(dinas_records)
    ax_df_out    = pd.DataFrame(ax_records)

    if dinas_df_out.empty and ax_df_out.empty:
        return pd.DataFrame(columns=_OUT_COLS)

    # Compute Dinas mean eur_pro_einheit per family — gesamte Dinas-Ära, kein Zeitfenster.
    # Referenzbasis: Top-N Cluster nach eur_pro_einheit DESC (mind. 1, sonst orphan_ax).
    dinas_family_stats: dict[str, dict] = {}

    if not dinas_df_out.empty:
        for fkey, grp in dinas_df_out.groupby("family_key"):
            valid  = grp[grp["eur_pro_einheit"].notna()]
            sample = valid.nlargest(top_n, "eur_pro_einheit") if len(valid) else valid
            mean_epe = sample["eur_pro_einheit"].mean() if len(sample) else None

            dinas_family_stats[str(fkey)] = {
                "mean_eur_pro_einheit": mean_epe,
                "n_dinas":             len(grp),
            }
            selected_ids = set(sample["cluster_id"])
            dinas_df_out.loc[
                (dinas_df_out["family_key"] == fkey) &
                (dinas_df_out["cluster_id"].isin(selected_ids)),
                "selected_as",
            ] = "dinas_sample"

    # Fill Dinas mean into AX rows & compute abweichung
    if not ax_df_out.empty:
        ax_families = set(ax_df_out["family_key"].unique())
        dinas_families = set(dinas_df_out["family_key"].unique()) if not dinas_df_out.empty else set()

        for fkey in ax_families:
            stats = dinas_family_stats.get(str(fkey))
            mean_epe = stats["mean_eur_pro_einheit"] if stats else None

            mask = ax_df_out["family_key"] == fkey
            ax_df_out.loc[mask, "dinas_mean_eur_pro_einheit"] = mean_epe

            if mean_epe is not None:
                ax_eur = ax_df_out.loc[mask, "eur_pro_einheit"]
                ax_df_out.loc[mask, "abweichung_vs_dinas_mean"] = mean_epe - ax_eur  # positive = dinas>ax = underbilling
            else:
                ax_df_out.loc[mask, "is_orphan_ax"] = True

        # Mark orphan_dinas: Dinas families with no AX counterpart
        if not dinas_df_out.empty:
            for fkey in dinas_families - ax_families:
                dinas_df_out.loc[dinas_df_out["family_key"] == fkey, "is_orphan_dinas"] = True

        # Ensure numeric dtype for comparisons
        ax_df_out["abweichung_vs_dinas_mean"] = pd.to_numeric(
            ax_df_out["abweichung_vs_dinas_mean"], errors="coerce"
        )

        # Mark selected AX: top_n by abweichung DESC (most underbilled first)
        for fkey, grp in ax_df_out.groupby("family_key"):
            has_underbilling = grp["abweichung_vs_dinas_mean"].gt(0).any() if "abweichung_vs_dinas_mean" in grp else False
            if not has_underbilling:
                continue
            top_ax = (
                grp[grp["abweichung_vs_dinas_mean"].notna()]
                .nlargest(top_n, "abweichung_vs_dinas_mean")  # most positive = worst underbilling (dinas>>ax)
            )
            ax_df_out.loc[top_ax.index, "selected_as"] = "ax_underbilling"

    # ── 7.5 PLZ-Toleranz-Pass (Hamming-1 auf empf_plz_2) ───────────────────
    # Versucht, noch ungematchte Dinas/AX-Orphan-Familien zusammenzuführen,
    # wenn (kunde, abs_plz_2, tarifgruppe) übereinstimmen und die Empfänger-PLZ
    # sich in genau einem Zeichen unterscheidet.
    if not dinas_df_out.empty and not ax_df_out.empty:
        matched_ax_fkeys  = set(ax_df_out["family_key"]) & set(dinas_df_out["family_key"])
        unmatched_dinas   = set(dinas_df_out["family_key"]) - matched_ax_fkeys
        unmatched_ax      = set(ax_df_out["family_key"])   - matched_ax_fkeys

        def _parse_fkey(fkey: str) -> tuple[str, str, str, str] | None:
            parts_ = fkey.split("|")
            return tuple(parts_) if len(parts_) == 4 else None  # type: ignore[return-value]

        # Build AX lookup: (kunde, abs_plz, tg) → list[(empf_plz, fkey)]
        ax_tol_lookup: dict[tuple, list[tuple]] = {}
        for fkey in unmatched_ax:
            parsed = _parse_fkey(fkey)
            if parsed is None:
                continue
            kunde_, abs_, empf_, tg_ = parsed
            if not empf_:
                continue
            ax_tol_lookup.setdefault((kunde_, abs_, tg_), []).append((empf_, fkey))

        # fkey_remaps: old AX fkey → (new fkey = Dinas fkey, reason)
        fkey_remaps: dict[str, tuple[str, str]] = {}

        for dinas_fkey in unmatched_dinas:
            parsed = _parse_fkey(dinas_fkey)
            if parsed is None:
                continue
            kunde_, abs_, empf_, tg_ = parsed
            if not empf_:
                continue
            candidates = ax_tol_lookup.get((kunde_, abs_, tg_), [])
            h1_matches = [
                (ax_empf, ax_fkey)
                for ax_empf, ax_fkey in candidates
                if _hamming1(empf_, ax_empf)
            ]
            if len(h1_matches) == 1:
                _, ax_fkey = h1_matches[0]
                fkey_remaps[ax_fkey] = (dinas_fkey, "plz_tolerance_1")
            elif len(h1_matches) > 1:
                for _, ax_fkey in h1_matches:
                    fkey_remaps.setdefault(ax_fkey, (ax_fkey, "plz_tolerance_ambiguous"))

        if fkey_remaps:
            logger.info(
                "PLZ-Toleranz-Pass: %d AX-Familien remapped (%d eindeutig, %d ambiguous)",
                len(fkey_remaps),
                sum(1 for _, (_, r) in fkey_remaps.items() if r == "plz_tolerance_1"),
                sum(1 for _, (_, r) in fkey_remaps.items() if r == "plz_tolerance_ambiguous"),
            )
            for old_fkey, (new_fkey, reason) in fkey_remaps.items():
                mask = ax_df_out["family_key"] == old_fkey
                ax_df_out.loc[mask, "family_key"]   = new_fkey
                ax_df_out.loc[mask, "merge_reason"] = reason

                if reason == "plz_tolerance_1":
                    # Recompute abweichung using the now-matched Dinas family stats
                    stats    = dinas_family_stats.get(str(new_fkey))
                    mean_epe = stats["mean_eur_pro_einheit"] if stats else None
                    ax_df_out.loc[mask, "dinas_mean_eur_pro_einheit"] = mean_epe
                    ax_df_out.loc[mask, "is_orphan_ax"] = False
                    if mean_epe is not None:
                        ax_eur = pd.to_numeric(ax_df_out.loc[mask, "eur_pro_einheit"], errors="coerce")
                        ax_df_out.loc[mask, "abweichung_vs_dinas_mean"] = mean_epe - ax_eur
                    # Clear orphan_dinas flag on the Dinas side
                    dinas_df_out.loc[
                        dinas_df_out["family_key"] == new_fkey, "is_orphan_dinas"
                    ] = False

            # Re-enforce numeric dtype after remapping
            ax_df_out["abweichung_vs_dinas_mean"] = pd.to_numeric(
                ax_df_out["abweichung_vs_dinas_mean"], errors="coerce"
            )

    # ── 8. Assemble output ──────────────────────────────────────────────────
    parts = []
    if not dinas_df_out.empty:
        parts.append(dinas_df_out)
    if not ax_df_out.empty:
        parts.append(ax_df_out)

    if not parts:
        return pd.DataFrame(columns=_OUT_COLS)

    out = pd.concat(parts, ignore_index=True)

    # Ensure all columns present
    for col in _OUT_COLS:
        if col not in out.columns:
            out[col] = None

    return out[_OUT_COLS].reset_index(drop=True)
