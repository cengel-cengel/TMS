"""Shared helpers for Dinas-AX Vergleich pro-Kunde Excel-Dateien."""
import math, pickle
from collections import defaultdict
import pandas as pd
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

ABR_BASE = "data/extracted/abrechnungsstrecken/Abrechnungsstrecken"

COLS = [
    "System","Auftrags-Nr","Master-Nr","Sub-Nr(n)","Zusammengefasst in",
    "Anzahl Subs","Ist Master","Rech.-Nr","Leistungsdatum","Kunde",
    "Land","Empf. PLZ","Vers. PLZ","Gew.band","Zone",
    "Basis","Basis Menge","Basispreis","Eff. Preis","Tonnage kg",
    "Stellplaetze","Lademeter","Volumen","Soll EUR","Fracht EUR",
    "Diesel EUR","Maut EUR","Lademittel","Peak","EUST/Zoll",
    "Versicherung","Sonstige NK","Σ Erloese","Abw. Grund",
]
assert len(COLS) == 34

BLUE  = "1F4E79"; DINAS_BG = "FFF2CC"; AX_BG = "DDEEFF"
HDR_BG= "2E74B5"; GRN = "C6EFCE"; RED = "FFC7CE"; LGRAY = "D9D9D9"


def load_zgi_map(kunde_file: str) -> dict:
    """Load Auftragsnummer→ZGI map from abrechnungsstrecken file."""
    wb = openpyxl.load_workbook(f"{ABR_BASE}/{kunde_file}", read_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    hdr = list(rows[0])
    ai = hdr.index("Auftragsnummer")
    zi = hdr.index("Zusammengefasst in")
    m = {str(r[ai]).strip(): r[zi] for r in rows[1:] if r[ai]}
    wb.close()
    return m


def billing_kg_geze(ton: float) -> int:
    return max(100, math.ceil(ton / 100) * 100)


def band_label(billing_kg: int, band_limits: list[int]) -> str:
    """Return DLV band label string for given billing_kg."""
    for lim in sorted(band_limits):
        if billing_kg <= lim:
            return f"bis {lim:,}kg".replace(",", ".")
    return f"über {max(band_limits):,}kg".replace(",", ".")


def abw_grund(soll, ist):
    if soll is None or soll == 0:
        return "Soll n/a"
    if ist is None:
        return "Soll n/a"
    diff = (ist - soll) / soll
    if diff < -0.05:
        return "Unterfakturierung"
    if diff > 0.05:
        return "Überfakturierung"
    return "OK"


def write_cluster_sheet(ws, title: str, clusters: list[dict],
                        meta_lines: list[str]):
    """Write cluster blocks to openpyxl worksheet."""
    # File header
    ws.merge_cells(f"A1:{get_column_letter(len(COLS))}1")
    ws["A1"] = title
    ws["A1"].font = Font(name="Calibri", bold=True, size=13, color="FFFFFF")
    ws["A1"].fill = PatternFill("solid", fgColor=BLUE)
    for i, ml in enumerate(meta_lines, 2):
        ws.cell(row=i, column=1, value=ml).font = Font(name="Calibri", italic=True, size=9)
    header_offset = 1 + len(meta_lines) + 1  # 1 title + meta rows + blank

    # Column header row
    for ci, col in enumerate(COLS, 1):
        c = ws.cell(row=header_offset, column=ci, value=col)
        c.font = Font(name="Calibri", bold=True, size=9, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor=HDR_BG)
        c.alignment = Alignment(horizontal="center", wrap_text=True)
    ws.row_dimensions[header_offset].height = 28
    ws.freeze_panes = ws.cell(row=header_offset+1, column=1)

    cur_row = header_offset + 1
    for clust in clusters:
        # Cluster header row
        ws.merge_cells(f"A{cur_row}:{get_column_letter(len(COLS))}{cur_row}")
        ws[f"A{cur_row}"] = f"▶  {clust['key']}  |  n_alt={clust['n_alt']}  n_neu={clust['n_neu']}"
        ws[f"A{cur_row}"].font = Font(name="Calibri", bold=True, size=10, color="FFFFFF")
        ws[f"A{cur_row}"].fill = PatternFill("solid", fgColor="2E74B5")
        cur_row += 1

        for row_dict in clust["rows"]:
            sys_val = row_dict.get("System","")
            bg = DINAS_BG if sys_val == "alt" else AX_BG
            for ci, col in enumerate(COLS, 1):
                v = row_dict.get(col, "")
                c = ws.cell(row=cur_row, column=ci, value=v)
                c.font = Font(name="Calibri", size=9)
                c.fill = PatternFill("solid", fgColor=bg)
                c.alignment = Alignment(horizontal="center" if ci != 4 else "left")
                if col in ("Soll EUR","Fracht EUR","Diesel EUR","Maut EUR",
                           "Lademittel","Peak","EUST/Zoll","Versicherung",
                           "Sonstige NK","Σ Erloese","Basispreis","Eff. Preis"):
                    if isinstance(v, (int, float)):
                        c.number_format = "#,##0.00"
                if col == "Abw. Grund" and isinstance(v, str):
                    if "Unter" in v:
                        c.fill = PatternFill("solid", fgColor=RED)
                    elif "Über" in v:
                        c.fill = PatternFill("solid", fgColor="FFEB9C")
                    elif v == "OK":
                        c.fill = PatternFill("solid", fgColor=GRN)
            cur_row += 1
        cur_row += 1  # blank separator

    # Column widths
    widths = [5,14,12,16,14,8,8,12,12,14,5,9,9,12,5,10,10,10,10,
              9,8,8,8,10,10,9,9,9,7,9,9,10,10,14]
    for ci, w in enumerate(widths[:len(COLS)], 1):
        ws.column_dimensions[get_column_letter(ci)].width = w


# ── Generic row builders ────────────────────────────────────────────────────

def _safe(df_row, col, default=""):
    v = df_row.get(col, default)
    if v is None: return default
    try:
        if pd.isna(v): return default
    except (TypeError, ValueError):
        pass
    return v


def ax_row_generic(r, zgi_map: dict, soll_fn, kunde_name: str) -> dict:
    """Build 34-col dict for one AX POST row from bi_top20 DataFrame."""
    land   = str(_safe(r, "Empfänger Land")).strip()
    plz    = str(_safe(r, "Empfänger PLZ")).strip()
    ton    = float(_safe(r, "Tonnage (eff.)", 0) or 0)
    ldm    = float(_safe(r, "Lademeter", 0) or 0)
    stp    = _safe(r, "Stellplätze", "")
    auftrag = str(_safe(r, "Auftragsnummer")).strip()
    ms  = str(_safe(r, "Mastersendung", ""))
    ua  = str(_safe(r, "Unterauftrag", ""))
    fracht = float(_safe(r, "Erlöse Fracht", 0) or 0)
    diesel = float(_safe(r, "Erlöse Diesel", 0) or 0)
    maut   = float(_safe(r, "Erlöse Maut", 0) or 0)
    lm     = float(_safe(r, "Erlöse Lademittel", 0) or 0)
    peak   = float(_safe(r, "Erlöse Peak", 0) or 0)
    eust   = float(_safe(r, "Erlöse EUST Zoll", 0) or 0)
    vers   = float(_safe(r, "Erlöse Transportversicherung", 0) or 0)
    nk     = float(_safe(r, "Erlöse Nebengebühr", 0) or 0)
    sigma  = fracht + diesel + maut + lm + peak + eust + vers + nk
    bp, bl, zone, basis, bm = soll_fn(land, plz, ton, ldm, stp)
    soll_eur = bp or 0
    eff = round(sigma / bm * 100, 4) if bm and bm > 0 and basis=="EUR/100kg" else (
          round(sigma / bm, 4) if bm and bm > 0 else "")
    return {
        "System":"neu","Auftrags-Nr":auftrag,
        "Master-Nr":ms,"Sub-Nr(n)":ua,
        "Zusammengefasst in":zgi_map.get(auftrag, 0) or 0,
        "Anzahl Subs":"","Ist Master":"ja" if ms else "nein",
        "Rech.-Nr":str(_safe(r, "Rechnungsnummer")),"Leistungsdatum":str(_safe(r, "Leistungsdatum"))[:10],
        "Kunde":kunde_name,"Land":land,"Empf. PLZ":plz,
        "Vers. PLZ":str(_safe(r, "Versender PLZ")).strip(),
        "Gew.band":bl or "","Zone":zone or "","Basis":basis or "",
        "Basis Menge":bm or "","Basispreis":bp or "","Eff. Preis":eff,
        "Tonnage kg":ton,"Stellplaetze":stp,"Lademeter":ldm or "","Volumen":float(_safe(r,"Volumen",0) or 0),
        "Soll EUR":soll_eur,"Fracht EUR":fracht,"Diesel EUR":diesel,"Maut EUR":maut,
        "Lademittel":lm,"Peak":peak,"EUST/Zoll":eust,"Versicherung":vers,
        "Sonstige NK":nk,"Σ Erloese":sigma,"Abw. Grund":abw_grund(soll_eur, sigma),
    }


def dinas_row_generic(r, soll_fn, kunde_name: str) -> dict:
    """Build 34-col dict for one Dinas cache row."""
    land = str(r.get("empf_land","")).strip()
    plz  = str(r.get("empf_plz","")).strip()
    ton  = float(r["kg_rechnung"]) if r.get("kg_rechnung") else 0
    ldm  = float(r["ldm"]) if r.get("ldm") and not (isinstance(r["ldm"],float) and math.isnan(r["ldm"])) else 0
    stp  = str(r.get("stellplaetze","")) or ""
    fracht = float(r["fracht"]) if r.get("fracht") else 0
    diesel = float(r["diesel"]) if r.get("diesel") else 0
    maut   = float(r["maut_ssd"]) if r.get("maut_ssd") else 0
    nk_cols = ["ausfuhr","verzollung","zoll_duty","zoll_betrag","sulphur","neben_pausch","redebit","sonstige"]
    sonst = sum(float(r[c]) for c in nk_cols if r.get(c) and not (isinstance(r[c],float) and math.isnan(r[c])))
    sigma = fracht + diesel + maut + sonst
    bp, bl, zone, basis, bm = soll_fn(land, plz, ton, ldm, stp)
    soll_eur = bp or 0
    return {
        "System":"alt","Auftrags-Nr":str(r.get("sendungs_nr","")),
        "Master-Nr":"","Sub-Nr(n)":"","Zusammengefasst in":0,"Anzahl Subs":0,"Ist Master":"",
        "Rech.-Nr":str(r.get("rechnung_nr","")),"Leistungsdatum":str(r.get("leistungsdatum","")),
        "Kunde":kunde_name,"Land":land,"Empf. PLZ":plz,"Vers. PLZ":"",
        "Gew.band":bl or "","Zone":zone or "","Basis":basis or "",
        "Basis Menge":bm or "","Basispreis":bp or "","Eff. Preis":"",
        "Tonnage kg":ton,"Stellplaetze":stp,"Lademeter":ldm or "","Volumen":float(r["volumen"]) if r.get("volumen") and not (isinstance(r["volumen"],float) and math.isnan(r["volumen"])) else "",
        "Soll EUR":soll_eur,"Fracht EUR":fracht,"Diesel EUR":diesel,"Maut EUR":maut,
        "Lademittel":"","Peak":"","EUST/Zoll":"","Versicherung":"",
        "Sonstige NK":sonst,"Σ Erloese":sigma,"Abw. Grund":abw_grund(soll_eur, sigma),
    }


def build_and_save(knr_list, dinas_df, post_df, zgi_map, soll_fn,
                   kunde_name, out_path, abr_file):
    """Generic cluster build + Excel save."""
    dinas_rows = [dinas_row_generic(r, soll_fn, kunde_name)
                  for _, r in dinas_df.iterrows()
                  if (r.get("kg_rechnung") or 0) > 0]
    ax_rows = [ax_row_generic(r, zgi_map, soll_fn, kunde_name)
               for _, r in post_df.iterrows()
               if (float(_safe(r,"Erlöse Fracht",0) or 0)) > 0]

    d_map = defaultdict(list); a_map = defaultdict(list)
    def ck(rd): return f"{rd['Land']}|{rd['Gew.band']}"
    for rd in dinas_rows: d_map[ck(rd)].append(rd)
    for ra in ax_rows:    a_map[ck(ra)].append(ra)

    clusters = []
    for key in sorted(set(d_map) | set(a_map)):
        ax_unt = [r for r in a_map.get(key,[]) if r["Abw. Grund"]=="Unterfakturierung"]
        if not ax_unt: continue
        knr_str = "|".join(str(k) for k in knr_list)
        d_in  = sorted(d_map.get(key,[]), key=lambda x:-(x["Σ Erloese"] or 0))[:5]
        ax_sh = sorted(ax_unt, key=lambda x:(x["Soll EUR"] or 0)-(x["Σ Erloese"] or 0), reverse=True)[:5]
        clusters.append({"key":f"{knr_str}|{key}","n_alt":len(d_map.get(key,[])),
                         "n_neu":len(a_map.get(key,[])),"rows":d_in+ax_sh})

    wb = openpyxl.Workbook(); ws = wb.active
    ws.title = f"{kunde_name[:28]} Vergleich"
    meta = [
        f"{kunde_name} | KNR {'/'.join(str(k) for k in knr_list)} | Dinas PRE: {len(dinas_df)} pos | AX POST: {len(post_df)} Sendungen",
        f"Cluster mit Unterfakturierung: {len(clusters)} | Gelb=Dinas | Blau=AX | Soll=DLV-Tarif",
    ]
    write_cluster_sheet(ws, f"{kunde_name} — Dinas-AX Vergleich", clusters, meta)
    wb.save(out_path)
    return len(clusters), len(dinas_rows), len(ax_rows)
