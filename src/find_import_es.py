"""
Find all invoices involving Spain (import from ES or export to ES)
across all DINAS PDF caches and BI/AX data.

Output: output/billing_report/import_es.xlsx
  Sheet 1 "Import aus ES (Versender=ES)" — BI rows where Versender Land = ES
  Sheet 2 "Export nach ES (Empfänger=ES)" — BI + DINAS rows where Empfänger = ES
"""
from pathlib import Path
import pandas as pd
import re

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
OUT_DIR   = Path('output/billing_report')
BI_TOP20  = Path('output/bi_top20_data.pkl')
BI_CACHES = [
    Path('output/bi_cache_sika_527406.pkl'),
    Path('output/bi_cache_sika_atm_de.pkl'),
    Path('output/bi_cache_groz_beckert.pkl'),
]
DINAS_CACHES = {
    'output/dinas_cache_406345.pkl': 406345,
    'output/dinas_cache_409480.pkl': 409480,
    'output/dinas_cache_490085.pkl': 490085,
    'output/dinas_cache_486073.pkl': 486073,
    'output/dinas_cache_410844.pkl': 410844,
    'output/dinas_cache_423650.pkl': 423650,
    'output/dinas_cache_408244.pkl': 408244,
    'output/dinas_cache_491063.pkl': 491063,
    'output/dinas_cache_406035.pkl': 406035,
    'output/dinas_cache_groz_beckert.pkl': None,   # multiple KNRs
    'output/dinas_cache_ssc_511241.pkl': 511241,
}

OUTPUT_COLS = [
    'Rechnungsnummer', 'Kunden Nr BK', 'Kunde',
    'Datum', 'System',
    'Versender Name', 'Versender PLZ', 'Versender Land',
    'Empfänger Name', 'Empfänger PLZ', 'Empfänger Land',
    'Tonnage kg', 'Fracht EUR', 'Zoll/EUST EUR', 'Gesamt EUR',
]

# ---------------------------------------------------------------------------
# Step 1: Build KNR → Kundenname lookup from BI top20
# ---------------------------------------------------------------------------
print("Loading BI data …")
bi_top20 = pd.read_pickle(BI_TOP20)['df']
knr_to_name: dict[float, str] = (
    bi_top20.groupby('Kunden Nr BK')['Kunden Name']
    .first()
    .to_dict()
)

# ---------------------------------------------------------------------------
# Step 2: Combine all BI sources
# ---------------------------------------------------------------------------
bi_frames = [bi_top20]
for p in BI_CACHES:
    if p.exists():
        bi_frames.append(pd.read_pickle(p))

bi_all = pd.concat(bi_frames, ignore_index=True)
bi_all['Leistungsdatum'] = pd.to_datetime(bi_all['Leistungsdatum'], errors='coerce')

MIGRATION = pd.Timestamp('2025-09-26')

def bi_system(row):
    return 'AX' if row['Leistungsdatum'] >= MIGRATION else 'DINAS'

bi_all['_system'] = bi_all.apply(bi_system, axis=1)

def _num(series):
    return pd.to_numeric(series, errors='coerce').fillna(0)

def _bi_to_output(sub: pd.DataFrame) -> pd.DataFrame:
    knr_series = _num(sub['Kunden Nr BK'])
    name_series = sub.get('Kunden Name', pd.Series([''] * len(sub), index=sub.index))
    # fallback to lookup if Kunden Name missing
    name_series = name_series.where(name_series.notna() & (name_series != ''),
                                    knr_series.map(knr_to_name))

    fracht = _num(sub.get('Erlöse Fracht'))
    gesamt = _num(sub.get('Erloese'))
    zoll   = _num(sub.get('Erlöse EUST Zoll'))

    out = pd.DataFrame({
        'Rechnungsnummer': sub['Rechnungsnummer'].astype(str),
        'Kunden Nr BK':    knr_series.astype('Int64').astype(str),
        'Kunde':           name_series.astype(str),
        'Datum':           sub['Leistungsdatum'].dt.strftime('%Y-%m-%d'),
        'System':          sub['_system'],
        'Versender Name':  sub.get('Versender Name', '').astype(str),
        'Versender PLZ':   sub.get('Versender PLZ', '').astype(str),
        'Versender Land':  sub.get('Versender Land', '').astype(str),
        'Empfänger Name':  sub.get('Empfänger Name', '').astype(str),
        'Empfänger PLZ':   sub.get('Empfänger PLZ', '').astype(str),
        'Empfänger Land':  sub.get('Empfänger Land', '').astype(str),
        'Tonnage kg':      _num(sub.get('Tonnage (eff.)')),
        'Fracht EUR':      fracht,
        'Zoll/EUST EUR':   zoll,
        'Gesamt EUR':      gesamt,
    }, index=sub.index)
    return out[OUTPUT_COLS]

# ---------------------------------------------------------------------------
# Step 3: BI — Import aus ES (Versender Land = ES)
# ---------------------------------------------------------------------------
mask_vers_es = bi_all['Versender Land'].str.upper().str.strip() == 'ES'
bi_import = _bi_to_output(bi_all[mask_vers_es])
print(f"BI Import aus ES (Versender=ES): {len(bi_import)} rows")

# ---------------------------------------------------------------------------
# Step 4: BI — Export nach ES (Empfänger Land = ES)
# ---------------------------------------------------------------------------
mask_empf_es = bi_all['Empfänger Land'].str.upper().str.strip() == 'ES'
bi_export = _bi_to_output(bi_all[mask_empf_es])
print(f"BI Export nach ES (Empfänger=ES): {len(bi_export)} rows")

# ---------------------------------------------------------------------------
# Step 5: DINAS caches — Export nach ES (empf_land = ES)
# ---------------------------------------------------------------------------
dinas_rows = []
for cache_path, knr in DINAS_CACHES.items():
    p = Path(cache_path)
    if not p.exists():
        continue
    dc = pd.read_pickle(p)
    dc_es = dc[dc['empf_land'].str.upper().str.strip() == 'ES'].copy()
    if dc_es.empty:
        continue
    kunde = knr_to_name.get(float(knr), '') if knr else 'Groz-Beckert'
    knr_str = str(knr) if knr else '410912/490527/527410'
    rows = pd.DataFrame({
        'Rechnungsnummer': dc_es['rechnung_nr'].astype(str),
        'Kunden Nr BK':    knr_str,
        'Kunde':           kunde,
        'Datum':           pd.to_datetime(dc_es.get('leistungsdatum'), errors='coerce').dt.strftime('%Y-%m-%d') if 'leistungsdatum' in dc_es.columns else '',
        'System':          'DINAS (PDF)',
        'Versender Name':  '',
        'Versender PLZ':   '',
        'Versender Land':  '',
        'Empfänger Name':  '',
        'Empfänger PLZ':   dc_es['empf_plz'].astype(str),
        'Empfänger Land':  dc_es['empf_land'].astype(str),
        'Tonnage kg':      pd.to_numeric(dc_es.get('kg_rechnung'), errors='coerce').fillna(0),
        'Fracht EUR':      pd.to_numeric(dc_es.get('fracht'), errors='coerce').fillna(0),
        'Zoll/EUST EUR':   (pd.to_numeric(dc_es.get('verzollung'), errors='coerce').fillna(0)
                            + pd.to_numeric(dc_es.get('zoll_duty'), errors='coerce').fillna(0)
                            + pd.to_numeric(dc_es.get('zoll_betrag'), errors='coerce').fillna(0)),
        'Gesamt EUR':      pd.to_numeric(dc_es.get('gesamtbetrag'), errors='coerce').fillna(0),
    })
    rows = rows[OUTPUT_COLS]
    dinas_rows.append(rows)
    print(f"  DINAS {p.name}: {len(rows)} ES rows → Kunde={kunde}")

dinas_export = pd.concat(dinas_rows, ignore_index=True) if dinas_rows else pd.DataFrame(columns=OUTPUT_COLS)

# Merge BI export + DINAS export, sort by Datum descending
export_all = pd.concat([bi_export, dinas_export], ignore_index=True)
try:
    export_all = export_all.sort_values('Datum', ascending=False)
except Exception:
    pass

print(f"Export nach ES total: {len(export_all)} rows  ({len(bi_export)} BI + {len(dinas_export)} DINAS)")

# ---------------------------------------------------------------------------
# Step 6: Write Excel
# ---------------------------------------------------------------------------
OUT_DIR.mkdir(parents=True, exist_ok=True)
out_path = OUT_DIR / 'import_es.xlsx'

with pd.ExcelWriter(out_path, engine='openpyxl') as writer:
    bi_import.to_excel(writer, sheet_name='Import aus ES (Versender=ES)', index=False)
    export_all.to_excel(writer, sheet_name='Export nach ES (Empfänger=ES)', index=False)

print(f"\nDone → {out_path}")
print(f"  Sheet 'Import aus ES (Versender=ES)': {len(bi_import)} rows")
print(f"  Sheet 'Export nach ES (Empfänger=ES)': {len(export_all)} rows")
