"""Bitzer SE (406345) Dinas-AX Vergleich Excel."""
import sys, pickle, math
from pathlib import Path
import pandas as pd
sys.path.insert(0,"src")
from build_vergleich_helpers import load_zgi_map, build_and_save

OUT = Path("output/erka_lieferung/Bitzer_Vergleich.xlsx")

from tms.tariff.calculators.bitzer import BitzCalculator
_calc = BitzCalculator()

def soll_fn(land, plz, ton, ldm, stp):
    try:
        t = float(ton) if ton else 0.0
        r = _calc.calculate(empf_plz=str(plz).strip(), empf_land=str(land).strip(), tonnage_kg=t)
        bk = float(next((v.split('=')[1] for v in r.notes if v.startswith('billing_kg')),
                        max(100, math.ceil(t/100)*100)))
        zone = next((v.split('=')[1] for v in r.notes if v.startswith('zone')), "")
        bl = f"bis {bk:.0f}kg"
        return (float(r.basispreis), bl, zone, "EUR/100kg", bk)
    except Exception:
        return (None, None, None, "EUR/100kg", None)

with open("output/bi_top20_data.pkl","rb") as f:
    bi = pickle.load(f)["df"]
dinas = pickle.load(open("output/dinas_cache_406345.pkl","rb"))
post  = bi[(bi["Kunden Nr BK"]==406345)&(bi["periode"]=="POST")].copy()
zgi   = load_zgi_map("Bitzer.xlsx")

n_clust, n_d, n_a = build_and_save(
    [406345], dinas, post, zgi, soll_fn,
    "Bitzer SE", OUT, "Bitzer.xlsx")
print(f"Bitzer: {n_clust} Cluster, {n_d} Dinas, {n_a} AX  → {OUT}")
