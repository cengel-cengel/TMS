"""Excel Schritt 5 — Sheet 15 DLV-Vergleich + Sheet 16 Operative Klaerungen."""
from pathlib import Path
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

OUT = Path("output/erka_lieferung/Sendungs_Gegenueberstellung_v1_0.xlsx")
BLUE="1F4E79"; LGRAY="D9D9D9"; GRN="C6EFCE"; RED="FFC7CE"; YLW="FFEB9C"

def hdr(ws, row, cols, vals):
    for c, v in enumerate(vals, 1):
        cell = ws.cell(row=row, column=c, value=v)
        cell.font = Font(name="Calibri", bold=True, size=10, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor=BLUE)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    ws.row_dimensions[row].height = 22

wb = load_workbook(OUT)

# ── Sheet 15: DLV-Soll vs AX-Ist ─────────────────────────────────────────────
ws15 = wb.create_sheet("DLV-Soll vs AX-Ist")
ws15.merge_cells("A1:H1")
ws15["A1"].value = "DLV-Soll vs. AX-Ist Vergleich — Cluster-Ebene pro Scope"
ws15["A1"].font = Font(name="Calibri", bold=True, size=12, color=BLUE)
ws15["A2"].value = ("HINWEIS: AX und Dinas haben disjunkte Nummernräume — kein direkter Sendungs-zu-Sendungs-Join möglich. "
                    "Vergleich erfolgt auf Cluster-Ebene: (Empf-PLZ, Empf-Land) vs. DLV-Soll-Berechnung.")
ws15.merge_cells("A2:H2")
ws15["A2"].font = Font(name="Calibri", italic=True, size=9)

hdr(ws15, 4, None, ["Scope","Kunde","Beurteilbar","Σ ef AX (EUR)","Σ DLV-Soll (EUR)",
                     "Net Δ nom. (EUR)","Net Δ adj. (EUR)","M1 %"])

rows15 = [
    ("GEZE","GEZE GmbH",2759,391904,387766,4138,4138,"92,4%"),
    ("EBM","EBM-Papst",308,480133,476619,3514,3514,"92,5%"),
    ("Fischerwerke","Fischerwerke GmbH",839,537574,430763,106811,106811,"38,3%"),
    ("HERMA","HERMA GmbH",3642,2428736,2445110,-16374,-16374,"78,0%"),
    ("CHT","CHT Germany",554,257594,258262,-668,-668,"97,3%"),
    ("Bitzer","Bitzer SE",3330,723694,697287,26407,26407,"86,1%"),
    ("Groz-Beckert","Groz-Beckert",527,112997,107269,5729,5729,"89,8%"),
    ("HELU","HELU-KABEL",2185,315991,315789,203,203,"93,5%"),
    ("Hornschuch","Hornschuch AG",1565,408579,408784,-205,-205,"99,0%"),
    ("Sika DE","Sika Deutschland",1379,1278459,1304217,-25758,4797,"64,3%"),
    ("Sika SSC","Sika Supply Center",62,43358,40758,2600,2600,"69,4%"),
    ("Sika Import","Sika Import-Flow",346,629422,637814,-8392,9914,"86,4%"),
    ("Sika ATM","Sika Automotive AG",395,217470,224713,-7243,-7243,"75,4%"),
    ("GESAMT","",17891,7825911,7735145,90762,139623,"83,8%"),
]
for r, row in enumerate(rows15, 5):
    for c, v in enumerate(row, 1):
        cell = ws15.cell(row=r, column=c, value=v)
        cell.font = Font(name="Calibri", size=10, bold=(row[0]=="GESAMT"))
        cell.alignment = Alignment(horizontal="center")
        if c in (4,5,6,7):
            if isinstance(v,(int,float)):
                cell.number_format = '#,##0'
        if isinstance(v,(int,float)) and c in (6,7):
            if v < 0: cell.font = Font(name="Calibri", size=10, color="C00000", bold=(row[0]=="GESAMT"))
            elif v > 0: cell.font = Font(name="Calibri", size=10, color="375623", bold=(row[0]=="GESAMT"))
        if row[0]=="GESAMT":
            cell.fill = PatternFill("solid", fgColor=LGRAY)

ws15.freeze_panes = "A5"
for c, w in enumerate([12,18,11,16,16,16,16,8],1):
    ws15.column_dimensions[get_column_letter(c)].width = w

# ── Sheet 16: Operative Klaerungen ────────────────────────────────────────────
ws16 = wb.create_sheet("Operative Klaerungen")
ws16.merge_cells("A1:G1")
ws16["A1"].value = "Operative Klärungsbedarfe — 7 Punkte (kein Migrationsbefund)"
ws16["A1"].font = Font(name="Calibri", bold=True, size=12, color=BLUE)
ws16["A2"].value = "Quelle: docs/OPERATIVE_KLAERUNGEN_v1_0.md | Alle Positionen sind operative/vertragliche Klärungsbedarfe außerhalb des Billing-Audits."
ws16.merge_cells("A2:G2")
ws16["A2"].font = Font(name="Calibri", italic=True, size=9)

hdr(ws16, 4, None, ["Punkt","Kunde","KNR","Σ ef (EUR)","Rows","Priorität","Beschreibung"])

klaerungen = [
    ("C.1","Hornschuch AG","490085",203992,726,"Mittel",
     "PL-DLV-Lücke: ERKA-DLV enthält 99 PL-Zonen mit leeren Raten. ContiTech-Vertragsscope PL klären."),
    ("C.2","Sika SSC","511241",631702,347,"Mittel",
     "de_oos-Block: 347 DE-Ziel-Sendungen unter SSC-KNR gebucht. Buchungszugehörigkeit/DE-Inbound-DLV klären."),
    ("C.3","Fischerwerke","409480",102052,264,"Niedrig",
     "GR-Tarif-Lücke: Calculator wirft LookupError für GR-PLZ. GR-Tarif-Datei beschaffen."),
    ("C.4","HERMA GmbH","423650",61917,93,"Niedrig",
     "GB-Zone-Lücke: 10 GB-Postcode-Areas nicht im DLV. DLV-Ergänzung oder Klärung Tarifklasse."),
    ("C.5","Bitzer SE","406345",33970,67,"Niedrig",
     "DE-Inbound OOS: Import-Sendungen nicht im Export-DLV. Prüfen ob DE-Inbound-Tarif existiert."),
    ("C.6","CHT Germany","486073",38776,102,"Niedrig",
     "GR-Calculator fehlt: CHTGreeceCalculator.calculate() nicht implementiert. GR-Tarif + Calculator erstellen."),
    ("C.7","Bitzer SE","406345",445,7,"Niedrig",
     "FR sonstige: FR-92000 Hauts-de-Seine Zonenzuordnung (Zone 7 vs 8). ERKA-Rückfrage."),
    ("ΣGESAMT","",""  ,1072854,1606,"",""),
]
for r, row in enumerate(klaerungen, 5):
    is_tot = row[0]=="ΣGESAMT"
    for c, v in enumerate(row, 1):
        cell = ws16.cell(row=r, column=c, value=v)
        cell.font = Font(name="Calibri", size=10, bold=is_tot)
        cell.alignment = Alignment(horizontal="center" if c<7 else "left", vertical="center", wrap_text=(c==7))
        if c == 4 and isinstance(v,(int,float)):
            cell.number_format = '#,##0'
        if c == 6:
            if v == "Mittel": cell.fill = PatternFill("solid", fgColor=YLW)
            elif v == "Niedrig": cell.fill = PatternFill("solid", fgColor=GRN)
        if is_tot: cell.fill = PatternFill("solid", fgColor=LGRAY)
    ws16.row_dimensions[r].height = 28

ws16.freeze_panes = "A5"
for c, w in enumerate([8,18,8,14,7,10,55],1):
    ws16.column_dimensions[get_column_letter(c)].width = w

wb.save(OUT)

# Validation: count sheets and verify Uebersicht total
wb2 = load_workbook(OUT, read_only=True)
print(f"Sheets ({len(wb2.sheetnames)}): {wb2.sheetnames}")
wb2.close()
print(f"Saved: {OUT}")
