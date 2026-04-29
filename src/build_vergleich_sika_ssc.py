"""Sika SSC (511241) Dinas-AX Vergleich Excel."""
import sys, pickle
from pathlib import Path
import pandas as pd
sys.path.insert(0,"src")
from build_vergleich_helpers import load_zgi_map, build_and_save

OUT = Path("output/erka_lieferung/Sika_SSC_Vergleich.xlsx")

from tms.tariff.calculators.ssc import SSCCalculator
_calc = SSCCalculator()

def soll_fn(land, plz, ton, ldm, stp):
    try:
        n = max(1, int(round(float(stp)))) if stp and str(stp).strip() not in ('','nan') else 1
        r = _calc.calculate(empf_plz=str(plz).strip(), empf_land=str(land).strip(), stellplaetze=n)
        zone = next((v.split('=')[1] for v in r.notes if v.startswith('zone')), "")
        bl = f"{n} Stp"
        return (float(r.basispreis), bl, zone, "EUR/Stp", n)
    except Exception:
        return (None, None, None, "EUR/Stp", None)

with open("output/bi_top20_data.pkl","rb") as f:
    bi = pickle.load(f)["df"]
dinas = pickle.load(open("output/dinas_cache_ssc_511241.pkl","rb"))
post  = bi[(bi["Kunden Nr BK"]==511241)&(bi["periode"]=="POST")].copy()
zgi   = load_zgi_map("Sika.xlsx")

n_clust, n_d, n_a = build_and_save(
    [511241], dinas, post, zgi, soll_fn,
    "Sika SSC (ssc_eu)", OUT, "Sika.xlsx")
print(f"Sika SSC: {n_clust} Cluster, {n_d} Dinas, {n_a} AX  → {OUT}")
