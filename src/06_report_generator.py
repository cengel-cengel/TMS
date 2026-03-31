"""
06_report_generator.py
=======================
Generates comprehensive Excel audit report with charts.

Output sheets per customer:
  1. Zusammenfassung   — KPIs, Gesamtdelta, Fehlerklassen
  2. Sendungsdetail    — Every shipment with Soll/Ist/Delta
  3. Monatsvergleich   — Ø Preis/Sendung per month with 26.09 marker
  4. Routen-Analyse    — Comparable route breakdown
  5. Fehlerklassen     — Error type distribution
  6. Top20-Übersicht   — All Top-20 customers ranked

Usage:
    python src/06_report_generator.py --output output/
"""

import pandas as pd
import numpy as np
import argparse
from pathlib import Path
from datetime import datetime
import warnings
warnings.filterwarnings("ignore")

try:
    import openpyxl
    from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    from openpyxl.chart import BarChart, LineChart, Reference
    from openpyxl.chart.series import SeriesLabel
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False

try:
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

MIGRATION_DATE = pd.Timestamp("2025-09-26")

# ─── Color scheme ─────────────────────────────────────────────────────────────
CLR_HEADER    = "1F3864"  # dark blue
CLR_PRE       = "D9EAD3"  # light green (pre-migration)
CLR_POST      = "FCE5CD"  # light orange (post-migration)
CLR_OK        = "D9EAD3"
CLR_WARN      = "FFF2CC"
CLR_ERROR     = "F4CCCC"
CLR_ACCENT    = "4472C4"  # blue


def auto_fit_columns(ws):
    """Auto-fit column widths in a worksheet."""
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            try:
                max_len = max(max_len, len(str(cell.value or "")))
            except Exception:
                pass
        ws.column_dimensions[col_letter].width = min(max_len + 3, 50)


def style_header_row(ws, row_num: int = 1, color: str = CLR_HEADER):
    """Apply header styling to a row."""
    fill = PatternFill(start_color=color, end_color=color, fill_type="solid")
    font = Font(bold=True, color="FFFFFF" if color == CLR_HEADER else "000000")
    for cell in ws[row_num]:
        cell.fill = fill
        cell.font = font
        cell.alignment = Alignment(horizontal="center", vertical="center")


def write_kpi_sheet(wb, kunde: str, df_recon: pd.DataFrame, bruch_data: dict,
                     schaden_data: dict):
    """Write summary KPI sheet."""
    ws = wb.create_sheet("Zusammenfassung")

    # Title
    ws["A1"] = f"TMS-MIGRATIONSAUDIT — {kunde.upper()}"
    ws["A1"].font = Font(bold=True, size=16, color=CLR_ACCENT)
    ws["A2"] = f"Erstellt: {datetime.now().strftime('%d.%m.%Y %H:%M')} | Migrationsdatum: 26.09.2025"
    ws["A2"].font = Font(italic=True, color="666666")

    row = 4
    ws.cell(row=row, column=1, value="KENNZAHL")
    ws.cell(row=row, column=2, value="PRE-MIGRATION")
    ws.cell(row=row, column=3, value="POST-MIGRATION")
    ws.cell(row=row, column=4, value="DELTA")
    ws.cell(row=row, column=5, value="BEWERTUNG")
    style_header_row(ws, row)
    row += 1

    kpis = []
    if not df_recon.empty and "migration_periode" in df_recon.columns:
        pre = df_recon[df_recon["migration_periode"] == "pre"]
        post = df_recon[df_recon["migration_periode"] == "post"]

        for label, pre_val, post_val, fmt in [
            ("Anzahl Sendungen", len(pre), len(post), "{:,.0f}"),
            ("Ø Preis/Sendung (€)", pre["frachtkosten_netto"].mean() if "frachtkosten_netto" in pre.columns else 0,
                                     post["frachtkosten_netto"].mean() if "frachtkosten_netto" in post.columns else 0,
                                     "{:,.2f} €"),
            ("Ø Preis/kg (€/kg)", pre["preis_je_kg"].mean() if "preis_je_kg" in pre.columns else 0,
                                   post["preis_je_kg"].mean() if "preis_je_kg" in post.columns else 0,
                                   "{:.4f} €/kg"),
            ("Ø Preis/LDM (€/LDM)", pre["preis_je_ldm"].mean() if "preis_je_ldm" in pre.columns else 0,
                                      post["preis_je_ldm"].mean() if "preis_je_ldm" in post.columns else 0,
                                      "{:.2f} €/LDM"),
            ("Gesamtumsatz netto (€)", pre["frachtkosten_netto"].sum() if "frachtkosten_netto" in pre.columns else 0,
                                        post["frachtkosten_netto"].sum() if "frachtkosten_netto" in post.columns else 0,
                                        "{:,.2f} €"),
        ]:
            delta = post_val - pre_val if (pre_val and post_val) else None
            delta_pct = (delta / pre_val * 100) if (pre_val and pre_val != 0 and delta is not None) else None
            kpis.append((label, pre_val, post_val, delta, delta_pct, fmt))

    for label, pre_val, post_val, delta, delta_pct, fmt in kpis:
        ws.cell(row=row, column=1, value=label)
        ws.cell(row=row, column=2, value=fmt.format(pre_val) if pre_val else "—")
        ws.cell(row=row, column=3, value=fmt.format(post_val) if post_val else "—")
        if delta is not None:
            ws.cell(row=row, column=4, value=f"{delta:+,.2f} ({delta_pct:+.1f}%)")
            # Color coding
            fill_color = CLR_ERROR if abs(delta_pct) > 10 else CLR_WARN if abs(delta_pct) > 2 else CLR_OK
            for col in range(1, 6):
                ws.cell(row=row, column=col).fill = PatternFill(
                    start_color=fill_color, end_color=fill_color, fill_type="solid")
        row += 1

    # Damage estimate
    row += 1
    ws.cell(row=row, column=1, value="SCHADENSSCHÄTZUNG")
    ws.cell(row=row, column=1).font = Font(bold=True, size=12)
    row += 1
    schaden = schaden_data.get("schaden_gesamt_eur", 0)
    ws.cell(row=row, column=1, value="Geschätzter Gesamtschaden seit 26.09.2025:")
    ws.cell(row=row, column=2, value=f"{schaden:+,.2f} €")
    ws.cell(row=row, column=3, value=schaden_data.get("richtung", ""))
    if abs(schaden) > 0:
        color = CLR_ERROR if schaden > 0 else CLR_WARN
        ws.cell(row=row, column=2).fill = PatternFill(start_color=color, end_color=color, fill_type="solid")
        ws.cell(row=row, column=2).font = Font(bold=True)

    auto_fit_columns(ws)


def write_detail_sheet(wb, df_recon: pd.DataFrame):
    """Write per-shipment detail sheet."""
    if df_recon.empty:
        return

    cols = [c for c in [
        "auftragsnummer", "ladedatum", "migration_periode",
        "kundenname", "absender_plz", "empfaenger_plz", "route_group",
        "gewicht_kg", "lademeter", "stellplaetze", "packstücke",
        "frachtkosten_netto", "ist_netto", "soll_netto",
        "delta_eur", "delta_pct", "fehler_typ", "fehler_beschreibung"
    ] if c in df_recon.columns]

    df_out = df_recon[cols].copy()
    ws = wb.create_sheet("Sendungsdetail")

    # Headers
    for j, col in enumerate(cols, 1):
        ws.cell(row=1, column=j, value=col.upper().replace("_", " "))
    style_header_row(ws, 1)

    # Data rows with color coding
    for i, (_, row_data) in enumerate(df_out.iterrows(), 2):
        for j, col in enumerate(cols, 1):
            cell = ws.cell(row=i, column=j, value=row_data.get(col))

        # Row color by migration period
        periode = row_data.get("migration_periode", "")
        fehler = row_data.get("fehler_typ", "OK")
        if fehler == "OK":
            fill_color = CLR_PRE if periode == "pre" else CLR_POST
        else:
            fill_color = CLR_ERROR

        fill = PatternFill(start_color=fill_color, end_color=fill_color, fill_type="solid")
        for j in range(1, len(cols) + 1):
            ws.cell(row=i, column=j).fill = fill

    auto_fit_columns(ws)
    ws.freeze_panes = "A2"


def write_monthly_sheet(wb, df_recon: pd.DataFrame):
    """Write monthly price comparison sheet."""
    if df_recon.empty or "monat" not in df_recon.columns:
        return

    ws = wb.create_sheet("Monatsvergleich")

    price_col = "frachtkosten_netto" if "frachtkosten_netto" in df_recon.columns else "ist_netto"
    if price_col not in df_recon.columns:
        return

    monthly = (df_recon.groupby("monat")
               .agg(
                   avg_preis=(price_col, "mean"),
                   n_sendungen=(price_col, "count"),
                   gesamt=(price_col, "sum"),
               )
               .reset_index()
               .sort_values("monat"))

    monthly["migration"] = monthly["monat"].apply(
        lambda m: "PRE" if m < "2025-09" else "POST"
    )

    headers = ["Monat", "Ø Preis/Sendung (€)", "Anzahl Sendungen", "Gesamtumsatz (€)", "Periode"]
    for j, h in enumerate(headers, 1):
        ws.cell(row=1, column=j, value=h)
    style_header_row(ws, 1)

    for i, row_data in enumerate(monthly.itertuples(), 2):
        ws.cell(row=i, column=1, value=row_data.monat)
        ws.cell(row=i, column=2, value=round(row_data.avg_preis, 2))
        ws.cell(row=i, column=3, value=row_data.n_sendungen)
        ws.cell(row=i, column=4, value=round(row_data.gesamt, 2))
        ws.cell(row=i, column=5, value=row_data.migration)

        color = CLR_POST if row_data.migration == "POST" else CLR_PRE
        fill = PatternFill(start_color=color, end_color=color, fill_type="solid")
        for j in range(1, 6):
            ws.cell(row=i, column=j).fill = fill

    # Add line chart
    chart = LineChart()
    chart.title = "Ø Preis/Sendung nach Monat (grün=pre, orange=post Migration)"
    chart.style = 10
    chart.y_axis.title = "Ø Preis (€)"
    chart.x_axis.title = "Monat"

    data = Reference(ws, min_col=2, min_row=1, max_row=len(monthly) + 1)
    chart.add_data(data, titles_from_data=True)
    cats = Reference(ws, min_col=1, min_row=2, max_row=len(monthly) + 1)
    chart.set_categories(cats)
    ws.add_chart(chart, "G2")

    auto_fit_columns(ws)


def write_error_sheet(wb, df_recon: pd.DataFrame):
    """Write error type distribution sheet."""
    if df_recon.empty or "fehler_typ" not in df_recon.columns:
        return

    ws = wb.create_sheet("Fehlerklassen")
    post = df_recon[df_recon.get("migration_periode", pd.Series()) == "post"] if "migration_periode" in df_recon.columns else df_recon

    error_counts = post["fehler_typ"].value_counts().reset_index()
    error_counts.columns = ["Fehlertyp", "Anzahl"]
    error_counts["Anteil %"] = error_counts["Anzahl"] / error_counts["Anzahl"].sum() * 100

    ERROR_TYPES = {
        "OK": "Korrekt abgerechnet",
        "A_PAUSCHAL": "Pauschaltarif statt Staffel",
        "B_ZUSCHLAG": "Zuschlag fehlt oder falsch",
        "C_KONDGRUPPE": "Falsche Konditionsgruppe",
        "D_PLZZONE": "Falsche Entfernungszone",
        "E_PARAMETER": "Falscher Abrechnungsparameter",
        "F_NICHT_FAKTURIERT": "Nicht fakturiert",
        "G_DOPPELT": "Doppelt berechnet",
        "UNBEKANNT": "Ursache unklar",
    }
    error_counts["Beschreibung"] = error_counts["Fehlertyp"].map(ERROR_TYPES)

    for j, h in enumerate(["Fehlertyp", "Beschreibung", "Anzahl", "Anteil %"], 1):
        ws.cell(row=1, column=j, value=h)
    style_header_row(ws, 1)

    for i, row_data in enumerate(error_counts.itertuples(), 2):
        ws.cell(row=i, column=1, value=row_data.Fehlertyp)
        ws.cell(row=i, column=2, value=row_data.Beschreibung)
        ws.cell(row=i, column=3, value=row_data.Anzahl)
        ws.cell(row=i, column=4, value=round(row_data._3, 1))
        color = CLR_OK if row_data.Fehlertyp == "OK" else CLR_ERROR
        fill = PatternFill(start_color=color, end_color=color, fill_type="solid")
        for j in range(1, 5):
            ws.cell(row=i, column=j).fill = fill

    auto_fit_columns(ws)


def generate_customer_report(kunde: str, output_dir: Path):
    """Generate full Excel report for one customer."""
    if not HAS_OPENPYXL:
        print("[ERROR] openpyxl not installed")
        return

    recon_file = output_dir / f"{kunde}_reconciliation.csv"
    if not recon_file.exists():
        print(f"[WARN] No reconciliation data for {kunde}")
        return

    df_recon = pd.read_csv(recon_file, sep=";", dtype=str, encoding="utf-8-sig")
    for col in ["frachtkosten_netto", "ist_netto", "soll_netto", "delta_eur",
                "delta_pct", "gewicht_kg", "lademeter", "preis_je_kg", "preis_je_ldm"]:
        if col in df_recon.columns:
            df_recon[col] = pd.to_numeric(df_recon[col].astype(str).str.replace(",", "."), errors="coerce")

    if "ladedatum" in df_recon.columns:
        df_recon["ladedatum"] = pd.to_datetime(df_recon["ladedatum"], errors="coerce")
        df_recon["monat"] = df_recon["ladedatum"].dt.to_period("M").astype(str)
        df_recon["migration_periode"] = np.where(df_recon["ladedatum"] < MIGRATION_DATE, "pre", "post")

    wb = openpyxl.Workbook()
    wb.remove(wb.active)  # Remove default sheet

    write_kpi_sheet(wb, kunde, df_recon, {}, {})
    write_detail_sheet(wb, df_recon)
    write_monthly_sheet(wb, df_recon)
    write_error_sheet(wb, df_recon)

    out_file = output_dir / f"{kunde}_audit_report.xlsx"
    wb.save(out_file)
    print(f"  → Saved: {out_file}")


def generate_top20_report(output_dir: Path):
    """Generate combined Top-20 Excel report."""
    if not HAS_OPENPYXL:
        print("[ERROR] openpyxl not installed")
        return

    top20_file = output_dir / "top20_analyse.csv"
    if not top20_file.exists():
        print("[WARN] Top-20 analysis file not found — run 05_top20_analysis.py first")
        return

    df = pd.read_csv(top20_file, sep=";", encoding="utf-8-sig")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Top-20 Übersicht"

    # Title
    ws["A1"] = "TOP-20 KUNDEN — TMS MIGRATIONSAUDIT NOERPEL"
    ws["A1"].font = Font(bold=True, size=14, color=CLR_ACCENT)
    ws["A2"] = f"Migrationsdatum: 26.09.2025 | Erstellt: {datetime.now().strftime('%d.%m.%Y')}"

    row = 4
    headers = ["Rang", "Kunde", "Umsatz (€)", "Ø Pre (€)", "Ø Post (€)",
               "Delta (€)", "Delta (%)", "p-Wert", "Signifikant", "Effektgröße",
               "Schaden (€)", "Richtung"]
    for j, h in enumerate(headers, 1):
        ws.cell(row=row, column=j, value=h)
    style_header_row(ws, row)
    row += 1

    col_map = {
        "rang": "rang",
        "kunde": "kunde",
        "umsatz_gesamt": "umsatz_gesamt",
        "bruch_mean_pre": "bruch_mean_pre",
        "bruch_mean_post": "bruch_mean_post",
        "bruch_delta_abs": "bruch_delta_abs",
        "bruch_delta_pct": "bruch_delta_pct",
        "bruch_p_value": "bruch_p_value",
        "bruch_signifikant": "bruch_signifikant",
        "bruch_effektstaerke": "bruch_effektstaerke",
        "schaden_schaden_gesamt_eur": "schaden_schaden_gesamt_eur",
        "schaden_richtung": "schaden_richtung",
    }

    for _, data_row in df.iterrows():
        vals = [data_row.get(col_map.get(h.replace(" ", "_").lower(), ""), "") for h in headers]
        for j, v in enumerate(vals, 1):
            ws.cell(row=row, column=j, value=v)

        # Highlight significant results
        signif = data_row.get("bruch_signifikant", False)
        schaden = data_row.get("schaden_schaden_gesamt_eur", 0)
        color = CLR_ERROR if (signif and abs(float(schaden or 0)) > 1000) else CLR_WARN if signif else "FFFFFF"
        fill = PatternFill(start_color=color, end_color=color, fill_type="solid")
        for j in range(1, len(headers) + 1):
            ws.cell(row=row, column=j).fill = fill
        row += 1

    auto_fit_columns(ws)
    out_file = output_dir / "top20_summary.xlsx"
    wb.save(out_file)
    print(f"  → Saved: {out_file}")


def main():
    parser = argparse.ArgumentParser(description="TMS Audit Report Generator")
    parser.add_argument("--output", type=str, default="output/",
                        help="Output directory")
    parser.add_argument("--kunde", type=str, default="",
                        help="Generate report for specific customer only")
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(exist_ok=True)

    if args.kunde:
        kunden = [args.kunde]
    else:
        # Find all reconciliation files
        kunden = [f.stem.replace("_reconciliation", "")
                  for f in output_dir.glob("*_reconciliation.csv")]

    print(f"Generating reports for: {kunden}")
    for kunde in kunden:
        print(f"\n  Report: {kunde}")
        generate_customer_report(kunde, output_dir)

    print("\n  Top-20 Summary Report:")
    generate_top20_report(output_dir)

    print(f"\nAlle Reports gespeichert in: {output_dir}/")


if __name__ == "__main__":
    main()
