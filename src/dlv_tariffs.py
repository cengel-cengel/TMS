import pandas as pd
import numpy as np
from pathlib import Path

TARIFF_CACHE = {}

def get_tariff(knr: str) -> pd.DataFrame:
    if knr in TARIFF_CACHE:
        return TARIFF_CACHE[knr]
    loader = LOADERS.get(knr)
    if loader is None:
        return pd.DataFrame()
    result = loader()
    TARIFF_CACHE[knr] = result
    return result

LOADERS = {}

def load_herma():
    """Lädt HERMA Tarifdaten (KNR 423650). Abrechnungsbasis: max(Tonnage, LDM*1500, Vol*300), Preis pro Sendung."""
    # Finde den tatsächlichen Pfad zur Herma-Frachtraten-Datei im Projekt
    # Erwarteter Pfad enthält: Herma, Frachtraten, 2026-2028
    # Sheets: AT, CH, EE, ES, FR, GB, IRL, IT, PT, RS/MK/BA

    filepath = Path('/home/user/TMS/Herma/Herma Konditionen/Herma Konditionen/Herma Etiketten/2026/20251212_Herma_Frachtraten mit VL_2026-2028_NT.xlsx')
    if not filepath.exists():
        # Fallback: rglob-Suche
        for p in Path('/home/user/TMS').rglob('*Herma*Frachtraten*'):
            if p.suffix == '.xlsx':
                filepath = p
                break
        else:
            print("HERMA Tarifdatei nicht gefunden")
            return pd.DataFrame()

    print(f"HERMA Tarifdatei: {filepath}")
    sheets = ['AT','CH','EE','ES','FR','GB','IRL','IT','PT']
    all_rows = []

    for sheet in sheets:
        try:
            raw = pd.read_excel(filepath, sheet_name=sheet)
            # Gewichtsspalten identifizieren (enthalten "kg" oder "bis")
            weight_cols = [c for c in raw.columns if any(kw in str(c).lower() for kw in ['kg', 'bis'])]
            id_cols = [c for c in raw.columns if c not in weight_cols]

            if not weight_cols:
                print(f"  {sheet}: keine Gewichtsspalten gefunden, übersprungen")
                continue

            melted = raw.melt(id_vars=id_cols, value_vars=weight_cols, var_name='weight_band_raw', value_name='price')
            melted['country'] = sheet
            melted['pricing_basis'] = 'EUR/Sendung'
            melted['knr'] = '423650'
            all_rows.append(melted)
            print(f"  {sheet}: {len(melted)} Zeilen geladen")
        except Exception as e:
            print(f"  {sheet}: Fehler - {e}")

    result = pd.concat(all_rows, ignore_index=True) if all_rows else pd.DataFrame()
    print(f"HERMA gesamt: {len(result)} Tarifzeilen")
    return result

def load_geze():
    """Lädt GEZE Tarifdaten (KNR 406035). Abrechnungsbasis: EUR/100kg. Sheet: Exporttarife.
    Struktur: col A=Zone, col B=PLZ (2-st), col C=Minimum (€/Sendung), col D-I=Gewichtsstufen bis 300/500/1000/1500/2000/2500-3000 kg."""

    filepath = Path('/home/user/TMS/GEZE Leonberg/2025/20250305_Geze_Export_incl. MP_ PT_GB_IT_FR_AT_ES_CH_inkl. Maut und Zusatzkosten IT-00_ERGÄNZT UM DUBLIN.xlsx')
    if not filepath.exists():
        # Fallback: rglob-Suche
        for p in Path('/home/user/TMS').rglob('*Geze*Export*'):
            if p.suffix == '.xlsx':
                filepath = p
                break
        else:
            print("GEZE Tarifdatei nicht gefunden")
            return pd.DataFrame()

    print(f"GEZE Tarifdatei: {filepath}")
    raw = pd.read_excel(filepath, sheet_name='Exporttarife')
    raw.columns = raw.columns.str.strip()

    # Erste 3 Spalten sind Zone, PLZ, Minimum
    first_cols = raw.columns[:3].tolist()
    weight_cols = raw.columns[3:].tolist()

    melted = raw.melt(id_vars=first_cols, value_vars=weight_cols, var_name='weight_band_raw', value_name='price_per_100kg')
    melted['pricing_basis'] = 'EUR/100kg'
    melted['knr'] = '406035'
    melted.rename(columns={first_cols[0]: 'zone', first_cols[1]: 'plz_prefix', first_cols[2]: 'min_price'}, inplace=True)

    print(f"GEZE: {len(melted)} Tarifzeilen geladen")
    return melted

LOADERS['406035'] = load_geze

def load_ebm():
    """Lädt EBM-Papst Tarifdaten (KNR 410844). Abrechnungsbasis: EUR/Stellplatz (LDM-basiert).
    Sheets: Tariffs_DE_EU (Fracht), Toll_DE_EU (Maut), Surcharges (Zuschläge).
    Struktur: Pick-up Location, To EU-Location, Leadtime, dann 1-10 Palletspaces.
    Row 7 enthält LDM-Werte (0.4, 0.8, 1.2, ...). Preise ab Row 9."""

    filepath = Path('/home/user/TMS/EBM-Papst, Mulfingen/20260227_ebm-papst Mulfingen GmbH  Co. KG 74673 Hollenbach_Export Europa.xlsx')
    if not filepath.exists():
        # Fallback: rglob-Suche
        for p in Path('/home/user/TMS').rglob('*ebm-papst*Export*Europa*'):
            if p.suffix == '.xlsx':
                filepath = p
                break
        else:
            print("EBM-Papst Tarifdatei nicht gefunden")
            return pd.DataFrame()

    print(f"EBM-Papst Tarifdatei: {filepath}")

    # Tariffs Sheet lesen - Header ist nicht in Row 0
    raw = pd.read_excel(filepath, sheet_name='Tariffs_DE_EU', header=None)
    print(f"  Tariffs_DE_EU: {raw.shape[0]} rows x {raw.shape[1]} cols")
    print(f"  Row 7 (LDM-Header): {raw.iloc[7].tolist()[:8]}")
    print(f"  Row 9 (erste Preiszeile): {raw.iloc[9].tolist()[:8]}")

    # Toll Sheet
    toll = pd.read_excel(filepath, sheet_name='Toll_DE_EU', header=None)
    print(f"  Toll_DE_EU: {toll.shape[0]} rows x {toll.shape[1]} cols")

    # Surcharges Sheet
    surcharges = pd.read_excel(filepath, sheet_name='Surcharges')
    print(f"  Surcharges: {surcharges.shape[0]} rows, Spalten: {surcharges.columns.tolist()}")

    # Parse Tariffs: iloc[7] = Header mit LDM-Werten, ab iloc[9] = Preisdaten (iloc[8] = 'per shipment')
    ldm_header = raw.iloc[7]  # 0-indexed: row 8 (Pick up Location, To EU-Location, Leadtime, 0.4, 0.8, ...)
    col_names = raw.iloc[7] if raw.iloc[7].notna().any() else ldm_header

    tariff_data = raw.iloc[9:].copy()  # ab row 10 (row 9 = 'per shipment')
    tariff_data.columns = range(len(tariff_data.columns))

    # Erste 3 Spalten = Pick-up, To, Leadtime; Rest = Stellplatz-Preise
    id_cols = [0, 1, 2]
    price_cols = [c for c in tariff_data.columns if c not in id_cols]

    melted = tariff_data.melt(id_vars=id_cols, value_vars=price_cols, var_name='stellplatz_col', value_name='price')
    melted.rename(columns={0: 'pickup', 1: 'destination', 2: 'leadtime'}, inplace=True)
    melted['pricing_basis'] = 'EUR/Stellplatz'
    melted['knr'] = '410844'

    # Stellplatz-Nummer aus Spaltenposition ableiten (col 3=1SP, col 4=2SP, ...)
    melted['stellplaetze'] = melted['stellplatz_col'] - 2

    print(f"EBM-Papst: {len(melted)} Tarifzeilen geladen")
    return melted

LOADERS['410844'] = load_ebm

def load_cht():
    """Lädt CHT Tarifdaten (KNR 486073). EUR/100kg.
    Struktur: Spalte 0 = 'bis'/'Minimum'/'Komplett', Spalte 1 = Gewichtsgrenze,
    Spalten 2-N = Preise pro Zone, letzte Spalte = Einheit.
    Zonenmapping folgt weiter unten (Zeilen mit 'Zone X')."""

    base = Path('/home/user/TMS/CHT/2026')
    if not base.is_dir():
        for p in Path('/home/user/TMS').rglob('CHT'):
            if (p / '2026').is_dir():
                base = p / '2026'
                break
        else:
            print("CHT Verzeichnis nicht gefunden")
            return pd.DataFrame()

    print(f"CHT Verzeichnis: {base}")
    all_rows = []

    for f in sorted(base.glob('*CHT_Export*.xlsx')):
        try:
            raw = pd.read_excel(f, sheet_name=0, header=None)

            # Tarifzeilen: Spalte 0 enthält 'bis'
            tarif_mask = raw[0].astype(str).str.lower().str.contains('bis', na=False)
            tarif_rows = raw[tarif_mask].copy()

            if tarif_rows.empty:
                print(f"  {f.name}: keine 'bis'-Zeilen gefunden")
                continue

            # Minimum-Zeile finden
            min_mask = raw[0].astype(str).str.lower().str.contains('minimum', na=False)
            min_row = raw[min_mask].iloc[0] if min_mask.any() else None

            # Zonenspalten = Spalten 2 bis vorletzte (letzte = Einheit)
            n_cols = raw.shape[1]
            zone_cols = list(range(2, n_cols - 1))

            # Zonenmapping: Zeilen mit 'Zone' in Spalte 0
            zone_mask = raw[0].astype(str).str.lower().str.contains('zone', na=False)
            zone_names = raw[zone_mask][0].tolist() if zone_mask.any() else [f'Zone_{i}' for i in zone_cols]

            for _, row in tarif_rows.iterrows():
                weight_to = row[1]
                for i, zcol in enumerate(zone_cols):
                    price = row[zcol]
                    zone_name = zone_names[i] if i < len(zone_names) else f'Zone_{i}'
                    min_price = min_row[zcol] if min_row is not None else np.nan

                    all_rows.append({
                        'weight_band_raw': f'bis {weight_to} kg',
                        'weight_to': weight_to,
                        'zone': zone_name,
                        'price_per_100kg': price,
                        'min_price': min_price,
                        'source_file': f.name,
                        'pricing_basis': 'EUR/100kg',
                        'knr': '486073'
                    })

            print(f"  {f.name}: {len(tarif_rows)} Gewichtsstufen x {len(zone_cols)} Zonen")
        except Exception as e:
            print(f"  {f.name}: Fehler - {e}")

    result = pd.DataFrame(all_rows) if all_rows else pd.DataFrame()
    print(f"CHT gesamt: {len(result)} Tarifzeilen")
    return result

LOADERS['486073'] = load_cht

def load_fischerwerke():
    """Lädt Fischerwerke Tarifdaten (KNR 409480). Abrechnungsbasis: EUR/Stellplatz, pro Sendung.
    Eine Datei pro Route unter Fischerwerke/DLVs & Tarife/2026/.
    Sheets: Tarifblatt DE-72->XX-YYYY. Spalten: Stellplätze 1-N, Preis pro Sendung."""

    base = Path('/home/user/TMS/Fischerwerke/DLVs & Tarife/2026')
    if not base.is_dir():
        for p in Path('/home/user/TMS').rglob('Fischerwerke'):
            tarif_dir = p / 'DLVs & Tarife' / '2026'
            if tarif_dir.is_dir():
                base = tarif_dir
                break
        else:
            # Alternativ: direkt nach Tarifblatt-Dateien suchen
            for p in Path('/home/user/TMS').rglob('*Fischerwerke*2026*'):
                if p.is_dir():
                    base = p
                    break
            else:
                print("Fischerwerke Verzeichnis nicht gefunden")
                return pd.DataFrame()

    print(f"Fischerwerke Verzeichnis: {base}")
    all_rows = []

    for f in sorted(base.glob('*.xlsx')):
        try:
            raw = pd.read_excel(f, sheet_name=0)

            # Route aus Dateiname extrahieren (z.B. "nach IT-35127 Padua_2026")
            route = f.stem  # Dateiname ohne Extension

            # Stellplatz-Spalten identifizieren (numerische Spalten)
            stellplatz_cols = [c for c in raw.columns if str(c).strip().isdigit() or 'Stellpl' in str(c) or 'platz' in str(c).lower()]

            if not stellplatz_cols:
                # Versuch: alle numerischen Spalten nach den ersten ID-Spalten
                id_cols = raw.columns[:2].tolist()
                stellplatz_cols = raw.columns[2:].tolist()
            else:
                id_cols = [c for c in raw.columns if c not in stellplatz_cols]

            melted = raw.melt(id_vars=id_cols, value_vars=stellplatz_cols, var_name='stellplaetze_raw', value_name='price')
            melted['route'] = route
            melted['pricing_basis'] = 'EUR/Stellplatz'
            melted['knr'] = '409480'
            all_rows.append(melted)
            print(f"  {f.name}: {len(melted)} Zeilen")
        except Exception as e:
            print(f"  {f.name}: Fehler - {e}")

    result = pd.concat(all_rows, ignore_index=True) if all_rows else pd.DataFrame()
    print(f"Fischerwerke gesamt: {len(result)} Tarifzeilen")
    return result

LOADERS['409480'] = load_fischerwerke

LOADERS['423650'] = load_herma

def lookup_tariff_price(row):
    """Berechnet Soll-Frachtpreis für eine Sendung. Dispatch nach Kunden Nr BK."""
    knr = str(int(row['Kunden Nr BK'])) if pd.notna(row['Kunden Nr BK']) else ''
    tariff = get_tariff(knr)

    default = pd.Series({
        'soll_fracht': np.nan,
        'pricing_basis': 'unbekannt',
        'weight_band_matched': '',
        'zone_matched': '',
        'min_price_tariff': np.nan
    })

    if tariff.empty or knr not in LOADERS:
        return default

    try:
        if knr == '423650':
            return _lookup_herma(row, tariff)
        elif knr == '406035':
            return _lookup_geze(row, tariff)
        elif knr == '410844':
            return _lookup_ebm(row, tariff)
        elif knr == '486073':
            return _lookup_cht(row, tariff)
        elif knr == '409480':
            return _lookup_fischer(row, tariff)
        else:
            return default
    except Exception as e:
        return default

# Placeholder-Lookups — werden in den nächsten Prompts implementiert
def _lookup_herma(row, tariff):
    """HERMA: Preis pro Sendung. Abrechnungsgewicht = max(Tonnage, LDM*1500, Vol*300).
    Lookup: Empfänger Land → country, dann PLZ → Zone (je Land unterschiedlich), dann Gewichtsband."""

    country = str(row.get('Empfänger Land', '')).strip()
    plz = str(row.get('Empfänger PLZ', '')).strip()
    gewicht = row.get('herma_gewicht', row.get('Tonnage (eff.)', 0))
    if pd.isna(gewicht) or gewicht <= 0:
        gewicht = row.get('Tonnage (eff.)', 0)

    # Filter auf Land
    t = tariff[tariff['country'] == country]
    if t.empty:
        return pd.Series({'soll_fracht': np.nan, 'pricing_basis': 'EUR/Sendung', 'weight_band_matched': '', 'zone_matched': country, 'min_price_tariff': np.nan})

    # Gewichtsband parsen: "bis 50 kg" → 50, "bis 100 kg" → 100
    t = t.copy()
    t['weight_limit'] = t['weight_band_raw'].str.extract(r'(\d+)').astype(float)
    t = t.dropna(subset=['weight_limit', 'price'])
    t = t[t['price'].apply(lambda x: pd.notna(x) and isinstance(x, (int, float)))]

    if t.empty:
        return pd.Series({'soll_fracht': np.nan, 'pricing_basis': 'EUR/Sendung', 'weight_band_matched': '', 'zone_matched': country, 'min_price_tariff': np.nan})

    # Passendes Gewichtsband: kleinstes weight_limit >= gewicht
    passend = t[t['weight_limit'] >= gewicht]
    if passend.empty:
        # Über höchstem Band → nehme höchstes
        match = t.loc[t['weight_limit'].idxmax()]
    else:
        match = passend.loc[passend['weight_limit'].idxmin()]

    price = float(match['price']) if pd.notna(match['price']) else np.nan
    band = str(match['weight_band_raw'])

    return pd.Series({
        'soll_fracht': price,
        'pricing_basis': 'EUR/Sendung',
        'weight_band_matched': band,
        'zone_matched': country,
        'min_price_tariff': np.nan
    })

def _lookup_geze(row, tariff):
    return pd.Series({'soll_fracht': np.nan, 'pricing_basis': 'EUR/100kg', 'weight_band_matched': '', 'zone_matched': '', 'min_price_tariff': np.nan})

def _lookup_ebm(row, tariff):
    return pd.Series({'soll_fracht': np.nan, 'pricing_basis': 'EUR/Stellplatz', 'weight_band_matched': '', 'zone_matched': '', 'min_price_tariff': np.nan})

def _lookup_cht(row, tariff):
    return pd.Series({'soll_fracht': np.nan, 'pricing_basis': 'EUR/100kg', 'weight_band_matched': '', 'zone_matched': '', 'min_price_tariff': np.nan})

def _lookup_fischer(row, tariff):
    return pd.Series({'soll_fracht': np.nan, 'pricing_basis': 'EUR/Stellplatz', 'weight_band_matched': '', 'zone_matched': '', 'min_price_tariff': np.nan})
