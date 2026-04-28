"""
Sika Welle 1 — Step 2+3 Pipeline v1.9.7
KNRs: 491063 (Sika Deutschland GmbH / CH AG) + 511241 (SIKA Supply Center AG)
Variante B: vollumfänglich (alle Rows, Scope-Labeling im Output)
ATM 527406: NICHT in dieser Session.

Scope-Labeling 511241:
  ssc_eu   = Versender "Supply Center" AND Empf-Land != DE
  de_oos   = Empf-Land == DE (any versender)
  import_flow = Versender non-SSC AND Empf-Land != DE
  dlv_luecke  = Calculator raises LookupError
"""
from __future__ import annotations

import math
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))

from tms.tariff.calculators.sika_de import SikaDeCalculator, SSCCalculator

# ── Config ───────────────────────────────────────────────────────────────────
SCOPE_KNR = {491063, 511241}
OOS_LAND   = {"DE"}          # for KNR 491063 only (1 DE row)
OUTPUT_PKL = Path("output/sika_welle1_step23_results_v197.pkl")

calc_de  = SikaDeCalculator()
calc_ssc = SSCCalculator()

# ── Helpers ───────────────────────────────────────────────────────────────────

def _nonempty(v) -> bool:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return False
    return str(v).strip() not in ("", "nan", "None")


def _stp_eff(row) -> float:
    stp = float(row["stp"]) if _nonempty(row.get("stp")) else 0.0
    ldm = float(row["ldm"]) if _nonempty(row.get("ldm")) else 0.0
    if stp > 0:
        return stp
    if ldm > 0:
        return float(max(1, math.ceil(ldm / 0.4)))  # P6 fallback
    return 0.0


def _is_ssc_versender(name: str) -> bool:
    return "supply center" in str(name).lower()


# ── Load BI data ──────────────────────────────────────────────────────────────
print("Loading bi_top20_data.pkl ...")
bi = pd.read_pickle("output/bi_top20_data.pkl")["df"]
raw = bi[bi["Kunden Nr BK"].isin(SCOPE_KNR)].copy()

raw["ef"]  = pd.to_numeric(raw["Erlöse Fracht"],  errors="coerce").fillna(0)
raw["ton"] = pd.to_numeric(raw["Tonnage (eff.)"], errors="coerce").fillna(0)
raw["stp"] = pd.to_numeric(raw["Stellplätze"],    errors="coerce").fillna(0)
raw["ldm"] = pd.to_numeric(raw["Lademeter"],      errors="coerce").fillna(0)

raw["has_ms"] = raw["Mastersendung"].apply(_nonempty)
raw["has_ua"] = raw["Unterauftrag"].apply(_nonempty)
raw["is_sub"] = raw["has_ms"] & ~raw["has_ua"]

raw["ship_dt"] = pd.to_datetime(raw["Leistungsdatum"], errors="coerce").dt.date

# ── Pool filters ──────────────────────────────────────────────────────────────
pool_raw = raw[(raw["ef"] > 0)].copy()
pool     = pool_raw[(~pool_raw["is_sub"]) & (pool_raw["ton"] > 0)].copy()

pool["stp_eff"] = pool.apply(_stp_eff, axis=1)

print(f"Pool roh (ef>0):                 {len(pool_raw)}")
print(f"  is_sub (ef>0):                 {pool_raw['is_sub'].sum()}")
print(f"  ton=0 non-sub:                 {(pool_raw[(~pool_raw['is_sub']) & (pool_raw['ton']==0)]).shape[0]}")
print(f"Pipeline pool (ef>0 ~sub ton>0): {len(pool)}")
print(f"  stp_eff=0 after P6:            {(pool['stp_eff']==0).sum()} → unbeurteilbar")

# KNR-level breakdown
for knr in sorted(SCOPE_KNR):
    g = pool[pool["Kunden Nr BK"] == knr]
    print(f"  KNR {knr}: {len(g)} rows, Σef={g['ef'].sum():,.0f} EUR")

# ── Calculator run ─────────────────────────────────────────────────────────────
results = []
for idx, row in pool.iterrows():
    knr  = int(row["Kunden Nr BK"])
    land = str(row["Empfänger Land"]).strip().upper()
    plz  = str(row["Empfänger PLZ"]).strip()
    stp  = row["stp_eff"]
    ef   = float(row["ef"])
    dt   = row["ship_dt"] if pd.notna(row["ship_dt"]) else date(2025, 10, 1)
    vname = str(row.get("Versender Name", "")).strip()

    # Choose calculator
    calc = calc_ssc if knr == 511241 or _is_ssc_versender(vname) else calc_de

    # Scope classification (preliminary, before Calculator)
    if knr == 511241:
        is_ssc_v = _is_ssc_versender(vname)
        if land == "DE":
            scope_label = "de_oos"
        elif not is_ssc_v:
            scope_label = "import_flow"   # IT/ES-origin non-SSC → Welle 2
        else:
            scope_label = "ssc_eu"
    else:  # KNR 491063
        scope_label = "de_oos" if land == "DE" else "ok"

    # Skip Calculator for OOS and import_flow (still log)
    if scope_label in ("de_oos", "import_flow") or stp == 0:
        results.append({
            "knr": knr, "land": land, "plz": plz, "stp_eff": stp, "ef": ef,
            "dlv": None, "delta": None, "fp": None,
            "scope": scope_label if stp == 0 else scope_label,
            "dlv_file": None, "notes": [],
            "versender_name": vname,
        })
        continue

    try:
        r = calc.calculate(plz, land, stellplaetze=stp, shipment_date=dt)
        dlv_val = float(r.basispreis) + float(r.maut_surcharge)
        delta   = ef - dlv_val
        fp      = delta / dlv_val if dlv_val else None
        scope   = scope_label  # already "ssc_eu" or "ok"
        results.append({
            "knr": knr, "land": land, "plz": plz, "stp_eff": stp, "ef": ef,
            "dlv": dlv_val, "delta": delta, "fp": fp,
            "scope": scope,
            "dlv_file": r.tariff_file_used, "notes": r.notes,
            "versender_name": vname,
        })
    except LookupError as e:
        results.append({
            "knr": knr, "land": land, "plz": plz, "stp_eff": stp, "ef": ef,
            "dlv": None, "delta": None, "fp": None,
            "scope": "dlv_luecke",
            "dlv_file": None, "notes": [str(e)],
            "versender_name": vname,
        })

df_res = pd.DataFrame(results)

# ── M-classification ──────────────────────────────────────────────────────────
def _mclass(fp):
    if fp is None:
        return None
    if abs(fp) <= 0.05:
        return "M1"
    if fp < -0.05:
        return "M2"
    return "M_over"

df_res["mclass"] = df_res["fp"].apply(_mclass)

# ── Summaries ─────────────────────────────────────────────────────────────────
ok = df_res[df_res["scope"].isin(["ok", "ssc_eu"])].copy()

print(f"\n=== Step 3 Results ===")
for knr in sorted(SCOPE_KNR):
    g = ok[ok["knr"] == knr]
    if len(g) == 0:
        print(f"KNR {knr}: 0 beurteilbar")
        continue
    m1  = (g["mclass"] == "M1").sum()
    m2  = (g["mclass"] == "M2").sum()
    mov = (g["mclass"] == "M_over").sum()
    net = g["delta"].sum()
    sef = g["ef"].sum()
    sdlv = g["dlv"].sum()
    fp_net = net / sdlv if sdlv else 0
    print(f"\nKNR {knr} (beurteilbar={len(g)}, Σef={sef:,.0f}, Σdlv={sdlv:,.0f})")
    print(f"  M1={m1} ({100*m1/len(g):.1f}%)  M2={m2}  M_over={mov}")
    print(f"  Net Δ = {net:+.2f} EUR  ({fp_net:+.4%})")

# Scope breakdown for 511241
g511 = df_res[df_res["knr"] == 511241]
print(f"\nKNR 511241 scope breakdown:")
for sc, grp in g511.groupby("scope"):
    print(f"  {sc}: {len(grp)} rows, Σef={grp['ef'].sum():,.0f} EUR")

# Land-level for 491063 beurteilbar
g491 = ok[ok["knr"] == 491063]
print("\nKNR 491063 land breakdown (beurteilbar):")
for land, grp in g491.groupby("land"):
    net = grp["delta"].sum()
    fp  = net / grp["dlv"].sum() if grp["dlv"].sum() else 0
    print(f"  {land}: n={len(grp)}, Σef={grp['ef'].sum():,.0f}, Δ={net:+.0f} ({fp:+.2%})")

# Top M2/M_over for 491063
print("\nTop M2 + M_over rows (491063, |Δ| > 200):")
noteworthy = g491[g491["mclass"].isin(["M2","M_over"])].copy()
noteworthy["abs_delta"] = noteworthy["delta"].abs()
noteworthy = noteworthy.nlargest(15, "abs_delta")
print(noteworthy[["land","plz","stp_eff","ef","dlv","delta","fp","mclass"]].to_string(index=False))

# ── Save ─────────────────────────────────────────────────────────────────────
OUTPUT_PKL.parent.mkdir(exist_ok=True)
save = {
    "df_res":     df_res,
    "ok":         ok,
    "n_pool_raw": len(pool_raw),
    "n_is_sub":   pool_raw["is_sub"].sum(),
    "n_pipeline": len(pool),
    "knr_summary": ok.groupby("knr").agg(
        n=("ef","count"), sum_ef=("ef","sum"),
        sum_dlv=("dlv","sum"), sum_delta=("delta","sum"),
        m1=("mclass", lambda x: (x=="M1").sum()),
        m2=("mclass", lambda x: (x=="M2").sum()),
        mover=("mclass", lambda x: (x=="M_over").sum()),
    ).assign(fp_net=lambda d: d["sum_delta"]/d["sum_dlv"]),
    "land_summary_491": g491.groupby("land").agg(
        n=("ef","count"), sum_ef=("ef","sum"),
        sum_dlv=("dlv","sum"), sum_delta=("delta","sum"),
    ).assign(fp_net=lambda d: d["sum_delta"]/d["sum_dlv"]),
    "scope_511": g511.groupby("scope").agg(
        n=("ef","count"), sum_ef=("ef","sum"),
    ),
}
pd.to_pickle(save, OUTPUT_PKL)
print(f"\nSaved → {OUTPUT_PKL}")
