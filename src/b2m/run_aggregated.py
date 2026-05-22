"""SCHRITT 5: Aggregierter Excel-Export aus allen 5 B2M-JSONLs.

Erzeugt output/b2m/b2m_aggregiert.xlsx mit 3 Sheets:
  - Positionen : (RN, KZ, WG) Aggregation — 12 Spalten + K1
  - Kontrolle  : K2 pro RN (Σ kz_summen vs Zusammenstellung)
  - Befunde     : Dokumentierte AT/DE Differenzen

Pre-re-run: K1=?, KZ-Gesamt=leer — erwartet und korrekt.

Run:
    python -m src.b2m.run_aggregated
"""
from __future__ import annotations
import json
from decimal import Decimal
from pathlib import Path
from typing import Optional

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from src.b2m.schema import PageResult, ManifestEntry
from src.b2m.aggregator import aggregate, AggRow, KontrolleRow

FULL_DIR = Path("output/b2m/full")
OUT_FILE = Path("output/b2m/b2m_aggregiert.xlsx")

PDF_STEMS = ["B2M_1_1", "B2M_2_1", "B2M_3_1", "B2M_4_1", "B2M_5_1"]

# ── Colours ────────────────────────────────────────────────────────────────
_C_HEADER   = "1F4E79"   # dark blue
_C_RN       = "2E75B6"   # medium blue
_C_OK       = "E2EFDA"   # green  — K1/K2 ✓
_C_FAIL     = "FFB3B3"   # red    — K1/K2 ✗
_C_UNKNOWN  = "F2F2F2"   # light grey — K1 ?
_C_DELTA_OK   = "E2EFDA"
_C_DELTA_WARN = "FFE699"
_C_DELTA_BAD  = "FFB3B3"


def _fill(hex_color: str) -> PatternFill:
    return PatternFill("solid", fgColor=hex_color)


def _hdr_font() -> Font:
    return Font(bold=True, color="FFFFFF", size=10)


def _thin() -> Border:
    s = Side(style="thin", color="AAAAAA")
    return Border(left=s, right=s, top=s, bottom=s)


def _pct(d: Optional[Decimal]) -> str:
    if d is None:
        return ""
    return f"{d:.2f}%"


def _dec(d: Optional[Decimal]) -> str:
    if d is None:
        return ""
    return f"{d:.2f}"


def _k_symbol(val: Optional[bool]) -> str:
    if val is True:
        return "✓"
    if val is False:
        return "✗"
    return "?"


def _k_fill(val: Optional[bool]) -> PatternFill:
    if val is True:
        return _fill(_C_OK)
    if val is False:
        return _fill(_C_FAIL)
    return _fill(_C_UNKNOWN)


# ── Load all pages from JSONLs ─────────────────────────────────────────────
def _load_all_pages() -> tuple[list[PageResult], Optional[list[ManifestEntry]]]:
    all_pages: list[PageResult] = []
    manifest: Optional[list[ManifestEntry]] = None
    for stem in PDF_STEMS:
        jsonl = FULL_DIR / f"{stem}_pages.jsonl"
        if not jsonl.exists():
            print(f"  SKIP (not found): {jsonl}")
            continue
        pdf_name = stem.removesuffix("_1") + " 1.pdf"
        for line in jsonl.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            raw = {k: v for k, v in d.items() if not k.startswith("_")}
            p = PageResult.from_dict(pdf_name, d.get("_seite", 0), raw)
            all_pages.append(p)
            if manifest is None and p.seiten_typ == "abrechnungsbrief" and p.manifest:
                manifest = p.manifest
    return all_pages, manifest


# ── Sheet 1: Positionen ────────────────────────────────────────────────────
_POS_COLS = [
    ("Rechnungsnummer",   16),
    ("Land",               6),
    ("Währung",            8),
    ("Kennzeichen (KZ)",  18),
    ("Warengruppe/Gruppe", 22),
    ("Artikelbezeichnung", 32),
    ("Σ Netto (WG)",      14),
    ("Σ USt (WG)",        14),
    ("Σ Brutto (WG)",     14),
    ("USt%",               8),
    ("Anz. Transakt.",    12),
    ("KZ-Gesamt Netto",   16),
    ("KZ-Gesamt Brutto",  16),
    ("K1",                  6),
]


def _write_positionen(ws, rows: list[AggRow]) -> None:
    ws.freeze_panes = "A2"

    # Header row
    for col, (title, width) in enumerate(_POS_COLS, 1):
        c = ws.cell(row=1, column=col, value=title)
        c.font = _hdr_font()
        c.fill = _fill(_C_HEADER)
        c.alignment = Alignment(horizontal="center", wrap_text=True)
        c.border = _thin()
        ws.column_dimensions[get_column_letter(col)].width = width

    ws.row_dimensions[1].height = 30

    for r_idx, row in enumerate(rows, 2):
        vals = [
            row.rn,
            row.land,
            row.waehrung,
            row.kz,
            row.wg,
            row.artikel,
            _dec(row.sum_netto),
            _dec(row.sum_ust),
            _dec(row.sum_brutto),
            _pct(row.ust_pct),
            row.n,
            _dec(row.kz_gesamt_netto),
            _dec(row.kz_gesamt_brutto),
            _k_symbol(row.k1),
        ]
        for col, val in enumerate(vals, 1):
            c = ws.cell(row=r_idx, column=col, value=val)
            c.border = _thin()
            c.font = Font(size=10)
            # K1 colour (last column)
            if col == len(_POS_COLS):
                c.fill = _k_fill(row.k1)
                c.alignment = Alignment(horizontal="center")
            elif col in (7, 8, 9, 12, 13):
                c.alignment = Alignment(horizontal="right")
            elif col in (10, 11, 14):
                c.alignment = Alignment(horizontal="center")

    # RN group separators: light blue background for first row of each new RN
    last_rn = None
    for r_idx, row in enumerate(rows, 2):
        if row.rn != last_rn:
            for col in range(1, len(_POS_COLS)):   # not K1 col
                ws.cell(row=r_idx, column=col).fill = _fill("BDD7EE")
            last_rn = row.rn


# ── Sheet 2: Kontrolle ────────────────────────────────────────────────────
_K2_COLS = [
    ("Rechnungsnummer",     16),
    ("Land",                 6),
    ("Währung",              8),
    ("Σ KZ-Netto",          14),
    ("Σ KZ-Brutto",         14),
    ("Zusammenst. Netto",   16),
    ("Zusammenst. Brutto",  16),
    ("K2",                   6),
    ("Manifest-Brutto",     16),
    ("Δ Cent",              10),
]


def _write_kontrolle(ws, rows: list[KontrolleRow]) -> None:
    ws.freeze_panes = "A2"

    for col, (title, width) in enumerate(_K2_COLS, 1):
        c = ws.cell(row=1, column=col, value=title)
        c.font = _hdr_font()
        c.fill = _fill(_C_HEADER)
        c.alignment = Alignment(horizontal="center", wrap_text=True)
        c.border = _thin()
        ws.column_dimensions[get_column_letter(col)].width = width
    ws.row_dimensions[1].height = 30

    for r_idx, row in enumerate(rows, 2):
        delta_str = f"{row.delta_cent:+d}" if row.delta_cent is not None else ""
        vals = [
            row.rn,
            row.land,
            row.waehrung,
            _dec(row.sigma_kz_netto),
            _dec(row.sigma_kz_brutto),
            _dec(row.zusammenstellung_netto),
            _dec(row.zusammenstellung_brutto),
            _k_symbol(row.k2),
            _dec(row.manifest_brutto),
            delta_str,
        ]
        for col, val in enumerate(vals, 1):
            c = ws.cell(row=r_idx, column=col, value=val)
            c.border = _thin()
            c.font = Font(size=10)

        # K2 colour
        k2_cell = ws.cell(row=r_idx, column=8)
        k2_cell.fill = _k_fill(row.k2)
        k2_cell.alignment = Alignment(horizontal="center")

        # Δ colour
        delta_cell = ws.cell(row=r_idx, column=10)
        delta_cell.alignment = Alignment(horizontal="right")
        if row.delta_cent is not None:
            ab = abs(row.delta_cent)
            if ab <= 10:
                delta_cell.fill = _fill(_C_DELTA_OK)
            elif ab <= 500:
                delta_cell.fill = _fill(_C_DELTA_WARN)
            else:
                delta_cell.fill = _fill(_C_DELTA_BAD)


# ── Sheet 3: Befunde ──────────────────────────────────────────────────────
_BEFUNDE = [
    # (PDF, RN, Land, Ist EUR, Soll EUR, Δ EUR, Befund)
    ("B2M_1", "3603006105", "AT", "2155.50", "2155.50",    "0.00", "✓ korrekt"),
    ("B2M_2", "3603014114", "AT", "1734.83", "1734.83",    "0.00", "✓ korrekt"),
    ("B2M_3", "3603022414", "AT", "2163.17", "1459.74", "+703.43", "✗ echte Abrechnungsdiff."),
    ("B2M_4", "3603030499", "AT", "2699.91", "1880.30", "+819.61", "✗ echte Abrechnungsdiff."),
]

_BEF_COLS = [
    ("PDF",           10),
    ("Rechnungsnummer", 16),
    ("Land",            6),
    ("Ist (EUR)",      12),
    ("Soll (EUR)",     12),
    ("Δ (EUR)",        12),
    ("Befund",         36),
]


def _write_befunde(ws) -> None:
    ws.cell(row=1, column=1,
            value="Dokumentierte Abrechnungsunterschiede — Carlos 2026-05-22"
            ).font = Font(bold=True, size=11)

    note = ("ERSATZKARTE 2 ist in ALLEN B2M-AT-Rechnungen ein echter Einzelposten. "
            "Die Δ-Werte in B2M_3/4 AT sind echte Abrechnungsdifferenzen, keine Extraktionsfehler.")
    ws.cell(row=2, column=1, value=note).font = Font(italic=True, size=10)
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=7)

    for col, (title, width) in enumerate(_BEF_COLS, 1):
        c = ws.cell(row=4, column=col, value=title)
        c.font = _hdr_font()
        c.fill = _fill(_C_HEADER)
        c.alignment = Alignment(horizontal="center")
        c.border = _thin()
        ws.column_dimensions[get_column_letter(col)].width = width

    for r_idx, (pdf, rn, land, ist, soll, delta, befund) in enumerate(_BEFUNDE, 5):
        vals = [pdf, rn, land, ist, soll, delta, befund]
        for col, val in enumerate(vals, 1):
            c = ws.cell(row=r_idx, column=col, value=val)
            c.border = _thin()
            c.font = Font(size=10)
        ok = delta.startswith("0") or delta == "0.00"
        ws.cell(row=r_idx, column=7).fill = _fill(_C_OK if ok else _C_FAIL)


# ── Main ──────────────────────────────────────────────────────────────────
def run() -> None:
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    print("Lade JSONLs ...")
    all_pages, manifest = _load_all_pages()
    rechnungen = [p for p in all_pages if p.seiten_typ == "rechnung"]
    print(f"  {len(all_pages)} Seiten gesamt, {len(rechnungen)} RECHNUNG-Seiten")
    if manifest:
        print(f"  Manifest: {len(manifest)} Einträge")

    print("Aggregiere ...")
    agg_rows, kontrolle_rows = aggregate(all_pages, manifest)
    print(f"  {len(agg_rows)} Aggregat-Zeilen, {len(kontrolle_rows)} Kontrolle-Zeilen")

    # K1 statistics
    k1_ok   = sum(1 for r in agg_rows if r.k1 is True)
    k1_fail = sum(1 for r in agg_rows if r.k1 is False)
    k1_none = sum(1 for r in agg_rows if r.k1 is None)
    print(f"  K1: ✓{k1_ok}  ✗{k1_fail}  ?{k1_none}")

    k2_ok   = sum(1 for r in kontrolle_rows if r.k2 is True)
    k2_fail = sum(1 for r in kontrolle_rows if r.k2 is False)
    k2_none = sum(1 for r in kontrolle_rows if r.k2 is None)
    print(f"  K2: ✓{k2_ok}  ✗{k2_fail}  ?{k2_none}")

    print(f"Schreibe {OUT_FILE} ...")
    wb = openpyxl.Workbook()

    ws_pos = wb.active
    ws_pos.title = "Positionen"
    _write_positionen(ws_pos, agg_rows)

    ws_k2 = wb.create_sheet("Kontrolle")
    _write_kontrolle(ws_k2, kontrolle_rows)

    ws_bef = wb.create_sheet("Befunde")
    _write_befunde(ws_bef)

    wb.save(OUT_FILE)
    print(f"  Gespeichert: {OUT_FILE}")

    # Delta summary
    print("\n  Δ-Übersicht (Kontrolle-Sheet):")
    print(f"  {'RN':12s}  {'Land':4s}  {'Δ Cent':>8s}  Status")
    for r in kontrolle_rows:
        if r.delta_cent is not None:
            ab = abs(r.delta_cent)
            status = "✓" if ab <= 10 else ("~" if ab <= 500 else "✗")
            print(f"  {r.rn:12s}  {r.land:4s}  {r.delta_cent:>+8d}  {status}")


if __name__ == "__main__":
    run()
