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
DEST_RE  = re.compile(r'^([A-Z]{2})-(\S+)')                    # "GB-LE671 ELLISTOWN"
LDM_RE   = re.compile(r'([\d,]+)\s+ldm\s*=\s*([\d.]+)\s+kg')  # "0,40 ldm = 600 kg"
BETRAG   = 'Betrag'

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

        # ── Empfänger-Land/PLZ "GB-LE671 ELLISTOWN" ──────────────────────
        m_dest = DEST_RE.match(line)
        if m_dest and not cur['empf_land']:
            cur['empf_land'] = m_dest.group(1)
            cur['empf_plz']  = m_dest.group(2).split()[0]
            label_buf = []
            continue

        # ── Gewicht / LDM (kann eine oder zwei Zeilen sein) ───────────────
        m_wt = LDM_RE.match(line)
        if m_wt:
            cur['ldm']         = eur_to_float(m_wt.group(1))
            cur['kg_rechnung'] = float(m_wt.group(2).replace('.', ''))
            label_buf = []
            continue
        # zweizeilig: "0,40 ldm =" auf Zeile i, "600 kg" auf Zeile i+1
        if re.match(r'^[\d,]+\s+ldm\s*=$', line):
            if i + 1 < len(body):
                next_l = body[i + 1]
                m_kg   = re.match(r'^([\d.]+)\s+kg$', next_l)
                if m_kg:
                    cur['ldm']         = eur_to_float(line.split()[0])
                    cur['kg_rechnung'] = float(m_kg.group(1).replace('.', ''))
            label_buf = []
            continue
        if re.match(r'^[\d.]+\s+kg$', line) and cur['ldm'] is not None:
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
    row = {k: v for k, v in pos.items() if k != '_items'}
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


# ── Alle PDFs eines Verzeichnisses parsen ─────────────────────────────────
def parse_directory(pdf_dir: str | Path, verbose: bool = True) -> pd.DataFrame:
    pdfs = sorted(glob.glob(str(Path(pdf_dir) / '*.pdf')))
    if verbose:
        print(f'Parsing {len(pdfs)} PDFs from {pdf_dir} …')

    rows = []
    skipped = 0
    for path in pdfs:
        positions = parse_one(path)
        if not positions:
            skipped += 1
            continue
        for pos in positions:
            rows.append(flatten(pos))

    if verbose:
        print(f'  → {len(rows)} Positionen aus {len(pdfs) - skipped} PDFs '
              f'({skipped} ohne Rechnungs-Body übersprungen)')

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    # Typen
    df['rechnung_nr']  = df['rechnung_nr'].astype(str)
    df['sendungs_nr']  = df['sendungs_nr'].astype(str)
    df['ldm']          = pd.to_numeric(df['ldm'],          errors='coerce')
    df['kg_rechnung']  = pd.to_numeric(df['kg_rechnung'],  errors='coerce')
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
