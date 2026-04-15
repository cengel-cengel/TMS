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
Output:   output/cluster_vergleich_5vs5.xlsx  (ein Sheet pro Kunde)

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
OUT_DIR = BASE / 'output'
BI_PKL  = OUT_DIR / 'bi_top20_data.pkl'
OUT_XL  = OUT_DIR / 'cluster_vergleich_5vs5.xlsx'

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

ABS_THRESH = 1.0   # EUR absolute Abweichungsschwelle
REL_THRESH = 2.0   # % relative Abweichungsschwelle
N_ABW      = 4     # max AX-Zeilen MIT Abweichung pro Cluster
N_CTRL     = 1     # max AX-Zeilen OHNE Abweichung pro Cluster (Kontrollgruppe)

# ── Ausgabespalten ────────────────────────────────────────────────────────────
DISPLAY_COLS = [
    'sample_typ',
    'cluster_key',
    'system',
    'Ausgangsbordero',
    'Rechnungsnummer',
    'Kunden Name',
    'Kunden Nr BK',
    'Versender Name',
    'Versender PLZ',
    'Empfänger Name',
    'Empfänger PLZ',
    'Empfänger Land',
    'Tonnage (eff.)',
    'Lademeter',
    'Stellplätze_calc',
    'weight_band',
    'pricing_basis',
    'soll_fracht',
    'Erlöse Fracht',
    'abweichung_eur',
    'abweichung_pct',
    'periode',
]

COL_META = {
    'sample_typ':       ('Typ',         14),
    'cluster_key':      ('Cluster Key', 42),
    'system':           ('System',       8),
    'Ausgangsbordero':  ('Bordero',     12),
    'Rechnungsnummer':  ('Rech-Nr',     13),
    'Kunden Name':      ('Kunde',       20),
    'Kunden Nr BK':     ('KNR',          8),
    'Versender Name':   ('Versender',   22),
    'Versender PLZ':    ('Vers.PLZ',     9),
    'Empfänger Name':   ('Empfänger',   22),
    'Empfänger PLZ':    ('Empf.PLZ',    10),
    'Empfänger Land':   ('Land',         6),
    'Tonnage (eff.)':   ('Tonnage kg',  10),
    'Lademeter':        ('LDM',          8),
    'Stellplätze_calc': ('Stpl',         6),
    'weight_band':      ('Gew.band',    12),
    'pricing_basis':    ('Basis',        8),
    'soll_fracht':      ('Soll EUR',    10),
    'Erlöse Fracht':    ('Ist EUR',     10),
    'abweichung_eur':   ('Abw. EUR',    10),
    'abweichung_pct':   ('Abw. %',       9),
    'periode':          ('Periode',      9),
}

NUM_COLS = {'soll_fracht', 'Erlöse Fracht', 'abweichung_eur',
            'abweichung_pct', 'Tonnage (eff.)', 'Lademeter', 'Stellplätze_calc'}


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
        + df['Empfänger Land'].astype(str) + '|'
        + df['weight_band'].astype(str) + '|'
        + df['pricing_basis'].fillna('unbekannt')
    )

    # Nur Zeilen mit Tarif-Match
    df = df[df['soll_fracht'].notna()].copy()
    print(f'    {len(df):,} Zeilen mit Tarif-Match')
    return df


# ═══════════════════════════════════════════════════════════════════════════════
# 2) Cluster-Analyse
# ═══════════════════════════════════════════════════════════════════════════════

def _has_abweichung(ist: float, soll: float) -> bool:
    """True wenn Abweichung > Schwellwert (absolut ODER relativ)."""
    if pd.isna(ist) or pd.isna(soll) or soll == 0:
        return False
    diff = abs(ist - soll)
    pct  = diff / abs(soll) * 100
    return diff > ABS_THRESH or pct > REL_THRESH


def _cluster_block(pre_rows: pd.DataFrame,
                   post_rows: pd.DataFrame) -> pd.DataFrame | None:
    """
    Baut den Sample-Block für einen cluster_key.
    Gibt None zurück wenn keine AX-Sendung mit Abweichung existiert.
    """
    post = post_rows.copy()
    post['abweichung_eur'] = post['Erlöse Fracht'] - post['soll_fracht']
    post['abweichung_pct'] = (
        post['abweichung_eur'] / post['soll_fracht'].replace(0, np.nan) * 100
    )

    mask_abw = post.apply(
        lambda r: _has_abweichung(r['Erlöse Fracht'], r['soll_fracht']), axis=1
    )
    ax_abw  = post[mask_abw].copy()
    ax_ctrl = post[~mask_abw].copy()

    if ax_abw.empty:
        return None  # Cluster überspringen

    # PRE: alle Dinas-Zeilen
    pre = pre_rows.copy()
    pre['abweichung_eur'] = pre['Erlöse Fracht'] - pre['soll_fracht']
    pre['abweichung_pct'] = (
        pre['abweichung_eur'] / pre['soll_fracht'].replace(0, np.nan) * 100
    )
    pre['sample_typ'] = 'Dinas_Basis'

    # AX mit Abweichung: größte Abw. zuerst, max N_ABW Zeilen
    ax_abw['sample_typ'] = 'AX_Abweichung'
    ax_abw = ax_abw.loc[
        ax_abw['abweichung_eur'].abs().sort_values(ascending=False).index
    ].head(N_ABW)

    # AX Kontrolle: max N_CTRL Zeilen ohne Abweichung
    ax_ctrl['sample_typ'] = 'AX_Kontrolle'
    ax_ctrl = ax_ctrl.head(N_CTRL)

    return pd.concat([pre, ax_abw, ax_ctrl], ignore_index=True)


def analyse(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Führt Cluster-Analyse für alle 5 Zielkunden durch."""
    results: dict[str, pd.DataFrame] = {}

    for knr, cname in CUSTOMERS.items():
        knr_str = str(knr)
        cdf = df[df['Kunden Nr BK'] == knr_str].copy()
        if cdf.empty:
            print(f'  {cname}: keine Daten nach Tarif-Match')
            results[cname] = pd.DataFrame()
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
            results[cname] = pd.DataFrame()
            continue

        result    = pd.concat(parts, ignore_index=True)
        n_ck_abw  = len(parts)
        n_ax_abw  = (result['sample_typ'] == 'AX_Abweichung').sum()
        total_abw = result.loc[
            result['sample_typ'] == 'AX_Abweichung', 'abweichung_eur'
        ].sum()
        print(
            f'  {cname}: {len(pre_keys):3d} PRE-Cluster, {len(post_keys):3d} POST-Cluster, '
            f'{len(common):3d} gemeinsam → {n_ck_abw:3d} mit Abw. | '
            f'{n_ax_abw:4d} AX_Abw-Rows  Σ {total_abw:+,.2f} EUR'
        )
        results[cname] = result

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

TYP_ORDER = {'Dinas_Basis': 0, 'AX_Abweichung': 1, 'AX_Kontrolle': 2}
TYP_FILL  = {'Dinas_Basis': DINAS_FILL, 'AX_Abweichung': ABW_FILL, 'AX_Kontrolle': CTRL_FILL}


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


def write_excel(results: dict[str, pd.DataFrame]) -> None:
    wb = Workbook()
    wb.remove(wb.active)

    avail = [c for c in DISPLAY_COLS if c in COL_META]

    for cname, df in results.items():
        ws = wb.create_sheet(title=cname[:31])
        _write_sheet(ws, df, avail)

    wb.save(OUT_XL)
    print(f'\n[Excel] gespeichert: {OUT_XL}')


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
    print('\n' + '=' * 70)
    print('  ZUSAMMENFASSUNG CLUSTER-VERGLEICH')
    print('=' * 70)
    total_rows = 0
    total_eur  = 0.0
    for cname, res_df in results.items():
        if res_df.empty:
            print(f'  {cname:<30s}  — keine Abweichungen')
            continue
        n_abw  = (res_df['sample_typ'] == 'AX_Abweichung').sum()
        n_ck   = res_df.loc[res_df['sample_typ'] == 'AX_Abweichung', 'cluster_key'].nunique()
        summe  = res_df.loc[res_df['sample_typ'] == 'AX_Abweichung', 'abweichung_eur'].sum()
        total_rows += n_abw
        total_eur  += summe
        print(
            f'  {cname:<30s}  {n_ck:3d} Cluster  '
            f'{n_abw:4d} AX-Abw-Rows  Σ {summe:+10,.2f} EUR'
        )
    print('-' * 70)
    print(
        f'  {"GESAMT":<30s}  '
        f'{total_rows:4d} AX-Abw-Rows  Σ {total_eur:+10,.2f} EUR'
    )
    print('=' * 70)


if __name__ == '__main__':
    main()
