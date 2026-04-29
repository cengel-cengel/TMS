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

# §8 Ausnahmen: (RN, PLZ)-Paare explizit als anomale Billing-Fälle klassifiziert
# (aus build_9c2b_cht_es_calculator_test.py KNOWN_S8)
_KNOWN_S8 = {("924029","46890"), ("924029","08310"),
             ("924040","46890"), ("924145","46890")}

def soll_fn(land, plz, ton, ldm, stp, vers_plz=None):
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

# Filter §8 KNOWN_S8 rows (documented anomalies, not billing errors)
post["_rn"]  = post["Rechnungsnummer"].astype(str).str.strip()
post["_plz"] = post["Empfänger PLZ"].astype(str).str.strip()
post = post[~post.apply(lambda r: (r["_rn"], r["_plz"]) in _KNOWN_S8, axis=1)].copy()

# Filter split-positions: ton < 2 kg (sub-fragments of multi-PLZ shipments)
post["_ton"] = pd.to_numeric(post["Tonnage (eff.)"], errors="coerce").fillna(0)
post = post[(post["_ton"] == 0) | (post["_ton"] >= 2.0)].copy()

zgi   = load_zgi_map("CHT.xlsx")

n_clust, n_d, n_a = build_and_save(
    [486073], dinas, post, zgi, soll_fn,
    "CHT Germany GmbH", OUT, "CHT.xlsx")
print(f"CHT: {n_clust} Cluster, {n_d} Dinas, {n_a} AX  → {OUT}")
