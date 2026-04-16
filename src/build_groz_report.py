#!/usr/bin/env python3
"""build_groz_report.py — Groz-Beckert DINAS vs AX, nur Rechnungsdaten"""
import re, glob, math
from pathlib import Path
import fitz, numpy as np, pandas as pd
from openpyxl import Workbook
from openpyxl.styles import PatternFill, Font, Alignment
from openpyxl.utils import get_column_letter
import sys; sys.path.insert(0,'src')
from dinas_pdf_parser import parse_one, flatten

DINAS_DIR = Path('/home/user/TMS/data/extracted/v1/Noerpel AI/Groz Beckert/Rechnungen/Rechnungen DINAS')
AX_DIR    = Path('/home/user/TMS/data/extracted/v1/Noerpel AI/Groz Beckert/Rechnungen/Rechnungen AX')
CACHE     = Path('/home/user/TMS/output/dinas_cache_groz_beckert.pkl')
OUT       = Path('/home/user/TMS/output/billing_report/groz_beckert_vergleich.xlsx')
OUT.parent.mkdir(exist_ok=True)
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

# AX: 3-line charge format (label / M-code / amount EUR)
AX_C = {'fracht':['FRACHT','VEREINBARTE'],'diesel':['DIESEL','FLOATER'],
         'maut':['MAUT','TOLL'],'verzollung':['VERZOLL','ZOLL'],'peak':['PEAK']}
axcat = lambda l: next((c for c,ks in AX_C.items() if any(k in l.upper() for k in ks)),'sonstige')
ax_rows = []
for p in glob.glob(str(AX_DIR/'*.PDF')):
    rn = Path(p).stem.split(' - ')[1].strip() if ' - ' in Path(p).stem else ''
    ls = [l.strip() for pg in fitz.open(p) for l in pg.get_text().split('\n') if l.strip()]
    leist=kg=land=plz=name=''; ch={}
    for i,l in enumerate(ls):
        m=re.match(r'(\d{2}\.\d{2}\.\d{4})\s*/\s*([\d.,]+)\s+kg',l)
        if m: leist=m.group(1); kg=float(m.group(2).replace('.','').replace(',','.'))
        if l.lower()=='nach:' and i+1<len(ls):
            m2=re.match(r'([A-Z]{2})-(\S+)',ls[i+1])
            if m2: land=m2.group(1); plz=m2.group(2).split()[0]
        if 'mpf' in l and l.endswith(':') and i+1<len(ls): name=ls[i+1].split(',')[0]
        m3=re.match(r'(-?[\d.,]+)\s+EUR$',l)
        if m3 and i>=2: ch[axcat(ls[i-2])]=ch.get(axcat(ls[i-2]),0)+float(m3.group(1).replace('.','').replace(',','.'))
    if ch: ax_rows.append({'rn':rn,'dat':leist,'land':land,'plz':plz,'name':name,'kg':kg,**ch,'ax_gesamt':sum(ch.values())})
post = pd.DataFrame(ax_rows); print(f'AX: {len(post)} rows')

# Cluster
pre['_kg']=pd.to_numeric(pre['kg_rechnung'],errors='coerce'); post['_kg']=pd.to_numeric(post['kg'],errors='coerce')
for df,lc in [(pre,'empf_land'),(post,'land')]:
    df['_p2']=df.get('empf_plz',df.get('plz','')).astype(str).str[:2]
    df['_cl']=df[lc].astype(str).fillna('')+'|'+df['_p2']+'|'+df['_kg'].apply(gwb)
pa=pre.groupby('_cl').agg(np_=('gesamtbetrag','count'),ad=('gesamtbetrag','mean'),af=('fracht','mean'),add=('diesel','mean'),am=('maut_ssd','mean')).reset_index()
oa=post.groupby('_cl').agg(na_=('ax_gesamt','count'),aa=('ax_gesamt','mean'),af_=('fracht','mean'),ad_=('diesel','mean'),am_=('maut','mean')).reset_index()
st=pa.merge(oa,on='_cl',how='inner'); st=st[st['aa']<st['ad']].copy()
st['delta']=st['aa']-st['ad']; st['pct']=st['delta']/st['ad'].replace(0,np.nan)*100; st['loss']=st['delta']*st['na_']
def abw(r):
    neg={k:v for k,v in {'Fracht':r.af_-r.af,'Diesel':r.ad_-r.add,'Maut':r.am_-r.am}.items() if v<-0.5}
    return ('Ursache: '+', '.join(f'{k}:{v/sum(neg.values())*100:+.0f}%' for k,v in sorted(neg.items(),key=lambda x:x[1])[:2])) if neg else 'n/a'
st['abw']=st.apply(abw,axis=1); st=st.sort_values('loss').reset_index(drop=True)
print(f'Cluster: {len(st)}, Sigma Verlust: {st["loss"].sum():,.0f} EUR')

# Excel
wb=Workbook(); ws0=wb.active; ws0.title='Zusammenfassung'
BL=PatternFill('solid',fgColor='2E75B6'); WF=Font(bold=True,color='FFFFFF',size=10)
for i,(k,v) in enumerate([('Groz-Beckert KG — DINAS vs AX (Rechnungsdaten)',''),('PRE DINAS Positionen',len(pre)),('POST AX Rechnungen',len(post)),('Unterfakturierungs-Cluster',len(st)),('Sigma Verlust EUR',round(st['loss'].sum(),0))],1):
    ws0.cell(i,1).value=k; ws0.cell(i,2).value=v
for ttl,df in [('PRE Dinas Detail',pre),('POST AX Detail',post)]:
    ws=wb.create_sheet(ttl); ws.append(list(df.columns))
    for _,r in df.iterrows(): ws.append(list(r))
wsc=wb.create_sheet('Cluster-Vergleich'); row=1
PC=['rechnung_nr','leistungsdatum','empf_land','empf_plz','_kg','fracht','diesel','maut_ssd','sonstige','gesamtbetrag']
AC=['rn','dat','land','plz','_kg','fracht','diesel','maut','sonstige','ax_gesamt']
for _,cl in st.head(20).iterrows():
    c=cl['_cl']; hdr=f"CLUSTER {c}  n_pre={int(cl.np_)} n_post={int(cl.na_)}  Ø D={cl.ad:.2f}  Ø AX={cl.aa:.2f}  D={cl.delta:.2f}({cl.pct:+.1f}%)  Verlust={cl.loss:,.0f} EUR  {cl.abw}"
    wsc.merge_cells(start_row=row,start_column=1,end_row=row,end_column=11)
    cell=wsc.cell(row,1); cell.value=hdr; cell.fill=BL; cell.font=WF; cell.alignment=Alignment(horizontal='left'); row+=1
    wsc.append(['Sys','RN','Dat','Land','PLZ','kg','Fracht','Diesel','Maut','Sonst','Gesamt']); row+=1
    for _,r in pre[pre['_cl']==c].head(5).iterrows(): wsc.append(['PRE']+[r.get(col) for col in PC]); row+=1
    for _,r in post[post['_cl']==c].head(5).iterrows(): wsc.append(['AX']+[r.get(col) for col in AC]); row+=1
    wsc.append([]); row+=1
for ci,w in enumerate([6,14,12,6,6,8,10,10,10,10,10],1): wsc.column_dimensions[get_column_letter(ci)].width=w
wsc.freeze_panes='A2'
wb.save(OUT); print(f'Saved: {OUT}')
