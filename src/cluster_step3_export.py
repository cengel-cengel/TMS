#!/usr/bin/env python3
"""
cluster_step3_export.py
=======================
Schritt 3: Liest cluster_samples.csv (aus Schritt 2) und
schreibt das Sheet "Cluster-Vergleich" in geze_dinas_vergleich.xlsx.

Eingabe:  output/geze_cluster_stats.csv
          output/geze_cluster_samples.csv
Ausgabe:  output/geze_dinas_vergleich.xlsx  (neues Sheet eingefügt)
"""

from pathlib import Path

import numpy as np
import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

XLSX         = Path('/home/user/TMS/output/geze_dinas_vergleich.xlsx')
STATS_CSV    = Path('/home/user/TMS/output/geze_cluster_stats.csv')
SAMPLES_CSV  = Path('/home/user/TMS/output/geze_cluster_samples.csv')

# ── Farben & Stile ─────────────────────────────────────────────────────────────
def fill(hex_): return PatternFill('solid', fgColor=hex_)
def font(bold=False, color='000000', size=9, italic=False):
    return Font(bold=bold, color=color, size=size, italic=italic)

FILL_TITLE    = fill('1F497D')
FILL_CLUSTER  = fill('2E75B6')
FILL_STATS    = fill('D6E4F7')
FILL_PRE_HDR  = fill('4472C4')
FILL_PRE      = fill('BDD7EE')
FILL_POST_HDR = fill('C55A11')
FILL_POST     = fill('FCE4D6')
FILL_CTRL     = fill('E2EFDA')

THIN   = Side(border_style='thin',   color='AAAAAA')
MEDIUM = Side(border_style='medium', color='555555')
BRD    = Border(left=THIN, right=THIN, top=THIN,   bottom=THIN)
BRD_H  = Border(left=THIN, right=THIN, top=MEDIUM, bottom=MEDIUM)

EUR = '#,##0.00'
PCT = '+0.0%;-0.0%;0.0%'

# ── Spalten-Layout ─────────────────────────────────────────────────────────────
# (display_header, pre_src_col, post_src_col, width)
# Wo post_src_col=None → Zelle bleibt leer für POST-Zeilen
COLS = [
    ('RN',          'Rechnungsnummer',          'Rechnungsnummer',    11),
    ('Auftrag',     'Auftragsnummer',            'Auftragsnummer',     12),
    ('Datum',       'Leistungsdatum',            'Leistungsdatum',     11),
    ('Empfänger',   'Empfänger Name',            'Empfänger Name',     22),
    ('PLZ',         'Empfänger PLZ',             'Empfänger PLZ',       7),
    ('Ton. kg',     'Tonnage (eff.)',             'Tonnage (eff.)',       8),
    ('Soll €',      'Soll EUR',                  'Soll EUR',            9),
    # NK — PRE: Dinas-Labels / POST: AX-Labels
    ('Fracht €',    'Dinas Fracht',              'AX Fracht',          10),
    ('Diesel €',    'Dinas Diesel',              'AX Diesel',           9),
    ('Maut/SSD €',  'Dinas Maut/SSD',            'AX Maut',             9),
    ('Ausfuhr €',   'Dinas Ausfuhr',             'AX Nebengebühr',      9),
    ('Verzoll. €',  'Dinas Verzollung',           'AX Lademittel',       9),
    ('ZollD. €',    'Dinas Zoll Duty',            'AX Peak',             8),
    ('Sulphur €',   'Dinas Sulphur',              'AX EUST/Zoll',        9),
    ('NKPausch. €', 'Dinas Nebenkostenpausch.',   'AX Versicherung',    10),
    ('Redebit €',   'Dinas Redebit',              None,                  8),
    ('Sonstige €',  'Dinas Sonstige',             None,                  8),
    ('GESAMT €',    'Dinas Gesamt',               'AX Gesamt',          11),
]
N_COLS = len(COLS)

# PRE-spezifische Header-Labels (Spalten 8-18 umbenennen)
PRE_HDR_OVERRIDE = {
    8:  'Dinas Fracht €', 9:  'Dinas Diesel €', 10: 'Dinas Maut €',
    11: 'Dinas Ausfuhr €', 12: 'Dinas Verzoll. €', 13: 'Dinas ZollD. €',
    14: 'Dinas Sulphur €', 15: 'Dinas NKPausch. €', 16: 'Dinas Redebit €',
    17: 'Dinas Sonstige €', 18: 'Dinas GESAMT €',
}
POST_HDR_OVERRIDE = {
    8:  'AX Fracht €', 9:  'AX Diesel €', 10: 'AX Maut €',
    11: 'AX Nebengebühr €', 12: 'AX Lademittel €', 13: 'AX Peak €',
    14: 'AX EUST/Zoll €', 15: 'AX Versich. €', 16: '', 17: '',
    18: 'AX GESAMT €',
}

# ── Hilfsfunktionen ────────────────────────────────────────────────────────────
def wc(ws, row, col, value=None, f=None, fnt=None,
        al='left', fmt=None, brd=None):
    cell = ws.cell(row=row, column=col)
    if value is not None:
        cell.value = value
    if f:   cell.fill      = f
    if fnt: cell.font      = fnt
    if fmt: cell.number_format = fmt
    if brd: cell.border    = brd
    cell.alignment = Alignment(horizontal=al, vertical='center')
    return cell

def merge_row(ws, row, c1, c2, val, f=None, fnt=None, al='left'):
    ws.merge_cells(start_row=row, start_column=c1,
                   end_row=row,   end_column=c2)
    wc(ws, row, c1, val, f, fnt, al)

def write_col_headers(ws, row, override, hdr_fill):
    for ci, (hdr, _, _, _) in enumerate(COLS, start=1):
        label = override.get(ci, hdr)
        wc(ws, row, ci, label, hdr_fill,
           font(bold=True, color='FFFFFF', size=8), 'center', brd=BRD_H)

def write_data_row(ws, row, src_row, src_col_idx, row_fill):
    """Schreibt eine Datenzeile; src_col_idx = 2 (pre_src) oder 3 (post_src)."""
    for ci, col_def in enumerate(COLS, start=1):
        src_col = col_def[src_col_idx]
        val     = src_row.get(src_col) if src_col else None
        if val is not None and pd.isna(val):
            val = None
        hdr  = col_def[0]
        is_eur = '€' in hdr
        fmt  = EUR if is_eur else None
        al   = 'right' if is_eur or hdr == 'Ton. kg' else 'left'
        wc(ws, row, ci, val, row_fill, font(size=9), al, fmt, BRD)

# ── Hauptfunktion ──────────────────────────────────────────────────────────────
def write_sheet(ws, stats: pd.DataFrame, samples: pd.DataFrame, top_n: int = 20):
    ws.title = 'Cluster-Vergleich'

    # Titelzeile
    merge_row(ws, 1, 1, N_COLS,
              'GEZE GmbH (406035) — Cluster-Vergleich mit vollständiger NK-Aufschlüsselung',
              fill('1F497D'), font(bold=True, color='FFFFFF', size=13), 'center')
    merge_row(ws, 2, 1, N_COLS,
              'PRE: Dinas NK-Positionen  |  POST: AX NK-Positionen  |  '
              'Soll EUR aus Tarifmotor  |  Grün = Kontroll-Sendung (bestes PRE/POST-Paar)',
              fill('2E4057'), font(color='CCCCCC', size=9, italic=True), 'center')

    row = 2

    for _, cl in stats.head(top_n).iterrows():
        ckey     = cl['_cluster']
        land     = cl.get('Land', '')
        plz_p    = cl.get('PLZ_pre', '')
        gwb      = cl.get('Gew_band', '')
        n_pre    = int(cl.get('n_pre', 0))
        n_post   = int(cl.get('n_post', 0))
        avg_d    = cl.get('avg_dinas_ges', 0)
        avg_a    = cl.get('avg_ax_ges', 0)
        delta    = cl.get('delta_ges', 0)
        pct      = cl.get('delta_pct', 0)
        est      = cl.get('total_loss_est', 0)
        abw      = cl.get('abw_grund', '')

        clus_rows = samples[samples['_cluster'] == ckey]
        pre_rows  = clus_rows[clus_rows['_system'] == 'PRE']
        post_rows = clus_rows[clus_rows['_system'] == 'POST']
        kpre_rows = clus_rows[clus_rows['_system'] == 'KONTROLL_PRE']
        kpost_rows= clus_rows[clus_rows['_system'] == 'KONTROLL_POST']

        # ── Cluster-Header ────────────────────────────────────────────────────
        row += 1
        merge_row(ws, row, 1, N_COLS,
                  f'  CLUSTER: Land={land}  |  PLZ-Prefix={plz_p}  |  Gew.band={gwb}  '
                  f'|  n PRE={n_pre}  |  n POST={n_post}',
                  FILL_CLUSTER, font(bold=True, color='FFFFFF', size=10))
        row += 1
        merge_row(ws, row, 1, N_COLS,
                  f'  Ø Dinas Gesamt: {avg_d:,.2f} €  |  Ø AX Gesamt: {avg_a:,.2f} €  '
                  f'|  Δ: {delta:,.2f} € ({pct:+.1f}%)  '
                  f'|  Gesch. Gesamtverlust: {est:,.0f} €  |  {abw}',
                  FILL_STATS, font(size=9))

        # ── PRE (Dinas) ───────────────────────────────────────────────────────
        row += 1
        merge_row(ws, row, 1, N_COLS, '  PRE — Dinas Rechnungen (NK-Aufschlüsselung)',
                  FILL_PRE_HDR, font(bold=True, color='FFFFFF'))
        row += 1
        write_col_headers(ws, row, PRE_HDR_OVERRIDE, FILL_PRE_HDR)
        for _, pr in pre_rows.iterrows():
            row += 1
            write_data_row(ws, row, pr, 1, FILL_PRE)   # src_col_idx=1 → pre_src

        # ── POST (AX) ─────────────────────────────────────────────────────────
        row += 1
        merge_row(ws, row, 1, N_COLS, '  POST — AX Rechnungen (NK-Aufschlüsselung)',
                  FILL_POST_HDR, font(bold=True, color='FFFFFF'))
        row += 1
        write_col_headers(ws, row, POST_HDR_OVERRIDE, FILL_POST_HDR)
        for _, po in post_rows.iterrows():
            row += 1
            write_data_row(ws, row, po, 2, FILL_POST)  # src_col_idx=2 → post_src

        # ── Kontroll-Sendung ──────────────────────────────────────────────────
        if not kpre_rows.empty or not kpost_rows.empty:
            row += 1
            merge_row(ws, row, 1, N_COLS,
                      '  ★ Kontroll-Sendung — bestes PRE/POST-Paar (gleicher Empfänger, ähnl. Gewicht)',
                      FILL_CTRL, font(bold=True, color='1F5C00'))
            if not kpre_rows.empty:
                row += 1
                wc(ws, row, 1, 'PRE', FILL_CTRL, font(bold=True, italic=True))
                pr = kpre_rows.iloc[0]
                for ci, col_def in enumerate(COLS[1:], start=2):
                    src = col_def[1]
                    val = pr.get(src) if src else None
                    if val is not None and pd.isna(val): val = None
                    is_eur = '€' in col_def[0]
                    wc(ws, row, ci, val, FILL_CTRL, font(size=9),
                       'right' if is_eur else 'left',
                       EUR if is_eur else None, BRD)
            if not kpost_rows.empty:
                row += 1
                wc(ws, row, 1, 'POST', FILL_CTRL, font(bold=True, italic=True))
                po = kpost_rows.iloc[0]
                for ci, col_def in enumerate(COLS[1:], start=2):
                    src = col_def[2]
                    val = po.get(src) if src else None
                    if val is not None and pd.isna(val): val = None
                    is_eur = '€' in col_def[0]
                    wc(ws, row, ci, val, FILL_CTRL, font(size=9),
                       'right' if is_eur else 'left',
                       EUR if is_eur else None, BRD)

        row += 1   # Leerzeile zwischen Clustern

    # Spaltenbreiten
    for ci, (_, _, _, w) in enumerate(COLS, start=1):
        ws.column_dimensions[get_column_letter(ci)].width = w
    ws.row_dimensions[1].height = 22
    ws.freeze_panes = 'A3'

    return row


# ══════════════════════════════════════════════════════════════════════════════
def main():
    stats   = pd.read_csv(STATS_CSV,   sep=';')
    samples = pd.read_csv(SAMPLES_CSV, sep=';')

    print(f'Cluster:  {len(stats)}')
    print(f'Samples:  {len(samples)} Zeilen '
          f'({(samples["_system"]=="PRE").sum()} PRE, '
          f'{(samples["_system"]=="POST").sum()} POST, '
          f'{(samples["_system"].str.startswith("KONTROLL")).sum()} Kontroll)')

    wb = load_workbook(XLSX)
    if 'Cluster-Vergleich' in wb.sheetnames:
        del wb['Cluster-Vergleich']
    ws = wb.create_sheet('Cluster-Vergleich', 1)

    last_row = write_sheet(ws, stats, samples, top_n=20)
    wb.save(XLSX)

    print(f'\nSheet "Cluster-Vergleich" geschrieben ({last_row} Zeilen)')
    print(f'Datei: {XLSX}')


if __name__ == '__main__':
    main()
