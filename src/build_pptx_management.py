"""PPT — 4-Folien Management-Präsentation Migrationsaudit Dinas→AX."""
from pathlib import Path
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN

OUT = Path("output/erka_lieferung/Audit_Praesentation_Management_v1_0.pptx")
BLUE = RGBColor(0x1F,0x4E,0x79)
LGRAY = RGBColor(0xD9,0xD9,0xD9)
GRN  = RGBColor(0x37,0x56,0x23)
RED  = RGBColor(0xC0,0x00,0x00)
WHITE= RGBColor(0xFF,0xFF,0xFF)

prs = Presentation()
prs.slide_width  = Inches(13.33)
prs.slide_height = Inches(7.5)

blank = prs.slide_layouts[6]  # fully blank

def txb(slide, l, t, w, h, text, sz=18, bold=False, color=None, align=PP_ALIGN.LEFT, italic=False):
    tb = slide.shapes.add_textbox(Inches(l), Inches(t), Inches(w), Inches(h))
    tf = tb.text_frame; tf.word_wrap = True
    p = tf.paragraphs[0]; p.alignment = align
    run = p.add_run(); run.text = text
    run.font.size = Pt(sz); run.font.bold = bold; run.font.italic = italic
    run.font.color.rgb = color or RGBColor(0x26,0x26,0x26)
    return tb

def rect(slide, l, t, w, h, fill, line=None):
    from pptx.util import Inches
    shape = slide.shapes.add_shape(1, Inches(l), Inches(t), Inches(w), Inches(h))
    shape.fill.solid(); shape.fill.fore_color.rgb = fill
    if line is None:
        shape.line.fill.background()
    else:
        shape.line.color.rgb = line
    return shape

def header_bar(slide, title):
    rect(slide, 0, 0, 13.33, 1.1, BLUE)
    txb(slide, 0.3, 0.15, 12, 0.8, title, sz=28, bold=True, color=WHITE)
    txb(slide, 0.3, 0.78, 8, 0.35,
        "ERKA-Management / Noerpel-Gruppe  |  2026-04-29  |  Vertraulich",
        sz=9, color=RGBColor(0xBF,0xBF,0xBF))

def footer(slide):
    txb(slide, 0, 7.2, 13.33, 0.3,
        "Migrationsaudit Dinas → AX  |  Abschlussbericht v2.0  |  Methodik v1.9.7  |  Vertraulich",
        sz=8, color=RGBColor(0x80,0x80,0x80), align=PP_ALIGN.CENTER)

# ── Folie 1: Titel ──────────────────────────────────────────────────────────
s1 = prs.slides.add_slide(blank)
rect(s1, 0, 0, 13.33, 7.5, BLUE)
txb(s1, 1.5, 1.5, 10, 1.2, "Migrationsaudit Dinas → AX",
    sz=36, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
txb(s1, 1.5, 2.8, 10, 0.7, "Abschlussbericht v2.0  —  ERKA-Management",
    sz=20, color=LGRAY, align=PP_ALIGN.CENTER)
txb(s1, 1.5, 3.55, 10, 0.5, "Noerpel-Gruppe  |  Stand: 2026-04-29  |  Methodik v1.9.7",
    sz=14, italic=True, color=LGRAY, align=PP_ALIGN.CENTER)
bullets1 = [
    "13 Scope-Einheiten  |  11 Kunden  |  17.891 beurteilbare Sendungen",
    "Gesamtvolumen: 7,83 MEUR  |  Netto-Δ adj. +139.623 EUR (+1,78 %)",
    "Befund: 0 Migrationsfehler  |  32/32 Aggregationstests bestanden",
]
for bi, b in enumerate(bullets1):
    txb(s1, 2.0, 4.4 + bi*0.55, 9.33, 0.55, f"▸  {b}", sz=13, color=WHITE)
footer(s1)

# ── Folie 2: Scope + Vorgehen ────────────────────────────────────────────────
s2 = prs.slides.add_slide(blank)
header_bar(s2, "Scope & Vorgehen")
rect(s2, 0.3, 1.25, 6.0, 5.8, RGBColor(0xF2,0xF2,0xF2))
txb(s2, 0.5, 1.3, 5.6, 0.5, "Geprüfte Kunden (13 Scopes)", sz=13, bold=True, color=BLUE)
scope_lines = [
    "GEZE GmbH (406035)          2.759 Send.",
    "EBM-Papst (410844)            308 Send.",
    "Fischerwerke (409480)         839 Send.",
    "HERMA GmbH (423650)         3.642 Send.",
    "CHT Germany (486073)          554 Send.",
    "Bitzer SE (406345)           3.330 Send.",
    "Groz-Beckert (490527+)        527 Send.",
    "HELU-KABEL (408244)          2.185 Send.",
    "Hornschuch AG (490085)       1.565 Send.",
    "Sika DE (491063)             1.379 Send.",
    "Sika SSC (511241-ssc)           62 Send.",
    "Sika Import (511241-imp)       346 Send.",
    "Sika ATM (527406)              395 Send.",
]
for li, ln in enumerate(scope_lines):
    txb(s2, 0.5, 1.85 + li*0.37, 5.6, 0.38, ln, sz=10)

txb(s2, 6.6, 1.3, 6.4, 0.5, "Methodik v1.9.7 — Ablauf", sz=13, bold=True, color=BLUE)
steps = [
    ("1", "Daten-Pool", "AX-Billing-Cache (bi_top20) bereinigt:\nSub-Rows, Null-Erlöse, Stornos ausgeschlossen"),
    ("2", "DLV-Kalkulation", "Kundenspez. Tabellenwerk (Anlage 1):\nTonnage-/Gewichts-/Stellplatz-basiert"),
    ("3", "Vergleich & M-Klassifikation", "M1: fp ∈ [−1%,+1%]  M2: fp < −1%\nM_over: fp > +1%  (fp = (ef−dlv)/dlv)"),
    ("4", "P20-Anpassung", "Erlöse Maut einbez. (Sika DE/Import)\nRS Serbia-Sondervereinbarung isoliert"),
    ("5", "Aggregations-Audit", "32/32 Tests: Sub-Row-Ausschluss,\nCluster-Konsolidierung verifiziert"),
]
for si, (num, title, desc) in enumerate(steps):
    rect(s2, 6.6, 1.85 + si*1.06, 6.3, 0.95, WHITE, BLUE)
    txb(s2, 6.75, 1.9 + si*1.06, 0.5, 0.4, num, sz=16, bold=True, color=BLUE)
    txb(s2, 7.1, 1.88 + si*1.06, 5.6, 0.35, title, sz=11, bold=True, color=BLUE)
    txb(s2, 7.1, 2.22 + si*1.06, 5.6, 0.55, desc, sz=9)
footer(s2)

# ── Folie 3: Ergebnisse ──────────────────────────────────────────────────────
s3 = prs.slides.add_slide(blank)
header_bar(s3, "Audit-Ergebnis: Quantitative Befunde")
kpis = [
    ("17.891","beurteilbare Sendungen"),
    ("83,8 %","M1-Pass-Rate (Treffer)"),
    ("+1,78 %","Netto-Δ adj. (unkritisch)"),
    ("0","Migrationsfehler"),
]
for ki, (val, lbl) in enumerate(kpis):
    x = 0.3 + ki * 3.2
    rect(s3, x, 1.2, 3.0, 1.5, BLUE)
    txb(s3, x, 1.25, 3.0, 0.9, val, sz=30, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    txb(s3, x, 2.05, 3.0, 0.6, lbl, sz=11, color=LGRAY, align=PP_ALIGN.CENTER)

txb(s3, 0.3, 2.9, 6.2, 0.4, "M-Klassen-Verteilung", sz=13, bold=True, color=BLUE)
mrows = [
    ("M1 (Treffer fp∈[−1%,+1%])","14.998","83,8 %","+53.226 EUR"),
    ("M2 (Unterabr. fp < −1 %)","1.351","7,6 %","−170.878 EUR"),
    ("M_over (Überabr. fp > +1 %)","1.542","8,6 %","+208.415 EUR"),
    ("GESAMT","17.891","100 %","+90.762 EUR nom."),
]
hdrs = ["Klasse","Sendungen","%","Net-Δ"]
for ci, h in enumerate(hdrs):
    rect(s3, 0.3 + ci*1.5, 3.35, 1.45, 0.38, BLUE)
    txb(s3, 0.3 + ci*1.5, 3.37, 1.45, 0.35, h, sz=10, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
for ri, row in enumerate(mrows):
    bg = LGRAY if row[0]=="GESAMT" else WHITE
    for ci, v in enumerate(row):
        rect(s3, 0.3 + ci*1.5, 3.73 + ri*0.38, 1.45, 0.37, bg, RGBColor(0xCC,0xCC,0xCC))
        col = RED if ("−" in v and ci==3) else (GRN if (ci==3 and "+" in v and row[0]!="GESAMT") else RGBColor(0x26,0x26,0x26))
        txb(s3, 0.3 + ci*1.5, 3.76 + ri*0.38, 1.45, 0.35, v, sz=9, color=col, align=PP_ALIGN.CENTER)

txb(s3, 6.6, 2.9, 6.4, 0.4, "Wesentliche Anpassungen (P20)", sz=13, bold=True, color=BLUE)
p20s = [
    ("Sika DE","KNR 491063","Erlöse Maut","+ 30.555 EUR","adj. Δ: +4.797 EUR (−2,05% → −0,37%)"),
    ("Sika Import","KNR 511241-imp","Erlöse Maut","+ 18.306 EUR","adj. Δ: +9.914 EUR (−1,33% → +1,57%)"),
    ("Sika ATM","KNR 527406","RS Serbia pre-ex.","isoliert","Exkl. RS: −1.886 EUR (−0,95%)"),
]
for pi, (kd, knr, typ, betrag, effect) in enumerate(p20s):
    rect(s3, 6.6, 3.35 + pi*1.1, 6.3, 1.0, RGBColor(0xF2,0xF2,0xF2), BLUE)
    txb(s3, 6.75, 3.4 + pi*1.1, 4, 0.38, f"{kd} ({knr})", sz=11, bold=True, color=BLUE)
    txb(s3, 6.75, 3.76 + pi*1.1, 5.9, 0.32, f"{typ}: {betrag}  →  {effect}", sz=9)
footer(s3)

# ── Folie 4: Klärungen + Empfehlungen ────────────────────────────────────────
s4 = prs.slides.add_slide(blank)
header_bar(s4, "Operative Klärungen & Empfehlungen")
txb(s4, 0.3, 1.25, 6.5, 0.45, "Operative Klärungsbedarfe (kein Migrationsfehler)",
    sz=13, bold=True, color=BLUE)
klaer = [
    ("C.1","Hornschuch AG","PL-DLV-Lücke — 99 PL-Zonen ohne Rate","∑ 203.992 EUR","Mittel"),
    ("C.2","Sika SSC","de_oos-Block — 347 DE-Sendungen unter SSC-KNR","∑ 631.702 EUR","Mittel"),
    ("C.3","Fischerwerke","GR-Tarif-Lücke (LookupError für GR-PLZ)","∑ 102.052 EUR","Niedrig"),
    ("C.4","HERMA GmbH","GB-Zone-Lücke — 10 Postcode-Areas fehlen","∑ 61.917 EUR","Niedrig"),
    ("C.5","Bitzer SE","DE-Inbound OOS (Import-Send. nicht im Export-DLV)","∑ 33.970 EUR","Niedrig"),
    ("C.6","CHT Germany","GR-Calculator fehlt (nicht implementiert)","∑ 38.776 EUR","Niedrig"),
    ("C.7","Bitzer SE","FR-92000 Zonenzuordnung unklar (Zone 7 vs 8)","∑ 445 EUR","Niedrig"),
]
for ki, (pt, kd, desc, betrag, prio) in enumerate(klaer):
    pc = RGBColor(0xFF,0xEB,0x9C) if prio=="Mittel" else RGBColor(0xC6,0xEF,0xCE)
    rect(s4, 0.3, 1.78 + ki*0.72, 6.3, 0.65, RGBColor(0xFA,0xFA,0xFA), RGBColor(0xCC,0xCC,0xCC))
    rect(s4, 0.3, 1.78 + ki*0.72, 0.5, 0.65, pc)
    txb(s4, 0.35, 1.83 + ki*0.72, 0.42, 0.32, pt, sz=9, bold=True, align=PP_ALIGN.CENTER)
    txb(s4, 0.85, 1.8 + ki*0.72, 3.3, 0.32, f"{kd}: {desc}", sz=9, bold=False)
    txb(s4, 4.2, 1.8 + ki*0.72, 1.0, 0.32, betrag, sz=9, bold=True, color=BLUE)
    txb(s4, 5.25, 1.8 + ki*0.72, 1.3, 0.32, prio, sz=8, color=RGBColor(0x40,0x40,0x40))
    txb(s4, 5.25, 2.1 + ki*0.72, 1.3, 0.28, "→ Klärung ERKA", sz=8, italic=True)
txb(s4, 0.3, 6.7, 3, 0.3, f"Gesamt 7 Punkte: ∑ 1.072.854 EUR", sz=10, bold=True, color=RED)

txb(s4, 7.1, 1.25, 5.9, 0.45, "Empfehlungen", sz=13, bold=True, color=BLUE)
empf = [
    ("1","Freigabe Abschlussbericht v2.0",
     "Befundlage: 0 Migrationsfehler, 83,8 % M1. Bericht kann\nfür ERKA-Management und Noerpel freigegeben werden."),
    ("2","Operative Klärungen beauftragen",
     "7 Punkte (Σ 1,07 MEUR) sind vertragliche / operative\nFragestellungen außerhalb des Billing-Audits."),
    ("3","Methodikstandard v1.9.7 übernehmen",
     "Aggregationsregel (AX-Sub-Row-Ausschluss, Dinas-Cluster)\nals Standard für künftige AX-Audits dokumentieren."),
    ("4","Abschluss & Archivierung",
     "PKL-Caches + ERKA-Lieferpaket (XLSX, DOCX, PPTX)\narchivierten und Projektabschluss bestätigen."),
]
for ei, (num, title, desc) in enumerate(empf):
    rect(s4, 7.1, 1.78 + ei*1.3, 5.9, 1.2, WHITE, BLUE)
    rect(s4, 7.1, 1.78 + ei*1.3, 0.55, 1.2, BLUE)
    txb(s4, 7.1, 1.98 + ei*1.3, 0.55, 0.5, num, sz=20, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    txb(s4, 7.72, 1.82 + ei*1.3, 5.1, 0.38, title, sz=11, bold=True, color=BLUE)
    txb(s4, 7.72, 2.18 + ei*1.3, 5.1, 0.72, desc, sz=9)
footer(s4)

prs.save(OUT)
print(f"Saved: {OUT}  ({len(prs.slides)} slides)")
