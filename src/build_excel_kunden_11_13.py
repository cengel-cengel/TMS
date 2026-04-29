"""Excel Schritt 4 — Sheets Sika SSC / Sika Import / Sika ATM."""
import sys, pickle, numpy as np
from pathlib import Path
from openpyxl import load_workbook
sys.path.insert(0, "src")
from build_excel_helpers import mc, write_scope_sheet

OUT = Path("output/erka_lieferung/Sendungs_Gegenueberstellung_v1_0.xlsx")

def ld(p):
    with open(p,'rb') as f: return pickle.load(f)

wb = load_workbook(OUT)

# Sika SSC
g = ld("output/sika_welle1_step23_results_v197.pkl")
ok_ssc = g["ok"][g["ok"]["knr"]==511241].copy()
if "mclass" not in ok_ssc.columns:
    ok_ssc["mclass"] = ok_ssc["fp"].apply(mc)
if "delta" not in ok_ssc.columns:
    ok_ssc["delta"] = ok_ssc["ef"] - ok_ssc["dlv"]
rows = []
for _, r in ok_ssc.iterrows():
    fp_val = float(r["fp"]) if not np.isnan(float(r["fp"])) else None
    rows.append({
        "land": str(r.get("land","")),
        "plz": str(r.get("plz","")),
        "basis": round(float(r["stp_eff"]),1) if r.get("stp_eff") else "",
        "ef": round(float(r["ef"]),2),
        "maut": 0.0, "diesel": 0.0,
        "dlv": round(float(r["dlv"]),2),
        "delta": round(float(r["delta"]),2),
        "fp_pct": fp_val,
        "mclass": str(r.get("mclass","")),
        "notes": str(r.get("scope",""))[:40],
    })
meta = f"Sika SSC | KNR 511241 (ssc_eu) | {len(rows)} Zeilen | Σ ef={sum(r['ef'] for r in rows):,.0f} EUR"
write_scope_sheet(wb, "Sika SSC 511241", rows, meta)
print(f"Sika SSC: {len(rows)} rows")

# Sika Import
g = ld("output/sika_import_step23_results_v197.pkl")
ok = g["ok"].copy()
if "mclass" not in ok.columns:
    ok["mclass"] = ok["fp"].apply(mc)
rows = []
for _, r in ok.iterrows():
    fp_val = float(r["fp"]) if not np.isnan(float(r["fp"])) else None
    maut_v = float(r["maut_bi"]) if "maut_bi" in r.index and r["maut_bi"] else 0.0
    dlv_v = float(r["dlv"]) if r["dlv"] else 0.0
    ef_v = float(r["ef"])
    delta_v = float(r.get("delta", ef_v - dlv_v))
    rows.append({
        "land": str(r.get("vers_land","")),
        "plz": str(r.get("vers_plz","")),
        "basis": round(float(r["stp_eff"]),1) if r.get("stp_eff") else "",
        "ef": round(ef_v,2),
        "maut": round(maut_v,2),
        "diesel": 0.0,
        "dlv": round(dlv_v,2),
        "delta": round(delta_v,2),
        "fp_pct": fp_val,
        "mclass": str(r.get("mclass","")),
        "notes": "P20.1 adj: ef_total=ef+Maut",
    })
meta = f"Sika Import-Flow | KNR 511241 | {len(rows)} Zeilen | Σ ef={sum(r['ef'] for r in rows):,.0f} EUR | P20.1 adj +18.306 EUR"
write_scope_sheet(wb, "Sika Import 511241", rows, meta)
print(f"Sika Import: {len(rows)} rows")

# Sika ATM
g = ld("output/sika_atm_step23_results_v197.pkl")
df_res = g["df_res"].copy()
rows = []
for _, r in df_res.iterrows():
    scope_v = str(r.get("scope",""))
    mc_v = str(r.get("mclass","")) if r.get("mclass") else scope_v
    dlv_v = float(r["dlv"]) if r["dlv"] is not None and not (isinstance(r["dlv"],float) and np.isnan(r["dlv"])) else 0.0
    delta_v = float(r["delta"]) if r["delta"] is not None and not (isinstance(r["delta"],float) and np.isnan(r["delta"])) else 0.0
    fp_val = float(r["fp"]) if r["fp"] is not None and not (isinstance(r["fp"],float) and np.isnan(r["fp"])) else None
    nt = scope_v if scope_v not in ("ok","") else ""
    rows.append({
        "land": str(r.get("land","")),
        "plz": str(r.get("plz","")),
        "basis": round(float(r["ton"]),1) if r["ton"] else "",
        "ef": round(float(r["ef"]),2),
        "maut": 0.0, "diesel": 0.0,
        "dlv": round(dlv_v,2),
        "delta": round(delta_v,2),
        "fp_pct": fp_val,
        "mclass": mc_v if mc_v in ("M1","M2","M_over") else ("dlv_luecke" if scope_v=="dlv_luecke" else ""),
        "notes": nt,
    })
meta = f"Sika ATM | KNR 527406 | {len(rows)} Zeilen | 395 beurteilbar | RS pre-existing"
write_scope_sheet(wb, "Sika ATM 527406", rows, meta)
print(f"Sika ATM: {len(rows)} rows")

wb.save(OUT)
print(f"Saved: {OUT}")
