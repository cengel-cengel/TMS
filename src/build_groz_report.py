#!/usr/bin/env python3
"""build_groz_report.py — Groz-Beckert DINAS vs AX, nur Rechnungsdaten
Output: output/billing_report/groz_beckert_dinas_vergleich.xlsx (33-Spalten-Format)
"""
import re, glob, math
from pathlib import Path
import fitz, numpy as np, pandas as pd
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
import sys; sys.path.insert(0,'src')
from dinas_pdf_parser import parse_one, flatten
from dinas_bi_enrichment import enrich_customer_bi

DINAS_DIR = Path('/home/user/TMS/data/extracted/v1/Noerpel AI/Groz Beckert/Rechnungen/Rechnungen DINAS')
AX_DIR    = Path('/home/user/TMS/data/extracted/v1/Noerpel AI/Groz Beckert/Rechnungen/Rechnungen AX')
NK_XLSX   = Path('/home/user/TMS/data/extracted/v1/Noerpel AI/Groz Beckert/Nebenbedingungen DINAS/NK Groz.xlsx')
CACHE     = Path('/home/user/TMS/output/dinas_cache_groz_beckert.pkl')
REPORT_DIR = Path('/home/user/TMS/output/billing_report')
OUT       = REPORT_DIR / 'groz_beckert_dinas_vergleich.xlsx'
REPORT_DIR.mkdir(exist_ok=True)
CMAP  = {'A':'AT','B':'BE','E':'ES','F':'FR','H':'HU','I':'IT','L':'LU','N':'NO','P':'PT','S':'SE'}
BANDS = [50,100,150,200,250,300,500,750,1000,2000,3000]
gwb   = lambda kg: next((f'bis{b}kg' for b in BANDS if (lambda v: not math.isnan(v) and v<=b)(float(kg) if str(kg).replace('.','').isdigit() else float('nan'))), '>3000kg') if str(kg).strip() not in ('','nan','None') else '?'

# DINAS: flatten + fix 1-letter country codes and missing kg from label buffer
def dinas_fix(pos):
    r   = flatten(pos)
    lbl = '/'.join(it.get('label','') for it in pos.get('_items',[]))
    if not r.get('empf_land'):
        ae  = re.sub(r'.*Empf\.:\s*','',lbl,1) if 'Empf.:' in lbl else ''
        if 'GROZ' in ae.upper()[:25]:  # import → receiver is DE
            m = re.search(r'(\d{5})\s',lbl); r['empf_land']='DE'; r['empf_plz']=m.group(1) if m else ''
        else:
            hits = re.findall(r'([A-Z]{1,2})-(\d{4,6})',lbl)
            if hits: c,n=hits[-1]; r['empf_land']=CMAP.get(c,c if len(c)==2 else ''); r['empf_plz']=n
    if not r.get('kg_rechnung') or pd.isna(pd.to_numeric(r.get('kg_rechnung'),errors='coerce')):
        m = re.search(r'([\d.]+)\s+k(?:g\b|$)',lbl)
        if m: r['kg_rechnung'] = float(m.group(1).replace('.',''))
    return r

if CACHE.exists():
    pre = pd.read_pickle(CACHE); print(f'DINAS cache: {len(pre)} rows')
else:
    pdfs = glob.glob(str(DINAS_DIR/'*.pdf'))
    print(f'Parsing {len(pdfs)} DINAS PDFs...')
    rows = [dinas_fix(pos) for p in pdfs for pos in parse_one(p)]
    pre  = pd.DataFrame(rows); pre.to_pickle(CACHE); print(f'DINAS: {len(pre)} rows cached')

# POST von vollem BI (KNRs 410912, 490527, 527410, 527373)
_bi_cache = Path('output/bi_cache_groz_beckert.pkl')
_groz_knrs = [410912, 490527, 527410, 527373]
if not _bi_cache.exists():
    print('Lade Groz-Beckert aus vollem BI...')
    _bi_all = pd.read_excel(Path('data/bi_report/Tagesbericht.Einzeldaten.alle.VKA.5.xlsx'), header=0)
    _bi_groz = _bi_all[_bi_all['Kunden Nr BK'].isin(_groz_knrs)].copy()
    _bi_groz.to_pickle(_bi_cache)
else:
    _bi_groz = pd.read_pickle(_bi_cache)
_bi_groz['Leistungsdatum'] = pd.to_datetime(_bi_groz['Leistungsdatum'], errors='coerce')
_post_bi = _bi_groz[_bi_groz['Leistungsdatum'] >= pd.Timestamp('2025-09-26')].copy()

def _bi_num(col):
    return pd.to_numeric(_post_bi[col], errors='coerce').fillna(0) if col in _post_bi.columns else 0.0

post = pd.DataFrame({
    'rn':        _post_bi['Rechnungsnummer'].astype(str),
    'dat':       _post_bi['Leistungsdatum'],
    'land':      _post_bi['Empfänger Land'].astype(str).str.strip(),
    'plz':       _post_bi['Empfänger PLZ'].astype(str).str.strip(),
    'name':      _post_bi['Empfänger Name'].astype(str) if 'Empfänger Name' in _post_bi.columns else '',
    'kg':        pd.to_numeric(_post_bi['Tonnage (eff.)'], errors='coerce'),
    'fracht':    _bi_num('Erlöse Fracht'),
    'diesel':    _bi_num('Erlöse Diesel'),
    'maut':      _bi_num('Erlöse Maut'),
    'peak':      _bi_num('Erlöse Peak'),
    'sonstige':  _bi_num('Erlöse Nebengebühr'),
    'verzollung':_bi_num('Erlöse EUST Zoll'),
    'ax_gesamt': _bi_num('Erloese'),
})
print(f'AX (BI): {len(post)} rows')

# ── Cluster-Setup ─────────────────────────────────────────────────────────────
pre['_kg']  = pd.to_numeric(pre['kg_rechnung'], errors='coerce')
post['_kg'] = pd.to_numeric(post['kg'], errors='coerce')
pre['_p2']  = pre['empf_plz'].astype(str).str[:2]
pre['_cl']  = pre['empf_land'].astype(str).fillna('') + '|' + pre['_p2'] + '|' + pre['_kg'].apply(gwb)
post['_p2'] = post['plz'].astype(str).str[:2]
post['_cl'] = post['land'].astype(str).fillna('') + '|' + post['_p2'] + '|' + post['_kg'].apply(gwb)

pre['_eff_d']   = pre['fracht']  / pre['_kg'].replace(0, np.nan) * 100
post['_eff_ax'] = post['fracht'] / post['_kg'].replace(0, np.nan) * 100
pre['_basispreis']  = None
post['_basispreis'] = None
pre['Soll EUR']  = None
post['Soll EUR'] = None
for df in (pre, post):
    df['_master_nr'] = None; df['_sub_nrs'] = None
    df['_n_subs']    = 0;    df['_ist_master'] = ''

pa = pre.groupby('_cl').agg(
    n_pre=('gesamtbetrag','count'), avg_d=('gesamtbetrag','mean'),
    avg_df=('fracht','mean'), avg_dd=('diesel','mean'), avg_dm=('maut_ssd','mean'),
    avg_eff_d=('_eff_d','mean'), avg_dlv=('_basispreis','mean')).reset_index()
oa = post.groupby('_cl').agg(
    n_post=('ax_gesamt','count'), avg_ax=('ax_gesamt','mean'),
    avg_af=('fracht','mean'), avg_ad=('diesel','mean'), avg_am=('maut','mean'),
    avg_eff_ax=('_eff_ax','mean')).reset_index()
stats = pa.merge(oa, on='_cl', how='inner')
stats = stats[stats['avg_ax'] < stats['avg_d']].copy()
stats['delta'] = stats['avg_ax'] - stats['avg_d']
stats['pct']   = stats['delta'] / stats['avg_d'].replace(0, np.nan) * 100
stats['loss']  = stats['delta'] * stats['n_post']
stats['delta_eff_pct'] = (stats['avg_eff_ax'] - stats['avg_eff_d']) / stats['avg_eff_d'].replace(0, np.nan) * 100

def abw_grund_cluster(r):
    neg = {k:v for k,v in
           {'Fracht': r.avg_af-r.avg_df, 'Diesel': r.avg_ad-r.avg_dd,
            'Maut':   r.avg_am-r.avg_dm}.items() if v < -0.5}
    if not neg: return 'sonstige NK'
    t = sum(neg.values())
    return ', '.join(f'{k} ({v/t*100:+.0f}%)' for k,v in sorted(neg.items(), key=lambda x:x[1])[:2])

stats['abw_grund'] = stats.apply(abw_grund_cluster, axis=1)
stats = stats[stats['delta_eff_pct'].abs() > 5].copy()
stats = stats.sort_values('loss').reset_index(drop=True)
print(f'Cluster (|ΔEff|>5%): {len(stats)}, Sigma Verlust: {stats["loss"].sum():,.0f} EUR')

KUNDE = 'Groz-Beckert KG'
BASIS = 'EUR/100kg'

# ── BI-Enrichment: Coverage stats (Groz uses pre=DINAS, no KNR constant) ─────
print('\n── BI-Enrichment (Groz) ─────────────────────────────────────────────────')
_bi_groz['periode'] = _bi_groz['Leistungsdatum'].apply(
    lambda d: 'POST' if pd.notna(d) and d >= pd.Timestamp('2025-09-26') else 'PRE')
_bi_enriched, _dinas_net, _enrich_stats = enrich_customer_bi(_bi_groz, pre)
s = _enrich_stats
_tmp = _bi_enriched.drop_duplicates('_snr').set_index('_snr')
_flag_kp  = _tmp['flag_komplettpreis'].to_dict()
_flag_sp  = _tmp['flag_bi_split'].to_dict()
_flag_dvp = _tmp['dinas_vs_bi_diff_pct'].to_dict()
_flag_mr  = _tmp['flag_multi_rn_dinas'].fillna(False).to_dict()
del _tmp

# ── NK-Mapping ─────────────────────────────────────────────────────────────────
def get_nk_alt(r):
    fracht  = r.get('fracht') or 0
    diesel  = r.get('diesel') or 0
    maut    = r.get('maut_ssd') or 0
    neben   = r.get('ausfuhr') or 0
    eust    = (r.get('verzollung') or 0) + (r.get('zoll_duty') or 0) + (r.get('zoll_betrag') or 0)
    versich = (r.get('sulphur') or 0) + (r.get('neben_pausch') or 0) + (r.get('redebit') or 0) + (r.get('sonstige') or 0)
    return fracht, diesel, maut, 0, 0, neben, eust, versich

def get_nk_neu(r):
    return (r.get('fracht') or 0, r.get('diesel') or 0,
            r.get('maut') or 0,   0,
            r.get('peak') or 0,   r.get('sonstige') or 0,
            r.get('verzollung') or 0, 0)

def abw_grund_row(nk, soll, erloese):
    if pd.isna(soll) or soll == 0: return 'Soll n/a'
    pct = (erloese - soll) / soll * 100
    return 'OK' if abs(pct) < 5 else ('Unterfakturierung' if pct < 0 else 'Überfakturierung')

# ── Styles ─────────────────────────────────────────────────────────────────────
def fill(h): return PatternFill('solid', fgColor=h)
def fnt(bold=False, color='000000', size=9, italic=False):
    return Font(bold=bold, color=color, size=size, italic=italic)
THIN = Side(border_style='thin', color='BBBBBB')
BRD  = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
EUR_FMT = '#,##0.00'

HDR_COLS = ['System','Auftrags-Nr','Master-Nr','Sub-Nr(n)','Anzahl Subs','Ist Master',
            'Rech.-Nr','Sendungsdatum','Kunde','Land','Empf.PLZ','Vers.PLZ',
            'Gew.band','Zone','Basis','Basis Menge','Basispreis',
            'Eff. Preis','Tonnage kg','Stellplätze','Lademeter','Volumen','Soll EUR',
            'Fracht EUR','Diesel EUR','Maut EUR','Lademittel','Peak EUR',
            'Neben EUR','EUST Zoll','Versich.',
            'Erlöse','Abw. Grund',
            'Komplettpreis','BI-Split','DINAS vs BI %','DINAS Multi-Row']
N = len(HDR_COLS)
EUR_COLS  = {17,18,23,24,25,26,27,28,29,30,31,32}
NUM_RIGHT = {5,16,19,20,21,22, 36}
DATE_COL  = 8
STR_COLS  = {2,3,7}

FILL_HDR  = fill('1F497D')
FILL_CLU  = fill('2E75B6')
FILL_ALT  = fill('BDD7EE')
FILL_NEU  = fill('FCE4D6')
FILL_CTRL = fill('E2EFDA')

def wc(ws, r, c, v=None, f=None, fn=None, al='left', fmt=None, brd=None):
    cell = ws.cell(row=r, column=c)
    if v is not None: cell.value = v
    if f:   cell.fill  = f
    if fn:  cell.font  = fn
    if fmt: cell.number_format = fmt
    if brd: cell.border = brd
    cell.alignment = Alignment(horizontal=al, vertical='center')

def write_row(ws, row, values, row_fill, is_ctrl=False):
    rf = FILL_CTRL if is_ctrl else row_fill
    for ci, v in enumerate(values, 1):
        if v is not None and isinstance(v, float) and math.isnan(v): v = None
        if ci in STR_COLS and v is not None:
            try: v = str(int(float(str(v))))
            except: v = str(v)
        fmt = ('DD.MM.YYYY' if ci == DATE_COL else EUR_FMT if ci in EUR_COLS else None)
        al  = 'right' if ci in EUR_COLS or ci in NUM_RIGHT else 'left'
        wc(ws, row, ci, v, rf, fnt(size=9), al, fmt, BRD)

# ── Sheet 1: Groz-Beckert ──────────────────────────────────────────────────────
def build_main_sheet(ws):
    ws.title = 'Groz-Beckert (PDF-only Vergleich)'
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=N)
    wc(ws,1,1, f'Groz-Beckert KG — Dinas PRE vs AX POST (PDF-only)  |  '
               f'Cluster: {len(stats)}  |  Sigma Verlust: {stats["loss"].sum():,.0f} EUR',
       FILL_HDR, fnt(bold=True, color='FFFFFF', size=12), 'center')

    # ── DQ block + PDF-Coverage ───────────────────────────────────────────
    n_pre_bi   = len(_bi_groz[_bi_groz['periode'] == 'PRE'])
    n_post_bi  = len(_bi_groz[_bi_groz['periode'] == 'POST'])
    _pre_enr   = _bi_enriched[_bi_enriched['periode'] == 'PRE']
    _has_m     = _pre_enr['dinas_netto_compare'].notna()
    _is_mr     = _pre_enr['flag_multi_rn_dinas'].fillna(False)
    n_matched  = int(_has_m.sum())
    n_multi_rn = int((_has_m & _is_mr).sum())
    n_acc_base = n_matched - n_multi_rn
    n_ok       = int((_pre_enr.loc[_has_m & ~_is_mr, 'dinas_vs_bi_diff_pct'].abs() <= 5).sum())
    n_sp       = s['n_split_snrs']
    n_gus      = s['n_gutschrift_solo']
    cov_pct    = n_matched / n_pre_bi * 100 if n_pre_bi else 0
    cov_warn   = '  ⚠ Coverage < 50% — Accuracy auf Stichprobe!' if cov_pct < 50 else ''
    FILL_DQ  = fill('F2F2F2')
    FILL_DQH = fill('D9D9D9')
    FILL_DQW = fill('FFF2CC')
    dq_rows = [
        ('Datenqualität — PDF-Coverage + Accuracy-Basis', None, True),
        ('PRE-Sendungen gesamt (aus bi_raw)', f'{n_pre_bi}  (POST: {n_post_bi})', False),
        ('davon mit DINAS-PDF-Match',
         f'{n_matched} / {n_pre_bi} ({cov_pct:.0f}%){cov_warn}', False),
        ('davon nach Multi-Row-Ausschluss vergleichbar', f'{n_acc_base}', False),
        ('davon im ±5%-Band',
         (f'{n_ok} / {n_acc_base} ({n_ok/n_acc_base*100:.0f}% der Acc.-Basis)  ← Basis-Accuracy'
          if n_acc_base else '–'), False),
        ('Ausschluss-Gründe',
         f'A) Kein DINAS-Match: {n_pre_bi - n_matched}  |  '
         f'B) Sammelposten: {n_sp} ({s["pct_split"]:.0f}%)  |  '
         f'C) Solo-Gutschriften: {n_gus}  |  '
         f'D) DINAS Multi-Row: {n_multi_rn}', False),
        ('Vergleich-Methode',
         'Groz-Beckert: DINAS-PDF direkt vs AX-BI (Leistungsdatum-Split 26.09.2025)', False),
    ]
    for ri, (label, val, is_hdr) in enumerate(dq_rows, 2):
        rf   = FILL_DQH if is_hdr else (FILL_DQW if '⚠' in (val or '') else FILL_DQ)
        fn_l = fnt(bold=is_hdr, size=9)
        fn_v = fnt(bold=False, size=9, italic=True)
        ws.merge_cells(start_row=ri, start_column=1, end_row=ri, end_column=N//2)
        wc(ws, ri, 1, label, rf, fn_l, 'left')
        if val:
            ws.merge_cells(start_row=ri, start_column=N//2+1, end_row=ri, end_column=N)
            wc(ws, ri, N//2+1, val, rf, fn_v, 'left')
    DQ_ROWS = len(dq_rows) + 1
    ws.freeze_panes = f'A{DQ_ROWS + 2}'
    HDR_ROW = DQ_ROWS + 1

    for ci, h in enumerate(HDR_COLS, 1):
        wc(ws, HDR_ROW, ci, h, FILL_HDR, fnt(bold=True, color='FFFFFF', size=9), 'center', brd=BRD)

    row = HDR_ROW
    for _, cl in stats.iterrows():
        ckey  = cl['_cl']
        parts = ckey.split('|')
        land, plz_p, gwband = (parts+['','',''])[:3]

        pre_all   = pre[pre['_cl']==ckey]
        post_all  = post[post['_cl']==ckey]
        post_under = post_all[post_all['fracht'].fillna(float('inf')) < cl.avg_df]
        if len(post_under) == 0:
            post_under = post_all  # show all if none strictly below

        pre_s  = pre_all.head(5)
        post_s = post_under.head(5)

        row += 1
        lbl = (f'▶ GB|{land}|{plz_p}|{gwband}|{BASIS}     '
               f'n_PRE={int(cl.n_pre)}  n_POST={int(cl.n_post)}  '
               f'Ø Dinas={cl.avg_d:,.2f} EUR  Ø AX={cl.avg_ax:,.2f} EUR  '
               f'Δ={cl.delta:,.2f} EUR ({cl.pct:+.1f}%)  '
               f'est.Verlust={cl.loss:,.0f} EUR  |  '
               f'Eff. Dinas={cl.avg_eff_d:,.2f} | Eff. AX={cl.avg_eff_ax:,.2f} | '
               f'ΔEff={cl.delta_eff_pct:+.1f}%  |  {cl.abw_grund}')
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=N)
        wc(ws, row, 1, lbl, FILL_CLU, fnt(bold=True, color='FFFFFF', size=10))

        for _, r in pre_s.iterrows():
            row += 1
            nk      = get_nk_alt(r)
            erloese = r.get('gesamtbetrag') or 0
            soll    = r.get('Soll EUR')
            kg      = r.get('_kg')
            billing_kg = math.ceil(float(kg)/100)*100 if pd.notna(kg) and float(kg) > 0 else None
            eff = r.get('_eff_d')
            _sk = str(r.get('sendungs_nr', ''))
            vals = ['alt', r.get('sendungs_nr'),
                    None, None, 0, '',
                    r.get('rechnung_nr'), r.get('leistungsdatum'), KUNDE,
                    r.get('empf_land'), r.get('empf_plz'), None,
                    gwband, 'n/a', BASIS, billing_kg, None, eff,
                    kg, None, r.get('ldm'), None, soll,
                    *nk,
                    erloese, abw_grund_row(nk, soll, erloese),
                    'JA' if _flag_kp.get(_sk, False) else '',
                    'JA' if _flag_sp.get(_sk, False) else '',
                    _flag_dvp.get(_sk, None),
                    'JA' if _flag_mr.get(_sk, False) else '']
            write_row(ws, row, vals, FILL_ALT)

        for _, r in post_s.iterrows():
            row += 1
            nk      = get_nk_neu(r)
            erloese = r.get('ax_gesamt') or 0
            soll    = r.get('Soll EUR')
            kg      = r.get('_kg')
            billing_kg = math.ceil(float(kg)/100)*100 if pd.notna(kg) and float(kg) > 0 else None
            eff = r.get('_eff_ax')
            _sk = str(r.get('rn', ''))
            vals = ['neu', r.get('rn'),
                    None, None, 0, '',
                    r.get('rn'), r.get('dat'), KUNDE,
                    r.get('land'), r.get('plz'), None,
                    gwband, 'n/a', BASIS, billing_kg, None, eff,
                    kg, None, None, None, soll,
                    *nk,
                    erloese, abw_grund_row(nk, soll, erloese),
                    '', 'JA' if _flag_sp.get(_sk, False) else '', None, None]
            write_row(ws, row, vals, FILL_NEU)

        row += 1

    widths = [8,15,16,30,8,9, 13,12,18,5,8,8, 11,8,10, 9,10,10, 9,9,9,9, 10, 10,9,9,9,9,9,9,9, 11,22, 12,12,10,12]
    for ci, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(ci)].width = w
    ws.row_dimensions[1].height = 20
    ws.row_dimensions[HDR_ROW].height = 18
    return row

# ── Sheet 2: NK_Konditionen ────────────────────────────────────────────────────
def build_nk_sheet(ws):
    ws.title = 'NK_Konditionen'
    nk_wb = load_workbook(NK_XLSX, data_only=True)
    nk_ws = nk_wb.active
    for r_idx, row in enumerate(nk_ws.iter_rows(values_only=True), 1):
        for c_idx, val in enumerate(row, 1):
            ws.cell(row=r_idx, column=c_idx).value = val
    for ci in range(1, (nk_ws.max_column or 19) + 1):
        ws.column_dimensions[get_column_letter(ci)].width = 22

# ── Sheet 3: Accuracy_PRE ─────────────────────────────────────────────────────
def build_accuracy_sheet(ws):
    ws.title = 'Accuracy_PRE'
    ws.freeze_panes = 'A3'
    _pre = _bi_enriched[_bi_enriched['periode'] == 'PRE'].copy()
    _rn_lkp = _dinas_net.set_index('_snr')[['rechnung_nr', 'n_rows']].to_dict('index')
    _pre['rechnung_nr_dinas'] = _pre['_snr'].map(
        lambda s_: _rn_lkp.get(s_, {}).get('rechnung_nr', ''))
    _pre['n_dinas_rows'] = _pre['_snr'].map(
        lambda s_: _rn_lkp.get(s_, {}).get('n_rows', None))
    acc = _pre[_pre['dinas_netto_compare'].notna()].copy()
    acc['diff_eur'] = acc['dinas_vs_bi_diff_eur'].round(2)
    acc['diff_pct'] = acc['dinas_vs_bi_diff_pct'].round(1)
    acc = acc.sort_values('diff_pct', key=abs, ascending=False).reset_index(drop=True)
    n_tot     = len(acc)
    _is_multi = acc['flag_multi_rn_dinas'].fillna(False).astype(bool)
    n_multi   = int(_is_multi.sum())
    n_acc     = n_tot - n_multi
    n_ok_a    = int((acc.loc[~_is_multi, 'diff_pct'].abs() <= 5).sum()) if n_acc else 0
    n_big_a   = int((acc.loc[~_is_multi, 'diff_pct'].abs() > 10).sum()) if n_acc else 0
    n_kp      = int(acc['flag_komplettpreis'].sum())
    n_sp_a    = int(acc['flag_bi_split'].sum())
    n_gus_a   = int(acc['flag_gutschrift_solo'].fillna(False).sum())
    summary = (f'Groz-Beckert KG (multi-KNR) — PRE Accuracy: DINAS Total vs BI Erloese_effektiv  |  '
               f'Rows: {n_tot}  |  Multi-Row (ausgeschl.): {n_multi}  |  Acc.-Basis: {n_acc}  |  '
               f'±5%: {n_ok_a} ({n_ok_a/n_acc*100:.0f}% der Basis)  |  >10% Abw.: {n_big_a}  |  '
               f'Komplettpreis: {n_kp}  |  Sammelposten: {n_sp_a}  |  Solo-Gutschrift: {n_gus_a}')
    ACC_COLS = ['Auftrags-Nr','Rech.-Nr DINAS','Rech.-Nr BI','Datum',
                'Land','Empf.PLZ','Tonnage kg',
                'DINAS Total/Fracht','BI Erloese_eff','Diff EUR','Diff %',
                'Komplettpreis','BI-Split','Solo-Gutschrift','Multi-Row DINAS','Abw. Klasse']
    NA = len(ACC_COLS)
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=NA)
    wc(ws, 1, 1, summary, FILL_HDR, fnt(bold=True, color='FFFFFF', size=10), 'left')
    for ci, h in enumerate(ACC_COLS, 1):
        wc(ws, 2, ci, h, FILL_HDR, fnt(bold=True, color='FFFFFF', size=9), 'center', brd=BRD)
    FILL_OK   = fill('E2EFDA')
    FILL_WARN = fill('FFEB9C')
    FILL_BAD  = fill('FFC7CE')
    FILL_MROW = fill('FFCC99')
    EUR_ACC = {8, 9, 10}; PCT_ACC = {11}
    def abw_klasse(pct):
        if pd.isna(pct): return 'n/a'
        a = abs(pct)
        if a <= 5:  return '±5%'
        if a <= 10: return '5-10%'
        return '>10%'
    rnum = 2
    for _, r in acc.iterrows():
        rnum += 1
        pct   = r['diff_pct']
        is_mr = bool(r.get('flag_multi_rn_dinas', False))
        rf    = FILL_MROW if is_mr else (
                FILL_OK   if pd.notna(pct) and abs(pct) <= 5 else (
                FILL_WARN if pd.notna(pct) and abs(pct) <= 10 else FILL_BAD))
        vals = [
            r.get('Auftragsnummer'), r.get('rechnung_nr_dinas') or '',
            r.get('Rechnungsnummer') or '', r.get('Leistungsdatum') or '',
            r.get('Empfänger Land') or '', r.get('Empfänger PLZ') or '',
            r.get('Tonnage (eff.)'), r.get('dinas_netto_compare'),
            r.get('erloese_fracht_effektiv'), r.get('diff_eur'), pct,
            'JA' if r.get('flag_komplettpreis') else '',
            'JA' if r.get('flag_bi_split') else '',
            'JA' if r.get('flag_gutschrift_solo') else '',
            'JA' if is_mr else '',
            abw_klasse(pct) if not is_mr else 'Multi-Row',
        ]
        for ci, v in enumerate(vals, 1):
            if isinstance(v, float) and math.isnan(v): v = None
            fmt = EUR_FMT if ci in EUR_ACC else ('#,##0.0"%"' if ci in PCT_ACC else None)
            al  = 'right' if ci in EUR_ACC or ci in PCT_ACC else 'left'
            if ci in {1, 2, 3} and v is not None:
                try: v = str(int(float(str(v))))
                except: v = str(v)
            wc(ws, rnum, ci, v, rf, fnt(size=9), al, fmt, BRD)
    col_widths = [15, 14, 14, 12, 6, 8, 10, 12, 12, 10, 8, 10, 8, 12, 12, 10]
    for ci, w in enumerate(col_widths, 1):
        ws.column_dimensions[get_column_letter(ci)].width = w
    ws.row_dimensions[1].height = 18
    ws.row_dimensions[2].height = 16
    return rnum

# ── Schreiben ──────────────────────────────────────────────────────────────────
wb = Workbook()
last_row = build_main_sheet(wb.active)
build_nk_sheet(wb.create_sheet('NK_Konditionen'))
acc_rows = build_accuracy_sheet(wb.create_sheet('Accuracy_PRE'))
wb.save(OUT)
print(f'\nGespeichert: {OUT}')
print(f'  Sheet "Groz-Beckert (PDF-only Vergleich)": {last_row} Zeilen')
print(f'  Sheet "NK_Konditionen": NK Groz.xlsx kopiert')
print(f'  Sheet "Accuracy_PRE":   {acc_rows-2} Rows')
