#!/usr/bin/env python3
"""
build_helu_report_v2.py
=======================
Erstellt output/billing_report/helu_dinas_vergleich.xlsx im GEZE-Format:
  Sheet 1 "Helu GmbH"      — 23-Spalten Cluster-Vergleich (alt/neu, ▶-Header)
  Sheet 2 "NK_Konditionen"  — NK Helu.xlsx kopiert

Korrekturen v2:
  - Soll EUR via _lookup_helu() Tarif-Engine (IT und alle Länder)
  - Neue Spalte "Basispreis" (Preis/100kg aus DLV)
  - Zone aus zone_matched (nicht mehr n/a)
  - Spalten entfernt: NK Summe, Abw. EUR, Abw. %
"""

import glob as _glob, math, re
from pathlib import Path
import numpy as np
import pandas as pd
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
import sys; sys.path.insert(0, 'src')
from dlv_tariffs import load_helu, _lookup_helu
from dinas_pdf_parser import parse_one, flatten

SRC_XLSX    = Path('/home/user/TMS/output/helu_dinas_vergleich.xlsx')
CLUSTER_XLS = Path('/home/user/TMS/output/cluster_vergleich/408244_HELU_KABEL_GMBH_cluster.xlsx')
NK_XLSX     = Path('/home/user/TMS/data/extracted/v1/Noerpel AI/Helu/Nebenbedingungen DINAS/NK Helu.xlsx')
DINAS_DIR   = Path('/home/user/TMS/data/extracted/v1/Noerpel AI/Helu/Rechnungen/Rechnungen DINAS')
CACHE       = Path('/home/user/TMS/output/dinas_cache_408244.pkl')
REPORT_DIR  = Path('/home/user/TMS/output/billing_report')
OUT_XLSX    = REPORT_DIR / 'helu_dinas_vergleich.xlsx'
REPORT_DIR.mkdir(exist_ok=True)

KNR   = 408244
KUNDE = 'HELU KABEL GmbH'
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
print('Lade Helu-Tarif...')
tariff = load_helu()
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
pre_lookup  = pre.apply(lambda r: _lookup_helu(r, tariff), axis=1)
post_lookup = post.apply(lambda r: _lookup_helu(r, tariff), axis=1)

pre['_soll_tarif']  = pre_lookup['soll_fracht']
pre['_zone']        = pre_lookup['zone_matched'].str.replace(r'^[A-Z]{2}\s+', '', regex=True)
pre['_basispreis']  = pre_lookup['base_rate']
post['_soll_tarif'] = post_lookup['soll_fracht']
post['_zone']       = post_lookup['zone_matched'].str.replace(r'^[A-Z]{2}\s+', '', regex=True)
post['_basispreis'] = post_lookup['base_rate']

it_hit_pre  = pre[pre['_land']=='IT']['_soll_tarif'].notna().sum()
it_hit_post = post[post['_land']=='IT']['_soll_tarif'].notna().sum()
print(f'IT Soll EUR gesetzt: PRE {it_hit_pre}/{(pre["_land"]=="IT").sum()}, '
      f'POST {it_hit_post}/{(post["_land"]=="IT").sum()}')

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
            'Erlöse','Abw. Grund']
N = len(HDR_COLS)  # 33

EUR_COLS  = {17,18,23,24,25,26,27,28,29,30,31,32}  # 1-based
NUM_RIGHT = {5, 16, 19, 20, 21, 22}  # Anzahl Subs, Basis Menge, Tonnage kg, Stellplätze, Lademeter, Volumen
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

# ── Sheet 1: Helu GmbH ────────────────────────────────────────────────────
def build_main_sheet(ws):
    ws.title = 'Helu GmbH'
    ws.freeze_panes = 'A3'

    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=N)
    wc(ws,1,1, f'HELU KABEL GmbH ({KNR}) — Dinas PRE vs AX POST  |  '
               f'Cluster: {len(stats)}  |  Sigma Verlust: {stats["loss"].sum():,.0f} EUR',
       FILL_HDR, fnt(bold=True, color='FFFFFF', size=12), 'center')

    for ci, h in enumerate(HDR_COLS, 1):
        wc(ws, 2, ci, h, FILL_HDR, fnt(bold=True, color='FFFFFF', size=9), 'center', brd=BRD)

    row = 2

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
            vals = ['alt', r.get('Auftragsnummer'),
                    r.get('_master_nr'), r.get('_sub_nrs'), int(r.get('_n_subs') or 0), r.get('_ist_master') or '',
                    r.get('Rechnungsnummer'), r.get('Leistungsdatum'), KUNDE,
                    r.get('Empfänger Land'), r.get('Empfänger PLZ'), r.get('Versender PLZ'),
                    gwband, zone, BASIS, billing_kg, bp, eff,
                    kg, r.get('Stellplätze'), r.get('Lademeter'), r.get('Volumen'), soll,
                    *nk,
                    erloese, abw_grund_row(nk, soll, erloese)]
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
                    erloese, abw_grund_row(nk, soll, erloese)]
            write_row(ws, row, vals, FILL_NEU, is_ctrl)

        row += 1  # Leerzeile

    widths = [8,15,16,30,8,9, 13,12,18,5,8,8, 11,8,10, 9,10,10, 9,9,9,9, 10, 10,9,9,9,9,9,9,9, 11,22]
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
