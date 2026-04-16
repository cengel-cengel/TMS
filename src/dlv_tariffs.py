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
        elif knr == '408244':
            return _lookup_helu(row, tariff)
        elif knr == '406345':
            return _lookup_bitzer(row, tariff)
        elif knr == '490085':
            return _lookup_hornschuch(row, tariff)
        elif knr == '491063':
            return _lookup_sika(row, tariff)
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


# ─────────────────────────────────────────────────────────────────────────────
# Neue Loader: Helu (408244), Bitzer (406345), Hornschuch (490085)
# Groz-Beckert: kein KNR in BI-Daten → nur NK-Glob-Pattern, kein LOADERS-Eintrag
# ─────────────────────────────────────────────────────────────────────────────

# Globale Zone-Maps, die beim Laden befüllt werden
HELU_ZONE_MAPS: dict = {}    # {'GB': {area_str: zone_str}, 'PL': {2digit_int: 'Zone N'}}
BITZER_ZONE_MAPS: dict = {}  # {country_iso: {2digit_int: 'Zone N'}}

_HELU_BASE    = Path('/home/user/TMS/data/extracted/v1/Noerpel AI/Helu/DLV')
_BITZER_BASE  = Path('/home/user/TMS/data/extracted/v1/Noerpel AI/Bitzer/DLV/Bitzer Rottenburg/2026')
_HORNSCHUCH_DLV = Path(
    '/home/user/TMS/data/extracted/v1/Noerpel AI/Hornschuch/DLV/2025/'
    '20250129_Erka_ContiTech Megatrans Deutsc.xlsx'
)
# PL-Korrekturdatei: Sondertarife Polen (Sheet 'CT-SSL-WEI-P001.' mit korrigiertem Spalten-Offset)
_HORNSCHUCH_PL = Path(
    '/home/user/TMS/data/extracted/v1/Noerpel AI/Hornschuch/DLV/2025/'
    '20250612_Erka_ContiTech_PL_korrigiert.xlsx'
)
_GROZ_BASE    = Path('/home/user/TMS/data/extracted/v1/Noerpel AI/Groz Beckert/DLV')
_SIKA_DLV     = Path(
    '/home/user/TMS/data/extracted/v1/Noerpel AI/SIka/DLV/'
    'SIKA Deutschland GmbH Stuttgart/2026/'
    '20260211_SIKA DE & SSC Export div. LKZ_Stellplatzofferte_2026.xlsx'
)


def _erka_zone_plz_map(raw) -> dict:
    """Parst 'Zoneneinteilung'-Abschnitt → {2-stellige PLZ-Prefix (int): 'Zone N'}.
    Erkennt 2-stellige Bereiche ('20 - 25') sowie 3-/4-/5-stellige Bereiche → 2-digit-Prefix.
    Bei überlappenden Zonen gewinnt die erste Zuweisung (setdefault)."""
    zone_plz: dict = {}
    in_sec = False

    def _to2(n: int) -> int | None:
        """Konvertiert beliebige Ganzzahl → 2-stelliger PLZ-Prefix."""
        while n >= 100:
            n //= 10
        return n if n >= 0 else None

    def _register(n: int, zname: str) -> None:
        p = _to2(n)
        if p is not None:
            zone_plz.setdefault(p, zname)

    def _process_part(part: str, zname: str) -> None:
        """Verarbeitet einen Token (Einzelzahl oder Bereich) und registriert PLZ-Prefixes."""
        part = part.strip()
        if not part:
            return
        # Versuche als Bereich (z.B. '20 - 25', '330-337', '35 -39')
        mr = re.match(r'^(\d+)\s*[-–]\s*(\d+)$', part)
        ms = re.match(r'^(\d+)$', part)
        if mr:
            lo = int(mr.group(1))
            hi = int(mr.group(2))
            if lo > hi:
                lo, hi = hi, lo
            if hi < 100:
                # Direkter 2-stelliger Bereich → alle Werte
                for n in range(lo, hi + 1):
                    zone_plz.setdefault(n, zname)
            else:
                # 3-stelliger+ Bereich → 2-digit-Prefixes extrahieren
                p_lo = _to2(lo)
                p_hi = _to2(hi)
                if p_lo is not None and p_hi is not None:
                    for p in range(p_lo, p_hi + 1):
                        zone_plz.setdefault(p, zname)
        elif ms:
            _register(int(ms.group(1)), zname)
        else:
            # Fallback: führende Zahl extrahieren (z.B. '08 Barcelona', '28 Madrid')
            ml = re.match(r'^(\d+)', part)
            if ml:
                _register(int(ml.group(1)), zname)

    for _, row in raw.iterrows():
        v0 = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ''
        if 'zoneneinteilung' in v0.lower():
            in_sec = True
            continue
        if not in_sec:
            continue
        if v0 == '' and zone_plz:
            break
        m = re.match(r'Zone\s*(\d+)', v0, re.I)
        if not m:
            continue
        zone_name = f'Zone {m.group(1)}'
        for v in row.iloc[1:]:
            if pd.isna(v):
                continue
            # Numerische Excel-Zellen (int/float) direkt umwandeln
            if isinstance(v, (int, float)):
                cell = str(int(round(v)))
            else:
                cell = str(v).strip()
            if not cell or cell in ('-', 'nan'):
                continue
            # Zuerst nach Komma aufteilen, dann Bereichserkennung pro Teil
            for part in re.split(r',\s*', cell):
                _process_part(part, zone_name)
    return zone_plz


def _parse_erka_bands(raw, header_idx: int, zone_cols: list, country: str, knr: str) -> list:
    """Parst Gewichtsbandzeilen ab header_idx+1.
    Unterstützt Helu-Format (Gewicht in col0, Zonen in col1+)
    und Bitzer-Format ('bis' in col0, Gewicht in col1, Zonen in col2+, Einheit in letzter Spalte).
    Gibt Liste von Dicts zurück (weight_to, zone, unit, price, country, pricing_basis, knr)."""
    rows: list = []
    if not zone_cols:
        return rows
    unit_col = max(ci for ci, _ in zone_cols) + 1

    _STOP = ('zoneneinteilung', 'abfahrt', 'volumen', 'rundung', 'selbstk',
             'profit', 'verkauf', 'postcode', 'laufzeit', 'komplett',
             'maximale', 'maut:', 'diesel', 'versicher', 'gültig', 'angebot',
             'frachtberech', 'mehrkosten')

    for i in range(header_idx + 1, len(raw)):
        row = raw.iloc[i]
        cells = [str(v).strip() if pd.notna(v) else '' for v in row]
        c0 = cells[0].lower() if cells else ''

        if any(k in c0 for k in _STOP):
            break

        # Minimum-Zeile
        is_min = any('minimum' in cells[j].lower() or 'm/m' in cells[j].lower()
                     for j in range(min(3, len(cells))))
        if is_min:
            weight_to, unit = 100.0, 'per Sendung'
        else:
            # Gewicht aus col0 (Helu) oder col1 nach 'bis'/'ab' (Bitzer)
            weight_str = ''
            if c0 in ('bis', 'ab') and len(cells) > 1:
                nums = re.findall(r'[\d.]+', cells[1].replace(' ', ''))
                if nums:
                    weight_str = nums[0]
            elif c0 and c0 != '-':
                nums = re.findall(r'[\d.]+', cells[0].replace(' ', ''))
                if nums:
                    weight_str = nums[0]
            if not weight_str:
                continue
            try:
                if '.' in weight_str:
                    parts = weight_str.split('.')
                    weight_to = (float(weight_str.replace('.', ''))
                                 if len(parts[-1]) == 3
                                 else float(weight_str))
                else:
                    weight_to = float(weight_str)
            except ValueError:
                continue
            if weight_to <= 0:
                continue

            unit = 'per 100 kg'
            if unit_col < len(cells):
                u = cells[unit_col].lower()
                if 'sendung' in u or 'pauschal' in u or 'lkw' in u:
                    unit = 'per Sendung'
            for j in range(min(3, len(cells))):
                if 'pauschal' in cells[j].lower():
                    unit = 'per Sendung'
                    break
                if 'per 100' in cells[j].lower():
                    unit = 'per 100 kg'
                    break

        for ci, zone_key in zone_cols:
            try:
                price = float(row.iloc[ci])
                if price > 0:
                    rows.append({
                        'weight_to': weight_to, 'zone': zone_key, 'unit': unit,
                        'price': price, 'country': country,
                        'pricing_basis': 'EUR', 'knr': knr,
                    })
            except (TypeError, ValueError, IndexError):
                pass
    return rows


def load_groz_beckert():
    """Groz-Beckert: kein KNR in den BI-Rohdaten → kein LOADERS-Eintrag.
    Diese Funktion ist ein Platzhalter; gibt leeres DataFrame zurück."""
    print("Groz-Beckert: nicht in BI-Daten, kein Tarif-Lookup möglich.")
    return pd.DataFrame()
# Hinweis: LOADERS-Eintrag für Groz-Beckert wird NICHT gesetzt.


def load_helu():
    """Lädt Helu Tarifdaten (KNR 408244).
    Strukturen je nach Land:
      AT/PT : ERKA-Format, 'PLZ N' Zonen-Spalten (1. Stelle PLZ)
      IT    : Direkt-Spalten '00\\nRoma', '01\\nViterbo' ... (2-stelliger Prefix)
      ES    : Direkt-Spalten 'PLZ 01\\nAlava' ... (2-stelliger Prefix)
      GR    : 2 Zonen ('gr-other', 'gr-athen')
      IE    : County-Namen als Zonen
      GB    : Zonen 1-10, Postcodes-Abschnitt → HELU_ZONE_MAPS['GB']
      PL    : Separate Zonen-Kopfzeile + PLZ-Mapping → HELU_ZONE_MAPS['PL']
      CH    : 'Postcode'-Kopfzeile, Gewichtsstufen-Spalten (per Sendung)
    """
    if not _HELU_BASE.is_dir():
        print(f"Helu DLV-Verzeichnis nicht gefunden: {_HELU_BASE}")
        return pd.DataFrame()

    all_rows: list = []

    for fp in sorted(_HELU_BASE.glob('*.xlsx')):
        name = fp.name

        # ── Land aus Dateiname erkennen ──────────────────────────────────────
        if 'Export AT' in name:
            country = 'AT'
        elif 'Export CH' in name and 'CH-' not in name:
            country = 'CH'
        elif re.search(r'Export ES\s', name):          # "Export ES " – nicht ES-Mendaro
            country = 'ES'
        elif 'Export ES-' in name:
            continue
        elif 'Export GB' in name:
            country = 'GB'
        elif 'Export IE' in name:
            country = 'IE'
        elif 'Export IT' in name:
            country = 'IT'
        elif 'Export PL' in name:
            country = 'PL'
        elif re.search(r'Export PT\s', name):          # "Export PT " – nicht PT-Lanheses
            country = 'PT'
        elif 'Export PT-' in name:
            continue
        elif 'GR' in name or '#U00e4' in name:         # URL-kodiertes 'ä' in "ergänzt"
            country = 'GR'
        else:
            continue                                    # xlsb-Masterdatei u. a. überspringen

        try:
            raw = pd.read_excel(fp, sheet_name=0, header=None)
        except Exception as exc:
            print(f"  Helu {name}: Fehler – {exc}")
            continue

        before = len(all_rows)

        # ── CH: 'Postcode'-Kopfzeile + Gewichtsstufen-Spalten ───────────────
        if country == 'CH':
            hdr = next(
                (i for i, r in raw.iterrows()
                 if pd.notna(r.iloc[0]) and 'postcode' in str(r.iloc[0]).lower()),
                None)
            if hdr is None:
                continue
            wt_cols = [
                (ci, float(str(raw.iloc[hdr, ci]).replace(',', '.')))
                for ci in range(1, raw.shape[1])
                if pd.notna(raw.iloc[hdr, ci]) and
                re.match(r'[\d,\.]+$', str(raw.iloc[hdr, ci]).strip())
            ]
            for i in range(hdr + 1, len(raw)):
                plz_val = str(raw.iloc[i, 0]).strip() if pd.notna(raw.iloc[i, 0]) else ''
                if not re.match(r'CH\d+', plz_val, re.I):
                    continue
                zone_key = plz_val.upper()
                for ci, wt in wt_cols:
                    try:
                        price = float(raw.iloc[i, ci])
                        if price > 0:
                            all_rows.append({'weight_to': wt, 'zone': zone_key,
                                             'unit': 'per Sendung', 'price': price,
                                             'country': 'CH', 'pricing_basis': 'EUR',
                                             'knr': '408244'})
                    except (TypeError, ValueError):
                        pass

        # ── PL: Separate Zonen-Kopfzeile, PLZ-Mapping, dann Gewichtszeilen ──
        elif country == 'PL':
            # 1) Zonen-Kopfzeile finden (Zone 1–7)
            zh_idx = None
            zone_cols_pl: list = []
            for i, row in raw.iterrows():
                cands = [(ci, str(v).strip()) for ci, v in enumerate(row)
                         if pd.notna(v) and re.match(r'Zone\s*\d+', str(v).strip(), re.I)]
                if len(cands) >= 2:
                    zh_idx, zone_cols_pl = i, cands
                    break
            if zh_idx is None:
                continue

            # 2) PLZ-Mapping aufbauen (PLZ 0 … PLZ 9 → Zone N)
            pl_map: dict = {}
            wh_idx = None
            for i in range(zh_idx + 1, len(raw)):
                v0 = str(raw.iloc[i, 0]).strip() if pd.notna(raw.iloc[i, 0]) else ''
                if 'bis kg' in v0.lower():
                    wh_idx = i
                    break
                if not re.match(r'PLZ\s*\d', v0, re.I):
                    continue
                for ci, zone_name in zone_cols_pl:
                    v = raw.iloc[i, ci] if ci < raw.shape[1] else np.nan
                    if pd.isna(v) or str(v).strip() in ('', '-', 'nan'):
                        continue
                    for part in re.split(r',', str(v)):
                        part = part.strip()
                        mr = re.match(r'(\d+)\s*[-–]\s*(\d+)', part)
                        if mr:
                            for n in range(min(int(mr.group(1)), int(mr.group(2))),
                                           max(int(mr.group(1)), int(mr.group(2))) + 1):
                                pl_map[n] = zone_name
                        elif re.search(r'\d+', part):
                            pl_map[int(re.search(r'\d+', part).group())] = zone_name
            HELU_ZONE_MAPS['PL'] = pl_map

            if wh_idx is None:
                continue
            rows = _parse_erka_bands(raw, wh_idx, zone_cols_pl, 'PL', '408244')
            all_rows.extend(rows)

        # ── GB: Zonen 1–10, dann Postcodes-Abschnitt ────────────────────────
        elif country == 'GB':
            zh_idx = None
            zone_cols_gb: list = []
            for i, row in raw.iterrows():
                num_cells = [(ci, int(float(str(v)))) for ci, v in enumerate(row.iloc[1:12], 1)
                             if pd.notna(v) and re.match(r'^\d+$', str(v).strip())]
                nums = [n for _, n in num_cells]
                if len(nums) >= 8 and nums[0] == 1:
                    zh_idx = i
                    zone_cols_gb = [(ci, str(n)) for ci, n in num_cells if n <= 10]
                    break
            if zh_idx is None:
                continue

            all_rows.extend(_parse_erka_bands(raw, zh_idx, zone_cols_gb, 'GB', '408244'))

            # Postcodes → HELU_ZONE_MAPS['GB']
            pc_idx = next(
                (i for i, r in raw.iterrows()
                 if pd.notna(r.iloc[0]) and 'postcode' in str(r.iloc[0]).lower()),
                None)
            if pc_idx is not None:
                col_to_zone = {ci: z for ci, z in zone_cols_gb}
                gb_map: dict = {}
                for i in range(pc_idx, min(pc_idx + 60, len(raw))):
                    for ci in range(1, 11):
                        v = raw.iloc[i, ci] if ci < raw.shape[1] else np.nan
                        if pd.isna(v):
                            continue
                        area = str(v).strip().upper()
                        if re.match(r'^[A-Z]{1,2}$', area) and ci in col_to_zone:
                            gb_map[area] = col_to_zone[ci]
                HELU_ZONE_MAPS['GB'] = gb_map

        # ── GR: 2 Zonen (col1 = gr-other, col2 = gr-athen) ─────────────────
        elif country == 'GR':
            hdr = next(
                (i for i, r in raw.iterrows()
                 if pd.notna(r.iloc[0]) and 'bis kg' in str(r.iloc[0]).lower()),
                None)
            if hdr is None:
                continue
            zone_cols_gr: list = []
            for ci in range(1, min(6, raw.shape[1])):
                v = raw.iloc[hdr, ci]
                if pd.isna(v) or str(v).strip() in ('', '-', 'nan'):
                    continue
                if not zone_cols_gr:
                    zone_cols_gr.append((ci, 'gr-other'))
                elif len(zone_cols_gr) == 1:
                    zone_cols_gr.append((ci, 'gr-athen'))
                if len(zone_cols_gr) == 2:
                    break
            all_rows.extend(_parse_erka_bands(raw, hdr, zone_cols_gr, 'GR', '408244'))

        # ── AT / PT / IT / ES / IE: Standard-ERKA-Format ────────────────────
        else:
            hdr = None
            zone_cols_std: list = []
            for i, row in raw.iterrows():
                v0 = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ''
                is_hdr = (v0.lower() in ('bis kg', 'gewichte') or 'bis kg' in v0.lower())
                # IE: Kopfzeile hat leeres col0, col1 = 'Dublin' etc.
                if country == 'IE' and not is_hdr and v0 == '':
                    v1 = str(row.iloc[1]).strip() if raw.shape[1] > 1 and pd.notna(row.iloc[1]) else ''
                    if v1 and v1[0].isupper() and len(v1) > 2 and not v1[0].isdigit():
                        is_hdr = True
                if not is_hdr:
                    continue
                cands: list = []
                for ci in range(1, raw.shape[1]):
                    v = row.iloc[ci]
                    if pd.isna(v) or str(v).strip() in ('', '-', 'nan'):
                        continue
                    v_str = str(v).strip()
                    if country in ('AT', 'PT'):
                        if re.match(r'PLZ\s*\d+', v_str, re.I):
                            cands.append((ci, v_str))
                    elif country == 'IT':
                        m = re.match(r'^(\d{2})\b', v_str.replace('\n', ' '))
                        if m:
                            cands.append((ci, m.group(1).zfill(2)))
                    elif country == 'ES':
                        m = re.search(r'PLZ\s*(\d+)', v_str, re.I)
                        if m:
                            cands.append((ci, m.group(1).zfill(2)))
                    elif country == 'IE':
                        if v_str[0].isupper() and len(v_str) > 2:
                            cands.append((ci, v_str))
                if len(cands) >= 2:
                    hdr, zone_cols_std = i, cands
                    break
            if hdr is not None and zone_cols_std:
                all_rows.extend(
                    _parse_erka_bands(raw, hdr, zone_cols_std, country, '408244'))

        file_rows = len(all_rows) - before
        print(f"  Helu {country} ({fp.name[:50]}): {file_rows} Zeilen")

    result = pd.DataFrame(all_rows) if all_rows else pd.DataFrame()
    countries = sorted(result['country'].unique().tolist()) if not result.empty else []
    print(f"Helu gesamt: {len(result)} Tarifzeilen, Länder: {countries}")
    return result


LOADERS['408244'] = load_helu


def load_bitzer():
    """Lädt Bitzer Tarifdaten (KNR 406345).
    Strukturen je nach Land:
      AT/IT/FR/ES/PT : ERKA-Format, 'Zone N' ab col2, Zoneneinteilung → BITZER_ZONE_MAPS
      BENELUX         : col2='Belgien\\nNiederlande' (Zone 1), col3='Zone 2'
      CH              : col1='PLZ', Gewichtsstufen-Spalten ab col3
    Importdateien, Sonderdestinationen (FR-13400, PT-6001) werden übersprungen.
    """
    if not _BITZER_BASE.is_dir():
        print(f"Bitzer DLV-Verzeichnis nicht gefunden: {_BITZER_BASE}")
        return pd.DataFrame()

    all_rows: list = []

    for fp in sorted(_BITZER_BASE.glob('*.xlsx')):
        name = fp.name

        # ── Importdateien und Sonderdestinationen überspringen ───────────────
        if 'Import' in name:
            continue

        # ── Land aus Dateiname erkennen ──────────────────────────────────────
        if 'sterreich' in name.lower() or '#U00d6' in name:   # Österreich (Ö URL-kodiert)
            country = 'AT'
        elif 'BeNeLux' in name:
            country = 'BENELUX'
        elif 'Frankreich_Zonentarif' in name:
            country = 'FR'
        elif 'FR-' in name:
            continue                                            # FR-13400, FR-77380 überspringen
        elif 'Italien' in name:
            country = 'IT'
        elif 'Portugal_Zonentarif' in name:
            country = 'PT'
        elif 'PT-' in name:
            continue                                            # PT-6001 überspringen
        elif 'Schweiz' in name:
            country = 'CH'
        elif 'Spanien' in name:
            country = 'ES'
        else:
            continue

        try:
            raw = pd.read_excel(fp, sheet_name=0, header=None)
        except Exception as exc:
            print(f"  Bitzer {name}: Fehler – {exc}")
            continue

        before = len(all_rows)

        # ── CH: col1='PLZ', Gewichtsstufen in col3+ ─────────────────────────
        if country == 'CH':
            hdr = next(
                (i for i, r in raw.iterrows()
                 if raw.shape[1] > 1 and pd.notna(r.iloc[1])
                 and 'plz' in str(r.iloc[1]).lower()),
                None)
            if hdr is None:
                continue

            # Gewichtsstufen aus Kopfzeile (col3+)
            wt_data: list = []         # (col_idx, weight_to, unit)
            for ci in range(3, raw.shape[1]):
                v = raw.iloc[hdr, ci]
                if pd.isna(v):
                    continue
                v_str = str(v).strip()
                if 'minimum' in v_str.lower():
                    wt_data.append([ci, 100.0, 'per Sendung'])
                else:
                    try:
                        wt_data.append([ci, float(v_str.replace(',', '.')), 'per 100 kg'])
                    except ValueError:
                        pass

            # Einheiten aus Folgezeile (hdr+1) nachschärfen
            if hdr + 1 < len(raw):
                for entry in wt_data:
                    ci = entry[0]
                    u = str(raw.iloc[hdr + 1, ci]).lower() if ci < raw.shape[1] else ''
                    if 'sendung' in u:
                        entry[2] = 'per Sendung'
                    elif 'per 100' in u or '100 kg' in u:
                        entry[2] = 'per 100 kg'

            for i in range(hdr + 2, len(raw)):
                row = raw.iloc[i]
                plz_val = str(row.iloc[1]).strip() if pd.notna(row.iloc[1]) else ''
                if not plz_val or plz_val in ('-', 'nan'):
                    continue
                c0 = str(row.iloc[0]).lower() if pd.notna(row.iloc[0]) else ''
                if any(k in c0 for k in ('komplett', 'volumen', 'rundung', 'maut')):
                    break
                # PLZ-Werte: "10 + 14", "18", "2074", "31, 32" usw.
                plz_keys: set = set()
                for token in re.split(r'[,\s+]+', plz_val):
                    token = token.strip()
                    if re.match(r'^\d{2,4}$', token):
                        plz_keys.add(token[:2])
                if not plz_keys:
                    continue
                for ci, wt, unit in wt_data:
                    try:
                        price = float(row.iloc[ci])
                        if price <= 0:
                            continue
                    except (TypeError, ValueError):
                        continue
                    for pk in plz_keys:
                        all_rows.append({
                            'weight_to': wt, 'zone': f'CH{pk}', 'unit': unit,
                            'price': price, 'country': 'CH',
                            'pricing_basis': 'EUR', 'knr': '406345',
                        })

        # ── BENELUX: col2='Belgien\\nNiederlande', col3='Zone 2' ─────────────
        elif country == 'BENELUX':
            hdr = None
            zone_cols_bn: list = []
            for i, row in raw.iterrows():
                cands = []
                for ci in range(2, min(6, raw.shape[1])):
                    v = str(row.iloc[ci]).strip() if pd.notna(row.iloc[ci]) else ''
                    if not v or v == '-':
                        continue
                    if 'belgien' in v.lower():
                        cands.append((ci, 'Zone 1'))
                    elif re.match(r'Zone\s*2', v, re.I):
                        cands.append((ci, 'Zone 2'))
                if len(cands) >= 2:
                    hdr, zone_cols_bn = i, cands
                    break
            if hdr is None or not zone_cols_bn:
                continue
            all_rows.extend(
                _parse_erka_bands(raw, hdr, zone_cols_bn, 'BENELUX', '406345'))

        # ── AT / IT / FR / ES / PT: Standard-ERKA-Format ────────────────────
        else:
            # Zonen-Kopfzeile: col2..N enthalten 'Zone N'
            hdr = None
            zone_cols_std: list = []
            for i, row in raw.iterrows():
                cands = [(ci, str(v).strip()) for ci, v in enumerate(row.iloc[2:], 2)
                         if pd.notna(v) and re.match(r'Zone\s*\d+', str(v).strip(), re.I)]
                if len(cands) >= 2:
                    hdr, zone_cols_std = i, cands
                    break
            if hdr is None or not zone_cols_std:
                continue

            all_rows.extend(
                _parse_erka_bands(raw, hdr, zone_cols_std, country, '406345'))

            # Zoneneinteilung → BITZER_ZONE_MAPS[country]
            zone_map = _erka_zone_plz_map(raw)
            if zone_map:
                BITZER_ZONE_MAPS[country] = zone_map

        file_rows = len(all_rows) - before
        print(f"  Bitzer {country} ({fp.name[:50]}): {file_rows} Zeilen")

    result = pd.DataFrame(all_rows) if all_rows else pd.DataFrame()
    countries = sorted(result['country'].unique().tolist()) if not result.empty else []
    print(f"Bitzer gesamt: {len(result)} Tarifzeilen, Länder: {countries}")
    print(f"  BITZER_ZONE_MAPS: {list(BITZER_ZONE_MAPS.keys())}")
    return result


LOADERS['406345'] = load_bitzer


def load_hornschuch():
    """Lädt Hornschuch Tarifdaten (KNR 490085) aus CT-SSL-WEI-P001 (MegaTrans-Format).

    Struktur:
      - Header-Zeile an Row-Index 7; Daten ab Row 8
      - Filter: Origin Country='DE', Origin Cluster='74', In/Out='Outbound'
      - Destination Cluster = PLZ-Prefix des Empfängers
        * Länder mit Zonen '1'-'9'  (AT,BE,CH,GR,NL,SI,…): 1-stelliger PLZ-Prefix
        * Länder mit Zonen '00'-'99' (IT,FR,ES,PL,DE,…):    2-stelliger PLZ-Prefix
        * GB: Outward-Code (AB, AL, B, …)
        * IE: Eircode-Routing-Key (D01, …)
      - Preisspalten:
        * col12: Minimum (€/Sendung) für < 50,01 kg
        * col13-col36: €/kg für gewichtsbasierte Bänder

    Gibt DataFrame zurück mit Spalten:
      weight_to, zone (= Cluster-Wert), unit (per Sendung | per_kg),
      price, country, pricing_basis, knr
    """
    if not _HORNSCHUCH_DLV.is_file():
        print(f"Hornschuch DLV nicht gefunden: {_HORNSCHUCH_DLV}")
        return pd.DataFrame()

    try:
        raw = pd.read_excel(_HORNSCHUCH_DLV, sheet_name='CT-SSL-WEI-P001', header=None)
    except Exception as exc:
        print(f"Hornschuch DLV Lesefehler: {exc}")
        return pd.DataFrame()

    hdr_row = raw.iloc[7]

    # ── Gewichtsbänder aus Kopfzeile extrahieren (col 12-35) ─────────────────
    # col36 = '24000 kg' ist FTL-Pauschale → wird weggelassen
    # Ergebnis: [(col_idx, weight_to_kg, unit), …]
    wt_bands: list = []
    for ci in range(12, min(36, raw.shape[1])):
        v = str(hdr_row.iloc[ci]).strip() if pd.notna(hdr_row.iloc[ci]) else ''
        if not v or v == 'nan':
            continue
        if 'minimum' in v.lower():
            # Minimum < 50,01 kg → Pauschale per Sendung
            wt_bands.append((ci, 50.0, 'per Sendung'))
        else:
            # "A,BC - D,EF kg" oder "24000 kg" → obere Grenze
            norm = v.replace(',', '.')
            nums = re.findall(r'\d+\.?\d*', norm)
            if not nums:
                continue
            try:
                wt_bands.append((ci, float(nums[-1]), 'per_kg'))
            except ValueError:
                continue

    if not wt_bands:
        print("Hornschuch: Keine Gewichtsbänder gefunden")
        return pd.DataFrame()

    # ── Outbound-Zeilen filtern und Tarifzeilen aufbauen ─────────────────────
    all_rows: list = []

    for i in range(8, len(raw)):
        row = raw.iloc[i]
        # Columns by position (0-based):
        # 5=Origin Country, 6=Origin Cluster, 9=Dest Country,
        # 10=Dest Cluster, 11=In/Outbound

        def cell(ci):
            v = row.iloc[ci]
            return str(v).strip() if pd.notna(v) else ''

        if cell(5) != 'DE' or cell(6) != '74' or cell(11) != 'Outbound':
            continue

        dest_country = cell(9)
        zone_cluster = cell(10)
        if not dest_country or dest_country == 'nan':
            continue
        if not zone_cluster or zone_cluster == 'nan':
            continue

        for ci, wt, unit in wt_bands:
            try:
                price = float(row.iloc[ci])
            except (TypeError, ValueError):
                continue
            if pd.isna(price) or price <= 0 or price >= 9999:
                continue
            all_rows.append({
                'weight_to':     wt,
                'zone':          zone_cluster,   # = PLZ-Prefix (direkt verwendbar)
                'unit':          unit,
                'price':         price,
                'country':       dest_country,
                'pricing_basis': 'EUR/kg',
                'knr':           '490085',
            })

    # ── PL-Korrekturdatei: 'CT-SSL-WEI-P001.' mit Offset -1 ─────────────────
    # Spalten-Layout im Dot-Sheet: col4=Origin, col5=OriginCluster,
    # col8=DestCountry, col9=DestCluster, col10=In/Out, col11+=Preise
    if _HORNSCHUCH_PL.is_file():
        try:
            raw_pl = pd.read_excel(_HORNSCHUCH_PL, sheet_name='CT-SSL-WEI-P001.', header=None)
            hdr_pl = raw_pl.iloc[7]
            # Gewichtsbänder aus Kopfzeile (col 11-34, analog zu Hauptblatt)
            wt_bands_pl: list = []
            for ci in range(11, min(35, raw_pl.shape[1])):
                v = str(hdr_pl.iloc[ci]).strip() if pd.notna(hdr_pl.iloc[ci]) else ''
                if not v or v == 'nan':
                    continue
                if 'minimum' in v.lower():
                    wt_bands_pl.append((ci, 50.0, 'per Sendung'))
                else:
                    norm = v.replace(',', '.')
                    nums = re.findall(r'\d+\.?\d*', norm)
                    if nums:
                        try:
                            wt_bands_pl.append((ci, float(nums[-1]), 'per_kg'))
                        except ValueError:
                            pass
            for i in range(8, len(raw_pl)):
                row = raw_pl.iloc[i]
                def _c(ci): return str(row.iloc[ci]).strip() if pd.notna(row.iloc[ci]) else ''
                if _c(4) != 'DE' or _c(5) != '74' or _c(10) != 'Outbound':
                    continue
                dest_country = _c(8)
                zone_cluster = _c(9)
                if not dest_country or not zone_cluster:
                    continue
                for ci, wt, unit in wt_bands_pl:
                    try:
                        price = float(row.iloc[ci])
                    except (TypeError, ValueError):
                        continue
                    if price <= 0 or price >= 9999:
                        continue
                    all_rows.append({
                        'weight_to': wt, 'zone': zone_cluster, 'unit': unit,
                        'price': price, 'country': dest_country,
                        'pricing_basis': 'EUR/kg', 'knr': '490085',
                    })
        except Exception as exc:
            print(f"  Hornschuch PL-Korrektur Lesefehler: {exc}")

    result = pd.DataFrame(all_rows) if all_rows else pd.DataFrame()
    if not result.empty:
        # Doppelte Zeilen (ggf. aus PL-Überschneidung) entfernen
        result = result.drop_duplicates(subset=['country', 'zone', 'weight_to'])
        countries = sorted(result['country'].unique().tolist())
        n_zones = result.groupby('country')['zone'].nunique()
        print(f"Hornschuch gesamt: {len(result)} Tarifzeilen, {len(countries)} Länder")
        print(f"  Länder: {countries}")
        for c in ['IT', 'PL', 'FR', 'ES', 'AT', 'PT']:
            if c in n_zones.index:
                print(f"  {c}: {n_zones[c]} Zonen/PLZ-Cluster")
    else:
        print("Hornschuch: keine Tarifzeilen geladen")
    return result


LOADERS['490085'] = load_hornschuch


# ─────────────────────────────────────────────────────────────────────────────
# Lookup-Funktionen für Helu, Bitzer, Hornschuch
# ─────────────────────────────────────────────────────────────────────────────

def _lookup_helu(row, tariff):
    """Helu (KNR 408244): EUR/100kg mit Minimum per Sendung.
    Zone-Mapping je Land:
      AT/PT  → 'PLZ N' (N = erstes Digit des PLZ)
      IT/ES  → 2-stelliger PLZ-Prefix (zero-padded)
      GR     → 'gr-athen' (PLZ-Prefix 11/12/14/16/17) oder 'gr-other'
      IE     → County-Name via _eircode_to_county()
      GB     → Zone '1'-'10' via HELU_ZONE_MAPS['GB'] (Outward-Code → Zone)
      PL     → 'Zone N' via HELU_ZONE_MAPS['PL'] (2-digit int → Zone)
      CH     → 'CH' + 2-stelliger PLZ-Prefix
    """
    _nan = pd.Series({'soll_fracht': np.nan, 'pricing_basis': 'EUR/100kg',
                      'weight_band_matched': '', 'zone_matched': '', 'min_price_tariff': np.nan})

    country = str(row.get('Empfänger Land', '')).strip().upper()
    plz     = str(row.get('Empfänger PLZ',  '')).strip()
    weight  = row.get('Tonnage (eff.)', 0)
    if pd.isna(weight) or weight <= 0:
        return _nan

    billing_kg = math.ceil(weight / 100) * 100
    d = ''.join(filter(str.isdigit, plz))

    # ── Zone bestimmen ────────────────────────────────────────────────────────
    if country in ('AT', 'PT'):
        zone = f'PLZ {d[0]}' if d else None
    elif country in ('IT', 'ES'):
        zone = d[:2].zfill(2) if len(d) >= 2 else None
    elif country == 'GR':
        if len(d) >= 2 and int(d[:2]) in {11, 12, 14, 16, 17}:
            zone = 'gr-athen'
        else:
            zone = 'gr-other'
    elif country == 'IE':
        zone = _eircode_to_county(plz)
    elif country == 'GB':
        m = re.match(r'^([A-Z]{1,2})', plz.upper())
        if m:
            area = m.group(1)
            gb_map = HELU_ZONE_MAPS.get('GB', {})
            zone = gb_map.get(area, gb_map.get(area[:1]))
        else:
            zone = None
    elif country == 'PL':
        if len(d) >= 2:
            pl_map = HELU_ZONE_MAPS.get('PL', {})
            zone = pl_map.get(int(d[:2]))
        else:
            zone = None
    elif country == 'CH':
        zone = f'CH{d[:2]}' if len(d) >= 2 else None
    else:
        return _nan

    if zone is None:
        return _nan

    # ── Tarifzeilen filtern ───────────────────────────────────────────────────
    t = tariff[(tariff['country'] == country) & (tariff['zone'] == str(zone))].copy()
    if t.empty:
        return _nan

    t['wt'] = pd.to_numeric(t['weight_to'], errors='coerce')
    t = t.dropna(subset=['wt', 'price'])

    passend = t[t['wt'] >= billing_kg]
    match = (passend.loc[passend['wt'].idxmin()] if not passend.empty
             else t.loc[t['wt'].idxmax()])

    unit  = str(match.get('unit', 'per 100 kg'))
    price = float(match['price'])
    soll  = price if 'sendung' in unit.lower() else price * billing_kg / 100

    return pd.Series({
        'soll_fracht':         soll,
        'pricing_basis':       'EUR/100kg',
        'weight_band_matched': f"bis {match['wt']:.0f} kg",
        'zone_matched':        f'{country} {zone}',
        'min_price_tariff':    np.nan,
        'base_rate':           price,   # raw rate per 100 kg (or per Sendung)
    })


def _lookup_bitzer(row, tariff):
    """Bitzer (KNR 406345): EUR/100kg mit Minimum per Sendung.
    Zone-Mapping je Land:
      AT/FR/IT/PT/ES → 'Zone N' via BITZER_ZONE_MAPS[country] (2-digit PLZ → Zone)
      BE             → BENELUX Zone 1
      NL/LU          → BENELUX Zone 2
      CH             → 'CH' + 2-stelliger PLZ-Prefix
    """
    _nan = pd.Series({'soll_fracht': np.nan, 'pricing_basis': 'EUR/100kg',
                      'weight_band_matched': '', 'zone_matched': '', 'min_price_tariff': np.nan})

    empf_land = str(row.get('Empfänger Land', '')).strip().upper()
    plz       = str(row.get('Empfänger PLZ',  '')).strip()
    weight    = row.get('Tonnage (eff.)', 0)
    if pd.isna(weight) or weight <= 0:
        return _nan

    billing_kg = math.ceil(weight / 100) * 100
    d = ''.join(filter(str.isdigit, plz))

    # ── Land → Tarif-Land + Zone ──────────────────────────────────────────────
    if empf_land in ('NL', 'LU'):
        country, zone = 'BENELUX', 'Zone 2'
    elif empf_land == 'BE':
        country, zone = 'BENELUX', 'Zone 1'
    elif empf_land == 'CH':
        country = 'CH'
        zone    = f'CH{d[:2]}' if len(d) >= 2 else None
    elif empf_land in BITZER_ZONE_MAPS:
        country = empf_land
        zone    = BITZER_ZONE_MAPS[empf_land].get(int(d[:2])) if len(d) >= 2 else None
    else:
        return _nan

    if zone is None:
        return _nan

    # ── Tarifzeilen filtern ───────────────────────────────────────────────────
    t = tariff[(tariff['country'] == country) & (tariff['zone'] == str(zone))].copy()
    if t.empty:
        return _nan

    t['wt'] = pd.to_numeric(t['weight_to'], errors='coerce')
    t = t.dropna(subset=['wt', 'price'])

    passend = t[t['wt'] >= billing_kg]
    match = (passend.loc[passend['wt'].idxmin()] if not passend.empty
             else t.loc[t['wt'].idxmax()])

    unit  = str(match.get('unit', 'per 100 kg'))
    price = float(match['price'])
    soll  = price if 'sendung' in unit.lower() else price * billing_kg / 100

    return pd.Series({
        'soll_fracht':         soll,
        'pricing_basis':       'EUR/100kg',
        'weight_band_matched': f"bis {match['wt']:.0f} kg",
        'zone_matched':        f'{country} {zone}',
        'min_price_tariff':    np.nan,
    })


# Länder in CT-SSL-WEI-P001 mit 1-stelligem PLZ-Prefix als Zone-Key
_HS_SINGLE_DIGIT = frozenset({
    'AT', 'BE', 'CH', 'DK', 'GR', 'LT', 'LU', 'LV', 'NL', 'PT', 'SI',
})


def _lookup_hornschuch(row, tariff):
    """Hornschuch (KNR 490085): EUR/kg direkt (ContiTech MegaTrans CT-SSL-WEI-P001).
    Zone-Key = PLZ-Prefix (2-stellig für IT/FR/ES/PL/…, 1-stellig für AT/BE/CH/…).
    Minimum-Band (weight_to=50, per Sendung) für Sendungen ≤ 50 kg.
    """
    _nan = pd.Series({'soll_fracht': np.nan, 'pricing_basis': 'EUR/kg',
                      'weight_band_matched': '', 'zone_matched': '', 'min_price_tariff': np.nan})

    country = str(row.get('Empfänger Land', '')).strip().upper()
    plz     = str(row.get('Empfänger PLZ',  '')).strip()
    weight  = row.get('Tonnage (eff.)', 0)
    if pd.isna(weight) or weight <= 0:
        return _nan

    d = ''.join(filter(str.isdigit, plz))

    # ── Zone aus PLZ ──────────────────────────────────────────────────────────
    if country == 'GB':
        m = re.match(r'^([A-Z]{1,2})', plz.upper())
        zone = m.group(1) if m else None
    elif country == 'IE':
        ec = plz.upper().strip()
        zone = ec[:3] if len(ec) >= 3 else None
    elif country in _HS_SINGLE_DIGIT:
        zone = d[:1] if d else None
    else:
        zone = d[:2] if len(d) >= 2 else None

    if zone is None:
        return _nan

    t = tariff[(tariff['country'] == country) & (tariff['zone'] == str(zone))].copy()
    if t.empty and country == 'PT' and d:
        # Sonderfall PT-Inseln: zone '9 (islands)' → startswith('9')
        t = tariff[(tariff['country'] == 'PT') &
                   tariff['zone'].str.startswith(d[:1])].copy()
    if t.empty:
        return _nan

    t['wt'] = pd.to_numeric(t['weight_to'], errors='coerce')
    t = t.dropna(subset=['wt', 'price'])

    # Minimum-Pauschale für ≤ 50 kg
    if weight <= 50:
        min_rows = t[t['unit'] == 'per Sendung']
        if not min_rows.empty:
            price = float(min_rows.iloc[0]['price'])
            return pd.Series({
                'soll_fracht': price, 'pricing_basis': 'EUR/kg',
                'weight_band_matched': 'minimum <50kg',
                'zone_matched': f'{country} {zone}', 'min_price_tariff': np.nan,
            })

    # Gewichtsband: kleinster weight_to ≥ weight (nur per_kg-Zeilen)
    per_kg = t[t['unit'] == 'per_kg']
    if per_kg.empty:
        per_kg = t
    passend = per_kg[per_kg['wt'] >= weight]
    match = (passend.loc[passend['wt'].idxmin()] if not passend.empty
             else per_kg.loc[per_kg['wt'].idxmax()])

    soll = weight * float(match['price'])

    return pd.Series({
        'soll_fracht':         soll,
        'pricing_basis':       'EUR/kg',
        'weight_band_matched': f"bis {match['wt']:.0f} kg",
        'zone_matched':        f'{country} {zone}',
        'min_price_tariff':    np.nan,
    })


# ─────────────────────────────────────────────────────────────────────────────
# SIKA DEUTSCHLAND (KNR 491063) — Stellplatzofferte
# ─────────────────────────────────────────────────────────────────────────────

def _sika_parse_zip_key(country: str, zip_raw) -> list:
    """Parst eine DLV-ZIP-Zelle in eine Liste von Lookup-Schlüsseln (Strings).

    ES  : 2-stellige PLZ-Prefixes (aus 'NN, NN, ...' oder 'NNxxx' oder int)
    IT  : 2-stellige Prefixes aus 'IT-NN+NN+NN'
    GB  : Outward-Area-Codes aus 'GB-XY' oder 'GB-XY-ZZ'
    PT  : Erste PLZ-Stelle aus 'PT-N'
    IE  : Routing-Key aus 'IE-XX'
    """
    if pd.isna(zip_raw):
        return []
    if isinstance(zip_raw, (int, float)):
        val = str(int(round(float(zip_raw))))
    else:
        val = str(zip_raw).strip()

    keys: list = []

    if country == 'IT':
        # 'IT-10+12', 'IT-00+58+71+80', 'IT-32+32'
        core = re.sub(r'^IT-', '', val, flags=re.I)
        for p in core.split('+'):
            p = p.strip().zfill(2)
            if p and p not in keys:
                keys.append(p)

    elif country == 'GB':
        # 'GB-AB', 'GB-DH-NE'  →  ['AB'] oder ['DH', 'NE']
        core = re.sub(r'^GB-', '', val, flags=re.I)
        for p in core.split('-'):
            p = p.strip()
            if p and p not in keys:
                keys.append(p)

    elif country == 'PT':
        # 'PT-2', 'PT-3', 'PT-4'
        p = re.sub(r'^PT-', '', val, flags=re.I).strip()
        if p:
            keys.append(p)

    elif country == 'IE':
        # 'IE-D1'
        p = re.sub(r'^IE-', '', val, flags=re.I).strip()
        if p:
            keys.append(p)

    elif country == 'ES':
        # '02, 24, 30 ,34, 37', '08', 19 (int), '20xxx', '28xxx', '45xxx'
        val_clean = re.sub(r'[xX]+', '', val)   # entferne 'xxx'-Suffix
        for token in re.split(r'[,\s]+', val_clean):
            token = token.strip()
            if re.match(r'^\d+$', token) and token not in keys:
                keys.append(token.zfill(2))

    return keys


def load_sika():
    """Lädt Sika Deutschland Tarifdaten (KNR 491063).

    Format: Stellplatzofferte — Per-Sendung-Preise für 1–10 Stellplätze.
    Länder: ES, GB, IE, IT, PT.
    Zone  = PLZ-Lookup-Key (2-digit für ES/IT, Outward-Code für GB,
            erste Stelle für PT, 'D1' für IE).
    weight_to = Anzahl Stellplätze (1–10).
    """
    if not _SIKA_DLV.exists():
        print(f"Sika DLV nicht gefunden: {_SIKA_DLV}")
        return pd.DataFrame()

    try:
        raw = pd.read_excel(_SIKA_DLV, sheet_name='Sika Export Rates 2025', header=None)
    except Exception as exc:
        print(f"Sika DLV Lesefehler: {exc}")
        return pd.DataFrame()

    # Kopfzeile mit Stellplatz-Zählern finden (1, 2, 3, ..., N in Datenspalten)
    hdr_idx = None
    stpl_cols: dict = {}     # {n_stpl (int): col_index}
    for i, row in raw.iterrows():
        counts = {int(round(v)): ci for ci, v in enumerate(row)
                  if isinstance(v, (int, float)) and not pd.isna(v) and 1 <= v <= 50}
        if len(counts) >= 5:
            hdr_idx = i
            stpl_cols = counts
            break

    if hdr_idx is None:
        print("Sika: Stellplatz-Kopfzeile nicht gefunden")
        return pd.DataFrame()

    all_rows: list = []

    for i in range(hdr_idx + 1, len(raw)):
        row_data = raw.iloc[i]
        c0 = row_data.iloc[0]
        if not isinstance(c0, str):
            continue
        country = c0.strip()
        if country not in ('ES', 'GB', 'IE', 'IT', 'PT', 'FR'):
            break   # Ende des Preisabschnitts

        zip_raw = row_data.iloc[1]
        zone_keys = _sika_parse_zip_key(country, zip_raw)
        if not zone_keys:
            continue

        for n_stpl, col_idx in stpl_cols.items():
            if col_idx >= len(row_data):
                continue
            price = row_data.iloc[col_idx]
            if price is None or isinstance(price, str) or pd.isna(price) or price <= 0:
                continue
            price = float(price)
            for zk in zone_keys:
                all_rows.append({
                    'weight_to':     float(n_stpl),
                    'zone':          zk,
                    'unit':          'per Sendung',
                    'price':         price,
                    'country':       country,
                    'pricing_basis': 'EUR/Stpl',
                    'knr':           '491063',
                })

    result = pd.DataFrame(all_rows) if all_rows else pd.DataFrame()
    countries = sorted(result['country'].unique().tolist()) if not result.empty else []
    max_stpl = int(result['weight_to'].max()) if not result.empty else 0
    print(f"Sika gesamt: {len(result)} Tarifzeilen, Länder: {countries}, max Stellplätze: {max_stpl}")
    return result


LOADERS['491063'] = load_sika


def _lookup_sika(row, tariff):
    """Sika Deutschland (KNR 491063): Stellplatz-Lookup per Sendung.

    Für n_stpl > 10: 10-Stellplatz-Rate als Untergrenze verwendet.
    """
    _nan = pd.Series({'soll_fracht': np.nan, 'pricing_basis': 'EUR/Stpl',
                      'weight_band_matched': '', 'zone_matched': '',
                      'min_price_tariff': np.nan})

    country = str(row.get('Empfänger Land', '') or '').strip().upper()
    empf_plz = str(row.get('Empfänger PLZ', '') or '').strip()

    n_stpl_raw = row.get('Stellplätze', None)
    if n_stpl_raw is None or pd.isna(n_stpl_raw) or float(n_stpl_raw) <= 0:
        # Fallback auf Stellplätze_calc (aus Lademeter abgeleitet, immer vorhanden)
        n_stpl_raw = row.get('Stellplätze_calc', None)
    if n_stpl_raw is None or pd.isna(n_stpl_raw):
        return _nan
    n_stpl_raw = float(n_stpl_raw)
    if n_stpl_raw <= 0:
        return _nan
    # DLV-Obergrenze ermitteln; darüber wird der Max-Stpl-Preis verwendet
    max_stpl = int(tariff['weight_to'].max()) if not tariff.empty else 33
    n_stpl = max(1, min(max_stpl, int(round(n_stpl_raw))))

    d = re.sub(r'\s+', '', empf_plz).upper()

    # ── Zone-Key aus PLZ ────────────────────────────────────────────────────
    if country == 'ES':
        zone_key = d[:2].zfill(2) if len(d) >= 2 else None
    elif country == 'IT':
        zone_key = d[:2].zfill(2) if len(d) >= 2 else None
    elif country == 'PT':
        zone_key = d[:1] if d else None
    elif country == 'GB':
        m = re.match(r'^([A-Z]+)', d)
        zone_key = m.group(1) if m else None
    elif country == 'IE':
        zone_key = 'D1'
    else:
        return _nan

    if zone_key is None:
        return _nan

    match = tariff[
        (tariff['country'] == country) &
        (tariff['zone'] == zone_key) &
        (tariff['weight_to'] == float(n_stpl))
    ]

    if match.empty:
        return _nan

    price = float(match.iloc[0]['price'])
    return pd.Series({
        'soll_fracht':         price,
        'pricing_basis':       'EUR/Stpl',
        'weight_band_matched': f'{n_stpl} Stpl' + (f' (cap@{max_stpl}, actual {n_stpl_raw:.0f})' if n_stpl_raw > max_stpl else ''),
        'zone_matched':        f'{country} {zone_key}',
        'min_price_tariff':    np.nan,
    })
