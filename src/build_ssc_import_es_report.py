#!/usr/bin/env python3
"""build_ssc_import_es_report.py — SSC (KNR 511241) Import aus Spanien, Vollanalyse"""
import glob as _glob, math, re
from pathlib import Path
import numpy as np, pandas as pd
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
import sys; sys.path.insert(0, 'src')
from dinas_pdf_parser import parse_one, flatten
from tms.billing import aggregate_dinas_per_invoice

BI_PKL    = Path('output/bi_top20_data.pkl')
NK_XLSX   = Path('data/extracted/v1/Noerpel AI/SIka/Nebenbedingungen DINAS/NK Sika.xlsx')
IMPORT_DLV_2025 = Path('data/extracted/v1/Noerpel AI/SIka/DLV/SIKA Deutschland GmbH Stuttgart/2025/20250109_Sika Supply_Import Spanien und Italien 2025.xlsx')
IMPORT_DLV_2026 = Path('data/extracted/v1/Noerpel AI/SIka/DLV/SIKA Deutschland GmbH Stuttgart/2026/20251216_Sika Supply_Import Spanien und Italien 2026.xlsx')
DINAS_DIR = Path('data/extracted/sika_ssc/Dinas SSC')
CACHE     = Path('output/dinas_cache_ssc_511241.pkl')
OUT_XLSX  = Path('output/billing_report/ssc_import_es_vollanalyse.xlsx')
OUT_XLSX.parent.mkdir(exist_ok=True)
KNR, KUNDE, BASIS = 511241, 'Sika Supply Center GmbH', 'EUR/Stpl'

STPL_BANDS = [2, 5, 10, 20, 33]
def stpl_band(n):
    try: n = float(n)
    except: return '?'
    if math.isnan(n) or n <= 0: return '?'
    for b in STPL_BANDS:
        if n <= b: return f'bis {b} Stpl'
    return 'ueber 33 Stpl'

# ── DLV Import Spanien → DE (Stellplatz-Festpreis, single route) ──────────
def _load_import_rates(path):
    df = pd.read_excel(path, sheet_name=0, header=None)
    rates = {}
    for _, r in df.iloc[16:55].iterrows():
        n = r.iloc[0]; price = r.iloc[2]
        if pd.isna(n) or pd.isna(price): continue
        try: rates[int(float(n))] = float(price)
        except (ValueError, TypeError): pass
    return rates

def lookup_import_es(rates_2025, rates_2026, leistungsdatum, n_stpl):
    rates = rates_2026 if pd.Timestamp(leistungsdatum) >= pd.Timestamp('2025-09-26') else rates_2025
    n = max(1, min(n_stpl, max(rates)))
    return rates.get(n)

# ── Master/Sub-Konsolidierung ──────────────────────────────────────────────
_ms_map_cache = None

def norm_ms(v):
    try: return str(int(float(str(v).strip())))
    except: return str(v).strip()

def _get_ms_map():
    global _ms_map_cache
    if _ms_map_cache is not None: return _ms_map_cache
    _bi = pd.read_pickle(BI_PKL)['df']
    _bi = _bi[['Auftragsnummer','Mastersendung','Unterauftrag']].copy()
    _bi['_aid'] = _bi['Auftragsnummer'].astype(str).str.strip().apply(norm_ms)
    _bi['_ms']  = _bi['Mastersendung'].apply(lambda v: norm_ms(v) if pd.notna(v) else '')
    _ms_map_cache = _bi.drop_duplicates('_aid').set_index('_aid')[['_ms','Unterauftrag']]
    return _ms_map_cache

def enrich_master_sub(df):
    fin_cols = ['AX Fracht','AX Diesel','AX Maut','AX Nebengebühr',
                'AX Lademittel','AX Peak','AX EUST/Zoll','AX Versicherung','AX Gesamt']
    msmap = _get_ms_map()
    df = df.copy()
    aid = df['Auftragsnummer'].astype(str).str.strip().apply(norm_ms)
    ms  = aid.map(msmap['_ms']).fillna('')
    ua  = aid.map(msmap['Unterauftrag'])
    df['_is_master']  = (ms.values == aid.values) & (ms.values != '')
    df['_is_sub']     = (ms.values != '') & ~df['_is_master']
    df['_ms_ref']     = ms.values
    df['_unterauftr'] = ua.values
    subs = df[df['_is_sub']]
    if len(subs) > 0:
        present = [c for c in fin_cols if c in df.columns]
        for c in present: df[c] = pd.to_numeric(df[c], errors='coerce')
        ssums = subs.groupby('_ms_ref')[present].sum()
        for c in present:
            msk = df['_is_master']
            df.loc[msk, c] = df.loc[msk,'_ms_ref'].map(ssums[c]).fillna(df.loc[msk,c])
    df['_master_nr']  = ms.where(ms != '', None).values
    df['_sub_nrs']    = df.apply(
        lambda r: str(r['_unterauftr']) if r['_is_master'] and pd.notna(r['_unterauftr']) else None, axis=1)
    df['_n_subs']     = df['_sub_nrs'].apply(lambda v: len(v.split(',')) if isinstance(v, str) and v else 0)
    df['_ist_master'] = df['_is_master'].map({True:'Ja', False:''})
    n_sub = df['_is_sub'].sum()
    df = df[~df['_is_sub']].copy()
    print(f'  Master/Sub: {n_sub} Subs entfernt, {df["_is_master"].sum()} Masters angereichert')
    return df

def add_empty_master_cols(df):
    df = df.copy()
    for c in ('_master_nr','_sub_nrs','_ist_master'): df[c] = None
    df['_n_subs'] = 0
    return df

print('Lade Import-ES DLV...')
rates_2025 = _load_import_rates(IMPORT_DLV_2025)
rates_2026 = _load_import_rates(IMPORT_DLV_2026)
print(f'Import DLV: 2025={len(rates_2025)} Stpl-Stufen, 2026={len(rates_2026)} Stpl-Stufen')

# ── Daten laden aus BI-Pickle (KNR 511241, nur Export) ────────────────────
_bi = pd.read_pickle(BI_PKL)['df']
_ssc = _bi[(_bi['Kunden Nr BK'] == 511241) & (_bi['Versender Land'].str.upper().str.strip() == 'ES')].copy()
pre  = _ssc[_ssc['periode'] == 'PRE'].copy()
post = _ssc[_ssc['periode'] == 'POST'].copy()
print(f'SSC geladen: {len(pre)} PRE, {len(post)} POST (nur Export)')

# POST: Erlöse-Spalten → AX-Namen
post = post.rename(columns={
    'Erlöse Fracht': 'AX Fracht', 'Erlöse Diesel': 'AX Diesel',
    'Erlöse Maut': 'AX Maut', 'Erlöse Nebengebühr': 'AX Nebengebühr',
    'Erlöse Lademittel': 'AX Lademittel', 'Erlöse Peak': 'AX Peak',
    'Erlöse EUST Zoll': 'AX EUST/Zoll', 'Erlöse Transportversicherung': 'AX Versicherung',
    'Erloese': 'AX Gesamt',
})

for df, name in [(pre,'PRE'),(post,'POST')]:
    bad = df['Rechnungsnummer'].apply(
        lambda v: str(v).strip().rstrip('0').rstrip('.') in ('0','','nan'))
    if bad.sum():
        print(f'Filtere {bad.sum()} {name} Zeilen RN=0')
        df.drop(index=df[bad].index, inplace=True)

POST_NK = ['AX Fracht','AX Diesel','AX Maut','AX Nebengebühr',
           'AX Lademittel','AX Peak','AX EUST/Zoll','AX Versicherung','AX Gesamt']
for c in POST_NK: post[c] = pd.to_numeric(post.get(c), errors='coerce')

# ── DINAS-NK: per-Sendung aus Cache ────────────────────────────────────────
if CACHE.exists():
    dinas_cache = pd.read_pickle(CACHE)
    print(f'DINAS cache: {len(dinas_cache)} Positionen')
else:
    pdfs = _glob.glob(str(DINAS_DIR / '*.pdf'))
    rows = [flatten(pos) for p in pdfs for pos in parse_one(p)]
    dinas_cache = pd.DataFrame(rows)
    dinas_cache.to_pickle(CACHE)
    print(f'Cache gespeichert: {len(dinas_cache)} Positionen')

# v1.9 §2e Rule B: per-Rechnung Routing-Key-Aggregation (SSC Import ES/IT)
dinas_rk_agg = aggregate_dinas_per_invoice(
    dinas_cache,
    rn_col='rechnung_nr',
    sender_plz_col='empf_land',
    empf_plz_col='empf_plz',
    date_col='leistungsdatum',
    agg_cols=['fracht', 'diesel', 'maut_ssd', 'gesamtbetrag', 'stellplaetze', 'ldm'],
)
_n_multi = (dinas_rk_agg['n_positionen'] > 1).sum()
print(f'Dinas RK-Aggregat: {len(dinas_rk_agg)} Gruppen '
      f'({_n_multi} mit >1 Position je Routing-Key)')

def _norm(v):
    s = re.sub(r'\D', '', str(v)).lstrip('0')
    return s if s else str(v).strip()

dinas_cache['_snr'] = dinas_cache['sendungs_nr'].astype(str).apply(_norm)
pre['_snr'] = pre['Auftragsnummer'].astype(str).apply(_norm)
PRE_NK = ['Dinas Fracht','Dinas Diesel','Dinas Maut/SSD','Dinas Ausfuhr',
          'Dinas Verzollung','Dinas Zoll Duty','Dinas Zollbetrag',
          'Dinas Sulphur','Dinas Nebenkostenpausch.','Dinas Redebit',
          'Dinas Sonstige','Dinas Gesamt']
pre.drop(columns=[c for c in PRE_NK if c in pre.columns], inplace=True)
DINAS_RENAME = {
    'fracht':'Dinas Fracht', 'diesel':'Dinas Diesel', 'maut_ssd':'Dinas Maut/SSD',
    'ausfuhr':'Dinas Ausfuhr', 'verzollung':'Dinas Verzollung',
    'zoll_duty':'Dinas Zoll Duty', 'zoll_betrag':'Dinas Zollbetrag',
    'sulphur':'Dinas Sulphur', 'neben_pausch':'Dinas Nebenkostenpausch.',
    'redebit':'Dinas Redebit', 'sonstige':'Dinas Sonstige', 'gesamtbetrag':'Dinas Gesamt',
    'ldm':'Dinas LDM',
}
cache_nk = dinas_cache.rename(columns=DINAS_RENAME)[['_snr']+list(DINAS_RENAME.values())].copy()
pre = pre.merge(cache_nk, on='_snr', how='left')
pre.drop(columns=['_snr'], inplace=True)
for c in PRE_NK: pre[c] = pd.to_numeric(pre.get(c), errors='coerce')
print(f'DINAS re-joined: {pre["Dinas Fracht"].notna().sum()}/{len(pre)} PRE')
pre = pre[pre['Dinas Fracht'].fillna(0) > 0].copy()

# ── Stellplätze ────────────────────────────────────────────────────────────
def _stpl_from_ldm(ldm):
    return max(1, math.ceil(float(ldm) / 0.4))

def _stpl_inverse(gesamt, rates):
    """Back-calculate n_stpl from billed amount using closest rate."""
    gesamt = float(gesamt or 0)
    if gesamt <= 0: return 1
    best_n, best_d = 1, float('inf')
    for n, r in rates.items():
        if abs(r - gesamt) < best_d:
            best_d = abs(r - gesamt)
            best_n = n
    return best_n

def _pre_stpl(r):
    # 1) DINAS LDM from cache
    for col in ('Dinas LDM', 'Lademeter'):
        v = pd.to_numeric(r.get(col), errors='coerce')
        if pd.notna(v) and v > 0:
            return _stpl_from_ldm(v)
    # 2) Back-calculate from Dinas Gesamt (assumes DINAS billed per DLV)
    gesamt = pd.to_numeric(r.get('Dinas Gesamt'), errors='coerce')
    if pd.notna(gesamt) and gesamt > 0:
        return _stpl_inverse(gesamt, rates_2025)
    return 1

pre['_stpl'] = pre.apply(_pre_stpl, axis=1)

def _post_stpl(r):
    stpl = pd.to_numeric(r.get('Stellplätze'), errors='coerce')
    if pd.notna(stpl) and stpl > 0:
        return max(1, int(math.ceil(stpl)))
    ldm = pd.to_numeric(r.get('Lademeter'), errors='coerce')
    if pd.notna(ldm) and ldm > 0:
        return _stpl_from_ldm(ldm)
    return 1

post['_stpl'] = post.apply(_post_stpl, axis=1)

print('Konsolidiere Master/Sub-Sendungen...')
post = enrich_master_sub(post)
pre  = add_empty_master_cols(pre)

for df in (pre, post):
    df['_land']  = df['Empfänger Land'].astype(str).str.strip()
    df['_plz2']  = df['Empfänger PLZ'].astype(str).str.strip().str[:2]
    df['_vplz2'] = df['Versender PLZ'].astype(str).str.strip().str[:2]
    df['_sb']    = df['_stpl'].apply(stpl_band)
    df['_cl']    = df['_land'] + '|' + df['_plz2'] + '|' + df['_sb']

pre['_eff']  = pre['Dinas Fracht']  / pre['_stpl']
post['_eff'] = post['AX Fracht']    / post['_stpl']

# ── Soll EUR via Import-ES DLV ─────────────────────────────────────────────
print('Berechne Soll EUR (Import ES DLV)...')
pre['Soll EUR']  = pre.apply(
    lambda r: lookup_import_es(rates_2025, rates_2026, r['Leistungsdatum'], int(r['_stpl'])), axis=1)
post['Soll EUR'] = post.apply(
    lambda r: lookup_import_es(rates_2025, rates_2026, r['Leistungsdatum'], int(r['_stpl'])), axis=1)
print(f'Soll EUR: PRE {pre["Soll EUR"].notna().sum()}/{len(pre)}, POST {post["Soll EUR"].notna().sum()}/{len(post)}')

# ── Cluster-Statistiken ────────────────────────────────────────────────────
pa = pre.groupby('_cl').agg(
    n_pre=('Dinas Gesamt','count'), avg_d=('Dinas Gesamt','mean'),
    avg_df=('Dinas Fracht','mean'), avg_dd=('Dinas Diesel','mean'),
    avg_dm=('Dinas Maut/SSD','mean'), vplz2=('_vplz2','first'),
    avg_eff_d=('_eff','mean'), avg_dlv=('Soll EUR','mean')).reset_index()
oa = post.groupby('_cl').agg(
    n_post=('AX Gesamt','count'), avg_ax=('AX Gesamt','mean'),
    avg_af=('AX Fracht','mean'), avg_ad=('AX Diesel','mean'),
    avg_am=('AX Maut','mean'), avg_eff_ax=('_eff','mean')).reset_index()
stats = pa.merge(oa, on='_cl', how='outer').fillna(0)
stats['delta'] = stats['avg_ax'] - stats['avg_d']
stats['pct']   = stats['delta'] / stats['avg_d'].replace(0, np.nan) * 100
stats['loss']  = stats['delta'] * stats['n_post']
stats['delta_eff_pct'] = ((stats['avg_eff_ax'] - stats['avg_eff_d'])
                          / stats['avg_eff_d'].replace(0, np.nan) * 100)
stats = stats.sort_values('_cl').reset_index(drop=True)
print(f'Cluster (|ΔEff|>5%): {len(stats)}, Sigma Verlust: {stats["loss"].sum():,.0f} EUR')

# ── NK-Mapping ─────────────────────────────────────────────────────────────
def get_nk_alt(r):
    fracht = r.get('Dinas Fracht') or 0; diesel = r.get('Dinas Diesel') or 0
    maut   = r.get('Dinas Maut/SSD') or 0; neben  = r.get('Dinas Ausfuhr') or 0
    eust   = ((r.get('Dinas Verzollung') or 0) + (r.get('Dinas Zoll Duty') or 0)
               + (r.get('Dinas Zollbetrag') or 0))
    versich = ((r.get('Dinas Sulphur') or 0) + (r.get('Dinas Nebenkostenpausch.') or 0)
               + (r.get('Dinas Redebit') or 0) + (r.get('Dinas Sonstige') or 0))
    return fracht, diesel, maut, 0, 0, neben, eust, versich

def get_nk_neu(r):
    return (r.get('AX Fracht') or 0, r.get('AX Diesel') or 0,
            r.get('AX Maut') or 0, r.get('AX Lademittel') or 0,
            r.get('AX Peak') or 0, r.get('AX Nebengebühr') or 0,
            r.get('AX EUST/Zoll') or 0, r.get('AX Versicherung') or 0)

def abw_grund_row(nk, soll, erloese):
    if pd.isna(soll) or soll == 0: return 'Soll n/a'
    pct = (erloese - soll) / soll * 100
    if abs(pct) < 5: return 'OK'
    return 'Unterfakturierung' if pct < 0 else 'Überfakturierung'

# ── Styles ─────────────────────────────────────────────────────────────────
def fill(h): return PatternFill('solid', fgColor=h)
def fnt(bold=False, color='000000', size=9):
    return Font(bold=bold, color=color, size=size)
THIN = Side(border_style='thin', color='BBBBBB')
BRD  = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
EUR_FMT = '#,##0.00'
HDR_COLS = ['System','Auftrags-Nr','Master-Nr','Sub-Nr(n)','Anzahl Subs','Ist Master',
            'Rech.-Nr','Sendungsdatum','Kunde','Land','Empf.PLZ','Vers.PLZ',
            'Gew.band','Zone','Basis','Basis Menge','Basispreis',
            'Eff. Preis','Tonnage kg','Stellplätze','Lademeter','Volumen','Soll EUR',
            'Fracht EUR','Diesel EUR','Maut EUR','Lademittel','Peak EUR',
            'Neben EUR','EUST Zoll','Versich.',
            'Erlöse','Abw. Grund']
N = len(HDR_COLS)
EUR_COLS  = {17,18,23,24,25,26,27,28,29,30,31,32}
NUM_RIGHT = {5, 16, 19, 20, 21, 22}
STR_COLS  = {2, 3, 7}; DATE_COL = 8
FILL_HDR = fill('1F497D'); FILL_CLU = fill('2E75B6')
FILL_ALT = fill('BDD7EE'); FILL_NEU = fill('FCE4D6'); FILL_CTRL = fill('E2EFDA')

def wc(ws, r, c, v=None, f=None, fn=None, al='left', fmt=None, brd=None):
    cell = ws.cell(row=r, column=c)
    if v is not None: cell.value = v
    if f:   cell.fill = f
    if fn:  cell.font = fn
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

# ── Sheet 1: Sika Deutschland GmbH ────────────────────────────────────────
def build_main_sheet(ws):
    ws.title = 'SSC Import aus Spanien — Vollanalyse'
    ws.freeze_panes = 'A3'
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=N)
    wc(ws,1,1, f'SSC Import aus Spanien ({KNR}) — Vollanalyse  |  '
               f'Cluster: {len(stats)}  |  Sigma Δ: {stats["loss"].sum():,.0f} EUR',
       FILL_HDR, fnt(bold=True, color='FFFFFF', size=12), 'center')
    for ci, h in enumerate(HDR_COLS, 1):
        wc(ws,2,ci,h,FILL_HDR,fnt(bold=True,color='FFFFFF',size=9),'center',brd=BRD)
    row = 2
    for _, cl in stats.iterrows():
        ckey = cl['_cl']; parts = ckey.split('|')
        land, plz_p, sb = (parts+['','',''])[:3]
        vplz = str(cl.get('vplz2',''))
        pre_all  = pre[pre['_cl']==ckey]
        post_all = post[post['_cl']==ckey]
        post_under = post_all
        if len(pre_all) == 0 and len(post_under) == 0: continue
        pre_s = pre_all; post_s = post_under
        ctrl_pi = ctrl_oi = None; best = float('inf')
        for pi, pr in pre_all.iterrows():
            for oi, po in post_under.iterrows():
                d = abs(float(pr.get('_stpl') or 0) - float(po.get('_stpl') or 0))
                if d < best: best=d; ctrl_pi=pi; ctrl_oi=oi
        row += 1
        dlv_str = f'{cl.avg_dlv:,.2f}' if not pd.isna(cl.avg_dlv) else 'n/a'
        lbl = (f'▶ {KNR}|{vplz}|{land}|{plz_p}|{sb}|{BASIS}     '
               f'n_PRE={int(cl.n_pre)}  n_POST={int(cl.n_post)}  '
               f'Ø Dinas={cl.avg_d:,.2f} EUR  Ø AX={cl.avg_ax:,.2f} EUR  '
               f'Δ={cl.delta:,.2f} EUR ({cl.pct:+.1f}%)  '
               f'est.Verlust={cl.loss:,.0f} EUR  |  '
               f'Eff. Dinas={cl.avg_eff_d:,.2f} | Eff. AX={cl.avg_eff_ax:,.2f} | '
               f'DLV={dlv_str} | ΔEff={cl.delta_eff_pct:+.1f}%')
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=N)
        wc(ws, row, 1, lbl, FILL_CLU, fnt(bold=True, color='FFFFFF', size=10))
        for _, r in pre_s.iterrows():
            row += 1
            nk = get_nk_alt(r); erloese = r.get('Dinas Gesamt') or 0
            soll = r.get('Soll EUR'); stpl = r.get('_stpl') or 1; eff = r.get('_eff')
            bp = soll / stpl if soll and stpl else None
            vals = ['alt', r.get('Auftragsnummer'),
                    r.get('_master_nr'), r.get('_sub_nrs'), int(r.get('_n_subs') or 0), r.get('_ist_master') or '',
                    r.get('Rechnungsnummer'), r.get('Leistungsdatum'), KUNDE,
                    r.get('Empfänger Land'), r.get('Empfänger PLZ'), r.get('Versender PLZ'),
                    sb, 'n/a', BASIS, stpl, bp, eff,
                    r.get('Tonnage (eff.)'), r.get('Stellplätze'), r.get('Lademeter'), r.get('Volumen'), soll,
                    *nk, erloese, abw_grund_row(nk, soll, erloese)]
            write_row(ws, row, vals, FILL_ALT, r.name==ctrl_pi)
        for _, r in post_s.iterrows():
            row += 1
            nk = get_nk_neu(r); erloese = r.get('AX Gesamt') or 0
            soll = r.get('Soll EUR'); stpl = r.get('_stpl') or 1; eff = r.get('_eff')
            bp = soll / stpl if soll and stpl else None
            vals = ['neu', r.get('Auftragsnummer'),
                    r.get('_master_nr'), r.get('_sub_nrs'), int(r.get('_n_subs') or 0), r.get('_ist_master') or '',
                    r.get('Rechnungsnummer'), r.get('Leistungsdatum'), KUNDE,
                    r.get('Empfänger Land'), r.get('Empfänger PLZ'), r.get('Versender PLZ'),
                    sb, 'n/a', BASIS, stpl, bp, eff,
                    r.get('Tonnage (eff.)'), r.get('Stellplätze'), r.get('Lademeter'), r.get('Volumen'), soll,
                    *nk, erloese, abw_grund_row(nk, soll, erloese)]
            write_row(ws, row, vals, FILL_NEU, r.name==ctrl_oi)
        row += 1
    widths = [8,15,16,30,8,9, 13,12,18,5,8,8, 11,8,10, 9,10,10, 9,9,9,9, 10, 10,9,9,9,9,9,9,9, 11,22]
    for ci, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(ci)].width = w
    ws.row_dimensions[1].height = 20; ws.row_dimensions[2].height = 18
    return row

# ── Sheet 2: NK_Konditionen ────────────────────────────────────────────────
def build_nk_sheet(ws):
    ws.title = 'NK_Konditionen'
    nk_wb = load_workbook(NK_XLSX, data_only=True); nk_ws = nk_wb.active
    for r_idx, r in enumerate(nk_ws.iter_rows(values_only=True), 1):
        for c_idx, val in enumerate(r, 1):
            ws.cell(row=r_idx, column=c_idx).value = val
    for ci in range(1, (nk_ws.max_column or 19)+1):
        ws.column_dimensions[get_column_letter(ci)].width = 22

# ── Schreiben ──────────────────────────────────────────────────────────────
wb = Workbook()
last_row = build_main_sheet(wb.active)
build_nk_sheet(wb.create_sheet('NK_Konditionen'))
wb.save(OUT_XLSX)
print(f'\nGespeichert: {OUT_XLSX}')
print(f'  Sheet "SSC Import aus Spanien — Vollanalyse": {last_row} Zeilen')
print(f'  Sheet "NK_Konditionen": NK Sika.xlsx kopiert')
