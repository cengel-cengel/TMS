"""
coverage_bi_vs_pdf.py — Coverage analysis: BI PRE rows vs DINAS PDF cache

For each customer with a DINAS cache, compute:
  - BI PRE rows (Leistungsdatum < 2025-09-26)
  - PDF Rechnungen (unique rechnung_nr in cache)
  - PDF Positionen (total cache rows)
  - Matches at RechNr level and Sendungs level
  - Unmatched BI / unmatched PDF rows
"""
from pathlib import Path
import re
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill, Border, Side
from openpyxl.utils import get_column_letter

MIG  = pd.Timestamp('2025-09-26')
OUT  = Path('output/billing_report/00_coverage_bi_vs_pdf.xlsx')
OUT.parent.mkdir(exist_ok=True)

# KNR(s), display name, dinas_cache, bi_cache (None = use bi_top20)
CUSTOMERS = [
    ([406345],                         'Bitzer Kühlmaschinenbau',    'output/dinas_cache_406345.pkl',       None),
    ([409480],                         'Fischerwerke GmbH',          'output/dinas_cache_409480.pkl',       None),
    ([490085],                         'Konrad Hornschuch GmbH',     'output/dinas_cache_490085.pkl',       None),
    ([486073],                         'CHT Germany GmbH',           'output/dinas_cache_486073.pkl',       None),
    ([410844],                         'EBM-Papst Mulfingen',        'output/dinas_cache_410844.pkl',       None),
    ([423650],                         'HERMA GmbH',                 'output/dinas_cache_423650.pkl',       None),
    ([408244],                         'HELU KABEL GMBH',            'output/dinas_cache_408244.pkl',       None),
    ([491063],                         'Sika Deutschland GmbH',      'output/dinas_cache_491063.pkl',       None),
    ([406035],                         'GEZE GmbH',                  'output/dinas_cache_406035.pkl',       None),
    ([410912, 490527, 527410, 527373], 'Groz-Beckert',               'output/dinas_cache_groz_beckert.pkl', 'output/bi_cache_groz_beckert.pkl'),
    ([511241],                         'Sika Supply Center AG',      'output/dinas_cache_ssc_511241.pkl',   None),
]

def _norm(v):
    s = re.sub(r'\D', '', str(v)).lstrip('0')
    return s if s else str(v).strip()

# ── Load BI sources ──────────────────────────────────────────────────────────
print('Lade BI-Daten …')
bi_top20 = pd.read_pickle('output/bi_top20_data.pkl')['df']
bi_top20['Leistungsdatum'] = pd.to_datetime(bi_top20['Leistungsdatum'], errors='coerce')

bi_groz = pd.read_pickle('output/bi_cache_groz_beckert.pkl')
bi_groz['Leistungsdatum'] = pd.to_datetime(bi_groz['Leistungsdatum'], errors='coerce')

def get_bi_pre(knrs, bi_cache_path):
    if bi_cache_path:
        src = pd.read_pickle(bi_cache_path)
        src['Leistungsdatum'] = pd.to_datetime(src['Leistungsdatum'], errors='coerce')
    else:
        src = bi_top20
    rows = src[src['Kunden Nr BK'].isin(knrs) & (src['Leistungsdatum'] < MIG)].copy()
    return rows

# ── Per-customer analysis ────────────────────────────────────────────────────
results = []

for knrs, name, dc_path, bi_cache in CUSTOMERS:
    if not Path(dc_path).exists():
        print(f'  SKIP {name}: cache not found')
        continue

    pre = get_bi_pre(knrs, bi_cache)
    dc  = pd.read_pickle(dc_path)

    # Normalize join keys — Sendungsebene
    bi_snr  = pre['Auftragsnummer'].astype(str).apply(_norm)
    pdf_snr = dc['sendungs_nr'].astype(str).apply(_norm)

    # Sets
    bi_snr_set  = set(bi_snr)  - {'', '0', 'nan'}
    pdf_snr_set = set(pdf_snr) - {'', '0', 'nan'}

    # Counts
    bi_sendungen    = len(bi_snr_set)
    pdf_sendungen   = len(pdf_snr_set)
    pdf_positionen  = len(dc)

    # Matches at Sendungsebene
    matches = len(bi_snr_set & pdf_snr_set)

    # Unmatched
    bi_ohne_pdf   = bi_sendungen - matches
    pdf_ohne_bi   = pdf_sendungen - matches

    # Coverage %
    bi_cov_pct  = matches / bi_sendungen  * 100 if bi_sendungen  else 0
    pdf_cov_pct = matches / pdf_sendungen * 100 if pdf_sendungen else 0

    # Anmerkung
    avg_pos_per_snr = pdf_positionen / pdf_sendungen if pdf_sendungen else 0
    if bi_sendungen > pdf_sendungen * 1.3:
        note = f'{bi_sendungen - pdf_sendungen} mehr BI-Sendungen als PDF-Sendungen → fehlende PDFs'
    elif pdf_sendungen > bi_sendungen * 1.3:
        note = f'{pdf_sendungen - bi_sendungen} mehr PDF-Sendungen als BI-Sendungen → PDFs aus anderen Perioden/Kunden'
    else:
        note = f'Ø {avg_pos_per_snr:.1f} PDF-Positionen/Sendung'
    if avg_pos_per_snr > 3:
        note += f'; PDF sehr granular ({avg_pos_per_snr:.1f} Pos/Sendung)'

    knr_str = '+'.join(str(k) for k in knrs)
    results.append({
        'Kunde':               name,
        'KNR':                 knr_str,
        'BI PRE-Sendungen':    bi_sendungen,
        'PDF Sendungen':       pdf_sendungen,
        'PDF Positionen':      pdf_positionen,
        'Matches':             matches,
        'BI ohne PDF (abs)':   bi_ohne_pdf,
        'BI ohne PDF (%)':     round(100 - bi_cov_pct, 1),
        'PDF ohne BI (abs)':   pdf_ohne_bi,
        'PDF ohne BI (%)':     round(100 - pdf_cov_pct, 1),
        'Anmerkung':           note,
    })
    print(f'  {name}: BI={bi_sendungen} Sendungen, PDF={pdf_sendungen} Sendungen/{pdf_positionen} Pos, '
          f'Match={matches} ({bi_cov_pct:.0f}% BI, {pdf_cov_pct:.0f}% PDF)')

# ── Excel output ─────────────────────────────────────────────────────────────
COLS = list(results[0].keys())
N    = len(COLS)

FILL_HDR  = PatternFill('solid', fgColor='1F497D')
FILL_ALT  = PatternFill('solid', fgColor='DCE6F1')
FILL_WARN = PatternFill('solid', fgColor='FCE4D6')
THIN = Side(border_style='thin', color='BBBBBB')
BRD  = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
FNT_HDR = Font(bold=True, color='FFFFFF', size=9)
FNT_REG = Font(size=9)

WIDTHS = {
    'Kunde': 26, 'KNR': 18,
    'BI PRE-Sendungen': 15, 'PDF Sendungen': 13, 'PDF Positionen': 14,
    'Matches': 12,
    'BI ohne PDF (abs)': 15, 'BI ohne PDF (%)': 14,
    'PDF ohne BI (abs)': 15, 'PDF ohne BI (%)': 14,
    'Anmerkung': 58,
}
PCT_COLS = {'BI ohne PDF (%)', 'PDF ohne BI (%)'}
NUM_COLS = {
    'BI PRE-Sendungen', 'PDF Sendungen', 'PDF Positionen', 'Matches',
    'BI ohne PDF (abs)', 'PDF ohne BI (abs)',
}

wb = Workbook()
ws = wb.active
ws.title = 'Coverage BI vs PDFs'
ws.freeze_panes = 'A3'

# Title row
ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=N)
tc = ws.cell(row=1, column=1,
    value='Coverage-Analyse: BI PRE-Zeilen vs DINAS PDF-Extraktion  '
          f'(Stichtag Migration: 26.09.2025)')
tc.fill = FILL_HDR
tc.font = Font(bold=True, color='FFFFFF', size=12)
tc.alignment = Alignment(horizontal='center', vertical='center')
ws.row_dimensions[1].height = 20

# Header row
for ci, col in enumerate(COLS, 1):
    c = ws.cell(row=2, column=ci, value=col)
    c.fill = FILL_HDR; c.font = FNT_HDR; c.border = BRD
    c.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
    ws.column_dimensions[get_column_letter(ci)].width = WIDTHS.get(col, 14)
ws.row_dimensions[2].height = 28

# Data rows
for ri, row in enumerate(results, 3):
    hi_bi  = row['BI ohne PDF (%)'] > 30
    hi_pdf = row['PDF ohne BI (%)'] > 30
    rf = FILL_WARN if (hi_bi or hi_pdf) else (FILL_ALT if ri % 2 == 0 else None)
    for ci, col in enumerate(COLS, 1):
        v = row[col]
        c = ws.cell(row=ri, column=ci, value=v)
        if rf: c.fill = rf
        c.font = FNT_REG; c.border = BRD
        is_right = col in NUM_COLS or col in PCT_COLS
        c.alignment = Alignment(
            horizontal='right' if is_right else 'left',
            vertical='center',
            wrap_text=(col == 'Anmerkung'))
        if col in PCT_COLS and isinstance(v, (int, float)):
            c.number_format = '0.0"%"'

wb.save(OUT)
print(f'\nGespeichert: {OUT}')
