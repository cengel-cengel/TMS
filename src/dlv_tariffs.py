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

LOADERS['423650'] = load_herma
