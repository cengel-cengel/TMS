"""
Script 3: Add per-customer detail sheets to the Excel workbook.
One sheet per top-20 customer: summary KPI by va_norm + 5 PRE + 5 POST samples.
"""
import pickle, pandas as pd, numpy as np
from pathlib import Path
from openpyxl import load_workbook
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter

OUT = Path('/home/user/TMS/output')
XLSX = OUT / 'top20_audit_abweichungsanalyse_2026.xlsx'

# ── Load ──────────────────────────────────────────────────────────────────────
with open(OUT / 'top20_abw_stats.pkl', 'rb') as f:
    d = pickle.load(f)
stats      = d['stats']
top20_meta = d['top20_meta']
# basis_map: knr → (basis_col, corr) — added by s1 when billing-basis logic is active
basis_map  = d.get('basis_map', {})

with open(OUT / 'top20_abw_samples.pkl', 'rb') as f:
    samples_df = pickle.load(f)

try:
    with open(OUT / 'top20_abw_route_outliers.pkl', 'rb') as f:
        route_outliers = pickle.load(f)
    has_route_outliers = (len(route_outliers) > 0 and
                          '_kunden_nr' in route_outliers.columns)
except FileNotFoundError:
    route_outliers = pd.DataFrame()
    has_route_outliers = False

wb = load_workbook(str(XLSX))

# ── Styles ────────────────────────────────────────────────────────────────────
WHITE_FILL  = PatternFill(fill_type=None)
BLUE_FILL   = PatternFill('solid', fgColor='1F4E79')
LBLUE_FILL  = PatternFill('solid', fgColor='2E75B6')
PRE_FILL    = PatternFill('solid', fgColor='D6E4F0')
POST_FILL   = PatternFill('solid', fgColor='E2EFDA')
GREY_FILL      = PatternFill('solid', fgColor='BFBFBF')
RED_FILL       = PatternFill('solid', fgColor='FF0000')
ORANGE_FILL    = PatternFill('solid', fgColor='FFC000')
YELLOW_FILL    = PatternFill('solid', fgColor='FFFF00')
DARK_RED_FILL  = PatternFill('solid', fgColor='7B2C2C')
LIGHT_RED_FILL = PatternFill('solid', fgColor='FFD9D9')

def hfont(bold=False, size=11, color='000000'):
    return Font(name='Calibri', bold=bold, size=size, color=color)

def thin():
    s = Side(style='thin')
    return Border(left=s, right=s, top=s, bottom=s)

def sev_fill(delta_pct, n_post):
    if n_post == 0:            return GREY_FILL
    if pd.isna(delta_pct):     return WHITE_FILL
    if delta_pct <= -40:       return RED_FILL
    if delta_pct <= -20:       return ORANGE_FILL
    if delta_pct <= -5:        return YELLOW_FILL
    return WHITE_FILL

def set_width(ws, col, w):
    ws.column_dimensions[get_column_letter(col)].width = w

# ── Sample columns to display ─────────────────────────────────────────────────
SHOW_COLS = [
    'Leistungsdatum', 'Rechnungsnummer', 'Ausgangsbordero',
    'va_norm', 'Verkehrsart', 'Verkehrsart Detail',
    'Versender PLZ', 'Empfänger Land', 'Empfänger PLZ', 'route_2',
    'Colli', 'Tonnage (eff.)', 'Lademeter', 'Volumen',
    'Erlöse Fracht', 'Erlöse Diesel', 'Erlöse Maut', 'Erlöse Nebengebühr',
    'Erloese', 'Kosten Gesamt', 'DB II', 'DB II%',
]
SHOW_COLS = [c for c in SHOW_COLS if c in samples_df.columns]

NUM_COLS = {'Colli','Tonnage (eff.)','Lademeter','Volumen',
            'Erlöse Fracht','Erlöse Diesel','Erlöse Maut','Erlöse Nebengebühr',
            'Erloese','Kosten Gesamt','DB II','DB II%'}

COL_WIDTHS = {
    'Leistungsdatum': 14, 'Rechnungsnummer': 16, 'Ausgangsbordero': 18,
    'va_norm': 14, 'Verkehrsart': 20, 'Verkehrsart Detail': 16,
    'Versender PLZ': 12, 'Empfänger Land': 14, 'Empfänger PLZ': 12,
    'route_2': 14, 'Colli': 7, 'Tonnage (eff.)': 14, 'Lademeter': 11,
    'Volumen': 10, 'Erlöse Fracht': 15, 'Erlöse Diesel': 14,
    'Erlöse Maut': 13, 'Erlöse Nebengebühr': 18,
    'Erloese': 13, 'Kosten Gesamt': 14, 'DB II': 12, 'DB II%': 10,
}

SUMMARY_HEADERS = [
    'Verkehrsart', 'n PRE', 'n POST',
    'Ø Erlös PRE €', 'Ø Erlös POST €', 'Δ € / Sendung', 'Δ %',
    'Ø DB II PRE €', 'Ø DB II POST €', 'Status'
]

# ── Build one sheet per customer ──────────────────────────────────────────────
for _, meta_row in top20_meta.iterrows():
    knr   = meta_row['kunden_nr']
    kname = str(meta_row['kunden_name'])

    # Sheet name max 31 chars
    sname = kname[:28].strip().rstrip('.')
    if sname in wb.sheetnames:
        sname = sname[:25] + f'_{knr}'[:5]
    ws = wb.create_sheet(sname)

    # ── Title row ──────────────────────────────────────────────────────────
    ws.merge_cells('A1:V1')
    c = ws.cell(1, 1, f'{kname}  |  Kunden-Nr: {knr}')
    c.font = hfont(bold=True, size=14, color='FFFFFF')
    c.fill = BLUE_FILL
    c.alignment = Alignment(horizontal='left', vertical='center')
    ws.row_dimensions[1].height = 28

    # ── Total Erlös from meta ──────────────────────────────────────────────
    gesamt_erloes = meta_row.get('gesamt_erloes', np.nan)
    ws.cell(2, 1, 'Gesamterlös (POST):').font = hfont(bold=True)
    c2 = ws.cell(2, 2, round(float(gesamt_erloes), 2) if not pd.isna(gesamt_erloes) else '')
    if isinstance(c2.value, float): c2.number_format = '#,##0.00 "€"'

    # ── Section A: Summary by va_norm ──────────────────────────────────────
    row = 4
    ws.merge_cells(f'A{row}:J{row}')
    c = ws.cell(row, 1, 'A — Kennzahlen nach Verkehrsart (PRE vs. POST)')
    c.font = hfont(bold=True, size=12, color='FFFFFF')
    c.fill = LBLUE_FILL

    row += 1
    for ci, h in enumerate(SUMMARY_HEADERS, 1):
        c = ws.cell(row, ci, h)
        c.font = hfont(bold=True, color='FFFFFF')
        c.fill = LBLUE_FILL
        c.border = thin()
        c.alignment = Alignment(horizontal='center', wrap_text=True)
    ws.row_dimensions[row].height = 28

    cust_stats = stats[(stats['Kunden Nr BK'] == knr) & (stats['va_norm'] != '(Gesamt)')]
    has_any_post = False

    for _, sr in cust_stats.iterrows():
        row += 1
        n_pre  = int(sr['n_pre'])  if not pd.isna(sr['n_pre'])  else 0
        n_post = int(sr['n_post']) if not pd.isna(sr['n_post']) else 0
        if n_post > 0:
            has_any_post = True

        delta_pct = sr['delta_pct']
        fill = sev_fill(delta_pct, n_post)

        status = ('VERKEHR VERLOREN' if n_post == 0
                  else 'Kritisch'  if not pd.isna(delta_pct) and delta_pct <= -40
                  else 'Stark'     if not pd.isna(delta_pct) and delta_pct <= -20
                  else 'Moderat'   if not pd.isna(delta_pct) and delta_pct <= -5
                  else 'Stabil')

        def fe(v): return round(float(v), 2) if not pd.isna(v) else ''
        def fp(v): return round(float(v), 2) if not pd.isna(v) else ''

        row_vals = [
            sr['va_norm'], n_pre, n_post,
            fe(sr['avg_pre']), fe(sr['avg_post']), fe(sr['delta_eur']), fp(delta_pct),
            fe(sr.get('avg_pre_dbii', np.nan)), fe(sr.get('avg_post_dbii', np.nan)),
            status
        ]
        num_fmt_map = {4:'#,##0.00 "€"', 5:'#,##0.00 "€"', 6:'#,##0.00 "€"',
                       7:'0.00"%"', 8:'#,##0.00 "€"', 9:'#,##0.00 "€"'}
        for ci, val in enumerate(row_vals, 1):
            c = ws.cell(row, ci, val)
            c.fill = fill
            c.border = thin()
            c.alignment = Alignment(horizontal='center')
            if ci in num_fmt_map and isinstance(val, (int, float)) and val != '':
                c.number_format = num_fmt_map[ci]

    # Totals row
    tot_row = stats[(stats['Kunden Nr BK'] == knr) & (stats['va_norm'] == '(Gesamt)')]
    if len(tot_row) > 0:
        row += 1
        tr = tot_row.iloc[0]
        n_pre_t  = int(tr['n_pre'])  if not pd.isna(tr['n_pre'])  else 0
        n_post_t = int(tr['n_post']) if not pd.isna(tr['n_post']) else 0
        fill_t = sev_fill(tr['delta_pct'], n_post_t)
        tot_vals = [
            'GESAMT', n_pre_t, n_post_t,
            fe(tr['avg_pre']), fe(tr['avg_post']), fe(tr['delta_eur']), fp(tr['delta_pct']),
            fe(tr.get('avg_pre_dbii', np.nan)), fe(tr.get('avg_post_dbii', np.nan)), ''
        ]
        for ci, val in enumerate(tot_vals, 1):
            c = ws.cell(row, ci, val)
            c.fill = fill_t
            c.font = hfont(bold=True)
            c.border = thin()
            c.alignment = Alignment(horizontal='center')
            if ci in {4,5,6,8,9} and isinstance(val,(int,float)) and val != '':
                c.number_format = '#,##0.00 "€"'
            if ci == 7 and isinstance(val,(int,float)) and val != '':
                c.number_format = '0.00"%"'

    # ── Lost banner ────────────────────────────────────────────────────────
    if not has_any_post:
        row += 1
        ws.merge_cells(f'A{row}:J{row}')
        c = ws.cell(row, 1, '⚠ VERKEHR / KUNDE VERLOREN – keine POST-Sendungen fakturiert')
        c.font = hfont(bold=True, size=12, color='FFFFFF')
        c.fill = RED_FILL
        c.alignment = Alignment(horizontal='center')
        ws.row_dimensions[row].height = 22

    # ── Section B: PRE samples ─────────────────────────────────────────────
    row += 2
    cust_samples_pre = samples_df[
        (samples_df['Kunden Nr BK'] == knr) & (samples_df['periode'] == 'PRE')
    ]
    cust_samples_post = samples_df[
        (samples_df['Kunden Nr BK'] == knr) & (samples_df['periode'] == 'POST')
    ]

    for section_label, sect_fill, sect_samples in [
        ('B — Repräsentative PRE-Sendungen (nächste am Median-Erlös)', PRE_FILL, cust_samples_pre),
        ('C — Repräsentative POST-Sendungen (nächste am Median-Erlös)', POST_FILL, cust_samples_post),
    ]:
        n_cols = len(SHOW_COLS)
        end_col = get_column_letter(n_cols)
        ws.merge_cells(f'A{row}:{end_col}{row}')
        c = ws.cell(row, 1, section_label)
        c.font = hfont(bold=True, size=11, color='FFFFFF')
        c.fill = LBLUE_FILL
        ws.row_dimensions[row].height = 20

        row += 1
        for ci, col_name in enumerate(SHOW_COLS, 1):
            c = ws.cell(row, ci, col_name)
            c.font = hfont(bold=True)
            c.fill = sect_fill
            c.border = thin()
            c.alignment = Alignment(horizontal='center', wrap_text=True)
            set_width(ws, ci, COL_WIDTHS.get(col_name, 14))
        ws.row_dimensions[row].height = 28

        if len(sect_samples) == 0:
            row += 1
            ws.cell(row, 1, 'Keine fakturierten Sendungen in diesem Zeitraum.').font = hfont(bold=True)
        else:
            for _, srow in sect_samples.iterrows():
                row += 1
                for ci, col_name in enumerate(SHOW_COLS, 1):
                    val = srow.get(col_name, '')
                    if pd.isna(val) if not isinstance(val, str) else False:
                        val = ''
                    # convert timestamps to date strings
                    if hasattr(val, 'date'):
                        val = str(val.date())
                    c = ws.cell(row, ci, val)
                    c.border = thin()
                    c.alignment = Alignment(horizontal='center')
                    if col_name in NUM_COLS and isinstance(val, (int, float)) and val != '':
                        if col_name == 'DB II%':
                            c.number_format = '0.00"%"'
                        else:
                            c.number_format = '#,##0.00'
        row += 2  # gap before next section

    # ── Section D: Ausreißer-Analyse nach Relation (Abrechnungsbasis-aware) ───
    # Shows Dinas (PRE) reference + AX (POST) outliers per route.
    # Deviation is computed as €/billing-unit (PPU), so size differences
    # (e.g. more pallets) are correctly neutralised.
    # PRE reference is matched by similar billing-dimension value, not raw Erlöse.
    if has_route_outliers:
        cust_outs = route_outliers[route_outliers['_kunden_nr'] == knr]
        if len(cust_outs) > 0:
            routes_with_outliers = (cust_outs[cust_outs['_row_type'] == 'POST_OUTLIER']
                                    ['_route'].dropna().unique())

            if len(routes_with_outliers) > 0:
                # Billing basis for this customer
                basis_entry   = basis_map.get(knr, ('Lademeter', None))
                abr_basis_col = basis_entry[0] if isinstance(basis_entry, tuple) else basis_entry
                UNIT_LABELS   = {'Lademeter': 'LDM', 'Stellplätze': 'Stpl',
                                 'Tonnage (eff.)': 't', 'Volumen': 'm³', 'Colli': 'Col'}
                unit_lbl = UNIT_LABELS.get(abr_basis_col, abr_basis_col)

                # Extended display: existing cols + PPU + deviation-on-PPU
                OUTLIER_SHOW_COLS = SHOW_COLS + ['_ppu', '_deviation_pct']
                OUTLIER_HDRS = {**{c: c for c in SHOW_COLS},
                                '_ppu':          f'€/{unit_lbl}',
                                '_deviation_pct': f'Δ% €/{unit_lbl}'}
                d_ncols = len(OUTLIER_SHOW_COLS)
                d_end   = get_column_letter(d_ncols)

                set_width(ws, d_ncols - 1, 10)   # _ppu column
                set_width(ws, d_ncols,     12)    # _deviation_pct column

                row += 1
                ws.merge_cells(f'A{row}:{d_end}{row}')
                c = ws.cell(row, 1,
                    f'D — Ausreißer-Analyse nach Relation: '
                    f'Dinas (PRE) Referenz  →  AX (POST) Ausreißer  |  '
                    f'Abrechnungsbasis: {abr_basis_col}  |  '
                    f'Schwellenwert: |Δ €/{unit_lbl}| > 7 %')
                c.font  = hfont(bold=True, size=11, color='FFFFFF')
                c.fill  = DARK_RED_FILL
                c.alignment = Alignment(horizontal='left', vertical='center')
                ws.row_dimensions[row].height = 20

                BASIS_HIGHLIGHT = PatternFill('solid', fgColor='FFE4B5')  # moccasin

                for route in routes_with_outliers:
                    r_data   = cust_outs[cust_outs['_route'] == route]
                    pre_rows = r_data[r_data['_row_type'] == 'PRE_REF']
                    pst_rows = r_data[r_data['_row_type'] == 'POST_OUTLIER']
                    if len(pst_rows) == 0:
                        continue

                    ppu_pre_v    = float(r_data['_ppu_pre_route'].iloc[0])
                    # Use the actual basis applied on this route (may differ from customer
                    # default when the fallback dimension was used)
                    route_basis  = str(r_data['_abr_basis'].iloc[0])
                    route_unit   = UNIT_LABELS.get(route_basis, route_basis)
                    # Column headers adapt per route to reflect the actual basis used
                    route_hdrs   = {**{c: c for c in SHOW_COLS},
                                    '_ppu':          f'€/{route_unit}',
                                    '_deviation_pct': f'Δ% €/{route_unit}'}

                    # Route sub-header — shows PPU baseline and the actual basis used
                    row += 1
                    ws.merge_cells(f'A{row}:{d_end}{row}')
                    fallback_note = (f'  [Fallback: {route_basis}]'
                                     if route_basis != abr_basis_col else '')
                    c = ws.cell(row, 1,
                        f'Relation: {route}   |   '
                        f'Ø PRE-Basis (Dinas): {ppu_pre_v:,.2f} €/{route_unit}{fallback_note}   |   '
                        f'{len(pst_rows)} Ausreißer  >7%  €/{route_unit}')
                    c.font  = hfont(bold=True)
                    c.fill  = LIGHT_RED_FILL
                    c.alignment = Alignment(horizontal='left', vertical='center')
                    ws.row_dimensions[row].height = 18

                    # Column headers — highlight the actual billing-basis column
                    row += 1
                    for ci, col_name in enumerate(OUTLIER_SHOW_COLS, 1):
                        lbl = route_hdrs.get(col_name, col_name)
                        c = ws.cell(row, ci, lbl)
                        c.font   = hfont(bold=True)
                        c.fill   = BASIS_HIGHLIGHT if col_name == route_basis else PRE_FILL
                        c.border = thin()
                        c.alignment = Alignment(horizontal='center', wrap_text=True)
                    ws.row_dimensions[row].height = 28

                    def _cells(srow, xrow_fill, xshow_cols, ppu_override=None):
                        """Write one shipment row; returns nothing (uses enclosing `row` via caller)."""
                        for ci, col_name in enumerate(xshow_cols, 1):
                            if col_name == '_ppu':
                                if ppu_override is not None:
                                    val = round(float(ppu_override), 2)
                                else:
                                    raw = srow.get('_ppu', np.nan)
                                    try:    val = round(float(raw), 2)
                                    except: val = ''
                            elif col_name == '_deviation_pct':
                                raw = srow.get('_deviation_pct', np.nan)
                                try:    val = round(float(raw), 2)
                                except: val = ''
                            else:
                                val = srow.get(col_name, '')
                                if not isinstance(val, str) and pd.isna(val):
                                    val = ''
                                if hasattr(val, 'date'):
                                    val = str(val.date())
                            c = ws.cell(row, ci, val)
                            c.fill  = xrow_fill
                            c.border = thin()
                            c.alignment = Alignment(horizontal='center')
                            if col_name == '_ppu' and isinstance(val, (int, float)):
                                c.number_format = '#,##0.00'
                            elif col_name == '_deviation_pct' and isinstance(val, (int, float)):
                                c.number_format = '0.00"%"'
                            elif col_name in NUM_COLS and isinstance(val, (int, float)):
                                c.number_format = ('0.00"%"' if col_name == 'DB II%'
                                                   else '#,##0.00')

                    # PRE reference row — size-matched to typical POST outlier
                    for _, srow in pre_rows.iterrows():
                        row += 1
                        _cells(srow, PRE_FILL, OUTLIER_SHOW_COLS, ppu_override=ppu_pre_v)

                    # POST outlier rows (AX), colour-coded by |Δ% €/unit|
                    for _, srow in pst_rows.iterrows():
                        dev = srow.get('_deviation_pct', np.nan)
                        try:
                            dev_f  = float(dev)
                            is_num = not np.isnan(dev_f)
                        except (TypeError, ValueError):
                            dev_f, is_num = np.nan, False

                        if is_num:
                            if   abs(dev_f) >= 40: row_fill = RED_FILL
                            elif abs(dev_f) >= 20: row_fill = ORANGE_FILL
                            else:                  row_fill = YELLOW_FILL
                        else:
                            row_fill = POST_FILL
                        row += 1
                        _cells(srow, row_fill, OUTLIER_SHOW_COLS)

                    row += 1  # gap between routes

print(f"Added {len(top20_meta)} customer sheets")
wb.save(str(XLSX))
print(f"Saved: {XLSX}")
