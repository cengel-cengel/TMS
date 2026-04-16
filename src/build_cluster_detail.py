#!/usr/bin/env python3
"""
build_cluster_detail.py  — Schritt 1/3
=======================================
Liest geze_dinas_vergleich.xlsx (PRE Dinas Detail + POST AX Detail),
bildet Cluster (Land + PLZ-Prefix + Gewichtsband), identifiziert
Unterfakturierung (AX < Dinas) und schreibt ein neues Sheet
"Cluster-Vergleich" in die bestehende Datei.

Noch KEINE NK-Aufschlüsselung — nur die Grundstruktur.
"""

import math
from pathlib import Path

import numpy as np
import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import (
    Alignment, Border, Font, PatternFill, Side
)
from openpyxl.utils import get_column_letter

XLSX = Path('/home/user/TMS/output/geze_dinas_vergleich.xlsx')

# ── Gewichtsbänder (GEZE: EUR/100kg-Tarif) ───────────────────────────────────
BANDS_KG = [50, 100, 150, 200, 250, 300, 500, 750, 1000, 2000, 3000]

def gew_band(kg) -> str:
    try:
        kg = float(kg)
    except (TypeError, ValueError):
        return '?'
    if math.isnan(kg) or kg <= 0:
        return '?'
    for b in BANDS_KG:
        if kg <= b:
            return f'bis {b}kg'
    return 'über 3000kg'


def plz_prefix(plz, n: int = 2) -> str:
    """Erste n Zeichen der PLZ (als String)."""
    s = str(plz).strip()
    return s[:n] if len(s) >= n else s


# ── Daten laden ───────────────────────────────────────────────────────────────
def load_sheets() -> tuple[pd.DataFrame, pd.DataFrame]:
    pre  = pd.read_excel(XLSX, sheet_name='PRE Dinas Detail',  header=2)
    post = pd.read_excel(XLSX, sheet_name='POST AX Detail',    header=2)

    for df in (pre, post):
        df['Tonnage (eff.)'] = pd.to_numeric(df['Tonnage (eff.)'], errors='coerce')
        df['Empfänger PLZ']  = df['Empfänger PLZ'].astype(str).str.strip()
        df['Empfänger Land'] = df['Empfänger Land'].astype(str).str.strip()

    pre['_gew_band'] = pre['Tonnage (eff.)'].apply(gew_band)
    pre['_plz_pre']  = pre['Empfänger PLZ'].apply(plz_prefix)
    pre['_cluster']  = (pre['Empfänger Land'] + '|'
                        + pre['_plz_pre']     + '|'
                        + pre['_gew_band'])

    post['_gew_band'] = post['Tonnage (eff.)'].apply(gew_band)
    post['_plz_pre']  = post['Empfänger PLZ'].apply(plz_prefix)
    post['_cluster']  = (post['Empfänger Land'] + '|'
                         + post['_plz_pre']      + '|'
                         + post['_gew_band'])

    pre['Dinas Gesamt'] = pd.to_numeric(pre['Dinas Gesamt'], errors='coerce')
    pre['Dinas Fracht'] = pd.to_numeric(pre['Dinas Fracht'], errors='coerce')
    post['AX Gesamt']   = pd.to_numeric(post['AX Gesamt'],  errors='coerce')
    post['AX Fracht']   = pd.to_numeric(post['AX Fracht'],  errors='coerce')

    return pre, post


# ── Cluster-Statistiken ───────────────────────────────────────────────────────
def build_cluster_stats(pre: pd.DataFrame,
                         post: pd.DataFrame) -> pd.DataFrame:
    pre_stats = (
        pre.groupby('_cluster')
        .agg(
            n_pre          = ('Dinas Gesamt', 'count'),
            avg_dinas_ges  = ('Dinas Gesamt', 'mean'),
            sum_dinas_ges  = ('Dinas Gesamt', 'sum'),
            avg_dinas_fr   = ('Dinas Fracht', 'mean'),
        )
        .reset_index()
    )

    post_stats = (
        post.groupby('_cluster')
        .agg(
            n_post       = ('AX Gesamt',  'count'),
            avg_ax_ges   = ('AX Gesamt',  'mean'),
            sum_ax_ges   = ('AX Gesamt',  'sum'),
            avg_ax_fr    = ('AX Fracht',  'mean'),
        )
        .reset_index()
    )

    stats = pre_stats.merge(post_stats, on='_cluster', how='inner')

    # Nur Cluster mit Unterfakturierung: Ø AX Gesamt < Ø Dinas Gesamt
    stats = stats[stats['avg_ax_ges'] < stats['avg_dinas_ges']].copy()

    stats['delta_ges']     = stats['avg_ax_ges'] - stats['avg_dinas_ges']
    stats['delta_pct']     = stats['delta_ges'] / stats['avg_dinas_ges'].replace(0, np.nan) * 100
    stats['total_loss_est'] = stats['delta_ges'] * stats['n_post']   # Hochrechnung auf POST-Zeilen

    # Land + PLZ + Band aus Cluster-Key
    parts = stats['_cluster'].str.split('|', expand=True)
    stats['Land']     = parts[0]
    stats['PLZ_pre']  = parts[1]
    stats['Gew.band'] = parts[2]

    # Sortierung: größter geschätzter Verlust zuerst
    stats = stats.sort_values('total_loss_est').reset_index(drop=True)

    return stats


# ── Kontroll-Sendung finden ────────────────────────────────────────────────────
def find_kontroll(pre_rows: pd.DataFrame,
                  post_rows: pd.DataFrame) -> tuple[pd.Series | None, pd.Series | None]:
    """
    Versucht, ein PRE-POST-Paar mit gleichem Empfänger + ähnlichem Gewicht zu finden.
    Liefert (pre_row, post_row) oder (None, None).
    """
    if pre_rows.empty or post_rows.empty:
        return None, None

    best_pre, best_post, best_diff = None, None, float('inf')

    for _, pr in pre_rows.iterrows():
        same_name = post_rows[
            post_rows['Empfänger Name'].astype(str).str[:12]
            == str(pr['Empfänger Name'])[:12]
        ]
        candidates = same_name if not same_name.empty else post_rows
        for _, po in candidates.iterrows():
            try:
                diff = abs(float(pr['Tonnage (eff.)']) - float(po['Tonnage (eff.)']))
                if diff < best_diff:
                    best_diff, best_pre, best_post = diff, pr, po
            except (TypeError, ValueError):
                continue

    return best_pre, best_post


# ── Excel-Formatierung ─────────────────────────────────────────────────────────
THIN     = Side(border_style='thin',   color='AAAAAA')
THICK    = Side(border_style='medium', color='444444')
BORDER_T = Border(left=THIN, right=THIN, top=THIN,  bottom=THIN)
BORDER_H = Border(left=THIN, right=THIN, top=THICK, bottom=THICK)

FILL_HDR      = PatternFill('solid', fgColor='1F497D')   # dunkles Blau — Sheet-Header
FILL_CLUSTER  = PatternFill('solid', fgColor='2E75B6')   # Blau — Cluster-Block-Header
FILL_STATS    = PatternFill('solid', fgColor='D6E4F7')   # Hellblau — Statistik-Zeile
FILL_PRE_HDR  = PatternFill('solid', fgColor='4472C4')   # Mittelblau — PRE Spaltenheader
FILL_PRE      = PatternFill('solid', fgColor='BDD7EE')   # Hellblau — PRE Daten
FILL_POST_HDR = PatternFill('solid', fgColor='C55A11')   # Orange — POST Spaltenheader
FILL_POST     = PatternFill('solid', fgColor='FCE4D6')   # Hellorange — POST Daten
FILL_CTRL     = PatternFill('solid', fgColor='E2EFDA')   # Hellgrün — Kontroll-Sendung

FONT_WH   = Font(bold=True, color='FFFFFF', size=10)
FONT_BK   = Font(bold=True, color='000000', size=10)
FONT_BOLD = Font(bold=True, size=9)
FONT_NORM = Font(size=9)

def _c(ws, row, col, value=None, fill=None, font=None,
        align='left', number_format=None, border=None):
    cell = ws.cell(row=row, column=col)
    if value is not None:
        cell.value = value
    if fill:
        cell.fill = fill
    if font:
        cell.font = font
    cell.alignment = Alignment(horizontal=align, vertical='center',
                                wrap_text=False)
    if number_format:
        cell.number_format = number_format
    if border:
        cell.border = border
    return cell

def _merge_row(ws, row, col_start, col_end, value,
               fill=None, font=None, align='left'):
    ws.merge_cells(start_row=row, start_column=col_start,
                   end_row=row,   end_column=col_end)
    _c(ws, row, col_start, value, fill, font, align)

EUR_FMT = '#,##0.00'
PCT_FMT = '+0.0%;-0.0%;0.0%'


# ── Spalten-Definitionen ───────────────────────────────────────────────────────
PRE_COLS = [
    ('RN',          'Rechnungsnummer',   10),
    ('Auftrag',     'Auftragsnummer',    12),
    ('Datum',       'Leistungsdatum',    11),
    ('Empfänger',   'Empfänger Name',    22),
    ('PLZ',         'Empfänger PLZ',      7),
    ('Tonnage kg',  'Tonnage (eff.)',      9),
    ('Dinas Ges. €','Dinas Gesamt',      12),
    ('Dinas Fr. €', 'Dinas Fracht',      11),
]

POST_COLS = [
    ('RN',          'Rechnungsnummer',   10),
    ('Auftrag',     'Auftragsnummer',    12),
    ('Datum',       'Leistungsdatum',    11),
    ('Empfänger',   'Empfänger Name',    22),
    ('PLZ',         'Empfänger PLZ',      7),
    ('Tonnage kg',  'Tonnage (eff.)',      9),
    ('AX Ges. €',   'AX Gesamt',         12),
    ('AX Fr. €',    'AX Fracht',         11),
    ('AX Diesel €', 'AX Diesel',         10),
    ('AX Maut €',   'AX Maut',            9),
]

N_COL = len(POST_COLS)   # POST has more cols — determines sheet width


def write_cluster_sheet(ws, clusters: pd.DataFrame,
                         pre: pd.DataFrame, post: pd.DataFrame,
                         top_n: int = 20):
    ws.title = 'Cluster-Vergleich'

    # ── Titelzeile ────────────────────────────────────────────────────────────
    _merge_row(ws, 1, 1, N_COL,
               'GEZE GmbH (406035) — Cluster-Vergleich: Unterfakturierung AX vs Dinas',
               FILL_HDR, Font(bold=True, color='FFFFFF', size=13), 'center')
    _merge_row(ws, 2, 1, N_COL,
               f'Top-{min(top_n, len(clusters))} Cluster nach geschätztem Gesamtverlust '
               f'(nur Cluster mit Ø AX Gesamt < Ø Dinas Gesamt)',
               PatternFill('solid', fgColor='2E4057'),
               Font(color='DDDDDD', size=9, italic=True), 'center')
    row = 3

    shown = 0
    for _, stat in clusters.head(top_n).iterrows():
        cluster_key = stat['_cluster']
        land   = stat['Land']
        plz_p  = stat['PLZ_pre']
        gwb    = stat['Gew.band']
        n_pre  = int(stat['n_pre'])
        n_post = int(stat['n_post'])
        avg_d  = stat['avg_dinas_ges']
        avg_a  = stat['avg_ax_ges']
        delta  = stat['delta_ges']
        pct    = stat['delta_pct']
        est    = stat['total_loss_est']

        # ── Cluster-Block-Header ──────────────────────────────────────────────
        row += 1
        _merge_row(ws, row, 1, N_COL,
                   f'  CLUSTER:  Land={land}  |  PLZ-Prefix={plz_p}  |  Gew.band={gwb}',
                   FILL_CLUSTER, Font(bold=True, color='FFFFFF', size=10))
        row += 1
        _merge_row(ws, row, 1, N_COL,
                   (f'  n PRE={n_pre}  |  n POST={n_post}  '
                    f'|  Ø Dinas Gesamt={avg_d:,.2f} €  '
                    f'|  Ø AX Gesamt={avg_a:,.2f} €  '
                    f'|  Δ={delta:,.2f} €  ({pct:+.1f}%)  '
                    f'|  Gesch. Gesamtverlust={est:,.0f} €'),
                   FILL_STATS, Font(size=9))

        # ── PRE-Zeilen ────────────────────────────────────────────────────────
        row += 1
        _merge_row(ws, row, 1, N_COL, '  PRE — Dinas (Sendungen)',
                   FILL_PRE_HDR, Font(bold=True, color='FFFFFF', size=9))
        row += 1
        for ci, (hdr, _, _) in enumerate(PRE_COLS, start=1):
            _c(ws, row, ci, hdr, FILL_PRE_HDR,
               Font(bold=True, color='FFFFFF', size=8), 'center', border=BORDER_H)

        pre_rows = pre[pre['_cluster'] == cluster_key].head(5)
        for _, pr in pre_rows.iterrows():
            row += 1
            vals = [pr.get(col) for _, col, _ in PRE_COLS]
            for ci, (v, (hdr, _, _)) in enumerate(zip(vals, PRE_COLS), start=1):
                is_eur = '€' in hdr
                fmt    = EUR_FMT if is_eur else None
                al     = 'right' if is_eur or hdr in ('Tonnage kg',) else 'left'
                _c(ws, row, ci, v if not pd.isna(v) else None,
                   FILL_PRE, FONT_NORM, al, fmt, BORDER_T)

        # ── POST-Zeilen ───────────────────────────────────────────────────────
        row += 1
        _merge_row(ws, row, 1, N_COL, '  POST — AX (Sendungen)',
                   FILL_POST_HDR, Font(bold=True, color='FFFFFF', size=9))
        row += 1
        for ci, (hdr, _, _) in enumerate(POST_COLS, start=1):
            _c(ws, row, ci, hdr, FILL_POST_HDR,
               Font(bold=True, color='FFFFFF', size=8), 'center', border=BORDER_H)

        post_rows = post[post['_cluster'] == cluster_key].head(5)
        for _, po in post_rows.iterrows():
            row += 1
            vals = [po.get(col) for _, col, _ in POST_COLS]
            for ci, (v, (hdr, _, _)) in enumerate(zip(vals, POST_COLS), start=1):
                is_eur = '€' in hdr
                fmt    = EUR_FMT if is_eur else None
                al     = 'right' if is_eur or hdr == 'Tonnage kg' else 'left'
                _c(ws, row, ci, v if not pd.isna(v) else None,
                   FILL_POST, FONT_NORM, al, fmt, BORDER_T)

        # ── Kontroll-Sendung ──────────────────────────────────────────────────
        ctrl_pre, ctrl_post = find_kontroll(pre_rows, post_rows)
        if ctrl_pre is not None and ctrl_post is not None:
            row += 1
            _merge_row(ws, row, 1, N_COL,
                       f'  ★ Kontroll-Sendung — gleicher/ähnlicher Empfänger '
                       f'(PRE vs POST, Tonnage-Differenz: '
                       f'{abs(float(ctrl_pre["Tonnage (eff.)"]) - float(ctrl_post["Tonnage (eff.)"])):,.0f} kg)',
                       FILL_CTRL, Font(bold=True, size=9, color='1F5C00'))
            # PRE Kontroll
            row += 1
            _c(ws, row, 1, 'PRE', FILL_CTRL, Font(bold=True, size=9, italic=True))
            for ci, (hdr, src, _) in enumerate(PRE_COLS[1:], start=2):
                v   = ctrl_pre.get(src)
                fmt = EUR_FMT if '€' in hdr else None
                al  = 'right' if '€' in hdr or hdr == 'Tonnage kg' else 'left'
                _c(ws, row, ci, v if not pd.isna(v) else None,
                   FILL_CTRL, FONT_NORM, al, fmt, BORDER_T)
            # POST Kontroll
            row += 1
            _c(ws, row, 1, 'POST', FILL_CTRL, Font(bold=True, size=9, italic=True))
            for ci, (hdr, src, _) in enumerate(POST_COLS[1:], start=2):
                v   = ctrl_post.get(src)
                fmt = EUR_FMT if '€' in hdr else None
                al  = 'right' if '€' in hdr or hdr == 'Tonnage kg' else 'left'
                _c(ws, row, ci, v if not pd.isna(v) else None,
                   FILL_CTRL, FONT_NORM, al, fmt, BORDER_T)

        shown += 1

    # ── Spaltenbreiten setzen ─────────────────────────────────────────────────
    widths = [w for _, _, w in POST_COLS]
    for ci, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(ci)].width = w

    # Erste Spalte etwas breiter für Labels
    ws.row_dimensions[1].height = 22
    ws.freeze_panes = 'A4'

    return shown


# ══════════════════════════════════════════════════════════════════════════════
def main():
    print('=== GEZE Cluster-Vergleich (Schritt 1/3) ===\n')

    pre, post = load_sheets()
    print(f'PRE Dinas: {len(pre)} Zeilen  |  POST AX: {len(post)} Zeilen')

    clusters = build_cluster_stats(pre, post)
    print(f'\nCluster mit Unterfakturierung (AX < Dinas): {len(clusters)}')
    print()

    # Vorschau Top-10
    preview = clusters[['Land','PLZ_pre','Gew.band','n_pre','n_post',
                         'avg_dinas_ges','avg_ax_ges','delta_ges',
                         'delta_pct','total_loss_est']].head(10)
    preview.columns = ['Land','PLZ','Band','nPRE','nPOST',
                        'Ø Dinas €','Ø AX €','Δ €','Δ %','Est.Verlust €']
    print(preview.round(2).to_string(index=False))
    print(f'\n  Σ geschätzter Gesamtverlust: {clusters["total_loss_est"].sum():,.0f} EUR')
    print()

    # Existierende Datei laden + neues Sheet einfügen
    wb = load_workbook(XLSX)

    # Altes Sheet entfernen falls vorhanden
    if 'Cluster-Vergleich' in wb.sheetnames:
        del wb['Cluster-Vergleich']

    # Neues Sheet an Position 1 (nach Zusammenfassung)
    ws = wb.create_sheet('Cluster-Vergleich', 1)

    n_shown = write_cluster_sheet(ws, clusters, pre, post, top_n=20)

    wb.save(XLSX)
    print(f'Sheet "Cluster-Vergleich" mit {n_shown} Clustern gespeichert in:')
    print(f'  {XLSX}')


if __name__ == '__main__':
    main()
