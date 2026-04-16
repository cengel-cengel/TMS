#!/usr/bin/env python3
"""
build_helu_report_v2.py
=======================
Erstellt output/billing_report/helu_dinas_vergleich.xlsx
im GEZE-Cluster-Format mit:
  Sheet 1 "Helu GmbH"     — 25-Spalten Cluster-Vergleich (alt/neu, ▶-Header)
  Sheet 2 "NK_Konditionen" — NK Helu.xlsx kopiert
"""

import math
from pathlib import Path
import numpy as np
import pandas as pd
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

SRC_XLSX    = Path('/home/user/TMS/output/helu_dinas_vergleich.xlsx')
CLUSTER_XLS = Path('/home/user/TMS/output/cluster_vergleich/408244_HELU_KABEL_GMBH_cluster.xlsx')
NK_XLSX     = Path('/home/user/TMS/data/extracted/v1/Noerpel AI/Helu/Nebenbedingungen DINAS/NK Helu.xlsx')
REPORT_DIR  = Path('/home/user/TMS/output/billing_report')
OUT_XLSX    = REPORT_DIR / 'helu_dinas_vergleich.xlsx'
REPORT_DIR.mkdir(exist_ok=True)

KNR    = 408244
KUNDE  = 'HELU KABEL GmbH'
BASIS  = 'EUR/100kg'

BANDS = [50,100,150,200,250,300,500,750,1000,2000,3000]
def gew_band(kg):
    try: kg = float(kg)
    except: return '?'
    if math.isnan(kg) or kg <= 0: return '?'
    for b in BANDS:
        if kg <= b: return f'bis {b}kg'
    return 'ueber 3000kg'

def norm_id(v):
    try: return str(int(float(str(v))))
    except: return str(v).strip()

# ── Daten laden ────────────────────────────────────────────────────────────
pre  = pd.read_excel(SRC_XLSX, sheet_name='PRE Dinas Detail',  header=2)
post = pd.read_excel(SRC_XLSX, sheet_name='POST AX Detail',    header=2)

for df in (pre, post):
    df['Tonnage (eff.)'] = pd.to_numeric(df['Tonnage (eff.)'], errors='coerce')
    df['_plz2']  = df['Empfänger PLZ'].astype(str).str.strip().str[:2]
    df['_land']  = df['Empfänger Land'].astype(str).str.strip()
    df['_vplz2'] = df['Versender PLZ'].astype(str).str.strip().str[:2]
    df['_gwb']   = df['Tonnage (eff.)'].apply(gew_band)
    df['_cl']    = df['_land'] + '|' + df['_plz2'] + '|' + df['_gwb']

PRE_NK  = ['Dinas Fracht','Dinas Diesel','Dinas Maut/SSD','Dinas Ausfuhr',
           'Dinas Verzollung','Dinas Zoll Duty','Dinas Zollbetrag',
           'Dinas Sulphur','Dinas Nebenkostenpausch.','Dinas Redebit',
           'Dinas Sonstige','Dinas Gesamt']
POST_NK = ['AX Fracht','AX Diesel','AX Maut','AX Nebengebühr',
           'AX Lademittel','AX Peak','AX EUST/Zoll','AX Versicherung','AX Gesamt']
for c in PRE_NK:  pre[c]  = pd.to_numeric(pre.get(c),  errors='coerce')
for c in POST_NK: post[c] = pd.to_numeric(post.get(c), errors='coerce')

# ── Soll EUR joinen ────────────────────────────────────────────────────────
cl_df = pd.read_excel(CLUSTER_XLS, sheet_name=0)
alt_cl = cl_df[cl_df['System']=='alt'][['Auftrags-Nr','Soll EUR']].copy()
neu_cl = cl_df[cl_df['System']=='neu'][['Auftrags-Nr','Soll EUR']].copy()
for df in (alt_cl, neu_cl):
    df['_aid'] = df['Auftrags-Nr'].apply(norm_id)
    df['Soll EUR'] = pd.to_numeric(df['Soll EUR'], errors='coerce')
soll_pre  = alt_cl.dropna(subset=['Soll EUR']).set_index('_aid')['Soll EUR'].to_dict()
soll_post = neu_cl.dropna(subset=['Soll EUR']).set_index('_aid')['Soll EUR'].to_dict()
pre['_aid']      = pre['Auftragsnummer'].apply(norm_id)
post['_aid']     = post['Auftragsnummer'].apply(norm_id)
pre['Soll EUR']  = pre['_aid'].map(soll_pre)
post['Soll EUR'] = post['_aid'].map(soll_post)
print(f'Soll EUR: PRE {pre["Soll EUR"].notna().sum()}/{len(pre)}, '
      f'POST {post["Soll EUR"].notna().sum()}/{len(post)}')

# ── Cluster-Statistiken ────────────────────────────────────────────────────
pa = pre.groupby('_cl').agg(
    n_pre=('Dinas Gesamt','count'), avg_d=('Dinas Gesamt','mean'),
    avg_df=('Dinas Fracht','mean'), avg_dd=('Dinas Diesel','mean'),
    avg_dm=('Dinas Maut/SSD','mean'), vplz2=('_vplz2','first')).reset_index()
oa = post.groupby('_cl').agg(
    n_post=('AX Gesamt','count'), avg_ax=('AX Gesamt','mean'),
    avg_af=('AX Fracht','mean'), avg_ad=('AX Diesel','mean'),
    avg_am=('AX Maut','mean')).reset_index()
stats = pa.merge(oa, on='_cl', how='inner')
stats = stats[stats['avg_ax'] < stats['avg_d']].copy()
stats['delta']  = stats['avg_ax'] - stats['avg_d']
stats['pct']    = stats['delta'] / stats['avg_d'].replace(0, np.nan) * 100
stats['loss']   = stats['delta'] * stats['n_post']

def abw_grund_cluster(r):
    neg = {k:v for k,v in
           {'Fracht': r.avg_af-r.avg_df, 'Diesel': r.avg_ad-r.avg_dd,
            'Maut':   r.avg_am-r.avg_dm}.items() if v < -0.5}
    if not neg: return 'sonstige NK'
    t = sum(neg.values())
    return ', '.join(f'{k} ({v/t*100:+.0f}%)'
                     for k,v in sorted(neg.items(), key=lambda x:x[1])[:2])

stats['abw_grund'] = stats.apply(abw_grund_cluster, axis=1)
stats = stats.sort_values('loss').reset_index(drop=True)
print(f'Cluster: {len(stats)}, Sigma Verlust: {stats["loss"].sum():,.0f} EUR')

# ── NK-Mapping: Dinas→unified / AX→unified ────────────────────────────────
def get_unified_nk_alt(r):
    """Map Dinas NK cols → 8 unified NK columns."""
    fracht   = r.get('Dinas Fracht') or 0
    diesel   = r.get('Dinas Diesel') or 0
    maut     = r.get('Dinas Maut/SSD') or 0
    lademl   = 0
    peak     = 0
    neben    = r.get('Dinas Ausfuhr') or 0
    eust     = (r.get('Dinas Verzollung') or 0) + (r.get('Dinas Zoll Duty') or 0) + (r.get('Dinas Zollbetrag') or 0)
    versich  = (r.get('Dinas Sulphur') or 0) + (r.get('Dinas Nebenkostenpausch.') or 0) + \
               (r.get('Dinas Redebit') or 0)  + (r.get('Dinas Sonstige') or 0)
    return fracht, diesel, maut, lademl, peak, neben, eust, versich

def get_unified_nk_neu(r):
    """Map AX NK cols → 8 unified NK columns."""
    fracht  = r.get('AX Fracht') or 0
    diesel  = r.get('AX Diesel') or 0
    maut    = r.get('AX Maut') or 0
    lademl  = r.get('AX Lademittel') or 0
    peak    = r.get('AX Peak') or 0
    neben   = r.get('AX Nebengebühr') or 0
    eust    = r.get('AX EUST/Zoll') or 0
    versich = r.get('AX Versicherung') or 0
    return fracht, diesel, maut, lademl, peak, neben, eust, versich

def abw_grund_row(nk_tuple, soll, erloese):
    """Per-Zeile Abweichungsgrund."""
    if pd.isna(soll) or soll == 0:
        return 'Soll n/a'
    abw_pct = (erloese - soll) / soll * 100 if soll else 0
    if abs(abw_pct) < 5:
        return 'OK'
    fracht, diesel, maut, *_ = nk_tuple
    # Could expand with more detail — keep simple
    if abw_pct < -5:
        return 'Unterfakturierung'
    return 'Überfakturierung'

# ── Styles ─────────────────────────────────────────────────────────────────
def fill(h): return PatternFill('solid', fgColor=h)
def fnt(bold=False, color='000000', size=9, italic=False):
    return Font(bold=bold, color=color, size=size, italic=italic)
THIN  = Side(border_style='thin',   color='BBBBBB')
BRD   = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
EUR_FMT = '#,##0.00'
PCT_FMT = '+0.0%;-0.0%;0.0%'

HDR_COLS = ['System','Auftrags-Nr','Rech.-Nr','Kunde','Land','Empf.PLZ','Vers.PLZ',
            'Gew.band','Zone','Basis','Tonnage kg','Soll EUR',
            'Fracht EUR','Diesel EUR','Maut EUR','Lademittel','Peak EUR',
            'Neben EUR','EUST Zoll','Versich.','NK Summe','Erlöse',
            'Abw. EUR','Abw. %','Abw. Grund']
N = len(HDR_COLS)  # 25

EUR_COLS = {12,13,14,15,16,17,18,19,20,21,22}  # 1-based indices of EUR columns
PCT_COL  = 23
KG_COL   = 10

FILL_HDR   = fill('1F497D')
FILL_CLU   = fill('2E75B6')
FILL_ALT   = fill('BDD7EE')
FILL_NEU   = fill('FCE4D6')
FILL_CTRL  = fill('E2EFDA')
FILL_STATS = fill('D9E1F2')

def wc(ws, r, c, v=None, f=None, fn=None, al='left', fmt=None, brd=None):
    cell = ws.cell(row=r, column=c)
    if v is not None: cell.value = v
    if f:   cell.fill  = f
    if fn:  cell.font  = fn
    if fmt: cell.number_format = fmt
    if brd: cell.border = brd
    cell.alignment = Alignment(horizontal=al, vertical='center', wrap_text=False)

def write_row(ws, row, values, row_fill, is_ctrl=False):
    rf = FILL_CTRL if is_ctrl else row_fill
    for ci, v in enumerate(values, 1):
        if v is not None and isinstance(v, float) and math.isnan(v): v = None
        fmt = None
        al  = 'left'
        if ci in EUR_COLS: fmt = EUR_FMT; al = 'right'
        elif ci == PCT_COL: fmt = PCT_FMT; al = 'right'
        elif ci == KG_COL:  al = 'right'
        wc(ws, row, ci, v, rf, fnt(size=9), al, fmt, BRD)

# ── Sheet 1: Helu GmbH ────────────────────────────────────────────────────
def build_main_sheet(ws):
    ws.title = 'Helu GmbH'
    ws.freeze_panes = 'A3'

    # Title rows
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=N)
    wc(ws,1,1, f'HELU KABEL GmbH ({KNR}) — Dinas PRE vs AX POST  |  '
               f'Cluster: {len(stats)}  |  '
               f'Sigma Verlust: {stats["loss"].sum():,.0f} EUR',
       FILL_HDR, fnt(bold=True, color='FFFFFF', size=12), 'center')

    # Column headers
    for ci, h in enumerate(HDR_COLS, 1):
        wc(ws, 2, ci, h, FILL_HDR, fnt(bold=True, color='FFFFFF', size=9), 'center', brd=BRD)

    row = 2

    for _, cl in stats.iterrows():
        ckey   = cl['_cl']
        parts  = ckey.split('|')
        land   = parts[0] if len(parts)>0 else ''
        plz_p  = parts[1] if len(parts)>1 else ''
        gwband = parts[2] if len(parts)>2 else ''
        vplz   = str(cl.get('vplz2',''))

        pre_rows  = pre[pre['_cl']==ckey].head(5)
        post_rows = post[post['_cl']==ckey].head(5)

        # Find Kontroll-Paar
        ctrl_pi, ctrl_oi = None, None
        best = float('inf')
        pre_all  = pre[pre['_cl']==ckey]
        post_all = post[post['_cl']==ckey]
        for pi, pr in pre_all.iterrows():
            pr_kg = pr.get('Tonnage (eff.)')
            if pd.isna(pr_kg): continue
            for oi, po in post_all.iterrows():
                po_kg = po.get('Tonnage (eff.)')
                if pd.isna(po_kg): continue
                d = abs(float(pr_kg)-float(po_kg))
                if d < best: best=d; ctrl_pi=pi; ctrl_oi=oi

        # Cluster header row
        row += 1
        clu_label = (f'▶ {KNR}|{vplz}|{land}|{plz_p}|{gwband}|{BASIS}     '
                     f'n_PRE={int(cl.n_pre)}  n_POST={int(cl.n_post)}  '
                     f'Ø Dinas={cl.avg_d:,.2f} EUR  Ø AX={cl.avg_ax:,.2f} EUR  '
                     f'Δ={cl.delta:,.2f} EUR ({cl.pct:+.1f}%)  '
                     f'est.Verlust={cl.loss:,.0f} EUR  |  {cl.abw_grund}')
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=N)
        wc(ws, row, 1, clu_label, FILL_CLU, fnt(bold=True, color='FFFFFF', size=10))

        # alt rows (Dinas)
        for _, r in pre_rows.iterrows():
            row += 1
            nk = get_unified_nk_alt(r)
            nk_sum = sum(nk)
            erloese = r.get('Dinas Gesamt') or 0
            soll    = r.get('Soll EUR')
            is_ctrl = (r.name == ctrl_pi)
            vals = [
                'alt',
                r.get('Auftragsnummer'), r.get('Rechnungsnummer'), KUNDE,
                r.get('Empfänger Land'), r.get('Empfänger PLZ'), r.get('Versender PLZ'),
                gwband, 'n/a', BASIS,
                r.get('Tonnage (eff.)'), soll,
                *nk,          # 8 NK cols
                nk_sum,       # NK Summe
                erloese,      # Erlöse
                None, None,   # Abw. EUR / Abw. % → not meaningful for alt reference
                'PRE (Referenz)',
            ]
            write_row(ws, row, vals, FILL_ALT, is_ctrl)

        # neu rows (AX)
        for _, r in post_rows.iterrows():
            row += 1
            nk = get_unified_nk_neu(r)
            nk_sum  = sum(nk)
            erloese = r.get('AX Gesamt') or 0
            soll    = r.get('Soll EUR')
            abw_eur = (erloese - soll) if pd.notna(soll) else None
            abw_pct = (abw_eur / soll)  if (abw_eur is not None and soll) else None
            is_ctrl = (r.name == ctrl_oi)
            grund   = abw_grund_row(nk, soll, erloese)
            vals = [
                'neu',
                r.get('Auftragsnummer'), r.get('Rechnungsnummer'), KUNDE,
                r.get('Empfänger Land'), r.get('Empfänger PLZ'), r.get('Versender PLZ'),
                gwband, 'n/a', BASIS,
                r.get('Tonnage (eff.)'), soll,
                *nk,
                nk_sum, erloese,
                abw_eur, abw_pct,
                grund,
            ]
            write_row(ws, row, vals, FILL_NEU, is_ctrl)

        row += 1  # Leerzeile

    # Spaltenbreiten
    widths = [8,15,13,18,5,8,8,11,6,10,9,10, 10,9,9,9,9,9,9,9, 11,11,11,9,22]
    for ci, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(ci)].width = w
    ws.row_dimensions[1].height = 20
    ws.row_dimensions[2].height = 18

    return row

# ── Sheet 2: NK_Konditionen ───────────────────────────────────────────────
def build_nk_sheet(ws):
    ws.title = 'NK_Konditionen'
    nk_wb = load_workbook(NK_XLSX, data_only=True)
    nk_ws = nk_wb.active
    for r_idx, row in enumerate(nk_ws.iter_rows(values_only=True), 1):
        for c_idx, val in enumerate(row, 1):
            ws.cell(row=r_idx, column=c_idx).value = val
    # Basic column widths
    for ci in range(1, (nk_ws.max_column or 19) + 1):
        ws.column_dimensions[get_column_letter(ci)].width = 22

# ── Schreiben ──────────────────────────────────────────────────────────────
wb = Workbook()
last_row = build_main_sheet(wb.active)
build_nk_sheet(wb.create_sheet('NK_Konditionen'))
wb.save(OUT_XLSX)

print(f'\nGespeichert: {OUT_XLSX}')
print(f'  Sheet "Helu GmbH":      {last_row} Zeilen')
print(f'  Sheet "NK_Konditionen": NK Helu.xlsx kopiert')
