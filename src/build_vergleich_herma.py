"""HERMA GmbH (423650) Dinas-AX Vergleich Excel."""
import sys, pickle, math
from pathlib import Path
import pandas as pd
sys.path.insert(0,"src")
from build_vergleich_helpers import load_zgi_map, build_and_save

OUT = Path("output/erka_lieferung/HERMA_Vergleich.xlsx")

from tms.tariff.calculators.herma import HermaCalculator
_calc = HermaCalculator()

_HERMA_LIMITS = [50,100,150,200,250,300,500,1000,2000,3000]

def _herma_band(bw):
    for lim in _HERMA_LIMITS:
        if bw <= lim: return f"bis {lim}kg"
    return "über 3000kg"

def soll_fn(land, plz, ton, ldm, stp, vers_plz=None):
    try:
        t = float(ton) if ton else 0.0
        l = float(ldm) if ldm and str(ldm).strip() not in ('','nan') else 0.0
        r = _calc.calculate(empf_plz=str(plz).strip(), empf_land=str(land).strip(),
                            tonnage_kg=t, lademeter=l)
        bw = float(next((v.split('=')[1] for v in r.notes if v.startswith('billing_wt')), t))
        zone = next((v.split('=')[1] for v in r.notes if v.startswith('zone')), "")
        bl   = _herma_band(bw)
        return (float(r.basispreis), bl, zone, "EUR/Sendung", bw)
    except Exception:
        return (None, None, None, "EUR/Sendung", None)

with open("output/bi_top20_data.pkl","rb") as f:
    bi = pickle.load(f)["df"]
dinas = pickle.load(open("output/dinas_cache_423650.pkl","rb"))
post  = bi[(bi["Kunden Nr BK"]==423650)&(bi["periode"]=="POST")].copy()
zgi   = load_zgi_map("Herma.xlsx")

n_clust, n_d, n_a = build_and_save(
    [423650], dinas, post, zgi, soll_fn,
    "HERMA GmbH", OUT, "Herma.xlsx")
print(f"HERMA: {n_clust} Cluster, {n_d} Dinas, {n_a} AX  → {OUT}")
