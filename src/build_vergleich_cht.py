"""CHT Germany (486073) Dinas-AX Vergleich Excel."""
import sys, pickle, math
from pathlib import Path
import pandas as pd
sys.path.insert(0,"src")
from build_vergleich_helpers import load_zgi_map, build_and_save

OUT = Path("output/erka_lieferung/CHT_Vergleich.xlsx")

from tms.tariff.calculators.cht import CHTItalyCalculator
from tms.tariff.calculators.cht_be import CHTBelgiumCalculator
from tms.tariff.calculators.cht_es import CHTSpainCalculator
from tms.tariff.calculators.cht_at import CHTAustriaCalculator

_calcs = {"IT": CHTItalyCalculator(), "BE": CHTBelgiumCalculator(),
          "ES": CHTSpainCalculator(), "AT": CHTAustriaCalculator()}

def soll_fn(land, plz, ton, ldm, stp):
    calc = _calcs.get(str(land).upper().strip())
    if calc is None:
        return (None, None, None, "EUR/100kg", None)
    try:
        t = float(ton) if ton else 0.0
        r = calc.calculate(empf_plz=str(plz).strip(), empf_land=str(land).strip(), tonnage_kg=t)
        bk = float(next((v.split('=')[1] for v in r.notes if v.startswith('billing_kg')),
                        math.ceil(t/100)*100))
        bl = f"bis {bk:.0f}kg"
        return (float(r.basispreis), bl, "", "EUR/100kg", bk)
    except Exception:
        return (None, None, None, "EUR/100kg", None)

with open("output/bi_top20_data.pkl","rb") as f:
    bi = pickle.load(f)["df"]
dinas = pickle.load(open("output/dinas_cache_486073.pkl","rb"))
post  = bi[(bi["Kunden Nr BK"]==486073)&(bi["periode"]=="POST")].copy()
zgi   = load_zgi_map("CHT.xlsx")

n_clust, n_d, n_a = build_and_save(
    [486073], dinas, post, zgi, soll_fn,
    "CHT Germany GmbH", OUT, "CHT.xlsx")
print(f"CHT: {n_clust} Cluster, {n_d} Dinas, {n_a} AX  → {OUT}")
