"""
top20_abw_s5_tariff_check.py  –  DLV-Based Tariff Reconciliation (s5)

Computes Soll-Erlös per POST shipment using contracted DLV rate sheets for 5 customers,
compares against AX-invoiced Erlöse Fracht, and identifies routes with >7 % underbilling.

Customers:
  423650  HERMA GmbH          – weight-based, flat per Sendung
  409480  Fischerwerke GmbH   – Stellplatz-based, flat per Sendung
  406035  GEZE GmbH           – weight-based, EUR/100 kg
  410844  EBM-Papst Mulfingen – LDM→Stellplatz, EUR/Sendung
  486073  CHT Germany GmbH    – weight-based, EUR/100 kg or flat
"""

import sys
import math
import re
import pickle
import numpy as np
import pandas as pd
from pathlib import Path
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

# ---------------------------------------------------------------------------
# Paths and constants
# ---------------------------------------------------------------------------
BASE    = Path('/home/user/TMS')
SRC_DIR = BASE / 'src'
OUT_DIR = BASE / 'output'
BI_PKL  = OUT_DIR / 'bi_top20_data.pkl'
OUT_XL  = OUT_DIR / 's5_tariff_check_2026.xlsx'

RN_MIN              = 5
MIN_UNDERBILLING_PCT = 7.0    # threshold: |underbilling| > 7 % → flag row

CUSTOMERS = {
    423650: ('HERMA GmbH',           'weight_herma'),
    409480: ('Fischerwerke GmbH',    'stellplatz'),
    406035: ('GEZE GmbH',            'weight_100kg'),
    410844: ('EBM-Papst Mulfingen',  'ldm_stpl'),
    486073: ('CHT Germany GmbH',     'weight_100kg'),
}

# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------
def _parse_kg(s):
    """Parse weight-band string 'bis 1.000 kg' → 1000.0. Handles German thousands sep."""
    s2 = str(s).replace('.', '').replace(',', '')
    m = re.search(r'(\d+)', s2)
    return float(m.group(1)) if m else np.nan


def _rn_valid(x):
    try:
        return float(str(x).replace(',', '.')) > RN_MIN
    except Exception:
        return False


# ===========================================================================
# GEZE  (KNR 406035) – import from dlv_tariffs
# ===========================================================================
sys.path.insert(0, str(SRC_DIR))
from dlv_tariffs import load_geze as _load_geze_dlv, _lookup_geze as _lookup_geze_dlv  # noqa: E402

_GEZE_TARIFF = None

def _get_geze():
    global _GEZE_TARIFF
    if _GEZE_TARIFF is None:
        _GEZE_TARIFF = _load_geze_dlv()
    return _GEZE_TARIFF


def lookup_geze(row):
    res = _lookup_geze_dlv(row, _get_geze())
    v = res.get('soll_fracht') if hasattr(res, 'get') else res['soll_fracht']
    return float(v) if pd.notna(v) else None


# ===========================================================================
# CHT  (KNR 486073) – import from dlv_tariffs; add GR special case
# ===========================================================================
from dlv_tariffs import (  # noqa: E402
    load_cht as _load_cht_dlv,
    _lookup_cht as _lookup_cht_dlv,
    CHT_ZONE_MAPS as _CHT_ZONE_MAPS,
)

_CHT_TARIFF    = None
_CHT_GR_RATES  = None   # {weight_to: (price, unit)} for single-zone GR Hauptlauf


def _get_cht():
    global _CHT_TARIFF
    if _CHT_TARIFF is None:
        _CHT_TARIFF = _load_cht_dlv()
    return _CHT_TARIFF


def _load_cht_gr_rates():
    """Parse CHT Greece Hauptlauf single-rate table (rows before zone section)."""
    fp = BASE / 'CHT' / '2026' / '20260112_CHT_Export Griechenland.xlsx'
    if not fp.exists():
        return {}
    raw = pd.read_excel(fp, sheet_name=0, header=None)
    rates = {}   # {weight_to: (price_per_100kg, unit)}
    for _, row in raw.iterrows():
        v0 = str(row.iloc[0]).strip().lower() if pd.notna(row.iloc[0]) else ''
        if 'zoneneinteilung' in v0 or 'ab speditionspartner' in str(row.iloc[0]).lower():
            break
        if v0 != 'bis':
            continue
        try:
            wt = float(re.sub(r'[^\d.]', '', str(row.iloc[1])))
        except Exception:
            continue
        # price in col 2; unit in col 3
        try:
            price = float(row.iloc[2])
        except Exception:
            continue
        unit_raw = str(row.iloc[3]).lower() if len(row) > 3 and pd.notna(row.iloc[3]) else 'per 100 kg'
        unit = 'per Sendung' if 'sendung' in unit_raw else 'per 100 kg'
        # Also handle 'ab' rows (open-ended, e.g. 'ab 20001')
        rates[wt] = (price, unit)
    return rates


def _get_cht_gr():
    global _CHT_GR_RATES
    if _CHT_GR_RATES is None:
        _CHT_GR_RATES = _load_cht_gr_rates()
    return _CHT_GR_RATES


def lookup_cht(row):
    empf_land = str(row.get('Empfänger Land', '')).upper().strip()
    gewicht   = row.get('Tonnage (eff.)', 0) or 0
    if pd.isna(gewicht) or gewicht <= 0:
        return None

    if empf_land == 'GR':
        # Special case: Greece, single-rate Hauptlauf
        rates = _get_cht_gr()
        if not rates:
            return None
        billing_kg = math.ceil(gewicht / 100) * 100
        sorted_bands = sorted(rates.items())
        match = None
        for wt, (price, unit) in sorted_bands:
            if wt >= billing_kg:
                match = (wt, price, unit)
                break
        if match is None:
            match = (*sorted_bands[-1][0:1], *sorted_bands[-1][1])
        if match is None:
            return None
        _, price, unit = match
        if 'sendung' in unit:
            return float(price)
        else:
            return float(price) * billing_kg / 100

    # Ensure CHT tariff (and zone maps) are loaded
    _ = _get_cht()
    res = _lookup_cht_dlv(row, _get_cht())
    v = res.get('soll_fracht') if hasattr(res, 'get') else res['soll_fracht']
    return float(v) if pd.notna(v) else None


# ===========================================================================
# Fischerwerke  (KNR 409480) – import from dlv_tariffs
# ===========================================================================
from dlv_tariffs import (  # noqa: E402
    load_fischerwerke as _load_fw_dlv,
    _lookup_fischer as _lookup_fw_dlv,
)

_FW_TARIFF = None

def _get_fw():
    global _FW_TARIFF
    if _FW_TARIFF is None:
        _FW_TARIFF = _load_fw_dlv()
    return _FW_TARIFF


def lookup_fischer(row):
    res = _lookup_fw_dlv(row, _get_fw())
    v = res.get('soll_fracht') if hasattr(res, 'get') else res['soll_fracht']
    return float(v) if pd.notna(v) else None


# ===========================================================================
# EBM-Papst  (KNR 410844) – fresh parser (correct stpl mapping)
# ===========================================================================

_EBM_FREIGHT = None
_EBM_TOLL    = None


def _load_ebm_sheet(fp, sheetname):
    """Parse one EBM-Papst rate sheet. Returns {dest_key: {n_stpl: price}}."""
    raw = pd.read_excel(fp, sheet_name=sheetname, header=None)
    # Row 5 (0-indexed): actual Palletspace numbers (1,2,...33)
    stpl_row = raw.iloc[5]
    col_to_stpl = {}
    for ci in range(len(stpl_row)):
        v = stpl_row.iloc[ci]
        try:
            s = int(float(str(v)))
            if 1 <= s <= 50:
                col_to_stpl[ci] = s
        except Exception:
            pass

    result = {}  # {dest_key: {n_stpl: price}}
    for idx in range(9, len(raw)):
        row = raw.iloc[idx]
        dest_raw = str(row.iloc[1]).strip() if pd.notna(row.iloc[1]) else ''
        if not dest_raw or dest_raw == 'nan':
            continue
        # Some rows have multiple destinations separated by '|'
        for dest_part in dest_raw.split('|'):
            dest_key = dest_part.strip()
            if not dest_key or dest_key == 'nan':
                continue
            if dest_key not in result:
                result[dest_key] = {}
            for ci, stpl in col_to_stpl.items():
                v = row.iloc[ci] if ci < len(row) else np.nan
                vs = str(v).strip() if pd.notna(v) else ''
                if vs in ('nan', '-', ''):
                    continue
                try:
                    price = float(vs)
                    if price > 0:
                        result[dest_key][stpl] = price
                except Exception:
                    pass
    return result


def _load_ebm_rates():
    fp = (BASE / 'EBM-Papst, Mulfingen' /
          '20260227_ebm-papst Mulfingen GmbH  Co. KG 74673 Hollenbach_Export Europa.xlsx')
    if not fp.exists():
        print("EBM-Papst Tarifdatei nicht gefunden")
        return {}, {}
    freight = _load_ebm_sheet(fp, 'Tariffs_DE_EU')
    toll    = _load_ebm_sheet(fp, 'Toll_DE_EU')
    print(f"EBM-Papst: {len(freight)} Frachtziele, {len(toll)} Tollziele geladen")
    return freight, toll


def _get_ebm():
    global _EBM_FREIGHT, _EBM_TOLL
    if _EBM_FREIGHT is None:
        _EBM_FREIGHT, _EBM_TOLL = _load_ebm_rates()
    return _EBM_FREIGHT, _EBM_TOLL


def _ebm_dest_match(dest_key, empf_land, empf_plz):
    """True if dest_key (e.g. 'IE-A92' or 'SK-913 11 | SK-913 04') matches empf_land+empf_plz."""
    for part in dest_key.split('|'):
        part = part.strip()
        m = re.match(r'^([A-Z]{2})-(.+)$', part, re.I)
        if not m:
            continue
        cntry = m.group(1).upper()
        plz_norm = re.sub(r'[\s\-]', '', m.group(2)).upper()
        if cntry != empf_land:
            continue
        min_len = min(len(empf_plz), len(plz_norm))
        if min_len >= 2 and empf_plz[:min_len] == plz_norm[:min_len]:
            return True
    return False


def lookup_ebm(row):
    empf_land = str(row.get('Empfänger Land', '')).upper().strip()
    empf_plz  = re.sub(r'[\s\-]', '', str(row.get('Empfänger PLZ', ''))).upper()
    ldm       = row.get('Lademeter', 0)
    if pd.isna(ldm) or ldm <= 0:
        return None

    n_stpl = max(1, math.ceil(float(ldm) / 0.4))
    freight, toll = _get_ebm()

    for dest_key, prices in freight.items():
        if not _ebm_dest_match(dest_key, empf_land, empf_plz):
            continue
        if not prices:
            continue
        max_stpl = max(prices)
        n_use    = min(n_stpl, max_stpl)
        # Exact match or next-higher stpl
        if n_use in prices:
            fracht = prices[n_use]
        else:
            higher = {k: v for k, v in prices.items() if k >= n_use}
            fracht = prices[min(higher)] if higher else prices[max_stpl]

        # Toll: find toll entry where toll_dest starts with dest_key (prefix match)
        toll_amt = 0.0
        dest_prefix = dest_key.split(' ')[0].upper()
        for toll_key, toll_prices in toll.items():
            if toll_key.upper().startswith(dest_prefix):
                n_toll = min(n_use, max(toll_prices)) if toll_prices else n_use
                toll_amt = toll_prices.get(n_toll, 0.0)
                break

        return fracht + toll_amt

    return None


# ===========================================================================
# HERMA  (KNR 423650) – fresh standalone parser
# ===========================================================================

_HERMA_RATES = None   # {sheet: {'weight_bands': [(col_idx, limit_kg)], 'data': DataFrame, 'sheet_type': str}}

_HERMA_FP = (BASE / 'Herma' / 'Herma Konditionen' / 'Herma Konditionen' /
             'Herma Etiketten' / '2026' /
             '20251212_Herma_Frachtraten mit VL_2026-2028_NT.xlsx')

# Map from ISO country code → HERMA sheet name
_HERMA_SHEET_MAP = {
    'AT': 'AT', 'CH': 'CH', 'EE': 'EE', 'ES': 'ES',
    'FR': 'FR', 'GB': 'GB', 'IE': 'IRL', 'IT': 'IT', 'PT': 'PT',
}


def _herma_find_header(raw):
    """Return LAST row index (within first 15 rows) that has weight-band columns.
    A header row must contain at least one cell with 'kg' (weight band label)."""
    last_found = None
    for idx in range(min(15, len(raw))):
        vals_lower = [str(v).strip().lower() for v in raw.iloc[idx] if pd.notna(v)]
        # Must have at least one weight band label 'bis X kg' — not just 'kg' in metadata
        if any(re.search(r'bis\s*[\d.]+\s*kg', v) for v in vals_lower):
            last_found = idx
    return last_found


def _herma_weight_bands(headers):
    """Extract [(col_idx, limit_kg)] from a header list."""
    bands = []
    for ci, h in enumerate(headers):
        hs = str(h)
        if re.search(r'\d', hs) and 'kg' in hs.lower():
            lim = _parse_kg(hs)
            if not np.isnan(lim):
                bands.append((ci, lim))
    return bands


def _parse_herma_pt_zones(raw):
    """Parse PT zone→PLZ-4digit-range mapping. Returns {zone_name: [(von, bis), ...]}."""
    zone_ranges = {}
    for _, row in raw.iterrows():
        v0 = str(row.iloc[0]).strip()
        if not re.match(r'Zone\s*\d+', v0, re.I):
            continue
        zone_name = v0
        ranges = []
        for ci in range(1, len(row)):
            cell = str(row.iloc[ci]).strip() if pd.notna(row.iloc[ci]) else ''
            if not cell or cell in ('nan', ''):
                continue
            # Skip parenthetical comments
            if cell.startswith('('):
                continue
            # Split on semicolons and parse each range "XXXX-YYYY"
            for part in re.split(r'[;,]', cell):
                part = part.strip().rstrip(';')
                nums = re.findall(r'\d+', part)
                if len(nums) == 2:
                    ranges.append((int(nums[0]), int(nums[1])))
                elif len(nums) == 1:
                    ranges.append((int(nums[0]), int(nums[0])))
        if ranges:
            zone_ranges[zone_name] = ranges
    return zone_ranges


def _load_herma_rates():
    """Load HERMA tariff for all country sheets. Returns dict keyed by sheet name."""
    if not _HERMA_FP.exists():
        print("HERMA Tarifdatei nicht gefunden")
        return {}

    result = {}
    for sheet in ['AT', 'CH', 'EE', 'ES', 'FR', 'GB', 'IRL', 'IT', 'PT']:
        try:
            raw = pd.read_excel(_HERMA_FP, sheet_name=sheet, header=None)
        except Exception as e:
            print(f"  HERMA {sheet}: Fehler beim Lesen – {e}")
            continue

        header_row_idx = _herma_find_header(raw)
        if header_row_idx is None:
            print(f"  HERMA {sheet}: kein Header gefunden")
            continue

        headers     = raw.iloc[header_row_idx].tolist()
        weight_bands = _herma_weight_bands(headers)

        if not weight_bands:
            print(f"  HERMA {sheet}: keine Gewichtsbänder in Header row {header_row_idx}")
            continue

        # Skip "[Unit price]" metadata row if present
        data_start = header_row_idx + 1
        if data_start < len(raw):
            first_vals = [str(v).strip().lower() for v in raw.iloc[data_start] if pd.notna(v)]
            if any('[unit price]' in v for v in first_vals):
                data_start += 1

        data = raw.iloc[data_start:].reset_index(drop=True)

        # Determine sheet_type
        if sheet == 'FR' or sheet == 'CH':
            sheet_type = 'plz_2digit'     # col 1 = exact 2-digit PLZ/dept
        elif sheet == 'GB':
            sheet_type = 'gb'             # col 1 = district code list
        elif sheet == 'IT':
            sheet_type = 'it_range'       # col 1 = text range "XX - YY" (2-digit prefixes)
        elif sheet == 'PT':
            sheet_type = 'pt_zone'        # col 1 = zone name; zone mapping in bottom rows
        elif sheet == 'IRL':
            sheet_type = 'irl_default'    # col 1 = county name; use first row as default
        else:
            sheet_type = 'von_bis'        # col 1=Von, col 2=Bis (numeric PLZ range)

        info = {
            'weight_bands': weight_bands,
            'data': data,
            'sheet_type': sheet_type,
        }

        # Pre-compute PT zone→PLZ mapping
        if sheet == 'PT':
            info['zone_ranges'] = _parse_herma_pt_zones(raw)

        result[sheet] = info
        print(f"  HERMA {sheet}: {len(data)} Zeilen, {len(weight_bands)} Gewichtsbänder, "
              f"type={sheet_type}")

    return result


def _get_herma():
    global _HERMA_RATES
    if _HERMA_RATES is None:
        _HERMA_RATES = _load_herma_rates()
    return _HERMA_RATES


def _herma_price_from_row(data_row, weight_bands, billing_weight):
    """Return flat Preis-pro-Sendung for given billing_weight from a tariff data row."""
    for col_idx, limit_kg in sorted(weight_bands, key=lambda x: x[1]):
        if limit_kg >= billing_weight:
            try:
                p = float(data_row.iloc[col_idx])
                if p > 0:
                    return p
            except Exception:
                pass
    # Fallback: highest band
    if weight_bands:
        col_idx, _ = max(weight_bands, key=lambda x: x[1])
        try:
            p = float(data_row.iloc[col_idx])
            return p if p > 0 else None
        except Exception:
            pass
    return None


def lookup_herma(row):
    empf_land = str(row.get('Empfänger Land', '')).upper().strip()
    empf_plz  = str(row.get('Empfänger PLZ', '')).strip().upper()
    tonnage   = float(row.get('Tonnage (eff.)', 0) or 0)
    ldm       = float(row.get('Lademeter', 0) or 0)
    vol       = float(row.get('Volumen', 0) or 0)

    billing_weight = max(tonnage, ldm * 1500.0, vol * 300.0)
    if billing_weight <= 0:
        return None

    sheet_name = _HERMA_SHEET_MAP.get(empf_land)
    if not sheet_name:
        return None

    rates = _get_herma()
    info  = rates.get(sheet_name)
    if info is None:
        return None

    data         = info['data']
    weight_bands = info['weight_bands']
    sheet_type   = info['sheet_type']

    if sheet_type == 'plz_2digit':
        # Col 1: exact 2-digit department/PLZ number
        plz_digits = re.findall(r'\d+', empf_plz)
        if not plz_digits:
            return None
        dept = int(plz_digits[0][:2])
        for _, data_row in data.iterrows():
            try:
                v = int(float(str(data_row.iloc[1])))
                if v == dept:
                    return _herma_price_from_row(data_row, weight_bands, billing_weight)
            except Exception:
                pass

    elif sheet_type == 'gb':
        # Col 1: comma/semicolon-separated GB outward area codes
        area_m = re.match(r'^([A-Z]{1,2})', empf_plz)
        if not area_m:
            return None
        area = area_m.group(1)
        for _, data_row in data.iterrows():
            dist_str = str(data_row.iloc[1]) if pd.notna(data_row.iloc[1]) else ''
            tokens = re.split(r'[,;\s]+', dist_str.upper())
            if area in tokens:
                return _herma_price_from_row(data_row, weight_bands, billing_weight)

    elif sheet_type == 'it_range':
        # Col 1: text range like "00 - 06" or "10 - 19" (2-digit PLZ prefix ranges)
        plz_digits = re.sub(r'[^0-9]', '', empf_plz)
        if len(plz_digits) < 2:
            return None
        try:
            plz_prefix = int(plz_digits[:2])
        except Exception:
            return None
        for _, data_row in data.iterrows():
            rng = str(data_row.iloc[1]) if pd.notna(data_row.iloc[1]) else ''
            nums = re.findall(r'\d+', rng)
            if len(nums) == 2:
                try:
                    von, bis = int(nums[0]), int(nums[1])
                    if von <= plz_prefix <= bis:
                        return _herma_price_from_row(data_row, weight_bands, billing_weight)
                except Exception:
                    pass
            elif len(nums) == 1:
                try:
                    if int(nums[0]) == plz_prefix:
                        return _herma_price_from_row(data_row, weight_bands, billing_weight)
                except Exception:
                    pass

    elif sheet_type == 'pt_zone':
        # Col 1: zone name; zone_ranges maps zone → [(von_4digit, bis_4digit), ...]
        zone_ranges = info.get('zone_ranges', {})
        plz_digits  = re.sub(r'[^0-9]', '', empf_plz)
        if len(plz_digits) < 4:
            return None
        try:
            plz_4 = int(plz_digits[:4])
        except Exception:
            return None
        # Find which zone the PLZ belongs to
        target_zone = None
        for zone_name, ranges in zone_ranges.items():
            for von, bis in ranges:
                if von <= plz_4 <= bis:
                    target_zone = zone_name
                    break
            if target_zone:
                break
        if target_zone is None:
            # Fallback: Zone 1
            target_zone = 'Zone 1'
        for _, data_row in data.iterrows():
            zone_val = str(data_row.iloc[1]).strip() if pd.notna(data_row.iloc[1]) else ''
            if zone_val.lower() == target_zone.lower():
                return _herma_price_from_row(data_row, weight_bands, billing_weight)
        # Fallback: first valid row
        for _, data_row in data.iterrows():
            p = _herma_price_from_row(data_row, weight_bands, billing_weight)
            if p:
                return p

    elif sheet_type == 'irl_default':
        # Use the first data row (all prices very similar across counties)
        for _, data_row in data.iterrows():
            p = _herma_price_from_row(data_row, weight_bands, billing_weight)
            if p:
                return p

    else:  # von_bis: AT, EE, ES
        # Col 1 = Von, Col 2 = Bis (numeric PLZ range, full integer)
        plz_digits = re.sub(r'[^0-9]', '', empf_plz)
        if not plz_digits:
            return None
        try:
            plz_int = int(plz_digits)
        except Exception:
            return None
        for _, data_row in data.iterrows():
            try:
                von = int(float(str(data_row.iloc[1])))
                bis = int(float(str(data_row.iloc[2])))
                if von <= plz_int <= bis:
                    return _herma_price_from_row(data_row, weight_bands, billing_weight)
            except Exception:
                pass

    return None


# ===========================================================================
# Dispatch: lookup_soll(knr, row) → float | None
# ===========================================================================

_LOOKUP_FNS = {
    423650: lookup_herma,
    409480: lookup_fischer,
    406035: lookup_geze,
    410844: lookup_ebm,
    486073: lookup_cht,
}


def lookup_soll(knr, row):
    """Return Soll-Fracht for a single BI row, or None if no rate found."""
    fn = _LOOKUP_FNS.get(knr)
    if fn is None:
        return None
    try:
        return fn(row)
    except Exception:
        return None


# ===========================================================================
# Per-customer analysis
# ===========================================================================

def billing_unit_str(knr):
    if knr == 409480:
        return 'Stellplätze'
    elif knr == 410844:
        return 'LDM'
    else:
        return 'kg'


def billing_dimension(knr, row):
    """Return the per-unit quantity used for rate normalisation."""
    if knr == 409480:
        stpl = row.get('Stellplätze', 0) or 0
        if pd.isna(stpl) or stpl <= 0:
            ldm = row.get('Lademeter', 0) or 0
            stpl = max(1, math.ceil(float(ldm) / 0.4)) if ldm > 0 else 1
        return max(1.0, float(stpl))
    elif knr == 410844:
        ldm = row.get('Lademeter', 0) or 0
        return max(0.4, float(ldm)) if ldm > 0 else 1.0
    elif knr == 423650:
        tonnage = float(row.get('Tonnage (eff.)', 0) or 0)
        ldm     = float(row.get('Lademeter', 0) or 0)
        vol     = float(row.get('Volumen', 0) or 0)
        bw = max(tonnage, ldm * 1500.0, vol * 300.0)
        return max(100.0, bw) / 100.0   # units of 100 kg
    else:
        # weight-based: billing in 100-kg steps
        gewicht = float(row.get('Tonnage (eff.)', 0) or 0)
        billing_kg = math.ceil(gewicht / 100) * 100 if gewicht > 0 else 100
        return max(1.0, billing_kg / 100.0)


def analyse_customer(knr, cname, bi_df):
    """
    For one customer: filter POST rows, compute Soll, identify underbilling.
    Returns DataFrame of flagged rows + summary dict.
    """
    df = bi_df[bi_df['Kunden Nr BK'] == knr].copy()
    df = df[df['periode'] == 'POST']
    df = df[df['Rechnungsnummer'].apply(_rn_valid)]

    if df.empty:
        print(f"  {cname}: keine POST-Zeilen nach Filter")
        return pd.DataFrame(), {}

    print(f"  {cname}: {len(df)} POST-Zeilen nach RN-Filter")

    # Compute Soll-Fracht
    soll_list = [lookup_soll(knr, row) for _, row in df.iterrows()]
    df = df.copy()
    df['soll_fracht'] = soll_list

    matched = df['soll_fracht'].notna().sum()
    print(f"    → {matched} Zeilen mit DLV-Rate ({len(df)-matched} ohne Match)")

    df = df[df['soll_fracht'].notna()].copy()
    if df.empty:
        return pd.DataFrame(), {}

    # Per-unit normalisation (to handle different shipment sizes)
    df['billing_dim'] = [billing_dimension(knr, row) for _, row in df.iterrows()]

    df['ist_fracht']      = pd.to_numeric(df['Erlöse Fracht'], errors='coerce').fillna(0)
    df['soll_rate']       = df['soll_fracht'] / df['billing_dim']
    df['ist_rate']        = df['ist_fracht']  / df['billing_dim']
    df['underbilling_pct'] = np.where(
        df['soll_rate'] > 0,
        (df['ist_rate'] - df['soll_rate']) / df['soll_rate'] * 100,
        np.nan,
    )
    df['expected_loss']   = df['soll_fracht'] - df['ist_fracht']

    # Flag rows with significant underbilling (ist < soll by > MIN_UNDERBILLING_PCT %)
    flagged = df[df['underbilling_pct'] < -MIN_UNDERBILLING_PCT].copy()
    print(f"    → {len(flagged)} Zeilen mit Unterfakturierung > {MIN_UNDERBILLING_PCT}%")

    if flagged.empty:
        return pd.DataFrame(), {}

    # Top-10 routes by total expected loss
    route_col = 'Ausgangsrelation Business Key'
    if route_col not in flagged.columns:
        route_col = 'Relation Ausgang'
    flagged['_route'] = flagged[route_col].fillna('UNBEKANNT')

    route_stats = (
        flagged.groupby('_route')
        .agg(
            n_underbilling=('expected_loss', 'count'),
            total_loss    =('expected_loss', 'sum'),
        )
        .reset_index()
        .sort_values('total_loss', ascending=False)
        .head(10)
    )

    # For each top route: up to 5 example rows with highest expected loss
    examples = []
    for _, rrow in route_stats.iterrows():
        rt = rrow['_route']
        route_rows = flagged[flagged['_route'] == rt].nlargest(5, 'expected_loss')
        for _, ex in route_rows.iterrows():
            examples.append(ex.to_dict() | {'_route_label': rt,
                                              '_route_n': int(rrow['n_underbilling']),
                                              '_route_total_loss': float(rrow['total_loss'])})

    return pd.DataFrame(examples), route_stats.to_dict('records')


# ===========================================================================
# Excel output
# ===========================================================================

HDR_FILL  = PatternFill('solid', fgColor='1F4E79')
HDR_FONT  = Font(color='FFFFFF', bold=True, size=10)
SUB_FILL  = PatternFill('solid', fgColor='2E75B6')
SUB_FONT  = Font(color='FFFFFF', bold=True, size=10)
ROUTE_FILL = PatternFill('solid', fgColor='D6E4F0')
ROUTE_FONT = Font(bold=True, size=10)
WARN_FILL  = PatternFill('solid', fgColor='FFE699')
THIN       = Side(style='thin', color='CCCCCC')
THIN_BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

COLS = [
    ('Ausgangsbordero',       'Ausgangsbordero',     12),
    ('Rechnungsnummer',       'Rechnung-Nr',          12),
    ('Versender Name',        'Versender',            22),
    ('Versender PLZ',         'Vers. PLZ',            10),
    ('Empfänger Name',        'Empfänger',            22),
    ('Empfänger PLZ',         'Empf. PLZ',            10),
    ('Empfänger Land',        'Land',                  6),
    ('Relation Ausgang',      'Relation',             18),
    ('Tonnage (eff.)',         'Tonnage kg',           10),
    ('Lademeter',             'LDM',                   8),
    ('Stellplätze',           'Stpl',                  6),
    ('ist_fracht',            'Ist Fracht €',         12),
    ('soll_fracht',           'Soll Fracht €',        12),
    ('underbilling_pct',      'Abw %',                 8),
    ('expected_loss',         'Verlust €',            10),
    ('Erlöse Diesel',         'Diesel €',              9),
    ('Erlöse Maut',           'Maut €',                9),
    ('Erlöse Nebengebühr',    'NK €',                  9),
    ('Erloese',               'Erlöse ges.',          12),
]


def _write_header_row(ws, row_num, texts, fill, font):
    for ci, txt in enumerate(texts, start=1):
        cell = ws.cell(row=row_num, column=ci, value=txt)
        cell.fill  = fill
        cell.font  = font
        cell.alignment = Alignment(wrap_text=False, vertical='center')
        cell.border = THIN_BORDER


def _write_data_row(ws, row_num, data_row, col_defs, warn=False):
    fill = WARN_FILL if warn else None
    for ci, (field, _, _) in enumerate(col_defs, start=1):
        v = data_row.get(field, '')
        if pd.isna(v) if isinstance(v, float) else False:
            v = ''
        cell = ws.cell(row=row_num, column=ci, value=v)
        if fill:
            cell.fill = fill
        cell.border = THIN_BORDER
        if isinstance(v, float):
            cell.number_format = '#,##0.00'


def write_excel(results):
    """results: {knr: (examples_df, route_stats)} """
    wb = Workbook()
    wb.remove(wb.active)  # remove default sheet

    for knr, (cname, billing_type) in CUSTOMERS.items():
        if knr not in results:
            continue
        examples_df, route_stats = results[knr]
        if examples_df.empty:
            continue

        # Safe sheet name (max 31 chars)
        safe_name = cname[:28].replace('/', '-').replace(':', '')
        ws = wb.create_sheet(title=safe_name)

        # Column widths
        for ci, (_, hdr, width) in enumerate(COLS, start=1):
            ws.column_dimensions[get_column_letter(ci)].width = width

        rn = 1
        # Customer header
        ws.cell(row=rn, column=1, value=f'{cname} (KNR {knr}) – {billing_type}').font = Font(bold=True, size=12)
        ws.row_dimensions[rn].height = 18
        rn += 1
        ws.cell(row=rn, column=1, value=f'Filter: POST, Rechnungsnummer > {RN_MIN}, Unterfakturierung > {MIN_UNDERBILLING_PCT}%')
        ws.cell(row=rn, column=1).font = Font(size=9, italic=True)
        rn += 2

        # Column headers
        _write_header_row(ws, rn, [h for _, h, _ in COLS], HDR_FILL, HDR_FONT)
        rn += 1

        # Group examples by route
        for rs in route_stats:
            rt = rs['_route']
            n  = rs['n_underbilling']
            total = rs['total_loss']

            # Route header row
            for ci in range(1, len(COLS) + 1):
                ws.cell(row=rn, column=ci).fill   = ROUTE_FILL
                ws.cell(row=rn, column=ci).border = THIN_BORDER
            ws.cell(row=rn, column=1, value=f'▶ {rt}')
            ws.cell(row=rn, column=1).font = ROUTE_FONT
            ws.cell(row=rn, column=12, value=f'n={n}  Ges.Verlust: {total:,.0f} €')
            ws.cell(row=rn, column=12).font = ROUTE_FONT
            rn += 1

            # Up to 5 example rows for this route
            route_examples = examples_df[examples_df['_route_label'] == rt]
            for _, ex in route_examples.iterrows():
                pct = float(ex.get('underbilling_pct', 0) or 0)
                _write_data_row(ws, rn, ex, COLS, warn=(pct < -15))
                rn += 1

        ws.freeze_panes = 'A5'
        print(f"  Sheet '{safe_name}': {rn-5} Datenzeilen geschrieben")

    wb.save(OUT_XL)
    print(f"\nOutput: {OUT_XL}")


# ===========================================================================
# Main
# ===========================================================================

def main():
    print("Lade BI-Daten …")
    with open(BI_PKL, 'rb') as fh:
        data = pickle.load(fh)
    bi = data['df']
    print(f"  {len(bi)} Zeilen geladen")

    # Pre-load all tariffs (triggers prints from dlv_tariffs loaders)
    print("\nLade DLV-Tarife …")
    print("GEZE:")
    _get_geze()
    print("CHT:")
    _get_cht()
    _get_cht_gr()
    print("Fischerwerke:")
    _get_fw()
    print("EBM-Papst:")
    _get_ebm()
    print("HERMA:")
    _get_herma()

    results = {}
    print("\nAnalyse pro Kunde …")
    for knr, (cname, billing_type) in CUSTOMERS.items():
        print(f"\n{'='*60}\n{cname} (KNR {knr})")
        examples_df, route_stats = analyse_customer(knr, cname, bi)
        if not examples_df.empty:
            results[knr] = (examples_df, route_stats)
            total_loss = examples_df['expected_loss'].sum()
            print(f"    Gesamtverlust (flagged rows): {total_loss:,.0f} €")

    if results:
        print("\nSchreibe Excel …")
        write_excel(results)
    else:
        print("\nKeine Ergebnisse – Excel nicht geschrieben")


if __name__ == '__main__':
    main()
