"""
rechnungsvergleich.py  (Dateiname: gb_rechnungsvergleich.py)
=============================================================
Multi-Kunden PDF-Vergleich DINAS vs. AX/CARGOsuite.

Kunden aus ZIP:  Groz Beckert, Bitzer, CHT, EBM, GEZE, Helu, Hornschuch
Kunden aus FS:   Herma, Fischerwerke  (Ordner data/<slug>/rechnungen_*)

Pro Kunde wird eine Excel-Datei erzeugt:
    output/<slug>/rechnungsvergleich.xlsx

Usage:
    python src/gb_rechnungsvergleich.py
    python src/gb_rechnungsvergleich.py bitzer cht   # nur bestimmte Kunden
"""

import math
import re
import warnings
import zipfile
from pathlib import Path
from datetime import datetime

import fitz          # PyMuPDF  – DINAS extraction
import numpy as np
import pandas as pd
import pdfplumber    # AX extraction
from openpyxl import Workbook
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter

warnings.filterwarnings("ignore")


# ── Pfade ──────────────────────────────────────────────────────────────────────
BASE        = Path("/home/user/TMS")
ZIP_PATH    = BASE / "data/Noerpel.AI.zip"
BI_ZIP_NAME = "Noerpel AI/Tagesbericht Einzeldaten alle VKA.xlsx"  # inside ZIP
BESONDERHEITEN_PATH = BASE / "data/Besonderheiten_bei_der_Kundenabrechnung.xlsx"
OUTPUT_DIR  = BASE / "output"

MIGRATION_DATE = pd.Timestamp("2025-09-26")

# ── Kunden-Konfiguration ───────────────────────────────────────────────────────
# zip_dinas / zip_ax : Ordnerpräfix innerhalb der ZIP-Datei
# fs_dinas  / fs_ax  : Ordner im Dateisystem  (Herma, Fischerwerke)
# bi_filter          : Regex gegen "Kunden Name" im BI-Report
CUSTOMERS = [
    dict(name="Groz Beckert", slug="groz_beckert",
         zip_dinas="Noerpel AI/Groz Beckert/Rechnungen/Rechnungen DINAS",
         zip_ax="Noerpel AI/Groz Beckert/Rechnungen/Rechnungen AX",
         bi_filter=r"[Gg]roz|[Bb]eckert",
         name_check=r"GROZ-BECKERT\s+(?:KG|EU|PORTUGUESA|EUROPE)"),
    dict(name="Bitzer", slug="bitzer",
         zip_dinas="Noerpel AI/Bitzer/Rechnungen/Rechnungen DINAS",
         zip_ax="Noerpel AI/Bitzer/Rechnungen/Rechnungen AX",
         bi_filter=r"[Bb]itzer"),
    dict(name="CHT", slug="cht",
         zip_dinas="Noerpel AI/CHT/Rechnungen/Rechnungen DINAS",
         zip_ax="Noerpel AI/CHT/Rechnungen/Rechnungen AX",
         bi_filter=r"CHT|Cht"),
    dict(name="EBM", slug="ebm",
         zip_dinas="Noerpel AI/EBM/Rechnungen/Rechnungen DINAS",
         zip_ax="Noerpel AI/EBM/Rechnungen/Rechnungen AX",
         bi_filter=r"[Ee][Bb][Mm]"),
    dict(name="GEZE", slug="geze",
         zip_dinas="Noerpel AI/GEZE/Rechnungen/Rechnungen DINAS",
         zip_ax="Noerpel AI/GEZE/Rechnungen/Rechnungen AX",
         bi_filter=r"[Gg][Ee][Zz][Ee]"),
    dict(name="Helu", slug="helu",
         zip_dinas="Noerpel AI/Helu/Rechnungen/Rechnungen DINAS",
         zip_ax="Noerpel AI/Helu/Rechnungen/Rechnungen AX",
         bi_filter=r"[Hh]elu"),
    dict(name="Hornschuch", slug="hornschuch",
         zip_dinas="Noerpel AI/Hornschuch/Rechnungen/Rechnungen DINAS",
         zip_ax="Noerpel AI/Hornschuch/Rechnungen/Rechnungen AX",
         bi_filter=r"[Hh]ornschuch"),
    dict(name="Herma", slug="herma",
         fs_dinas=BASE / "data/herma/rechnungen_dinas",
         fs_ax=BASE / "data/herma/rechnungen_cargosuite",
         bi_filter=r"[Hh]erma"),
    dict(name="Fischerwerke", slug="fischerwerke",
         fs_dinas=BASE / "data/fischerwerke/rechnungen_dinas",
         fs_ax=BASE / "data/fischerwerke/rechnungen_cargosuite",
         bi_filter=r"[Ff]ischer"),
]
MAX_EXAMPLES   = 5   # max. Sendungen pro Parametergruppe

# ── Fahrzeugkennzeichen → ISO-2 ─────────────────────────────────────────────────
VEHICLE_TO_ISO = {
    "A": "AT", "B": "BE", "BG": "BG", "BY": "BY", "CH": "CH",
    "CZ": "CZ", "D": "DE", "DK": "DK", "E": "ES", "EE": "EE",
    "EST": "EE", "F": "FR", "FI": "FI", "FL": "LI", "GB": "GB",
    "GR": "GR", "H": "HU", "HR": "HR", "I": "IT", "IE": "IE",
    "L": "LU", "LT": "LT", "LV": "LV", "MA": "MA", "N": "NO",
    "NL": "NL", "P": "PT", "PL": "PL", "PT": "PT", "RO": "RO",
    "RS": "RS", "RUS": "RU", "S": "SE", "SK": "SK", "SLO": "SI",
    "TR": "TR", "UA": "UA", "USA": "US",
}

# ── Farbpalette ────────────────────────────────────────────────────────────────
C_TITLE   = "1F3864"
C_HDR     = "2E75B6"
C_DINAS   = "D6E4F7"
C_AX      = "F7E4D6"
C_COMP    = "E2EFDA"
C_WARN    = "FFD700"
C_LOSS    = "FF9090"
C_OK      = "C6EFCE"
C_GREY    = "F2F2F2"


# ═══════════════════════════════════════════════════════════════════════════════
# A  DINAS PDF PARSER  (PyMuPDF)
# ═══════════════════════════════════════════════════════════════════════════════

def _iso_from_prefix(prefix: str) -> str:
    """Fahrzeugkennzeichen-Präfix → ISO-2-Ländercode."""
    return VEHICLE_TO_ISO.get(prefix.upper(), prefix.upper())


def _parse_german_num(s: str) -> float | None:
    """'1.234,56' → 1234.56"""
    if not s:
        return None
    s = s.strip().replace(" ", "")
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _parse_dinas_date(s: str) -> str | None:
    """'06.08.25' oder '26.08.2025' → 'YYYY-MM-DD'."""
    if not s:
        return None
    for fmt in ("%d.%m.%y", "%d.%m.%Y"):
        try:
            return datetime.strptime(s.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None


def _empf_plz_land(text_fragment: str) -> tuple[str, str]:
    """
    PLZ und Land aus Textfragment extrahieren.
    Erwartet z.B. 'B-8760 MEULEBEKE' oder '72458 ALBSTADT'.
    Gibt (plz_str, iso_land) zurück.
    """
    # Mit Länderpräfix: "B-8760", "F-69470", "GB-CB9 8PR", "CZ-338 22"
    m = re.match(r"([A-Z]{1,3})-([0-9A-Z][0-9A-Z \-]*)", text_fragment.strip())
    if m:
        iso = _iso_from_prefix(m.group(1))
        plz = m.group(2).split()[0].replace("-", "")
        return plz, iso
    # Ohne Präfix (DE): "72458 ALBSTADT"
    m2 = re.match(r"(\d{4,5})", text_fragment.strip())
    if m2:
        return m2.group(1), "DE"
    return "", "DE"


def _extract_plz_pair(block: str) -> tuple[str, str, str, str, str, str]:
    """
    Extrahiert (sender_name, sender_plz, sender_land, empf_name, empf_plz, empf_land).

    DINAS-Format:
      Abs.: SENDER_NAME  Empf.: RECEIVER_NAME   (gleiche Zeile)
      oder:
      Abs.: SENDER_NAME
      Empf.: RECEIVER_NAME
      SENDER_PLZ  SENDER_CITY          ← erste PLZ-Zeile = Absender
      RECEIVER_PLZ  RECEIVER_CITY      ← zweite PLZ-Zeile = Empfänger
    """
    abs_pos = re.search(r'Abs\.\s*:', block)
    if not abs_pos:
        return "", "72458", "DE", "", "", "DE"

    abs_line_start = abs_pos.end()
    nl = block.find('\n', abs_line_start)
    abs_line = block[abs_line_start: nl if nl >= 0 else len(block)]

    # Sender-Name: von Abs.: bis Empf.: (gleiche Zeile) oder bis Zeilenende
    empf_in_line = re.search(r'Empf\.\s*:', abs_line)
    if empf_in_line:
        sender_name = abs_line[:empf_in_line.start()].strip()
        empf_name   = abs_line[empf_in_line.end():].strip()
        tail_start  = nl + 1 if nl >= 0 else len(block)
    else:
        sender_name = abs_line.strip()
        tail_start  = nl + 1 if nl >= 0 else len(block)
        tail_head   = block[tail_start:]
        empf_pos    = re.match(r'\s*Empf\.\s*:', tail_head)
        if empf_pos:
            empf_line_end = tail_head.find('\n')
            empf_name = tail_head[empf_pos.end(): empf_line_end if empf_line_end >= 0 else len(tail_head)].strip()
            tail_start += (empf_line_end + 1) if empf_line_end >= 0 else len(tail_head)
        else:
            empf_name = ""

    tail = block[tail_start:]

    plz_lines = []
    for line in tail.split('\n'):
        s = line.strip()
        if not s:
            continue
        if s.startswith('Ref.') or s.startswith('REF.'):
            break
        if re.match(r'^\d{5}\s+[A-ZÄÖÜ]', s):
            plz_lines.append(s)
        elif re.match(r'^[A-Z]{1,3}-[0-9A-Z]', s):
            plz_lines.append(s)
        if len(plz_lines) >= 2:
            break

    if not plz_lines:
        return sender_name, "72458", "DE", empf_name, "", "DE"
    sender_plz, sender_land = _empf_plz_land(plz_lines[0])
    if len(plz_lines) >= 2:
        empf_plz, empf_land = _empf_plz_land(plz_lines[1])
    else:
        empf_plz, empf_land = "", "DE"
    return sender_name, sender_plz, sender_land, empf_name, empf_plz, empf_land


def parse_dinas_pdf_text(text: str, pdf_name: str) -> list[dict]:
    """
    DINAS-Rechnungstext (PyMuPDF) → Liste von Sendungs-Dicts.
    Jede Sendung enthält alle für den Vergleich relevanten Felder.
    """
    records = []

    # ── AX-Rechnung im DINAS-Ordner? ──────────────────────────────────────────
    # AX-Format hat "/ STP /" im Route-String oder 16-stellige Auftrags-Nr.
    if (re.search(r'/\s*[\d.,]+\s*STP\s*/', text)
            or re.search(r'Auftrags-Nr\.:\s*\d{16}', text)):
        return []   # AX-Rechnung – wird von load_ax_from_zip verarbeitet

    # ── Rechnungskopf ──────────────────────────────────────────────────────────
    rn_m = re.search(r'Rechnung-Nr\.:\s*(\d+)', text)
    rechnungsnr = rn_m.group(1) if rn_m else re.sub(r'\D', '', pdf_name)

    datum_m = re.search(r'Stuttgart\s+den\s+(\d{1,2}\.\d{2}\.(?:\d{2}|\d{4}))', text)
    rechnungsdatum = _parse_dinas_date(datum_m.group(1)) if datum_m else None

    is_storno = bool(re.search(r'STORNO|Rechnungskorrektur', text, re.I))
    sign = -1 if is_storno else 1

    # ── Sendungsblöcke aufteilen: "N) DD.MM.YY\n(sdgnr)" ───────────────────────
    # Jeder Block beginnt mit einer nummerierten Position
    block_starts = list(re.finditer(
        r'(?m)^(\d+)\)\s+(\d{2}\.\d{2}\.(?:\d{2}|\d{4}))\s*\n\s*\((\d+)\)',
        text
    ))

    if not block_starts:
        # Ältere DINAS-Rechnungen ohne nummerierte Blöcke — versuche einfachere Extraktion
        rec = _extract_simple_dinas_block(text, rechnungsnr, rechnungsdatum, pdf_name, sign)
        if rec:
            records.append(rec)
        return records

    # Jeden Block einzeln parsen
    for i, m in enumerate(block_starts):
        start = m.start()
        end   = block_starts[i + 1].start() if i + 1 < len(block_starts) else len(text)
        block = text[start:end]

        leistungsdatum = _parse_dinas_date(m.group(2))
        sendungsnr     = m.group(3)

        rec = _parse_dinas_block(
            block, rechnungsnr, rechnungsdatum, leistungsdatum, sendungsnr, pdf_name, sign
        )
        if rec:
            records.append(rec)

    return records


def _parse_dinas_block(block: str, rechnungsnr: str, rechnungsdatum: str,
                        leistungsdatum: str, sendungsnr: str,
                        pdf_name: str, sign: int) -> dict | None:
    """Einen Sendungsblock parsen."""

    # Auftragsnummer aus Ref.-Zeile
    ref_m = re.search(r'Ref\.\s*:.*?/(\d{12,})', block)
    if not ref_m:
        # Einige Refs ohne /: "Ref.: 4121068818"
        ref_m2 = re.search(r'Ref\.\s*:\s*(\d{12,})', block)
        auftragsnr = ref_m2.group(1) if ref_m2 else None
    else:
        auftragsnr = ref_m.group(1)

    # AX-Rechnungen im DINAS-Ordner: 16-stellige Auftragsnummer → überspringen
    if auftragsnr and len(str(auftragsnr)) == 16:
        return None

    # Absender (Abs.) und Empfänger (Empf.) Namen + PLZ + Land
    sender_name, sender_plz, sender_land, empf_name, empf_plz, empf_land = _extract_plz_pair(block)

    # Abrechnungsgewicht + Lademeter
    # Format: "5,000 Ldm = 6250 k" oder "5,000 Ldm =11250 k" (kein Leerzeichen vor Zahl)
    # oder "2,00 ldm = 3000 kg"
    lademeter = None
    stellplaetze = None
    bweight   = None

    ldm_m = re.search(r'([\d.,]+)\s*[Ll]dm\s*=\s*([\d.,]+)\s*[Kk]', block)
    if ldm_m:
        lademeter = _parse_german_num(ldm_m.group(1))
        bweight   = _parse_german_num(ldm_m.group(2))
    else:
        cbm_m = re.search(r'([\d.,]+)\s*cbm\s*=\s*([\d.,]+)\s*[Kk]', block, re.I)
        if cbm_m:
            bweight = _parse_german_num(cbm_m.group(2))
        else:
            bw_m = re.search(r'=\s*([\d.,]+)\s*[Kk]g\b', block, re.I)
            if bw_m:
                bweight = _parse_german_num(bw_m.group(1))
            else:
                kg_m = re.search(r'\b([\d.,]+)\s*[Kk]g\b', block, re.I)
                if kg_m:
                    bweight = _parse_german_num(kg_m.group(1))

    # Stellplätze: nicht explizit in DINAS – aus LDM schätzbar (1 STP ≈ 0,4 LDM)
    # Nur setzen wenn LDM bekannt
    if lademeter and lademeter > 0:
        stellplaetze = round(lademeter / 0.4, 1)

    if not bweight or bweight <= 0:
        return None

    # Fracht
    fracht_m = re.search(r'FRACHT(?:/FREIGHT)?\s+([\d.,]+)\s*EUR', block, re.I)
    fracht = sign * (_parse_german_num(fracht_m.group(1)) or 0) if fracht_m else 0.0

    # Maut
    maut_m = re.search(r'MAUT(?:/TOLL)?\s+([\d.,]+)\s*EUR', block, re.I)
    maut = sign * (_parse_german_num(maut_m.group(1)) or 0) if maut_m else 0.0

    # Diesel / Kraftstoff
    diesel_m = re.search(
        r'(?:DIESEL\S*|KRAFTSTOFF\S*)\s+\S+\s+([-\d.,]+)\s*EUR', block, re.I
    )
    diesel = sign * (_parse_german_num(diesel_m.group(1)) or 0) if diesel_m else 0.0

    # Nebengebühren (alles außer Fracht/Maut/Diesel bis zur Sendungssumme)
    sdgsum_m = re.search(
        r'Sendungssumme\s+steuerpfl\.\s*:\s*([\d.,]+)\s*EUR', block, re.I
    )
    sdgsumme = sign * (_parse_german_num(sdgsum_m.group(1)) or 0) if sdgsum_m else None

    nebenkost = 0.0
    if sdgsumme is not None:
        nebenkost = sdgsumme - fracht - maut - diesel

    erloes_total = sdgsumme if sdgsumme is not None else fracht + maut + diesel

    return dict(
        system         = "DINAS",
        rechnungsnr    = rechnungsnr,
        rechnungsdatum = rechnungsdatum,
        leistungsdatum = leistungsdatum,
        sendungsnr     = sendungsnr,
        auftragsnr     = auftragsnr,
        sender_name    = sender_name,
        sender_plz     = sender_plz,
        sender_land    = sender_land,
        empf_name      = empf_name,
        empf_plz       = empf_plz,
        empf_land      = empf_land,
        gewicht_kg     = bweight,
        lademeter      = lademeter,
        stellplaetze   = stellplaetze,
        fracht_eur     = fracht,
        maut_eur       = maut,
        diesel_eur     = diesel,
        verzoll_eur    = 0.0,
        neben_eur      = nebenkost,
        erloes_eur     = erloes_total,
        is_storno      = (sign == -1),
        pdf_name       = pdf_name,
    )


def _extract_simple_dinas_block(text: str, rechnungsnr: str, rechnungsdatum: str,
                                  pdf_name: str, sign: int) -> dict | None:
    """Fallback für DINAS-Rechnungen ohne nummerierte Blöcke (Storni, alte Formate)."""
    # Auftragsnummer
    ref_m = re.search(r'Auftrags-Nr\.\s*[:\.]?\s*(\d{8,})', text)
    auftragsnr = ref_m.group(1) if ref_m else None

    # Leistungsdatum aus Storno-Block
    ld_m = re.search(r'Datum\s+(\d{2}\.\d{2}\.\d{4})', text)
    leistungsdatum = _parse_dinas_date(ld_m.group(1)) if ld_m else rechnungsdatum

    # Gewicht aus Frachtumsatz-Block (Storno: Sachkontobetrag)
    # "Frachtumsatz  32904279  519,69 EUR"
    fu_m = re.search(r'Frachtumsatz\s+\d+\s+([-\d.,]+)\s*EUR', text)
    if fu_m:
        fracht = sign * abs(_parse_german_num(fu_m.group(1)) or 0)
    else:
        fracht_m = re.search(r'FRACHT(?:/FREIGHT)?\s+([\d.,]+)\s*EUR', text, re.I)
        fracht = sign * (_parse_german_num(fracht_m.group(1)) or 0) if fracht_m else 0.0

    # Empfänger
    lp_m = re.search(r'\b([A-Z]{1,3})-([0-9][0-9A-Z \-]{2,8})\b', text)
    empf_plz, empf_land = _empf_plz_land(lp_m.group(0)) if lp_m else ("", "PT")

    # Gesamtbetrag
    gs_m = re.search(r'(?:Endsumme|Rechnungsbetrag)\s+([\d.,]+)\s*EUR', text)
    erloes = sign * (_parse_german_num(gs_m.group(1)) or 0) if gs_m else fracht

    # Sendungsnummer
    sdg_m = re.search(r'Sendungsnr\s*:\s*(\d+)', text)
    sendungsnr = sdg_m.group(1) if sdg_m else ""

    # Für Storno: Gewicht oft nicht direkt im Text → verwenden wir 0 als Sentinel
    return dict(
        system         = "DINAS",
        rechnungsnr    = rechnungsnr,
        rechnungsdatum = rechnungsdatum,
        leistungsdatum = leistungsdatum,
        sendungsnr     = sendungsnr,
        auftragsnr     = auftragsnr,
        sender_name    = "",
        sender_plz     = "72458",
        sender_land    = "DE",
        empf_name      = "",
        empf_plz       = empf_plz,
        empf_land      = empf_land,
        gewicht_kg     = 0.0,   # unbekannt
        lademeter      = None,
        stellplaetze   = None,
        fracht_eur     = fracht,
        maut_eur       = 0.0,
        diesel_eur     = 0.0,
        verzoll_eur    = 0.0,
        neben_eur      = erloes - fracht,
        erloes_eur     = erloes,
        is_storno      = (sign == -1),
        pdf_name       = pdf_name,
    )


def _load_dinas_from_zip(zip_path: Path, zip_folder: str, name_check: str | None = None) -> pd.DataFrame:
    """DINAS-Rechnungen aus ZIP-Unterordner extrahieren.
    name_check: optionales Regex – Rechnungen ohne Treffer werden übersprungen.
    """
    records = []
    with zipfile.ZipFile(zip_path) as z:
        pdfs = sorted([
            f for f in z.namelist()
            if f.startswith(zip_folder) and f.lower().endswith(".pdf")
        ])
        print(f"  {len(pdfs)} DINAS-PDFs gefunden")
        ok = skip = 0
        for ppath in pdfs:
            fname = ppath.split("/")[-1]
            data  = z.read(ppath)
            try:
                doc  = fitz.open(stream=data, filetype="pdf")
                text = "\n".join(page.get_text() for page in doc)
                doc.close()
                if name_check and not re.search(name_check, text, re.I):
                    skip += 1
                    continue
                recs = parse_dinas_pdf_text(text, fname)
                records.extend(recs)
                ok += 1
            except Exception:
                skip += 1
    print(f"  Verarbeitet: {ok} Rechnungen, {skip} übersprungen")
    print(f"  Extrahierte Sendungen: {len(records)}")
    return pd.DataFrame(records) if records else pd.DataFrame()


def _load_dinas_from_fs(folder: Path) -> pd.DataFrame:
    """DINAS-Rechnungen aus Dateisystem-Ordner extrahieren."""
    records = []
    pdfs = sorted(folder.glob("*.pdf"))
    print(f"  {len(pdfs)} DINAS-PDFs gefunden")
    ok = skip = 0
    for pdf_path in pdfs:
        try:
            doc  = fitz.open(str(pdf_path))
            text = "\n".join(page.get_text() for page in doc)
            doc.close()
            recs = parse_dinas_pdf_text(text, pdf_path.name)
            records.extend(recs)
            ok += 1
        except Exception:
            skip += 1
    print(f"  Verarbeitet: {ok} Rechnungen, {skip} übersprungen")
    print(f"  Extrahierte Sendungen: {len(records)}")
    return pd.DataFrame(records) if records else pd.DataFrame()


# ═══════════════════════════════════════════════════════════════════════════════
# B  AX PDF PARSER  (pdfplumber)
# ═══════════════════════════════════════════════════════════════════════════════

def parse_ax_pdf_text(text: str, pdf_name: str) -> dict | None:
    """AX-Rechnungstext (pdfplumber) → Sendungs-Dict."""

    is_storno = bool(re.search(r'Rechnungskorrektur|Storno zu Beleg', text, re.I))
    sign = -1 if is_storno else 1

    # Belegnummer
    bn_m = re.search(r'Belegnummer:\s*(\d+)', text)
    belegnr = bn_m.group(1) if bn_m else re.sub(r'\D', '', pdf_name)[:12]

    # Belegdatum
    bd_m = re.search(r'Belegdatum:\s*(\d{2}\.\d{2}\.\d{4})', text)
    belegdatum = _parse_dinas_date(bd_m.group(1)) if bd_m else None

    # Leistungsdatum
    ld_m = re.search(r'Leistungsdatum:\s*(\d{2}\.\d{2}\.\d{4})', text)
    leistungsdatum = _parse_dinas_date(ld_m.group(1)) if ld_m else belegdatum

    # Auftragsnummer
    an_m = re.search(r'Auftrags-Nr\.:\s*(\S+)', text)
    auftragsnr = an_m.group(1) if an_m else None

    # Route: "DD.MM.YYYY / 111,00 kg / 1,00 STP / 0,40 LDM / 0,00 m3 / …"
    route_m = re.search(
        r'\d{2}\.\d{2}\.\d{4}\s*/\s*([\d.,]+)\s*kg\s*/\s*([\d.,]+)\s*STP\s*/\s*([\d.,]+)\s*LDM',
        text
    )
    gewicht      = _parse_german_num(route_m.group(1)) if route_m else None
    stellplaetze = _parse_german_num(route_m.group(2)) if route_m else None
    lademeter    = _parse_german_num(route_m.group(3)) if route_m else None

    # von/nach: "Von: DE-72458 Albstadt Nach: PT-4409 Vila Nova de Gaia"
    von_m = re.search(r'[Vv]on:\s*([A-Z]{2})-(\S+)\s', text)
    nach_m = re.search(r'[Nn]ach:\s*([A-Z]{2})-(\S+)\s', text)

    sender_land = von_m.group(1)  if von_m  else "DE"
    sender_plz  = von_m.group(2)  if von_m  else "72458"
    empf_land   = nach_m.group(1) if nach_m else ""
    empf_plz    = nach_m.group(2) if nach_m else ""

    # Versender/Empfänger Namen: "Versender: Name, Strasse, DE-72458 Stadt"
    vs_m = re.search(r'Versender:\s*(.+?)(?:,\s*[A-Z]{2}-[\d\w]|\n|$)', text)
    em_m = re.search(r'Empf[äa]nger:\s*(.+?)(?:,\s*[A-Z]{2}-[\d\w]|\n|$)', text)
    sender_name = vs_m.group(1).strip().rstrip(',') if vs_m else ""
    empf_name   = em_m.group(1).strip().rstrip(',') if em_m else ""

    if not gewicht or gewicht <= 0:
        return None

    # Positionen – "M\d+" steht für die Kostenstelle (z.B. M3, M92 etc.)
    _MX = r'M\d+'   # Kostenstellenmuster
    fracht_m  = re.search(rf'Fracht\s+{_MX}\s+([-\d.,]+)EUR', text)
    maut_m    = re.search(rf'Maut\s+(?:\S+\s+)?{_MX}\s+([-\d.,]+)EUR', text)
    diesel_m  = re.search(rf'Diesel(?:zuschlag)?\s+{_MX}\s+([-\d.,]+)EUR', text)
    verzoll_m = re.search(rf'Verzollung\s+{_MX}\s+([-\d.,]+)EUR', text)
    gesamt_m  = re.search(r'Gesamtbetrag\s+([-\d.,]+)EUR', text)

    fracht  = sign * (_parse_german_num(fracht_m.group(1))   or 0) if fracht_m  else 0.0
    maut    = sign * (_parse_german_num(maut_m.group(1))     or 0) if maut_m    else 0.0
    diesel  = sign * (_parse_german_num(diesel_m.group(1))   or 0) if diesel_m  else 0.0
    verzoll = sign * (_parse_german_num(verzoll_m.group(1))  or 0) if verzoll_m else 0.0

    # Nettobetrag aus Nettobetrag-Zeile (= Zwischensumme ohne MwSt)
    netto_m = re.search(rf'Zwischensumme\s+{_MX}\s+[-\d.,]+\s+([-\d.,]+)EUR', text)
    if netto_m:
        netto = sign * (_parse_german_num(netto_m.group(1)) or 0)
    elif gesamt_m:
        netto = sign * (_parse_german_num(gesamt_m.group(1)) or 0)
    else:
        netto = fracht + maut + diesel + verzoll

    # Nebenkosten = alles außer den explizit aufgeführten Positionen
    nebenkost = netto - fracht - maut - diesel - verzoll

    return dict(
        system         = "AX",
        rechnungsnr    = belegnr,
        rechnungsdatum = belegdatum,
        leistungsdatum = leistungsdatum,
        sendungsnr     = auftragsnr or belegnr,
        auftragsnr     = auftragsnr,
        sender_name    = sender_name,
        sender_plz     = sender_plz.split("-")[0] if "-" in sender_plz else sender_plz,
        sender_land    = sender_land,
        empf_name      = empf_name,
        empf_plz       = empf_plz.split("-")[0] if "-" in empf_plz else empf_plz,
        empf_land      = empf_land,
        gewicht_kg     = gewicht,
        lademeter      = lademeter,
        stellplaetze   = stellplaetze,
        fracht_eur     = fracht,
        maut_eur       = maut,
        diesel_eur     = diesel,
        verzoll_eur    = verzoll,
        neben_eur      = nebenkost,
        erloes_eur     = netto,
        is_storno      = (sign == -1),
        pdf_name       = pdf_name,
    )


def _load_ax_from_zip(zip_path: Path, zip_folder: str) -> pd.DataFrame:
    """AX-Rechnungen aus ZIP-Unterordner extrahieren."""
    import io
    records = []
    with zipfile.ZipFile(zip_path) as z:
        pdfs = sorted([
            f for f in z.namelist()
            if f.startswith(zip_folder) and f.lower().endswith(".pdf")
        ])
        print(f"  {len(pdfs)} AX-PDFs gefunden")
        ok = skip = 0
        for ppath in pdfs:
            fname = ppath.split("/")[-1]
            data  = z.read(ppath)
            try:
                with pdfplumber.open(io.BytesIO(data)) as pdf:
                    text = "\n".join(p.extract_text() or "" for p in pdf.pages)
                rec = parse_ax_pdf_text(text, fname)
                if rec:
                    records.append(rec)
                    ok += 1
                else:
                    skip += 1
            except Exception:
                skip += 1
    print(f"  Verarbeitet: {ok} Rechnungen, {skip} übersprungen")
    return pd.DataFrame(records) if records else pd.DataFrame()


def _load_ax_from_fs(folder: Path) -> pd.DataFrame:
    """AX/CARGOsuite-Rechnungen aus Dateisystem-Ordner extrahieren."""
    records = []
    pdfs = sorted(folder.glob("*.pdf"))
    print(f"  {len(pdfs)} AX-PDFs gefunden")
    ok = skip = 0
    for pdf_path in pdfs:
        try:
            with pdfplumber.open(str(pdf_path)) as pdf:
                text = "\n".join(p.extract_text() or "" for p in pdf.pages)
            rec = parse_ax_pdf_text(text, pdf_path.name)
            if rec:
                records.append(rec)
                ok += 1
            else:
                skip += 1
        except Exception:
            skip += 1
    print(f"  Verarbeitet: {ok} Rechnungen, {skip} übersprungen")
    return pd.DataFrame(records) if records else pd.DataFrame()


def load_invoices_for_customer(customer: dict, zip_path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Lädt DINAS- und AX-Rechnungen für einen Kunden (ZIP oder FS)."""
    if "zip_dinas" in customer:
        print(f"[DINAS] {customer['name']} aus ZIP …")
        dinas_df = _load_dinas_from_zip(zip_path, customer["zip_dinas"],
                                        customer.get("name_check"))
    else:
        print(f"[DINAS] {customer['name']} aus Ordner …")
        dinas_df = _load_dinas_from_fs(customer["fs_dinas"])

    if "zip_ax" in customer:
        print(f"[AX]    {customer['name']} aus ZIP …")
        ax_df = _load_ax_from_zip(zip_path, customer["zip_ax"])
    else:
        print(f"[AX]    {customer['name']} aus Ordner …")
        ax_df = _load_ax_from_fs(customer["fs_ax"])

    return dinas_df, ax_df


# ═══════════════════════════════════════════════════════════════════════════════
# C  BI-FALLBACK & NORMALISIERUNG
# ═══════════════════════════════════════════════════════════════════════════════

def load_bi_fallback(bi_path: Path) -> pd.DataFrame:
    """BI-Report für Fallback laden (Auftragsnummer als Join-Key).

    Lädt nur die benötigten Spalten um Ladezeit zu minimieren.
    """
    print("[BI] Lade Fallback-Daten …")
    needed = [
        "Kunden Name", "Kunden Nr BK", "Auftragsnummer", "Rechnungsnummer",
        "Tonnage (eff.)", "Lademeter", "Erloese", "Erlöse Fracht",
        "Versender PLZ", "Versender Land", "Empfänger PLZ", "Empfänger Land",
    ]
    try:
        df = pd.read_excel(
            bi_path,
            usecols=lambda c: c in needed,
            dtype={"Auftragsnummer": str, "Rechnungsnummer": str, "Kunden Nr BK": str},
        )
    except Exception:
        # Fallback: load all columns (slower but safer)
        df = pd.read_excel(bi_path, dtype={"Auftragsnummer": str, "Rechnungsnummer": str})

    mask = df["Kunden Name"].astype(str).str.contains(r"Groz|Beckert", case=False, na=False)
    df   = df[mask].copy()
    df["Auftragsnummer"] = df["Auftragsnummer"].astype(str).str.strip()
    for col in ["Versender PLZ", "Versender Land", "Empfänger PLZ", "Empfänger Land"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()
    print(f"  BI Groz-Beckert: {len(df):,} Zeilen")
    return df


def enrich_with_bi(invoices: pd.DataFrame, bi: pd.DataFrame) -> pd.DataFrame:
    """
    Für Sendungen ohne Gewicht (gewicht_kg == 0 oder NaN) BI-Daten einlesen.
    Für AX-Sendungen BI-Erlöse ergänzen wo PDF keine exakten Beträge hat.
    """
    if invoices.empty or bi.empty:
        return invoices

    needed_cols = [c for c in ["Tonnage (eff.)", "Lademeter", "Erloese", "Erlöse Fracht",
                               "Versender PLZ", "Versender Land", "Empfänger PLZ", "Empfänger Land"]
                   if c in bi.columns]
    # Keep first occurrence per Auftragsnummer (duplicates allowed in BI)
    bi_dedup = bi.drop_duplicates(subset=["Auftragsnummer"], keep="first")
    bi_lookup = bi_dedup.set_index("Auftragsnummer")[needed_cols].to_dict("index")

    rows = []
    for _, row in invoices.iterrows():
        r = row.to_dict()
        auftrag = str(r.get("auftragsnr") or "").strip()
        bi_row  = bi_lookup.get(auftrag)
        if bi_row:
            # Gewicht aus BI wenn PDF-Gewicht fehlt
            if not r.get("gewicht_kg") or r["gewicht_kg"] <= 0:
                r["gewicht_kg"]  = bi_row.get("Tonnage (eff.)") or 0
                r["lademeter"]   = bi_row.get("Lademeter")
                r["_from_bi"]    = True
            # Erlöse aus BI wenn PDF-Wert fehlt (v.a. DINAS Storni)
            if not r.get("erloes_eur") or r["erloes_eur"] == 0:
                r["erloes_eur"]  = bi_row.get("Erloese") or 0
                r["fracht_eur"]  = bi_row.get("Erlöse Fracht") or 0
                r["_from_bi"]    = True
            # Empfänger-PLZ/Land aus BI wenn unbekannt
            if not r.get("empf_plz"):
                r["empf_plz"]    = str(bi_row.get("Empfänger PLZ") or "").strip()
                r["empf_land"]   = str(bi_row.get("Empfänger Land") or "").strip()
        rows.append(r)

    return pd.DataFrame(rows)


def normalize_invoices(df: pd.DataFrame) -> pd.DataFrame:
    """PLZ bereinigen, billing_weight_kg und €/100kg berechnen, route_key setzen."""
    if df.empty:
        return df
    df = df.copy()

    # Typ-Sicherheit
    df["gewicht_kg"]  = pd.to_numeric(df["gewicht_kg"],  errors="coerce").fillna(0)
    df["erloes_eur"]  = pd.to_numeric(df["erloes_eur"],  errors="coerce").fillna(0)
    df["fracht_eur"]  = pd.to_numeric(df["fracht_eur"],  errors="coerce").fillna(0)
    df["leistungsdatum"] = pd.to_datetime(df["leistungsdatum"], errors="coerce")

    # Rechnungen vor 01.01.2025 ignorieren
    MIN_DATE = pd.Timestamp("2025-01-01")
    df = df[df["leistungsdatum"] >= MIN_DATE].copy()

    # Storni + Nullgewicht ausschließen
    df = df[~df["is_storno"].fillna(False)].copy()
    df = df[df["gewicht_kg"] > 0].copy()

    # PRE / POST / AX_HIST
    # Systembasierte Zuweisung:
    #   DINAS-Rechnungen → immer PRE (Altsystem)
    #   AX-Rechnungen ab Migrationsdatum → POST (Neusystem)
    #   AX-Rechnungen vor Migrationsdatum → AX_HIST (historisch, kein Vergleich)
    def _assign_periode(row):
        if row["system"] == "DINAS":
            return "PRE"
        elif row["leistungsdatum"] >= MIGRATION_DATE:
            return "POST"
        else:
            return "AX_HIST"   # alte AX-Rechnungen vor Migration

    df["periode"] = df.apply(_assign_periode, axis=1)

    # PLZ normalisieren (5 Zeichen, führende Nullen)
    df["sender_plz"] = df["sender_plz"].astype(str).str.strip().str.replace(r"[^\w]", "", regex=True).str[:5]
    df["empf_plz"]   = df["empf_plz"].astype(str).str.strip().str.replace(r"[^\w]", "", regex=True).str[:5]
    df["sender_land"]= df["sender_land"].astype(str).str.strip().str.upper()
    df["empf_land"]  = df["empf_land"].astype(str).str.strip().str.upper()

    # Abrechnungsgewicht auf 100 kg aufrunden (für Gruppierung)
    df["billing_weight_kg"] = df["gewicht_kg"].apply(
        lambda t: int(math.ceil(t / 100) * 100) if t > 0 else 0
    )

    # Frachterlös je 100 kg = Fracht-EUR / frachtpflichtiges Gewicht * 100
    # (frachtpflichtiges Gewicht = gewicht_kg direkt aus Rechnung, ohne Rundung)
    df["erloes_je_100kg"] = np.where(
        df["gewicht_kg"] > 0,
        df["fracht_eur"] / df["gewicht_kg"] * 100,
        np.nan
    )
    # Alias (gleiche Berechnung, für Rückwärtskompatibilität der Spaltenbezeichnung)
    df["fracht_je_100kg"] = df["erloes_je_100kg"]

    # Relation-Key
    df["route_key"] = (
        df["sender_plz"] + "|" + df["sender_land"]
        + " → "
        + df["empf_plz"].str[:2] + "|" + df["empf_land"]
    )

    return df


# ═══════════════════════════════════════════════════════════════════════════════
# D  VERGLEICHSENGINE
# ═══════════════════════════════════════════════════════════════════════════════

def build_comparison_groups(df: pd.DataFrame) -> list[dict]:
    """
    Pro Relation (route_key) mit mind. 1 PRE + 1 POST Sendung:
    Statistiken und bis zu MAX_EXAMPLES Beispielsendungen je Seite.

    Vergleich auf Basis Median-€/100kg (Erlöse), da DINAS-Rechnungen
    oft konsolidierte Sendungen mit höherem Gesamtgewicht haben als
    einzelne AX-Sendungen → exaktes Gewichts-Matching meist nicht möglich.

    Innerhalb der Relation werden Sendungen nach Gewichtsklassen gruppiert
    (bis 500 / bis 1000 / bis 2000 / bis 3000 / bis 5000 / bis 10000 / >10000 kg)
    um die Darstellung übersichtlich zu halten.
    """
    WEIGHT_BANDS = [500, 1000, 2000, 3000, 5000, 10000, float("inf")]
    BAND_LABELS  = [
        "bis 500 kg", "501–1.000 kg", "1.001–2.000 kg",
        "2.001–3.000 kg", "3.001–5.000 kg", "5.001–10.000 kg", "über 10.000 kg"
    ]

    def weight_band(kg):
        for i, limit in enumerate(WEIGHT_BANDS):
            if kg <= limit:
                return BAND_LABELS[i]
        return BAND_LABELS[-1]

    groups = []
    pre_df  = df[df["periode"] == "PRE"]
    post_df = df[df["periode"] == "POST"]

    common_routes = set(pre_df["route_key"]) & set(post_df["route_key"])
    for route in sorted(common_routes):
        p = pre_df[pre_df["route_key"]  == route].copy()
        q = post_df[post_df["route_key"] == route].copy()

        pre_rate  = p["erloes_je_100kg"].median()
        post_rate = q["erloes_je_100kg"].median()

        if pd.isna(pre_rate) or pd.isna(post_rate) or pre_rate == 0:
            continue

        abw = (post_rate - pre_rate) / abs(pre_rate) * 100

        # Beispielsendungen: bis zu MAX_EXAMPLES je Gewichtsklasse je Seite (PRE / POST)
        # Sortiert: jeweils neueste Sendungen zuerst
        def pick_examples(sub):
            sub = sub.sort_values("leistungsdatum", ascending=False)
            sub["_band"] = sub["billing_weight_kg"].apply(weight_band)
            rows = []
            seen_bands: dict[str, int] = {}
            for _, r in sub.iterrows():
                b = r["_band"]
                if seen_bands.get(b, 0) < MAX_EXAMPLES:
                    rows.append(r.to_dict())
                    seen_bands[b] = seen_bands.get(b, 0) + 1
                if len(rows) >= MAX_EXAMPLES * 3:   # hard cap
                    break
            return rows

        groups.append(dict(
            route_key         = route,
            billing_weight_kg = None,   # route-level (no exact weight matching)
            empf_land         = p["empf_land"].iloc[0],
            empf_plz_sample   = p["empf_plz"].iloc[0],
            # PRE stats
            n_pre             = len(p),
            sum_erloes_pre    = p["erloes_eur"].sum(),
            avg_erloes_pre    = p["erloes_eur"].mean(),
            median_100kg_pre  = pre_rate,
            avg_fracht_pre    = p["fracht_eur"].mean(),
            min_weight_pre    = int(p["billing_weight_kg"].min()),
            max_weight_pre    = int(p["billing_weight_kg"].max()),
            # POST stats
            n_post            = len(q),
            sum_erloes_post   = q["erloes_eur"].sum(),
            avg_erloes_post   = q["erloes_eur"].mean(),
            median_100kg_post = post_rate,
            avg_fracht_post   = q["fracht_eur"].mean(),
            min_weight_post   = int(q["billing_weight_kg"].min()),
            max_weight_post   = int(q["billing_weight_kg"].max()),
            # Delta
            abw_pct           = abw,
            unterfakt         = abw < -5.0,
            # Beispielsendungen
            examples_pre      = pick_examples(p),
            examples_post     = pick_examples(q),
        ))

    # Sortierung: Unterfakturierung zuerst, dann nach |Abweichung|
    groups.sort(key=lambda g: (not g["unterfakt"], abs(g["abw_pct"])), reverse=True)
    return groups


# ═══════════════════════════════════════════════════════════════════════════════
# E  EXCEL WRITER
# ═══════════════════════════════════════════════════════════════════════════════

def _hdr(cell, bg=C_HDR, fc="FFFFFF", bold=True, sz=9):
    cell.fill = PatternFill("solid", fgColor=bg)
    cell.font = Font(bold=bold, color=fc, name="Calibri", size=sz)
    cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

def _dat(cell, bg=None, right=False, sz=9, bold=False):
    if bg:
        cell.fill = PatternFill("solid", fgColor=bg)
    cell.font = Font(name="Calibri", size=sz, bold=bold)
    cell.alignment = Alignment(
        horizontal="right" if (right or isinstance(cell.value, (int, float))) else "left",
        vertical="center"
    )

def _border():
    s = Side(border_style="thin", color="CCCCCC")
    return Border(left=s, right=s, top=s, bottom=s)

def _autofit(ws, mn=8, mx=50):
    for col in ws.columns:
        w = max((len(str(c.value or "")) for c in col), default=0)
        ws.column_dimensions[get_column_letter(col[0].column)].width = max(mn, min(w + 2, mx))

def _pct_bg(pct):
    if pd.isna(pct):
        return None
    if pct < -10:   return C_LOSS
    if pct < -5:    return C_WARN
    if pct > 5:     return C_OK
    return None


# ── Sheet 0: Zusammenfassung ──────────────────────────────────────────────────

def write_summary(ws, df, groups):
    ws.title = "Zusammenfassung"
    pre  = df[df["periode"] == "PRE"]
    post = df[df["periode"] == "POST"]
    n_unterfakt = sum(1 for g in groups if g["unterfakt"])

    rows = [
        ("GROZ-BECKERT – Dinas vs. AX Rechnungsvergleich (PDF-Basis)", ""),
        ("Erstellt", pd.Timestamp.today().strftime("%d.%m.%Y")),
        ("", ""),
        ("Vergleichsmethode", "Nur fakturierte PDF-Rechnungen; Fallback BI via Auftragsnummer"),
        ("Matching-Kriterium", "Gleiche Route + gleiches auf 100 kg aufgerundetes Gewicht"),
        ("Max. Beispiele je Gruppe", str(MAX_EXAMPLES)),
        ("", ""),
        ("── PRE (Dinas-System) ──────────────────────", ""),
        ("Sendungen", len(pre)),
        ("Σ Erlöse", f"{pre['erloes_eur'].sum():,.2f} €"),
        ("Ø Erlöse/Sendung", f"{pre['erloes_eur'].mean():,.2f} €"),
        ("Median €/100 kg", f"{pre['erloes_je_100kg'].median():,.4f}"),
        ("Ø Gewicht kg", f"{pre['gewicht_kg'].mean():,.1f}"),
        ("", ""),
        ("── POST (AX-System) ────────────────────────", ""),
        ("Sendungen", len(post)),
        ("Σ Erlöse", f"{post['erloes_eur'].sum():,.2f} €"),
        ("Ø Erlöse/Sendung", f"{post['erloes_eur'].mean():,.2f} €"),
        ("Median €/100 kg", f"{post['erloes_je_100kg'].median():,.4f}"),
        ("Ø Gewicht kg", f"{post['gewicht_kg'].mean():,.1f}"),
        ("", ""),
        ("── Paarvergleich (gleiche Route + gleiches Gewicht) ──", ""),
        ("Vergleichsgruppen gesamt", len(groups)),
        ("Davon Unterfakturierung AX (>5% unter Dinas)", n_unterfakt),
    ]

    for ri, (lbl, val) in enumerate(rows, 1):
        cl = ws.cell(ri, 1, lbl)
        cv = ws.cell(ri, 2, val)
        if lbl.startswith("GROZ"):
            cl.font = Font(bold=True, name="Calibri", size=13, color=C_TITLE)
            ws.merge_cells(f"A{ri}:B{ri}")
        elif lbl.startswith("──"):
            cl.font = Font(bold=True, name="Calibri", size=10, color=C_TITLE)
        else:
            cl.font = Font(name="Calibri", size=10)
            cv.font = Font(bold=True, name="Calibri", size=10)

    ws.column_dimensions["A"].width = 46
    ws.column_dimensions["B"].width = 30


# ── Sheet 1: Relationen-Übersicht ─────────────────────────────────────────────

def write_uebersicht(ws, groups):
    ws.title = "Übersicht_Relationen"
    cols = [
        ("Relation", 30), ("Land", 7),
        ("Gew.-Bereich Dinas (kg)", 18), ("Gew.-Bereich AX (kg)", 18),
        ("n Dinas", 8), ("Σ Erlöse Dinas €", 14), ("Ø Erlöse Dinas €", 13),
        ("Median €/100kg Dinas", 16), ("Ø Fracht Dinas €", 13),
        ("n AX", 7), ("Σ Erlöse AX €", 12), ("Ø Erlöse AX €", 12),
        ("Median €/100kg AX", 15), ("Ø Fracht AX €", 12),
        ("Abw. %", 9), ("Status", 14),
    ]
    for ci, (h, w) in enumerate(cols, 1):
        cell = ws.cell(1, ci, h)
        _hdr(cell)
        ws.column_dimensions[get_column_letter(ci)].width = w

    ws.row_dimensions[1].height = 30
    ws.freeze_panes = "A2"

    for ri, g in enumerate(groups, 2):
        abw = g["abw_pct"]
        bg  = C_LOSS if abw < -10 else (C_WARN if abw < -5 else (C_OK if abw > 5 else "FFFFFF"))
        pre_range  = f"{g['min_weight_pre']:,} – {g['max_weight_pre']:,}"
        post_range = f"{g['min_weight_post']:,} – {g['max_weight_post']:,}"
        vals = [
            g["route_key"], g["empf_land"],
            pre_range, post_range,
            g["n_pre"],
            round(g["sum_erloes_pre"], 2), round(g["avg_erloes_pre"], 2),
            round(g["median_100kg_pre"], 4), round(g["avg_fracht_pre"], 2),
            g["n_post"],
            round(g["sum_erloes_post"], 2), round(g["avg_erloes_post"], 2),
            round(g["median_100kg_post"], 4), round(g["avg_fracht_post"], 2),
            round(abw, 2),
            "⚠ Unterfakt." if g["unterfakt"] else ("↑ Überfakt." if abw > 5 else "✓ OK"),
        ]
        for ci, v in enumerate(vals, 1):
            cell = ws.cell(ri, ci, v)
            _dat(cell, bg if ci in (15, 16) else ("F5F5F5" if ri % 2 == 0 else "FFFFFF"))
            cell.border = _border()


# ── Sheet 2: Paarvergleich Sendungsebene ──────────────────────────────────────

def write_paarvergleich(ws, groups):
    ws.title = "Paarvergleich_Sendungen"
    ws.freeze_panes = "A3"

    # Spaltenköpfe
    hdr1 = ["System", "Rechnungsnr.", "Auftragsnr.", "Leistungsdatum",
             "Absender", "Sender PLZ", "Empfänger", "Empf. PLZ", "Empf. Land",
             "Gewicht kg", "Abr.-Gew. kg", "LDM", "Stellplätze",
             "Fracht €", "Maut €", "Diesel €", "Verzollung €", "Neben €",
             "Erlöse gesamt €", "Fracht €/100kg", "PDF-Datei"]

    for ci, h in enumerate(hdr1, 1):
        _hdr(ws.cell(1, ci, h), bg=C_TITLE, sz=9)
    ws.row_dimensions[1].height = 26

    ri = 2
    for g in groups:
        # Gruppenüberschrift
        label = (f"RELATION: {g['route_key']}  |  "
                 f"Abw.: {g['abw_pct']:+.1f}%  |  "
                 f"Dinas (n={g['n_pre']}, {g['min_weight_pre']:,}–{g['max_weight_pre']:,} kg)"
                 f" Median: {g['median_100kg_pre']:.3f} €/100kg  |  "
                 f"AX (n={g['n_post']}, {g['min_weight_post']:,}–{g['max_weight_post']:,} kg)"
                 f" Median: {g['median_100kg_post']:.3f} €/100kg")

        title_bg = C_LOSS if g["unterfakt"] else (C_WARN if g["abw_pct"] > 5 else C_COMP)
        cell = ws.cell(ri, 1, label)
        cell.fill = PatternFill("solid", fgColor=title_bg)
        cell.font = Font(bold=True, name="Calibri", size=9, color="000000")
        ws.merge_cells(f"A{ri}:{get_column_letter(len(hdr1))}{ri}")
        ws.row_dimensions[ri].height = 18
        ri += 1

        def write_examples(examples, system_label, bg_base):
            nonlocal ri
            for ex in examples[:MAX_EXAMPLES]:
                ld = ex.get("leistungsdatum")
                ld_str = ld.strftime("%d.%m.%Y") if hasattr(ld, "strftime") else str(ld or "")[:10]
                rate = ex.get("erloes_je_100kg")
                stp = ex.get("stellplaetze")
                ldm = ex.get("lademeter")
                # Use actual system name from data (AX or DINAS), fallback to label
                system = ex.get("system") or system_label
                vals = [
                    system,
                    ex.get("rechnungsnr", ""),
                    ex.get("auftragsnr", ""),
                    ld_str,
                    ex.get("sender_name", ""),
                    ex.get("sender_plz", ""),
                    ex.get("empf_name", ""),
                    ex.get("empf_plz", ""),
                    ex.get("empf_land", ""),
                    round(ex.get("gewicht_kg", 0) or 0, 2),
                    ex.get("billing_weight_kg", ""),
                    round(ldm, 2) if ldm and not (isinstance(ldm, float) and math.isnan(ldm)) else "",
                    round(stp, 2) if stp and not (isinstance(stp, float) and math.isnan(stp)) else "",
                    round(ex.get("fracht_eur", 0) or 0, 2),
                    round(ex.get("maut_eur",   0) or 0, 2),
                    round(ex.get("diesel_eur",  0) or 0, 2),
                    round(ex.get("verzoll_eur", 0) or 0, 2),
                    round(ex.get("neben_eur",   0) or 0, 2),
                    round(ex.get("erloes_eur", 0) or 0, 2),
                    round(rate, 4) if rate and not (isinstance(rate, float) and math.isnan(rate)) else "",
                    ex.get("pdf_name", ""),
                ]
                for ci, v in enumerate(vals, 1):
                    cell = ws.cell(ri, ci, v)
                    _dat(cell, bg_base)
                    cell.border = _border()
                ri += 1

        write_examples(g["examples_pre"],  "DINAS", C_DINAS)
        # Trennzeile mit Statistik
        sep = ws.cell(ri, 1, f"  ∅ Dinas: {g['avg_erloes_pre']:.2f} €  |  Median Fracht €/100kg: {g['median_100kg_pre']:.4f}")
        sep.fill = PatternFill("solid", fgColor="DDEEFF")
        sep.font = Font(italic=True, name="Calibri", size=8)
        ws.merge_cells(f"A{ri}:{get_column_letter(len(hdr1))}{ri}")
        ri += 1

        write_examples(g["examples_post"], "AX", C_AX)
        sep2 = ws.cell(ri, 1, f"  ∅ AX:    {g['avg_erloes_post']:.2f} €  |  Median Fracht €/100kg: {g['median_100kg_post']:.4f}  |  Abw.: {g['abw_pct']:+.2f}%")
        sep2.fill = PatternFill("solid", fgColor="FFE8CC")
        sep2.font = Font(italic=True, name="Calibri", size=8)
        ws.merge_cells(f"A{ri}:{get_column_letter(len(hdr1))}{ri}")
        ri += 1

        # Leerzeile
        ri += 1

    _autofit(ws, mn=8, mx=45)


# ── Sheet 3: Alle DINAS-Sendungen ─────────────────────────────────────────────

def write_all_invoices(ws, df, title, bg):
    ws.title = title
    cols = ["rechnungsnr","rechnungsdatum","leistungsdatum","sendungsnr","auftragsnr",
            "sender_name","sender_plz","sender_land","empf_name","empf_plz","empf_land",
            "gewicht_kg","billing_weight_kg","lademeter","stellplaetze",
            "fracht_eur","maut_eur","diesel_eur","verzoll_eur","neben_eur","erloes_eur",
            "erloes_je_100kg","route_key","pdf_name"]
    labels = {
        "rechnungsnr": "Rechnungsnr.", "rechnungsdatum": "Rechng.-Datum",
        "leistungsdatum": "Leistungsdatum", "sendungsnr": "Sendungsnr.",
        "auftragsnr": "Auftragsnr.",
        "sender_name": "Absender", "sender_plz": "Sender PLZ",
        "sender_land": "Sender Land", "empf_name": "Empfänger", "empf_plz": "Empf. PLZ",
        "empf_land": "Empf. Land", "gewicht_kg": "Gew. kg",
        "billing_weight_kg": "Abr.-Gew. kg", "lademeter": "LDM",
        "stellplaetze": "Stellplätze",
        "fracht_eur": "Fracht €", "maut_eur": "Maut €",
        "diesel_eur": "Diesel €", "verzoll_eur": "Verzollung €", "neben_eur": "Neben €",
        "erloes_eur": "Erlöse gesamt €",
        "erloes_je_100kg": "Fracht €/100kg",
        "route_key": "Relation", "pdf_name": "PDF-Datei",
    }
    existing = [c for c in cols if c in df.columns]
    for ci, c in enumerate(existing, 1):
        _hdr(ws.cell(1, ci, labels.get(c, c)), bg=C_HDR)
    ws.row_dimensions[1].height = 26
    ws.freeze_panes = "A2"

    for ri, (_, row) in enumerate(df.iterrows(), 2):
        row_bg = bg if ri % 2 == 0 else "FFFFFF"
        for ci, col in enumerate(existing, 1):
            val = row.get(col, "")
            if pd.isna(val): val = ""
            elif isinstance(val, float): val = round(val, 4)
            elif hasattr(val, "strftime"): val = val.strftime("%d.%m.%Y")
            cell = ws.cell(ri, ci, val)
            _dat(cell, row_bg)
            cell.border = _border()

    _autofit(ws, mn=8, mx=40)


def write_besonderheiten(ws, path: Path):
    """Kundenbesonderheiten als Referenzblatt einfügen."""
    ws.title = "Kundenbesonderheiten"
    try:
        df = pd.read_excel(path)
    except Exception as e:
        ws.cell(1, 1, f"Datei nicht gefunden: {e}")
        return

    for ci, col in enumerate(df.columns, 1):
        cell = ws.cell(1, ci, str(col).replace("\n", " ").strip())
        _hdr(cell, bg=C_HDR, sz=9)
        ws.column_dimensions[get_column_letter(ci)].width = min(40, max(12, len(str(col)) + 4))
    ws.row_dimensions[1].height = 28
    ws.freeze_panes = "A2"

    for ri, (_, row) in enumerate(df.iterrows(), 2):
        row_bg = C_GREY if ri % 2 == 0 else "FFFFFF"
        for ci, val in enumerate(row, 1):
            if isinstance(val, float) and math.isnan(val):
                val = ""
            cell = ws.cell(ri, ci, str(val).strip() if val != "" else "")
            cell.fill = PatternFill("solid", fgColor=row_bg)
            cell.font = Font(name="Calibri", size=8)
            cell.alignment = Alignment(wrap_text=True, vertical="top")
            cell.border = _border()

    ws.row_dimensions[1].height = 28


# ═══════════════════════════════════════════════════════════════════════════════
# F  MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def run_customer(customer: dict, bi_raw: pd.DataFrame, zip_path: Path) -> None:
    """Komplette Pipeline für einen Kunden: laden → normalisieren → Excel."""
    name = customer["name"]
    slug = customer["slug"]
    output_path = OUTPUT_DIR / slug / "rechnungsvergleich.xlsx"

    print("=" * 65)
    print(f"  {name}  –  DINAS ↔ AX")
    print("=" * 65)

    # ── 1. PDFs laden ────────────────────────────────────────────────────────
    dinas_df, ax_df = load_invoices_for_customer(customer, zip_path)

    if dinas_df.empty and ax_df.empty:
        print(f"  [{name}] Keine Rechnungen – übersprungen.\n")
        return

    # ── 2. BI-Fallback filtern ───────────────────────────────────────────────
    bi_df = pd.DataFrame()
    if not bi_raw.empty and customer.get("bi_filter"):
        mask = bi_raw["Kunden Name"].astype(str).str.contains(
            customer["bi_filter"], case=False, na=False
        )
        bi_df = bi_raw[mask].copy()
        if not bi_df.empty:
            print(f"  {name} im BI-Report: {len(bi_df):,} Zeilen")

    # ── 3. Anreichern & normalisieren ────────────────────────────────────────
    if not dinas_df.empty and not bi_df.empty:
        dinas_df = enrich_with_bi(dinas_df, bi_df)
    if not ax_df.empty and not bi_df.empty:
        ax_df = enrich_with_bi(ax_df, bi_df)

    all_df = pd.concat([dinas_df, ax_df], ignore_index=True)
    all_df = normalize_invoices(all_df)

    if all_df.empty:
        print(f"  [{name}] Nach Normalisierung keine Daten – übersprungen.\n")
        return

    n_pre  = (all_df["periode"] == "PRE").sum()
    n_post = (all_df["periode"] == "POST").sum()
    n_hist = (all_df["periode"] == "AX_HIST").sum()
    print(f"\n  Normalisiert: {len(all_df):,} Sendungen   "
          f"DINAS PRE={n_pre:,}  AX POST={n_post:,}  AX historisch (excl.)={n_hist:,}")

    # ── 4. Vergleichsgruppen bilden ──────────────────────────────────────────
    groups = build_comparison_groups(all_df)
    n_unter = sum(1 for g in groups if g["unterfakt"])
    print(f"  Vergleichsgruppen: {len(groups):,}   davon Unterfakturierung: {n_unter:,}")

    # ── 5. Excel schreiben ───────────────────────────────────────────────────
    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    wb.remove(wb.active)

    ws_sum = wb.create_sheet("Zusammenfassung")
    write_summary(ws_sum, all_df, groups)

    ws_ue = wb.create_sheet("Übersicht_Relationen")
    write_uebersicht(ws_ue, groups)

    ws_paar = wb.create_sheet("Paarvergleich_Sendungen")
    write_paarvergleich(ws_paar, groups)

    if not all_df[all_df["periode"] == "PRE"].empty:
        ws_din = wb.create_sheet("DINAS_Einzelrechnungen")
        write_all_invoices(ws_din, all_df[all_df["periode"] == "PRE"].copy(),
                           "DINAS_Einzelrechnungen", C_DINAS)

    if not all_df[all_df["periode"] == "POST"].empty:
        ws_ax = wb.create_sheet("AX_Einzelrechnungen")
        write_all_invoices(ws_ax, all_df[all_df["periode"] == "POST"].copy(),
                           "AX_Einzelrechnungen", C_AX)

    ax_hist = all_df[all_df["periode"] == "AX_HIST"]
    if not ax_hist.empty:
        ws_axh = wb.create_sheet("AX_historisch")
        write_all_invoices(ws_axh, ax_hist.copy(), "AX_historisch", "E8F5E9")

    if BESONDERHEITEN_PATH.exists():
        ws_beson = wb.create_sheet("Kundenbesonderheiten")
        write_besonderheiten(ws_beson, BESONDERHEITEN_PATH)

    wb.save(output_path)
    print(f"\n  Gespeichert: {output_path}\n")


def main():
    import sys
    # Optional: bestimmte Kunden per Kommandozeile angeben (slug oder name)
    filter_slugs = {a.lower() for a in sys.argv[1:]}

    customers = CUSTOMERS
    if filter_slugs:
        customers = [c for c in CUSTOMERS
                     if c["slug"] in filter_slugs or c["name"].lower() in filter_slugs]
        if not customers:
            print(f"Keine Kunden gefunden für: {filter_slugs}")
            return

    # BI-Report einmalig laden
    bi_raw = pd.DataFrame()
    if ZIP_PATH.exists():
        try:
            import io as _io
            print("[BI] Lade BI-Report aus ZIP …")
            with zipfile.ZipFile(ZIP_PATH) as _z:
                _data = _z.read(BI_ZIP_NAME)
            bi_raw = pd.read_excel(
                _io.BytesIO(_data),
                dtype={"Auftragsnummer": str, "Rechnungsnummer": str,
                       "Kunden Nr BK": str, "Versender PLZ": str, "Empfänger PLZ": str},
            )
            bi_raw["Auftragsnummer"] = bi_raw["Auftragsnummer"].astype(str).str.strip()
            print(f"  {len(bi_raw):,} Zeilen geladen\n")
        except Exception as e:
            print(f"[WARN] BI-Report nicht geladen: {e}\n")

    for customer in customers:
        try:
            run_customer(customer, bi_raw, ZIP_PATH)
        except Exception as e:
            print(f"[FEHLER] {customer['name']}: {e}\n")

    print("=" * 65)
    print("  Alle Kunden verarbeitet.")
    print("=" * 65)


if __name__ == "__main__":
    main()
