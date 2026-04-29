"""
Sika ATM — Step 2+3 Pipeline v1.9.7
KNR: 527406 (Sika Automotive AG, Romanshorn CH — ERKA-Nr 18748)

Tariff: weight-band flat EUR/Sendung (Anlage 1 KORRIGIERT, 2024-07-01–2026-06-30)
Source: output/bi_cache_sika_527406.pkl
Output: output/sika_atm_step23_results_v197.pkl

Known pre-existing deviations:
  RS (34000 Kragujevac): DLV rates +20–43% above billed → separate rate agreement
  DE (1 row, 70499 Stuttgart): not nominated (ERKA = 0) → dlv_luecke
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))

from tms.tariff.calculators.sika_atm import SikaATMChCalculator

# ── Config ────────────────────────────────────────────────────────────────────
SCOPE_KNR  = 527406
INPUT_PKL  = Path("output/bi_cache_sika_527406.pkl")
OUTPUT_PKL = Path("output/sika_atm_step23_results_v197.pkl")

calc = SikaATMChCalculator()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _nonempty(v) -> bool:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return False
    return str(v).strip() not in ("", "nan", "None")


def _mclass(fp):
    if fp is None or (isinstance(fp, float) and np.isnan(fp)):
        return None
    if abs(fp) <= 0.05:
        return "M1"
    if fp < -0.05:
        return "M2"
    return "M_over"


# ── Load BI cache ─────────────────────────────────────────────────────────────
print(f"Loading {INPUT_PKL} ...")
raw = pd.read_pickle(INPUT_PKL)

raw["ef"]  = pd.to_numeric(raw["Erlöse Fracht"],  errors="coerce").fillna(0)
raw["ton"] = pd.to_numeric(raw["Tonnage (eff.)"], errors="coerce").fillna(0)

raw["has_ms"] = raw["Mastersendung"].apply(_nonempty)
raw["has_ua"] = raw["Unterauftrag"].apply(_nonempty)
raw["is_sub"] = raw["has_ms"] & ~raw["has_ua"]

raw["ship_dt"] = pd.to_datetime(raw["Leistungsdatum"], errors="coerce").dt.date

# ── Pool filters ──────────────────────────────────────────────────────────────
pool_raw = raw[raw["ef"] > 0].copy()
pool     = pool_raw[~pool_raw["is_sub"]].copy()

n_sub      = pool_raw["is_sub"].sum()
n_ton_zero = (pool["ton"] == 0).sum()

print(f"Pool roh (ef>0):              {len(pool_raw)}")
print(f"  is_sub:                     {n_sub}")
print(f"  Sub Tonnage=0:              {pool_raw[pool_raw['is_sub']]['ton'].eq(0).sum()}")
print(f"  Sub Tonnage>0:              {pool_raw[pool_raw['is_sub']]['ton'].gt(0).sum()}")
print(f"Pipeline pool (ef>0 ~sub):    {len(pool)}")
print(f"  Tonnage=0 (im Pool):        {n_ton_zero}  → unbeurteilbar")
print(f"  Empfänger Land: {dict(pool['Empfänger Land'].value_counts())}")

# ── Calculator run ─────────────────────────────────────────────────────────────
results = []

for idx, row in pool.iterrows():
    land = str(row["Empfänger Land"]).strip().upper()
    plz  = str(row["Empfänger PLZ"]).strip()
    ton  = float(row["ton"])
    ef   = float(row["ef"])

    if ton == 0:
        results.append({
            "idx": idx, "land": land, "plz": plz, "ton": ton, "ef": ef,
            "dlv": None, "delta": None, "fp": None,
            "scope": "ton_zero", "notes": ["Tonnage=0"],
        })
        continue

    try:
        r = calc.calculate(empf_plz=plz, empf_land=land, tonnage_kg=ton)
        dlv_val = float(r.basispreis)
        delta   = ef - dlv_val
        fp      = delta / dlv_val if dlv_val else None
        results.append({
            "idx": idx, "land": land, "plz": plz, "ton": ton, "ef": ef,
            "dlv": dlv_val, "delta": delta, "fp": fp,
            "scope": "ok",
            "notes": r.notes,
        })
    except LookupError as e:
        results.append({
            "idx": idx, "land": land, "plz": plz, "ton": ton, "ef": ef,
            "dlv": None, "delta": None, "fp": None,
            "scope": "dlv_luecke",
            "notes": [str(e)[:120]],
        })

df_res = pd.DataFrame(results)
df_res["mclass"] = df_res["fp"].apply(_mclass)

# ── Step 3 summaries ──────────────────────────────────────────────────────────
ok = df_res[df_res["scope"] == "ok"].copy()

print(f"\n=== Step 3 Results  KNR {SCOPE_KNR} ===")
print(f"Pipeline pool:    {len(pool)}")
print(f"Beurteilbar (ok): {len(ok)}")
print(f"dlv_luecke:       {(df_res['scope']=='dlv_luecke').sum()}")
print(f"ton_zero:         {(df_res['scope']=='ton_zero').sum()}")

if len(ok):
    m1  = (ok["mclass"] == "M1").sum()
    m2  = (ok["mclass"] == "M2").sum()
    mov = (ok["mclass"] == "M_over").sum()
    sum_ef  = ok["ef"].sum()
    sum_dlv = ok["dlv"].sum()
    net     = ok["delta"].sum()
    fp_net  = net / sum_dlv if sum_dlv else 0
    print(f"\nM1={m1} ({100*m1/len(ok):.1f}%)  M2={m2} ({100*m2/len(ok):.1f}%)  "
          f"M_over={mov} ({100*mov/len(ok):.1f}%)")
    print(f"Σef = {sum_ef:,.2f} EUR")
    print(f"Σdlv= {sum_dlv:,.2f} EUR")
    print(f"Net Δ = {net:+,.2f} EUR  ({fp_net:+.4%})")

# Land breakdown (beurteilbar)
print("\nLand-Breakdown (beurteilbar):")
for land, grp in ok.groupby("land"):
    net = grp["delta"].sum()
    sdlv = grp["dlv"].sum()
    fp  = net / sdlv if sdlv else 0
    m1c = (grp["mclass"] == "M1").sum()
    m2c = (grp["mclass"] == "M2").sum()
    mvc = (grp["mclass"] == "M_over").sum()
    print(f"  {land}: n={len(grp)}, Σef={grp['ef'].sum():,.0f}, "
          f"Δ={net:+.0f} ({fp:+.2%}), M1={m1c} M2={m2c} M_ov={mvc}")

# dlv_luecke detail
luecke = df_res[df_res["scope"] == "dlv_luecke"]
if len(luecke):
    print(f"\ndlv_luecke rows ({len(luecke)}):")
    print(luecke[["land","plz","ton","ef","notes"]].to_string(index=False))

# Top deviations
print("\nTop M2 + M_over rows (|Δ| largest):")
dev = ok[ok["mclass"].isin(["M2","M_over"])].copy()
dev["abs_delta"] = dev["delta"].abs()
top = dev.nlargest(15, "abs_delta")
print(top[["land","plz","ton","ef","dlv","delta","fp","mclass"]].to_string(index=False))

# ── Save ─────────────────────────────────────────────────────────────────────
OUTPUT_PKL.parent.mkdir(exist_ok=True)

land_summary = ok.groupby("land").agg(
    n=("ef","count"),
    sum_ef=("ef","sum"),
    sum_dlv=("dlv","sum"),
    sum_delta=("delta","sum"),
    m1=("mclass", lambda x: (x=="M1").sum()),
    m2=("mclass", lambda x: (x=="M2").sum()),
    mover=("mclass", lambda x: (x=="M_over").sum()),
).assign(fp_net=lambda d: d["sum_delta"]/d["sum_dlv"])

save = {
    "df_res":        df_res,
    "ok":            ok,
    "n_pool_raw":    len(pool_raw),
    "n_is_sub":      int(n_sub),
    "n_ton_zero_sub": int(pool_raw[pool_raw["is_sub"]]["ton"].eq(0).sum()),
    "n_ton_gt0_sub": int(pool_raw[pool_raw["is_sub"]]["ton"].gt(0).sum()),
    "n_pipeline":    len(pool),
    "n_beurteilbar": len(ok),
    "n_luecke":      int((df_res["scope"]=="dlv_luecke").sum()),
    "n_ton_zero":    int(n_ton_zero),
    "sum_ef_pool":   float(pool_raw["ef"].sum()),
    "sum_ef_ok":     float(ok["ef"].sum()),
    "sum_dlv_ok":    float(ok["dlv"].sum()),
    "net_delta":     float(ok["delta"].sum()),
    "fp_net":        float(ok["delta"].sum() / ok["dlv"].sum()) if ok["dlv"].sum() else 0.0,
    "land_summary":  land_summary,
    "m1": int((ok["mclass"]=="M1").sum()),
    "m2": int((ok["mclass"]=="M2").sum()),
    "mover": int((ok["mclass"]=="M_over").sum()),
}
pd.to_pickle(save, OUTPUT_PKL)
print(f"\nSaved → {OUTPUT_PKL}")
