#!/usr/bin/env python3
"""
cluster_vergleich_5vs5.py
=========================
Cluster-basierter Vergleich: Dinas (PRE/alt) vs. AX (POST/neu)

Grundprinzip:
  - Basis = alle Dinas-Sendungen (system='alt') MIT Tarif-Match
  - Pro cluster_key (Kunde|Land|Gewichtsband|Preisbasis) werden
    passende AX-Sendungen (system='neu') gesucht
  - Abweichung = |Erlöse Fracht - soll_fracht| > 1 EUR ODER > 2% relativ
  - Cluster OHNE AX-Abweichung → nicht im Output

Pro Cluster gezeigt:
  - Alle Dinas-Sendungen             (sample_typ='Dinas_Basis')
  - Bis zu 4 AX-Zeilen MIT Abw.     (sample_typ='AX_Abweichung')
  - Bis zu 1 AX-Zeile OHNE Abw.     (sample_typ='AX_Kontrolle')

Daten:    output/bi_top20_data.pkl  +  dlv_tariffs.lookup_tariff_price
Output:   output/cluster_vergleich/{KNR}_{Name}_cluster.xlsx  (pro Kunde)

Usage:
    python src/cluster_vergleich_5vs5.py
"""

import sys
import pickle
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import PatternFill, Font, Alignment
from openpyxl.utils import get_column_letter

warnings.filterwarnings('ignore')

BASE    = Path('/home/user/TMS')
SRC_DIR = BASE / 'src'
OUT_DIR    = BASE / 'output'
OUT_DIR_CL = OUT_DIR / 'cluster_vergleich'
BI_PKL     = OUT_DIR / 'bi_top20_data.pkl'

sys.path.insert(0, str(SRC_DIR))
from dlv_tariffs import lookup_tariff_price  # noqa: E402

# ── Zielkunden ────────────────────────────────────────────────────────────────
CUSTOMERS = {
    423650: 'HERMA GmbH',
    409480: 'Fischerwerke GmbH',
    406035: 'GEZE GmbH',
    410844: 'EBM-Papst Mulfingen',
    486073: 'CHT Germany GmbH',
}

# ── NK-Quellen pro Kunde (KNR-String → Excel-Quelldatei + Sheet) ─────────────
_GEZE_DLV = (
    BASE / 'GEZE Leonberg/2025/'
    '20250305_Geze_Export_incl. MP_ PT_GB_IT_FR_AT_ES_CH_'
    'inkl. Maut und Zusatzkosten IT-00_ERGÄNZT UM DUBLIN.xlsx'
)
_EBM_DLV = (
    BASE / 'EBM-Papst, Mulfingen/'
    '20260227_ebm-papst Mulfingen GmbH  Co. KG 74673 Hollenbach_Export Europa.xlsx'
)
NK_SOURCES: dict[str, dict] = {
    '406035': {'file': _GEZE_DLV,  'sheet': 'Dieselfloater'},
    '410844': {'file': _EBM_DLV,   'sheet': 'Surcharges'},
}

# Glob-Muster für NK-Dateien ohne festen Pfad (nur xlsx, case-sensitive)
_NK_GLOB_PATTERNS: dict[str, list[str]] = {
    '423650': ['**/*Nebenkosten*Herma*.xlsx', '**/*Herma*Nebenkosten*.xlsx',
               '**/*NK*Herma*.xlsx',          '**/*Herma*NK*.xlsx'],
    '486073': ['**/*NK*CHT*.xlsx',            '**/*CHT*NK*.xlsx'],
    '409480': ['**/*NK*Fischer*.xlsx',        '**/*Fischer*NK*.xlsx'],
    # Groz-Beckert (KNR falls später ergänzt)
    'GROZ':   ['**/NK*Groz*.xlsx',            '**/*Groz*NK*.xlsx'],
}

ABS_THRESH = 1.0   # EUR absolute Abweichungsschwelle
N_EACH     = 5     # Zeilen pro System pro Cluster

# ── Ausgabespalten (ÄNDERUNG 3) ───────────────────────────────────────────────
DISPLAY_COLS = [
    'system',
    'Auftragsnummer',
    'Kunden Name',
    'Empfänger Land',
    'Empfänger PLZ',
    'Versender PLZ',
    'weight_band',
    'zone_matched',
    'pricing_basis',
    'Tonnage (eff.)',
    'soll_fracht',
    'nk_fracht',
    'nk_diesel',
    'nk_maut',
    'nk_lademittel',
    'nk_peak',
    'nk_nebengebuehren',
    'nk_eust_zoll',
    'nk_versicherung',
    'nk_summe',
    'Erloese',
    'abweichung_eur',
    'abweichung_pct',
    'abweichung_grund',
]

COL_META = {
    'system':             ('System',       8),
    'Auftragsnummer':     ('Auftrags-Nr', 14),
    'Kunden Name':        ('Kunde',       20),
    'Empfänger Land':     ('Land',         6),
    'Empfänger PLZ':      ('Empf.PLZ',    10),
    'Versender PLZ':      ('Vers.PLZ',     9),
    'weight_band':        ('Gew.band',    12),
    'zone_matched':       ('Zone',        18),
    'pricing_basis':      ('Basis',        8),
    'Tonnage (eff.)':     ('Tonnage kg',  10),
    'soll_fracht':        ('Soll EUR',    10),
    'nk_fracht':          ('Fracht EUR',  10),
    'nk_diesel':          ('Diesel EUR',  10),
    'nk_maut':            ('Maut EUR',     9),
    'nk_lademittel':      ('Lademittel',  10),
    'nk_peak':            ('Peak EUR',     9),
    'nk_nebengebuehren':  ('Neben EUR',   10),
    'nk_eust_zoll':       ('EUST Zoll',   10),
    'nk_versicherung':    ('Versich.',     9),
    'nk_summe':           ('NK Summe',    10),
    'Erloese':            ('Erlöse',      10),
    'abweichung_eur':     ('Abw. EUR',    10),
    'abweichung_pct':     ('Abw. %',       9),
    'abweichung_grund':   ('Abw. Grund',  16),
}

NUM_COLS = {
    'soll_fracht', 'nk_fracht', 'nk_diesel', 'nk_maut', 'nk_lademittel',
    'nk_peak', 'nk_nebengebuehren', 'nk_eust_zoll', 'nk_versicherung',
    'nk_summe', 'Erloese', 'abweichung_eur', 'abweichung_pct', 'Tonnage (eff.)',
}


# ═══════════════════════════════════════════════════════════════════════════════
# 1) Daten laden & anreichern
# ═══════════════════════════════════════════════════════════════════════════════

def build_bi_raw() -> pd.DataFrame:
    """Lädt bi_top20_data.pkl und reichert mit Tarif + Cluster-Spalten an."""
    print('[1] Lade bi_top20_data.pkl …')
    with open(BI_PKL, 'rb') as f:
        d = pickle.load(f)
    df = d['df'].copy()

    # Nur Zielkunden
    knrs_float = [float(k) for k in CUSTOMERS]
    df = df[df['Kunden Nr BK'].isin(knrs_float)].copy()
    print(f'    {len(df):,} Zeilen für 5 Zielkunden')

    # Bereinigung
    for col in ('Empfänger PLZ', 'Versender PLZ', 'Empfänger Land'):
        df[col] = df[col].astype(str).str.strip()
    df['Kunden Nr BK'] = (
        pd.to_numeric(df['Kunden Nr BK'], errors='coerce')
        .astype('Int64').astype(str)
    )

    # HERMA Abrechnungsgewicht: max(Tonnage, LDM*1500, Vol*300)
    df['herma_gewicht'] = pd.concat([
        df['Tonnage (eff.)'],
        df['Lademeter'].mul(1500),
        df['Volumen'].mul(300),
    ], axis=1).max(axis=1)

    # Stellplätze ableiten
    df['Stellplätze_calc'] = np.where(
        df['Stellplätze'].isna() | (df['Stellplätze'] == 0),
        np.ceil(df['Lademeter'] / 0.4),
        df['Stellplätze']
    )

    # Tarifmotor
    print('[2] Berechne soll_fracht (Tarifmotor) …')
    tariff_result = df.apply(lookup_tariff_price, axis=1)
    df['soll_fracht']   = tariff_result['soll_fracht']
    df['pricing_basis'] = tariff_result['pricing_basis']
    df['zone_matched']  = tariff_result['zone_matched']
    n_matched = df['soll_fracht'].notna().sum()
    print(f'    soll_fracht befüllt: {n_matched:,} / {len(df):,}')

    # Cluster-Spalten
    bins = [0, 50, 100, 150, 200, 250, 300, 500, 1000, 2000, 3000, float('inf')]
    labels = [
        'bis 50kg', 'bis 100kg', 'bis 150kg', 'bis 200kg', 'bis 250kg',
        'bis 300kg', 'bis 500kg', 'bis 1000kg', 'bis 2000kg', 'bis 3000kg',
        'über 3000kg',
    ]
    df['weight_band'] = pd.cut(df['Tonnage (eff.)'], bins=bins, labels=labels, right=True)
    df['system'] = df['periode'].map({'PRE': 'alt', 'POST': 'neu'})
    df['cluster_key'] = (
        df['Kunden Nr BK'].astype(str) + '|'
        + df['Versender PLZ'].str[:2] + '|'
        + df['Empfänger Land'].astype(str) + '|'
        + df['Empfänger PLZ'].str[:2] + '|'
        + df['weight_band'].astype(str) + '|'
        + df['pricing_basis'].fillna('unbekannt')
    )

    # ── Dinas-Rechnungsdaten joinen (HERMA GB PRE) ────────────────────────────
    # Join-Key:  BI Rechnungsnummer  ↔  Zahl aus Dinas-Dateiname (RECHNUNG0XXXXXXX.pdf)
    # Sekundär:  BI Empfänger-PLZ (erstes Token) ↔  Dinas postcode-Spalte
    # Columns:   fracht→nk_fracht, diesel→nk_diesel, lsz→nk_maut,
    #            ausfuhr→nk_eust_zoll, ssd→nk_nebengebuehren, total_shipment→nk_erloes_dinas
    _DINAS_FP = OUT_DIR / 'herma_dinas_gb_invoices.csv'
    for _c in ['nk_fracht', 'nk_diesel', 'nk_maut', 'nk_eust_zoll', 'nk_nebengebuehren',
               'nk_lademittel', 'nk_peak', 'nk_versicherung', 'nk_summe', 'nk_erloes_dinas']:
        df[_c] = np.nan

    if _DINAS_FP.exists():
        _dinas = pd.read_csv(_DINAS_FP, sep=';')
        # Rechnungsnummer aus Dateiname extrahieren: 'RECHNUNG03764345.pdf' → '03764345'
        _dinas['_rn']      = _dinas['invoice'].str.extract(r'(\d+)', expand=False)
        _dinas['_plz_key'] = _dinas['postcode'].astype(str).str.strip()
        # Pro (Rechnung, PLZ) aggregieren → kein kartesisches Produkt beim Join
        _dinas_agg = (
            _dinas
            .groupby(['_rn', '_plz_key'], as_index=False)
            [['fracht', 'diesel', 'lsz', 'ausfuhr', 'ssd', 'total_shipment']]
            .sum()
        )
        # BI-Seite normalisieren
        _pre_mask = df['periode'] == 'PRE'
        df['_rn']      = df['Rechnungsnummer'].astype(str).str.strip()
        df['_plz_key'] = df['Empfänger PLZ'].str.strip().str.split().str[0]
        # Left-join nur auf PRE-Zeilen
        _df_pre  = df[_pre_mask].copy()
        _merged  = _df_pre.merge(_dinas_agg,
                                  left_on=['_rn', '_plz_key'],
                                  right_on=['_rn', '_plz_key'],
                                  how='left')
        # Werte zurückschreiben (gleiche Länge dank left-join auf aggregiertem rechts)
        df.loc[_pre_mask, 'nk_fracht']         = _merged['fracht'].values
        df.loc[_pre_mask, 'nk_diesel']         = _merged['diesel'].values
        df.loc[_pre_mask, 'nk_maut']           = _merged['lsz'].values
        df.loc[_pre_mask, 'nk_eust_zoll']      = _merged['ausfuhr'].values
        df.loc[_pre_mask, 'nk_nebengebuehren'] = _merged['ssd'].values
        df.loc[_pre_mask, 'nk_erloes_dinas']   = _merged['total_shipment'].values
        _n_filled = int(df.loc[_pre_mask, 'nk_fracht'].notna().sum())
        print(f'    [Dinas] {_n_filled} PRE-Zeilen mit Dinas-IST-Kosten befüllt '
              f'(von {int(_pre_mask.sum())} PRE gesamt)')
        # Test-Ausgabe: 5 befüllte PRE-Zeilen
        _sample = df[_pre_mask & df['nk_fracht'].notna()][
            ['Rechnungsnummer', 'Auftragsnummer', 'Empfänger PLZ', 'Empfänger Land',
             'Tonnage (eff.)', 'nk_fracht', 'nk_diesel', 'nk_maut',
             'nk_eust_zoll', 'nk_nebengebuehren', 'nk_erloes_dinas']
        ].head(5)
        print(_sample.to_string(index=False))
        df.drop(columns=['_rn', '_plz_key'], inplace=True)
    else:
        print(f'    [Dinas] Datei nicht gefunden: {_DINAS_FP}')

    # POST: NK-Spalten aus BI-Erlöse-Spalten befüllen
    _post_mask = df['periode'] == 'POST'
    for _src, _dst in [
        ('Erlöse Fracht',                'nk_fracht'),
        ('Erlöse Diesel',                'nk_diesel'),
        ('Erlöse Maut',                  'nk_maut'),
        ('Erlöse Lademittel',            'nk_lademittel'),
        ('Erlöse Peak',                  'nk_peak'),
        ('Erlöse Nebengebühr',           'nk_nebengebuehren'),
        ('Erlöse EUST Zoll',             'nk_eust_zoll'),
        ('Erlöse Transportversicherung', 'nk_versicherung'),
    ]:
        if _src in df.columns:
            df.loc[_post_mask, _dst] = pd.to_numeric(
                df.loc[_post_mask, _src], errors='coerce'
            )

    # nk_summe = Summe aller Komponenten (wo vorhanden)
    _nk_comp = ['nk_fracht', 'nk_diesel', 'nk_maut', 'nk_lademittel',
                'nk_peak', 'nk_nebengebuehren', 'nk_eust_zoll', 'nk_versicherung']
    df['nk_summe'] = df[[c for c in _nk_comp if c in df.columns]].sum(axis=1, min_count=1)

    # Nur Zeilen mit Tarif-Match
    df = df[df['soll_fracht'].notna()].copy()
    print(f'    {len(df):,} Zeilen mit Tarif-Match')
    return df


# ═══════════════════════════════════════════════════════════════════════════════
# 2) Cluster-Analyse
# ═══════════════════════════════════════════════════════════════════════════════

def _abweichung_grund(row) -> str:
    """Klassifiziert die Abweichungsursache einer Zeile."""
    soll = row.get('soll_fracht')
    if pd.isna(soll) or soll == 0:
        return 'Kein Tarif-Match'
    abw = row.get('abweichung_eur', np.nan)
    if pd.isna(abw) or abs(abw) <= ABS_THRESH:
        return 'OK'
    nk_fr = row.get('nk_fracht', np.nan)
    if pd.notna(nk_fr) and not pd.isna(soll):
        fd = float(nk_fr) - float(soll)
        if abs(fd) > ABS_THRESH:
            return 'Fracht niedriger' if fd < 0 else 'Fracht höher'
    return 'NK-Differenz'


def _cluster_block(pre_rows: pd.DataFrame,
                   post_rows: pd.DataFrame) -> pd.DataFrame | None:
    """
    Baut den Sample-Block für einen cluster_key.
    Gibt None zurück wenn kein POST-Eintrag eine signifikante Abweichung hat.
    POST: top-5 nach |abweichung_eur|; PRE: erste 5.
    """
    # ── POST ──────────────────────────────────────────────────────────────────
    post = post_rows.copy()
    post['abweichung_eur'] = (
        pd.to_numeric(post['Erloese'], errors='coerce') - post['soll_fracht']
    )
    post['abweichung_pct'] = (
        post['abweichung_eur'] / post['soll_fracht'].replace(0, np.nan) * 100
    )

    has_abw = post[post['abweichung_eur'].abs() > ABS_THRESH]
    if has_abw.empty:
        return None  # Kein Ausreißer → Cluster überspringen

    post['_abs_abw'] = post['abweichung_eur'].abs()
    post_sel = (
        post.sort_values('_abs_abw', ascending=False)
        .head(N_EACH)
        .drop(columns='_abs_abw')
        .copy()
    )
    post_sel['sample_typ']      = 'AX_POST'
    post_sel['abweichung_grund'] = post_sel.apply(_abweichung_grund, axis=1)

    # ── PRE ───────────────────────────────────────────────────────────────────
    pre = pre_rows.head(N_EACH).copy()
    _pre_erloes = pd.to_numeric(
        pre.get('nk_erloes_dinas', pd.Series(np.nan, index=pre.index)),
        errors='coerce'
    )
    pre['abweichung_eur'] = _pre_erloes - pre['soll_fracht']
    pre['abweichung_pct'] = (
        pre['abweichung_eur'] / pre['soll_fracht'].replace(0, np.nan) * 100
    )
    pre['sample_typ']      = 'Dinas_PRE'
    pre['abweichung_grund'] = pre.apply(_abweichung_grund, axis=1)

    return pd.concat([pre, post_sel], ignore_index=True)


def analyse(df: pd.DataFrame) -> list[dict]:
    """
    Führt Cluster-Analyse für alle 5 Zielkunden durch.
    Gibt Liste von Dicts zurück: {knr, bi_name, result_df}
    """
    results = []

    for knr, cname in CUSTOMERS.items():
        knr_str = str(knr)
        cdf = df[df['Kunden Nr BK'] == knr_str].copy()

        # BI-Kundenname aus den Daten (Spalte 'Kunden Name')
        bi_name = cdf['Kunden Name'].dropna().iloc[0] if not cdf.empty else cname
        bi_name = str(bi_name).strip()

        if cdf.empty:
            print(f'  {cname}: keine Daten nach Tarif-Match')
            results.append({'knr': knr_str, 'bi_name': bi_name, 'result_df': pd.DataFrame()})
            continue

        pre_df  = cdf[cdf['system'] == 'alt']
        post_df = cdf[cdf['system'] == 'neu']

        pre_keys  = set(pre_df['cluster_key'].unique())
        post_keys = set(post_df['cluster_key'].unique())
        common    = pre_keys & post_keys

        parts = []
        for ck in sorted(common):
            block = _cluster_block(
                pre_df[pre_df['cluster_key'] == ck],
                post_df[post_df['cluster_key'] == ck],
            )
            if block is not None:
                parts.append(block)

        if not parts:
            print(f'  {cname}: keine Cluster mit Abweichung')
            results.append({'knr': knr_str, 'bi_name': bi_name, 'result_df': pd.DataFrame()})
            continue

        result    = pd.concat(parts, ignore_index=True)
        n_ck_abw  = len(parts)
        post_res  = result[result['sample_typ'] == 'AX_POST']
        n_unter   = (post_res['abweichung_eur'] < -ABS_THRESH).sum()
        n_ueber   = (post_res['abweichung_eur'] >  ABS_THRESH).sum()
        total_abw = post_res['abweichung_eur'].sum()
        print(
            f'  {cname}: {len(pre_keys):3d} PRE, {len(post_keys):3d} POST, '
            f'{len(common):3d} gemeinsam → {n_ck_abw:3d} mit Abw. | '
            f'{n_unter} Unter / {n_ueber} Über  Σ {total_abw:+,.2f} EUR'
        )
        results.append({'knr': knr_str, 'bi_name': bi_name, 'result_df': result})

    return results


# ═══════════════════════════════════════════════════════════════════════════════
# 3) Excel-Export
# ═══════════════════════════════════════════════════════════════════════════════

HEADER_FILL  = PatternFill('solid', fgColor='1F3864')
CLUSTER_FILL = PatternFill('solid', fgColor='FFF2CC')
DINAS_FILL   = PatternFill('solid', fgColor='D9E1F2')
ABW_FILL     = PatternFill('solid', fgColor='FCE4D6')
CTRL_FILL    = PatternFill('solid', fgColor='E2EFDA')

WHITE_BOLD = Font(color='FFFFFF', bold=True, size=9)
BOLD_S9    = Font(bold=True, size=9)
PLAIN_S9   = Font(size=9)
CENTER     = Alignment(horizontal='center', vertical='center', wrap_text=True)
LEFT       = Alignment(horizontal='left',   vertical='center', wrap_text=False)

TYP_ORDER = {'Dinas_PRE': 0, 'AX_POST': 1}
TYP_FILL  = {'Dinas_PRE': DINAS_FILL, 'AX_POST': ABW_FILL}


def _write_sheet(ws, df: pd.DataFrame, avail: list[str]) -> None:
    ws.freeze_panes = 'A2'

    # Header-Zeile
    for ci, col in enumerate(avail, 1):
        label, width = COL_META[col]
        cell = ws.cell(row=1, column=ci, value=label)
        cell.fill      = HEADER_FILL
        cell.font      = WHITE_BOLD
        cell.alignment = CENTER
        ws.column_dimensions[get_column_letter(ci)].width = width

    if df.empty:
        ws.cell(row=2, column=1, value='Keine Cluster mit Abweichung gefunden.')
        return

    # Zeilen sortieren: cluster_key, dann Typ-Reihenfolge
    df = df.copy()
    df['_ord'] = df['sample_typ'].map(TYP_ORDER).fillna(9)
    df = df.sort_values(['cluster_key', '_ord']).drop(columns='_ord')

    prev_ck = None
    row_num = 2
    for _, rec in df.iterrows():
        ck = rec.get('cluster_key', '')

        # Cluster-Trennzeile
        if ck != prev_ck:
            cell = ws.cell(row=row_num, column=1, value=f'▶ {ck}')
            cell.fill      = CLUSTER_FILL
            cell.font      = BOLD_S9
            cell.alignment = LEFT
            ws.merge_cells(
                start_row=row_num, start_column=1,
                end_row=row_num, end_column=len(avail)
            )
            row_num += 1
            prev_ck = ck

        styp = rec.get('sample_typ', '')
        fill = TYP_FILL.get(styp, DINAS_FILL)

        for ci, col in enumerate(avail, 1):
            v = rec.get(col, '')
            if pd.isna(v):
                v = ''
            cell = ws.cell(row=row_num, column=ci, value=v)
            cell.fill      = fill
            cell.font      = PLAIN_S9
            cell.alignment = LEFT
            if col in NUM_COLS:
                cell.number_format = '#,##0.00'

        row_num += 1


def _safe_name(s: str) -> str:
    """Bereinigt einen String für Dateinamen (ersetzt Leerzeichen/Sonderzeichen)."""
    import re
    return re.sub(r'[^\w\-]', '_', s).strip('_')


def _append_nk_sheet(wb: Workbook, knr: str) -> None:
    """Hängt NK_Konditionen-Sheet an wb an.

    Strategie:
    1. NK_SOURCES: fester Pfad + Sheet-Name (GEZE, EBM)
    2. _NK_GLOB_PATTERNS: Suche per glob im Projektverzeichnis (xlsx only)
    Falls nichts gefunden: Sheet wird übersprungen.
    """
    # ── 1) Fester Pfad ────────────────────────────────────────────────────────
    src = NK_SOURCES.get(knr)
    if src is not None:
        fp, sname = src['file'], src['sheet']
        if not fp.exists():
            print(f'    [NK] Datei nicht gefunden: {fp.name}')
            return
        try:
            nk_df = pd.read_excel(fp, sheet_name=sname, header=None)
            ws = wb.create_sheet(title='NK_Konditionen')
            for r_idx, row in enumerate(nk_df.values, 1):
                for c_idx, val in enumerate(row, 1):
                    if pd.notna(val):
                        ws.cell(row=r_idx, column=c_idx, value=val)
            print(f'    [NK] Sheet "{sname}" aus {fp.name} eingefügt ({nk_df.shape[0]} Zeilen)')
        except Exception as e:
            print(f'    [NK] Fehler beim Lesen von {fp.name}: {e}')
        return

    # ── 2) Glob-Suche ─────────────────────────────────────────────────────────
    pats = _NK_GLOB_PATTERNS.get(knr, [])
    nk_fp: Path | None = None
    for pat in pats:
        hits = [p for p in BASE.glob(pat) if not p.name.startswith('~')]
        if hits:
            nk_fp = hits[0]
            break

    if nk_fp is None:
        print(f'    [NK] Keine NK-xlsx für KNR {knr} gefunden — Sheet übersprungen')
        return
    try:
        nk_df = pd.read_excel(nk_fp, header=None)
        ws = wb.create_sheet(title='NK_Konditionen')
        for r_idx, row in enumerate(nk_df.values, 1):
            for c_idx, val in enumerate(row, 1):
                if pd.notna(val):
                    ws.cell(row=r_idx, column=c_idx, value=val)
        print(f'    [NK] {nk_fp.name} eingefügt ({nk_df.shape[0]} Zeilen)')
    except Exception as e:
        print(f'    [NK] Fehler beim Lesen von {nk_fp.name}: {e}')


def write_excel(results: list[dict]) -> None:
    OUT_DIR_CL.mkdir(parents=True, exist_ok=True)
    avail = [c for c in DISPLAY_COLS if c in COL_META]

    for entry in results:
        knr     = entry['knr']
        df      = entry['result_df']

        # Name aus BI-Daten ('Name' bevorzugt, Fallback 'Kunden Name', dann CUSTOMERS-Dict)
        bi_name = entry['bi_name']
        if not df.empty:
            for _nc in ('Name', 'Kunden Name'):
                if _nc in df.columns:
                    _vals = df[_nc].dropna().unique()
                    if len(_vals) > 0:
                        bi_name = str(_vals[0]).strip()
                        break

        fname   = f"{knr}_{_safe_name(bi_name)}_cluster.xlsx"
        fpath   = OUT_DIR_CL / fname

        wb = Workbook()
        ws = wb.active
        ws.title = bi_name[:31]
        _write_sheet(ws, df, avail)
        _append_nk_sheet(wb, knr)
        wb.save(fpath)
        print(f'  → {fpath}')


# ═══════════════════════════════════════════════════════════════════════════════
# main
# ═══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    df = build_bi_raw()

    print('\n[3] Cluster-Analyse …')
    results = analyse(df)

    print('\n[4] Excel schreiben …')
    write_excel(results)

    # Zusammenfassung
    print('\n' + '=' * 72)
    print('  ZUSAMMENFASSUNG CLUSTER-VERGLEICH')
    print('=' * 72)
    total_rows = 0
    total_eur  = 0.0
    for entry in results:
        cname  = entry['bi_name']
        res_df = entry['result_df']
        if res_df.empty:
            print(f'  {cname:<30s}  — keine Abweichungen')
            continue
        post_df = res_df[res_df['sample_typ'] == 'AX_POST']
        n_ck    = post_df['cluster_key'].nunique()
        n_unter = (post_df['abweichung_eur'] < -ABS_THRESH).sum()
        n_ueber = (post_df['abweichung_eur'] >  ABS_THRESH).sum()
        summe   = post_df['abweichung_eur'].sum()
        total_rows += len(post_df)
        total_eur  += summe
        print(
            f'  {cname:<30s}  {n_ck:3d} Cluster  '
            f'Unter: {n_unter:3d}  Über: {n_ueber:3d}  '
            f'Σ {summe:+10,.2f} EUR'
        )
    print('-' * 72)
    print(f'  {"GESAMT":<30s}  {total_rows:4d} AX-POST-Rows  Σ {total_eur:+10,.2f} EUR')
    print('=' * 72)


if __name__ == '__main__':
    main()
