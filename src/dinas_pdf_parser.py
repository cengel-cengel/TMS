#!/usr/bin/env python3
"""
dinas_pdf_parser.py
===================
Parst Dinas-Rechnungs-PDFs (ERKA Internationale Spedition) und extrahiert
pro Sendungsposition: Rechnungsnummer, Sendungsnummer, Leistungsdatum,
Empfänger-PLZ/-Land sowie alle NK-Positionen aufgeschlüsselt.

Unterstützte Formate:
  A) Einzel-Sendungsrechnung (1 Position, explizite Labels)
     → FRACHT/FREIGHT, DIESEL, SSD, AUSFUHR, SULPHUR, ZOLL, …
  B) Multi-Sendungsrechnung (N Positionen, manchmal ohne Labels)
     → erster Betrag pro Position = FRACHT (Frankatur-Header)
  C) Sammelrechnungen (Flat-Pauschalen, kein Sendungsbezug)
     → werden übersprungen (kein DATE_POS-Muster)

Output: pd.DataFrame mit einer Zeile pro Sendungsposition
Physikalische Felder (direkt aus PDF):
  ldm, kg_rechnung, stellplaetze, volumen, leistungsdatum
"""

import re
import glob
import os
import pickle
import warnings
from pathlib import Path

import fitz          # PyMuPDF
import pandas as pd
import numpy as np

warnings.filterwarnings('ignore')

BASE    = Path('/home/user/TMS')
OUT_DIR = BASE / 'output'

# ── regex ──────────────────────────────────────────────────────────────────
# Betrag-Zeile: "-1.234,56 EUR" oder "1234,56 EUR" oder "-1,58 EUR"
EUR_RE   = re.compile(r'^(-?\d{1,3}(?:\.\d{3})*,\d{2}|-?\d+,\d{2})\s+EUR$')
CODE_RE  = re.compile(r'^\d{3,5}$')           # Kostenstellen-Codes (0102, 0500 …)
DATE_POS = re.compile(r'^(\d+)\)\s+(\d{2}\.\d{2}\.\d{2})$')  # "1) 15.08.25"
SEND_RE  = re.compile(r'^\((\d+)\)$')                          # "(32939529)"
# 1-2 letter country codes: GB-LE671, I-42017 (single), F-12100, E-46930
DEST_RE  = re.compile(r'^([A-Z]{1,2})-(\S+)')
# LDM/Stp lines: case-insensitive, trailing 'g' optional (PDF truncation)
#   "0,40 ldm = 600 kg", "1,240 ldm = 1550 k", "13,60 Ldm = 6145 kg"
LDM_RE   = re.compile(r'^([\d,]+)\s+[Ll][Dd][Mm]\s*=\s*([\d.]+)\s+kg?$')
#   "5,000 Stp = 3000 k", "2,500 Stp = 1500 k"
STP_RE   = re.compile(r'^([\d,]+)\s+[Ss]tp\s*=\s*([\d.]+)\s+k', re.I)
# Standalone kg: "1147 kg", "582 kg", "20.393 kg"
KG_ONLY_RE = re.compile(r'^([\d]+(?:\.\d{3})*)\s+kg$', re.I)
# Volume: "0,02 cbm =", "0,34 cbm", "2,89 cbm"
VOL_CBM_RE = re.compile(r'^([\d,]+)\s+cbm(?:\s*=|$|\s)', re.I)
# Solo (ohne = kg): "2,00 stp", "0,40 ldm"
STP_SOLO_RE = re.compile(r'^([\d,]+)\s+[Ss]tp$', re.I)
LDM_SOLO_RE = re.compile(r'^([\d,]+)\s+[Ll][Dd][Mm]$', re.I)
BETRAG   = 'Betrag'

# ── Parser B / C2: "DD.MM.YY Referenz-Erka: SNNNNN" (date optional) ─────────
REDEBIT_ENTRY      = re.compile(r'^(\d{2}\.\d{2}\.\d{2})\s+Referenz-Erka:\s+(\d+)')
REDEBIT_ENTRY_ND   = re.compile(r'^Referenz-Erka:\s+(\d+)')   # no-date variant
# Generic kg finder (used in fallback parsers)
GEW_KG_RE          = re.compile(r'(\d[\d.]*)\s+kg', re.I)

# Single-letter country codes used in DINAS → normalize to ISO 2-letter
_COUNTRY_NORM = {
    'F': 'FR', 'I': 'IT', 'E': 'ES', 'L': 'LU', 'B': 'BE',
    'A': 'AT', 'P': 'PT', 'N': 'NL', 'S': 'SE', 'D': 'DE',
}

# Zeilen-Präfixe, die NICHT als Label-Inhalt gezählt werden
SKIP_PREFIXES = (
    'NEU!!', 'Summe', 'Zwischensumme', 'WA-Zeit', 'https',
    'Gesamtstückzahl', 'Anlage', 'Zollpositionen', 'Bitte geben',
    'Buchungsdatum', 'Ihre Ust', 'Lieferantennr', 'WEITERE',
    'NEUES GESETZ', 'PORTE NACH', 'PRO SDG', 'Sendungssumme',
    'Umsatzsteuerfreie', 'gemäß', 'Gesamtbetrag', '1 Position',
    '2 Position', '3 Position',
    'Übertrag',   # Seitenübertrag in mehrseitigen Rechnungen
)

# Fußzeilen-Trigger → Sammeln von Items stoppen
FOOTER_TRIGGER = ('Sendungssumme', 'Zwischensumme', 'Gesamtbetrag',
                  '1 Position(en)', '2 Position(en)')


def eur_to_float(s: str) -> float:
    return float(s.replace('.', '').replace(',', '.'))


# ── NK-Kategorien ──────────────────────────────────────────────────────────
CATS = {
    'fracht'      : ['FRACHT', 'FREIGHT', 'FRANKATUR'],
    'diesel'      : ['DIESEL', 'ABSCHLAG', 'RÜCKVERGÜTUNG', 'FLOATER'],
    'maut_ssd'    : ['SSD', 'MAUT', 'SAFETY', 'SECURITY', 'LSZ',
                     'STRASSENBENUTZUNG'],
    'ausfuhr'     : ['AUSFUHRABFERT', 'AUSFUHR'],
    'verzollung'  : ['VERZOLLUNG', 'ZOLLPOSITION', 'ZUSÄTZLICHE ZOLL'],
    'zoll_duty'   : ['VORLAGEPROVISION', 'ZOLLEINFUHR'],
    'zoll_betrag' : ['ZOLL'],          # der Zollbetrag selbst (muss nach VERZOLLUNG stehen)
    'sulphur'     : ['SULPHUR', 'ENERGY', 'ENERGIEZUSCHLAG'],
    'neben_pausch': ['NEBENKOSTENPAUSCHALE'],
    'redebit'     : ['REDEBIT', 'RECHNUNGSBETRAG REDEBIT'],
}

def categorise(label: str) -> str:
    u = label.upper()
    for cat, keywords in CATS.items():
        if any(k in u for k in keywords):
            return cat
    return 'sonstige'


# ── Einzel-PDF parsen ──────────────────────────────────────────────────────
def parse_one(path: str) -> list[dict]:
    """
    Gibt Liste von Positions-Dicts zurück.
    Jedes Dict hat Schlüssel:
      rechnung_nr, sendungs_nr, leistungsdatum, empf_land, empf_plz,
      ldm, kg_rechnung, fracht, diesel, maut_ssd, ausfuhr, verzollung,
      zoll_duty, zoll_betrag, sulphur, neben_pausch, redebit, sonstige,
      total_steuerfrei, gesamtbetrag, n_items
    """
    doc   = fitz.open(path)
    # Alle Seiten lesen — mehrseitige Rechnungen (z.B. 23-seitige Sammelrechnungen)
    # würden bei doc[0]-only nur die erste Seite liefern.
    all_text = ''.join(page.get_text('text') for page in doc)
    lines = [l.strip() for l in all_text.split('\n') if l.strip()]
    rn    = os.path.basename(path).replace('RECHNUNG', '').replace('.pdf', '')

    # Suche nach invoice-Body-Start (Spalten-Header "Betrag")
    try:
        body_start = next(i for i, l in enumerate(lines) if l == BETRAG)
    except StopIteration:
        return []

    body = lines[body_start + 1:]

    positions: list[dict]     = []
    cur: dict | None          = None    # aktuell offene Position
    in_footer                 = False   # innerhalb Summen-Fußzeile
    label_buf: list[str]      = []      # Label-Zeilen vor nächster EUR-Zeile
    saw_any_item              = False   # schon ein Item in dieser Position?

    def _new_pos(pos_nr, leistdat):
        return {
            'rechnung_nr'    : rn,
            'pos_nr'         : pos_nr,
            'leistungsdatum' : leistdat,
            'sendungs_nr'    : '',
            'empf_land'      : '',
            'empf_plz'       : '',
            'ldm'            : None,
            'kg_rechnung'    : None,
            'stellplaetze'   : None,
            'volumen'        : None,
            '_await_vol_kg'  : False,  # after "N cbm =" grab next line as kg
            '_items'         : [],
        }

    def _save(pos):
        if pos and pos['_items']:
            positions.append(pos)

    for i, line in enumerate(body):

        # ── Positions-Start "1) 15.08.25" ────────────────────────────────
        m_date = DATE_POS.match(line)
        if m_date:
            _save(cur)
            cur         = _new_pos(m_date.group(1), m_date.group(2))
            in_footer   = False
            saw_any_item = False
            label_buf   = []
            continue

        if cur is None:
            continue

        # ── Sendungsnummer "(32939529)" ───────────────────────────────────
        if SEND_RE.match(line):
            cur['sendungs_nr'] = SEND_RE.match(line).group(1)
            label_buf = []
            continue

        # ── Fußzeile: Sammeln stoppen ─────────────────────────────────────
        if any(line.startswith(t) for t in FOOTER_TRIGGER):
            in_footer = True
            continue
        if in_footer:
            # Gesamtbetrag extrahieren, dann ignorieren
            if EUR_RE.match(line) and 'gesamtbetrag' not in cur:
                cur['gesamtbetrag'] = eur_to_float(EUR_RE.match(line).group(1))
            continue

        # ── Empfänger-Land/PLZ "GB-LE671 ..." or "I-42017 ..." ───────────
        m_dest = DEST_RE.match(line)
        if m_dest and not cur['empf_land']:
            raw_land = m_dest.group(1)
            cur['empf_land'] = _COUNTRY_NORM.get(raw_land, raw_land)
            cur['empf_plz']  = m_dest.group(2).split()[0]
            label_buf = []
            continue

        # ── Stellplätze: "5,000 Stp = 3000 k" (one-line) ───────────────
        m_stp = STP_RE.match(line)
        if m_stp:
            cur['stellplaetze'] = eur_to_float(m_stp.group(1))
            if cur['kg_rechnung'] is None:
                cur['kg_rechnung'] = float(m_stp.group(2).replace('.', ''))
            label_buf = []
            continue
        # zweizeilig: "1,000 Stp =" auf Zeile i, "600 k[g]" auf Zeile i+1
        if re.match(r'^[\d,]+\s+[Ss]tp\s*=$', line):
            cur['stellplaetze'] = eur_to_float(line.split()[0])
            if i + 1 < len(body):
                m_kg = re.match(r'^([\d.]+)\s+kg?$', body[i + 1], re.I)
                if m_kg and cur['kg_rechnung'] is None:
                    cur['kg_rechnung'] = float(m_kg.group(1).replace('.', ''))
            label_buf = []
            continue

        # ── Volumen: "0,02 cbm =" oder "0,34 cbm" ────────────────────────
        m_vol = VOL_CBM_RE.match(line)
        if m_vol:
            cur['volumen'] = eur_to_float(m_vol.group(1))
            # same-line kg after "=": "0,02 cbm = 5 kg"
            m_vol_kg = re.search(r'=\s*([\d]+(?:\.\d+)?)\s+kg?$', line, re.I)
            if m_vol_kg and cur['kg_rechnung'] is None:
                cur['kg_rechnung'] = float(m_vol_kg.group(1).replace('.', ''))
                cur['_await_vol_kg'] = False
            elif '=' in line:
                cur['_await_vol_kg'] = True   # next line = billing kg
            label_buf = []
            continue

        # ── await: kg line following "N cbm =" ───────────────────────────
        if cur['_await_vol_kg']:
            m_vkg = KG_ONLY_RE.match(line)
            if m_vkg:
                if cur['kg_rechnung'] is None:
                    cur['kg_rechnung'] = float(m_vkg.group(1).replace('.', ''))
                cur['_await_vol_kg'] = False
                label_buf = []
                continue
            cur['_await_vol_kg'] = False   # give up on next non-kg line

        # ── Solo Stellplätze: "2,00 stp" (kein = kg) ────────────────────
        if STP_SOLO_RE.match(line):
            cur['stellplaetze'] = eur_to_float(STP_SOLO_RE.match(line).group(1))
            label_buf = []
            continue

        # ── Solo LDM: "0,40 ldm" (kein = kg) ────────────────────────────
        if LDM_SOLO_RE.match(line):
            cur['ldm'] = eur_to_float(LDM_SOLO_RE.match(line).group(1))
            label_buf = []
            continue

        # ── LDM (case-insensitive, truncated k): "1,240 ldm = 1550 k" ───
        m_wt = LDM_RE.match(line)
        if m_wt:
            cur['ldm']         = eur_to_float(m_wt.group(1))
            cur['kg_rechnung'] = float(m_wt.group(2).replace('.', ''))
            label_buf = []
            continue
        # zweizeilig: "0,40 ldm =" auf Zeile i, "600 kg" auf Zeile i+1
        if re.match(r'^[\d,]+\s+[Ll][Dd][Mm]\s*=$', line):
            if i + 1 < len(body):
                next_l = body[i + 1]
                m_kg   = re.match(r'^([\d.]+)\s+kg?$', next_l, re.I)
                if m_kg:
                    cur['ldm']         = eur_to_float(line.split()[0])
                    cur['kg_rechnung'] = float(m_kg.group(1).replace('.', ''))
            label_buf = []
            continue

        # ── Standalone kg (first occurrence wins) ────────────────────────
        m_kg = KG_ONLY_RE.match(line)
        if m_kg:
            if cur['kg_rechnung'] is None:
                cur['kg_rechnung'] = float(m_kg.group(1).replace('.', ''))
            label_buf = []
            continue

        # ── EUR-Betragszeile ──────────────────────────────────────────────
        m_eur = EUR_RE.match(line)
        if m_eur:
            amount = eur_to_float(m_eur.group(1))
            # Label: label_buf bereinigen (Codes + Leerzeilen raus)
            clean  = [l for l in label_buf if l and not CODE_RE.match(l)]
            label  = ' / '.join(clean)

            # Erstes Item ohne explizites Service-Label → FRACHT
            if not saw_any_item and not any(
                kw in label.upper()
                for kwlist in CATS.values()
                for kw in kwlist
            ):
                label = 'FRACHT/FREIGHT'   # Implizit-Fracht

            cur['_items'].append({'label': label, 'amount': amount})
            saw_any_item = True
            label_buf    = []
            continue

        # ── Label-Puffer befüllen (Nicht-Fußzeile, Nicht-Code-Zeile) ──────
        if not any(line.startswith(p) for p in SKIP_PREFIXES):
            label_buf.append(line)

    _save(cur)
    return positions


# ── Positions-Dict → flache Zeile ─────────────────────────────────────────
def flatten(pos: dict) -> dict:
    _skip = {'_items', '_await_vol_kg'}
    row = {k: v for k, v in pos.items() if k not in _skip}
    # Kategorien null-initialisieren
    all_cats = list(CATS) + ['sonstige']
    for cat in all_cats:
        row[cat] = 0.0
    row['n_items'] = len(pos.get('_items', []))

    for item in pos.get('_items', []):
        cat = categorise(item['label'])
        row[cat] = round(row[cat] + item['amount'], 4)

    # Gesamtbetrag als Summe aller Positionen (falls nicht aus PDF)
    items_total = round(sum(row[c] for c in all_cats), 2)
    if 'gesamtbetrag' not in row or row.get('gesamtbetrag') is None:
        row['gesamtbetrag'] = items_total
    row['total_items'] = items_total
    return row


# ── Parser B / C2: Referenz-Erka body ────────────────────────────────────────
def parse_redebit_body(path: str, is_credit: bool = False) -> list[dict]:
    """
    Handles Rechnungskorrektur/Gutschrift (B), Redebit (C2), and misc special
    invoices that share the "DD.MM.YY Referenz-Erka: SNNNNN" entry format.
    One EUR amount per entry.  is_credit=True → amounts × -1.
    """
    doc      = fitz.open(path)
    all_text = ''.join(p.get_text('text') for p in doc)
    lines    = [l.strip() for l in all_text.split('\n') if l.strip()]
    rn       = os.path.basename(path).replace('RECHNUNG', '').replace('.pdf', '')
    sign     = -1.0 if is_credit else 1.0

    # Fallback date: document-level Buchungsdatum (used when entry has no date)
    doc_date = ''
    for idx, ln in enumerate(lines):
        if ln == 'Buchungsdatum' and idx + 1 < len(lines):
            doc_date = lines[idx + 1]
            break

    def _new():
        return {
            'rechnung_nr': rn, 'pos_nr': 0,
            'leistungsdatum': '', 'sendungs_nr': '',
            'empf_land': '', 'empf_plz': '',
            'ldm': None, 'kg_rechnung': None,
            'stellplaetze': None, 'volumen': None,
            '_await_vol_kg': False, '_items': [],
        }

    positions: list[dict] = []
    cur: dict | None      = None
    label_buf: list[str]  = []
    in_footer             = False

    for i, line in enumerate(lines):
        # ── New entry trigger ─────────────────────────────────────────────
        m = REDEBIT_ENTRY.match(line)
        m_nd = None if m else REDEBIT_ENTRY_ND.match(line)
        if m or m_nd:
            if cur and cur['_items']:
                positions.append(cur)
            cur               = _new()
            cur['pos_nr']     = len(positions) + 1
            cur['leistungsdatum'] = m.group(1) if m else doc_date
            cur['sendungs_nr']    = m.group(2) if m else m_nd.group(1)
            label_buf         = []
            in_footer         = False   # reset on each new entry
            continue

        if cur is None:
            continue

        # ── Footer: stop accumulating items once summary section reached ─
        if any(line.startswith(t) for t in FOOTER_TRIGGER):
            in_footer = True
            continue
        if in_footer:
            continue

        # ── Empfänger/destination ─────────────────────────────────────────
        if not cur['empf_land']:
            # Inline: "Emp/cons: COMPANY XX-NNNN CITY"
            m_empc = re.search(r'[Ee]mp/cons[: ]+.*?([A-Z]{1,2})-(\d+)', line)
            if m_empc:
                cur['empf_land'] = _COUNTRY_NORM.get(m_empc.group(1), m_empc.group(1))
                cur['empf_plz']  = m_empc.group(2)
                label_buf = []
                continue
            # Standalone dest line "I-40016 SAN GIORGIO"
            m_dest = DEST_RE.match(line)
            if m_dest:
                cur['empf_land'] = _COUNTRY_NORM.get(m_dest.group(1), m_dest.group(1))
                cur['empf_plz']  = m_dest.group(2).split()[0]
                label_buf = []
                continue

        # ── Gew/weight: kg ────────────────────────────────────────────────
        if re.match(r'[Gg]ew[./]', line):
            m_kg = GEW_KG_RE.search(line)
            if m_kg and cur['kg_rechnung'] is None:
                cur['kg_rechnung'] = float(m_kg.group(1).replace('.', ''))
            elif i + 1 < len(lines) and cur['kg_rechnung'] is None:
                m_kg2 = GEW_KG_RE.search(lines[i + 1])
                if m_kg2:
                    cur['kg_rechnung'] = float(m_kg2.group(1).replace('.', ''))
            label_buf = []
            continue

        # ── EUR amount ────────────────────────────────────────────────────
        m_eur = EUR_RE.match(line)
        if m_eur:
            amount = eur_to_float(m_eur.group(1)) * sign
            # Filter metadata noise from label buffer
            clean = [
                l for l in label_buf
                if l and not CODE_RE.match(l)
                and not re.match(r'^(Abs[/:]|Emp/|Your Ref|Ref\.:|[A-Z]\d{4,5}\b)', l)
            ]
            label = ' / '.join(clean) if clean else 'FRACHT/FREIGHT'
            if not any(kw in label.upper()
                       for kwlist in CATS.values() for kw in kwlist):
                label = 'FRACHT/FREIGHT'
            cur['_items'].append({'label': label, 'amount': amount})
            label_buf = []
            continue

        # ── Label buffer ──────────────────────────────────────────────────
        if not any(line.startswith(p) for p in SKIP_PREFIXES):
            label_buf.append(line)

    if cur and cur['_items']:
        positions.append(cur)
    return positions


# ── Parser C1: Differenzrechnung ──────────────────────────────────────────────
def parse_differenz(path: str) -> list[dict]:
    """
    Handles "Differenzrechnung zu Ihrem Beleg" format.
    Entry trigger: standalone line "Sendungsnr" → next line ": NNNN" → EUR.
    """
    doc      = fitz.open(path)
    all_text = ''.join(p.get_text('text') for p in doc)
    lines    = [l.strip() for l in all_text.split('\n') if l.strip()]
    rn       = os.path.basename(path).replace('RECHNUNG', '').replace('.pdf', '')

    # Document-level Buchungsdatum (shared by all entries)
    doc_date = ''
    for idx, ln in enumerate(lines):
        if ln == 'Buchungsdatum' and idx + 1 < len(lines):
            doc_date = lines[idx + 1]
            break

    def _new():
        return {
            'rechnung_nr': rn, 'pos_nr': 0,
            'leistungsdatum': doc_date, 'sendungs_nr': '',
            'empf_land': '', 'empf_plz': '',
            'ldm': None, 'kg_rechnung': None,
            'stellplaetze': None, 'volumen': None,
            '_await_vol_kg': False, '_items': [],
        }

    positions: list[dict] = []
    cur: dict | None      = None
    in_empf               = False
    in_gewicht            = False

    i = 0
    while i < len(lines):
        line = lines[i]

        # ── Entry trigger: "Sendungsnr" ───────────────────────────────────
        if line == 'Sendungsnr' and i + 1 < len(lines):
            if cur and cur['_items']:
                positions.append(cur)
            cur        = _new()
            cur['pos_nr'] = len(positions) + 1
            in_empf    = False
            in_gewicht = False
            # Next line: ": NNNN"
            m_snr = re.match(r'^:\s*(\d+)', lines[i + 1])
            if m_snr:
                cur['sendungs_nr'] = m_snr.group(1)
                i += 1
            # Line after that should be EUR amount
            if i + 1 < len(lines):
                m_eur = EUR_RE.match(lines[i + 1])
                if m_eur:
                    cur['_items'].append({
                        'label': 'FRACHT/FREIGHT',
                        'amount': eur_to_float(m_eur.group(1)),
                    })
                    i += 1
            i += 1
            continue

        if cur is None:
            i += 1
            continue

        # ── Empfänger block ───────────────────────────────────────────────
        if line == 'Empfänger':
            in_empf = True
            i += 1
            continue

        if in_empf and not cur['empf_land']:
            # PLZ/Ort pattern on this line or the next
            for check_ln in [line] + ([lines[i + 1]] if i + 1 < len(lines) else []):
                m_plz = re.search(r'PLZ/Ort:\s*([A-Z]{1,2})-(\d+)', check_ln, re.I)
                if m_plz:
                    cur['empf_land'] = _COUNTRY_NORM.get(m_plz.group(1), m_plz.group(1))
                    cur['empf_plz']  = m_plz.group(2)
                    break
            in_empf = False

        # ── Gewicht block ─────────────────────────────────────────────────
        if line == 'Gewicht':
            in_gewicht = True
            i += 1
            continue

        if in_gewicht and cur['kg_rechnung'] is None:
            if re.match(r'^:\s*kg', line, re.I):
                # Value on next line
                if i + 1 < len(lines):
                    m_num = re.match(r'^(\d+)', lines[i + 1])
                    if m_num:
                        cur['kg_rechnung'] = float(m_num.group(1))
                        i += 1
            elif re.match(r'^:\s*\d', line):
                m_num = re.match(r'^:\s*(\d+)', line)
                if m_num:
                    cur['kg_rechnung'] = float(m_num.group(1))
            in_gewicht = False

        i += 1

    if cur and cur['_items']:
        positions.append(cur)
    return positions


# ── Alle PDFs eines Verzeichnisses parsen ─────────────────────────────────
# Keywords that identify non-invoice documents or third-party billing formats.
# PDFs matching ANY of these are explicitly skipped (not counted as parse failures).
_EXPLICIT_SKIP_KW = (
    'B O R D E R O',            # Bordero-Belastung (billed to freight partner)
    'A-META-ABRECHNUNG',        # A-META Abrechnung (old ERKA billing system)
    'A-META-Abrechnung',        # case variant
    'Stornobeleg',              # cancellation note
    'S T O R N O B E L E G',
    'VERBRINGUNGSNACHWEIS',     # customs export declaration — no invoice amounts
    'Umsatzsteuerzwecke',       # VAT-exemption certificate (Spediteurbescheinigung)
    'Bord#',                    # columnar GUTSCHRIFT to freight partner (TRANSDANUBIA etc.)
)


def parse_directory(pdf_dir: str | Path, verbose: bool = True) -> pd.DataFrame:
    pdfs = sorted(glob.glob(str(Path(pdf_dir) / '*.pdf')))
    if verbose:
        print(f'Parsing {len(pdfs)} PDFs from {pdf_dir} …')

    rows             = []
    skipped_explicit = 0   # known non-parseable formats (explicit skip)
    skipped_unknown  = 0   # could not parse with any parser
    for path in pdfs:
        positions = parse_one(path)
        if positions:
            for pos in positions:
                rows.append(flatten(pos))
            continue

        # Fallback: read full text once for classification
        doc       = fitz.open(path)
        full_text = ''.join(p.get_text('text') for p in doc)
        doc.close()

        # Explicit skips: third-party billing formats (no sendungs_nr for this customer)
        if any(kw in full_text for kw in _EXPLICIT_SKIP_KW):
            skipped_explicit += 1
            continue

        # Parser B / C2: Referenz-Erka body (Gutschrift, Redebit, misc)
        if 'Referenz-Erka:' in full_text:
            is_credit = any(kw in full_text for kw in
                            ('RECHNUNGSKORREKTUR', 'GUTSCHRIFT', 'CREDIT NOTE'))
            positions = parse_redebit_body(path, is_credit=is_credit)
            if positions:
                for pos in positions:
                    rows.append(flatten(pos))
                continue

        # Parser C1: Differenzrechnung
        if 'Differenzrechnung' in full_text:
            positions = parse_differenz(path)
            if positions:
                for pos in positions:
                    rows.append(flatten(pos))
                continue

        skipped_unknown += 1

    if verbose:
        parsed_pdfs = len(pdfs) - skipped_explicit - skipped_unknown
        print(f'  → {len(rows)} Positionen aus {parsed_pdfs} PDFs '
              f'({skipped_explicit} explizit übersprungen, '
              f'{skipped_unknown} unbekannte Formate)')

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    # Typen
    df['rechnung_nr']  = df['rechnung_nr'].astype(str)
    df['sendungs_nr']  = df['sendungs_nr'].astype(str)
    df['ldm']          = pd.to_numeric(df['ldm'],          errors='coerce')
    df['kg_rechnung']  = pd.to_numeric(df['kg_rechnung'],  errors='coerce')
    df['stellplaetze'] = pd.to_numeric(df['stellplaetze'], errors='coerce')
    df['volumen']      = pd.to_numeric(df['volumen'],      errors='coerce')
    df['gesamtbetrag'] = pd.to_numeric(df['gesamtbetrag'], errors='coerce')
    return df


# ── Vergleichstabelle bauen ────────────────────────────────────────────────
DINAS_CATS = ['fracht', 'diesel', 'maut_ssd', 'ausfuhr', 'verzollung',
              'zoll_duty', 'zoll_betrag', 'sulphur', 'neben_pausch',
              'redebit', 'sonstige']

AX_COLS = {
    'ax_fracht'       : 'Erlöse Fracht',
    'ax_diesel'       : 'Erlöse Diesel',
    'ax_maut'         : 'Erlöse Maut',
    'ax_nebengebühr'  : 'Erlöse Nebengebühr',
    'ax_lademittel'   : 'Erlöse Lademittel',
    'ax_peak'         : 'Erlöse Peak',
    'ax_eust_zoll'    : 'Erlöse EUST Zoll',
    'ax_versicherung' : 'Erlöse Transportversicherung',
    'ax_gesamt'       : 'Erloese',
}


def build_comparison(bi_df: pd.DataFrame,
                     dinas_df: pd.DataFrame,
                     knr: int | str,
                     soll_col: str = 'soll_fracht') -> pd.DataFrame:
    """
    Baut Vergleichstabelle für einen Kunden.

    Join-Schlüssel: Rechnungsnummer (BI) ↔ rechnung_nr (Dinas)

    Spalten im Output:
      [BI-Metadaten] | soll_fracht | dinas_fracht | dinas_diesel | …
      dinas_gesamt | ax_fracht | ax_diesel | … | ax_gesamt
      | delta_fracht | delta_gesamt
    """
    knr_str = str(knr)
    bi = bi_df[bi_df['Kunden Nr BK'] == knr_str].copy()
    bi = bi[bi['periode'] == 'POST'].copy()  # nur AX-POST-Zeilen vergleichbar

    # Rechnungsnummer normalisieren: führende Nullen weg, Zahl-String
    bi['_rn_norm'] = (
        bi['Rechnungsnummer'].astype(str).str.strip()
        .str.lstrip('0').str.replace(r'\D', '', regex=True)
    )
    dinas = dinas_df.copy()
    dinas['_rn_norm'] = (
        dinas['rechnung_nr'].astype(str).str.strip()
        .str.lstrip('0')
    )

    merged = bi.merge(
        dinas[['_rn_norm', 'sendungs_nr', 'leistungsdatum', 'empf_land',
               'empf_plz', 'ldm', 'kg_rechnung'] + DINAS_CATS + ['gesamtbetrag']],
        on='_rn_norm',
        how='left',
        suffixes=('', '_dinas'),
    )
    merged.drop(columns=['_rn_norm'], inplace=True, errors='ignore')

    # AX-NK-Spalten umbenennen
    for new_col, src_col in AX_COLS.items():
        if src_col in merged.columns:
            merged[new_col] = pd.to_numeric(merged[src_col], errors='coerce')
        else:
            merged[new_col] = np.nan

    # Deltas
    merged['delta_fracht']  = merged['ax_fracht'] - merged.get(soll_col, np.nan)
    merged['delta_gesamt']  = merged['ax_gesamt']  - merged['fracht']   # AX-Total vs Dinas-Fracht

    return merged


# ══════════════════════════════════════════════════════════════════════════
# Pilot-Modus: zeigt die extrahierte Struktur für 10 HERMA-PDFs
# ══════════════════════════════════════════════════════════════════════════
if __name__ == '__main__':
    import sys

    HERMA_PDF_DIR = (BASE / 'data/extracted/v2/Herma/Rechnungen/Rechnungen DINAS')

    # ── Pilot: 10 PDFs ──────────────────────────────────────────────────
    all_pdfs = sorted(glob.glob(str(HERMA_PDF_DIR / '*.pdf')))
    known    = ['RECHNUNG03764345.pdf', 'RECHNUNG03776940.pdf',
                'RECHNUNG03764346.pdf', 'RECHNUNG03764347.pdf']
    others   = [p for p in all_pdfs
                if os.path.basename(p) not in known][15:21]
    pilot    = [str(HERMA_PDF_DIR / fn) for fn in known] + others

    print(f'=== PILOT: {len(pilot)} HERMA Dinas PDFs ===\n')
    rows = []
    for path in pilot:
        fn        = os.path.basename(path)
        positions = parse_one(path)
        if not positions:
            print(f'  {fn}: SKIP (kein Rechnungs-Body)')
            continue
        for pos in positions:
            row = flatten(pos)
            rows.append(row)
            cats_nonzero = {c: round(row[c], 2) for c in DINAS_CATS if row[c] != 0}
            print(f'  {fn}  RN={row["rechnung_nr"]:>10}  '
                  f'Sdg={row.get("sendungs_nr",""):>10}  '
                  f'{row.get("empf_land","  ")}-{row.get("empf_plz",""):8s}  '
                  f'kg={str(row.get("kg_rechnung") or "?"):>6}  '
                  f'{cats_nonzero}  '
                  f'Σ={row["total_items"]:>8.2f}')

    print(f'\n{len(rows)} Positionen extrahiert\n')

    df = pd.DataFrame(rows)
    print('\n=== Kategorien-Übersicht ===')
    print(df[DINAS_CATS + ['total_items', 'gesamtbetrag']].describe().round(2).to_string())

    # ── Vergleich mit existing CSV ───────────────────────────────────────
    old_csv = OUT_DIR / 'herma_dinas_gb_invoices.csv'
    if old_csv.exists():
        old = pd.read_csv(old_csv, sep=';')
        old['_rn'] = old['invoice'].str.extract(r'(\d+)')[0].str.lstrip('0')
        df['_rn']  = df['rechnung_nr'].str.lstrip('0')
        merged_check = df.merge(old[['_rn','fracht','total_shipment']],
                                on='_rn', how='inner',
                                suffixes=('_new','_old'))
        merged_check['diff_fracht'] = (merged_check['fracht_new']
                                       - merged_check['fracht_old']).abs()
        n_match = (merged_check['diff_fracht'] < 0.02).sum()
        print(f'\nAbgleich mit herma_dinas_gb_invoices.csv: '
              f'{n_match}/{len(merged_check)} Fracht-Werte übereinstimmend '
              f'(Toleranz 0,02 EUR)')
