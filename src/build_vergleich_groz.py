"""Groz-Beckert (490527+) Dinas-AX Vergleich Excel."""
import sys, pickle
from pathlib import Path
import pandas as pd
sys.path.insert(0,"src")
from build_vergleich_helpers import load_zgi_map, build_and_save

OUT = Path("output/erka_lieferung/Groz_Beckert_Vergleich.xlsx")

from tms.tariff.calculators.groz_beckert import GrozBeckertCalculator
_calc = GrozBeckertCalculator()

def soll_fn(land, plz, ton, ldm, stp):
    try:
        t = float(ton) if ton else 0.0
        l = float(ldm) if ldm and str(ldm).strip() not in ('','nan') else 0.0
        r = _calc.calculate(empf_plz=str(plz).strip(), empf_land=str(land).strip(),
                            tonnage_kg=t if t>0 else None, lademeter=l if l>0 else None)
        zone = next((v.replace('dest_zone=','') for v in r.notes if 'dest_zone' in v), "")
        bl = "GC" if 'mode=GC' in r.notes else "LTL"
        return (float(r.basispreis), bl, zone, "EUR/Sendung", 1)
    except Exception:
        return (None, None, None, "EUR/Sendung", None)

# Groz uses separate bi_cache
groz_ax = pickle.load(open("output/bi_cache_groz_beckert.pkl","rb"))
dinas = pickle.load(open("output/dinas_cache_groz_beckert.pkl","rb"))
post  = groz_ax[groz_ax["periode"]=="POST"].copy() if "periode" in groz_ax.columns else groz_ax.copy()
zgi   = load_zgi_map("Groz.xlsx")

knrs = [490527, 410912, 527373, 527410]
n_clust, n_d, n_a = build_and_save(
    knrs, dinas, post, zgi, soll_fn,
    "Groz-Beckert KG", OUT, "Groz.xlsx")
print(f"Groz-Beckert: {n_clust} Cluster, {n_d} Dinas, {n_a} AX  → {OUT}")
