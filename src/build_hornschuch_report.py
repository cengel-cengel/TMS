#!/usr/bin/env python3
"""
build_hornschuch_report.py
==========================
Erstellt output/billing_report/hornschuch_dinas_vergleich.xlsx:
  Sheet 1 "Hornschuch AG"  — 33-Spalten Cluster-Vergleich (alt/neu, ▶-Header)
  Sheet 2 "NK_Konditionen" — NK Hornschuch.xlsx kopiert
"""

import glob as _glob, math, re
from pathlib import Path
import numpy as np
import pandas as pd
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
import sys; sys.path.insert(0, 'src')
from dlv_tariffs import load_hornschuch, _lookup_hornschuch
from dinas_pdf_parser import parse_one, flatten
from dinas_bi_enrichment import enrich_customer_bi

SRC_XLSX    = Path('/home/user/TMS/output/hornschuch_dinas_vergleich.xlsx')
CLUSTER_XLS = Path('/home/user/TMS/output/cluster_vergleich/490085_Konrad_Hornschuch_GmbH_cluster.xlsx')
NK_XLSX     = Path('/home/user/TMS/data/extracted/v1/Noerpel AI/Hornschuch/Nebenbedingungen DINAS/NK Hornschuch.xlsx')
DINAS_DIR   = Path('/home/user/TMS/data/extracted/v1/Noerpel AI/Hornschuch/Rechnungen/Rechnungen DINAS')
CACHE       = Path('/home/user/TMS/output/dinas_cache_490085.pkl')
REPORT_DIR  = Path('/home/user/TMS/output/billing_report')
OUT_XLSX    = REPORT_DIR / 'hornschuch_dinas_vergleich.xlsx'
REPORT_DIR.mkdir(exist_ok=True)

KNR   = 490085
KUNDE = 'Hornschuch AG'
BASIS = 'EUR/100kg'

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

# ── Master/Sub-Konsolidierung ──────────────────────────────────────────────
_ms_map_cache = None

def norm_ms(v):
    try: return str(int(float(str(v).strip())))
    except: return str(v).strip()

def _get_ms_map():
    global _ms_map_cache
    if _ms_map_cache is not None: return _ms_map_cache
    _bi = pd.read_pickle(Path('output/bi_top20_data.pkl'))['df']
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

# ── Tarif laden ────────────────────────────────────────────────────────────
print('Lade Hornschuch-Tarif...')
tariff = load_hornschuch()
print(f'Tarif: {len(tariff)} Zeilen, Länder: {sorted(tariff["country"].unique())}')

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

# Filter ungültige Rechnungsnummern (RN=0 → kein Vergleich möglich)
for df, name in [(pre, 'PRE'), (post, 'POST')]:
    bad = df['Rechnungsnummer'].apply(
        lambda v: str(v).strip().rstrip('0').rstrip('.') in ('0', '', 'nan'))
    if bad.sum():
        print(f'Filtere {bad.sum()} {name} Zeile(n) mit RN=0: '
              f'{df[bad]["Auftragsnummer"].tolist()}')
        df.drop(index=df[bad].index, inplace=True)

POST_NK = ['AX Fracht','AX Diesel','AX Maut','AX Nebengebühr',
           'AX Lademittel','AX Peak','AX EUST/Zoll','AX Versicherung','AX Gesamt']
for c in POST_NK: post[c] = pd.to_numeric(post.get(c), errors='coerce')

# ── DINAS-NK: Per-Sendung aus Cache (sendungs_nr = Auftragsnummer) ─────────
# Bugfix: alte Version aggregierte ALLE Positionen einer Rechnung und wies den
# Gesamtbetrag jeder BI-Zeile zu (falsch bei Sammelrechnungen mit 50+ Sendungen).
# Fix: Parser liest jetzt alle Seiten; Join auf sendungs_nr = Auftragsnummer.
if CACHE.exists():
    dinas_cache = pd.read_pickle(CACHE)
    print(f'DINAS cache geladen: {len(dinas_cache)} Positionen')
else:
    print('Parse DINAS PDFs (einmalig, wird gecacht)...')
    pdfs = _glob.glob(str(DINAS_DIR / '*.pdf'))
    rows = [flatten(pos) for p in pdfs for pos in parse_one(p)]
    dinas_cache = pd.DataFrame(rows)
    dinas_cache.to_pickle(CACHE)
    print(f'Cache gespeichert: {len(dinas_cache)} Positionen')

# ── BI-Enrichment: Komplettpreis / Sammelposten / Gutschrift-Netting ──────────
print('\n── BI-Enrichment ──────────────────────────────────────────────────────')
_bi_raw = pd.read_pickle(Path('output/bi_top20_data.pkl'))['df']
_hn_bi  = _bi_raw[_bi_raw['Kunden Nr BK'] == KNR].copy()
_bi_enriched, _dinas_net, _enrich_stats = enrich_customer_bi(_hn_bi, dinas_cache)
s = _enrich_stats
print(f'  A) Komplettpreis: {s["n_komplettpreis"]} / {s["n_snrs"]} SNRs ({s["pct_komplettpreis"]:.1f}%)')
print(f'  B) Sammelposten:  {s["n_split_snrs"]} / {s["n_snrs"]} SNRs ({s["pct_split"]:.1f}%)')
print(f'  C) Gutschriften:  {s["n_gutschrift_solo"]} Solo-Gutschriften')
print(f'  DINAS-Match: {s["n_dinas_matched"]}  Multi-Row: {s["n_multi_rn_dinas"]}  '
      f'Acc.-Basis: {s["n_acc_base"]}  ±5%: {s["n_within_5pct"]} ({s["pct_within_5pct"]:.1f}%)')
print()
_tmp = _bi_enriched.drop_duplicates('_snr').set_index('_snr')
_flag_kp  = _tmp['flag_komplettpreis'].to_dict()
_flag_sp  = _tmp['flag_bi_split'].to_dict()
_flag_dvp = _tmp['dinas_vs_bi_diff_pct'].to_dict()
_flag_mr  = _tmp['flag_multi_rn_dinas'].fillna(False).to_dict()
del _tmp

def _norm(v):
    s = re.sub(r'\D', '', str(v)).lstrip('0')
    return s if s else str(v).strip()

dinas_cache['_snr'] = dinas_cache['sendungs_nr'].astype(str).apply(_norm)
pre['_snr'] = pre['Auftragsnummer'].astype(str).apply(_norm)

# Drop stale DINAS-NK columns (wrong aggregated values) and re-join per shipment
PRE_NK  = ['Dinas Fracht','Dinas Diesel','Dinas Maut/SSD','Dinas Ausfuhr',
           'Dinas Verzollung','Dinas Zoll Duty','Dinas Zollbetrag',
           'Dinas Sulphur','Dinas Nebenkostenpausch.','Dinas Redebit',
           'Dinas Sonstige','Dinas Gesamt']
pre.drop(columns=[c for c in PRE_NK if c in pre.columns], inplace=True)

DINAS_RENAME = {
    'fracht': 'Dinas Fracht', 'diesel': 'Dinas Diesel', 'maut_ssd': 'Dinas Maut/SSD',
    'ausfuhr': 'Dinas Ausfuhr', 'verzollung': 'Dinas Verzollung',
    'zoll_duty': 'Dinas Zoll Duty', 'zoll_betrag': 'Dinas Zollbetrag',
    'sulphur': 'Dinas Sulphur', 'neben_pausch': 'Dinas Nebenkostenpausch.',
    'redebit': 'Dinas Redebit', 'sonstige': 'Dinas Sonstige',
    'gesamtbetrag': 'Dinas Gesamt',
}
cache_nk = dinas_cache.rename(columns=DINAS_RENAME)[['_snr'] + list(DINAS_RENAME.values())].copy()
pre = pre.merge(cache_nk, on='_snr', how='left')
pre.drop(columns=['_snr'], inplace=True)

for c in PRE_NK: pre[c] = pd.to_numeric(pre.get(c), errors='coerce')
matched_pre = pre['Dinas Fracht'].notna().sum()
print(f'DINAS NK re-joined: {matched_pre}/{len(pre)} PRE Zeilen matched (sendungs_nr)')

# Filter PRE-Zeilen mit Fracht=0 (Zoll/NK-only Sendungen, nicht vergleichbar)
zero_pre = pre[pre['Dinas Fracht'].fillna(-1) == 0]
if len(zero_pre):
    print(f'Filtere {len(zero_pre)} PRE Zeile(n) mit Dinas Fracht=0 '
          f'(Zoll/NK-only, kein Frachtvergleich möglich):')
    for _, z in zero_pre.iterrows():
        print(f'  RN={z.get("Rechnungsnummer")}  Auftr={z.get("Auftragsnummer")}  '
              f'Gesamt={z.get("Dinas Gesamt"):.2f} EUR  '
              f'(Verzollung={z.get("Dinas Verzollung",0):.2f})')
pre = pre[pre['Dinas Fracht'].fillna(0) > 0].copy()

print('Konsolidiere Master/Sub-Sendungen...')
post = enrich_master_sub(post)
pre  = add_empty_master_cols(pre)

# ── Eff. EUR/100kg pro Sendung ─────────────────────────────────────────────
pre['_eff_100kg']  = pre['Dinas Fracht']  / pre['Tonnage (eff.)'] * 100
post['_eff_100kg'] = post['AX Fracht']    / post['Tonnage (eff.)'] * 100

# ── Tarif-Lookup für alle Zeilen ───────────────────────────────────────────
print('Berechne Soll EUR via Tarif-Engine...')
pre_lookup  = pre.apply(lambda r: _lookup_hornschuch(r, tariff), axis=1)
post_lookup = post.apply(lambda r: _lookup_hornschuch(r, tariff), axis=1)

pre['_soll_tarif']  = pre_lookup['soll_fracht']
pre['_zone']        = pre_lookup['zone_matched'].str.replace(r'^[A-Z]{2}\s+', '', regex=True)
pre['_basispreis']  = None  # Hornschuch gibt keine base_rate zurück
post['_soll_tarif'] = post_lookup['soll_fracht']
post['_zone']       = post_lookup['zone_matched'].str.replace(r'^[A-Z]{2}\s+', '', regex=True)
post['_basispreis'] = None

# ── Soll EUR: Tarif-Engine hat Vorrang; Cluster-Datei als Ergänzung ────────
cl_df = pd.read_excel(CLUSTER_XLS, sheet_name=0)
alt_cl = cl_df[cl_df['System']=='alt'][['Auftrags-Nr','Soll EUR']].copy()
neu_cl = cl_df[cl_df['System']=='neu'][['Auftrags-Nr','Soll EUR']].copy()
for df in (alt_cl, neu_cl):
    df['_aid'] = df['Auftrags-Nr'].apply(norm_id)
    df['Soll EUR'] = pd.to_numeric(df['Soll EUR'], errors='coerce')
soll_pre_cl  = alt_cl.dropna(subset=['Soll EUR']).set_index('_aid')['Soll EUR'].to_dict()
soll_post_cl = neu_cl.dropna(subset=['Soll EUR']).set_index('_aid')['Soll EUR'].to_dict()
pre['_aid']  = pre['Auftragsnummer'].apply(norm_id)
post['_aid'] = post['Auftragsnummer'].apply(norm_id)

# Prefer tariff; fall back to cluster file
pre['Soll EUR']  = pre['_soll_tarif'].where(pre['_soll_tarif'].notna(),
                       pre['_aid'].map(soll_pre_cl))
post['Soll EUR'] = post['_soll_tarif'].where(post['_soll_tarif'].notna(),
                       post['_aid'].map(soll_post_cl))
print(f'Soll EUR final: PRE {pre["Soll EUR"].notna().sum()}/{len(pre)}, '
      f'POST {post["Soll EUR"].notna().sum()}/{len(post)}')

# ── Cluster-Statistiken ────────────────────────────────────────────────────
pa = pre.groupby('_cl').agg(
    n_pre=('Dinas Gesamt','count'), avg_d=('Dinas Gesamt','mean'),
    avg_df=('Dinas Fracht','mean'), avg_dd=('Dinas Diesel','mean'),
    avg_dm=('Dinas Maut/SSD','mean'), vplz2=('_vplz2','first'),
    avg_eff_d=('_eff_100kg','mean'), avg_dlv=('_basispreis','mean')).reset_index()
oa = post.groupby('_cl').agg(
    n_post=('AX Gesamt','count'), avg_ax=('AX Gesamt','mean'),
    avg_af=('AX Fracht','mean'), avg_ad=('AX Diesel','mean'),
    avg_am=('AX Maut','mean'), avg_eff_ax=('_eff_100kg','mean')).reset_index()
stats = pa.merge(oa, on='_cl', how='inner')
stats = stats[stats['avg_ax'] < stats['avg_d']].copy()
stats['delta'] = stats['avg_ax'] - stats['avg_d']
stats['pct']   = stats['delta'] / stats['avg_d'].replace(0, np.nan) * 100
stats['loss']  = stats['delta'] * stats['n_post']

def abw_grund_cluster(r):
    neg = {k:v for k,v in
           {'Fracht': r.avg_af-r.avg_df, 'Diesel': r.avg_ad-r.avg_dd,
            'Maut':   r.avg_am-r.avg_dm}.items() if v < -0.5}
    if not neg: return 'sonstige NK'
    t = sum(neg.values())
    return ', '.join(f'{k} ({v/t*100:+.0f}%)'
                     for k,v in sorted(neg.items(), key=lambda x:x[1])[:2])

stats['abw_grund'] = stats.apply(abw_grund_cluster, axis=1)
stats['delta_eff_pct'] = ((stats['avg_eff_ax'] - stats['avg_eff_d'])
                           / stats['avg_eff_d'].replace(0, np.nan) * 100)
# Nur Cluster mit >5% Eff.-Preis-Abweichung
stats = stats[stats['delta_eff_pct'].abs() > 5].copy()
stats = stats.sort_values('loss').reset_index(drop=True)
print(f'Cluster (|ΔEff|>5%): {len(stats)}, Sigma Verlust: {stats["loss"].sum():,.0f} EUR')

top5 = stats.reindex(stats['delta_eff_pct'].abs().nlargest(5).index)
print('\nTop-5 Cluster nach Eff.-Preis-Abweichung:')
for _, cl in top5.iterrows():
    parts = cl['_cl'].split('|'); land, plz_p, gwband = (parts+['','',''])[:3]
    dlv = cl.avg_dlv if not pd.isna(cl.avg_dlv) else float('nan')
    print(f'  {land}|{plz_p}|{gwband}  '
          f'Eff.Dinas={cl.avg_eff_d:.2f}  Eff.AX={cl.avg_eff_ax:.2f}  '
          f'DLV={dlv:.2f}  Δ={cl.delta_eff_pct:+.1f}%')

# ── NK-Mapping ─────────────────────────────────────────────────────────────
def get_nk_alt(r):
    fracht  = r.get('Dinas Fracht') or 0
    diesel  = r.get('Dinas Diesel') or 0
    maut    = r.get('Dinas Maut/SSD') or 0
    lademl  = 0
    peak    = 0
    neben   = r.get('Dinas Ausfuhr') or 0
    eust    = ((r.get('Dinas Verzollung') or 0) + (r.get('Dinas Zoll Duty') or 0)
               + (r.get('Dinas Zollbetrag') or 0))
    versich = ((r.get('Dinas Sulphur') or 0) + (r.get('Dinas Nebenkostenpausch.') or 0)
               + (r.get('Dinas Redebit') or 0)  + (r.get('Dinas Sonstige') or 0))
    return fracht, diesel, maut, lademl, peak, neben, eust, versich

def get_nk_neu(r):
    return (r.get('AX Fracht') or 0, r.get('AX Diesel') or 0,
            r.get('AX Maut') or 0,   r.get('AX Lademittel') or 0,
            r.get('AX Peak') or 0,   r.get('AX Nebengebühr') or 0,
            r.get('AX EUST/Zoll') or 0, r.get('AX Versicherung') or 0)

def abw_grund_row(nk, soll, erloese):
    if pd.isna(soll) or soll == 0: return 'Soll n/a'
    pct = (erloese - soll) / soll * 100
    if abs(pct) < 5: return 'OK'
    return 'Unterfakturierung' if pct < 0 else 'Überfakturierung'

# ── Styles ─────────────────────────────────────────────────────────────────
def fill(h): return PatternFill('solid', fgColor=h)
def fnt(bold=False, color='000000', size=9, italic=False):
    return Font(bold=bold, color=color, size=size, italic=italic)
THIN = Side(border_style='thin', color='BBBBBB')
BRD  = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
EUR_FMT = '#,##0.00'

# 33 Spalten
HDR_COLS = ['System','Auftrags-Nr','Master-Nr','Sub-Nr(n)','Anzahl Subs','Ist Master',
            'Rech.-Nr','Sendungsdatum','Kunde','Land','Empf.PLZ','Vers.PLZ',
            'Gew.band','Zone','Basis','Basis Menge','Basispreis',
            'Eff. Preis','Tonnage kg','Stellplätze','Lademeter','Volumen','Soll EUR',
            'Fracht EUR','Diesel EUR','Maut EUR','Lademittel','Peak EUR',
            'Neben EUR','EUST Zoll','Versich.',
            'Erlöse','Abw. Grund',
            'Komplettpreis','BI-Split','DINAS vs BI %','DINAS Multi-Row']
N = len(HDR_COLS)  # 37

EUR_COLS  = {17,18,23,24,25,26,27,28,29,30,31,32}  # 1-based
NUM_RIGHT = {5, 16, 19, 20, 21, 22, 36}  # + DINAS vs BI %
DATE_COL  = 8
STR_COLS  = {2, 3, 7}  # Auftrags-Nr, Master-Nr, Rech.-Nr

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
        # Auftrags-Nr / Rech.-Nr als Text (verhindert E-Notation bei großen Nummern)
        if ci in STR_COLS and v is not None:
            try: v = str(int(float(str(v))))
            except: v = str(v)
        fmt = ('DD.MM.YYYY' if ci == DATE_COL else
               EUR_FMT if ci in EUR_COLS else None)
        al  = 'right' if ci in EUR_COLS or ci in NUM_RIGHT else 'left'
        wc(ws, row, ci, v, rf, fnt(size=9), al, fmt, BRD)

# ── Sheet 1: Hornschuch AG ────────────────────────────────────────────────
def build_main_sheet(ws):
    ws.title = 'Hornschuch AG'

    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=N)
    wc(ws,1,1, f'Hornschuch AG ({KNR}) — Dinas PRE vs AX POST  |  '
               f'Cluster: {len(stats)}  |  Sigma Verlust: {stats["loss"].sum():,.0f} EUR',
       FILL_HDR, fnt(bold=True, color='FFFFFF', size=12), 'center')

    # ── Rows 2–8: Datenqualitäts-Block (PDF-Coverage + Accuracy-Basis) ──────────
    n_pre  = len(_hn_bi[_hn_bi['periode'] == 'PRE'])
    n_post = len(_hn_bi[_hn_bi['periode'] == 'POST'])
    n_matched   = s['n_dinas_matched']
    n_multi_rn  = s.get('n_multi_rn_dinas', 0)
    n_acc_base  = s.get('n_acc_base', n_matched)
    n_ok        = s['n_within_5pct']
    n_sp   = s['n_split_snrs']
    n_gus  = s['n_gutschrift_solo']
    cov_pct  = n_matched / n_pre * 100 if n_pre else 0
    cov_warn = '  ⚠ Coverage < 50% — Accuracy auf Stichprobe!' if cov_pct < 50 else ''

    FILL_DQ  = fill('F2F2F2')
    FILL_DQH = fill('D9D9D9')
    FILL_DQW = fill('FFF2CC')

    dq_rows = [
        ('Datenqualität — PDF-Coverage + Accuracy-Basis', None, True),
        ('PRE-Sendungen gesamt (aus bi_raw)', f'{n_pre}  (POST: {n_post})', False),
        ('davon mit DINAS-PDF-Match',
         f'{n_matched} / {n_pre} ({cov_pct:.0f}%){cov_warn}', False),
        ('davon nach Multi-Row-Ausschluss vergleichbar', f'{n_acc_base}', False),
        ('davon im ±5%-Band',
         (f'{n_ok} / {n_acc_base} ({n_ok/n_acc_base*100:.0f}% der Acc.-Basis)  ← Basis-Accuracy'
          if n_acc_base else '–'), False),
        ('Ausschluss-Gründe',
         f'A) Kein DINAS-Match: {n_pre - n_matched}  |  '
         f'B) Sammelposten (nicht ausgeschl.): {n_sp} ({s["pct_split"]:.0f}%)  |  '
         f'C) Solo-Gutschriften: {n_gus}  |  '
         f'D) DINAS Multi-Row: {n_multi_rn} (aus ±5%-Basis ausgeschl.)', False),
        ('Vergleich-Methode',
         'Komplettpreis → DINAS total_items vs BI Erloese  |  Standard → DINAS fracht vs BI Erlöse Fracht', False),
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
        vplz  = str(cl.get('vplz2', ''))

        pre_all   = pre[pre['_cl']==ckey]
        post_all  = post[post['_cl']==ckey]
        # Nur unterfakturierte POST-Zeilen: AX Fracht < Ø Dinas Fracht im Cluster
        post_under = post_all[post_all['AX Fracht'].fillna(float('inf')) < cl.avg_df]
        # Zusätzlich: Abw.-Grund-Filter — nur Zeilen behalten wo abw_grund_row != 'Überfakturierung'
        post_under = post_under[[
            abw_grund_row(get_nk_neu(r), r.get('Soll EUR'), r.get('AX Gesamt') or 0) != 'Überfakturierung'
            for _, r in post_under.iterrows()
        ]]
        # Cluster komplett raus wenn keine unterfakturierten POST-Zeilen
        if len(post_under) == 0:
            continue
        pre_s  = pre_all.head(5)
        post_s = post_under.head(5)

        # Kontroll-Paar (aus gefilterten POST-Zeilen)
        ctrl_pi, ctrl_oi = None, None
        best = float('inf')
        for pi, pr in pre_all.iterrows():
            pr_kg = pr.get('Tonnage (eff.)')
            if pd.isna(pr_kg): continue
            for oi, po in post_under.iterrows():
                po_kg = po.get('Tonnage (eff.)')
                if pd.isna(po_kg): continue
                d = abs(float(pr_kg) - float(po_kg))
                if d < best: best=d; ctrl_pi=pi; ctrl_oi=oi

        # Cluster-Header
        row += 1
        dlv_str = f'{cl.avg_dlv:,.2f}' if not pd.isna(cl.avg_dlv) else 'n/a'
        lbl = (f'▶ {KNR}|{vplz}|{land}|{plz_p}|{gwband}|{BASIS}     '
               f'n_PRE={int(cl.n_pre)}  n_POST={int(cl.n_post)}  '
               f'Ø Dinas={cl.avg_d:,.2f} EUR  Ø AX={cl.avg_ax:,.2f} EUR  '
               f'Δ={cl.delta:,.2f} EUR ({cl.pct:+.1f}%)  '
               f'est.Verlust={cl.loss:,.0f} EUR  |  '
               f'Eff. Dinas={cl.avg_eff_d:,.2f} | Eff. AX={cl.avg_eff_ax:,.2f} | '
               f'DLV={dlv_str} | ΔEff={cl.delta_eff_pct:+.1f}%  |  {cl.abw_grund}')
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=N)
        wc(ws, row, 1, lbl, FILL_CLU, fnt(bold=True, color='FFFFFF', size=10))

        # alt (Dinas PRE)
        for _, r in pre_s.iterrows():
            row += 1
            nk      = get_nk_alt(r)
            erloese = r.get('Dinas Gesamt') or 0
            soll    = r.get('Soll EUR')
            zone    = r.get('_zone') or 'n/a'
            bp      = r.get('_basispreis')
            eff     = r.get('_eff_100kg')
            kg      = r.get('Tonnage (eff.)')
            billing_kg = math.ceil(float(kg)/100)*100 if pd.notna(kg) and float(kg) > 0 else None
            is_ctrl = (r.name == ctrl_pi)
            snr_key = _norm(str(r.get('Auftragsnummer', '')))
            kp_flag = 'JA' if _flag_kp.get(snr_key, False) else ''
            sp_flag = 'JA' if _flag_sp.get(snr_key, False) else ''
            dv_pct  = _flag_dvp.get(snr_key, None)
            mr_flag = 'JA' if _flag_mr.get(snr_key, False) else ''
            vals = ['alt', r.get('Auftragsnummer'),
                    r.get('_master_nr'), r.get('_sub_nrs'), int(r.get('_n_subs') or 0), r.get('_ist_master') or '',
                    r.get('Rechnungsnummer'), r.get('Leistungsdatum'), KUNDE,
                    r.get('Empfänger Land'), r.get('Empfänger PLZ'), r.get('Versender PLZ'),
                    gwband, zone, BASIS, billing_kg, bp, eff,
                    kg, r.get('Stellplätze'), r.get('Lademeter'), r.get('Volumen'), soll,
                    *nk,
                    erloese, abw_grund_row(nk, soll, erloese),
                    kp_flag, sp_flag, dv_pct, mr_flag]
            write_row(ws, row, vals, FILL_ALT, is_ctrl)

        # neu (AX POST)
        for _, r in post_s.iterrows():
            row += 1
            nk      = get_nk_neu(r)
            erloese = r.get('AX Gesamt') or 0
            soll    = r.get('Soll EUR')
            zone    = r.get('_zone') or 'n/a'
            bp      = r.get('_basispreis')
            eff     = r.get('_eff_100kg')
            kg      = r.get('Tonnage (eff.)')
            billing_kg = math.ceil(float(kg)/100)*100 if pd.notna(kg) and float(kg) > 0 else None
            is_ctrl = (r.name == ctrl_oi)
            vals = ['neu', r.get('Auftragsnummer'),
                    r.get('_master_nr'), r.get('_sub_nrs'), int(r.get('_n_subs') or 0), r.get('_ist_master') or '',
                    r.get('Rechnungsnummer'), r.get('Leistungsdatum'), KUNDE,
                    r.get('Empfänger Land'), r.get('Empfänger PLZ'), r.get('Versender PLZ'),
                    gwband, zone, BASIS, billing_kg, bp, eff,
                    kg, r.get('Stellplätze'), r.get('Lademeter'), r.get('Volumen'), soll,
                    *nk,
                    erloese, abw_grund_row(nk, soll, erloese),
                    '', 'JA' if _flag_sp.get(_norm(str(r.get('Auftragsnummer',''))), False) else '', None, None]
            write_row(ws, row, vals, FILL_NEU, is_ctrl)

        row += 1  # Leerzeile

    widths = [8,15,16,30,8,9, 13,12,18,5,8,8, 11,8,10, 9,10,10, 9,9,9,9, 10, 10,9,9,9,9,9,9,9, 11,22,
              10, 8, 10, 12]
    for ci, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(ci)].width = w
    ws.row_dimensions[1].height = 20
    ws.row_dimensions[HDR_ROW].height = 18
    return row

# ── Sheet 2: NK_Konditionen ───────────────────────────────────────────────
def build_nk_sheet(ws):
    ws.title = 'NK_Konditionen'
    nk_wb = load_workbook(NK_XLSX, data_only=True)
    nk_ws = nk_wb.active
    for r_idx, row in enumerate(nk_ws.iter_rows(values_only=True), 1):
        for c_idx, val in enumerate(row, 1):
            ws.cell(row=r_idx, column=c_idx).value = val
    for ci in range(1, (nk_ws.max_column or 19) + 1):
        ws.column_dimensions[get_column_letter(ci)].width = 22

# ── Sheet 3: Accuracy_PRE ────────────────────────────────────────────────────
def build_accuracy_sheet(ws):
    ws.title = 'Accuracy_PRE'
    ws.freeze_panes = 'A3'

    _hn_pre = _bi_enriched[_bi_enriched['periode'] == 'PRE'].copy()
    _rn_lkp = _dinas_net.set_index('_snr')[['rechnung_nr', 'n_rows']].to_dict('index')
    _hn_pre['rechnung_nr_dinas'] = _hn_pre['_snr'].map(
        lambda snr: _rn_lkp.get(snr, {}).get('rechnung_nr', ''))
    _hn_pre['n_dinas_rows'] = _hn_pre['_snr'].map(
        lambda snr: _rn_lkp.get(snr, {}).get('n_rows', None))
    acc = _hn_pre[_hn_pre['dinas_netto_compare'].notna()].copy()
    acc['diff_eur'] = acc['dinas_vs_bi_diff_eur'].round(2)
    acc['diff_pct'] = acc['dinas_vs_bi_diff_pct'].round(1)
    acc = acc.sort_values('diff_pct', key=abs, ascending=False).reset_index(drop=True)

    n_tot     = len(acc)
    _is_multi = acc['flag_multi_rn_dinas'].fillna(False).astype(bool)
    n_multi   = int(_is_multi.sum())
    n_acc     = n_tot - n_multi
    n_ok      = int((acc.loc[~_is_multi, 'diff_pct'].abs() <= 5).sum())
    n_big     = int((acc.loc[~_is_multi, 'diff_pct'].abs() > 10).sum())
    n_kp      = int(acc['flag_komplettpreis'].sum())
    n_sp      = int(acc['flag_bi_split'].sum())
    n_gus     = int(acc['flag_gutschrift_solo'].fillna(False).sum())

    summary = (f'Hornschuch AG ({KNR}) — PRE Accuracy: DINAS Total (Komplettpreis-Fix) vs BI Erloese_effektiv  |  '
               f'Rows: {n_tot}  |  Multi-Row (ausgeschl.): {n_multi}  |  Acc.-Basis: {n_acc}  |  '
               f'±5%: {n_ok} ({n_ok/n_acc*100:.0f}% der Basis)  |  >10% Abw.: {n_big}  |  '
               f'Komplettpreis: {n_kp}  |  Sammelposten: {n_sp}  |  Solo-Gutschrift: {n_gus}')

    ACC_COLS = ['Auftrags-Nr','Rech.-Nr DINAS','Rech.-Nr BI','Datum',
                'Land','Empf.PLZ','Tonnage kg',
                'DINAS Total/Fracht','BI Erloese_eff','Diff EUR','Diff %',
                'Komplettpreis','BI-Split','Solo-Gutschrift','Multi-Row DINAS','Abw. Klasse']
    NA = len(ACC_COLS)

    FILL_DQ_HDR = fill('1F497D')
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=NA)
    wc(ws, 1, 1, summary, FILL_DQ_HDR, fnt(bold=True, color='FFFFFF', size=10), 'left')
    for ci, h in enumerate(ACC_COLS, 1):
        wc(ws, 2, ci, h, FILL_DQ_HDR, fnt(bold=True, color='FFFFFF', size=9), 'center', brd=BRD)

    FILL_OK   = fill('E2EFDA')
    FILL_WARN = fill('FFEB9C')
    FILL_BAD  = fill('FFC7CE')
    FILL_MROW = fill('FFCC99')
    EUR_ACC   = {8, 9, 10}
    PCT_ACC   = {11}

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
            r.get('Auftragsnummer'),
            r.get('rechnung_nr_dinas') or '',
            r.get('Rechnungsnummer') or '',
            r.get('Leistungsdatum') or r.get('Sendungsdatum') or '',
            r.get('Empfänger Land') or '',
            r.get('Empfänger PLZ') or '',
            r.get('Tonnage (eff.)'),
            r.get('dinas_netto_compare'),
            r.get('erloese_fracht_effektiv'),
            r.get('diff_eur'),
            pct,
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


# ── Schreiben ──────────────────────────────────────────────────────────────
wb = Workbook()
last_row  = build_main_sheet(wb.active)
build_nk_sheet(wb.create_sheet('NK_Konditionen'))
acc_rows  = build_accuracy_sheet(wb.create_sheet('Accuracy_PRE'))
wb.save(OUT_XLSX)
print(f'\nGespeichert: {OUT_XLSX}')
print(f'  Sheet "Hornschuch AG":   {last_row} Zeilen')
print(f'  Sheet "NK_Konditionen":  NK Hornschuch.xlsx kopiert')
print(f'  Sheet "Accuracy_PRE":    {acc_rows-2} Rows (DINAS vs BI Accuracy)')
