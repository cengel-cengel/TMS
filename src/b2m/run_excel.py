"""SCHRITT 4: Excel-Exports aus run_full JSONL-Dateien.

Erzeugt pro PDF eine Excel-Datei (B2M_1.xlsx … B2M_5.xlsx) mit:
  - Detailzeilen: je Position gruppiert nach (RN, Karte, KZ, Artikel)
  - Pro-RN Summenblock: Σ netto/ust/brutto + Δ vs Manifest
  - Übersichts-Sheet: alle RN aller PDFs mit Δ-Spalte

Währung: CH=CHF, alle anderen=EUR (aus Manifest).

Run:
    python -m src.b2m.run_excel
"""
from __future__ import annotations
import json
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Optional

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from src.b2m.schema import PageResult, ManifestEntry, cents, parse_de

FULL_DIR   = Path("output/b2m/full")
EXCEL_DIR  = Path("output/b2m/excel")

PDF_STEMS = [
    "B2M_1_1",
    "B2M_2_1",
    "B2M_3_1",
    "B2M_4_1",
    "B2M_5_1",
]

# ── Colour palette ──────────────────────────────────────────────────────────
_C_HEADER  = "1F4E79"   # dark blue    — column headers
_C_RN      = "2E75B6"   # medium blue  — per-RN block header
_C_SUM     = "BDD7EE"   # light blue   — summary rows
_C_DELTA_OK  = "E2EFDA" # light green  — Δ ≤ 10 Cent
_C_DELTA_WARN = "FFE699" # amber        — 10 < Δ ≤ 500 Cent
_C_DELTA_BAD  = "FFB3B3" # light red   — Δ > 500 Cent (large gap)

_COLS = [
    "Rechnungsnummer",
    "Rechnungsdatum",
    "Kartennummer",
    "Kennzeichen",
    "Artikelbezeichnung",
    "Warengruppe",
    "Nettobetrag",
    "Steuerbetrag",
    "Bruttobetrag",
    "Währung",
]
_COL_WIDTHS = [16, 14, 18, 14, 32, 16, 14, 14, 14, 8]


def _fill(hex_color: str) -> PatternFill:
    return PatternFill("solid", fgColor=hex_color)


def _font(bold=False, color="000000", size=10) -> Font:
    return Font(bold=bold, color=color, size=size)


def _thin_border() -> Border:
    s = Side(style="thin", color="CCCCCC")
    return Border(left=s, right=s, top=s, bottom=s)


def _load_pages(stem: str) -> list[PageResult]:
    jsonl = FULL_DIR / f"{stem}_pages.jsonl"
    if not jsonl.exists():
        return []
    pages = []
    for line in jsonl.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        d = json.loads(line)
        seite = d.get("_seite") or d.get("seite") or 0
        raw = {k: v for k, v in d.items() if not k.startswith("_")}
        pages.append(PageResult.from_dict(stem, seite, raw))
    return pages


def _group_positions(pages: list[PageResult]) -> dict[str, list[dict]]:
    """Group positions by RN → list of aggregated rows (one per karte/kz/artikel)."""
    # raw accumulator: (rn, kartennummer, kennzeichen, artikel) → {netto, ust, brutto, warengruppe}
    acc: dict[tuple, dict] = defaultdict(lambda: {
        "netto": Decimal(0), "ust": Decimal(0), "brutto": Decimal(0),
        "warengruppe": None,
    })
    rn_order: list[str] = []
    seen_rn: set[str] = set()

    for page in pages:
        if page.seiten_typ != "rechnung":
            continue
        rn = page.rechnungsnummer or ""
        if rn not in seen_rn:
            rn_order.append(rn)
            seen_rn.add(rn)
        for pos in page.positionen:
            if pos.netto is None and pos.brutto is None:
                continue
            key = (rn, pos.kartennummer or "", pos.kennzeichen or "", pos.artikel or "")
            row = acc[key]
            row["netto"]  += pos.netto  or Decimal(0)
            row["ust"]    += pos.ust    or Decimal(0)
            row["brutto"] += pos.brutto or Decimal(0)
            if pos.warengruppe:
                row["warengruppe"] = pos.warengruppe

    by_rn: dict[str, list[dict]] = defaultdict(list)
    for (rn, karte, kz, artikel), row in acc.items():
        by_rn[rn].append({
            "rn":          rn,
            "kartennummer": karte,
            "kennzeichen":  kz,
            "artikel":      artikel,
            "warengruppe":  row["warengruppe"],
            "netto":        row["netto"],
            "ust":          row["ust"],
            "brutto":       row["brutto"],
        })

    result = {}
    for rn in rn_order:
        rows = by_rn.get(rn, [])
        rows.sort(key=lambda r: (r["kartennummer"], r["kennzeichen"], r["artikel"]))
        result[rn] = rows
    return result


def _build_manifest_index(pages: list[PageResult]) -> dict[str, ManifestEntry]:
    cover = next((p for p in pages if p.seiten_typ == "abrechnungsbrief"), None)
    if not cover or not cover.manifest:
        return {}
    return {m.rechnungsnummer: m for m in cover.manifest}


def _dec_str(d: Decimal) -> str:
    return f"{d:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _write_sheet(ws, pages: list[PageResult], pdf_label: str) -> list[dict]:
    """Fill the detail sheet. Returns list of per-RN delta dicts for Übersicht."""
    by_rn = _group_positions(pages)
    manifest = _build_manifest_index(pages)

    # Column headers
    for col_i, (name, width) in enumerate(zip(_COLS, _COL_WIDTHS), start=1):
        cell = ws.cell(row=1, column=col_i, value=name)
        cell.font = _font(bold=True, color="FFFFFF")
        cell.fill = _fill(_C_HEADER)
        cell.alignment = Alignment(horizontal="center", vertical="center")
        ws.column_dimensions[get_column_letter(col_i)].width = width
    ws.row_dimensions[1].height = 18
    ws.freeze_panes = "A2"

    current_row = 2
    overview_rows = []

    for rn, rows in by_rn.items():
        m = manifest.get(rn)
        datum    = m.datum    if m else ""
        waehrung = m.waehrung if m else "EUR"

        # ── RN-Header ────────────────────────────────────────────────────
        ws.merge_cells(start_row=current_row, start_column=1,
                       end_row=current_row, end_column=len(_COLS))
        hdr = ws.cell(row=current_row, column=1,
                      value=f"Rechnungsnummer: {rn}   |   {datum}   |   {waehrung}")
        hdr.font  = _font(bold=True, color="FFFFFF")
        hdr.fill  = _fill(_C_RN)
        hdr.alignment = Alignment(horizontal="left", vertical="center", indent=1)
        ws.row_dimensions[current_row].height = 16
        current_row += 1

        # ── Detail-Zeilen ─────────────────────────────────────────────────
        for row in rows:
            def _cv(col, val, num=False):
                c = ws.cell(row=current_row, column=col, value=val)
                c.border = _thin_border()
                if num:
                    c.number_format = '#,##0.00'
                    c.alignment = Alignment(horizontal="right")
                return c

            _cv(1,  rn)
            _cv(2,  datum)
            _cv(3,  row["kartennummer"])
            _cv(4,  row["kennzeichen"])
            _cv(5,  row["artikel"])
            _cv(6,  row["warengruppe"] or "")
            _cv(7,  float(row["netto"]),   num=True)
            _cv(8,  float(row["ust"]),     num=True)
            _cv(9,  float(row["brutto"]), num=True)
            _cv(10, waehrung)
            current_row += 1

        # ── Summen-Block ──────────────────────────────────────────────────
        sum_netto  = sum(r["netto"]  for r in rows)
        sum_ust    = sum(r["ust"]    for r in rows)
        sum_brutto = sum(r["brutto"] for r in rows)

        def _sum_row(label, netto_val, ust_val, brutto_val, fill_hex=_C_SUM):
            ws.merge_cells(start_row=current_row, start_column=1,
                           end_row=current_row, end_column=6)
            lc = ws.cell(row=current_row, column=1, value=label)
            lc.font  = _font(bold=True)
            lc.fill  = _fill(fill_hex)
            lc.alignment = Alignment(horizontal="right", vertical="center", indent=1)
            for col, val in [(7, netto_val), (8, ust_val), (9, brutto_val)]:
                c = ws.cell(row=current_row, column=col, value=val)
                c.font          = _font(bold=True)
                c.fill          = _fill(fill_hex)
                c.number_format = '#,##0.00'
                c.alignment     = Alignment(horizontal="right")
                c.border        = _thin_border()
            ws.cell(row=current_row, column=10).fill = _fill(fill_hex)

        _sum_row(f"Σ extrahiert ({waehrung})",
                 float(sum_netto), float(sum_ust), float(sum_brutto))
        current_row += 1

        # ── Manifest-Soll + Δ ─────────────────────────────────────────────
        if m:
            soll_lw = m.betrag_lw if m.betrag_lw is not None else m.betrag_eur
            soll_eur = m.betrag_eur
            delta_cent = cents(sum_brutto) - cents(soll_lw)

            _sum_row(f"Soll Manifest ({waehrung})",
                     None, None, float(soll_lw), fill_hex="D9E1F2")
            current_row += 1

            delta_color = (
                _C_DELTA_OK   if abs(delta_cent) <= 10   else
                _C_DELTA_WARN if abs(delta_cent) <= 500  else
                _C_DELTA_BAD
            )
            delta_label = f"Δ = {delta_cent:+d} Cent  ({delta_cent/100:+.2f} {waehrung})"
            _sum_row(delta_label, None, None, None, fill_hex=delta_color)
            current_row += 1

            overview_rows.append({
                "pdf":        pdf_label,
                "rn":         rn,
                "datum":      datum,
                "land":       m.land,
                "waehrung":   waehrung,
                "ist":        float(sum_brutto),
                "soll":       float(soll_lw),
                "delta_cent": delta_cent,
            })
        else:
            overview_rows.append({
                "pdf":        pdf_label,
                "rn":         rn,
                "datum":      "",
                "land":       "",
                "waehrung":   "EUR",
                "ist":        float(sum_brutto),
                "soll":       None,
                "delta_cent": None,
            })

        # blank separator
        current_row += 1

    return overview_rows


def _write_overview(wb: openpyxl.Workbook, all_overview: list[dict]) -> None:
    ws = wb.create_sheet("Übersicht", 0)
    headers = ["PDF", "Land", "Rechnungsnummer", "Datum", "Währung",
               "Ist Brutto", "Soll Brutto", "Δ Cent", "Δ EUR", "Status"]
    widths  = [10, 6, 18, 14, 8, 14, 14, 10, 10, 8]

    for col_i, (h, w) in enumerate(zip(headers, widths), start=1):
        cell = ws.cell(row=1, column=col_i, value=h)
        cell.font  = _font(bold=True, color="FFFFFF")
        cell.fill  = _fill(_C_HEADER)
        cell.alignment = Alignment(horizontal="center")
        ws.column_dimensions[get_column_letter(col_i)].width = w
    ws.row_dimensions[1].height = 18
    ws.freeze_panes = "A2"

    for r_i, row in enumerate(all_overview, start=2):
        dc = row["delta_cent"]
        status = (
            "✓" if dc is not None and abs(dc) <= 10 else
            f"Δ={dc:+d}¢" if dc is not None else "kein Manifest"
        )
        color = (
            _C_DELTA_OK   if dc is not None and abs(dc) <= 10   else
            _C_DELTA_WARN if dc is not None and abs(dc) <= 500  else
            _C_DELTA_BAD  if dc is not None else "F2F2F2"
        )
        vals = [
            row["pdf"], row["land"], row["rn"], row["datum"], row["waehrung"],
            row["ist"],
            row["soll"],
            dc,
            dc / 100 if dc is not None else None,
            status,
        ]
        for col_i, val in enumerate(vals, start=1):
            c = ws.cell(row=r_i, column=col_i, value=val)
            c.fill   = _fill(color)
            c.border = _thin_border()
            if col_i in (6, 7, 9):
                c.number_format = '#,##0.00'
                c.alignment = Alignment(horizontal="right")
            if col_i == 8:
                c.alignment = Alignment(horizontal="right")


def build_excel(stem: str) -> Optional[Path]:
    pages = _load_pages(stem)
    if not pages:
        print(f"  SKIP {stem}: keine JSONL-Daten")
        return None

    pdf_label = stem.removesuffix("_1").replace("_", " ")  # "B2M 1"
    excel_name = stem.removesuffix("_1") + ".xlsx"         # "B2M_1.xlsx"
    out_path = EXCEL_DIR / excel_name

    wb = openpyxl.Workbook()
    ws_detail = wb.active
    ws_detail.title = "Positionen"

    overview = _write_sheet(ws_detail, pages, pdf_label)
    _write_overview(wb, overview)

    wb.save(out_path)
    print(f"  ✓ {out_path}  ({len(overview)} RN)")
    return out_path


def run() -> None:
    EXCEL_DIR.mkdir(parents=True, exist_ok=True)
    all_overview = []

    for stem in PDF_STEMS:
        pages = _load_pages(stem)
        if not pages:
            print(f"  SKIP {stem}: keine JSONL-Daten")
            continue

        pdf_label = stem.removesuffix("_1").replace("_", " ")
        excel_name = stem.removesuffix("_1") + ".xlsx"
        out_path = EXCEL_DIR / excel_name

        wb = openpyxl.Workbook()
        ws_detail = wb.active
        ws_detail.title = "Positionen"

        overview = _write_sheet(ws_detail, pages, pdf_label)
        all_overview.extend(overview)
        _write_overview(wb, overview)

        wb.save(out_path)
        print(f"  ✓ {out_path}  ({len(overview)} RN)")

    # Combined overview workbook across all PDFs
    if all_overview:
        combined_path = EXCEL_DIR / "B2M_alle_Differenzen.xlsx"
        wb_all = openpyxl.Workbook()
        ws_all = wb_all.active
        ws_all.title = "Alle RN"
        _write_overview(wb_all, all_overview)  # reuse overview writer
        # The overview writer creates a new sheet at index 0 — move active sheet
        wb_all.active = wb_all["Alle RN"]
        wb_all.save(combined_path)
        print(f"\n  ✓ Kombiniert: {combined_path}  ({len(all_overview)} RN gesamt)")

        print(f"\n{'='*60}")
        print(f"DIFFERENZ-ÜBERSICHT ALLE RN")
        print(f"{'='*60}")
        hdr = f"  {'PDF':8s}  {'Land':4s}  {'RN':14s}  {'Währ':4s}  {'Ist':>12s}  {'Soll':>12s}  {'Δ Cent':>8s}  Status"
        print(hdr)
        print(f"  {'-'*8}  {'-'*4}  {'-'*14}  {'-'*4}  {'-'*12}  {'-'*12}  {'-'*8}  ------")
        for row in all_overview:
            dc = row["delta_cent"]
            status = "✓" if dc is not None and abs(dc) <= 10 else f"✗ Δ={dc:+d}¢" if dc is not None else "—"
            soll_str = f"{row['soll']:>12.2f}" if row['soll'] is not None else f"{'—':>12s}"
            print(f"  {row['pdf']:8s}  {row['land']:4s}  {row['rn']:14s}  {row['waehrung']:4s}  {row['ist']:>12.2f}  {soll_str}  {str(dc or '—'):>8s}  {status}")


if __name__ == "__main__":
    run()
