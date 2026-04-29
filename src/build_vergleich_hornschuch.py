"""Hornschuch AG (490085) Dinas-AX Vergleich Excel."""
import sys, pickle, re
from pathlib import Path
import pandas as pd
sys.path.insert(0,"src")
from build_vergleich_helpers import load_zgi_map, build_and_save

OUT = Path("output/erka_lieferung/Hornschuch_Vergleich.xlsx")

from tms.tariff.calculators.hornschuch import HornschuchCalculator
_calc = HornschuchCalculator()

def soll_fn(land, plz, ton, ldm, stp):
    try:
        t = float(ton) if ton else 0.0
        r = _calc.calculate(empf_plz=str(plz).strip(), empf_land=str(land).strip(), tonnage_kg=t)
        # notes: "zone=AT-4, 500.0kg, rate=0.2735€/kg"
        zone_note = next((v for v in r.notes if 'zone=' in v and 'kg' in v), "")
        zm = re.search(r'zone=(\S+),\s*([\d.]+)kg', zone_note)
        zone = zm.group(1) if zm else ""
        bl = f"{t:.0f}kg"
        return (float(r.basispreis), bl, zone, "EUR/kg", t)
    except Exception:
        return (None, None, None, "EUR/kg", None)

with open("output/bi_top20_data.pkl","rb") as f:
    bi = pickle.load(f)["df"]
dinas = pickle.load(open("output/dinas_cache_490085.pkl","rb"))
post  = bi[(bi["Kunden Nr BK"]==490085)&(bi["periode"]=="POST")].copy()
zgi   = load_zgi_map("Hornschuch.xlsx")

n_clust, n_d, n_a = build_and_save(
    [490085], dinas, post, zgi, soll_fn,
    "Hornschuch AG", OUT, "Hornschuch.xlsx")
print(f"Hornschuch: {n_clust} Cluster, {n_d} Dinas, {n_a} AX  → {OUT}")
