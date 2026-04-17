#!/usr/bin/env python3
"""
build_audit_report.py
=====================
Qualitäts-Audit für alle Kunden der TMS-Migration.
Output: output/billing_report/00_audit_extraktion.xlsx
  Sheet "Zusammenfassung" — eine Zeile pro Kunde, alle Metriken
  Sheet pro Kunde        — Detail-Felder-Vollständigkeit
"""
import glob, math
from pathlib import Path
import pandas as pd
import numpy as np
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

OUT = Path('output/billing_report/00_audit_extraktion.xlsx')
OUT.parent.mkdir(exist_ok=True)

V1     = Path('data/extracted/v1/Noerpel AI')
V2     = Path('data/extracted/v2')
BI_XLSX = Path('data/bi_report/Tagesbericht.Einzeldaten.alle.VKA.5.xlsx')

# ── Kunden-Konfiguration ────────────────────────────────────────────────────────
# name, knr, source_xlsx, hdr, dinas_dir, ax_dir, cache_path
CUSTOMERS = [
    ('HELU KABEL GmbH',          408244,
     'output/helu_dinas_vergleich.xlsx',        2,
     V1/'Helu/Rechnungen/Rechnungen DINAS',
     V1/'Helu/Rechnungen/Rechnungen AX',
     'output/dinas_cache_408244.pkl', None),
    ('Sika Dtl. CH AG & Co KG',  491063,
     'output/sika_dinas_vergleich.xlsx',         2,
     V1/'SIka/Rechnungen/Rechnungen DINAS',
     V1/'SIka/Rechnungen/Rechnungen AX',
     'output/dinas_cache_491063.pkl', None),
    ('Sika Supply Center GmbH',  511241,
     'output/ssc_dinas_vergleich.xlsx',           2,
     Path('data/extracted/sika_ssc/Dinas SSC'),
     None,
     'output/dinas_cache_ssc_511241.pkl', None),
    ('GEZE GmbH',                406035,
     'output/geze_dinas_vergleich.xlsx',         2,
     V1/'GEZE/Rechnungen/Rechnungen DINAS',
     V1/'GEZE/Rechnungen/Rechnungen AX',
     'output/dinas_cache_406035.pkl', None),
    ('HERMA GmbH',               423650,
     'output/herma_dinas_vergleich.xlsx',        0,
     Path('data/extracted/bi/Herma/Herma Dinas/Herma'),
     Path('data/extracted/bi/Herma/Herma AX/Herma AX'),
     'output/dinas_cache_423650.pkl',
     {  # HERMA uses short column names; map to standard audit names
         'pre':  {'Land': 'Empfänger Land', 'PLZ': 'Empfänger PLZ',
                  'Tonnage kg': 'Tonnage (eff.)', 'LDM': 'Lademeter',
                  'Diesel': 'Dinas Diesel', 'Maut/SSD': 'Dinas Maut/SSD'},
         'post': {'Land': 'Empfänger Land', 'PLZ': 'Empfänger PLZ',
                  'Tonnage kg': 'Tonnage (eff.)', 'LDM': 'Lademeter',
                  'Diesel': 'AX Diesel', 'Maut': 'AX Maut', 'Neben': 'AX Nebengebühr'},
     }),
    ('Bitzer Kühlmaschinenbau',  406345,
     'output/bitzer_dinas_vergleich.xlsx',       2,
     V1/'Bitzer/Rechnungen/Rechnungen DINAS',
     V1/'Bitzer/Rechnungen/Rechnungen AX',
     'output/dinas_cache_406345.pkl', None),
    ('CHT Germany GmbH',         486073,
     'output/cht_dinas_vergleich.xlsx',          2,
     V1/'CHT/Rechnungen/Rechnungen DINAS',
     V1/'CHT/Rechnungen/Rechnungen AX',
     'output/dinas_cache_486073.pkl', None),
    ('Konrad Hornschuch GmbH',   490085,
     'output/hornschuch_dinas_vergleich.xlsx',   2,
     V1/'Hornschuch/Rechnungen/Rechnungen DINAS',
     V1/'Hornschuch/Rechnungen/Rechnungen AX',
     'output/dinas_cache_490085.pkl', None),
    ('EBM-Papst Mulfingen',      410844,
     'output/ebm_dinas_vergleich.xlsx',          2,
     V1/'EBM/Rechnungen/Rechnungen DINAS',
     V1/'EBM/Rechnungen/Rechnungen AX',
     'output/dinas_cache_410844.pkl', None),
    ('Fischerwerke GmbH & Co KG',409480,
     'output/fischerwerke_dinas_vergleich.xlsx', 2,
     V2/'Fischer/Rechnungen/Rechnungen DINAS',
     V2/'Fischer/Rechnungen/Rechnungen AX',
     'output/dinas_cache_409480.pkl', None),
    ('Groz-Beckert KG',          410912,
     None,                                       None,
     V1/'Groz Beckert/Rechnungen/Rechnungen DINAS',
     V1/'Groz Beckert/Rechnungen/Rechnungen AX',
     'output/dinas_cache_groz_beckert.pkl', None),
    ('Sika Automotive AG',       527406,
     'output/bi_cache_sika_527406.pkl',          'bi_pkl',
     None, None, None, None),
    ('Sika Automotive DE',       '413276+493163',
     'output/bi_cache_sika_atm_de.pkl',          'bi_pkl',
     None, None, None, None),
]

# ── Felder die geprüft werden ────────────────────────────────────────────────
PRE_FIELDS_BI  = ['Empfänger Land','Empfänger PLZ','Tonnage (eff.)',
                   'Stellplätze','Lademeter','Volumen','Leistungsdatum']
PRE_FIELDS_PDF = ['Dinas Fracht','Dinas Diesel','Dinas Maut/SSD','Dinas Gesamt']
POST_FIELDS    = ['Empfänger Land','Empfänger PLZ','Tonnage (eff.)',
                  'Stellplätze','Lademeter','Volumen','Leistungsdatum',
                  'AX Fracht','AX Diesel','AX Maut','AX Nebengebühr','AX Gesamt']

def pct_filled(df, col):
    """Returns filled%, missing% as floats 0–100."""
    if col not in df.columns or len(df) == 0:
        return 0.0, 100.0
    s = df[col]
    filled = s.notna() & (s.astype(str).str.strip() != '') & (s.astype(str).str.lower() != 'nan')
    n = filled.sum()
    return round(n / len(df) * 100, 1), round((len(df) - n) / len(df) * 100, 1)

def count_pdfs(d):
    if d is None or not Path(d).exists():
        return 0
    return len(glob.glob(str(Path(d) / '*.pdf')) + glob.glob(str(Path(d) / '*.PDF')))

def _load_bi_pkl_for_audit(pkl_path):
    _bi = pd.read_pickle(pkl_path)
    _bi['Leistungsdatum'] = pd.to_datetime(_bi['Leistungsdatum'], errors='coerce')
    _mig = pd.Timestamp('2025-09-26')
    pre  = _bi[_bi['Leistungsdatum'] < _mig].copy().rename(columns={
        'Erlöse Fracht':'Dinas Fracht','Erlöse Diesel':'Dinas Diesel',
        'Erlöse Maut':'Dinas Maut/SSD','Erloese':'Dinas Gesamt'})
    post = _bi[_bi['Leistungsdatum'] >= _mig].copy().rename(columns={
        'Erlöse Fracht':'AX Fracht','Erlöse Diesel':'AX Diesel',
        'Erlöse Maut':'AX Maut','Erlöse Nebengebühr':'AX Nebengebühr',
        'Erloese':'AX Gesamt'})
    return pre, post

def load_sheet(xlsx_path, hdr, keyword):
    """Load the first sheet whose name contains keyword."""
    if xlsx_path is None or not Path(xlsx_path).exists():
        return pd.DataFrame()
    try:
        xls = pd.ExcelFile(xlsx_path)
        for sh in xls.sheet_names:
            if keyword.upper() in sh.upper():
                return pd.read_excel(xlsx_path, sheet_name=sh, header=hdr)
        return pd.DataFrame()
    except Exception as e:
        print(f'  WARNING load_sheet({xlsx_path}, {keyword}): {e}')
        return pd.DataFrame()

# ── Pro-Kunde Audit ─────────────────────────────────────────────────────────
results = []
detail_sheets = {}

for name, knr, src_xlsx, hdr, dinas_dir, ax_dir, cache_path, col_map in CUSTOMERS:
    print(f'\n--- {name} ---')
    rec = {'Kunde': name, 'KNR': str(knr) if knr else 'n/a'}

    # PDF counts
    dinas_total = count_pdfs(dinas_dir)
    ax_total    = count_pdfs(ax_dir)
    rec['DINAS PDFs abgelegt'] = dinas_total
    rec['AX PDFs abgelegt']    = ax_total

    # DINAS cache
    cache_rows = 0
    if cache_path and Path(cache_path).exists():
        cache_df = pd.read_pickle(cache_path)
        cache_rows = len(cache_df)
        # Unique Rechnungsnummern = approx extracted PDFs
        unique_rn = cache_df['rechnung_nr'].nunique() if 'rechnung_nr' in cache_df.columns else 0
        rec['DINAS extrahiert (Positionen)'] = cache_rows
        rec['DINAS extrahiert (Rechnungen)'] = unique_rn
        print(f'  DINAS cache: {cache_rows} Positionen, {unique_rn} Rechnungen')
    else:
        rec['DINAS extrahiert (Positionen)'] = 0
        rec['DINAS extrahiert (Rechnungen)'] = 0

    # PDFs ohne extrahierbare Positionen (Deckblätter / 0-Pos)
    rec['DINAS 0-Pos/Cover PDFs'] = max(0, dinas_total - rec['DINAS extrahiert (Rechnungen)'])

    # PRE sheet
    if hdr == 'bi_pkl' and src_xlsx and Path(src_xlsx).exists():
        pre, post = _load_bi_pkl_for_audit(src_xlsx)
    else:
        pre = load_sheet(src_xlsx, hdr, 'PRE')
        post = load_sheet(src_xlsx, hdr, 'POST')
    if col_map:
        if 'pre' in col_map and not pre.empty:
            pre = pre.rename(columns=col_map['pre'])
        if 'post' in col_map and not post.empty:
            post = post.rename(columns=col_map['post'])

    # For Groz-Beckert: PRE from cache
    if name == 'Groz-Beckert KG' and cache_path and Path(cache_path).exists():
        pre_groz = pd.read_pickle(cache_path)
        pre = pre_groz.rename(columns={
            'empf_land': 'Empfänger Land', 'empf_plz': 'Empfänger PLZ',
            'kg_rechnung': 'Tonnage (eff.)', 'ldm': 'Lademeter',
            'leistungsdatum': 'Leistungsdatum',
            'fracht': 'Dinas Fracht', 'diesel': 'Dinas Diesel',
            'maut_ssd': 'Dinas Maut/SSD', 'gesamtbetrag': 'Dinas Gesamt',
        })
        # POST from full BI (KNRs 410912, 490527, 527410, 527373)
        _bi_groz_cache = Path('output/bi_cache_groz_beckert.pkl')
        GROZ_KNRS = [410912, 490527, 527410, 527373]
        if not _bi_groz_cache.exists():
            print('  Lade Groz-Beckert aus vollem BI...')
            _bi_all = pd.read_excel(BI_XLSX, header=0)
            _bi_groz = _bi_all[_bi_all['Kunden Nr BK'].isin(GROZ_KNRS)].copy()
            _bi_groz.to_pickle(_bi_groz_cache)
        else:
            _bi_groz = pd.read_pickle(_bi_groz_cache)
        _bi_groz['Leistungsdatum'] = pd.to_datetime(_bi_groz['Leistungsdatum'], errors='coerce')
        post = _bi_groz[_bi_groz['Leistungsdatum'] >= pd.Timestamp('2025-09-26')].rename(columns={
            'Erlöse Fracht': 'AX Fracht', 'Erlöse Diesel': 'AX Diesel',
            'Erlöse Maut': 'AX Maut', 'Erlöse Nebengebühr': 'AX Nebengebühr',
            'Erloese': 'AX Gesamt',
        })

    rec['PRE Sendungen'] = len(pre)
    rec['POST Sendungen'] = len(post)
    print(f'  PRE: {len(pre)} Zeilen, POST: {len(post)} Zeilen')

    # Master/Sub from POST
    if 'Mastersendung' in post.columns:
        n_master = post['Mastersendung'].notna().sum()
        rec['POST Master'] = int(n_master)
    elif '_is_master' in post.columns:
        rec['POST Master'] = int(post['_is_master'].sum())
    else:
        rec['POST Master'] = 'n/a'
    rec['POST Sub'] = 'n/a'  # sub rows filtered out before report

    # Field completeness — PRE BI fields
    detail_rows = []
    for col in PRE_FIELDS_BI:
        ok, miss = pct_filled(pre, col)
        key = f'PRE {col} gefüllt%'
        rec[key] = ok
        detail_rows.append({'Sheet': 'PRE', 'Quelle': 'bi_raw', 'Feld': col,
                            'Gefüllt%': ok, 'Fehlt%': miss, 'N': len(pre)})

    # Field completeness — PRE PDF fields
    for col in PRE_FIELDS_PDF:
        ok, miss = pct_filled(pre, col)
        key = f'PRE {col} gefüllt%'
        rec[key] = ok
        detail_rows.append({'Sheet': 'PRE', 'Quelle': 'PDF', 'Feld': col,
                            'Gefüllt%': ok, 'Fehlt%': miss, 'N': len(pre)})

    # Field completeness — POST
    for col in POST_FIELDS:
        ok, miss = pct_filled(post, col)
        key = f'POST {col} gefüllt%'
        rec[key] = ok
        detail_rows.append({'Sheet': 'POST', 'Quelle': 'AX/BI', 'Feld': col,
                            'Gefüllt%': ok, 'Fehlt%': miss, 'N': len(post)})

    results.append(rec)
    detail_sheets[name] = pd.DataFrame(detail_rows)
    print(f'  Felder geprüft: {len(detail_rows)}')

summary_df = pd.DataFrame(results)

# ── Styles ──────────────────────────────────────────────────────────────────
def fill(h): return PatternFill('solid', fgColor=h)
def fnt(bold=False, color='000000', size=9):
    return Font(bold=bold, color=color, size=size)
THIN = Side(border_style='thin', color='CCCCCC')
BRD  = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

FILL_HDR  = fill('1F497D')
FILL_ALT1 = fill('DEEAF1')
FILL_ALT2 = fill('FFFFFF')
FILL_WARN = fill('FFEB9C')  # gelb wenn < 50%
FILL_OK   = fill('C6EFCE')  # grün wenn > 90%

def write_summary_sheet(ws, df):
    ws.title = 'Zusammenfassung'
    ws.freeze_panes = 'C3'

    # Title row
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(df.columns))
    cell = ws.cell(1, 1)
    cell.value = 'TMS Migration Audit — Daten-Qualität pro Kunde'
    cell.fill = FILL_HDR
    cell.font = Font(bold=True, color='FFFFFF', size=13)
    cell.alignment = Alignment(horizontal='center', vertical='center')
    ws.row_dimensions[1].height = 22

    # Header
    for ci, col in enumerate(df.columns, 1):
        cell = ws.cell(2, ci)
        cell.value = col
        cell.fill = FILL_HDR
        cell.font = fnt(bold=True, color='FFFFFF', size=8)
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        cell.border = BRD
    ws.row_dimensions[2].height = 40

    # Data rows
    for ri, (_, row) in enumerate(df.iterrows(), 3):
        bg = FILL_ALT1 if ri % 2 == 1 else FILL_ALT2
        for ci, val in enumerate(row, 1):
            cell = ws.cell(ri, ci)
            cell.value = val
            cell.border = BRD
            cell.alignment = Alignment(horizontal='right' if isinstance(val, (int, float)) else 'left',
                                       vertical='center')
            cell.font = fnt(size=9)
            # Color-code percentage fields
            col_name = df.columns[ci-1]
            if isinstance(val, float) and 'gefüllt%' in col_name:
                if val < 50:
                    cell.fill = FILL_WARN
                elif val >= 90:
                    cell.fill = FILL_OK
                else:
                    cell.fill = bg
            else:
                cell.fill = bg

    # Column widths
    ws.column_dimensions['A'].width = 26
    ws.column_dimensions['B'].width = 10
    for ci in range(3, len(df.columns) + 1):
        ws.column_dimensions[get_column_letter(ci)].width = 12

def write_detail_sheet(ws, name, df):
    ws.title = name[:31]
    ws.freeze_panes = 'A3'

    header = ['Sheet', 'Quelle', 'Feld', 'N Zeilen', 'Gefüllt%', 'Fehlt%', 'Bewertung']
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(header))
    cell = ws.cell(1, 1)
    cell.value = f'Daten-Qualität: {name}'
    cell.fill = FILL_HDR
    cell.font = Font(bold=True, color='FFFFFF', size=11)
    cell.alignment = Alignment(horizontal='center')
    ws.row_dimensions[1].height = 20

    for ci, h in enumerate(header, 1):
        cell = ws.cell(2, ci)
        cell.value = h
        cell.fill = FILL_HDR
        cell.font = fnt(bold=True, color='FFFFFF', size=9)
        cell.alignment = Alignment(horizontal='center')
        cell.border = BRD
    ws.row_dimensions[2].height = 18

    prev_sheet = None
    for ri, (_, row) in enumerate(df.iterrows(), 3):
        bg = FILL_ALT1 if row['Sheet'] == 'PRE' else FILL_ALT2
        ok_pct = row['Gefüllt%']
        bewertung = ('✓ OK' if ok_pct >= 90
                     else ('⚠ Teilweise' if ok_pct >= 50 else '✗ Lückenhaft'))
        vals = [row['Sheet'], row['Quelle'], row['Feld'],
                int(row['N']), row['Gefüllt%'], row['Fehlt%'], bewertung]
        for ci, val in enumerate(vals, 1):
            cell = ws.cell(ri, ci)
            cell.value = val
            cell.border = BRD
            cell.font = fnt(size=9)
            cell.alignment = Alignment(horizontal='right' if isinstance(val, (int, float)) else 'left',
                                       vertical='center')
            if ci in (5, 6) and isinstance(val, float):
                cell.fill = (FILL_OK if (ci == 5 and val >= 90)
                             else FILL_WARN if (ci == 5 and val < 50)
                             else bg)
            else:
                cell.fill = bg

    for ci, w in enumerate([8, 10, 28, 9, 11, 9, 14], 1):
        ws.column_dimensions[get_column_letter(ci)].width = w

# ── Workbook bauen ──────────────────────────────────────────────────────────
wb = Workbook()
write_summary_sheet(wb.active, summary_df)

for cust_name, detail_df in detail_sheets.items():
    ws = wb.create_sheet()
    write_detail_sheet(ws, cust_name, detail_df)

wb.save(OUT)
print(f'\n✓ Gespeichert: {OUT}')
print(f'  Kunden: {len(results)}, Sheets: {1 + len(detail_sheets)}')
