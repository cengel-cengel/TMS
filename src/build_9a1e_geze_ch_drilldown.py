#!/usr/bin/env python3
"""Etappe 9a.1.E — GEZE-CH root-cause drilldown + spread validation.

Outputs:
  data/reports/9a1e_geze_ch_drilldown.csv   — per-Sendung GEZE CH rows + delta
  data/reports/9a1e_geze_ch_dlv_sheet.txt   — DLV tariff cells used for CH
"""
from __future__ import annotations
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path('/home/user/TMS')
sys.path.insert(0, str(BASE / 'src'))

from top20_abw_s5_tariff_check import lookup_geze, _get_geze  # noqa: E402
from dlv_tariffs import _lookup_geze as _raw_lookup_geze      # noqa: E402

OUT = BASE / 'data/reports'

# ---------------------------------------------------------------------------
# Schritt 1 — GEZE-CH drilldown
# ---------------------------------------------------------------------------
print("Loading BI data …")
with open(BASE / 'output/bi_top20_data.pkl', 'rb') as f:
    bi = pickle.load(f)['df']

geze_pre = bi[(bi['Kunden Nr BK'] == 406035) & (bi['periode'] == 'PRE')].copy()
print(f"GEZE PRE rows: {len(geze_pre)}")

ch_mask = (
    geze_pre['Empfänger Land'].str.upper().str.strip() == 'CH'
)
geze_ch = geze_pre[ch_mask].copy()
print(f"GEZE CH rows: {len(geze_ch)}")

rows_out = []
tariff = _get_geze()

for _, row in geze_ch.iterrows():
    erloese = float(row.get('Erloese', 0) or 0)
    gewicht = float(row.get('Tonnage (eff.)', 0) or 0)

    lookup_res = _raw_lookup_geze(row, tariff)
    dlv_soll = lookup_res.get('soll_fracht') if hasattr(lookup_res, 'get') else lookup_res['soll_fracht']
    dlv_soll = float(dlv_soll) if pd.notna(dlv_soll) else None

    if erloese > 0 and dlv_soll is not None:
        delta = dlv_soll - erloese
        delta_pct = delta / erloese * 100
        dinas_erloese_kg = erloese / gewicht * 100 if gewicht > 0 else None
        dlv_soll_kg = dlv_soll / gewicht * 100 if gewicht > 0 else None
    else:
        delta = delta_pct = dinas_erloese_kg = dlv_soll_kg = None

    plz_raw = str(row.get('Empfänger PLZ', '') or '').strip()
    import re
    plz2 = re.sub(r'[^A-Z0-9]', '', plz_raw.upper())[:2]
    route = f"CH-{plz2}" if plz2 else 'CH-?'

    rows_out.append({
        'route':              route,
        'Empfänger PLZ':      plz_raw,
        'Empfänger Ort':      row.get('Empfänger Ort', ''),
        'Tonnage (eff.)':     gewicht,
        'Lademeter':          row.get('Lademeter', ''),
        'Erloese':            erloese if erloese > 0 else None,
        'dinas_erloese_kg':   round(dinas_erloese_kg, 4) if dinas_erloese_kg else None,
        'dlv_soll':           round(dlv_soll, 4) if dlv_soll else None,
        'dlv_soll_kg':        round(dlv_soll_kg, 4) if dlv_soll_kg else None,
        'delta_pct':          round(delta_pct, 2) if delta_pct is not None else None,
        'zone_matched':       lookup_res.get('zone_matched', ''),
        'weight_band_matched':lookup_res.get('weight_band_matched', ''),
        'Ausgangsbordero':    row.get('Ausgangsbordero', ''),
        'periode':            row.get('periode', ''),
    })

df_drill = pd.DataFrame(rows_out)
drill_path = OUT / '9a1e_geze_ch_drilldown.csv'
df_drill.to_csv(drill_path, index=False, float_format='%.4f')
print(f"Written: {drill_path} ({len(df_drill)} rows)")

# ---------------------------------------------------------------------------
# Schritt 2 — DLV tariff cells for CH
# ---------------------------------------------------------------------------
ch_tariff = tariff[tariff['country'] == 'Schweiz'].copy()

dlv_path = (BASE / 'GEZE Leonberg/2025/'
            '20250305_Geze_Export_incl. MP_ PT_GB_IT_FR_AT_ES_CH_inkl. Maut und Zusatzkosten IT-00_ERGÄNZT UM DUBLIN.xlsx')

txt_lines = [
    f"DLV-Datei: {dlv_path}",
    f"Sheet: Exporttarife, Block: Schweiz",
    f"Tarif-Zellen für CH (country='Schweiz'): {len(ch_tariff)} rows",
    "",
]

if not ch_tariff.empty:
    # Show unique zones and their PLZ ranges
    zones = ch_tariff[['zone', 'plz_prefix', 'min_price']].drop_duplicates()
    txt_lines.append("Zonen und PLZ-Bereiche:")
    for _, zr in zones.iterrows():
        txt_lines.append(f"  {zr['zone']:12s} PLZ={zr['plz_prefix']:20s} Minimum={zr['min_price']}")
    txt_lines.append("")

    # Show sample weight bands for each zone
    txt_lines.append("Preise pro 100kg je Gewichtsband (erste Zone):")
    first_zone = ch_tariff['zone'].iloc[0]
    zone_rates = ch_tariff[ch_tariff['zone'] == first_zone][
        ['weight_band_raw', 'price_per_100kg']
    ].drop_duplicates().sort_values('price_per_100kg')
    for _, r in zone_rates.iterrows():
        txt_lines.append(f"  {r['weight_band_raw']:20s} → {r['price_per_100kg']:.2f} EUR/100kg")

txt_path = OUT / '9a1e_geze_ch_dlv_sheet.txt'
txt_path.write_text('\n'.join(txt_lines))
print(f"Written: {txt_path}")
print('\n'.join(txt_lines))

# ---------------------------------------------------------------------------
# Schritt 3 — Spread histogram from 9a1d_routes_validation.csv
# ---------------------------------------------------------------------------
print("\n=== Spread-Histogramm (Klasse 'streut, prüfen') ===")
val_df = pd.read_csv(OUT / '9a1d_routes_validation.csv')
streut = val_df[val_df['interpretation'] == 'streut, prüfen'].copy()
print(f"Routen 'streut, prüfen': {len(streut)}")

bins = [0, 2, 5, 10, 20, float('inf')]
labels = ['≤2pp', '2-5pp', '5-10pp', '10-20pp', '>20pp']
streut['spread_bin'] = pd.cut(streut['spread'], bins=bins, labels=labels, right=True)

print("\nSpread-Histogramm:")
hist = streut['spread_bin'].value_counts().reindex(labels)
for label, cnt in hist.items():
    print(f"  {label:8s}: {cnt:4d}")

print("\nTop-5 Routen mit größtem Spread:")
top5 = streut.nlargest(5, 'spread')[
    ['kunde', 'route', 'tarifgruppe', 'n', 'median_pct', 'min_pct', 'max_pct', 'spread']
]
print(top5.to_string(index=False))

# ---------------------------------------------------------------------------
# Schritt 4 — Summary output (printed above; repeat key facts)
# ---------------------------------------------------------------------------
print("\n=== GEZE-CH Beispiel-Sendungen (erste 3 mit dlv_soll) ===")
sample = df_drill[df_drill['dlv_soll'].notna()].head(3)
print(sample[['route','Tonnage (eff.)','Erloese','dlv_soll','delta_pct',
              'zone_matched','weight_band_matched']].to_string(index=False))
