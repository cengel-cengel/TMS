"""
Etappe 8g — SSC Irland ax_coverage_gap Verifikation.

Prüft systematisch ob die 17 ax_coverage_gap-Familien auf fehlende
AX-Extraktion, echte Rechnungsstellungslücken oder eingestellte Lanes
zurückzuführen sind.
"""
from __future__ import annotations

import datetime
import sys
from pathlib import Path
from collections import Counter

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SIKA_XLSX    = Path("data/extracted/abrechnungsstrecken/Abrechnungsstrecken/Sika.xlsx")
TB_XLSX      = Path("data/bi_report/Tagesbericht.Einzeldaten.alle.VKA.5.xlsx")
DINAS_PQ     = Path("data/parsed/dinas_pdfs.parquet")
FAMILIES_PQ  = Path("output/etappe8_cluster_families.parquet")
OUT_MD       = Path("data/reports/ssc_ireland_gap_verification.md")

MIGRATION_CUTOFF = pd.Timestamp("2025-09-26")
POST_START       = pd.Timestamp("2025-09-27")
TB_END           = pd.Timestamp("2026-03-31")

SSC_KNR = "511241"

# The 17 ax_coverage_gap families (from Etappe 8f output)
GAP_FAMILIES_ALL = [
    "511241|70|17|ssc_stellplatz",
    "511241|70|19|ssc_stellplatz",
    "511241|70|20|ssc_stellplatz",
    "511241|70|IP|ssc_stellplatz",
    "511241|70|LS|ssc_stellplatz",
    "511241|70|AL|ssc_stellplatz",
    "511241|70|DU|ssc_stellplatz",
    "527406|70|28|sika_atm_ch",
    "511241|70|28|ssc_stellplatz",
    "527406|70|36|sika_atm_ch",
    "511241|70|41|ssc_stellplatz",
    "511241|70|LU|ssc_stellplatz",
    "527406|70|29|sika_atm_ch",
    "491063|72|95|sika_de_stellplatz",
    "491063|41|72|sika_de_stellplatz",
    "491063|47|70|sika_de_stellplatz",
    "491063|LU|72|sika_de_stellplatz",
]

# SSC Ireland focus families
SSC_IE_FAMILIES = [f for f in GAP_FAMILIES_ALL if f.startswith("511241|")]

# 3 sample lanes for TB cross-check
SAMPLE_LANES = ["511241|70|IP|ssc_stellplatz",
                "511241|70|LS|ssc_stellplatz",
                "511241|70|AL|ssc_stellplatz"]

# empf_plz_2 → country/city hint (for display)
PLZ_HINTS = {
    "IP": "Dublin IE (IP postcode)",
    "LS": "Dublin IE (LS postcode)",
    "AL": "Dublin IE (AL suburb)",
    "DU": "Dublin IE (DU)",
    "17": "Spanien ES-17 (Girona)",
    "19": "Spanien ES-19 (Guadalajara)",
    "20": "Spanien ES-20 (Gipuzkoa)",
    "28": "Spanien ES-28 (Madrid)",
    "41": "Spanien ES-41 (Sevilla)",
    "LU": "Luxemburg / diverse",
}


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_all():
    print("Loading Sika.xlsx …", flush=True)
    ax  = pd.read_excel(SIKA_XLSX)
    print(f"  AX rows: {len(ax):,}")

    print("Loading Tagesbericht …", flush=True)
    tb  = pd.read_excel(TB_XLSX)
    print(f"  TB rows: {len(tb):,}")

    print("Loading Dinas parquet …", flush=True)
    din = pd.read_parquet(DINAS_PQ)
    print(f"  Dinas rows: {len(din):,}")

    print("Loading families parquet …", flush=True)
    fam = pd.read_parquet(FAMILIES_PQ)
    print(f"  Family rows: {len(fam):,}")

    return ax, tb, din, fam


# ---------------------------------------------------------------------------
# Step 1: AX-Daten-Check
# ---------------------------------------------------------------------------

def analyse_ax(ax: pd.DataFrame, lines: list):
    lines += [
        "## 1. Datenquellen-Check AX",
        "",
    ]

    # 1a. SSC rows in Sika.xlsx
    ssc_rows = ax[ax["Kontonummer"].astype(str).str.strip() == SSC_KNR].copy()
    lines += [
        f"### 1a. SSC (KNR {SSC_KNR}) in Sika.xlsx",
        "",
        f"- Gesamt SSC-Rows in Sika.xlsx: **{len(ssc_rows):,}**",
    ]

    if len(ssc_rows):
        ssc_rows["_ldt"] = pd.to_datetime(ssc_rows["Leistungsdatum"], errors="coerce")
        ldt_min = ssc_rows["_ldt"].min()
        ldt_max = ssc_rows["_ldt"].max()
        betrag_sum = pd.to_numeric(ssc_rows["Betrag"], errors="coerce").sum()
        lines += [
            f"- Leistungsdatum: {ldt_min.date()} – {ldt_max.date()}",
            f"- Gesamt Betrag: {betrag_sum:,.2f} €",
        ]

        # Filter: Nach Ort contains IE or Ireland keywords
        nach_ort = ssc_rows["Nach Ort"].fillna("").astype(str).str.upper()
        ie_rows = ssc_rows[
            nach_ort.str.contains("IRELAND|DUBLIN|BELFAST|CORK|IE |IRLAND", na=False)
        ]
        lines += [
            f"- SSC-Rows mit Irland-Zielort ('Nach Ort' contains IE/Dublin/Ireland): **{len(ie_rows)}**",
        ]
        if len(ie_rows):
            ie_rows2 = ie_rows.copy()
            ie_rows2["_ldt"] = pd.to_datetime(ie_rows2["Leistungsdatum"], errors="coerce")
            lines += [
                f"  - Leistungsdatum: {ie_rows2['_ldt'].min().date()} – {ie_rows2['_ldt'].max().date()}",
                f"  - Zielorte: {sorted(ie_rows2['Nach Ort'].dropna().unique())[:10]}",
            ]

        # ZGI structure for SSC
        from tms.clustering.ax_cluster import _classify
        ssc_cl = _classify(ssc_rows)
        type_counts = ssc_cl["_row_type"].value_counts().to_dict()
        lines += [
            f"- Row-Typ Verteilung: MASTER={type_counts.get('MASTER',0)}, "
            f"SUB={type_counts.get('SUB',0)}, STANDALONE={type_counts.get('STANDALONE',0)}",
        ]

        # How many clusters (unique ZGI where ZGI == Abrechnungsstrecke = master)
        masters = ssc_cl[ssc_cl["_row_type"] == "MASTER"]
        subs    = ssc_cl[ssc_cl["_row_type"] == "SUB"]
        cluster_ids = subs["Zusammengefasst in"].nunique()
        lines += [
            f"- Cluster-Master-Rows: {len(masters)}, Sub-Rows: {len(subs)}, "
            f"unique Cluster-IDs (via SUB): {cluster_ids}",
        ]
    else:
        lines.append("⚠ **Keine SSC-Rows in Sika.xlsx gefunden.**")

    lines += [""]

    # 1b. Other AX files containing SSC KNR
    lines += [
        "### 1b. Weitere Abrechnungsstrecken-Dateien",
        "",
    ]
    ax_dir = Path("data/extracted/abrechnungsstrecken/Abrechnungsstrecken")
    other_files = [f for f in ax_dir.glob("*.xlsx") if f.name != "Sika.xlsx"]
    for fpath in sorted(other_files):
        try:
            df = pd.read_excel(fpath, nrows=5)
            knr_col = next((c for c in df.columns if "konto" in c.lower() or "knr" in c.lower()), None)
            lines.append(f"- `{fpath.name}`: Spalten={list(df.columns[:6])} — kein SSC-KNR erwartet")
        except Exception as e:
            lines.append(f"- `{fpath.name}`: Fehler beim Lesen: {e}")
    lines += [""]

    return ssc_rows


# ---------------------------------------------------------------------------
# Step 2: Dinas-Seite Detail
# ---------------------------------------------------------------------------

def analyse_dinas(din: pd.DataFrame, fam: pd.DataFrame, lines: list):
    lines += [
        "## 2. Dinas-Seite Detail",
        "",
    ]

    dinas_rows = fam[(fam["cluster_source"] == "DINAS") &
                     (fam["is_orphan_dinas"] == True)].copy()

    lines += [
        "### 2a. Letztes leistung_date und Abbruchmuster pro Gap-Familie",
        "",
        "| Familie | Letzter Dinas | Cluster | Fracht € | Rechnungs-Rhythmus |",
        "|---------|-------------|---------|---------|------------------|",
    ]

    for fkey in GAP_FAMILIES_ALL:
        rows = dinas_rows[dinas_rows["family_key"] == fkey].copy()
        if rows.empty:
            continue
        rows["_ldt"] = pd.to_datetime(rows["leistungsdatum"], errors="coerce")
        last = rows["_ldt"].max()
        n = len(rows)
        vol = rows["fracht_ohne_diesel_eur"].sum()

        # Rhythmus: median gap between consecutive cluster dates
        sorted_dates = rows["_ldt"].dropna().sort_values()
        if len(sorted_dates) >= 2:
            gaps = sorted_dates.diff().dropna().dt.days
            median_gap = int(gaps.median())
            rhythmus = f"~{median_gap}d"
        else:
            rhythmus = "–"

        empf_plz = fkey.split("|")[2]
        hint = PLZ_HINTS.get(empf_plz, "")
        lines.append(
            f"| `{fkey}` | {last.date() if pd.notna(last) else '–'} | "
            f"{n} | {vol:,.0f} | {rhythmus} |"
        )

    lines += [
        "",
        "### 2b. SSC IE-Lanes: Monatliche Fracht-Zeitreihe",
        "",
    ]

    # Show monthly breakdown for top SSC IE families
    for fkey in SSC_IE_FAMILIES[:5]:
        rows = dinas_rows[dinas_rows["family_key"] == fkey].copy()
        if rows.empty:
            continue
        rows["_ldt"] = pd.to_datetime(rows["leistungsdatum"], errors="coerce")
        rows["_ym"] = rows["_ldt"].dt.to_period("M")
        monthly = rows.groupby("_ym")["fracht_ohne_diesel_eur"].sum()
        empf = fkey.split("|")[2]
        lines.append(f"**{fkey}** (`{PLZ_HINTS.get(empf, '')}`):")
        lines.append("")
        lines.append("| Monat | Fracht € |")
        lines.append("|-------|---------|")
        for period, val in monthly.items():
            lines.append(f"| {period} | {val:,.0f} |")
        lines.append("")

    # 2c. Check if Dinas raw data has any activity after MIGRATION_CUTOFF
    din["_ldt"] = pd.to_datetime(din["leistung_date"], errors="coerce")
    ssc_din = din[din["erka_kundennr"].astype(str).isin(
        ["14466", "14464", "14465", "14468", "13890", "15550"]
    )].copy()

    ssc_ie_din = ssc_din[
        ssc_din["empf_land"].str.upper().str.strip().isin(["IE", "GB"])
    ] if "empf_land" in ssc_din.columns else pd.DataFrame()

    lines += [
        "### 2c. Dinas-Rohdaten: SSC IE/GB-Sendungen nach Zeitraum",
        "",
        f"- Gesamt SSC-Dinas-Rows (alle ERKAs): {len(ssc_din):,}",
        f"- Davon mit Land=IE/GB: {len(ssc_ie_din):,}" if len(ssc_ie_din) else "- IE/GB-Filter: 0 Rows",
    ]

    if len(ssc_ie_din):
        pre  = ssc_ie_din[ssc_ie_din["_ldt"] <= MIGRATION_CUTOFF]
        post = ssc_ie_din[ssc_ie_din["_ldt"] >  MIGRATION_CUTOFF]
        lines += [
            f"- PRE-Migration (≤ {MIGRATION_CUTOFF.date()}): {len(pre)} Rows, "
            f"bis {pre['_ldt'].max().date() if len(pre) else '–'}",
            f"- POST-Migration (> {MIGRATION_CUTOFF.date()}): {len(post)} Rows",
        ]
        if len(post):
            lines.append(f"  ⚠ POST-Migration Dinas-Rows vorhanden! Daten: {post['_ldt'].min().date()} – {post['_ldt'].max().date()}")

    lines += [""]


# ---------------------------------------------------------------------------
# Step 3: TB Cross-Check
# ---------------------------------------------------------------------------

def analyse_tb(tb: pd.DataFrame, lines: list):
    lines += [
        "## 3. Tagesbericht Cross-Check",
        "",
    ]

    tb["_ldt"] = pd.to_datetime(tb.get("Leistungsdatum", pd.Series(dtype="object")),
                                errors="coerce")
    # Post-migration window
    tb_post = tb[tb["_ldt"] > MIGRATION_CUTOFF].copy()

    lines += [
        f"- TB gesamt: {len(tb):,} Rows",
        f"- TB POST-Migration (>{MIGRATION_CUTOFF.date()}): {len(tb_post):,} Rows",
        "",
    ]

    # 3a. Look for SSC in TB via Kundenreferenz or Rechnungsnummer patterns
    # SSC AX Auftragsnummern are 16-digit
    auftr_str = tb_post["Auftragsnummer"].astype(str).str.strip()
    tb_post_16 = tb_post[auftr_str.str.len() == 16].copy()

    lines += [
        "### 3a. SSC-Sendungen im TB POST-Migration",
        "",
        f"- 16-stellige Auftragsnummern (AX-Seite): {len(tb_post_16):,} Rows",
    ]

    # Try to find SSC via Empfänger Land = IE or PLZ prefixes
    empf_land_col = next((c for c in tb_post.columns if "empf" in c.lower() and "land" in c.lower()), None)
    empf_plz_col  = next((c for c in tb_post.columns if "empf" in c.lower() and "plz" in c.lower()), None)

    if empf_land_col:
        ie_post = tb_post[tb_post[empf_land_col].astype(str).str.upper().str.strip() == "IE"]
        lines += [
            f"- TB POST mit Empfänger Land=IE: **{len(ie_post):,}** Rows",
        ]
        if len(ie_post):
            ie16 = ie_post[ie_post["Auftragsnummer"].astype(str).str.strip().str.len() == 16]
            ie8  = ie_post[ie_post["Auftragsnummer"].astype(str).str.strip().str.len() == 8]
            lines += [
                f"  - davon 16-digit (AX): {len(ie16)}",
                f"  - davon 8-digit (Dinas): {len(ie8)}",
            ]
            if len(ie16):
                lines += ["  - Zeitraum (16-digit IE): "
                          f"{ie16['_ldt'].min().date()} – {ie16['_ldt'].max().date()}"]
                # Show sample Auftragsnummern
                sample_auftr = ie16["Auftragsnummer"].astype(str).unique()[:5]
                lines.append(f"  - Sample Auftragsnummern: {list(sample_auftr)}")

    # 3b. Sample lanes: IP, LS, AL
    lines += [
        "",
        "### 3b. Stichproben-Lanes im TB (IP/LS/AL Postleitzahlen)",
        "",
    ]

    for fkey in SAMPLE_LANES:
        empf_plz2 = fkey.split("|")[2]
        lines.append(f"#### Lane `{fkey}` (empf_plz_2={empf_plz2!r})")
        lines.append("")

        if empf_plz_col:
            plz_match_post = tb_post[
                tb_post[empf_plz_col].astype(str).str.upper().str.startswith(empf_plz2)
            ]
            plz_match_all = tb[
                tb[empf_plz_col].astype(str).str.upper().str.startswith(empf_plz2)
            ]
            lines += [
                f"- TB-Rows mit Empfänger-PLZ-Präfix `{empf_plz2}` (gesamt): {len(plz_match_all)}",
                f"- Davon POST-Migration: {len(plz_match_post)}",
            ]
            if len(plz_match_post):
                m16 = plz_match_post[plz_match_post["Auftragsnummer"].astype(str).str.len() == 16]
                m8  = plz_match_post[plz_match_post["Auftragsnummer"].astype(str).str.len() == 8]
                lines += [
                    f"  - 16-digit (AX): {len(m16)}, 8-digit (Dinas): {len(m8)}",
                ]
                if len(m16):
                    # Check if any of these are in AX ax_clusters
                    lines.append(f"  - Zeitraum 16-digit: "
                                 f"{m16['_ldt'].min().date()} – {m16['_ldt'].max().date()}")
                    # Unique Auftragsnummern
                    sample = m16["Auftragsnummer"].astype(str).unique()[:3]
                    lines.append(f"  - Sample 16-digit Auftragsnr.: {list(sample)}")

                    # Check Sika.xlsx for these Auftragsnummern
                    ax_check = pd.read_excel(SIKA_XLSX)
                    ax_auftr = set(ax_check["Auftragsnummer"].astype(str).str.strip())
                    hits = [a for a in m16["Auftragsnummer"].astype(str) if a.strip() in ax_auftr]
                    lines.append(f"  - Davon in Sika.xlsx vorhanden: {len(hits)} von {len(m16)}")
                    if hits:
                        lines.append(f"    → Vorhanden in Sika.xlsx → sollte in ax_clusters sein!")
                    else:
                        lines.append(f"    → Nicht in Sika.xlsx → fehlt in AX-Extraktion")
            else:
                lines.append(f"  → Keine POST-Migration TB-Rows mit PLZ-Präfix `{empf_plz2}`")
        else:
            lines.append("  → Kein Empfänger-PLZ-Spalte in TB gefunden")
        lines.append("")

    # 3c. Check specific: post-migration TB rows with 16-digit for SSC cluster KNR
    # SSC in AX uses Kontonummer 511241, and the Tagesbericht might have those
    lines += [
        "### 3c. Gibt es 16-stellige TB-Einträge mit SSC-Kunden post-Migration?",
        "",
    ]

    # Rechnungsnummer in TB for SSC — look for AX-style patterns
    rn_col = next((c for c in tb_post.columns if "rechnungs" in c.lower()), None)
    kref_col = next((c for c in tb_post.columns if "kundenreferenz" in c.lower() or "kref" in c.lower()), None)

    if empf_land_col and rn_col:
        ie_16 = tb_post[
            (tb_post[empf_land_col].astype(str).str.upper().str.strip() == "IE") &
            (tb_post["Auftragsnummer"].astype(str).str.strip().str.len() == 16)
        ]
        if len(ie_16):
            rn_vals = ie_16[rn_col].value_counts().head(10)
            lines += [
                f"16-digit TB-Rows POST mit Land=IE: **{len(ie_16)}**",
                "",
                "Häufigste Rechnungsnummern dieser Rows:",
                "",
                "| Rechnungsnummer | Anzahl |",
                "|----------------|--------|",
            ]
            for rn, cnt in rn_vals.items():
                lines.append(f"| {rn} | {cnt} |")
        else:
            lines.append("→ Keine 16-digit POST-TB-Rows mit Land=IE gefunden.")
    lines += [""]


# ---------------------------------------------------------------------------
# Step 4: Per-Familie Klassifikation
# ---------------------------------------------------------------------------

def classify_gap_families(fam: pd.DataFrame, tb: pd.DataFrame, ssc_ax_rows: pd.DataFrame, lines: list):
    lines += [
        "## 4. Klassifikation pro Gap-Familie",
        "",
        "| Familie | Letzter Dinas | TB POST IE? | In Sika.xlsx? | Klassifikation |",
        "|---------|-------------|------------|--------------|----------------|",
    ]

    tb["_ldt"] = pd.to_datetime(tb.get("Leistungsdatum", pd.Series(dtype="object")), errors="coerce")
    tb_post = tb[tb["_ldt"] > MIGRATION_CUTOFF]
    empf_plz_col = next((c for c in tb.columns if "empf" in c.lower() and "plz" in c.lower()), None)
    empf_land_col = next((c for c in tb.columns if "empf" in c.lower() and "land" in c.lower()), None)

    # AX Auftragsnummern set
    ax_auftr_set = set(ssc_ax_rows["Auftragsnummer"].astype(str).str.strip()) if len(ssc_ax_rows) else set()

    dinas_rows = fam[(fam["cluster_source"] == "DINAS") & (fam["is_orphan_dinas"] == True)].copy()

    for fkey in GAP_FAMILIES_ALL:
        rows = dinas_rows[dinas_rows["family_key"] == fkey]
        if rows.empty:
            lines.append(f"| `{fkey}` | – | – | – | Nicht in Parquet |")
            continue

        rows2 = rows.copy()
        rows2["_ldt"] = pd.to_datetime(rows2["leistungsdatum"], errors="coerce")
        last = rows2["_ldt"].max().date() if pd.notna(rows2["_ldt"].max()) else None

        empf_plz2 = fkey.split("|")[2]

        # TB post check
        tb_post_match = 0
        if empf_plz_col:
            tb_p = tb_post[tb_post[empf_plz_col].astype(str).str.upper().str.startswith(empf_plz2)]
            tb_16 = tb_p[tb_p["Auftragsnummer"].astype(str).str.len() == 16]
            tb_post_match = len(tb_16)

        # In Sika.xlsx check (via empf_plz_2 from TB — proxy)
        in_sika = "Ja" if tb_post_match > 0 and any(
            a.strip() in ax_auftr_set for a in tb_16["Auftragsnummer"].astype(str)
        ) else "Nein" if tb_post_match > 0 else "–"

        # Classification
        if tb_post_match == 0:
            clf = "**vermutlich_eingestellt**"
        elif in_sika == "Ja":
            clf = "fehlt_in_ax_clusters"
        else:
            clf = "**echte_rechnungsstellung_fehlt**"

        tb_str = f"Ja ({tb_post_match} Rows)" if tb_post_match else "Nein"
        lines.append(
            f"| `{fkey}` | {last} | {tb_str} | {in_sika} | {clf} |"
        )

    lines += [
        "",
        "**Legende:**",
        "- `vermutlich_eingestellt`: Keine TB-Aktivität POST → Lane eingestellt",
        "- `fehlt_in_ax_clusters`: TB hat Sendungen, diese sind in Sika.xlsx → build_ax_clusters-Bug oder Filterung",
        "- `echte_rechnungsstellung_fehlt`: TB hat Sendungen, aber nicht in Sika.xlsx → fehlt in AX-Extraktion",
        "",
    ]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    ax, tb, din, fam = load_all()

    lines: list[str] = [
        "# Etappe 8g — SSC Irland ax_coverage_gap Verifikation",
        "",
        f"**Stand:** 2026-04-19  ",
        f"**Scope:** 17 ax_coverage_gap-Familien (827.784 €) aus Etappe 8f  ",
        f"**Migration-Cutoff:** {MIGRATION_CUTOFF.date()}",
        "",
        "---",
        "",
    ]

    ssc_ax_rows = analyse_ax(ax, lines)
    analyse_dinas(din, fam, lines)
    analyse_tb(tb, lines)
    classify_gap_families(fam, tb, ssc_ax_rows, lines)

    lines += [
        "## 5. Zusammenfassung und Empfehlung",
        "",
        "*(wird nach Analyse-Befunden ergänzt)*",
        "",
        "---",
        "",
        "*Bericht generiert von `scripts/ssc_ireland_gap_verification.py`.*",
    ]

    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nReport: {OUT_MD} ({len(lines)} Zeilen)")


if __name__ == "__main__":
    main()
