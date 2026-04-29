"""Excel Schritt 3 — Sheets Bitzer / Groz-Beckert / HELU / Hornschuch / SikaDE."""
import sys, pickle, numpy as np
from pathlib import Path
from openpyxl import load_workbook
sys.path.insert(0, "src")
from build_excel_helpers import mc, write_scope_sheet

OUT = Path("output/erka_lieferung/Sendungs_Gegenueberstellung_v1_0.xlsx")

def ld(p):
    with open(p,'rb') as f: return pickle.load(f)

def to_rows_ok(ok, basis_col="ton", maut_col=None, notes_col=None, land_col="land"):
    if "delta" not in ok.columns:
        ok = ok.copy(); ok["delta"] = ok["ef"] - ok["dlv"]
    if "mclass" not in ok.columns:
        ok = ok.copy(); ok["mclass"] = ok["fp"].apply(mc)
    rows = []
    for _, r in ok.iterrows():
        fp_val = float(r["fp"]) if not np.isnan(float(r["fp"])) else None
        b = ""
        if basis_col in r.index:
            v = r[basis_col]
            if v is not None and not (isinstance(v,float) and np.isnan(v)):
                b = round(float(v),1)
        nt = ""
        if notes_col and notes_col in r.index and r[notes_col]:
            nt = str(r[notes_col])[:60]
        rows.append({
            "land": str(r.get(land_col, r.get("land",""))),
            "plz": str(r.get("plz","")),
            "basis": b,
            "ef": round(float(r["ef"]),2),
            "maut": 0.0,
            "diesel": 0.0,
            "dlv": round(float(r["dlv"]),2),
            "delta": round(float(r["delta"]),2),
            "fp_pct": fp_val,
            "mclass": str(r.get("mclass","")),
            "notes": nt,
        })
    return rows

wb = load_workbook(OUT)

# Bitzer
g = ld("output/bitzer_step23_results_v196_postfix.pkl")
rows = to_rows_ok(g["ok"], basis_col="billing_kg", notes_col="tarifgruppe")
meta = f"Bitzer SE | KNR 406345 | {len(rows)} Zeilen | Σ ef={sum(r['ef'] for r in rows):,.0f} EUR"
write_scope_sheet(wb, "Bitzer 406345", rows, meta)
print(f"Bitzer: {len(rows)} rows")

# Groz-Beckert
g = ld("output/groz_beckert_step23_results_v196.pkl")
rows = to_rows_ok(g["ok"], basis_col="ton", notes_col="tarifgruppe" if "tarifgruppe" in g["ok"].columns else None)
meta = f"Groz-Beckert | KNR 490527/410912/527373 | {len(rows)} Zeilen | Σ ef={sum(r['ef'] for r in rows):,.0f} EUR"
write_scope_sheet(wb, "Groz-Beckert 490527+", rows, meta)
print(f"Groz-Beckert: {len(rows)} rows")

# HELU
g = ld("output/helu_step23_results_v196.pkl")
rows = to_rows_ok(g["ok"], basis_col="ton", notes_col="tarifgruppe" if "tarifgruppe" in g["ok"].columns else None)
meta = f"HELU-KABEL GmbH | KNR 408244 | {len(rows)} Zeilen | Σ ef={sum(r['ef'] for r in rows):,.0f} EUR"
write_scope_sheet(wb, "HELU 408244", rows, meta)
print(f"HELU: {len(rows)} rows")

# Hornschuch
g = ld("output/hornschuch_step23_results_v196.pkl")
rows = to_rows_ok(g["ok"], basis_col="ton", notes_col="zone" if "zone" in g["ok"].columns else None)
meta = f"Hornschuch AG | KNR 490085 | {len(rows)} Zeilen | Σ ef={sum(r['ef'] for r in rows):,.0f} EUR"
write_scope_sheet(wb, "Hornschuch 490085", rows, meta)
print(f"Hornschuch: {len(rows)} rows")

# Sika DE
g = ld("output/sika_welle1_step23_results_v197.pkl")
ok_de = g["ok"][g["ok"]["knr"]==491063].copy()
rows = to_rows_ok(ok_de, basis_col="stp_eff", notes_col="dlv_file" if "dlv_file" in ok_de.columns else None)
meta = f"Sika Deutschland GmbH | KNR 491063 | {len(rows)} Zeilen | Σ ef={sum(r['ef'] for r in rows):,.0f} EUR | P20.1 adj +30.555 EUR"
write_scope_sheet(wb, "Sika DE 491063", rows, meta)
print(f"Sika DE: {len(rows)} rows")

wb.save(OUT)
print(f"Saved: {OUT}")
