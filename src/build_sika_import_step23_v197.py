"""
Sika 511241 Import-Flow — Step 2+3 Pipeline v1.9.7
KNR: 511241 (SIKA Supply Center AG)
Scope: de_oos rows with Versender-PLZ in {28065 (IT), 28108 (ES)}
       (physical import shipments from Cerano/Alcobendas → Stuttgart DE-70499)

DLV: 'Import Spanien und Italien 2025/2026'
     ES-28108 per-Stellplatz; IT-28065 Komplett-LKW flat-rate
P20: ef_total = Erlöse Fracht + Erlöse Maut (DLV includes maut component)
"""
from __future__ import annotations

import math
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))

from tms.tariff.calculators.sika_import import SikaImportCalculator

# ── Config ───────────────────────────────────────────────────────────────────
KNR = 511241
IMPORT_VERS_PLZ = {"28108", "28065"}
OUTPUT_PKL = Path("output/sika_import_step23_results_v197.pkl")

calc = SikaImportCalculator()


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


# ── Load BI data ──────────────────────────────────────────────────────────────
print("Loading bi_top20_data.pkl ...")
bi = pd.read_pickle("output/bi_top20_data.pkl")["df"]
raw = bi[bi["Kunden Nr BK"] == KNR].copy()

raw["ef"]  = pd.to_numeric(raw["Erlöse Fracht"],  errors="coerce").fillna(0)
raw["maut_bi"] = pd.to_numeric(raw["Erlöse Maut"], errors="coerce").fillna(0)
raw["ton"] = pd.to_numeric(raw["Tonnage (eff.)"], errors="coerce").fillna(0)
raw["stp"] = pd.to_numeric(raw["Stellplätze"],    errors="coerce").fillna(0)
raw["ldm"] = pd.to_numeric(raw["Lademeter"],      errors="coerce").fillna(0)

raw["has_ms"] = raw["Mastersendung"].apply(_nonempty)
raw["has_ua"] = raw["Unterauftrag"].apply(_nonempty)
raw["is_sub"] = raw["has_ms"] & ~raw["has_ua"]

raw["vers_plz"]  = raw["Versender PLZ"].astype(str).str.strip()
raw["vers_land"] = raw["Versender Land"].astype(str).str.strip().str.upper()
raw["ship_dt"]   = pd.to_datetime(raw["Leistungsdatum"], errors="coerce").dt.date

# ── Pool filters ──────────────────────────────────────────────────────────────
pool_raw = raw[
    (raw["ef"] > 0) &
    (raw["vers_plz"].isin(IMPORT_VERS_PLZ))
].copy()

pool = pool_raw[
    (~pool_raw["is_sub"]) &
    (pool_raw["ton"] > 0)
].copy()

pool["stp_eff"] = pool.apply(_stp_eff, axis=1)

# P20: ef_total = Erlöse Fracht + Erlöse Maut
# DLV maut_surcharge is the calculated DLV maut component; Erlöse Maut is billed in AX separately.
# For fair comparison: dlv_val = basispreis + maut_surcharge; ef_comp = ef + maut_bi
pool["ef_total"] = pool["ef"] + pool["maut_bi"]

print(f"Pool roh (ef>0, import-origins):        {len(pool_raw)}")
print(f"  is_sub:                               {pool_raw['is_sub'].sum()}")
print(f"  ton=0 non-sub:                        {(pool_raw[(~pool_raw['is_sub']) & (pool_raw['ton']==0)]).shape[0]}")
print(f"Pipeline pool (~sub ton>0):             {len(pool)}")
print(f"  stp_eff=0 (unbeurteilbar):            {(pool['stp_eff']==0).sum()}")
print(f"  Σef:                                  {pool['ef'].sum():,.0f} EUR")
print(f"  Σ Erlöse Maut (P20):                  {pool['maut_bi'].sum():,.0f} EUR")
print(f"  Σef_total (ef+maut):                  {pool['ef_total'].sum():,.0f} EUR")
print()
for (vl, vp), grp in pool.groupby(["vers_land", "vers_plz"]):
    print(f"  {vl}-{vp}: {len(grp)} rows, Σef={grp['ef'].sum():,.0f}, Σmaut={grp['maut_bi'].sum():,.0f}")


# ── Calculator run ─────────────────────────────────────────────────────────────
results = []
for idx, row in pool.iterrows():
    vl   = str(row["vers_land"]).strip().upper()
    vp   = str(row["vers_plz"]).strip()
    stp  = row["stp_eff"]
    ef   = float(row["ef"])
    maut_bi = float(row["maut_bi"])
    ef_total = float(row["ef_total"])
    dt   = row["ship_dt"] if pd.notna(row["ship_dt"]) else date(2025, 10, 1)

    if stp == 0:
        results.append({
            "vers_land": vl, "vers_plz": vp, "stp_eff": stp,
            "ef": ef, "maut_bi": maut_bi, "ef_total": ef_total,
            "dlv": None, "delta": None, "delta_p20": None,
            "fp": None, "fp_p20": None,
            "scope": "stp_zero", "dlv_file": None, "notes": [],
        })
        continue

    try:
        r = calc.calculate(
            "70499", "DE",
            stellplaetze=stp,
            shipment_date=dt,
            vers_plz=vp,
            vers_land=vl,
        )
        dlv_val  = float(r.basispreis) + float(r.maut_surcharge)
        delta    = ef - dlv_val          # nominal (Erlöse Fracht only)
        delta_p20 = ef_total - dlv_val   # P20-adjusted (ef + Erlöse Maut)
        fp       = delta    / dlv_val if dlv_val else None
        fp_p20   = delta_p20 / dlv_val if dlv_val else None

        results.append({
            "vers_land": vl, "vers_plz": vp, "stp_eff": stp,
            "ef": ef, "maut_bi": maut_bi, "ef_total": ef_total,
            "dlv": dlv_val, "delta": delta, "delta_p20": delta_p20,
            "fp": fp, "fp_p20": fp_p20,
            "scope": "ok",
            "dlv_file": r.tariff_file_used, "notes": r.notes,
        })
    except LookupError as e:
        results.append({
            "vers_land": vl, "vers_plz": vp, "stp_eff": stp,
            "ef": ef, "maut_bi": maut_bi, "ef_total": ef_total,
            "dlv": None, "delta": None, "delta_p20": None,
            "fp": None, "fp_p20": None,
            "scope": "dlv_luecke",
            "dlv_file": None, "notes": [str(e)],
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

df_res["mclass"]     = df_res["fp"].apply(_mclass)
df_res["mclass_p20"] = df_res["fp_p20"].apply(_mclass)


# ── Summaries ─────────────────────────────────────────────────────────────────
ok = df_res[df_res["scope"] == "ok"].copy()

print(f"\n=== Step 3 Results (beurteilbar: {len(ok)}) ===")
print(f"  DLV-Lücke: {(df_res['scope']=='dlv_luecke').sum()}")
print()

# Overall
net_nom = ok["delta"].sum()
net_p20 = ok["delta_p20"].sum()
sdlv    = ok["dlv"].sum()
sef     = ok["ef"].sum()
sef_tot = ok["ef_total"].sum()
sm      = ok["maut_bi"].sum()
fp_nom  = net_nom / sdlv if sdlv else 0
fp_p20  = net_p20 / sdlv if sdlv else 0

m1  = (ok["mclass"] == "M1").sum()
m2  = (ok["mclass"] == "M2").sum()
mov = (ok["mclass"] == "M_over").sum()
m1p = (ok["mclass_p20"] == "M1").sum()
m2p = (ok["mclass_p20"] == "M2").sum()
movp = (ok["mclass_p20"] == "M_over").sum()

print(f"Nominal (ef vs dlv):        M1={m1} ({100*m1/len(ok):.1f}%)  M2={m2}  M_over={mov}")
print(f"P20-adj (ef+maut vs dlv):   M1={m1p} ({100*m1p/len(ok):.1f}%)  M2={m2p}  M_over={movp}")
print()
print(f"  Σef:         {sef:>12,.0f} EUR")
print(f"  Σ maut_bi:   {sm:>12,.0f} EUR")
print(f"  Σef_total:   {sef_tot:>12,.0f} EUR")
print(f"  Σdlv:        {sdlv:>12,.0f} EUR")
print()
print(f"  Net Δ nominal:    {net_nom:+12,.2f} EUR  ({fp_nom:+.4%})")
print(f"  Net Δ P20-adj:    {net_p20:+12,.2f} EUR  ({fp_p20:+.4%})")
print()

# Per versender-land
print("Per Versender-Land:")
for vl, grp in ok.groupby("vers_land"):
    nd  = grp["delta"].sum()
    nd2 = grp["delta_p20"].sum()
    sd  = grp["dlv"].sum()
    print(f"  {vl}: n={len(grp)}, Σef={grp['ef'].sum():,.0f}, Net Δ nom={nd:+.0f} ({nd/sd:+.2%}), Net Δ P20={nd2:+.0f} ({nd2/sd:+.2%})")

# Notable rows
print("\nTop M2/M_over rows by |delta_p20|:")
noteworthy = ok[ok["mclass_p20"].isin(["M2", "M_over"])].copy()
noteworthy["abs_d"] = noteworthy["delta_p20"].abs()
noteworthy = noteworthy.nlargest(10, "abs_d")
print(noteworthy[["vers_land","vers_plz","stp_eff","ef","dlv","delta_p20","fp_p20","mclass_p20"]].to_string(index=False))


# ── Save ─────────────────────────────────────────────────────────────────────
OUTPUT_PKL.parent.mkdir(exist_ok=True)
save = {
    "df_res":     df_res,
    "ok":         ok,
    "n_pool_raw": len(pool_raw),
    "n_is_sub":   pool_raw["is_sub"].sum(),
    "n_pipeline": len(pool),
    "n_beurteilbar": len(ok),
    "n_dlv_luecke":  (df_res["scope"] == "dlv_luecke").sum(),
    "sum_ef":     sef,
    "sum_maut_bi": sm,
    "sum_ef_total": sef_tot,
    "sum_dlv":    sdlv,
    "net_delta_nominal": net_nom,
    "net_delta_p20":     net_p20,
    "fp_net_nominal":    fp_nom,
    "fp_net_p20":        fp_p20,
    "m_summary_nominal": {
        "M1": int(m1), "M2": int(m2), "M_over": int(mov)
    },
    "m_summary_p20": {
        "M1": int(m1p), "M2": int(m2p), "M_over": int(movp)
    },
    "land_summary": ok.groupby("vers_land").agg(
        n=("ef", "count"),
        sum_ef=("ef", "sum"),
        sum_maut=("maut_bi", "sum"),
        sum_ef_total=("ef_total", "sum"),
        sum_dlv=("dlv", "sum"),
        sum_delta=("delta", "sum"),
        sum_delta_p20=("delta_p20", "sum"),
        m1=("mclass_p20", lambda x: (x == "M1").sum()),
        m2=("mclass_p20", lambda x: (x == "M2").sum()),
        mover=("mclass_p20", lambda x: (x == "M_over").sum()),
    ).assign(
        fp_net=lambda d: d["sum_delta"] / d["sum_dlv"],
        fp_net_p20=lambda d: d["sum_delta_p20"] / d["sum_dlv"],
    ),
}
pd.to_pickle(save, OUTPUT_PKL)
print(f"\nSaved → {OUTPUT_PKL}")
