"""EBM-Papst (410844) Dinas-AX Vergleich Excel."""
import sys, pickle, math
from pathlib import Path
import pandas as pd
sys.path.insert(0,"src")
from build_vergleich_helpers import load_zgi_map, build_and_save, _safe

OUT = Path("output/erka_lieferung/EBM_Vergleich.xlsx")

from tms.tariff.calculators.ebm import EBMCalculator
_calc = EBMCalculator()

def soll_fn(land, plz, ton, ldm, stp):
    try:
        n = max(1, int(round(float(stp)))) if stp and str(stp).strip() not in ('','nan') else 1
        r = _calc.calculate(empf_plz=str(plz).strip(), empf_land=str(land).strip(), stellplaetze=n)
        # Extract billing_pallets from notes
        bm = n
        bl = f"{n} Stp"
        zone = next((v.split('=')[1] for v in r.notes if v.startswith('zone')), "")
        return (float(r.basispreis), bl, zone, "EUR/Stp", bm)
    except Exception:
        return (None, None, None, "EUR/Stp", None)

with open("output/bi_top20_data.pkl","rb") as f:
    bi = pickle.load(f)["df"]
dinas = pickle.load(open("output/dinas_cache_410844.pkl","rb"))
post  = bi[(bi["Kunden Nr BK"]==410844)&(bi["periode"]=="POST")].copy()
zgi   = load_zgi_map("EBM.xlsx")

n_clust, n_d, n_a = build_and_save(
    [410844], dinas, post, zgi, soll_fn,
    "EBM-Papst Mulfingen", OUT, "EBM.xlsx")
print(f"EBM: {n_clust} Cluster, {n_d} Dinas, {n_a} AX  → {OUT}")
