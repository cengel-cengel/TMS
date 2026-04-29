"""Excel Schritt 2 — Sheets GEZE / EBM / Fischerwerke / HERMA / CHT."""
import sys, pickle, numpy as np
from pathlib import Path
from openpyxl import load_workbook
sys.path.insert(0, "src")
from build_excel_helpers import mc, write_scope_sheet

OUT = Path("output/erka_lieferung/Sendungs_Gegenueberstellung_v1_0.xlsx")

def ld(p):
    with open(p,'rb') as f: return pickle.load(f)

def to_rows_rdf(rdf, maut_col=None, diesel_col=None, basis_col="ton", notes_col=None):
    """Convert cluster-format rdf to scope rows."""
    if "delta" not in rdf.columns:
        rdf = rdf.copy()
        rdf["delta"] = rdf["ef"] - rdf["dlv"]
    if "mclass" not in rdf.columns:
        rdf = rdf.copy()
        rdf["mclass"] = rdf["fp"].apply(mc)
    rows = []
    for _, r in rdf.iterrows():
        fp_val = float(r["fp"]) if not np.isnan(float(r["fp"])) else None
        rows.append({
            "land": r.get("land", r.get("cc","")),
            "plz": str(r.get("plz","")),
            "basis": round(float(r[basis_col]),1) if basis_col in r.index and not np.isnan(float(r[basis_col])) else "",
            "ef": round(float(r["ef"]),2),
            "maut": round(float(r[maut_col]),2) if maut_col and maut_col in r.index else 0.0,
            "diesel": 0.0,
            "dlv": round(float(r["dlv"]),2),
            "delta": round(float(r["delta"]),2),
            "fp_pct": fp_val,
            "mclass": r.get("mclass",""),
            "notes": "",
        })
    return rows

def to_rows_ok(ok, basis_col="ton", maut_col=None, notes_col="notes"):
    """Convert ok-frame to scope rows."""
    if "delta" not in ok.columns:
        ok = ok.copy()
        ok["delta"] = ok["ef"] - ok["dlv"]
    if "mclass" not in ok.columns:
        ok = ok.copy()
        ok["mclass"] = ok["fp"].apply(mc)
    rows = []
    for _, r in ok.iterrows():
        fp_val = float(r["fp"]) if not np.isnan(float(r["fp"])) else None
        b = ""
        if basis_col in r.index:
            v = r[basis_col]
            if v is not None and not (isinstance(v,float) and np.isnan(v)):
                b = round(float(v),1)
        nt = ""
        if notes_col and notes_col in r.index:
            nt = str(r[notes_col])[:60] if r[notes_col] else ""
        rows.append({
            "land": str(r.get("land","")),
            "plz": str(r.get("plz","")),
            "basis": b,
            "ef": round(float(r["ef"]),2),
            "maut": round(float(r[maut_col]),2) if maut_col and maut_col in r.index else 0.0,
            "diesel": 0.0,
            "dlv": round(float(r["dlv"]),2),
            "delta": round(float(r["delta"]),2),
            "fp_pct": fp_val,
            "mclass": r.get("mclass",""),
            "notes": nt,
        })
    return rows

wb = load_workbook(OUT)

# GEZE
g = ld("output/geze_step23_results_v196.pkl")
rows = to_rows_rdf(g["rdf"])
meta = f"GEZE GmbH | KNR 406035 | {len(rows)} Zeilen | Σ ef={sum(r['ef'] for r in rows):,.0f} EUR"
write_scope_sheet(wb, "GEZE 406035", rows, meta)
print(f"GEZE: {len(rows)} rows")

# EBM
g = ld("output/ebm_step23_results_v196.pkl")
rows = to_rows_ok(g["ok"], basis_col="stp_eff", notes_col="tarifgruppe")
meta = f"EBM-Papst | KNR 410844 | {len(rows)} Zeilen | Σ ef={sum(r['ef'] for r in rows):,.0f} EUR"
write_scope_sheet(wb, "EBM 410844", rows, meta)
print(f"EBM: {len(rows)} rows")

# Fischerwerke
g = ld("output/fischerwerke_step23_results_v196.pkl")
rows = to_rows_rdf(g["rdf"])
meta = f"Fischerwerke GmbH | KNR 409480 | {len(rows)} Zeilen | Σ ef={sum(r['ef'] for r in rows):,.0f} EUR"
write_scope_sheet(wb, "Fischerwerke 409480", rows, meta)
print(f"Fischerwerke: {len(rows)} rows")

# HERMA
g = ld("output/herma_step23_results_v196.pkl")
rows = to_rows_rdf(g["rdf"], basis_col="billing_wt")
meta = f"HERMA GmbH | KNR 423650 | {len(rows)} Zeilen | Σ ef={sum(r['ef'] for r in rows):,.0f} EUR"
write_scope_sheet(wb, "HERMA 423650", rows, meta)
print(f"HERMA: {len(rows)} rows")

# CHT
g = ld("output/cht_step23_results_v196.pkl")
rows = to_rows_rdf(g["rdf"])
meta = f"CHT Germany | KNR 486073 | {len(rows)} Zeilen | Σ ef={sum(r['ef'] for r in rows):,.0f} EUR"
write_scope_sheet(wb, "CHT 486073", rows, meta)
print(f"CHT: {len(rows)} rows")

wb.save(OUT)
print(f"Saved: {OUT}")
