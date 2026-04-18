"""
HERMA GmbH (KNR 423650) — flat-per-shipment per-country tariff calculator.

Rate files (POST period Sep–Oct 2025):
  ES/IT/FR/GB/IRL/CH → 2025 BiddingMatrix Workbook_1
  PT/RS              → 2025 BiddingMatrix Workbook_4
  AT (zeros in 2025) → 2026 Haftmaterial DLV

Billing weight: max(tonnage_kg, lademeter × ldm_factor, volume_cbm × vol_factor)
  ES/AT/GB/IRL/PT : ldm_factor=1500, vol_factor=300
  IT (PLZ 38-39)  : ldm_factor=1500, vol_factor=300
  IT (other)      : ldm_factor=1250, vol_factor=250
  FR              : ldm_factor=1250, vol_factor=250
  BA/MK           : ldm_factor=1650, vol_factor=333

Rate selection: billing_weight <= 3000 → ohne VL = mit VL;
               billing_weight >  3000 → mit VL
"""
from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import NamedTuple

import openpyxl

from tms.tariff.base import TariffCalculator, TariffResult

_DLV_DIR = Path(
    "/home/user/TMS/data/extracted/v2/Herma/DLV"
)

_HAFT_2025_DIR = _DLV_DIR / "Herma Haftmaterial" / "2025"
_HAFT_2026_DIR = _DLV_DIR / "Herma Haftmaterial" / "2026"

_WB1_OHNE = _HAFT_2025_DIR / "ohne Vorholung" / "BiddingMatrix_T2307040744_Workbook_1_2023-07-04T13-49-35.xlsx"
_WB1_MIT  = _HAFT_2025_DIR / "mit Vorholung"  / "R2_BiddingMatrix_T2306201202_Workbook_1_2023-07-03T14-39-24.xlsx"
_WB4_OHNE = _HAFT_2025_DIR / "ohne Vorholung" / "BiddingMatrix_T2307041343_Workbook_4_2023-07-04T15-58-35.xlsx"
_WB4_MIT  = _HAFT_2025_DIR / "mit Vorholung"  / "R2_BiddingMatrix_T2306201202_Workbook_4_2023-07-03T14-40-12.xlsx"
_AT_OHNE  = _HAFT_2026_DIR / "20251212_Herma_Frachtraten ohne VL_2026-2028.xlsx"
_AT_MIT   = _HAFT_2026_DIR / "20251212_Herma_Frachtraten mit VL_2026-2028.xlsx"

# countries in 2025 WB1 with non-zero rates
_WB1_COUNTRIES = frozenset({"ES", "IT", "FR", "GB", "IRL", "CH"})
# countries in 2025 WB4 with non-zero rates
_WB4_COUNTRIES = frozenset({"PT", "RS", "RO", "SE", "SK", "SLO", "TR"})
# countries that use 2026 file (zeros or missing in 2025)
_AT_COUNTRIES  = frozenset({"AT", "BA", "MK", "EE", "BE", "BG", "CZ", "DE", "DK",
                             "FI", "GR", "HR", "HU", "LUX", "LT", "LV", "NL"})

# (ldm_factor, vol_factor) per country
_BILLING_FACTORS: dict[str, tuple[float, float]] = {
    "ES":  (1500.0, 300.0),
    "AT":  (1500.0, 300.0),
    "GB":  (1500.0, 300.0),
    "IRL": (1500.0, 300.0),
    "PT":  (1500.0, 300.0),
    "RS":  (1500.0, 300.0),
    "CH":  (1500.0, 300.0),
    "FR":  (1250.0, 250.0),
    "BA":  (1650.0, 333.0),
    "MK":  (1650.0, 333.0),
}

_VL_THRESHOLD = 3000.0  # billing_weight > this → use mit VL


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def _cell(v) -> str:
    s = str(v).strip() if v is not None else ""
    return "" if s in ("nan", "NaT", "None") else s


def _read_rows(path: Path, sheet: str) -> list[tuple]:
    wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
    ws = wb[sheet]
    rows = [tuple(r) for r in ws.iter_rows(values_only=True)]
    wb.close()
    return rows


def _parse_band_cols(hdr: tuple, start_col: int) -> list[tuple[int, int]]:
    """Return [(col_idx, band_kg), ...] for weight-band columns."""
    result = []
    for c, h in enumerate(hdr[start_col:], start_col):
        if h and "kg" in str(h):
            s = re.sub(r"[^0-9]", "", str(h))
            if s:
                result.append((c, int(s)))
    return result


def _lookup_band(bands: list[tuple[int, float]], billing_weight: float) -> float | None:
    """Return rate from first band where band_kg >= billing_weight."""
    for band_kg, rate in bands:
        if band_kg >= billing_weight and rate and rate != 0:
            return rate
    return None


# ---------------------------------------------------------------------------
# Sheet parsers
# ---------------------------------------------------------------------------

class _VBZEntry(NamedTuple):
    """Von–Bis–Zone entry."""
    von: int
    bis: int
    zone: str
    bands: list[tuple[int, float]]


def _parse_von_bis_zone(rows: list[tuple], hdr_row: int, data_start: int) -> list[_VBZEntry]:
    """Parse ES/AT/RS type sheets (Von, Bis, Zone, weight bands)."""
    hdr = rows[hdr_row]
    band_cols = _parse_band_cols(hdr, 4)
    result: list[_VBZEntry] = []
    for row in rows[data_start:]:
        if row[1] is None or not isinstance(row[1], (int, float)):
            break
        von, bis = int(row[1]), int(row[2])
        zone = str(row[3]).strip()
        bands = [(bk, row[c]) for c, bk in band_cols
                 if row[c] is not None and isinstance(row[c], (int, float)) and row[c] > 0]
        if bands:
            result.append(_VBZEntry(von, bis, zone, bands))
    return result


def _plz_int(plz: str) -> int | None:
    s = re.sub(r"[^0-9]", "", str(plz).strip())
    return int(s[:5]) if len(s) >= 4 else None


def _vbz_lookup(entries: list[_VBZEntry], plz: str, billing_weight: float) -> tuple[float, str] | None:
    """Return (rate, zone_str) or None."""
    plz_val = _plz_int(plz)
    if plz_val is None:
        return None
    for e in entries:
        if e.von <= plz_val <= e.bis:
            rate = _lookup_band(e.bands, billing_weight)
            if rate is not None:
                return rate, e.zone
    return None


# ---------------------------------------------------------------------------
# FR parser (2-digit PLZ prefix)
# ---------------------------------------------------------------------------

def _parse_fr(rows: list[tuple]) -> dict[str, list[tuple[int, float]]]:
    """Returns {plz2: [(band_kg, rate), ...]}."""
    hdr = rows[3]
    band_cols = _parse_band_cols(hdr, 2)
    result: dict[str, list] = {}
    for row in rows[5:]:
        if row[1] is None:
            break
        plz2 = str(int(row[1])).zfill(2)
        bands = [(bk, row[c]) for c, bk in band_cols
                 if row[c] is not None and isinstance(row[c], (int, float)) and row[c] > 0]
        if bands:
            result[plz2] = bands
    return result


def _fr_lookup(table: dict, plz: str, billing_weight: float) -> tuple[float, str] | None:
    s = re.sub(r"[^0-9]", "", str(plz).strip())
    key = s[:2].zfill(2)
    bands = table.get(key)
    if bands is None:
        return None
    rate = _lookup_band(bands, billing_weight)
    return (rate, key) if rate is not None else None


# ---------------------------------------------------------------------------
# GB parser (UK area codes)
# ---------------------------------------------------------------------------

def _parse_gb(rows: list[tuple]) -> dict[str, list[tuple[int, float]]]:
    """Returns {area_code: [(band_kg, rate), ...]}."""
    hdr = rows[4]
    band_cols = _parse_band_cols(hdr, 2)
    result: dict[str, list] = {}
    for row in rows[6:]:
        if row[1] is None or not _cell(row[1]):
            break
        area_str = _cell(row[1])
        # area_str like "DA, CV, LE, DY, WV, B, BR, ..."
        codes = [c.strip() for c in re.split(r"[,\s]+", area_str) if c.strip()]
        bands = [(bk, row[c]) for c, bk in band_cols
                 if row[c] is not None and isinstance(row[c], (int, float)) and row[c] > 0]
        for code in codes:
            if code and bands:
                result[code.upper()] = bands
    return result


def _gb_area(plz: str) -> str:
    """Extract UK area code from postcode like 'LE4 5GH' → 'LE' or 'SW1A 1AA' → 'SW'."""
    s = str(plz).strip().upper()
    m = re.match(r"^([A-Z]{1,2})\d", s)
    return m.group(1) if m else s[:2]


def _gb_lookup(table: dict, plz: str, billing_weight: float) -> tuple[float, str] | None:
    area = _gb_area(plz)
    bands = table.get(area)
    if bands is None:
        return None
    rate = _lookup_band(bands, billing_weight)
    return (rate, area) if rate is not None else None


# ---------------------------------------------------------------------------
# IT parser (two sub-tables)
# ---------------------------------------------------------------------------

class _ITTable(NamedTuple):
    ranges: list[tuple[int, int]]  # list of (plz_from_2d, plz_to_2d)
    bands: list[tuple[int, float]]
    ldm_factor: float
    vol_factor: float


def _parse_it(rows: list[tuple]) -> list[_ITTable]:
    """Parse IT sheet: returns list of _ITTable objects."""
    tables: list[_ITTable] = []

    # --- Sub-table 1: Bozen (row 4 header, row 6 data) ---
    hdr1 = rows[4]
    band_cols1 = _parse_band_cols(hdr1, 3)  # skip Bezeichnung, Plz, MM
    row6 = rows[6]
    if row6[0] == "Preis pro Sendung":
        bands1 = [(bk, row6[c]) for c, bk in band_cols1
                  if row6[c] is not None and isinstance(row6[c], (int, float)) and row6[c] > 0]
        if bands1:
            tables.append(_ITTable([(38, 39)], bands1, 1500.0, 300.0))

    # --- Sub-table 2: General Italy (row 11 header, rows 13+ data) ---
    hdr2 = rows[11]
    band_cols2 = _parse_band_cols(hdr2, 2)  # skip Bezeichnung, Plz
    for row in rows[13:]:
        if row[0] != "Preis pro Sendung":
            continue
        plz_str = _cell(row[1])
        if not plz_str:
            continue
        # parse ranges like "00 - 06", "10 - 19", "46" (single)
        nums = re.findall(r"\d+", plz_str)
        if len(nums) == 1:
            rng = [(int(nums[0]), int(nums[0]))]
        elif len(nums) == 2:
            rng = [(int(nums[0]), int(nums[1]))]
        else:
            continue
        bands = [(bk, row[c]) for c, bk in band_cols2
                 if row[c] is not None and isinstance(row[c], (int, float)) and row[c] > 0]
        if bands:
            tables.append(_ITTable(rng, bands, 1250.0, 250.0))

    return tables


def _it_lookup(tables: list[_ITTable], plz: str, billing_weight: float) -> tuple[float, str, float, float] | None:
    """Return (rate, plz2, ldm_factor, vol_factor) or None."""
    s = re.sub(r"[^0-9]", "", str(plz).strip())
    plz2 = int(s[:2]) if len(s) >= 2 else -1
    for tbl in tables:
        for lo, hi in tbl.ranges:
            if lo <= plz2 <= hi:
                rate = _lookup_band(tbl.bands, billing_weight)
                if rate is not None:
                    return rate, str(plz2).zfill(2), tbl.ldm_factor, tbl.vol_factor
    return None


# ---------------------------------------------------------------------------
# PT parser (zone names + PLZ range map)
# ---------------------------------------------------------------------------

def _parse_pt(rows: list[tuple]) -> tuple[dict[str, list[tuple[int, float]]], dict[tuple[int, int], str]]:
    """Returns (zone_rates, plz_ranges) where plz_ranges maps (lo, hi) → zone_key."""
    hdr = rows[4]
    band_cols = _parse_band_cols(hdr, 2)
    zone_rates: dict[str, list] = {}
    for row in rows[6:]:
        if row[0] != "Preis pro Sendung":
            break
        zone_key = _cell(row[1])
        bands = [(bk, row[c]) for c, bk in band_cols
                 if row[c] is not None and isinstance(row[c], (int, float)) and row[c] > 0]
        if zone_key and bands:
            zone_rates[zone_key] = bands

    # Parse zone map (rows 12+ starting with "Zone X")
    plz_ranges: dict[tuple[int, int], str] = {}
    for row in rows[12:]:
        if not row[0] or "Zone" not in str(row[0]):
            break
        zone_key = _cell(row[0])
        for cell in row[1:]:
            if cell is None:
                continue
            for m in re.finditer(r"(\d{4})-(\d{4})", str(cell)):
                lo, hi = int(m.group(1)), int(m.group(2))
                plz_ranges[(lo, hi)] = zone_key

    return zone_rates, plz_ranges


def _pt_lookup(zone_rates: dict, plz_ranges: dict, plz: str, billing_weight: float) -> tuple[float, str] | None:
    s = re.sub(r"[^0-9]", "", str(plz).strip())
    plz4 = int(s[:4]) if len(s) >= 4 else -1
    zone_key = None
    for (lo, hi), zk in plz_ranges.items():
        if lo <= plz4 <= hi:
            zone_key = zk
            break
    if zone_key is None:
        return None
    bands = zone_rates.get(zone_key)
    if bands is None:
        return None
    rate = _lookup_band(bands, billing_weight)
    return (rate, zone_key) if rate is not None else None


# ---------------------------------------------------------------------------
# IRL parser (county/city zone names)
# ---------------------------------------------------------------------------

def _parse_irl(rows: list[tuple]) -> dict[str, list[tuple[int, float]]]:
    """Returns {county_name_lower: [(band_kg, rate), ...]}."""
    hdr = rows[4]
    band_cols = _parse_band_cols(hdr, 2)
    result: dict[str, list] = {}
    for row in rows[6:]:
        if row[0] != "Preis pro Sendung":
            break
        zone_name = _cell(row[1]).lower()
        bands = [(bk, row[c]) for c, bk in band_cols
                 if row[c] is not None and isinstance(row[c], (int, float)) and row[c] > 0]
        if zone_name and bands:
            result[zone_name] = bands
    return result


# Dublin PLZ starts with D, Cork with T, etc.
_IRL_COUNTY_MAP: dict[str, str] = {
    # Eircode prefix → county name (lowercase, matching table)
    "D": "dublin", "A": "dublin", "K": "kildare",
    "T": "cork", "P": "cork",
    "H": "galway", "N": "galway",  # Gatway = Galway
    "V": "kerry",
    "R": "laois",
    "E": "tipperary",
    "W": "waterford",
    "X": "kilkenny",
    "Y": "wexford",
    "C": "cork",
    "F": "donegal",
    "L": "limerick",
    "G": "galway",
}

def _irl_lookup(table: dict, plz: str, billing_weight: float) -> tuple[float, str] | None:
    s = str(plz).strip().upper()
    m = re.match(r"^([A-Z])", s)
    prefix = m.group(1) if m else ""
    county = _IRL_COUNTY_MAP.get(prefix, "dublin")
    # Try exact county first, then try matching
    for key in [county, "gatway" if county == "galway" else county]:
        bands = table.get(key)
        if bands:
            rate = _lookup_band(bands, billing_weight)
            return (rate, key) if rate is not None else None
    # fallback: try all entries
    for key, bands in table.items():
        if county in key or key in county:
            rate = _lookup_band(bands, billing_weight)
            return (rate, key) if rate is not None else None
    return None


# ---------------------------------------------------------------------------
# Cache of parsed tables
# ---------------------------------------------------------------------------

# Key: (path_str, sheet, is_mit)
_SHEET_CACHE: dict[tuple, object] = {}


def _load_sheet(path: Path, sheet: str) -> list[tuple]:
    key = (str(path), sheet)
    if key not in _SHEET_CACHE:
        _SHEET_CACHE[key] = _read_rows(path, sheet)
    return _SHEET_CACHE[key]  # type: ignore


def _get_wb_sheet_name(cc: str) -> tuple[Path, Path, str] | None:
    """Return (ohne_path, mit_path, sheet_name) for a country code."""
    if cc in _WB1_COUNTRIES:
        sheet = "IRL" if cc == "IRL" else cc
        return _WB1_OHNE, _WB1_MIT, sheet
    if cc in _WB4_COUNTRIES:
        return _WB4_OHNE, _WB4_MIT, cc
    if cc in _AT_COUNTRIES:
        return _AT_OHNE, _AT_MIT, cc
    return None


# country → (ohne_parsed, mit_parsed, type_str, path_ohne, path_mit, valid_from, valid_to)
_COUNTRY_CACHE: dict[str, tuple] = {}


def _parse_country(cc: str) -> tuple:
    """Parse and cache rate tables for a country. Returns (ohne, mit, type, f_ohne, f_mit, vfrom, vto)."""
    if cc in _COUNTRY_CACHE:
        return _COUNTRY_CACHE[cc]

    info = _get_wb_sheet_name(cc)
    if info is None:
        raise LookupError(f"No DLV configured for country {cc!r}")
    path_ohne, path_mit, sheet = info

    # Valid date ranges
    if cc in _AT_COUNTRIES:
        vfrom, vto = date(2026, 1, 1), date(2028, 12, 31)
    else:
        vfrom, vto = date(2024, 1, 1), date(2026, 12, 31)

    rows_ohne = _load_sheet(path_ohne, sheet)
    rows_mit  = _load_sheet(path_mit, sheet)

    if cc == "FR":
        ohne_data = _parse_fr(rows_ohne)
        mit_data  = _parse_fr(rows_mit)
        ttype = "fr"
    elif cc == "GB":
        ohne_data = _parse_gb(rows_ohne)
        mit_data  = _parse_gb(rows_mit)
        ttype = "gb"
    elif cc == "IT":
        ohne_data = _parse_it(rows_ohne)
        mit_data  = _parse_it(rows_mit)
        ttype = "it"
    elif cc in ("IRL",):
        ohne_data = _parse_irl(rows_ohne)
        mit_data  = _parse_irl(rows_mit)
        ttype = "irl"
    elif cc == "PT":
        ohne_data = _parse_pt(rows_ohne)
        mit_data  = _parse_pt(rows_mit)
        ttype = "pt"
    else:
        # Von/Bis/Zone type (ES, AT, RS, MK, BA, etc.)
        hdr_row = 3 if cc not in ("ES",) else 4
        # ES uses row 4 as header (rows 0-4 in WB1), AT uses row 3
        # Detect hdr_row from actual content
        for ri, row in enumerate(rows_ohne[:8]):
            if row[0] == "Bezeichnung" or row[0] == "Bezeichung":
                hdr_row = ri
                break
        data_start = hdr_row + 2  # skip header + units row
        ohne_data = _parse_von_bis_zone(rows_ohne, hdr_row, data_start)
        mit_data  = _parse_von_bis_zone(rows_mit,  hdr_row, data_start)
        ttype = "vbz"

    result = (ohne_data, mit_data, ttype, path_ohne, path_mit, vfrom, vto)
    _COUNTRY_CACHE[cc] = result
    return result


# ---------------------------------------------------------------------------
# Billing weight calculation
# ---------------------------------------------------------------------------

def _billing_weight(cc: str, tonnage_kg: float, lademeter: float, volume_cbm: float,
                    it_plz2: int = -1) -> float:
    """Compute HERMA billing weight = max(tonnage, ldm×factor, vol×factor)."""
    if cc == "IT" and it_plz2 in (38, 39):
        ldm_f, vol_f = 1500.0, 300.0
    else:
        ldm_f, vol_f = _BILLING_FACTORS.get(cc, (1500.0, 300.0))
    ldm_weight = lademeter * ldm_f if lademeter and lademeter > 0 else 0.0
    vol_weight = volume_cbm * vol_f if volume_cbm and volume_cbm > 0 else 0.0
    return max(tonnage_kg, ldm_weight, vol_weight)


# ---------------------------------------------------------------------------
# Main rate lookup dispatcher
# ---------------------------------------------------------------------------

def _rate_lookup(cc: str, plz: str, billing_wt: float) -> tuple[float, str, Path, date, date]:
    """Return (rate, zone_info, dlv_path, valid_from, valid_to)."""
    ohne_data, mit_data, ttype, path_ohne, path_mit, vfrom, vto = _parse_country(cc)
    use_mit = billing_wt > _VL_THRESHOLD
    data = mit_data if use_mit else ohne_data
    path = path_mit if use_mit else path_ohne

    if ttype == "fr":
        result = _fr_lookup(data, plz, billing_wt)
        if result is None and use_mit:
            result = _fr_lookup(ohne_data, plz, billing_wt)
    elif ttype == "gb":
        result = _gb_lookup(data, plz, billing_wt)
        if result is None and use_mit:
            result = _gb_lookup(ohne_data, plz, billing_wt)
    elif ttype == "it":
        result_full = _it_lookup(data, plz, billing_wt)
        if result_full is None and use_mit:
            result_full = _it_lookup(ohne_data, plz, billing_wt)
        result = (result_full[0], result_full[1]) if result_full else None
    elif ttype == "irl":
        result = _irl_lookup(data, plz, billing_wt)
        if result is None and use_mit:
            result = _irl_lookup(ohne_data, plz, billing_wt)
    elif ttype == "pt":
        zone_rates, plz_ranges = data
        result = _pt_lookup(zone_rates, plz_ranges, plz, billing_wt)
        if result is None and use_mit:
            zone_rates_o, plz_ranges_o = ohne_data
            result = _pt_lookup(zone_rates_o, plz_ranges_o, plz, billing_wt)
    else:  # vbz
        result = _vbz_lookup(data, plz, billing_wt)
        if result is None and use_mit:
            result = _vbz_lookup(ohne_data, plz, billing_wt)

    if result is None:
        raise LookupError(
            f"No HERMA rate for land={cc!r} plz={plz!r} billing_wt={billing_wt:.0f}"
        )
    rate, zone_info = result
    return float(rate), zone_info, path, vfrom, vto


# ---------------------------------------------------------------------------
# IT-specific billing factor lookup
# ---------------------------------------------------------------------------

def _it_factors(plz: str) -> tuple[float, float]:
    """Return (ldm_factor, vol_factor) for an Italian PLZ."""
    s = re.sub(r"[^0-9]", "", str(plz).strip())
    plz2 = int(s[:2]) if len(s) >= 2 else 0
    if plz2 in (38, 39):
        return 1500.0, 300.0
    return 1250.0, 250.0


# ---------------------------------------------------------------------------
# TariffCalculator implementation
# ---------------------------------------------------------------------------

class HermaCalculator(TariffCalculator):
    customer_name = "HERMA GmbH"
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
        volume_cbm: float | None = None,
    ) -> TariffResult:
        if tonnage_kg is None or tonnage_kg < 0:
            raise ValueError("tonnage_kg required and must be >= 0")

        cc = empf_land.upper().strip()
        ldm_val = lademeter if lademeter is not None else (ldm if ldm is not None else 0.0)
        vol_val = volume_cbm if volume_cbm is not None else 0.0

        # Country-specific billing factors (IT uses PLZ-dependent factors)
        if cc == "IT":
            ldm_f, vol_f = _it_factors(empf_plz)
        else:
            ldm_f, vol_f = _BILLING_FACTORS.get(cc, (1500.0, 300.0))

        ldm_weight = ldm_val * ldm_f if ldm_val > 0 else 0.0
        vol_weight = vol_val * vol_f if vol_val > 0 else 0.0
        billing_wt = max(tonnage_kg, ldm_weight, vol_weight)

        rate, zone_info, dlv_path, vfrom, vto = _rate_lookup(cc, empf_plz, billing_wt)

        billing_det = (
            "ldm" if ldm_weight >= tonnage_kg and ldm_weight >= vol_weight and ldm_weight > tonnage_kg
            else ("vol" if vol_weight > tonnage_kg and vol_weight > ldm_weight else "weight")
        )

        notes = [
            f"zone={zone_info}",
            f"t_kg={tonnage_kg:.0f}",
            f"ldm={ldm_val}",
            f"vol={vol_val}",
            f"billing_wt={billing_wt:.1f}",
            f"billing_det={billing_det}",
        ]

        return TariffResult(
            basispreis=Decimal(str(round(rate, 4))).quantize(Decimal("0.0001")),
            diesel_surcharge=None,
            maut_surcharge=None,
            other_surcharges={},
            currency="EUR",
            tariff_file=dlv_path.name,
            tariff_valid_from=vfrom,
            tariff_valid_to=vto,
            notes=notes,
        )
