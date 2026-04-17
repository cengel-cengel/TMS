"""
coverage_bi_vs_pdf.py v2 — PRE/POST split, Sendungsebene
Match: BI.Auftragsnummer <-> DINAS.sendungs_nr (PRE)
       BI.Auftragsnummer <-> AX-PDF.sendungs_nr  (POST, currently 0 PDFs)
"""
from pathlib import Path
import re
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

MIG = pd.Timestamp('2025-09-26')
OUT = Path('output/billing_report/00_coverage_bi_vs_pdf.xlsx')
OUT.parent.mkdir(exist_ok=True)

V1 = Path('data/extracted/v1/Noerpel AI')
V2 = Path('data/extracted/v2')
BI = Path('data/extracted/bi')

# (knrs, display_name, dinas_cache, ax_dir, extra_bi_cache)
CUSTOMERS = [
    ([406345],                          'Bitzer',          'output/dinas_cache_406345.pkl',      V1/'Bitzer/Rechnungen/Rechnungen AX',      None),
    ([409480],                          'Fischerwerke',    'output/dinas_cache_409480.pkl',       V2/'Fischer/Rechnungen/Rechnungen AX',     None),
    ([490085],                          'Hornschuch',      'output/dinas_cache_490085.pkl',       V1/'Hornschuch/Rechnungen/Rechnungen AX',  None),
    ([486073],                          'CHT Germany',     'output/dinas_cache_486073.pkl',       V1/'CHT/Rechnungen/Rechnungen AX',         None),
    ([410844],                          'EBM-Papst',       'output/dinas_cache_410844.pkl',       V1/'EBM/Rechnungen/Rechnungen AX',         None),
    ([423650],                          'HERMA',           'output/dinas_cache_423650.pkl',       BI/'Herma/Herma AX/Herma AX',             None),
    ([408244],                          'HELU KABEL',      'output/dinas_cache_408244.pkl',       V1/'Helu/Rechnungen/Rechnungen AX',        None),
    ([491063],                          'Sika Deutschland','output/dinas_cache_491063.pkl',       V1/'SIka/Rechnungen/Rechnungen AX',        None),
    ([406035],                          'GEZE',            'output/dinas_cache_406035.pkl',       V1/'GEZE/Rechnungen/Rechnungen AX',        None),
    ([410912, 490527, 527410, 527373],  'Groz-Beckert',    'output/dinas_cache_groz_beckert.pkl', V1/'Groz Beckert/Rechnungen/Rechnungen AX','output/bi_cache_groz_beckert.pkl'),
    ([511241],                          'SSC',             'output/dinas_cache_ssc_511241.pkl',   None,                                      None),
]

DETAIL_COLS = ['Auftragsnummer', 'Leistungsdatum', 'Rechnungsnummer',
               'Empfänger Land', 'Empfänger PLZ', 'Versender PLZ',
               'Tonnage (eff.)', 'Erlöse Fracht', 'Erloese']

def _norm(v):
    s = re.sub(r'\D', '', str(v)).lstrip('0')
    return s if s else str(v).strip()

def ax_snr_from_dir(ax_dir):
    """Extract sendungs_nr from AX PDF filenames (RECHNUNG<nr>.pdf → nr)."""
    if ax_dir is None or not Path(ax_dir).exists():
        return set()
    return {_norm(f.stem.replace('RECHNUNG', ''))
            for f in Path(ax_dir).glob('*.pdf')} - {'', '0', 'nan'}

# ── Load BI ──────────────────────────────────────────────────────────────────
print('Lade BI-Daten …')
bi_top20 = pd.read_pickle('output/bi_top20_data.pkl')['df']
bi_top20['Leistungsdatum'] = pd.to_datetime(bi_top20['Leistungsdatum'], errors='coerce')

def get_bi(knrs, extra_bi):
    if extra_bi and Path(extra_bi).exists():
        src = pd.read_pickle(extra_bi)
        src['Leistungsdatum'] = pd.to_datetime(src['Leistungsdatum'], errors='coerce')
    else:
        src = bi_top20
    return src[src['Kunden Nr BK'].isin(knrs)].copy()

# ── Styles ───────────────────────────────────────────────────────────────────
FILL_HDR   = PatternFill('solid', fgColor='1F497D')
FILL_PRE   = PatternFill('solid', fgColor='BDD7EE')
FILL_POST  = PatternFill('solid', fgColor='FCE4D6')
FILL_SECTN = PatternFill('solid', fgColor='2E75B6')
FILL_WARN  = PatternFill('solid', fgColor='FF0000')
FILL_OK    = PatternFill('solid', fgColor='E2EFDA')
THIN = Side(border_style='thin', color='CCCCCC')
BRD  = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

def _hdr_cell(ws, r, c, val, fill, bold=True, size=9, color='FFFFFF', wrap=False):
    cell = ws.cell(row=r, column=c, value=val)
    cell.fill = fill
    cell.font = Font(bold=bold, color=color, size=size)
    cell.border = BRD
    cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=wrap)
    return cell

def _data_cell(ws, r, c, val, fill=None, right=False, date=False, eur=False):
    cell = ws.cell(row=r, column=c, value=val)
    if fill: cell.fill = fill
    cell.font = Font(size=9)
    cell.border = BRD
    al = 'right' if (right or date or eur) else 'left'
    cell.alignment = Alignment(horizontal=al, vertical='center')
    if date and val: cell.number_format = 'DD.MM.YYYY'
    if eur:          cell.number_format = '#,##0.00'
    return cell

# ── Process + collect results ────────────────────────────────────────────────
summary_rows = []
detail_data  = {}   # name -> {'pre_unmatched': df, 'post_unmatched': df, 'stats': dict}

for knrs, name, dc_path, ax_dir, extra_bi in CUSTOMERS:
    knr_str = '+'.join(str(k) for k in knrs)
    bi_all  = get_bi(knrs, extra_bi)
    pre_bi  = bi_all[bi_all['Leistungsdatum'] <  MIG].copy()
    post_bi = bi_all[bi_all['Leistungsdatum'] >= MIG].copy()

    # DINAS sendungs_nr set (PRE)
    dinas_snr_set = set()
    if Path(dc_path).exists():
        dc = pd.read_pickle(dc_path)
        dinas_snr_set = set(dc['sendungs_nr'].astype(str).apply(_norm)) - {'', '0', 'nan'}

    # AX PDF sendungs_nr set (POST)
    ax_snr_set = ax_snr_from_dir(ax_dir)

    # Normalize BI Auftragsnummer
    pre_snr  = pre_bi['Auftragsnummer'].astype(str).apply(_norm)
    post_snr = post_bi['Auftragsnummer'].astype(str).apply(_norm)

    # Unique sendungs sets
    pre_snr_set  = set(pre_snr)  - {'', '0', 'nan'}
    post_snr_set = set(post_snr) - {'', '0', 'nan'}

    # Matches
    pre_matches  = len(pre_snr_set  & dinas_snr_set)
    post_matches = len(post_snr_set & ax_snr_set)

    pre_cov  = pre_matches  / len(pre_snr_set)  * 100 if pre_snr_set  else 0
    post_cov = post_matches / len(post_snr_set) * 100 if post_snr_set else 0

    # Unmatched BI rows for detail sheet
    pre_unmatched  = pre_bi[~pre_snr.isin(dinas_snr_set)].copy()
    post_unmatched = post_bi[~post_snr.isin(ax_snr_set)].copy()

    # Keep only needed columns (graceful missing)
    def _slim(df):
        cols = [c for c in DETAIL_COLS if c in df.columns]
        return df[cols].sort_values('Leistungsdatum', ascending=False) if 'Leistungsdatum' in cols else df[cols]

    pre_unmatched  = _slim(pre_unmatched)
    post_unmatched = _slim(post_unmatched)

    summary_rows.append({
        'Kunde':              name,
        'KNR':                knr_str,
        'PRE BI Sendungen':   len(pre_snr_set),
        'PRE PDF Sendungen':  len(dinas_snr_set),
        'PRE Matches':        pre_matches,
        'PRE Coverage %':     round(pre_cov, 1),
        'POST BI Sendungen':  len(post_snr_set),
        'POST PDF Sendungen': len(ax_snr_set),
        'POST Matches':       post_matches,
        'POST Coverage %':    round(post_cov, 1),
    })
    detail_data[name] = {
        'knr':           knr_str,
        'pre_unmatched': pre_unmatched,
        'post_unmatched':post_unmatched,
        'pre_total':     len(pre_snr_set),
        'post_total':    len(post_snr_set),
        'pre_matches':   pre_matches,
        'post_matches':  post_matches,
        'pre_cov':       pre_cov,
        'post_cov':      post_cov,
    }
    print(f'  {name:20s}  PRE {pre_matches:4d}/{len(pre_snr_set):5d} ({pre_cov:5.1f}%)  '
          f'POST {post_matches:4d}/{len(post_snr_set):5d} ({post_cov:5.1f}%)')

# ── Excel ────────────────────────────────────────────────────────────────────
wb = Workbook()
SUM_COLS = list(summary_rows[0].keys())

# ── Sheet 1: Zusammenfassung ─────────────────────────────────────────────────
ws = wb.active
ws.title = 'Zusammenfassung'
ws.freeze_panes = 'A3'

N = len(SUM_COLS)
ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=N)
c = ws.cell(row=1, column=1,
    value='Coverage-Analyse: BI-Sendungen vs PDF-Extraktion (Sendungsebene)  |  '
          'PRE = Dinas PDFs  |  POST = AX PDFs  |  Stichtag: 26.09.2025')
c.fill = FILL_HDR; c.font = Font(bold=True, color='FFFFFF', size=11)
c.alignment = Alignment(horizontal='center', vertical='center')
ws.row_dimensions[1].height = 22

# PRE / POST group headers
ws.merge_cells(start_row=2, start_column=3, end_row=2, end_column=6)
c = ws.cell(row=2, column=3, value='◀ PRE (DINAS-PDFs)')
c.fill = FILL_PRE; c.font = Font(bold=True, size=10); c.alignment = Alignment(horizontal='center')
ws.merge_cells(start_row=2, start_column=7, end_row=2, end_column=10)
c = ws.cell(row=2, column=7, value='POST (AX-PDFs) ▶')
c.fill = FILL_POST; c.font = Font(bold=True, size=10); c.alignment = Alignment(horizontal='center')

# Column headers row 3
HDR_LABELS = ['Kunde', 'KNR',
               'BI Sendungen', 'PDF Sendungen', 'Matches', 'Coverage %',
               'BI Sendungen', 'PDF Sendungen', 'Matches', 'Coverage %']
HDR_WIDTHS = [22, 20, 14, 14, 10, 12, 14, 14, 10, 12]
for ci, (lbl, w) in enumerate(zip(HDR_LABELS, HDR_WIDTHS), 1):
    fill = FILL_PRE if 3 <= ci <= 6 else (FILL_POST if 7 <= ci <= 10 else FILL_HDR)
    _hdr_cell(ws, 3, ci, lbl, fill, color='000000', wrap=True)
    ws.column_dimensions[get_column_letter(ci)].width = w
ws.row_dimensions[2].height = 14
ws.row_dimensions[3].height = 28

NUM_RIGHT_SUM = {3, 4, 5, 6, 7, 8, 9, 10}
for ri, row in enumerate(summary_rows, 4):
    pre_warn  = row['PRE Coverage %'] < 50
    post_warn = row['POST Coverage %'] < 50 and row['POST BI Sendungen'] > 0
    alt = PatternFill('solid', fgColor='EBF3FB') if ri % 2 == 0 else None
    for ci, key in enumerate(SUM_COLS, 1):
        v = row[key]
        is_pct = 'Coverage' in key
        cell_fill = alt
        if ci in (6,) and pre_warn:  cell_fill = FILL_WARN if pre_warn else FILL_OK
        if ci in (10,) and post_warn: cell_fill = FILL_WARN
        c = _data_cell(ws, ri, ci, v, cell_fill, right=(ci in NUM_RIGHT_SUM))
        if is_pct and isinstance(v, (int, float)):
            c.number_format = '0.0"%"'
            c.fill = (FILL_WARN if v < 50 else FILL_OK) if v is not None else c.fill

# ── Detail sheets per customer ───────────────────────────────────────────────
DETAIL_HDR = ['Auftragsnummer', 'Leistungsdatum', 'Rechnungsnummer',
              'Empf.Land', 'Empf.PLZ', 'Vers.PLZ',
              'Tonnage kg', 'Fracht EUR', 'Gesamt EUR']
DETAIL_WIDTHS = [16, 14, 16, 9, 9, 9, 11, 12, 12]
EUR_DET  = {8, 9}
DATE_DET = {2}
NUM_DET  = {7}

for name, d in detail_data.items():
    sheet_name = name[:28]  # max 31 chars
    ws2 = wb.create_sheet(sheet_name)
    ws2.freeze_panes = 'A2'

    # Title
    ncols = len(DETAIL_HDR)
    ws2.merge_cells(start_row=1, start_column=1, end_row=1, end_column=ncols)
    c = ws2.cell(row=1, column=1,
        value=f'{name} ({d["knr"]})  |  '
              f'PRE: {d["pre_matches"]}/{d["pre_total"]} Sendungen mit PDF ({d["pre_cov"]:.1f}%)  |  '
              f'POST: {d["post_matches"]}/{d["post_total"]} Sendungen mit PDF ({d["post_cov"]:.1f}%)')
    c.fill = FILL_HDR; c.font = Font(bold=True, color='FFFFFF', size=10)
    c.alignment = Alignment(horizontal='left', vertical='center')
    ws2.row_dimensions[1].height = 18
    for ci, (h, w) in enumerate(zip(DETAIL_HDR, DETAIL_WIDTHS), 1):
        ws2.column_dimensions[get_column_letter(ci)].width = w

    row = 1
    for section_label, df_sec, fill_sec in [
        (f'PRE — DINAS PDF fehlend: {len(d["pre_unmatched"])} Sendungen', d['pre_unmatched'], FILL_PRE),
        (f'POST — AX PDF fehlend: {len(d["post_unmatched"])} Sendungen',  d['post_unmatched'], FILL_POST),
    ]:
        # Section header
        row += 1
        ws2.merge_cells(start_row=row, start_column=1, end_row=row, end_column=ncols)
        c = ws2.cell(row=row, column=1, value=section_label)
        c.fill = FILL_SECTN; c.font = Font(bold=True, color='FFFFFF', size=10)
        c.alignment = Alignment(horizontal='left', vertical='center')
        ws2.row_dimensions[row].height = 16

        # Column headers
        row += 1
        for ci, h in enumerate(DETAIL_HDR, 1):
            _hdr_cell(ws2, row, ci, h, fill_sec, color='000000', size=9)
        ws2.row_dimensions[row].height = 14

        # Data rows
        src_cols = DETAIL_COLS  # original BI column names
        alt_cols = ['Auftragsnummer', 'Leistungsdatum', 'Rechnungsnummer',
                    'Empfänger Land', 'Empfänger PLZ', 'Versender PLZ',
                    'Tonnage (eff.)', 'Erlöse Fracht', 'Erloese']
        for _, r in df_sec.iterrows():
            row += 1
            alt_fill = PatternFill('solid', fgColor='EBF3FB') if row % 2 == 0 else None
            for ci, col in enumerate(alt_cols, 1):
                v = r.get(col) if col in df_sec.columns else None
                if v is not None and isinstance(v, float) and pd.isna(v): v = None
                _data_cell(ws2, row, ci, v, alt_fill,
                           right=(ci in NUM_DET or ci in EUR_DET),
                           date=(ci in DATE_DET), eur=(ci in EUR_DET))
        if df_sec.empty:
            row += 1
            ws2.cell(row=row, column=1, value='— keine fehlenden Sendungen —')

wb.save(OUT)
print(f'\nGespeichert: {OUT}')
print(f'  Sheets: Zusammenfassung + {len(detail_data)} Kunden-Detail-Sheets')
