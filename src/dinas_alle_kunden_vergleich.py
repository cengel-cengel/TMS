#!/usr/bin/env python3
"""
dinas_alle_kunden_vergleich.py
==============================
Erweiterung des Dinas-PDF-Parsers auf alle Kunden (Step C).

Pro Kunde wird ein Excel erstellt mit:
  - Zusammenfassung   : Kennzahlen PRE-Dinas vs POST-AX
  - PRE Dinas Detail  : Gematcht PRE-Zeilen mit Dinas-NK-Aufschlüsselung
  - POST AX Detail    : POST-Zeilen mit AX-NK-Aufschlüsselung

Join:  BI Rechnungsnummer  ↔  Dinas-PDF rechnung_nr
       (normiert: führende Nullen entfernt, nur Ziffern)

Output: output/{kunde}_dinas_vergleich.xlsx  (je Kunde)

PDF-Caches: output/dinas_cache_{knr}.pkl  (je Kunde, für Wiederverwendung)
"""

import sys
import os
import pickle
import re
import math
import warnings
from pathlib import Path

import pandas as pd
import numpy as np
from openpyxl import Workbook
from openpyxl.styles import (
    PatternFill, Font, Alignment, Border, Side
)
from openpyxl.utils import get_column_letter

warnings.filterwarnings('ignore')

# ── Pfade ──────────────────────────────────────────────────────────────────
BASE    = Path('/home/user/TMS')
OUT_DIR = BASE / 'output'
sys.path.insert(0, str(BASE / 'src'))

from dinas_pdf_parser import parse_directory, DINAS_CATS

# ── Kundendefinitionen ─────────────────────────────────────────────────────
CUSTOMERS = {
    406345: {
        'name': 'Bitzer Kühlmaschinenbau GmbH',
        'short': 'bitzer',
        'pdf_dir': BASE / 'data/extracted/v1/Noerpel AI/Bitzer/Rechnungen/Rechnungen DINAS',
    },
    408244: {
        'name': 'HELU KABEL GMBH',
        'short': 'helu',
        'pdf_dir': BASE / 'data/extracted/v1/Noerpel AI/Helu/Rechnungen/Rechnungen DINAS',
    },
    491063: {
        'name': 'Sika Deutschland GmbH',
        'short': 'sika',
        'pdf_dir': BASE / 'data/extracted/v1/Noerpel AI/SIka/Rechnungen/Rechnungen DINAS',
    },
    409480: {
        'name': 'Fischerwerke GmbH & Co. KG',
        'short': 'fischerwerke',
        'pdf_dir': BASE / 'data/extracted/v2/Fischer/Rechnungen/Rechnungen DINAS',
    },
    490085: {
        'name': 'Konrad Hornschuch GmbH',
        'short': 'hornschuch',
        'pdf_dir': BASE / 'data/extracted/v1/Noerpel AI/Hornschuch/Rechnungen/Rechnungen DINAS',
    },
    406035: {
        'name': 'GEZE GmbH',
        'short': 'geze',
        'pdf_dir': BASE / 'data/extracted/v1/Noerpel AI/GEZE/Rechnungen/Rechnungen DINAS',
    },
    486073: {
        'name': 'CHT Germany GmbH',
        'short': 'cht',
        'pdf_dir': BASE / 'data/extracted/v1/Noerpel AI/CHT/Rechnungen/Rechnungen DINAS',
    },
    410844: {
        'name': 'EBM-Papst Mulfingen GmbH & Co. KG',
        'short': 'ebm',
        'pdf_dir': BASE / 'data/extracted/v1/Noerpel AI/EBM/Rechnungen/Rechnungen DINAS',
    },
}

# ── BI-Daten laden ─────────────────────────────────────────────────────────
def load_bi() -> pd.DataFrame:
    pklpath = OUT_DIR / 'bi_top20_data.pkl'
    with open(pklpath, 'rb') as f:
        data = pickle.load(f)
    df = data['df'].copy()
    df['Kunden Nr BK'] = pd.to_numeric(df['Kunden Nr BK'], errors='coerce')
    return df


# ── RN-Normalisierung ──────────────────────────────────────────────────────
def norm_rn(s) -> str:
    """Entfernt führende Nullen und Nicht-Ziffern."""
    return re.sub(r'\D', '', str(s)).lstrip('0')


# ── PDF-Cache ──────────────────────────────────────────────────────────────
def load_or_parse(knr: int, pdf_dir: Path) -> pd.DataFrame:
    """Lädt geparste PDFs aus Cache oder parst neu."""
    cache_path = OUT_DIR / f'dinas_cache_{knr}.pkl'
    if cache_path.exists():
        print(f'  Lade Cache {cache_path.name} …')
        with open(cache_path, 'rb') as f:
            return pickle.load(f)

    dinas_df = parse_directory(pdf_dir, verbose=True)
    if not dinas_df.empty:
        with open(cache_path, 'wb') as f:
            pickle.dump(dinas_df, f)
        print(f'  Cache gespeichert: {cache_path.name}')
    return dinas_df


# ── Join PRE BI ↔ Dinas PDFs ───────────────────────────────────────────────
BI_META_COLS = [
    'Rechnungsnummer', 'Auftragsnummer', 'Leistungsdatum',
    'Empfänger Name', 'Empfänger PLZ', 'Empfänger Land',
    'Versender Name', 'Versender PLZ',
    'Tonnage (eff.)', 'Lademeter',
    'Stellplätze', 'Volumen',
    'Ausgangsrelation Business Key',
]

AX_NK_COLS = {
    'AX Fracht'       : 'Erlöse Fracht',
    'AX Diesel'       : 'Erlöse Diesel',
    'AX Maut'         : 'Erlöse Maut',
    'AX Nebengebühr'  : 'Erlöse Nebengebühr',
    'AX Lademittel'   : 'Erlöse Lademittel',
    'AX Peak'         : 'Erlöse Peak',
    'AX EUST/Zoll'    : 'Erlöse EUST Zoll',
    'AX Versicherung' : 'Erlöse Transportversicherung',
    'AX Gesamt'       : 'Erloese',
}

DINAS_NK_RENAME = {
    'fracht'       : 'Dinas Fracht',
    'diesel'       : 'Dinas Diesel',
    'maut_ssd'     : 'Dinas Maut/SSD',
    'ausfuhr'      : 'Dinas Ausfuhr',
    'verzollung'   : 'Dinas Verzollung',
    'zoll_duty'    : 'Dinas Zoll Duty',
    'zoll_betrag'  : 'Dinas Zollbetrag',
    'sulphur'      : 'Dinas Sulphur',
    'neben_pausch' : 'Dinas Nebenkostenpausch.',
    'redebit'      : 'Dinas Redebit',
    'sonstige'     : 'Dinas Sonstige',
    'gesamtbetrag' : 'Dinas Gesamt',
}


def build_pre_detail(bi_df: pd.DataFrame, dinas_df: pd.DataFrame, knr: int) -> pd.DataFrame:
    """Gibt PRE-BI-Zeilen zurück, gejoint mit Dinas-NK-Aufschlüsselung."""
    bi_pre = bi_df[(bi_df['Kunden Nr BK'] == knr) & (bi_df['periode'] == 'PRE')].copy()

    # Meta-Spalten: nur vorhandene verwenden
    meta_cols = [c for c in BI_META_COLS if c in bi_pre.columns]

    # RN normieren
    bi_pre['_rn'] = bi_pre['Rechnungsnummer'].astype(str).apply(norm_rn)

    if dinas_df.empty:
        return pd.DataFrame()

    dinas_work = dinas_df.copy()
    dinas_work['_rn'] = dinas_work['rechnung_nr'].astype(str).apply(norm_rn)

    # Dinas-Spalten: nur NK-Kategorien + Gesamt
    dinas_sel = dinas_work[['_rn', 'ldm', 'kg_rechnung'] + DINAS_CATS + ['gesamtbetrag']].copy()
    # Aggregieren: mehrere Positionen pro RN summieren
    dinas_agg = dinas_sel.groupby('_rn', as_index=False).agg({
        'ldm': 'sum', 'kg_rechnung': 'sum',
        **{c: 'sum' for c in DINAS_CATS},
        'gesamtbetrag': 'sum',
    })

    merged = bi_pre[meta_cols + ['_rn']].merge(
        dinas_agg, on='_rn', how='inner'
    )
    merged.drop(columns=['_rn'], inplace=True)

    # Umbenennen
    for old, new in DINAS_NK_RENAME.items():
        if old in merged.columns:
            merged.rename(columns={old: new}, inplace=True)

    # Numerisch
    for c in ['Tonnage (eff.)', 'Lademeter']:
        if c in merged.columns:
            merged[c] = pd.to_numeric(merged[c], errors='coerce')

    return merged.reset_index(drop=True)


def build_post_detail(bi_df: pd.DataFrame, knr: int) -> pd.DataFrame:
    """Gibt POST-BI-Zeilen zurück mit AX-NK-Aufschlüsselung."""
    bi_post = bi_df[(bi_df['Kunden Nr BK'] == knr) & (bi_df['periode'] == 'POST')].copy()

    meta_cols = [c for c in BI_META_COLS if c in bi_post.columns]

    out = bi_post[meta_cols].copy()
    for new_col, src_col in AX_NK_COLS.items():
        if src_col in bi_post.columns:
            out[new_col] = pd.to_numeric(bi_post[src_col], errors='coerce')
        else:
            out[new_col] = np.nan

    return out.reset_index(drop=True)


# ── Zusammenfassung ────────────────────────────────────────────────────────
def build_zusammenfassung(knr: int, info: dict, bi_df: pd.DataFrame,
                           dinas_df: pd.DataFrame,
                           pre_detail: pd.DataFrame,
                           post_detail: pd.DataFrame) -> list[tuple]:
    """Erstellt Kennzahlen als (Schlüssel, Wert)-Tupelliste."""
    import glob as _glob

    n_pdfs = len(list(_glob.glob(str(info['pdf_dir'] / '*.pdf'))))
    n_pos  = len(dinas_df) if not dinas_df.empty else 0

    bi_pre  = bi_df[(bi_df['Kunden Nr BK'] == knr) & (bi_df['periode'] == 'PRE')]
    bi_post = bi_df[(bi_df['Kunden Nr BK'] == knr) & (bi_df['periode'] == 'POST')]

    rows = [
        (f'{info["name"]} ({knr}) — Dinas PDF vs AX Vergleich', ''),
        ('Erstellt', pd.Timestamp.today().strftime('%d.%m.%Y')),
        ('', ''),
        ('── PDFs & Parsing ─────────────────────────────', ''),
        ('PDF-Verzeichnis', str(info['pdf_dir'])),
        ('PDFs gesamt',     n_pdfs),
        ('Positionen geparst', n_pos),
        ('', ''),
        ('── PRE (Dinas-System) ──────────────────────────', ''),
        ('BI-Zeilen PRE',   len(bi_pre)),
        ('Gematchte Zeilen (RN-Join)', len(pre_detail)),
        ('Match-Quote',     f'{len(pre_detail)/max(len(bi_pre),1)*100:.1f}%'),
    ]

    if not pre_detail.empty and 'Dinas Fracht' in pre_detail.columns:
        rows += [
            ('Σ Dinas Fracht EUR',    round(pre_detail['Dinas Fracht'].sum(), 2)),
            ('Σ Dinas Diesel EUR',    round(pre_detail.get('Dinas Diesel', pd.Series([0])).sum(), 2) if 'Dinas Diesel' in pre_detail else 0),
            ('Σ Dinas Maut/SSD EUR',  round(pre_detail.get('Dinas Maut/SSD', pd.Series([0])).sum(), 2) if 'Dinas Maut/SSD' in pre_detail else 0),
            ('Σ Dinas Gesamt EUR',    round(pre_detail['Dinas Gesamt'].sum(), 2) if 'Dinas Gesamt' in pre_detail else '–'),
        ]

    rows += [
        ('', ''),
        ('── POST (AX-System) ────────────────────────────', ''),
        ('BI-Zeilen POST', len(bi_post)),
    ]

    if not post_detail.empty and 'AX Fracht' in post_detail.columns:
        post_fracht = pd.to_numeric(post_detail['AX Fracht'], errors='coerce')
        post_gesamt = pd.to_numeric(post_detail['AX Gesamt'], errors='coerce')
        rows += [
            ('Σ AX Fracht EUR',   round(post_fracht.sum(), 2)),
            ('Σ AX Gesamt EUR',   round(post_gesamt.sum(), 2)),
            ('Ø AX Fracht/Sdg.',  round(post_fracht.mean(), 2)),
        ]

    return rows


# ── Excel schreiben ────────────────────────────────────────────────────────
FILL_BLUE   = PatternFill('solid', fgColor='BDD7EE')   # PRE / Dinas
FILL_ORANGE = PatternFill('solid', fgColor='FCE4D6')   # POST / AX
FILL_HEADER = PatternFill('solid', fgColor='2E75B6')   # Header
FILL_SECTION = PatternFill('solid', fgColor='D6E4F7')  # Abschnitt

FONT_HEADER = Font(bold=True, color='FFFFFF', size=11)
FONT_BOLD   = Font(bold=True)
FONT_SMALL  = Font(size=9)

THIN = Side(border_style='thin', color='B0B0B0')
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def _auto_width(ws):
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            try:
                val = str(cell.value) if cell.value is not None else ''
                max_len = max(max_len, len(val))
            except Exception:
                pass
        ws.column_dimensions[col_letter].width = min(max(max_len + 2, 10), 50)


def _write_sheet_df(ws, df: pd.DataFrame, fill: PatternFill, title: str = ''):
    """Schreibt einen DataFrame als formatierte Tabelle."""
    if title:
        ws.append([title])
        title_cell = ws.cell(ws.max_row, 1)
        title_cell.font = Font(bold=True, size=12)
        title_cell.fill = FILL_SECTION
        ws.merge_cells(start_row=ws.max_row, start_column=1,
                       end_row=ws.max_row, end_column=len(df.columns))
        ws.append([])

    # Header
    ws.append(list(df.columns))
    header_row = ws.max_row
    for c_idx in range(1, len(df.columns) + 1):
        cell = ws.cell(header_row, c_idx)
        cell.fill = FILL_HEADER
        cell.font = FONT_HEADER
        cell.alignment = Alignment(horizontal='center', wrap_text=True)
        cell.border = BORDER

    # Daten
    for _, row in df.iterrows():
        ws.append(list(row))
        data_row = ws.max_row
        for c_idx in range(1, len(df.columns) + 1):
            cell = ws.cell(data_row, c_idx)
            cell.fill = fill
            cell.border = BORDER
            cell.font = FONT_SMALL
            # Zahlen rechtsbündig
            val = row.iloc[c_idx - 1]
            if isinstance(val, (int, float)) and not pd.isna(val):
                cell.alignment = Alignment(horizontal='right')
                if isinstance(val, float):
                    cell.number_format = '#,##0.00'

    _auto_width(ws)


def write_excel(knr: int, info: dict, zusammenfassung: list[tuple],
                pre_detail: pd.DataFrame, post_detail: pd.DataFrame,
                out_path: Path):
    wb = Workbook()

    # ── Sheet 1: Zusammenfassung ──────────────────────────────────────────
    ws_zs = wb.active
    ws_zs.title = 'Zusammenfassung'
    ws_zs.column_dimensions['A'].width = 45
    ws_zs.column_dimensions['B'].width = 25

    for key, val in zusammenfassung:
        ws_zs.append([key, val])
        row_idx = ws_zs.max_row
        cell_a = ws_zs.cell(row_idx, 1)
        cell_b = ws_zs.cell(row_idx, 2)

        if val == '' and key.startswith('─'):
            cell_a.fill = FILL_SECTION
            cell_a.font = FONT_BOLD
            ws_zs.merge_cells(start_row=row_idx, start_column=1,
                               end_row=row_idx, end_column=2)
        elif key == '' and val == '':
            pass
        elif row_idx == 1:
            cell_a.font = Font(bold=True, size=13)
        else:
            cell_b.alignment = Alignment(horizontal='right')

    # ── Sheet 2: PRE Dinas Detail ─────────────────────────────────────────
    ws_pre = wb.create_sheet('PRE Dinas Detail')
    if not pre_detail.empty:
        _write_sheet_df(ws_pre, pre_detail, FILL_BLUE,
                        title=f'PRE-Periode: Dinas-Rechnungen (gematcht via RN) — {len(pre_detail)} Zeilen')
    else:
        ws_pre.append(['Keine gematchten Zeilen gefunden.'])

    # ── Sheet 3: POST AX Detail ───────────────────────────────────────────
    ws_post = wb.create_sheet('POST AX Detail')
    if not post_detail.empty:
        _write_sheet_df(ws_post, post_detail, FILL_ORANGE,
                        title=f'POST-Periode: AX-Abrechnung — {len(post_detail)} Zeilen')
    else:
        ws_post.append(['Keine POST-Zeilen gefunden.'])

    wb.save(str(out_path))
    print(f'  → Gespeichert: {out_path}')


# ══════════════════════════════════════════════════════════════════════════
# Hauptprogramm
# ══════════════════════════════════════════════════════════════════════════
def main():
    print('=== Dinas PDF Vergleich — Alle Kunden (Step C) ===\n')

    bi_df = load_bi()
    print(f'BI-Daten geladen: {len(bi_df):,} Zeilen\n')

    results = []

    for knr, info in CUSTOMERS.items():
        print('-' * 60)
        print(f'  {info["name"]} (KNR {knr})')
        print('-' * 60)

        pdf_dir = info['pdf_dir']
        if not pdf_dir.exists():
            print(f'  WARNUNG: PDF-Verzeichnis nicht gefunden: {pdf_dir}')
            dinas_df = pd.DataFrame()
        else:
            dinas_df = load_or_parse(knr, pdf_dir)

        # PRE / POST Detail
        pre_detail  = build_pre_detail(bi_df, dinas_df, knr)
        post_detail = build_post_detail(bi_df, knr)

        print(f'  PRE: {len(bi_df[(bi_df["Kunden Nr BK"]==knr) & (bi_df["periode"]=="PRE")]):4d} BI-Zeilen  '
              f'→  {len(pre_detail):4d} gematchte Dinas-Zeilen')
        print(f'  POST: {len(post_detail):4d} AX-Zeilen')

        # NK-Summaries
        if not pre_detail.empty and 'Dinas Fracht' in pre_detail.columns:
            print(f'  Σ Dinas Fracht: {pre_detail["Dinas Fracht"].sum():>10,.2f} EUR'
                  f'  |  Σ Dinas Gesamt: {pre_detail.get("Dinas Gesamt", pd.Series([0])).sum():>10,.2f} EUR')
        if not post_detail.empty:
            ax_f = pd.to_numeric(post_detail.get('AX Fracht', pd.Series([])), errors='coerce').sum()
            ax_g = pd.to_numeric(post_detail.get('AX Gesamt', pd.Series([])), errors='coerce').sum()
            print(f'  Σ AX Fracht:    {ax_f:>10,.2f} EUR'
                  f'  |  Σ AX Gesamt:    {ax_g:>10,.2f} EUR')

        # Zusammenfassung bauen
        zs = build_zusammenfassung(knr, info, bi_df, dinas_df, pre_detail, post_detail)

        # Output-Pfad
        out_path = OUT_DIR / f'{info["short"]}_dinas_vergleich.xlsx'
        write_excel(knr, info, zs, pre_detail, post_detail, out_path)
        print()

        results.append({
            'KNR'         : knr,
            'Kunde'       : info['name'],
            'n_PDFs'      : len(dinas_df),
            'PRE_BI'      : len(bi_df[(bi_df['Kunden Nr BK']==knr) & (bi_df['periode']=='PRE')]),
            'Matched'     : len(pre_detail),
            'POST_BI'     : len(post_detail),
            'Σ_Dinas_Fracht': pre_detail['Dinas Fracht'].sum() if not pre_detail.empty and 'Dinas Fracht' in pre_detail.columns else 0,
            'Σ_AX_Fracht' : pd.to_numeric(post_detail.get('AX Fracht', pd.Series([])), errors='coerce').sum() if not post_detail.empty else 0,
        })

    # ── Gesamtübersicht ───────────────────────────────────────────────────
    print('═'*60)
    print('GESAMTÜBERSICHT')
    print('═'*60)
    summary_df = pd.DataFrame(results)
    print(summary_df[['Kunde', 'n_PDFs', 'PRE_BI', 'Matched', 'POST_BI',
                       'Σ_Dinas_Fracht', 'Σ_AX_Fracht']].to_string(index=False))
    print()

    # ── Gesamt-Excel ──────────────────────────────────────────────────────
    gesamt_path = OUT_DIR / 'alle_kunden_dinas_vergleich.xlsx'
    with pd.ExcelWriter(gesamt_path, engine='openpyxl') as writer:
        summary_df.to_excel(writer, sheet_name='Übersicht', index=False)
    print(f'Gesamtübersicht: {gesamt_path}')


if __name__ == '__main__':
    main()
