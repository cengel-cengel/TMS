"""
gb_invoice_reconciliation.py
============================
Groz-Beckert: Vergleich Dinas-Rechnungen (PRE) vs. AX-Rechnungen (POST).

Architektur:
  DataLoader    — BI-Extrakt laden, GB filtern, PRE/POST zuordnen, KPIs berechnen
  RelationMatcher — Sender+Empfänger normalisieren, Gewichtsbuckets bilden
  OutlierEngine — PRE-Median-Rate als Referenz, POST-Ausreißer >5% identifizieren
  ExcelWriter   — 3 Sheets: Übersicht, Ausreißer, Dinas_Nebenkosten

Annahme: Dinas (PRE) hat höhere Erlöse als AX (POST) → Unterfakturierung in AX.

Usage:
    python src/gb_invoice_reconciliation.py
"""

import math
import warnings
import numpy as np
import pandas as pd
from pathlib import Path
from openpyxl import Workbook
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter

warnings.filterwarnings("ignore")


# ── Konfiguration ──────────────────────────────────────────────────────────────

BI_EXTRACT_PATH = Path("/home/user/TMS/data/bi_report/Tagesbericht.Einzeldaten.alle.VKA.5.xlsx")
OUTPUT_PATH     = Path("/home/user/TMS/output/gb_dinas_ax_vergleich.xlsx")

# Trennzeitpunkt PRE (Dinas) / POST (AX): TMS-Go-Live
MIGRATION_DATE = pd.Timestamp("2025-09-26")

# Mindestabweichung für Ausreißer
DEVIATION_THRESHOLD_PCT = 5.0

# Gewichtsbuckets in kg für Apple-to-Apple-Vergleich (obere Grenzen)
WEIGHT_BUCKETS = [100, 300, 500, 1_000, 2_000, 5_000, 10_000, 50_000, float("inf")]
WEIGHT_LABELS  = ["0-100", "101-300", "301-500", "501-1k", "1k-2k", "2k-5k", "5k-10k", "10k-50k", ">50k"]

# Mindest-Sendungen pro Relation + Bucket für Vergleich
MIN_SHIPMENTS_PRE  = 3
MIN_SHIPMENTS_POST = 1

# Spalten, die in alle Ausgabe-Sheets übernommen werden
ERLOES_DETAIL_COLS = [
    "Erlöse Fracht", "Erlöse Diesel", "Erlöse Maut",
    "Erlöse Nebengebühr", "Erlöse EUST Zoll", "Erlöse Transportversicherung",
]
DIM_COLS = ["Tonnage (eff.)", "Lademeter", "Volumen", "Stellplätze", "Colli"]

# Farbpalette
FARBE_HEADER   = "1F3864"   # dunkelblau
FARBE_SUBHEAD  = "2E75B6"   # mittelblau
FARBE_ROW_PRE  = "D6E4F7"   # hellblau
FARBE_ROW_POST = "F7E4D6"   # hellorange
FARBE_WARN     = "FFD700"   # gelb (Ausreißer-Markierung)
FARBE_VERLUST  = "FF6B6B"   # rot (erwarteter Verlust)


# ═══════════════════════════════════════════════════════════════════════════════
# A  DATA LOADER
# ═══════════════════════════════════════════════════════════════════════════════

def load_groz_beckert_bi(path: Path) -> pd.DataFrame:
    """
    Liest den vollständigen BI-Extrakt, filtert Groz-Beckert-Zeilen,
    weist PRE/POST zu und berechnet alle KPI-Spalten.
    """
    print(f"[DataLoader] Lese BI-Extrakt: {path.name} …")
    df = pd.read_excel(path, dtype={"Rechnungsnummer": str, "Auftragsnummer": str})
    print(f"  Gesamt: {len(df):,} Zeilen")

    # ── Groz-Beckert filtern ───────────────────────────────────────────────────
    mask = df["Kunden Name"].astype(str).str.contains(r"Groz|Beckert", case=False, na=False)
    df = df[mask].copy()
    print(f"  Groz-Beckert: {len(df):,} Zeilen ({df['Kunden Nr BK'].nunique()} Kunden-IDs)")

    # ── PRE / POST zuweisen ────────────────────────────────────────────────────
    df["periode"] = np.where(
        pd.to_datetime(df["Leistungsdatum"]) < MIGRATION_DATE,
        "PRE", "POST"
    )
    print(f"  PRE={( df['periode']=='PRE').sum()}, POST={(df['periode']=='POST').sum()}")

    # ── PLZ / Land normalisieren ───────────────────────────────────────────────
    for col in ["Versender PLZ", "Versender Land", "Empfänger PLZ", "Empfänger Land",
                "Empfänger Stadt", "Versender Name", "Empfänger Name"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    # ── Billing-Gewicht (100-kg-Schritte, aufgerundet) ────────────────────────
    tonnage = df["Tonnage (eff.)"].fillna(0).clip(lower=0)
    df["billing_weight_kg"]     = tonnage.apply(lambda t: math.ceil(t / 100) * 100 if t > 0 else 0)
    df["billing_100kg_units"]   = df["billing_weight_kg"] / 100  # Anzahl 100-kg-Einheiten

    # ── KPI: Erlöse je 100 kg ──────────────────────────────────────────────────
    df["erloes_je_100kg"] = np.where(
        df["billing_100kg_units"] > 0,
        df["Erloese"] / df["billing_100kg_units"],
        np.nan
    )

    # ── KPI: Erlöse je Sendung = Erloese (jede BI-Zeile = 1 Sendung) ──────────
    df["erloes_je_sendung"] = df["Erloese"]

    # ── KPI: Gewichtsbucket ────────────────────────────────────────────────────
    df["gewicht_bucket"] = pd.cut(
        tonnage,
        bins=[0] + WEIGHT_BUCKETS,
        labels=WEIGHT_LABELS,
        right=True
    ).astype(str)

    # ── Relation-Key: Versender-PLZ + Land ↔ Empfänger-PLZ-Prefix + Land ──────
    def plz_prefix(plz: str, land: str) -> str:
        """2-stelliger PLZ-Prefix für DE/AT/CH/IT/FR/BE; sonst erste 3 Zeichen."""
        plz_clean = plz.replace(" ", "").replace("-", "")
        if land in {"DE", "AT", "IT", "FR"}:
            return plz_clean[:2]
        return plz_clean[:3]

    df["sender_key"]   = df["Versender PLZ"] + "|" + df["Versender Land"]
    df["receiver_key"] = (
        df.apply(lambda r: plz_prefix(r["Empfänger PLZ"], r["Empfänger Land"]), axis=1)
        + "|" + df["Empfänger Land"]
    )
    df["relation_key"] = df["sender_key"] + " → " + df["receiver_key"]

    # ── Fehlende Erlöse-Spalten auffüllen ──────────────────────────────────────
    for col in ERLOES_DETAIL_COLS:
        if col not in df.columns:
            df[col] = 0.0
        else:
            df[col] = df[col].fillna(0.0)

    return df


# ═══════════════════════════════════════════════════════════════════════════════
# B  OUTLIER ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

def compute_relation_stats(df: pd.DataFrame) -> pd.DataFrame:
    """
    Berechnet PRE- und POST-Statistiken pro (relation_key, gewicht_bucket).
    Gibt Zeilen mit |Abweichung| > DEVIATION_THRESHOLD_PCT zurück.
    """
    agg_fns = {
        "Erloese":         ["count", "sum", "mean", "median"],
        "erloes_je_100kg": ["mean", "median"],
        "Tonnage (eff.)":  ["mean", "median"],
    }

    stats_list = []
    for (rel, bucket), grp in df.groupby(["relation_key", "gewicht_bucket"], observed=True):
        pre  = grp[grp["periode"] == "PRE"]
        post = grp[grp["periode"] == "POST"]

        if len(pre) < MIN_SHIPMENTS_PRE or len(post) < MIN_SHIPMENTS_POST:
            continue

        # Medianrate PRE als Referenz (robuster als Mittelwert bei kleiner Stichprobe)
        pre_rate  = pre["erloes_je_100kg"].median()
        post_rate = post["erloes_je_100kg"].median()

        if pd.isna(pre_rate) or pd.isna(post_rate) or pre_rate == 0:
            continue

        abw_pct = (post_rate - pre_rate) / abs(pre_rate) * 100

        # Nur Ausreißer über Schwelle
        if abs(abw_pct) <= DEVIATION_THRESHOLD_PCT:
            continue

        # Erwarteter Verlust (Annahme: Dinas korrekt, AX zu niedrig)
        verlust_post = (pre_rate - post_rate) * post["billing_100kg_units"].sum()

        stats_list.append({
            "relation_key":       rel,
            "gewicht_bucket":     bucket,
            "sender_key":         pre["sender_key"].iloc[0],
            "receiver_key":       pre["receiver_key"].iloc[0],
            "land_von":           pre["Versender Land"].iloc[0],
            "land_nach":          pre["Empfänger Land"].iloc[0],
            "empf_land_sample":   post["Empfänger Land"].iloc[0],
            "empf_plz_sample":    post["Empfänger PLZ"].iloc[0],
            "empf_stadt_sample":  post.get("Empfänger Stadt", pd.Series([""])).iloc[0],
            # PRE
            "n_pre":              len(pre),
            "sum_erloes_pre":     pre["Erloese"].sum(),
            "avg_erloes_pre":     pre["Erloese"].mean(),
            "median_rate_pre":    pre_rate,
            "avg_gewicht_pre_kg": pre["Tonnage (eff.)"].mean(),
            # POST
            "n_post":             len(post),
            "sum_erloes_post":    post["Erloese"].sum(),
            "avg_erloes_post":    post["Erloese"].mean(),
            "median_rate_post":   post_rate,
            "avg_gewicht_post_kg":post["Tonnage (eff.)"].mean(),
            # Delta
            "abweichung_pct":     abw_pct,
            "erwarteter_verlust_eur": verlust_post,
            "unterfakturierung":  abw_pct < 0,  # True = POST < PRE
        })

    if not stats_list:
        return pd.DataFrame()

    result = pd.DataFrame(stats_list)
    # Positiver Verlust = Unterfakturierung (AX < Dinas) → absteigende Sortierung
    result = result.sort_values("erwarteter_verlust_eur", ascending=False)
    return result


def find_post_outliers(df: pd.DataFrame, relation_stats: pd.DataFrame) -> pd.DataFrame:
    """
    Sucht für jede auffällige Relation+Bucket die einzelnen POST-Sendungen,
    die vom PRE-Median um mehr als DEVIATION_THRESHOLD_PCT abweichen.
    """
    outlier_rows = []

    for _, stat in relation_stats.iterrows():
        rel    = stat["relation_key"]
        bucket = stat["gewicht_bucket"]
        pre_rate = stat["median_rate_pre"]

        # POST-Sendungen dieser Relation + Bucket
        post_sub = df[
            (df["relation_key"]   == rel) &
            (df["gewicht_bucket"] == bucket) &
            (df["periode"]        == "POST")
        ].copy()

        post_sub["ppu_pre_referenz"]  = pre_rate
        post_sub["abweichung_pct"]    = (
            (post_sub["erloes_je_100kg"] - pre_rate) / abs(pre_rate) * 100
        )
        post_sub["erwarteter_verlust_eur"] = (
            (pre_rate - post_sub["erloes_je_100kg"]) * post_sub["billing_100kg_units"]
        )
        post_sub["_abw_abs"] = post_sub["abweichung_pct"].abs()

        # Nur echte Ausreißer (>Schwelle)
        outs = post_sub[post_sub["_abw_abs"] > DEVIATION_THRESHOLD_PCT].copy()
        outs.drop(columns=["_abw_abs"], inplace=True)
        outlier_rows.append(outs)

    if not outlier_rows:
        return pd.DataFrame()

    all_outliers = pd.concat(outlier_rows, ignore_index=True)
    # Positive Verluste zuerst = größte Unterfakturierung oben
    return all_outliers.sort_values("erwarteter_verlust_eur", ascending=False)


def get_dinas_nebenkosten(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregiert die Dinas-Nebenkosten (PRE) nach Relation,
    aufgeschlüsselt nach Erlöse-Positionen.
    """
    pre = df[df["periode"] == "PRE"].copy()
    nk_cols = [c for c in ERLOES_DETAIL_COLS if c in pre.columns]

    agg = (
        pre.groupby(["relation_key", "Empfänger Land"])[nk_cols + ["Erloese"]]
        .agg(["count", "sum", "mean"])
    )
    agg.columns = ["_".join(c) for c in agg.columns]
    agg = agg.reset_index()
    agg.rename(columns={"Erloese_count": "n_sendungen"}, inplace=True)

    return agg.sort_values("Erloese_sum", ascending=False)


# ═══════════════════════════════════════════════════════════════════════════════
# C  EXCEL WRITER
# ═══════════════════════════════════════════════════════════════════════════════

def _header_style(cell, bg_hex: str, bold: bool = True, font_color: str = "FFFFFF"):
    cell.fill      = PatternFill("solid", fgColor=bg_hex)
    cell.font      = Font(bold=bold, color=font_color, name="Calibri", size=10)
    cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)


def _data_style(cell, bg_hex: str = None):
    if bg_hex:
        cell.fill = PatternFill("solid", fgColor=bg_hex)
    cell.font      = Font(name="Calibri", size=9)
    cell.alignment = Alignment(horizontal="right" if isinstance(cell.value, (int, float)) else "left")


def _thin_border() -> Border:
    s = Side(border_style="thin", color="CCCCCC")
    return Border(left=s, right=s, top=s, bottom=s)


def _autofit_columns(ws, min_width: int = 10, max_width: int = 45):
    for col_cells in ws.columns:
        max_len = max((len(str(c.value or "")) for c in col_cells), default=0)
        ws.column_dimensions[get_column_letter(col_cells[0].column)].width = max(
            min_width, min(max_len + 2, max_width)
        )


def write_uebersicht_sheet(ws, relation_stats: pd.DataFrame):
    """Sheet 1: Relationen mit Abweichung ≥5%, sortiert nach erwartetem Verlust."""
    ws.title = "Übersicht"

    header = [
        "Relation", "Gewichtsbucket", "Land Von", "Land Nach",
        "Empfänger PLZ", "Empfänger Ort",
        "n PRE (Dinas)", "Σ Erlöse PRE €", "Ø Erlöse PRE €", "Median €/100kg PRE",
        "n POST (AX)",   "Σ Erlöse POST €","Ø Erlöse POST €", "Median €/100kg POST",
        "Abweichung %",  "Erwarteter Verlust €", "Unterfakturierung",
        "Ø Gewicht PRE kg", "Ø Gewicht POST kg",
    ]
    for ci, h in enumerate(header, 1):
        cell = ws.cell(1, ci, h)
        _header_style(cell, FARBE_HEADER)

    ws.row_dimensions[1].height = 32
    ws.freeze_panes = "A2"

    for ri, (_, row) in enumerate(relation_stats.iterrows(), 2):
        vals = [
            row["relation_key"], row["gewicht_bucket"],
            row["land_von"], row["land_nach"],
            row["empf_plz_sample"], row.get("empf_stadt_sample", ""),
            int(row["n_pre"]), round(row["sum_erloes_pre"], 2),
            round(row["avg_erloes_pre"], 2), round(row["median_rate_pre"], 4),
            int(row["n_post"]), round(row["sum_erloes_post"], 2),
            round(row["avg_erloes_post"], 2), round(row["median_rate_post"], 4),
            round(row["abweichung_pct"], 2),
            round(row["erwarteter_verlust_eur"], 2),
            "JA" if row["unterfakturierung"] else "NEIN",
            round(row["avg_gewicht_pre_kg"], 1) if not pd.isna(row["avg_gewicht_pre_kg"]) else "",
            round(row["avg_gewicht_post_kg"], 1) if not pd.isna(row["avg_gewicht_post_kg"]) else "",
        ]
        bg = FARBE_ROW_POST if row["unterfakturierung"] else FARBE_ROW_PRE
        for ci, v in enumerate(vals, 1):
            cell = ws.cell(ri, ci, v)
            _data_style(cell, bg)
            cell.border = _thin_border()
            # Abweichung % farblich
            if ci == 15 and isinstance(v, float):
                cell.fill = PatternFill("solid", fgColor=FARBE_WARN if v < 0 else "C6EFCE")
            # Positiver Verlust = Unterfakturierung (AX < Dinas) → Rot
            if ci == 16 and isinstance(v, float) and v > 0:
                cell.fill = PatternFill("solid", fgColor=FARBE_VERLUST)
            elif ci == 16 and isinstance(v, float) and v < 0:
                cell.fill = PatternFill("solid", fgColor="C6EFCE")  # grün = AX billiger

    _autofit_columns(ws)


def write_ausreisser_sheet(ws, outliers: pd.DataFrame, relation_stats: pd.DataFrame):
    """Sheet 2: Sendungsebene — Auftragsnummer, Sender, Empfänger, alle KPIs."""
    ws.title = "Ausreißer"

    base_cols = [
        "Auftragsnummer", "Rechnungsnummer", "Ausgangsbordero", "Leistungsdatum",
        "Kunden Name",
        "Versender Name", "Versender PLZ", "Versender Land",
        "Empfänger Name", "Empfänger PLZ", "Empfänger Stadt", "Empfänger Land",
        "Relation Ausgang", "relation_key", "gewicht_bucket",
    ]
    kpi_cols = [
        "Tonnage (eff.)", "billing_weight_kg", "Lademeter", "Volumen", "Stellplätze", "Colli",
        "erloes_je_100kg", "erloes_je_sendung", "ppu_pre_referenz",
        "abweichung_pct", "erwarteter_verlust_eur",
        "Erloese",
    ]
    erloes_detail = [c for c in ERLOES_DETAIL_COLS if c in outliers.columns]
    all_cols = [c for c in base_cols + kpi_cols + erloes_detail if c in outliers.columns]

    # Spalten-Header
    header_labels = {
        "erloes_je_100kg":          "Erlöse/100kg POST €",
        "erloes_je_sendung":        "Erlöse/Sendung POST €",
        "ppu_pre_referenz":         "Ref. €/100kg Dinas",
        "abweichung_pct":           "Abw. %",
        "erwarteter_verlust_eur":   "Erw. Verlust €",
        "billing_weight_kg":        "Abrech.-Gew. kg",
    }
    header = [header_labels.get(c, c) for c in all_cols]

    for ci, h in enumerate(header, 1):
        cell = ws.cell(1, ci, h)
        _header_style(cell, FARBE_SUBHEAD)

    ws.row_dimensions[1].height = 28
    ws.freeze_panes = "A2"

    # Relationen für Farbwechsel
    rel_colors = {}
    for i, rel in enumerate(outliers["relation_key"].unique()):
        rel_colors[rel] = "EAF0FB" if i % 2 == 0 else "FFFFFF"

    for ri, (_, row) in enumerate(outliers.iterrows(), 2):
        bg = rel_colors.get(row.get("relation_key", ""), "FFFFFF")
        for ci, col in enumerate(all_cols, 1):
            val = row.get(col, "")
            if pd.isna(val):
                val = ""
            elif isinstance(val, float):
                val = round(val, 4)
            cell = ws.cell(ri, ci, val)
            _data_style(cell, bg)
            cell.border = _thin_border()
            # Ausreißer-Markierung
            if col == "abweichung_pct" and isinstance(val, float):
                cell.fill = PatternFill("solid", fgColor=FARBE_WARN if val < 0 else "C6EFCE")
            if col == "erwarteter_verlust_eur" and isinstance(val, float) and val > 0:
                cell.fill = PatternFill("solid", fgColor=FARBE_VERLUST)
            elif col == "erwarteter_verlust_eur" and isinstance(val, float) and val < 0:
                cell.fill = PatternFill("solid", fgColor="C6EFCE")

    _autofit_columns(ws)


def write_dinas_nebenkosten_sheet(ws, nebenkosten: pd.DataFrame):
    """Sheet 3: Dinas-Nebenkosten aggregiert nach Relation."""
    ws.title = "Dinas_Nebenkosten"

    header = list(nebenkosten.columns)
    for ci, h in enumerate(header, 1):
        cell = ws.cell(1, ci, h)
        _header_style(cell, FARBE_HEADER)

    ws.row_dimensions[1].height = 28
    ws.freeze_panes = "A2"

    for ri, (_, row) in enumerate(nebenkosten.iterrows(), 2):
        bg = "F0F8FF" if ri % 2 == 0 else "FFFFFF"
        for ci, h in enumerate(header, 1):
            val = row.get(h, "")
            if pd.isna(val):
                val = ""
            elif isinstance(val, float):
                val = round(val, 2)
            cell = ws.cell(ri, ci, val)
            _data_style(cell, bg)
            cell.border = _thin_border()

    _autofit_columns(ws)


def write_summary_sheet(ws, df: pd.DataFrame, relation_stats: pd.DataFrame):
    """Sheet 0: Management-Übersicht mit Gesamtkennzahlen."""
    ws.title = "Zusammenfassung"

    pre  = df[df["periode"] == "PRE"]
    post = df[df["periode"] == "POST"]

    rows = [
        ("", ""),
        ("GROZ-BECKERT – Dinas vs. AX Rechnungsvergleich", ""),
        ("Auswertungsdatum", pd.Timestamp.today().strftime("%d.%m.%Y")),
        ("", ""),
        ("── PRE (Dinas) ──", ""),
        ("Sendungen", len(pre)),
        ("Zeitraum von", str(pre["Leistungsdatum"].min())[:10] if len(pre) else ""),
        ("Zeitraum bis", str(pre["Leistungsdatum"].max())[:10] if len(pre) else ""),
        ("Σ Erlöse €", round(pre["Erloese"].sum(), 2)),
        ("Ø Erlöse/Sendung €", round(pre["Erloese"].mean(), 2)),
        ("Ø €/100kg", round(pre["erloes_je_100kg"].median(), 4)),
        ("Ø Gewicht kg", round(pre["Tonnage (eff.)"].mean(), 1)),
        ("", ""),
        ("── POST (AX) ──", ""),
        ("Sendungen", len(post)),
        ("Zeitraum von", str(post["Leistungsdatum"].min())[:10] if len(post) else ""),
        ("Zeitraum bis", str(post["Leistungsdatum"].max())[:10] if len(post) else ""),
        ("Σ Erlöse €", round(post["Erloese"].sum(), 2)),
        ("Ø Erlöse/Sendung €", round(post["Erloese"].mean(), 2)),
        ("Ø €/100kg", round(post["erloes_je_100kg"].median(), 4)),
        ("Ø Gewicht kg", round(post["Tonnage (eff.)"].mean(), 1)),
        ("", ""),
        ("── Ausreißer-Analyse (>5% Abw.) ──", ""),
        ("Auffällige Relationen+Buckets", len(relation_stats)),
        ("Davon Unterfakturierung (POST<PRE)", int(relation_stats["unterfakturierung"].sum()) if len(relation_stats) else 0),
        ("Erwarteter Gesamtverlust €", round(relation_stats[relation_stats["unterfakturierung"]]["erwarteter_verlust_eur"].sum(), 2) if len(relation_stats) else 0),
    ]

    for ri, (label, value) in enumerate(rows, 1):
        c_label = ws.cell(ri, 1, label)
        c_value = ws.cell(ri, 2, value)
        if label.startswith("──") or label in ("", ) and ri <= 2:
            c_label.font = Font(bold=True, name="Calibri", size=11, color="1F3864")
        elif label == "GROZ-BECKERT – Dinas vs. AX Rechnungsvergleich":
            c_label.font = Font(bold=True, name="Calibri", size=14, color="1F3864")
            ws.merge_cells(f"A{ri}:B{ri}")
        else:
            c_label.font = Font(name="Calibri", size=10)
            c_value.font = Font(name="Calibri", size=10, bold=True)

    ws.column_dimensions["A"].width = 35
    ws.column_dimensions["B"].width = 20


# ═══════════════════════════════════════════════════════════════════════════════
# D  MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    print("=" * 65)
    print("Groz-Beckert | Dinas vs. AX Rechnungsvergleich")
    print("=" * 65)

    # 1. Daten laden & KPIs berechnen
    df = load_groz_beckert_bi(BI_EXTRACT_PATH)

    # 2. Relationen-Statistiken + Ausreißer ermitteln
    print("\n[OutlierEngine] Berechne Relationen-Statistiken …")
    relation_stats = compute_relation_stats(df)
    print(f"  Auffällige Relationen+Buckets: {len(relation_stats)}")

    if len(relation_stats) > 0:
        print(f"  Davon Unterfakturierung:        {relation_stats['unterfakturierung'].sum()}")
        verlust = relation_stats[relation_stats["unterfakturierung"]]["erwarteter_verlust_eur"].sum()
        print(f"  Erwarteter Gesamtverlust:       {verlust:,.2f} €")

    # 3. POST-Ausreißer auf Sendungsebene
    print("\n[OutlierEngine] Suche POST-Ausreißer auf Sendungsebene …")
    outliers = find_post_outliers(df, relation_stats) if len(relation_stats) > 0 else pd.DataFrame()
    print(f"  POST-Ausreißer-Sendungen: {len(outliers)}")

    # 4. Dinas-Nebenkosten
    print("\n[DataLoader] Aggregiere Dinas-Nebenkosten …")
    nebenkosten = get_dinas_nebenkosten(df)

    # 5. Excel schreiben
    print(f"\n[ExcelWriter] Schreibe {OUTPUT_PATH.name} …")
    wb = Workbook()
    # Sheets in Reihenfolge
    ws0 = wb.active
    write_summary_sheet(ws0, df, relation_stats)

    ws1 = wb.create_sheet()
    write_uebersicht_sheet(ws1, relation_stats)

    ws2 = wb.create_sheet()
    write_ausreisser_sheet(ws2, outliers, relation_stats)

    ws3 = wb.create_sheet()
    write_dinas_nebenkosten_sheet(ws3, nebenkosten)

    wb.save(OUTPUT_PATH)
    print(f"  Gespeichert: {OUTPUT_PATH}")

    # ── Konsolen-Summary ───────────────────────────────────────────────────────
    print("\n" + "─" * 65)
    print("Top-10 auffällige Relationen (sortiert nach erwartetem Verlust):")
    print("─" * 65)
    if len(relation_stats) > 0:
        cols_show = ["relation_key", "gewicht_bucket", "n_pre", "n_post",
                     "median_rate_pre", "median_rate_post", "abweichung_pct",
                     "erwarteter_verlust_eur"]
        print(relation_stats[cols_show].head(10).to_string(index=False))
    else:
        print("  Keine Ausreißer gefunden.")
    print("\nFertig.")


if __name__ == "__main__":
    main()
