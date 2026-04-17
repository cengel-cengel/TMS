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

    # Normalize join keys
    bi_snr  = pre['Auftragsnummer'].astype(str).apply(_norm)   # Sendungsnummer
    bi_rnr  = pre['Rechnungsnummer'].astype(str).apply(_norm)  # Rechnungsnummer
    pdf_snr = dc['sendungs_nr'].astype(str).apply(_norm)
    pdf_rnr = dc['rechnung_nr'].astype(str).apply(_norm)

    # Sets for matching
    bi_snr_set  = set(bi_snr)  - {'', '0', 'nan'}
    bi_rnr_set  = set(bi_rnr)  - {'', '0', 'nan'}
    pdf_snr_set = set(pdf_snr) - {'', '0', 'nan'}
    pdf_rnr_set = set(pdf_rnr) - {'', '0', 'nan'}

    # Counts
    bi_pre_rows   = len(pre)
    bi_uniq_rnr   = len(bi_rnr_set)
    pdf_rechnungen = len(pdf_rnr_set)
    pdf_positionen = len(dc)

    # Matches
    match_snr = len(bi_snr_set & pdf_snr_set)
    match_rnr = len(bi_rnr_set & pdf_rnr_set)

    # BI rows matched (any row whose Auftragsnummer OR Rechnungsnummer hits)
    bi_matched_mask = bi_snr.isin(pdf_snr_set) | bi_rnr.isin(pdf_rnr_set)
    bi_matched_rows = bi_matched_mask.sum()
    bi_unmatched_rows = bi_pre_rows - bi_matched_rows

    # PDF rows unmatched (sendungs_nr not in BI, rechnung_nr not in BI)
    pdf_unmatched_rows = (~(pdf_snr.isin(bi_snr_set) | pdf_rnr.isin(bi_rnr_set))).sum()

    # Coverage %
    bi_cov_pct  = bi_matched_rows / bi_pre_rows * 100 if bi_pre_rows else 0
    pdf_cov_pct = (pdf_positionen - pdf_unmatched_rows) / pdf_positionen * 100 if pdf_positionen else 0

    # Anmerkung
    avg_bi_per_rnr  = bi_pre_rows / bi_uniq_rnr if bi_uniq_rnr else 0
    avg_pdf_per_rnr = pdf_positionen / pdf_rechnungen if pdf_rechnungen else 0
    if avg_bi_per_rnr > 5 and avg_pdf_per_rnr < 3:
        note = f'BI {avg_bi_per_rnr:.0f} Zeilen/RechNr, PDF {avg_pdf_per_rnr:.1f} Pos/RechNr → PDF ist aggregiert'
    elif avg_bi_per_rnr < 3 and avg_pdf_per_rnr > 5:
        note = f'PDF {avg_pdf_per_rnr:.0f} Pos/RechNr, BI {avg_bi_per_rnr:.1f} Zeilen/RechNr → PDF granularer'
    elif pdf_rechnungen > bi_uniq_rnr * 1.3:
        note = f'PDF hat {pdf_rechnungen - bi_uniq_rnr} mehr RechNr als BI → PDFs ohne BI-Eintrag'
    elif bi_uniq_rnr > pdf_rechnungen * 1.3:
        note = f'BI hat {bi_uniq_rnr - pdf_rechnungen} mehr RechNr als PDF → fehlende PDFs'
    else:
        note = f'BI {avg_bi_per_rnr:.1f} Zeilen/RechNr, PDF {avg_pdf_per_rnr:.1f} Pos/RechNr'

    knr_str = '+'.join(str(k) for k in knrs)
    results.append({
        'Kunde':             name,
        'KNR':               knr_str,
        'BI PRE-Zeilen':     bi_pre_rows,
        'BI uni. RechNr':    bi_uniq_rnr,
        'PDF Rechnungen':    pdf_rechnungen,
        'PDF Positionen':    pdf_positionen,
        'Matches (RechNr)':  match_rnr,
        'Matches (SendNr)':  match_snr,
        'BI-Zeilen mit Match': bi_matched_rows,
        'BI ohne PDF (abs)': bi_unmatched_rows,
        'BI ohne PDF (%)':   round(100 - bi_cov_pct, 1),
        'PDF ohne BI (abs)': pdf_unmatched_rows,
        'PDF ohne BI (%)':   round(100 - pdf_cov_pct, 1),
        'Anmerkung':         note,
    })
    print(f'  {name}: BI={bi_pre_rows} PRE, PDF={pdf_positionen} Pos/{pdf_rechnungen} Rechnungen, '
          f'Match(RNR)={match_rnr}/{bi_uniq_rnr} ({match_rnr/bi_uniq_rnr*100:.0f}%)')

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
    'Kunde': 26, 'KNR': 18, 'BI PRE-Zeilen': 13, 'BI uni. RechNr': 13,
    'PDF Rechnungen': 14, 'PDF Positionen': 14,
    'Matches (RechNr)': 15, 'Matches (SendNr)': 15,
    'BI-Zeilen mit Match': 17,
    'BI ohne PDF (abs)': 15, 'BI ohne PDF (%)': 14,
    'PDF ohne BI (abs)': 15, 'PDF ohne BI (%)': 14,
    'Anmerkung': 55,
}
PCT_COLS = {'BI ohne PDF (%)', 'PDF ohne BI (%)'}
NUM_COLS = {
    'BI PRE-Zeilen', 'BI uni. RechNr', 'PDF Rechnungen', 'PDF Positionen',
    'Matches (RechNr)', 'Matches (SendNr)', 'BI-Zeilen mit Match',
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
