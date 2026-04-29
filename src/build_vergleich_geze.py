"""GEZE GmbH (406035) Dinas-AX Vergleich Excel."""
import sys, pickle, math
from pathlib import Path
import pandas as pd
import openpyxl
sys.path.insert(0, "src")
from build_vergleich_helpers import (
    COLS, load_zgi_map, billing_kg_geze, band_label, abw_grund,
    write_cluster_sheet,
)
from tms.tariff.calculators.geze import (
    _get_rates, _find_zone_rates, _compute_soll,
)

KNR = 406035
OUT = Path("output/erka_lieferung/GEZE_Vergleich.xlsx")

# ── Load data ────────────────────────────────────────────────────────────────
with open("output/bi_top20_data.pkl","rb") as f:
    bi = pickle.load(f)["df"]

dinas = pickle.load(open("output/dinas_cache_406035.pkl","rb"))
zgi   = load_zgi_map("Geze.xlsx")
rates = _get_rates()

geze_all = bi[bi["Kunden Nr BK"]==KNR].copy()
post = geze_all[geze_all["periode"]=="POST"].copy()
pre  = geze_all[geze_all["periode"]=="PRE"].copy()

# ── Helpers ──────────────────────────────────────────────────────────────────
def soll_geze(land, plz, ton):
    try:
        bk = billing_kg_geze(float(ton))
        zr = _find_zone_rates(str(land).strip(), str(plz).strip())
        if zr is None: return None, None, None, None
        bl_limits = [b.weight_limit for b in zr.bands]
        bl = band_label(bk, bl_limits)
        bp = float(_compute_soll(zr, bk))
        return bp, bl, zr.zone, "EUR/100kg"
    except Exception:
        return None, None, None, "EUR/100kg"


def dinas_row(r) -> dict:
    land = str(r.get("empf_land","")).strip()
    plz  = str(r.get("empf_plz","")).strip()
    ton  = float(r["kg_rechnung"]) if r["kg_rechnung"] else 0
    bp, bl, zone, basis = soll_geze(land, plz, ton)
    bk   = billing_kg_geze(ton) if ton else None
    fracht = float(r["fracht"]) if r["fracht"] else 0
    diesel = float(r["diesel"]) if r["diesel"] else 0
    maut   = float(r["maut_ssd"]) if r["maut_ssd"] else 0
    sonst  = sum(float(r[c]) for c in ["ausfuhr","verzollung","zoll_duty",
             "zoll_betrag","sulphur","neben_pausch","redebit","sonstige"] if r[c])
    sigma  = fracht + diesel + maut + sonst
    soll_eur = (bp or 0)
    return {
        "System":"alt","Auftrags-Nr":str(r.get("sendungs_nr","")),
        "Master-Nr":"","Sub-Nr(n)":"","Zusammengefasst in":0,"Anzahl Subs":0,
        "Ist Master":"","Rech.-Nr":str(r.get("rechnung_nr","")),
        "Leistungsdatum":str(r.get("leistungsdatum","")),"Kunde":"GEZE GmbH",
        "Land":land,"Empf. PLZ":plz,"Vers. PLZ":"",
        "Gew.band":bl or "","Zone":zone or "","Basis":basis or "EUR/100kg",
        "Basis Menge":bk or "","Basispreis":bp or "","Eff. Preis":"",
        "Tonnage kg":ton,"Stellplaetze":"","Lademeter":float(r["ldm"]) if r["ldm"] else "",
        "Volumen":float(r["volumen"]) if r["volumen"] else "",
        "Soll EUR":soll_eur,"Fracht EUR":fracht,"Diesel EUR":diesel,"Maut EUR":maut,
        "Lademittel":"","Peak":"","EUST/Zoll":"","Versicherung":"",
        "Sonstige NK":sonst,"Σ Erloese":sigma,
        "Abw. Grund":abw_grund(soll_eur, sigma),
    }


def ax_row(r) -> dict:
    land = str(r.get("Empfänger Land","")).strip()
    plz  = str(r.get("Empfänger PLZ","")).strip().strip()
    ton  = float(r["Tonnage (eff.)"]) if pd.notna(r["Tonnage (eff.)"]) else 0
    bp, bl, zone, basis = soll_geze(land, plz, ton)
    bk   = billing_kg_geze(ton) if ton else None
    auftrag = str(r.get("Auftragsnummer","")).strip()
    ms  = str(r.get("Mastersendung","")) if pd.notna(r.get("Mastersendung","")) else ""
    ua  = str(r.get("Unterauftrag","")) if pd.notna(r.get("Unterauftrag","")) else ""
    fracht = float(r["Erlöse Fracht"]) if pd.notna(r["Erlöse Fracht"]) else 0
    diesel = float(r["Erlöse Diesel"]) if pd.notna(r["Erlöse Diesel"]) else 0
    maut   = float(r["Erlöse Maut"]) if pd.notna(r["Erlöse Maut"]) else 0
    lm     = float(r["Erlöse Lademittel"]) if pd.notna(r.get("Erlöse Lademittel",float("nan"))) else 0
    peak   = float(r["Erlöse Peak"]) if pd.notna(r.get("Erlöse Peak",float("nan"))) else 0
    eust   = float(r["Erlöse EUST Zoll"]) if pd.notna(r.get("Erlöse EUST Zoll",float("nan"))) else 0
    vers   = float(r["Erlöse Transportversicherung"]) if pd.notna(r.get("Erlöse Transportversicherung",float("nan"))) else 0
    nk     = float(r["Erlöse Nebengebühr"]) if pd.notna(r.get("Erlöse Nebengebühr",float("nan"))) else 0
    sigma  = fracht + diesel + maut + lm + peak + eust + vers + nk
    soll_eur = bp or 0
    eff    = round(sigma / bk * 100, 4) if bk and bk > 0 else ""
    zgi_val = zgi.get(auftrag, "")
    return {
        "System":"neu","Auftrags-Nr":auftrag,
        "Master-Nr":ms,"Sub-Nr(n)":ua,"Zusammengefasst in":zgi_val or 0,
        "Anzahl Subs":"","Ist Master":"ja" if ms else "nein",
        "Rech.-Nr":str(r.get("Rechnungsnummer","")),
        "Leistungsdatum":str(r.get("Leistungsdatum",""))[:10],"Kunde":"GEZE GmbH",
        "Land":land,"Empf. PLZ":plz,
        "Vers. PLZ":str(r.get("Versender PLZ","")).strip(),
        "Gew.band":bl or "","Zone":zone or "","Basis":basis or "EUR/100kg",
        "Basis Menge":bk or "","Basispreis":bp or "","Eff. Preis":eff,
        "Tonnage kg":ton,"Stellplaetze":str(r.get("Stellplätze","")) or "",
        "Lademeter":float(r["Lademeter"]) if pd.notna(r.get("Lademeter",float("nan"))) else "",
        "Volumen":float(r["Volumen"]) if pd.notna(r.get("Volumen",float("nan"))) else "",
        "Soll EUR":soll_eur,"Fracht EUR":fracht,"Diesel EUR":diesel,"Maut EUR":maut,
        "Lademittel":lm,"Peak":peak,"EUST/Zoll":eust,"Versicherung":vers,
        "Sonstige NK":nk,"Σ Erloese":sigma,
        "Abw. Grund":abw_grund(soll_eur, sigma),
    }


# ── Build cluster map ────────────────────────────────────────────────────────
def cluster_key_of(row_dict):
    return f"{row_dict['Land']}|{row_dict['Gew.band']}"

dinas_rows = [dinas_row(r) for _, r in dinas.iterrows()
              if r["kg_rechnung"] and float(r["kg_rechnung"]) > 0]
ax_rows    = [ax_row(r) for _, r in post.iterrows()
              if pd.notna(r["Erlöse Fracht"]) and float(r["Erlöse Fracht"]) > 0]

from collections import defaultdict
d_map = defaultdict(list); a_map = defaultdict(list)
for rd in dinas_rows: d_map[cluster_key_of(rd)].append(rd)
for ra in ax_rows:    a_map[cluster_key_of(ra)].append(ra)

# Only clusters where any AX row is Unterfakturierung
all_keys = sorted(set(d_map) | set(a_map))
clusters = []
for key in all_keys:
    ax_in = a_map.get(key, [])
    ax_unt = [r for r in ax_in if r["Abw. Grund"] == "Unterfakturierung"]
    if not ax_unt:
        continue
    d_in = sorted(d_map.get(key,[]), key=lambda x: -(x["Σ Erloese"] or 0))[:5]
    ax_show = sorted(ax_unt, key=lambda x: (x["Soll EUR"] or 0) - (x["Σ Erloese"] or 0),
                     reverse=True)[:5]
    clusters.append({"key": f"406035|{key}", "n_alt": len(d_map.get(key,[])),
                     "n_neu": len(ax_in), "rows": d_in + ax_show})

# ── Write Excel ──────────────────────────────────────────────────────────────
wb = openpyxl.Workbook()
ws = wb.active; ws.title = "GEZE 406035 Vergleich"
meta = [
    f"GEZE GmbH | KNR 406035 | Dinas PRE: {len(dinas)} pos | AX POST: {len(post)} Sendungen",
    f"Cluster mit Unterfakturierung (AX < Soll*0.95): {len(clusters)} von {len(all_keys)} Cluster-Schlüsseln",
    f"Gelb = Dinas (System alt)  |  Blau = AX (System neu)  |  Soll EUR = DLV-Tarif * Billing-kg/100",
]
write_cluster_sheet(ws, "GEZE GmbH — Dinas-AX Vergleich", clusters, meta)
wb.save(OUT)
print(f"Saved: {OUT}")
print(f"Clusters mit Unterfakturierung: {len(clusters)} / {len(all_keys)}")
print(f"Dinas-Rows gesamt: {len(dinas_rows)}  AX-Rows gesamt: {len(ax_rows)}")
