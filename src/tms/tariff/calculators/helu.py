"""
HELU-KABEL GmbH (KNR 408244) — per-100kg per-country tariff calculator.

DLV files in:
  /home/user/TMS/data/extracted/v1/Noerpel AI/Helu/DLV/

Year selection (per-country, NOT global):
  GR  → 20250520_Helukabel_Export GR erg*.xlsx  (2025 update)
  all → Export XX ab 01.12.2023*.xlsx           (2023 baseline)

Teilpartie LDM rule (effective_kg = max(t_kg, ldm * factor) when t_kg >= threshold):
  IT/ES  : threshold=2500, factor=1500 kg/LDM
  AT/PT/GB/IE/PL/CH : threshold≈2501, factor=1250 kg/LDM
  GR     : threshold=3301, factor=1650 kg/LDM

billing_kg = max(100, ceil(effective_kg / 100) * 100)
fracht = max(running_prev_max, rate_per_100kg × billing_kg / 100)

Maut included in base rates for all countries (maut_surcharge returns 0).
"""
from __future__ import annotations

import math
import re
from datetime import date
from decimal import Decimal
from pathlib import Path

import pandas as pd

from tms.tariff.base import TariffCalculator, TariffResult

_DLV_DIR = Path(
    "/home/user/TMS/data/extracted/v1/Noerpel AI/Helu/DLV"
)

# (ldm_threshold_kg, ldm_factor_kg_per_ldm)
_LDM_CONFIG: dict[str, tuple[int, int]] = {
    "IT": (2500, 1500),
    "AT": (2501, 1250),
    "ES": (2501, 1500),
    "PT": (2501, 1250),
    "GB": (2500, 1250),
    "IE": (2501, 1250),
    "PL": (2500, 1250),
    "CH": (2501, 1250),
    "GR": (3301, 1650),
}

# Cache: {country: (zone_fn, rates, valid_from, valid_to, filename)}
# rates format varies by country — accessed via zone_fn(plz) → zone_key → (flat_min, bands)
_CACHE: dict[str, tuple] = {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cell(v) -> str:
    s = str(v).strip() if v is not None else ""
    return "" if s in ("nan", "NaT", "None") else s


def _to_dec(v) -> Decimal | None:
    s = _cell(v)
    if not s or s in ("auf Anfrage", "pauschal", "0"):
        return None
    try:
        if "," in s:  # German format: "1.234,56" or "21,40"
            s = s.replace(".", "").replace(",", ".")
        # else English format: "21.4" — parse as-is
        return Decimal(str(round(float(s), 6)))
    except (ValueError, TypeError):
        return None


def _effective_kg(t_kg: float, ldm: float, threshold: int, factor: int) -> float:
    if t_kg >= threshold and ldm > 0:
        return max(t_kg, ldm * factor)
    return t_kg


def _billing_kg(eff_kg: float) -> int:
    return max(100, math.ceil(eff_kg / 100) * 100)


def _lookup_bands(flat_min: Decimal, bands: list[tuple[int, Decimal]], billing: int) -> Decimal:
    """
    Continuity lookup: fracht = max(running_prev_max, rate × billing / 100).
    Works for both standard DLVs (flat_min = min per shipment) and GR (continuity).
    """
    if billing <= 100:
        return flat_min
    prev_max = flat_min
    for bis_kg, rate in bands:
        candidate = rate * billing / 100
        if billing <= bis_kg:
            return max(prev_max, candidate)
        prev_max = max(prev_max, rate * bis_kg / 100)
    # above max band: apply last rate
    return bands[-1][1] * billing / 100


# ---------------------------------------------------------------------------
# Parser: vertical structure (IT, AT, ES-Mendaro, ES-general, PT, IE, GR)
# "vertical" = rows are weight bands, columns are zones
# Returns: {zone_key: (flat_min, [(bis_kg, rate), ...])}
# ---------------------------------------------------------------------------

def _parse_vertical(
    df: pd.DataFrame,
    header_row: int,
    min_row: int,
    band_start_row: int,
    col_start: int = 1,
    weight_col: int = 0,
    stop_marker: str = "Komplett",
) -> dict[str, tuple[Decimal, list]]:
    """Generic vertical DLV parser."""
    # Build zone_key → col_index map from header row
    zone_cols: dict[str, int] = {}
    for c in range(col_start, df.shape[1]):
        h = _cell(df.iloc[header_row, c])
        if not h:
            continue
        # Extract first numeric-or-alpha token (e.g. "26\nCremona" → "26", "PLZ 5" → "5")
        m = re.match(r"(?:PLZ\s+)?([A-Za-z0-9]+)", h)
        if m:
            zone_cols[m.group(1)] = c

    # Minimums
    flat_mins: dict[str, Decimal] = {}
    for key, c in zone_cols.items():
        v = _to_dec(df.iloc[min_row, c])
        flat_mins[key] = v if v is not None else Decimal("0")

    # Weight bands
    bands_by_zone: dict[str, list] = {k: [] for k in zone_cols}
    for ri in range(band_start_row, df.shape[0]):
        w_raw = _cell(df.iloc[ri, weight_col])
        if not w_raw or stop_marker.lower() in w_raw.lower():
            break
        # Parse weight: "- 300 kg", "300", "1.000" (German thousands), "1,000"
        w_clean = re.sub(r"[^0-9]", "", w_raw)
        if not w_clean:
            continue
        try:
            bis_kg = int(w_clean)
        except ValueError:
            continue
        for key, c in zone_cols.items():
            r = _to_dec(df.iloc[ri, c])
            if r is not None and r > 0:
                bands_by_zone[key].append((bis_kg, r))

    return {k: (flat_mins[k], bands_by_zone[k]) for k in zone_cols if bands_by_zone[k]}


# ---------------------------------------------------------------------------
# Per-country loaders
# ---------------------------------------------------------------------------

def _load_it() -> tuple:
    path = _DLV_DIR / "Export IT ab 01.12.2023 bis 31.12.2023.xlsx"
    df = pd.read_excel(path, header=None)
    rates = _parse_vertical(df, header_row=16, min_row=17, band_start_row=18)
    valid_from, valid_to = date(2023, 12, 1), date(2023, 12, 31)

    def zone_fn(plz: str) -> str:
        return re.sub(r"\s+", "", str(plz).upper())[:2]

    return zone_fn, rates, valid_from, valid_to, path.name


def _load_at() -> tuple:
    path = _DLV_DIR / "Export AT ab 01.12.2023 bis 31.12.2023.xlsx"
    df = pd.read_excel(path, header=None)
    # Header row 17: "bis kg", "PLZ 1" .. "PLZ 9"
    rates = _parse_vertical(df, header_row=17, min_row=18, band_start_row=19,
                             col_start=1, weight_col=0)
    valid_from, valid_to = date(2023, 12, 1), date(2023, 12, 31)

    def zone_fn(plz: str) -> str:
        return re.sub(r"\s+", "", str(plz))[0]

    return zone_fn, rates, valid_from, valid_to, path.name


def _load_es(plz: str) -> tuple:
    """Load ES-Mendaro for PLZ 20xxx, otherwise general ES."""
    plz2 = re.sub(r"\s+", "", str(plz).upper())[:2]
    if plz2 == "20":
        return _load_es_mendaro()
    return _load_es_general()


_ES_MENDARO_CACHE: tuple | None = None
_ES_GENERAL_CACHE: tuple | None = None


def _load_es_mendaro() -> tuple:
    global _ES_MENDARO_CACHE
    if _ES_MENDARO_CACHE is not None:
        return _ES_MENDARO_CACHE
    path = _DLV_DIR / "Export ES-Mendaro ab 01.12.2023 bis 31.12.2023.xlsx"
    df = pd.read_excel(path, header=None)
    # Row 17: "bis kg", "ES-20870"; Row 18: "Minimum"; bands from row 19
    rates = _parse_vertical(df, header_row=17, min_row=18, band_start_row=19,
                             col_start=1, weight_col=0)
    valid_from, valid_to = date(2023, 12, 1), date(2023, 12, 31)

    def zone_fn(_plz: str) -> str:
        return "ES-20870"  # single zone

    _ES_MENDARO_CACHE = (zone_fn, rates, valid_from, valid_to, path.name)
    return _ES_MENDARO_CACHE


def _load_es_general() -> tuple:
    global _ES_GENERAL_CACHE
    if _ES_GENERAL_CACHE is not None:
        return _ES_GENERAL_CACHE
    path = _DLV_DIR / "Export ES ab 01.12.2023 bis 31.12.2023.xlsx"
    df = pd.read_excel(path, sheet_name="Export Spanien", header=None)
    rates = _parse_vertical(df, header_row=16, min_row=17, band_start_row=18)
    valid_from, valid_to = date(2023, 12, 1), date(2023, 12, 31)

    def zone_fn(plz: str) -> str:
        return re.sub(r"\s+", "", str(plz).upper())[:2]

    _ES_GENERAL_CACHE = (zone_fn, rates, valid_from, valid_to, path.name)
    return _ES_GENERAL_CACHE


def _load_pt() -> tuple:
    path = _DLV_DIR / "Export PT ab 01.12.2023 bis 31.12.2023.xlsx"
    df = pd.read_excel(path, sheet_name="Tabelle1", header=None)
    rates = _parse_vertical(df, header_row=17, min_row=18, band_start_row=19,
                             col_start=1, weight_col=0)
    valid_from, valid_to = date(2023, 12, 1), date(2023, 12, 31)

    def zone_fn(plz: str) -> str:
        return re.sub(r"\s+", "", str(plz))[0]

    return zone_fn, rates, valid_from, valid_to, path.name


def _load_gb() -> tuple:
    path = _DLV_DIR / "Export GB ab 01.12.2023 bis 31.12.2023.xlsx"
    df = pd.read_excel(path, sheet_name="GB", header=None)

    # Row 17: zone descriptions, Row 18: "bis kg", Row 19: "m/m-100" (flat min)
    # Collect postcode areas per zone from row 17
    zone_areas: dict[int, list[str]] = {}
    for c in range(1, df.shape[1]):
        h = _cell(df.iloc[17, c])
        if not h:
            continue
        areas = [a.strip().upper() for a in re.split(r"[,\s]+", h) if a.strip().isalpha()]
        zone_areas[c] = areas

    # Build area → col mapping
    area_to_col: dict[str, int] = {}
    for col, areas in zone_areas.items():
        for area in areas:
            area_to_col[area] = col

    # Minimums (row 19)
    flat_mins: dict[int, Decimal] = {}
    for c in zone_areas:
        v = _to_dec(df.iloc[19, c])
        flat_mins[c] = v if v is not None else Decimal("0")

    # Weight bands (rows 20+)
    bands_by_col: dict[int, list] = {c: [] for c in zone_areas}
    for ri in range(20, df.shape[0]):
        w_raw = _cell(df.iloc[ri, 0])
        if not w_raw or "komplett" in w_raw.lower():
            break
        w_clean = re.sub(r"[^0-9]", "", w_raw)
        if not w_clean:
            continue
        try:
            bis_kg = int(w_clean)
        except ValueError:
            continue
        for c in zone_areas:
            r = _to_dec(df.iloc[ri, c])
            if r is not None and r > 0:
                bands_by_col[c].append((bis_kg, r))

    # Build rates dict keyed by col
    rates_by_col: dict[int, tuple] = {
        c: (flat_mins[c], bands_by_col[c])
        for c in zone_areas if bands_by_col[c]
    }

    valid_from, valid_to = date(2023, 12, 1), date(2023, 12, 31)

    def zone_fn(plz: str) -> str:
        plz_clean = re.sub(r"\s+", "", str(plz)).upper()
        m = re.match(r"^([A-Z]+)", plz_clean)
        area = m.group(1) if m else plz_clean
        col = area_to_col.get(area)
        if col is None:
            # Try 2-char, then 1-char prefix
            col = area_to_col.get(area[:2]) or area_to_col.get(area[:1])
        return str(col) if col else area

    return zone_fn, rates_by_col, valid_from, valid_to, path.name


def _load_ie() -> tuple:
    path = _DLV_DIR / "Export IE und Nord-IE ab 01.12.2023 bis 31.12.2023.xlsx"
    df = pd.read_excel(path, sheet_name="Tabelle1", header=None)

    # Row 17: county names in cols 1–32
    counties: dict[str, int] = {}
    for c in range(1, df.shape[1]):
        h = _cell(df.iloc[17, c])
        if h:
            counties[h] = c

    # Minimums row 18
    flat_mins: dict[str, Decimal] = {}
    for name, c in counties.items():
        v = _to_dec(df.iloc[18, c])
        flat_mins[name] = v if v is not None else Decimal("0")

    # Weight bands rows 19+
    bands_by_county: dict[str, list] = {n: [] for n in counties}
    for ri in range(19, df.shape[0]):
        w_raw = _cell(df.iloc[ri, 0])
        if not w_raw or "regelel" in w_raw.lower() or "volumen" in w_raw.lower():
            break
        w_clean = re.sub(r"[^0-9]", "", w_raw)
        if not w_clean:
            continue
        try:
            bis_kg = int(w_clean)
        except ValueError:
            continue
        for name, c in counties.items():
            r = _to_dec(df.iloc[ri, c])
            if r is not None and r > 0:
                bands_by_county[name].append((bis_kg, r))

    rates = {n: (flat_mins[n], bands_by_county[n]) for n in counties if bands_by_county[n]}
    valid_from, valid_to = date(2023, 12, 1), date(2023, 12, 31)

    # Irish Eircode routing key → county name
    _IE_ROUTING: dict[str, str] = {
        "D": "Dublin", "A": "Wicklow", "Y": "Wexford", "CW": "Carlow",
        "R": "Kildare", "KW": "Kildare", "MH": "Meath", "K": "Meath",
        "LH": "Louth", "MN": "Monaghan", "H": "Cavan", "CN": "Cavan",
        "N": "Longford", "LN": "Longford", "WH": "Westmeath", "W": "Westmeath",
        "OY": "Offaly", "LS": "Laois", "KK": "Kilkenny", "X": "Kilkenny",
        "WD": "Waterford", "C": "Cork", "V": "Kerry", "L": "Limerick",
        "LK": "Limerick", "T": "Tipperary", "E": "Clare", "G": "Galway",
        "F": "Galway", "MO": "Mayo", "RN": "Roscommon", "SL": "Sligo",
        "LM": "Leitrim", "DL": "Donegal", "F28": "Fermanagh", "BT": "Antrim",
        "BT47": "Derry", "BT6": "Down", "BT35": "Armagh",
    }

    def zone_fn(plz: str) -> str:
        plz_clean = re.sub(r"\s+", "", str(plz)).upper()
        # Try longest match first (up to 3 chars)
        for n in (3, 2, 1):
            prefix = plz_clean[:n]
            county = _IE_ROUTING.get(prefix)
            if county and county in rates:
                return county
        return plz_clean

    return zone_fn, rates, valid_from, valid_to, path.name


def _load_ch() -> tuple:
    path = _DLV_DIR / "Export CH ab 01.12.2023 bis 31.12.2023.xlsx"
    df = pd.read_excel(path, header=None)

    # Row 16: "Postcode", 100, 200, ..., 3000
    header = df.iloc[16].values
    billing_weights: list[int] = []
    for v in header[1:]:
        s = _cell(v)
        if s:
            try:
                billing_weights.append(int(float(s)))
            except (ValueError, TypeError):
                pass

    # Rows 17..99: CH code → rates per billing weight
    rates: dict[str, tuple] = {}
    for ri in range(17, df.shape[0]):
        code = _cell(df.iloc[ri, 0])
        if not code.startswith("CH"):
            break
        row_vals = df.iloc[ri].values[1:]
        flat_min: Decimal | None = None
        bands: list[tuple[int, Decimal]] = []
        for i, (bw, rv) in enumerate(zip(billing_weights, row_vals)):
            r = _to_dec(rv)
            if r is None:
                continue
            if bw == 100:
                flat_min = r  # flat per shipment (minimum)
            else:
                bands.append((bw, r))
        if flat_min is not None and bands:
            rates[code] = (flat_min, bands)

    valid_from, valid_to = date(2023, 12, 1), date(2023, 12, 31)

    def zone_fn(plz: str) -> str:
        digits = re.sub(r"\D", "", str(plz))[:2]
        return f"CH{digits}"

    return zone_fn, rates, valid_from, valid_to, path.name


def _load_pl() -> tuple:
    path = _DLV_DIR / "Export PL ab 01.12.2023 bis 31.12.2023.xlsx"
    df = pd.read_excel(path, sheet_name="Export PL", header=None)

    # Build zone mapping: 2-digit PLZ → zone number (1–7)
    # Rows 17–27 contain PLZ-0 .. PLZ-9 zone assignments
    # Row 17: Zone 1, Zone 2, ..., Zone 7 (headers in cols 0–6)
    plz2_to_zone: dict[str, int] = {}
    for ri in range(18, 28):
        row = df.iloc[ri]
        if not _cell(row.iloc[0]).startswith("PLZ"):
            break
        first_digit = _cell(row.iloc[0]).replace("PLZ", "").strip()
        for col_idx in range(1, 8):
            if col_idx >= len(row):
                break
            cell = _cell(row.iloc[col_idx])
            if not cell:
                continue
            zone_num = col_idx  # col 1 = Zone 1, col 2 = Zone 2, ...
            # Parse comma/range list of 2nd digits
            parts = re.split(r",\s*", cell)
            for part in parts:
                m = re.match(r"(\d{2})\s*-\s*(\d{2})", part)
                if m:
                    for d2 in range(int(m.group(1)), int(m.group(2)) + 1):
                        plz2_to_zone[f"{first_digit}{d2:02d}"[:2]] = zone_num
                else:
                    code = re.sub(r"\D", "", part)
                    if len(code) == 2:
                        plz2_to_zone[code] = zone_num
                    elif len(code) == 1:
                        # single digit 2nd char
                        plz2_to_zone[f"{first_digit}{code}"] = zone_num

    # Find rate rows: row 28 = "bis kg", row 29 = minimum
    band_header_row = 28
    min_row = 29
    band_start_row = 30

    # Zone columns: col 1 = Zone 1 (pauschal), cols 2–8 = Zones 2–7 + special
    flat_mins: dict[int, Decimal] = {}
    for z in range(1, 9):
        if z + 1 >= df.shape[1]:
            break
        v = _to_dec(df.iloc[min_row, z + 1])
        if v is not None:
            flat_mins[z] = v

    bands_by_zone: dict[int, list] = {z: [] for z in flat_mins}
    for ri in range(band_start_row, df.shape[0]):
        w_raw = _cell(df.iloc[ri, 0])
        if not w_raw or "komplett" in w_raw.lower() or "laufzeit" in w_raw.lower():
            break
        w_clean = re.sub(r"[^0-9]", "", w_raw)
        if not w_clean:
            continue
        try:
            bis_kg = int(w_clean)
        except ValueError:
            continue
        for z in flat_mins:
            r = _to_dec(df.iloc[ri, z + 1])
            if r is not None and r > 0:
                bands_by_zone[z].append((bis_kg, r))

    rates = {str(z): (flat_mins[z], bands_by_zone[z]) for z in flat_mins if bands_by_zone[z]}
    valid_from, valid_to = date(2023, 12, 1), date(2023, 12, 31)

    def zone_fn(plz: str) -> str:
        plz2 = re.sub(r"\s+", "", str(plz))[:2]
        z = plz2_to_zone.get(plz2, 2)  # default zone 2
        return str(z)

    return zone_fn, rates, valid_from, valid_to, path.name


def _load_gr() -> tuple:
    fname = "20250520_Helukabel_Export GR erg#U00e4nzt um Athen.xlsx"
    path = _DLV_DIR / fname
    df = pd.read_excel(path, header=None)

    # Row 17: "bis kg" + zone col 1 + zone col 2
    # Row 18: "m/m-100" flat minimum
    # Rows 19+: weight bands
    zone_cols: dict[str, int] = {}
    for c in range(1, df.shape[1]):
        h = _cell(df.iloc[17, c])
        if h and h not in ("bis kg", "per 100 kg", "pro Sendung"):
            if "then" in h:  # GR-Athen
                zone_cols["Athen"] = c
            else:
                # Header may contain multiple PLZ codes e.g. "GR-54627\nGR-57009"
                # Register each 2-digit prefix as a key pointing to same column
                for part in re.split(r"[\n\s/]+", h):
                    m = re.match(r"GR-?(\d{2})", part)
                    if m:
                        zone_cols[m.group(1)] = c

    flat_mins: dict[str, Decimal] = {}
    for key, c in zone_cols.items():
        v = _to_dec(df.iloc[18, c])
        flat_mins[key] = v if v is not None else Decimal("0")

    bands_by_zone: dict[str, list] = {k: [] for k in zone_cols}
    for ri in range(19, df.shape[0]):
        w_raw = _cell(df.iloc[ri, 0])
        if not w_raw or "komplett" in w_raw.lower() or "frachtber" in w_raw.lower():
            break
        w_clean = re.sub(r"[^0-9]", "", w_raw)
        if not w_clean:
            continue
        try:
            bis_kg = int(w_clean)
        except ValueError:
            continue
        for key, c in zone_cols.items():
            r = _to_dec(df.iloc[ri, c])
            if r is not None and r > 0:
                bands_by_zone[key].append((bis_kg, r))

    # Validity from file content
    valid_from, valid_to = date(2025, 6, 1), date(2025, 12, 31)

    # GR zone fn: PLZ 2-digit prefix
    # zone col headers are "54" (for 54xxx) and "Athen" (for 11,12,14,16,17 prefix)
    _ATHEN_PREFIXES = {"11", "12", "14", "16", "17"}

    def zone_fn(plz: str) -> str:
        plz2 = re.sub(r"\s+", "", str(plz))[:2]
        if plz2 in _ATHEN_PREFIXES:
            return "Athen"
        return plz2  # will match "54" or "57" keys

    rates = {k: (flat_mins[k], bands_by_zone[k]) for k in zone_cols if bands_by_zone[k]}
    return zone_fn, rates, valid_from, valid_to, fname


# ---------------------------------------------------------------------------
# DLV loader dispatcher
# ---------------------------------------------------------------------------

def _get_dlv(country: str, plz: str) -> tuple:
    """
    Returns (zone_fn, rates, valid_from, valid_to, filename).
    Per-country year selection: GR → 2025, all others → 2023 files.
    ES: dispatch to Mendaro or general based on PLZ.
    """
    cc = country.upper()

    # ES has PLZ-based dispatch — don't cache globally
    if cc == "ES":
        return _load_es(plz)

    if cc in _CACHE:
        return _CACHE[cc]

    loaders = {
        "IT": _load_it,
        "AT": _load_at,
        "PT": _load_pt,
        "GB": _load_gb,
        "IE": _load_ie,
        "PL": _load_pl,
        "CH": _load_ch,
        "GR": _load_gr,
    }
    if cc not in loaders:
        raise LookupError(f"No HELU DLV for country {cc!r}")

    result = loaders[cc]()
    _CACHE[cc] = result
    return result


# ---------------------------------------------------------------------------
# Calculator
# ---------------------------------------------------------------------------

class HeluCalculator(TariffCalculator):
    customer_name = "HELU-KABEL GmbH"
    pricing_basis = "kg"

    def calculate(
        self,
        empf_plz: str,
        empf_land: str,
        *,
        lademeter: float | None = None,
        stellplaetze: float | None = None,
        tonnage_kg: float | None = None,
        ldm: float | None = None,
        shipment_date: date | None = None,
    ) -> TariffResult:
        if tonnage_kg is None or tonnage_kg < 0:
            raise ValueError("tonnage_kg required and must be >= 0")

        ldm_val = lademeter if lademeter is not None else (ldm if ldm is not None else 0.0)
        cc = empf_land.upper()
        threshold, factor = _LDM_CONFIG.get(cc, (2501, 1250))

        eff = _effective_kg(tonnage_kg, ldm_val, threshold, factor)
        billing = _billing_kg(eff)

        zone_fn, rates, valid_from, valid_to, dlv_file = _get_dlv(cc, empf_plz)
        zone_key = zone_fn(empf_plz)

        entry = rates.get(zone_key)
        if entry is None:
            raise LookupError(
                f"No HELU rate for land={cc!r} plz={empf_plz!r} zone={zone_key!r}"
            )
        flat_min, bands = entry
        if not bands:
            raise LookupError(
                f"Empty bands for land={cc!r} zone={zone_key!r}"
            )

        fracht = _lookup_bands(flat_min, bands, billing)

        notes = [
            f"zone_key={zone_key}",
            f"t_kg={tonnage_kg}",
            f"ldm={ldm_val}",
            f"eff_kg={eff:.0f}",
            f"billing_kg={billing}",
            f"dlv={dlv_file}",
        ]

        return TariffResult(
            basispreis=fracht.quantize(Decimal("0.01")),
            diesel_surcharge=None,
            maut_surcharge=Decimal("0.00"),
            other_surcharges={},
            currency="EUR",
            tariff_file=dlv_file,
            tariff_valid_from=valid_from,
            tariff_valid_to=valid_to,
            notes=notes,
            tarifgruppe=f"helu_{cc.lower()}_zone{zone_key}",
            tariff_file_used=dlv_file,
            tariff_year_used=valid_from.year,
        )
