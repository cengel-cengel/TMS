import re
import math
import pandas as pd
import numpy as np
from pathlib import Path

TARIFF_CACHE = {}
CHT_ZONE_MAPS = {}   # {country_iso: {plz_prefix_int: zone_name}}
HERMA_PT_ZONE_MAP = {}  # {zone_num_int: [(plz_from, plz_to), ...]}

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
    """Lädt HERMA Tarifdaten (KNR 423650). Abrechnungsbasis: max(Tonnage, LDM*1500, Vol*300), Preis pro Sendung.

    Sheets mit Von/Bis/Zone-Struktur (AT, ES, EE) werden vollständig geparst:
      AT, ES : Bezeichnung | Von | Bis | Zone | bis 50 kg | bis 100 kg | ...
      EE     : Bezeichnung | Von PLZ | Zone | bis 50 kg | ...

    Sheets mit abweichender Struktur (CH, FR, GB, IRL, IT, PT) werden übersprungen
    und in einem separaten Schritt implementiert.

    Ergebnis-Spalten: Bezeichnung, Von, Bis, Zone (soweit vorhanden),
                      weight_band_raw, price, country, pricing_basis, knr
    """
    filepath = Path(
        '/home/user/TMS/Herma/Herma Konditionen/Herma Konditionen/'
        'Herma Etiketten/2026/20251212_Herma_Frachtraten mit VL_2026-2028_NT.xlsx'
    )
    if not filepath.exists():
        for p in Path('/home/user/TMS').rglob('*Herma*Frachtraten*'):
            if p.suffix == '.xlsx':
                filepath = p
                break
        else:
            print("HERMA Tarifdatei nicht gefunden")
            return pd.DataFrame()

    print(f"HERMA Tarifdatei: {filepath}")

    # Sheets mit Von/Bis/Zone-Struktur → vollständig geparst
    VON_BIS_ZONE = {'AT', 'ES', 'EE'}
    all_rows = []

    for sheet in ['AT', 'CH', 'EE', 'ES', 'FR', 'GB', 'IRL', 'IT', 'PT']:
        if sheet not in VON_BIS_ZONE:
            print(f"  {sheet}: übersprungen (andere Struktur, folgt)")
            continue
        try:
            raw = pd.read_excel(filepath, sheet_name=sheet, header=None)

            # Schritt 1: Header-Zeile finden
            # Kriterium: enthält Gewichtsspalte 'bis X kg' UND Zone-/Von-Kenner
            header_row_idx = None
            for i in range(min(15, len(raw))):
                vals = [str(v).strip() for v in raw.iloc[i]
                        if str(v).strip() not in ('nan', '')]
                has_wt  = any(re.search(r'bis\s+[\d.,]+\s*kg', v, re.I) for v in vals)
                has_key = any(v.lower() in ('zone', 'von', 'von plz') for v in vals)
                if has_wt and has_key:
                    header_row_idx = i
                    break

            if header_row_idx is None:
                print(f"  {sheet}: keine Header-Zeile gefunden, übersprungen")
                continue

            # Schritt 2: Header setzen, Daten ab nächster Zeile
            raw_hdrs = raw.iloc[header_row_idx].tolist()
            seen: dict[str, int] = {}
            headers = []
            for ci, v in enumerate(raw_hdrs):
                s = str(v).strip() if str(v).strip() not in ('nan', '') else f'_c{ci}'
                if s in seen:
                    seen[s] += 1
                    s = f'{s}_{seen[s]}'
                else:
                    seen[s] = 0
                headers.append(s)

            data = raw.iloc[header_row_idx + 1:].copy()
            data.columns = headers

            # Schritt 3: Gewichtsspalten ('bis X kg')
            weight_cols = [c for c in data.columns
                           if re.match(r'bis\s+[\d.,]+\s*kg', c, re.I)]
            if not weight_cols:
                print(f"  {sheet}: keine Gewichtsspalten, übersprungen")
                continue

            # Schritt 4: ID-Spalten (erste immer 'Bezeichnung' o.ä., plus Von/Bis/Zone)
            KNOWN_IDS = ('Bezeichnung', 'Von', 'Bis', 'Zone', 'Von PLZ')
            id_cols = [c for c in KNOWN_IDS if c in data.columns]
            if not id_cols:
                print(f"  {sheet}: keine ID-Spalten gefunden, übersprungen")
                continue

            # Schritt 5: Nur echte Datenzeilen behalten
            first_id = id_cols[0]
            data = data[
                data[first_id].apply(
                    lambda v: pd.notna(v) and str(v).strip() not in ('', 'nan')
                )
            ].copy()

            # Nur Zeilen mit mindestens einem positiv-numerischen Gewichtspreis
            def _any_price(row):
                for c in weight_cols[:6]:
                    try:
                        if float(str(row[c]).replace(',', '.')) > 0:
                            return True
                    except Exception:
                        pass
                return False

            data = data[data.apply(_any_price, axis=1)]

            if data.empty:
                print(f"  {sheet}: keine Datenzeilen nach Filter, übersprungen")
                continue

            # Schritt 6: Melt → eine Zeile pro (ID-Kombi × Gewichtsband)
            melted = data.melt(
                id_vars=id_cols, value_vars=weight_cols,
                var_name='weight_band_raw', value_name='price'
            )
            melted['country']       = sheet
            melted['pricing_basis'] = 'EUR/Sendung'
            melted['knr']           = '423650'
            melted['price'] = pd.to_numeric(
                melted['price'].astype(str).str.replace(',', '.'), errors='coerce'
            )
            melted = melted[melted['price'].notna() & (melted['price'] > 0)]

            # Numerische Von/Bis/Zone normalisieren
            for col in ('Von', 'Bis', 'Zone'):
                if col in melted.columns:
                    melted[col] = pd.to_numeric(melted[col], errors='coerce')

            all_rows.append(melted)
            print(f"  {sheet}: {len(melted)} Zeilen geladen")

        except Exception as e:
            print(f"  {sheet}: Fehler – {e}")

    # --- Sheets mit 2-stelligem PLZ-Prefix: CH, FR ---
    # Struktur: Bezeichnung | 2-st PLZ (int) | bis 50 kg | ...
    for sheet in ['CH', 'FR']:
        try:
            raw = pd.read_excel(filepath, sheet_name=sheet, header=None)
            header_row_idx = None
            for i in range(min(10, len(raw))):
                vals = [str(v).strip() for v in raw.iloc[i]
                        if str(v).strip() not in ('nan', '')]
                if any(re.search(r'bis\s+[\d.,]+\s*kg', v, re.I) for v in vals):
                    header_row_idx = i; break
            if header_row_idx is None:
                print(f"  {sheet}: keine Header-Zeile, übersprungen"); continue

            seen2: dict[str, int] = {}
            hdrs = []
            for ci, v in enumerate(raw.iloc[header_row_idx]):
                s = str(v).strip() if str(v).strip() not in ('nan', '') else f'_c{ci}'
                if s in seen2:
                    seen2[s] += 1; s = f'{s}_{seen2[s]}'
                else:
                    seen2[s] = 0
                hdrs.append(s)

            data = raw.iloc[header_row_idx + 1:].copy()
            data.columns = hdrs
            data = data[data.iloc[:, 0].astype(str).str.contains('Preis', na=False, case=False)]

            weight_cols = [c for c in data.columns if re.match(r'bis\s+[\d.,]+\s*kg', c, re.I)]
            if not weight_cols:
                print(f"  {sheet}: keine Gewichtsspalten"); continue

            plz_col = hdrs[1]   # immer zweite Spalte: '2-st PLZ'
            id_cols = [hdrs[0], plz_col]

            melted = data.melt(id_vars=id_cols, value_vars=weight_cols,
                               var_name='weight_band_raw', value_name='price')
            melted.rename(columns={plz_col: 'Plz_prefix'}, inplace=True)
            melted['Plz_prefix'] = pd.to_numeric(melted['Plz_prefix'], errors='coerce')
            melted = melted[melted['Plz_prefix'].notna() & (melted['Plz_prefix'] > 0)]
            melted['country']       = sheet
            melted['pricing_basis'] = 'EUR/Sendung'
            melted['knr']           = '423650'
            melted['match_type']    = 'plz_2digit'
            melted['price'] = pd.to_numeric(
                melted['price'].astype(str).str.replace(',', '.'), errors='coerce')
            melted = melted[melted['price'].notna() & (melted['price'] > 0)]
            all_rows.append(melted)
            print(f"  {sheet}: {len(melted)} Zeilen geladen")
        except Exception as e:
            print(f"  {sheet}: Fehler – {e}")

    # --- IT: zwei Abschnitte mit unterschiedlichen Gewichtsbändern ---
    # Struktur: Bezeichung | Plz (range '00-06') | [MM] | bis X kg | ...
    try:
        raw = pd.read_excel(filepath, sheet_name='IT', header=None)
        it_rows = []
        header_indices = []
        for i in range(len(raw)):
            vals = [str(v).strip() for v in raw.iloc[i]
                    if str(v).strip() not in ('nan', '')]
            has_plz = any(v.lower() in ('plz', 'bezeichung', 'bezeichnung') for v in vals)
            has_wt  = any(re.search(r'bis\s+[\d.,]+\s*kg', v, re.I) for v in vals)
            if has_plz and has_wt:
                header_indices.append(i)

        for hi, header_row_idx in enumerate(header_indices):
            next_hi = header_indices[hi + 1] if hi + 1 < len(header_indices) else len(raw)

            seen3: dict[str, int] = {}
            hdrs = []
            for ci, v in enumerate(raw.iloc[header_row_idx]):
                s = str(v).strip() if str(v).strip() not in ('nan', '') else f'_c{ci}'
                if s in seen3:
                    seen3[s] += 1; s = f'{s}_{seen3[s]}'
                else:
                    seen3[s] = 0
                hdrs.append(s)

            data_slice = raw.iloc[header_row_idx + 1: next_hi].copy()
            data_slice.columns = hdrs[:len(data_slice.columns)]
            data_slice = data_slice[
                data_slice.iloc[:, 0].astype(str).str.contains('Preis', na=False, case=False)]

            weight_cols = [c for c in hdrs if re.match(r'bis\s+[\d.,]+\s*kg', c, re.I)
                           and c in data_slice.columns]
            if not weight_cols:
                continue

            plz_col = hdrs[1]   # 'Plz'
            id_cols = [c for c in [hdrs[0], plz_col] if c in data_slice.columns]

            melted = data_slice.melt(id_vars=id_cols, value_vars=weight_cols,
                                     var_name='weight_band_raw', value_name='price')

            def _parse_it_plz(s):
                nums = re.findall(r'\d+', str(s))
                if len(nums) == 1: return int(nums[0]), int(nums[0])
                if len(nums) >= 2:  return int(nums[0]), int(nums[1])
                return None, None

            melted[['Von_int', 'Bis_int']] = melted[plz_col].apply(
                lambda s: pd.Series(_parse_it_plz(s)))
            melted = melted[melted['Von_int'].notna()]
            melted['country']       = 'IT'
            melted['pricing_basis'] = 'EUR/Sendung'
            melted['knr']           = '423650'
            melted['match_type']    = 'plz_2digit_range'
            melted['price'] = pd.to_numeric(
                melted['price'].astype(str).str.replace(',', '.'), errors='coerce')
            melted = melted[melted['price'].notna() & (melted['price'] > 0)]
            it_rows.append(melted)

        if it_rows:
            it_df = pd.concat(it_rows, ignore_index=True)
            all_rows.append(it_df)
            print(f"  IT: {len(it_df)} Zeilen geladen ({len(header_indices)} Abschnitte)")
    except Exception as e:
        import traceback
        print(f"  IT: Fehler – {e}"); traceback.print_exc()

    # --- GB: Bezeichnung | Postcode-Bereiche (kommagetrennt) | bis X kg | ... ---
    try:
        raw = pd.read_excel(filepath, sheet_name='GB', header=None)
        header_row_idx = None
        for i in range(min(10, len(raw))):
            vals = [str(v).strip() for v in raw.iloc[i]
                    if str(v).strip() not in ('nan', '')]
            if any(re.search(r'bis\s+[\d.,]+\s*kg', v, re.I) for v in vals):
                header_row_idx = i; break
        if header_row_idx is not None:
            seen4: dict[str, int] = {}
            hdrs = []
            for ci, v in enumerate(raw.iloc[header_row_idx]):
                s = str(v).strip() if str(v).strip() not in ('nan', '') else f'_c{ci}'
                if s in seen4:
                    seen4[s] += 1; s = f'{s}_{seen4[s]}'
                else:
                    seen4[s] = 0
                hdrs.append(s)
            data = raw.iloc[header_row_idx + 1:].copy()
            data.columns = hdrs
            data = data[data.iloc[:, 0].astype(str).str.contains('Preis', na=False, case=False)]
            weight_cols = [c for c in data.columns if re.match(r'bis\s+[\d.,]+\s*kg', c, re.I)]
            if weight_cols:
                area_col = hdrs[1]   # 'Bis' = area codes string
                id_cols  = [hdrs[0], area_col]
                melted = data.melt(id_vars=id_cols, value_vars=weight_cols,
                                   var_name='weight_band_raw', value_name='price')
                melted.rename(columns={area_col: 'GB_areas'}, inplace=True)
                melted['country']       = 'GB'
                melted['pricing_basis'] = 'EUR/Sendung'
                melted['knr']           = '423650'
                melted['match_type']    = 'gb_area'
                melted['price'] = pd.to_numeric(
                    melted['price'].astype(str).str.replace(',', '.'), errors='coerce')
                melted = melted[melted['price'].notna() & (melted['price'] > 0)]
                all_rows.append(melted)
                print(f"  GB: {len(melted)} Zeilen geladen")
    except Exception as e:
        print(f"  GB: Fehler – {e}")

    # --- IRL (→ 'IE'): Bezeichnung | Zone (county/city) | bis X kg | ... ---
    try:
        raw = pd.read_excel(filepath, sheet_name='IRL', header=None)
        header_row_idx = None
        for i in range(min(10, len(raw))):
            vals = [str(v).strip() for v in raw.iloc[i]
                    if str(v).strip() not in ('nan', '')]
            if any(re.search(r'bis\s+[\d.,]+\s*kg', v, re.I) for v in vals):
                header_row_idx = i; break
        if header_row_idx is not None:
            seen5: dict[str, int] = {}
            hdrs = []
            for ci, v in enumerate(raw.iloc[header_row_idx]):
                s = str(v).strip() if str(v).strip() not in ('nan', '') else f'_c{ci}'
                if s in seen5:
                    seen5[s] += 1; s = f'{s}_{seen5[s]}'
                else:
                    seen5[s] = 0
                hdrs.append(s)
            data = raw.iloc[header_row_idx + 1:].copy()
            data.columns = hdrs
            data = data[data.iloc[:, 0].astype(str).str.contains('Preis', na=False, case=False)]
            weight_cols = [c for c in data.columns if re.match(r'bis\s+[\d.,]+\s*kg', c, re.I)]
            if weight_cols:
                zone_col = hdrs[1]   # 'Zone' = county/city name
                id_cols  = [hdrs[0], zone_col]
                melted = data.melt(id_vars=id_cols, value_vars=weight_cols,
                                   var_name='weight_band_raw', value_name='price')
                melted.rename(columns={zone_col: 'IRL_county'}, inplace=True)
                melted['country']       = 'IE'   # Empfänger Land = 'IE', not 'IRL'
                melted['pricing_basis'] = 'EUR/Sendung'
                melted['knr']           = '423650'
                melted['match_type']    = 'irl_county'
                melted['price'] = pd.to_numeric(
                    melted['price'].astype(str).str.replace(',', '.'), errors='coerce')
                melted = melted[melted['price'].notna() & (melted['price'] > 0)]
                all_rows.append(melted)
                print(f"  IRL (IE): {len(melted)} Zeilen geladen")
    except Exception as e:
        print(f"  IRL: Fehler – {e}")

    # --- PT: Zone 1-5 + PLZ-Bereich-Mapping am Tabellenende ---
    try:
        raw = pd.read_excel(filepath, sheet_name='PT', header=None)
        header_row_idx = None
        for i in range(min(10, len(raw))):
            vals = [str(v).strip() for v in raw.iloc[i]
                    if str(v).strip() not in ('nan', '')]
            if any(re.search(r'bis\s+[\d.,]+\s*kg', v, re.I) for v in vals):
                header_row_idx = i; break
        if header_row_idx is not None:
            seen6: dict[str, int] = {}
            hdrs = []
            for ci, v in enumerate(raw.iloc[header_row_idx]):
                s = str(v).strip() if str(v).strip() not in ('nan', '') else f'_c{ci}'
                if s in seen6:
                    seen6[s] += 1; s = f'{s}_{seen6[s]}'
                else:
                    seen6[s] = 0
                hdrs.append(s)
            data = raw.iloc[header_row_idx + 1:].copy()
            data.columns = hdrs
            price_data = data[
                data.iloc[:, 0].astype(str).str.contains('Preis', na=False, case=False)].copy()
            weight_cols = [c for c in data.columns if re.match(r'bis\s+[\d.,]+\s*kg', c, re.I)]
            if weight_cols:
                zone_col = hdrs[1]   # 'Zone'
                id_cols  = [hdrs[0], zone_col]
                melted = price_data.melt(id_vars=id_cols, value_vars=weight_cols,
                                         var_name='weight_band_raw', value_name='price')
                melted.rename(columns={zone_col: 'PT_zone'}, inplace=True)
                melted['Zone_num'] = melted['PT_zone'].astype(str).str.extract(r'(\d+)')[0].astype(float)
                melted['country']       = 'PT'
                melted['pricing_basis'] = 'EUR/Sendung'
                melted['knr']           = '423650'
                melted['match_type']    = 'pt_zone'
                melted['price'] = pd.to_numeric(
                    melted['price'].astype(str).str.replace(',', '.'), errors='coerce')
                melted = melted[melted['price'].notna() & (melted['price'] > 0)]
                all_rows.append(melted)

            # Zone→PLZ-Bereich Mapping aus den unteren Zeilen
            for _, row in raw.iterrows():
                val0 = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ''
                m = re.match(r'Zone\s*(\d+)', val0)
                if not m:
                    continue
                zn = int(m.group(1))
                ranges = []
                for ci in range(1, len(row)):
                    cell = str(row.iloc[ci]).strip() if pd.notna(row.iloc[ci]) else ''
                    cell = cell.rstrip(';').strip()
                    if not cell or cell == 'nan' or any(k in cell for k in ('Azoren', 'Madiera', 'Madeira')):
                        continue
                    nums = re.findall(r'\d+', cell)
                    if len(nums) == 2:
                        ranges.append((int(nums[0]), int(nums[1])))
                    elif len(nums) == 1:
                        ranges.append((int(nums[0]), int(nums[0])))
                if ranges:
                    HERMA_PT_ZONE_MAP[zn] = ranges
            print(f"  PT: {len(melted) if weight_cols else 0} Zeilen, Zonen-PLZ-Mapping: {sorted(HERMA_PT_ZONE_MAP.keys())}")
    except Exception as e:
        import traceback
        print(f"  PT: Fehler – {e}"); traceback.print_exc()

    result = pd.concat(all_rows, ignore_index=True) if all_rows else pd.DataFrame()
    print(f"HERMA gesamt: {len(result)} Tarifzeilen")
    return result

def load_geze():
    """Lädt GEZE Tarifdaten (KNR 406035). EUR/100kg.
    Sheet Exporttarife hat mehrere Länderblöcke. Jeder Block:
    - Länderüberschrift (z.B. 'Portugal')
    - Header-Zeile: 'ab Werk Leonberg', 'PLZ', 'Minimum', 'bis 300 kg', 'bis 500 kg', ...
    - Datenzeilen: Zone X, PLZ-Range, Minimum-Preis, Preise/100kg"""

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
    raw = pd.read_excel(filepath, sheet_name='Exporttarife', header=None)

    all_rows = []
    current_country = None
    current_headers = None

    for idx, row in raw.iterrows():
        first_cell = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ''

        if 'ab Werk' in first_cell or ('leonberg' in first_cell.lower() if first_cell else False):
            prev_cell = str(raw.iloc[idx - 1, 0]).strip() if idx > 0 and pd.notna(raw.iloc[idx - 1, 0]) else current_country
            if prev_cell and prev_cell not in ['nan', '']:
                current_country = prev_cell

            current_headers = []
            for col_idx in range(3, len(row)):
                val = str(row.iloc[col_idx]).strip() if pd.notna(row.iloc[col_idx]) else ''
                if 'kg' in val.lower() or 'bis' in val.lower():
                    current_headers.append((col_idx, val))
            print(f"  {current_country}: Header mit {len(current_headers)} Gewichtsstufen")
            continue

        if current_headers and first_cell.lower().startswith('zone'):
            zone = first_cell
            plz_range = str(row.iloc[1]).strip() if pd.notna(row.iloc[1]) else ''
            min_price = row.iloc[2] if pd.notna(row.iloc[2]) else np.nan
            try:
                min_price = float(min_price)
            except (ValueError, TypeError):
                min_price = np.nan

            for col_idx, weight_band in current_headers:
                price = row.iloc[col_idx] if col_idx < len(row) and pd.notna(row.iloc[col_idx]) else np.nan
                try:
                    price = float(price)
                except (ValueError, TypeError):
                    continue

                all_rows.append({
                    'zone': zone,
                    'plz_prefix': plz_range,
                    'min_price': min_price,
                    'weight_band_raw': weight_band,
                    'price_per_100kg': price,
                    'country': current_country,
                    'pricing_basis': 'EUR/100kg',
                    'knr': '406035'
                })

    result = pd.DataFrame(all_rows) if all_rows else pd.DataFrame()
    print(f"GEZE gesamt: {len(result)} Tarifzeilen")
    return result

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

def _cht_country_from_filename(name):
    """Leitet ISO-Ländercode aus CHT-Dateiname ab."""
    n = name.upper()
    if 'BELGIEN' in n:   return 'BE'
    if 'ÖSTERREICH' in n or 'OSTERREICH' in n: return 'AT'
    if 'SPANIEN' in n:   return 'ES'
    if 'GRIECH' in n:    return 'GR'
    if 'ITALIEN' in n:   return 'IT'
    if 'IT-2005' in n:   return 'IT_SPECIAL'
    return 'UNKNOWN'

def _parse_cht_zone_plz(raw, country_iso):
    """Parst Zone→PLZ-Mapping aus dem unteren Teil des CHT-Sheets.
    Gibt dict {plz_prefix_int: zone_name} zurück."""
    zone_section = False
    zone_plz = {}
    for _, row in raw.iterrows():
        val0 = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ''
        if 'Zoneneinteilung' in val0:
            zone_section = True
            continue
        if zone_section and re.match(r'Zone\s*\d+', val0, re.I):
            zone_name = val0.strip()
            for col_idx in range(1, len(row)):
                cell = str(row.iloc[col_idx]).strip() if pd.notna(row.iloc[col_idx]) else ''
                if not cell or cell == 'nan':
                    continue
                # Einzelzellen können mehrere Ranges enthalten: "20 - 22", "238 + 239", "08"
                for part in re.split(r'[,;]', cell):
                    part = part.strip()
                    if '+' in part:
                        for num_s in part.split('+'):
                            nums = re.findall(r'\d+', num_s.strip())
                            for n in nums:
                                zone_plz[int(n)] = zone_name
                    elif '-' in part:
                        nums = re.findall(r'\d+', part)
                        if len(nums) >= 2:
                            for plz in range(int(nums[0]), int(nums[-1]) + 1):
                                zone_plz[plz] = zone_name
                    else:
                        nums = re.findall(r'\d+', part)
                        for n in nums:
                            zone_plz[int(n)] = zone_name
    return zone_plz

def load_cht():
    """Lädt CHT Tarifdaten (KNR 486073).
    Parst Zonen-Header, Tarifzeilen (col0='bis', col1=Gewicht, col2..N=Preise, letzte=Einheit)
    und Zone→PLZ-Mapping. Speichert PLZ-Mapping in CHT_ZONE_MAPS[country_iso]."""

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
        country_iso = _cht_country_from_filename(f.name)
        try:
            raw = pd.read_excel(f, sheet_name=0, header=None)

            # Zone-Header-Zeile finden: Zeile wo >=2 Zellen mit "Zone" beginnen
            zone_names = []   # list of (col_idx, zone_label)
            for idx, row in raw.iterrows():
                candidates = [(ci, str(v).strip()) for ci, v in enumerate(row)
                              if pd.notna(v) and re.match(r'Zone\s*\d+', str(v).strip(), re.I)]
                if len(candidates) >= 2:
                    zone_names = candidates
                    break

            # Einheitsspalte: Spalte direkt nach letzter Zone-Spalte
            unit_col = (max(ci for ci, _ in zone_names) + 1) if zone_names else 3

            # Tarifzeilen parsen (nur bis "Zoneneinteilung" oder neuen Abschnittsheader)
            file_rows = 0
            for _, row in raw.iterrows():
                val0 = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ''
                # Stopp bei Zoneneinteilung (kommt zwischen Haupttarif und Sonderabschnitt)
                if 'Zoneneinteilung' in val0:
                    break
                if val0.lower() != 'bis':
                    continue
                # Gewichtsgrenze: kann "500 kg" oder 500 (float) sein
                weight_raw = str(row.iloc[1]).strip() if pd.notna(row.iloc[1]) else ''
                nums = re.findall(r'\d+', weight_raw.replace('.', '').replace(',', ''))
                if not nums:
                    continue
                weight_to = float(nums[0])

                unit_val = str(row.iloc[unit_col]).strip() if unit_col < len(row) and pd.notna(row.iloc[unit_col]) else ''
                unit = 'per Sendung' if any(k in unit_val.lower() for k in ['sendung', 'lkw']) else 'per 100 kg'

                if zone_names:
                    for col_idx, zone_label in zone_names:
                        price_cell = row.iloc[col_idx] if col_idx < len(row) else np.nan
                        try:
                            price = float(price_cell)
                        except (ValueError, TypeError):
                            continue
                        all_rows.append({
                            'weight_to': weight_to,
                            'zone': zone_label,
                            'unit': unit,
                            'price': price,
                            'country': country_iso,
                            'source_file': f.name,
                            'pricing_basis': 'EUR',
                            'knr': '486073',
                        })
                        file_rows += 1
                else:
                    # Belgien: eine Zone, Preis in col 2
                    try:
                        price = float(row.iloc[2])
                    except (ValueError, TypeError):
                        continue
                    all_rows.append({
                        'weight_to': weight_to,
                        'zone': 'Zone 1',
                        'unit': unit,
                        'price': price,
                        'country': country_iso,
                        'source_file': f.name,
                        'pricing_basis': 'EUR',
                        'knr': '486073',
                    })
                    file_rows += 1

            # Zone→PLZ Mapping
            zone_plz = _parse_cht_zone_plz(raw, country_iso)
            if zone_plz:
                CHT_ZONE_MAPS[country_iso] = zone_plz
                print(f"  {f.name}: {file_rows} Tarifzeilen, {len(zone_plz)} PLZ-Einträge")
            else:
                print(f"  {f.name}: {file_rows} Tarifzeilen (kein PLZ-Mapping)")

        except Exception as e:
            import traceback
            print(f"  {f.name}: Fehler - {e}")
            traceback.print_exc()

    result = pd.DataFrame(all_rows) if all_rows else pd.DataFrame()
    print(f"CHT gesamt: {len(result)} Tarifzeilen, Länder mit PLZ-Mapping: {list(CHT_ZONE_MAPS.keys())}")
    return result

LOADERS['486073'] = load_cht

def load_fischerwerke():
    """Lädt Fischerwerke Tarifdaten (KNR 409480). EUR/Sendung, pro Stellplatz.
    Struktur: col 0 = Stellplätze (int), col 1 = Preis (float), col 2 = 'per Sendung'.
    Destination wird aus dem Dateinamen extrahiert: 'nach XX-NNNNN'."""

    base = Path('/home/user/TMS/Fischerwerke/DLVs & Tarife/2026')
    if not base.is_dir():
        for p in Path('/home/user/TMS').rglob('Fischerwerke'):
            tarif_dir = p / 'DLVs & Tarife' / '2026'
            if tarif_dir.is_dir():
                base = tarif_dir
                break
        else:
            print("Fischerwerke Verzeichnis nicht gefunden")
            return pd.DataFrame()

    print(f"Fischerwerke Verzeichnis: {base}")
    all_rows = []

    for f in sorted(base.glob('*.xlsx')):
        try:
            # Destination aus Dateiname: "nach XX-NNNNN (City)"
            dests = []
            for m in re.finditer(r'nach\s+([A-Z]{2})-(\S+)', f.stem, re.I):
                land = m.group(1).upper()
                plz_raw = re.sub(r'[^0-9A-Za-z]', '', m.group(2))  # normalize
                dests.append((land, plz_raw))
            if not dests:
                # Fallback: suche nur nach Land-PLZ Muster im Dateinamen
                for m in re.finditer(r'\b([A-Z]{2})-(\d+)', f.stem, re.I):
                    dests.append((m.group(1).upper(), m.group(2)))

            raw = pd.read_excel(f, sheet_name=0, header=None)
            file_rows = 0
            for _, row in raw.iterrows():
                vals = row.tolist()
                # Scan all (col_i, col_i+1) pairs for valid (Stellplätze_int, price_float)
                seen_pairs = set()
                for ci in range(len(vals) - 1):
                    v0, v1 = vals[ci], vals[ci + 1]
                    try:
                        v0s = str(v0).strip()
                        n_stpl = int(float(v0s))
                        price = float(str(v1).strip())
                        if n_stpl <= 0 or price <= 0 or n_stpl > 100:
                            continue
                        if (n_stpl, round(price, 4)) in seen_pairs:
                            continue
                        seen_pairs.add((n_stpl, round(price, 4)))
                    except (ValueError, TypeError):
                        continue
                    for (dest_land, dest_plz) in dests:
                        all_rows.append({
                            'stellplaetze': n_stpl,
                            'price': price,
                            'dest_land': dest_land,
                            'dest_plz': dest_plz,
                            'route': f.stem,
                            'pricing_basis': 'EUR/Sendung',
                            'knr': '409480',
                        })
                        file_rows += 1
            print(f"  {f.name}: {file_rows} Tarifzeilen, dests={dests}")
        except Exception as e:
            print(f"  {f.name}: Fehler - {e}")

    result = pd.DataFrame(all_rows) if all_rows else pd.DataFrame()
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

def _eircode_to_county(eircode):
    """Mapt irischen Eircode-Routing-Key auf County-Name (wie im HERMA IRL-Sheet)."""
    # Alte 3-Buchstaben-Codes (DUB, KID, SLI, ...)
    OLD_CODES = {
        'DUB': 'Dublin',   'KID': 'Kildare',  'SLI': 'Sligo',
        'COR': 'Cork',     'GAL': 'Gatway',   'LIM': 'Limerik',
        'WEX': 'Wexford',  'WAT': 'Waterford','KIL': 'Kilkenny',
        'CAR': 'Carlow',   'CAV': 'Cavan',    'CLA': 'Clare',
        'DON': 'Donegal',  'KER': 'Kerry',    'LAO': 'Laois',
        'LEI': 'Leitrim',  'LON': 'Longford', 'LOU': 'Louth',
        'MAY': 'Mayo',     'MEA': 'Meath',    'MON': 'Monaghan',
        'OFF': 'Offaly',   'ROS': 'Roscommon','TIP': 'Tipperary',
        'WEM': 'Westmeath','WIC': 'Wicklow',
    }
    ec = str(eircode).strip().upper()
    # 3-Letter old-style code?
    m3 = re.match(r'^([A-Z]{3})$', ec)
    if m3 and m3.group(1) in OLD_CODES:
        return OLD_CODES[m3.group(1)]
    # Prefix-match auf 3-Buchstaben
    if len(ec) >= 3 and ec[:3] in OLD_CODES:
        return OLD_CODES[ec[:3]]
    # Neuer Eircode: Letter + 2 Digits (z.B. D01, T12, F93)
    m_new = re.match(r'^([A-Z])(\d{2})', ec)
    if not m_new:
        return 'Dublin'
    letter, num = m_new.group(1), int(m_new.group(2))
    if letter == 'D': return 'Dublin'
    if letter == 'A': return 'Wicklow'
    if letter == 'C': return 'Cavan'
    if letter == 'E': return 'Waterford'
    if letter == 'F': return 'Donegal' if num >= 90 else 'Gatway'
    if letter == 'H': return 'Monaghan'
    if letter == 'K': return 'Kildare'
    if letter == 'N': return 'Meath'
    if letter == 'P': return 'Cork'
    if letter == 'R': return 'Kilkenny'
    if letter == 'T': return 'Cork'
    if letter == 'V': return 'Kerry'
    if letter == 'W': return 'Waterford'
    if letter == 'X': return 'Wexford'
    if letter == 'Y': return 'Wicklow'
    return 'Dublin'


def _lookup_herma(row, tariff):
    """HERMA: Preis pro Sendung. Abrechnungsgewicht = max(Tonnage, LDM*1500, Vol*300).
    Lookup: country → PLZ-Matching (Von/Bis, 2-digit-prefix, GB area, PT zone, IE county)
            → Gewichtsband."""

    _nan = pd.Series({'soll_fracht': np.nan, 'pricing_basis': 'EUR/Sendung',
                      'weight_band_matched': '', 'zone_matched': '', 'min_price_tariff': np.nan})

    country = str(row.get('Empfänger Land', '')).strip()
    plz     = str(row.get('Empfänger PLZ', '')).strip()
    gewicht = row.get('herma_gewicht', row.get('Tonnage (eff.)', 0))
    if pd.isna(gewicht) or gewicht <= 0:
        gewicht = row.get('Tonnage (eff.)', 0)

    # 1. Filter auf Land
    t = tariff[tariff['country'] == country]
    if t.empty:
        return _nan

    # 2. PLZ → Tarifzeilen filtern
    if 'match_type' in t.columns:
        # --- Neue Sheets (CH, FR, GB, IE, IT, PT) ---
        mt = t['match_type'].iloc[0]

        if mt == 'plz_2digit':           # CH, FR: 2-stelliger numerischer PLZ-Prefix
            try:
                prefix = int(''.join(filter(str.isdigit, plz[:2])))
            except (ValueError, TypeError):
                prefix = -1
            t_zone = t[t['Plz_prefix'] == prefix]
            if t_zone.empty:
                t_zone = t
            zone_label = str(prefix)

        elif mt == 'plz_2digit_range':   # IT: PLZ-Bereich '00-06' → Von_int/Bis_int
            try:
                prefix = int(''.join(filter(str.isdigit, plz[:2])))
            except (ValueError, TypeError):
                prefix = -1
            t_zone = t[(pd.to_numeric(t['Von_int'], errors='coerce') <= prefix) &
                       (pd.to_numeric(t['Bis_int'], errors='coerce') >= prefix)]
            if t_zone.empty:
                t_zone = t
            zone_label = str(prefix)

        elif mt == 'gb_area':            # GB: führende Buchstaben aus PLZ
            m = re.match(r'^([A-Z]{1,2})', plz.upper().strip())
            area = m.group(1) if m else ''
            def _area_match(areas_str):
                return any(a.strip() == area
                           for a in re.split(r'[,\s]+', str(areas_str)) if a.strip())
            t_zone = t[t['GB_areas'].apply(_area_match)]
            if t_zone.empty:
                t_zone = t
            zone_label = area

        elif mt == 'irl_county':         # IE: Eircode-Routing-Key → County
            county = _eircode_to_county(plz)
            t_zone = t[t['IRL_county'].str.lower() == county.lower()]
            if t_zone.empty:
                t_zone = t[t['IRL_county'].str.lower() == 'dublin']
            if t_zone.empty:
                t_zone = t
            zone_label = county

        elif mt == 'pt_zone':            # PT: 4-stellige PLZ → Zone via HERMA_PT_ZONE_MAP
            try:
                plz4 = int(''.join(filter(str.isdigit, plz[:4])))
            except (ValueError, TypeError):
                plz4 = 0
            zone_num = None
            for zn, ranges in HERMA_PT_ZONE_MAP.items():
                for (frm, to) in ranges:
                    if frm <= plz4 <= to:
                        zone_num = zn; break
                if zone_num is not None:
                    break
            if zone_num is not None:
                t_zone = t[pd.to_numeric(t['Zone_num'], errors='coerce') == zone_num]
            else:
                t_zone = t
            zone_label = f'Zone {zone_num}' if zone_num else '?'

        else:
            t_zone = t
            zone_label = ''

    else:
        # --- Bestehende Sheets (AT, ES, EE): Von/Bis PLZ-Bereich ---
        try:
            plz_int = int(''.join(filter(str.isdigit, plz[:5])))
        except (ValueError, TypeError):
            plz_int = 0

        if 'Von' in t.columns and 'Bis' in t.columns:
            t_von = pd.to_numeric(t['Von'], errors='coerce')
            t_bis = pd.to_numeric(t['Bis'], errors='coerce')
            t_zone = t[(t_von <= plz_int) & (t_bis >= plz_int)]
        elif 'Von PLZ' in t.columns:
            t_plz = pd.to_numeric(t['Von PLZ'], errors='coerce')
            t_zone = t[t_plz == plz_int]
        else:
            t_zone = pd.DataFrame()

        if t_zone.empty:
            t_zone = t
        zone_label = str(t_zone['Zone'].iloc[0]) if 'Zone' in t_zone.columns and not t_zone.empty else ''

    # 3. Gewichtsband matchen
    t_zone = t_zone.copy()
    t_zone['weight_limit'] = (
        t_zone['weight_band_raw']
        .str.replace(r'\.', '', regex=True)   # "1.000" → "1000"
        .str.extract(r'(\d+)')[0]
        .astype(float)
    )
    t_zone = t_zone.dropna(subset=['weight_limit', 'price'])
    if t_zone.empty:
        return _nan

    passend = t_zone[t_zone['weight_limit'] >= gewicht]
    if passend.empty:
        match = t_zone.loc[t_zone['weight_limit'].idxmax()]
    else:
        match = passend.loc[passend['weight_limit'].idxmin()]

    return pd.Series({
        'soll_fracht':         float(match['price']),
        'pricing_basis':       'EUR/Sendung',
        'weight_band_matched': str(match['weight_band_raw']),
        'zone_matched':        f'{country} {zone_label}',
        'min_price_tariff':    np.nan,
    })

def _lookup_geze(row, tariff):
    """GEZE: EUR/100kg. Lookup: ISO-Land → Ländername, PLZ-Prefix → Zone (Range-Matching), Gewichtsband.
    Billing: ceil(Tonnage / 100) * 100. Minimum beachten."""
    import math

    COUNTRY_MAP = {
        'PT': 'Portugal', 'GB': 'Großbritanien', 'UK': 'Großbritanien',
        'IE': 'Irland', 'IT': 'Italien', 'FR': 'Frankreich',
        'AT': 'Österreich', 'ES': 'Spanien', 'CH': 'Schweiz',
    }

    _nan = pd.Series({'soll_fracht': np.nan, 'pricing_basis': 'EUR/100kg',
                      'weight_band_matched': '', 'zone_matched': '', 'min_price_tariff': np.nan})

    empf_land = str(row.get('Empfänger Land', '')).strip().upper()
    plz = str(row.get('Empfänger PLZ', '')).strip()
    gewicht = row.get('Tonnage (eff.)', 0)

    if pd.isna(gewicht) or gewicht <= 0:
        return _nan

    geze_country = COUNTRY_MAP.get(empf_land)
    if geze_country is None:
        return _nan

    # Frankreich: beide Blöcke ("Frankreich" und "Frankreich Zone 7")
    if geze_country == 'Frankreich':
        t = tariff[tariff['country'].str.startswith('Frankreich')].copy()
    else:
        t = tariff[tariff['country'] == geze_country].copy()

    if t.empty:
        return _nan

    # PLZ: 2-stelliger numerischer Prefix
    plz_digits = ''.join(filter(str.isdigit, plz))
    try:
        plz_num = int(plz_digits[:2]) if len(plz_digits) >= 2 else int(plz_digits)
    except (ValueError, TypeError):
        return _nan

    def plz_in_range(range_str):
        """Prüft ob plz_num in einem der Ranges liegt.
        Unterstützt: '10-19, 26-29', 'Barcelona 08', 'Bilbao, Irun, 01, 17, 20'."""
        import re
        for part in str(range_str).split(','):
            part = part.strip()
            # Numerische Tokens aus dem Teil extrahieren
            nums = [int(n) for n in re.findall(r'\d+', part) if n.isdigit()]
            if not nums:
                continue
            if '-' in part and len(nums) >= 2:
                # Range: erstes und letztes Num als Grenzen
                if nums[0] <= plz_num <= nums[-1]:
                    return True
            else:
                # Einzelne Nummern
                if plz_num in nums:
                    return True
        return False

    zone_match = t[t['plz_prefix'].apply(plz_in_range)]
    if zone_match.empty:
        return _nan

    # Gewichtsband parsen: "bis 1.000 kg" → 1000 (Punkt = Tausendertrennzeichen)
    def parse_wb(s):
        s2 = str(s).replace('.', '').replace(',', '')
        m = pd.Series([s2]).str.extract(r'(\d+)')[0].iloc[0]
        return float(m) if pd.notna(m) else np.nan

    zone_match = zone_match.copy()
    zone_match['weight_limit'] = zone_match['weight_band_raw'].apply(parse_wb)
    zone_match = zone_match.dropna(subset=['weight_limit', 'price_per_100kg'])

    if zone_match.empty:
        return _nan

    billing_kg = math.ceil(gewicht / 100) * 100

    passend = zone_match[zone_match['weight_limit'] >= billing_kg]
    if passend.empty:
        match = zone_match.loc[zone_match['weight_limit'].idxmax()]
    else:
        match = passend.loc[passend['weight_limit'].idxmin()]

    price_100kg = float(match['price_per_100kg']) if pd.notna(match['price_per_100kg']) else np.nan
    fracht = price_100kg * billing_kg / 100 if pd.notna(price_100kg) else np.nan

    min_price_val = match['min_price'] if 'min_price' in match.index else np.nan
    min_price = float(min_price_val) if pd.notna(min_price_val) else np.nan
    if pd.notna(min_price) and pd.notna(fracht):
        fracht = max(fracht, min_price)

    return pd.Series({
        'soll_fracht': fracht,
        'pricing_basis': 'EUR/100kg',
        'weight_band_matched': str(match['weight_band_raw']),
        'zone_matched': str(match['zone']),
        'min_price_tariff': min_price
    })

def _lookup_ebm(row, tariff):
    """EBM-Papst: EUR/Stellplatz. LDM → n_stpl = ceil(LDM/0.4), max 10.
    Destination matching: Empfänger Land + PLZ-Prefix gegen Tarif-Destination."""

    _nan = pd.Series({'soll_fracht': np.nan, 'pricing_basis': 'EUR/Stellplatz',
                      'weight_band_matched': '', 'zone_matched': '', 'min_price_tariff': np.nan})

    empf_land = str(row.get('Empfänger Land', '')).strip().upper()
    empf_plz  = re.sub(r'[\s\-]', '', str(row.get('Empfänger PLZ', '')).strip()).upper()
    ldm = row.get('Lademeter', 0)

    if pd.isna(ldm) or ldm <= 0:
        return _nan

    n_stpl = max(1, math.ceil(float(ldm) / 0.4))
    n_stpl = min(n_stpl, 10)

    def _parse_dest(dest_raw):
        """Gibt Liste von (country_iso, norm_plz) aus Destination-String zurück."""
        pairs = []
        for part in str(dest_raw).split('|'):
            part = part.strip()
            if not part or part == 'nan':
                continue
            # Format: "XX-YYYYY" oder "XX-YY-ZZZ" → country = erste 2 Großbuchstaben
            m = re.match(r'^([A-Z]{2})-(.+)$', part, re.I)
            if m:
                cntry = m.group(1).upper()
                plz_norm = re.sub(r'[\s\-]', '', m.group(2)).upper()
                pairs.append((cntry, plz_norm))
        return pairs

    def _dest_matches(dest_raw):
        for cntry, plz_norm in _parse_dest(dest_raw):
            if cntry != empf_land:
                continue
            # Prefix-Match: Empfänger PLZ beginnt mit dest-PLZ oder umgekehrt
            min_len = min(len(empf_plz), len(plz_norm))
            if min_len >= 2 and empf_plz[:min_len] == plz_norm[:min_len]:
                return True
        return False

    # Nur Hauptpickup (DE-74673) und gültiger Stellplatz
    t = tariff[
        (tariff['pickup'] == 'DE-74673') &
        (tariff['stellplaetze'] == n_stpl)
    ].copy()

    t = t[pd.to_numeric(t['price'], errors='coerce').notna()].copy()
    t['price_num'] = pd.to_numeric(t['price'], errors='coerce')

    matches = t[t['destination'].apply(_dest_matches)]
    if matches.empty:
        return _nan

    match = matches.iloc[0]
    soll = float(match['price_num'])

    return pd.Series({
        'soll_fracht': soll,
        'pricing_basis': 'EUR/Stellplatz',
        'weight_band_matched': f'{n_stpl} Stellplätze',
        'zone_matched': str(match['destination']).strip(),
        'min_price_tariff': np.nan
    })

def _lookup_cht(row, tariff):
    """CHT: EUR/100kg oder EUR/Sendung je nach Gewichtsband.
    Lookup: Land → country_iso, PLZ-Prefix → Zone (via CHT_ZONE_MAPS), Gewichtsband."""

    LAND_MAP = {'IT': 'IT', 'AT': 'AT', 'BE': 'BE', 'ES': 'ES', 'GR': 'GR'}

    _nan = pd.Series({'soll_fracht': np.nan, 'pricing_basis': 'EUR',
                      'weight_band_matched': '', 'zone_matched': '', 'min_price_tariff': np.nan})

    empf_land = str(row.get('Empfänger Land', '')).strip().upper()
    plz = str(row.get('Empfänger PLZ', '')).strip()
    gewicht = row.get('Tonnage (eff.)', 0)

    if pd.isna(gewicht) or gewicht <= 0:
        return _nan

    country_iso = LAND_MAP.get(empf_land)
    if country_iso is None:
        return _nan

    # Zone bestimmen
    if country_iso == 'BE':
        zone = 'Zone 1'
    else:
        plz_digits = ''.join(filter(str.isdigit, plz))
        if not plz_digits:
            return _nan
        try:
            plz_num = int(plz_digits[:2])
        except ValueError:
            return _nan
        zone_map = CHT_ZONE_MAPS.get(country_iso, {})
        zone = zone_map.get(plz_num)
        if zone is None:
            return _nan

    t = tariff[(tariff['country'] == country_iso) & (tariff['zone'] == zone)].copy()
    if t.empty:
        return _nan

    billing_kg = math.ceil(gewicht / 100) * 100

    t['weight_to_num'] = pd.to_numeric(t['weight_to'], errors='coerce')
    t = t.dropna(subset=['weight_to_num', 'price'])

    passend = t[t['weight_to_num'] >= billing_kg]
    if passend.empty:
        match = t.loc[t['weight_to_num'].idxmax()]
    else:
        match = passend.loc[passend['weight_to_num'].idxmin()]

    price = float(match['price']) if pd.notna(match['price']) else np.nan
    unit = str(match.get('unit', 'per 100 kg'))

    if 'sendung' in unit.lower() or 'lkw' in unit.lower():
        soll = price
    else:
        soll = price * billing_kg / 100 if pd.notna(price) else np.nan

    return pd.Series({
        'soll_fracht': soll,
        'pricing_basis': unit,
        'weight_band_matched': f"bis {match['weight_to_num']:.0f} kg",
        'zone_matched': zone,
        'min_price_tariff': np.nan
    })

def _lookup_fischer(row, tariff):
    """Fischerwerke: EUR/Sendung. Lookup: Empfänger Land + PLZ → Route, dann Stellplätze → Preis."""

    _nan = pd.Series({'soll_fracht': np.nan, 'pricing_basis': 'EUR/Sendung',
                      'weight_band_matched': '', 'zone_matched': '', 'min_price_tariff': np.nan})

    empf_land = str(row.get('Empfänger Land', '')).strip().upper()
    empf_plz  = re.sub(r'[\s\-]', '', str(row.get('Empfänger PLZ', '')).strip()).upper()
    # Stellplätze: direkt aus BI, oder berechnen aus LDM
    stpl_raw = row.get('Stellplätze_calc', row.get('Stellplätze', np.nan))
    if pd.isna(stpl_raw) or stpl_raw <= 0:
        ldm = row.get('Lademeter', 0)
        stpl_raw = math.ceil(float(ldm) / 0.4) if pd.notna(ldm) and ldm > 0 else 0
    n_stpl = max(1, int(round(float(stpl_raw))))

    if not empf_land:
        return _nan

    # Route-Matching: Empfänger Land + PLZ-Prefix gegen dest_land + dest_plz
    t = tariff[tariff['dest_land'] == empf_land].copy()
    if t.empty:
        return _nan

    # PLZ-Prefix-Match (empf_plz beginnt mit dest_plz oder umgekehrt)
    def _plz_match(dest_plz):
        d = re.sub(r'[\s\-]', '', str(dest_plz)).upper()
        min_len = min(len(empf_plz), len(d))
        return min_len >= 3 and empf_plz[:min_len] == d[:min_len]

    t_route = t[t['dest_plz'].apply(_plz_match)]

    # Fallback: wenn kein PLZ-Match und nur eine Route für dieses Land → nehme die
    if t_route.empty and t['route'].nunique() == 1:
        t_route = t

    if t_route.empty:
        return _nan

    t_stpl = t_route[t_route['stellplaetze'] == n_stpl]
    if t_stpl.empty:
        # Nächst-höhere Stellplatz-Stufe nehmen
        higher = t_route[t_route['stellplaetze'] >= n_stpl]
        if higher.empty:
            t_stpl = t_route.loc[[t_route['stellplaetze'].idxmax()]]
        else:
            t_stpl = higher.loc[[higher['stellplaetze'].idxmin()]]

    match = t_stpl.iloc[0]
    soll = float(match['price'])
    route = str(match['route'])

    return pd.Series({
        'soll_fracht': soll,
        'pricing_basis': 'EUR/Sendung',
        'weight_band_matched': f'{n_stpl} Stellplätze',
        'zone_matched': route,
        'min_price_tariff': np.nan
    })
