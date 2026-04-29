"""Excel Schritt 1 — Sheet 'Uebersicht' (13-Scope-Tabelle)."""
import pickle, numpy as np
from pathlib import Path
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

OUT = Path("output/erka_lieferung/Sendungs_Gegenueberstellung_v1_0.xlsx")
OUT.parent.mkdir(exist_ok=True)

def ld(p):
    with open(p,'rb') as f: return pickle.load(f)

def mc(fp):
    if fp is None or (isinstance(fp,float) and np.isnan(fp)): return None
    return "M1" if abs(fp)<=0.05 else ("M2" if fp<-0.05 else "M_over")

# Consolidated scope data (PKL-verified)
SCOPES = [
    ("GEZE GmbH",       "406035",       2917, 2759, 2550, 132,  77,  391904,  4138,    4138),
    ("EBM-Papst",       "410844",        353,  308,  285,   1,  22,  480133,  3514,    3514),
    ("Fischerwerke",    "409480",       1173,  839,  321, 107, 411,  537574, 106811,  106811),
    ("HERMA GmbH",      "423650",       3781, 3642, 2842, 384, 416, 2428736, -16374,  -16374),
    ("CHT Germany",     "486073",        702,  554,  539,   0,  15,  257594,   -668,    -668),
    ("Bitzer SE",       "406345",       3406, 3330, 2868, 206, 256,  723694,  26407,   26407),
    ("Groz-Beckert",    "490527+",       621,  527,  473,   0,  54,  112997,   5729,    5729),
    ("HELU-KABEL",      "408244",       2293, 2185, 2044, 102,  39,  315991,    203,     203),
    ("Hornschuch AG",   "490085",       2551, 1565, 1549,   7,   9,  408579,   -205,    -205),
    ("Sika DE",         "491063",       1407, 1379,  887, 293, 199, 1278459, -25758,    4797),
    ("Sika SSC",        "511241-SSC",    415,   62,   43,   0,  19,   43358,   2600,    2600),
    ("Sika Import",     "511241-Imp",    346,  346,  299,  27,  20,  629422,  -8392,    9914),
    ("Sika ATM",        "527406",        396,  395,  298,  92,   5,  217470,  -7243,   -7243),
]

# Styles
BLUE  = "1F4E79"
LGRAY = "D9D9D9"
WHITE = "FFFFFF"
GRN   = "C6EFCE"
RED   = "FFC7CE"
YLW   = "FFEB9C"
DGRAY = "808080"

def hdr_font(bold=True): return Font(name="Calibri", bold=bold, size=10, color=WHITE)
def cell_font(bold=False): return Font(name="Calibri", bold=bold, size=10)
def hdr_fill(): return PatternFill("solid", fgColor=BLUE)
def gray_fill(): return PatternFill("solid", fgColor=LGRAY)
def wrap_align(): return Alignment(horizontal="center", vertical="center", wrap_text=True)

wb = Workbook()
ws = wb.active
ws.title = "Uebersicht"

# Title
ws.merge_cells("A1:K1")
t = ws["A1"]
t.value = "TMS-Migrations-Audit Dinas → AX — Sendungs-Gegenüberstellung v1.0"
t.font = Font(name="Calibri", bold=True, size=14, color=BLUE)
t.alignment = Alignment(horizontal="left", vertical="center")
ws.row_dimensions[1].height = 22

ws["A2"].value = "Stand: 2026-04-29 | 13 Scopes | 11 Kunden | 7,83 MEUR | Methodik: v1.9.7"
ws["A2"].font = Font(name="Calibri", size=10, italic=True)
ws.merge_cells("A2:K2")
ws.row_dimensions[2].height = 16

# Table header row 4
hdrs = ["Kunde","KNR","Pool roh","Beurteilbar","M1","M2","M_over",
        "Σ ef (EUR)","Net Δ nom. (EUR)","Net Δ adj. (EUR)","Headline"]
for c, h in enumerate(hdrs, 1):
    cell = ws.cell(row=4, column=c, value=h)
    cell.font = hdr_font()
    cell.fill = hdr_fill()
    cell.alignment = wrap_align()
ws.row_dimensions[4].height = 28

def fmt_eur(v):
    return v  # openpyxl will format via number_format

for r, row in enumerate(SCOPES, 5):
    name,knr,pool,beurt,m1,m2,mover,ef,nom,adj = row
    vals = [name,knr,pool,beurt,m1,m2,mover,ef,nom,adj,"kein Schaden"]
    for c, v in enumerate(vals, 1):
        cell = ws.cell(row=r, column=c, value=v)
        cell.font = cell_font()
        cell.alignment = Alignment(horizontal="center", vertical="center")
        if c >= 3:
            if c in (8,9,10):
                cell.number_format = '#,##0'
            if c in (9,10):
                if isinstance(v,int) and v < 0:
                    cell.font = Font(name="Calibri", size=10, color="C00000")
                elif isinstance(v,int) and v > 0:
                    cell.font = Font(name="Calibri", size=10, color="375623")

# Totals row
tr = len(SCOPES)+5
tot = ws.cell(row=tr, column=1, value="GESAMT")
tot.font = Font(name="Calibri", bold=True, size=10)
tot.fill = gray_fill()
totals = [None,20361,17891,14998,1351,1542,7825911,90762,139623]
for c2, v in enumerate(totals, 2):
    cell = ws.cell(row=tr, column=c2, value=v)
    cell.font = Font(name="Calibri", bold=True, size=10)
    cell.fill = gray_fill()
    cell.alignment = Alignment(horizontal="center", vertical="center")
    if v is not None and c2 >= 8:
        cell.number_format = '#,##0'
ws.cell(row=tr, column=11, value="0 Schäden").fill = gray_fill()

# Column widths
widths = [18,14,9,11,7,7,8,14,16,16,14]
for c, w in enumerate(widths, 1):
    ws.column_dimensions[get_column_letter(c)].width = w

# Versions-Historie section
vr = tr+3
ws.cell(row=vr, column=1, value="Versions-Historie").font = Font(name="Calibri",bold=True,size=11,color=BLUE)
ws.merge_cells(f"A{vr}:D{vr}")
for r2, row2 in enumerate([
    ("v1.0","2026-02","8207bef","11 Scopes"),
    ("v1.1","2026-04-28","0f343b0","12 Scopes + Sika Import"),
    ("v2.0","2026-04-29","992030c","13 Scopes + ATM + Aggregation-Audit (final)"),
], vr+1):
    for c3,v3 in enumerate(row2,1):
        ws.cell(row=r2,column=c3,value=v3).font = cell_font()

# Lese-Anleitung
lr = vr+6
ws.cell(row=lr,column=1,value="Lese-Anleitung").font = Font(name="Calibri",bold=True,size=11,color=BLUE)
hints = [
    "Sheets 2-14: Pro Scope eine Sheet mit Sendungs-Detaildaten (ef/dlv/fp/M-Klasse)",
    "Sheet 15: DLV-Soll vs. AX-Ist Cluster-Vergleich",
    "Sheet 16: Operative Klärungsbedarfe (7 Punkte, Σ 1,07 MEUR)",
    "M1 = Abweichung ≤ 5% (korrekt) | M2 = unter DLV | M_over = über DLV",
    "Net Δ adj. = Nach P20.1-Maut-Korrektur (Sika DE +30.555 EUR, Sika Import +18.306 EUR)",
]
for i, h in enumerate(hints, lr+1):
    ws.cell(row=i,column=1,value=h).font = cell_font()
    ws.merge_cells(f"A{i}:K{i}")

wb.save(OUT)
print(f"Saved: {OUT}  (Uebersicht sheet done)")
