"""
Bitzer Kühlmaschinenbau GmbH tariff calculator.

Two plant origins — both use **identical contractual rate values**:
  - Rottenburg:  Versender PLZ 71126 (Lauffen am Neckar) / 72108 (Rottenburg plant)
  - Schkeuditz:  Versender PLZ 04435

Origin dispatch is purely documentary; the calculator selects the correct DLV
directory based on origin_plz but the underlying rate tables are the same.

Pricing: per 100 kg, weight-based, with a minimum per Sendung per destination.
Billing weight: max(100, ceil(tonnage_kg / 100) * 100).
Caller is responsible for passing the freight-payable weight (Tonnage frpfl. if
it exceeds Tonnage eff.; for clean single-shipment rows they are equal).

Maut (DE + AT): INCLUDED in the contracted freight rate — no separate maut line.
Diesel:         Separate "Dieselfloater" surcharge (~4% of freight for 2025,
                frozen at April 2025 rate). NOT computed by this calculator.
                Appears in BI as Erlöse Diesel.

Countries implemented in this module:
  IT (Italy)  — 5 zones; DLV valid 2025-01-01 – 2025-12-31
  AT (Austria) — 7 zones; DLV valid 2025-01-01 – 2025-12-31
  FR (France) — 8 zones, zone tariff; specific destinations FR-77380 Combs La
                Ville and FR-13400 Aubagne use separate DLVs (not yet implemented).
  ES, CH, PT, NL, BE, LU — separate DLV files, not yet implemented.

DLV directory structure (year-fallback: 2026 > 2025 > root):
  data/extracted/v1/Noerpel AI/Bitzer/DLV/
    Bitzer Rottenburg/{year}/  ← primary source
    Bitzer Schkeuditz/{year}/  ← identical rates, different origin
"""
from __future__ import annotations

import math
import re
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import NamedTuple

import pandas as pd

from tms.tariff.base import TariffCalculator, TariffResult

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_BASE = Path("/home/user/TMS/data/extracted/v1/Noerpel AI/Bitzer/DLV")

_ROT_2025 = _BASE / "Bitzer Rottenburg/2025"
_SCH_2025 = _BASE / "Bitzer Schkeuditz/2025"
_ROT_2026_UPLOAD = _BASE / "Bitzer Rottenburg/2026/Upload"

# Map country code → (dlv_dir, glob).  IT uses the Upload-extended file (24 t cap).
_COUNTRY_DLV: dict[str, tuple[Path, str]] = {
    "IT": (_ROT_2026_UPLOAD, "V_FRA_7042_O_IT_ALL_Bitzer.xlsx"),
    "AT": (_ROT_2025, "*Export*sterreich*"),
    "FR": (_ROT_2025, "*Export*Frankreich*Zonentarif*"),
    "ES": (_ROT_2025, "*Export*Spanien*"),
}

_VALID_FROM_2025 = date(2025, 1, 1)
_VALID_TO_2025   = date(2025, 12, 31)

# Plants: set of known Versender PLZ → plant label
_PLANT_MAP: dict[str, str] = {
    "71126": "Rottenburg",
    "72108": "Rottenburg",
    "04435": "Schkeuditz",
}

# France-specific special destinations (not in zone tariff)
_FR_SPECIAL: dict[str, str] = {
    "77380": "Combs La Ville",
    "13400": "Aubagne",
}
_FR_SPECIAL_PATHS: dict[str, Path] = {
    "77380": _ROT_2025 / "20241213_Bitzer_Export FR-77380 Combs La Ville.xlsx",
    "13400": _ROT_2025 / "20241213_Bitzer_Export FR-13400 Aubagne.xlsx",
}


# ---------------------------------------------------------------------------
# Generic rate-table types
# ---------------------------------------------------------------------------

class _Band(NamedTuple):
    weight_limit: int          # upper bound (kg) for this bracket
    rates: dict[int, Decimal]  # zone_num → rate (per 100 kg, or flat if per_sendung)
    minimum: dict[int, Decimal] | None = None  # zone_num → minimum per Sendung
    per_sendung: bool = False  # True → rate is a flat EUR/Sendung, not per 100 kg


def _load_dlv(path: Path, sheet: str | int = 0) -> tuple[list[_Band], dict[str, int]]:
    """
    Parse a Bitzer per-country DLV sheet.

    Returns:
        bands:    weight-band list (ascending), each band has per-zone rates
        zone_map: PLZ-prefix → zone_num (2-digit, 3-digit, 5-digit prefixes)
    """
    df = pd.read_excel(path, sheet_name=sheet, header=None)

    # 1. Find zone header row (contains "Zone 1" in col 2)
    zone_header_row = None
    for i, row in df.iterrows():
        if re.search(r"Zone\s+1", str(row.iloc[2])):
            zone_header_row = i
            break
    if zone_header_row is None:
        raise ValueError(f"Cannot find zone header row in {path.name}")

    # Build col → zone_num mapping
    col_to_zone: dict[int, int] = {}
    hrow = df.iloc[zone_header_row]
    for ci, val in enumerate(hrow):
        m = re.search(r"Zone\s+(\d+)", str(val))
        if m:
            col_to_zone[ci] = int(m.group(1))

    # 2. Parse minimum row (just below header; label "Minimum" or "Mindestbetrag" in col 1)
    minimum: dict[int, Decimal] = {}
    for di in range(1, 4):
        mrow = df.iloc[zone_header_row + di]
        label = str(mrow.iloc[1]).lower()
        if "minimum" in label or "mindest" in label:
            for ci, zn in col_to_zone.items():
                try:
                    minimum[zn] = Decimal(str(float(mrow.iloc[ci])))
                except (ValueError, TypeError):
                    pass
            break

    # 3. Parse weight bands ("bis" in col 0).
    # Use enumerate for positional lookahead (to detect per-Sendung flat-rate bands).
    rows = list(df.iterrows())
    bands: list[_Band] = []
    for pos, (i, row) in enumerate(rows):
        cell0 = str(row.iloc[0]).strip().lower()
        if cell0 not in ("bis", "ab"):
            continue
        if cell0 == "ab":
            wlim = 999999  # open-ended last band (e.g. ES "ab 15001")
        else:
            try:
                wlim_raw = str(row.iloc[1]).strip()
                # Handles "21.500 kg" or "21500" etc.
                wlim = int(float(re.sub(r"[^\d]", "", wlim_raw.split()[0])))
            except (ValueError, TypeError, IndexError):
                continue
        rates: dict[int, Decimal] = {}
        for ci, zn in col_to_zone.items():
            try:
                val = float(row.iloc[ci])
                if not math.isnan(val) and val > 0:
                    rates[zn] = Decimal(str(val))
            except (ValueError, TypeError):
                pass
        # Lookahead: if the next row confirms "per Sendung" this band is a flat rate.
        per_sendung = False
        if pos + 1 < len(rows):
            _, nrow = rows[pos + 1]
            per_sendung = any("per sendung" in str(v).lower() for v in nrow)
        if rates:
            bands.append(_Band(weight_limit=wlim, rates=rates, per_sendung=per_sendung))

    bands.sort(key=lambda b: b.weight_limit)

    # 4. Parse zone → PLZ mapping table
    zone_map = _parse_zone_table(df, zone_header_row)

    return bands, zone_map, minimum


def _parse_zone_table(df: pd.DataFrame, zone_header_row: int) -> dict[str, int]:
    """
    Parse the "Zoneneinteilung" section below the rate table.

    Handles:
      - 2-digit prefixes:   "20 - 22"  → {"20","21","22"}: zone
      - 3-digit prefixes:   "330 - 337" → {"330",...,"337"}: zone  (higher priority)
      - 5-digit exact PLZ:  "91025"     → {"91025"}: zone  (highest priority)
      - Plus-separated:     "238 + 239" → {"238","239"}: zone
    Multiple spec cells per zone row; Zone 8 etc. may continue on following rows.
    """
    prefix_map: dict[str, int] = {}

    current_zone: int | None = None
    in_zone_section = False

    for i, row in df.iterrows():
        if i <= zone_header_row:
            continue
        cell0 = str(row.iloc[0]).strip()

        # Detect start of zone mapping section
        if "zonenein" in cell0.lower():
            in_zone_section = True
            continue

        if not in_zone_section:
            continue

        # Detect "Zone N" row
        zm = re.match(r"Zone\s+(\d+)", cell0, re.IGNORECASE)
        if zm:
            current_zone = int(zm.group(1))
        elif cell0 not in ("nan", "") and current_zone is not None:
            # Non-zone, non-empty col 0 means we've left the Zoneneinteilung
            # section (e.g. "Mehrkosten...", "Volumenberechnung:" footnotes).
            break

        if current_zone is None:
            continue

        # Parse PLZ specs from all non-empty cells in this row
        for ci in range(1, len(row)):
            val = str(row.iloc[ci]).strip()
            if val in ("nan", ""):
                continue
            # Skip header labels
            if "postleitzahl" in val.lower() or "zweistellig" in val.lower():
                continue

            for spec in _split_specs(val):
                for prefix in _expand_spec(spec):
                    prefix_map[prefix] = current_zone

    return prefix_map


def _split_specs(cell: str) -> list[str]:
    """Split a cell that may contain multiple PLZ specs separated by space."""
    # The cells typically contain single specs; split on whitespace to handle
    # cases like "67 - 69" already treated as one token by the outer loop.
    return [cell.strip()]


def _expand_spec(spec: str) -> list[str]:
    """
    Expand a PLZ spec into individual prefix strings.

    "20 - 22"    → ["20","21","22"]
    "330 - 337"  → ["330","331",...,"337"]
    "91025"      → ["91025"]
    "238 + 239"  → ["238","239"]
    "93"         → ["93"]
    """
    spec = spec.strip()

    # "+" separator: two or more entries
    if "+" in spec:
        result = []
        for part in spec.split("+"):
            result.extend(_expand_spec(part.strip()))
        return result

    # Range "A - B" or "A-B"
    range_m = re.match(r"^(\d+)\s*-\s*(\d+)$", spec)
    if range_m:
        start_s, end_s = range_m.group(1), range_m.group(2)
        width = max(len(start_s), len(end_s))
        start, end = int(start_s), int(end_s)
        return [str(n).zfill(width) for n in range(start, end + 1)]

    # Single value (may be 2, 3, or 5 digits)
    if re.match(r"^\d+$", spec):
        return [spec.zfill(2) if len(spec) <= 2 else spec]

    # Leading digits followed by city name (e.g. "08 Barcelona", "20 Irun", "36 Vigo")
    leading_m = re.match(r"^(\d+)", spec)
    if leading_m:
        digits = leading_m.group(1)
        return [digits.zfill(2) if len(digits) <= 2 else digits]

    return []


def _load_single_dest_dlv(path: Path, sheet: str | int = 0) -> tuple[list[_Band], Decimal]:
    """
    Parse a Bitzer single-destination DLV (one rate column, no zone map).

    All bands use zone_num=1 as a placeholder.  Per-Sendung flat rate is
    detected from "per Sendung" in the band row.  "Kompletter LKW" is mapped
    to weight_limit=999999 (open-ended FTL cap).  Out-of-order weight limits
    (e.g. "1000" typo for "10000" in FR-13400) are multiplied by 10 once.

    Rate column layout:
      "bis" rows         → col0="bis",  col1=weight, col2=rate
      "kompletter LKW"   → col0=label,  col1=rate
    """
    df = pd.read_excel(path, sheet_name=sheet, header=None)
    rows = list(df.iterrows())

    minimum = Decimal("0")
    raw: list[tuple[int, Decimal, bool]] = []  # (weight_limit, rate, per_sendung)

    for pos, (_, row) in enumerate(rows):
        cell0 = str(row.iloc[0]).strip().lower()
        cell1 = str(row.iloc[1]).strip().lower() if len(row) > 1 else ""

        # Minimum label may be in col 0 or col 1 (layout varies by DLV)
        if "minimum" in cell0 or "mindest" in cell0:
            try:
                minimum = Decimal(str(float(row.iloc[1])))
            except (ValueError, TypeError):
                pass
            continue
        if "minimum" in cell1 or "mindest" in cell1:
            try:
                minimum = Decimal(str(float(row.iloc[2])))
            except (ValueError, TypeError):
                pass
            continue

        is_bis = cell0 == "bis"
        # FTL label may be in col 0 or col 1 (layout varies)
        ftl_in_col0 = "komplett" in cell0 and "lkw" in cell0
        ftl_in_col1 = "komplett" in cell1 and "lkw" in cell1
        is_ftl = ftl_in_col0 or ftl_in_col1

        if not is_bis and not is_ftl:
            continue

        try:
            if is_ftl:
                wlim = 999999
                # Rate is one column after the label column
                rate = Decimal(str(float(row.iloc[2 if ftl_in_col1 else 1])))
            else:
                wlim = int(float(str(row.iloc[1]).strip()))
                rate = Decimal(str(float(row.iloc[2])))
        except (ValueError, TypeError, IndexError):
            continue

        per_sendung = is_ftl or any("per sendung" in str(v).lower() for v in row)
        if not per_sendung and pos + 1 < len(rows):
            _, nrow = rows[pos + 1]
            per_sendung = any("per sendung" in str(v).lower() for v in nrow)

        raw.append((wlim, rate, per_sendung))

    # Fix out-of-order weight bands (e.g. "1000" typo for "10000")
    max_seen = 0
    bands: list[_Band] = []
    for wlim, rate, ps in raw:
        if 0 < wlim < max_seen:
            wlim *= 10
        max_seen = max(max_seen, wlim)
        bands.append(_Band(weight_limit=wlim, rates={1: rate}, per_sendung=ps))

    bands.sort(key=lambda b: b.weight_limit)
    return bands, minimum


def _lookup_zone(plz: str, zone_map: dict[str, int]) -> int:
    """
    Return zone for a PLZ.  Priority: exact → 3-digit prefix → 2-digit prefix.

    Austrian PLZs are 4 digits (e.g. "4113"); Italian/French are 5 digits.
    Do NOT zero-pad before lookup — "4113"[:2] = "41" which hits "38-49" Zone 3,
    whereas zero-padding to "04113"[:2] = "04" would miss.
    """
    plz = str(plz).strip()
    # Exact match (handles 5-digit IT special: "91025")
    if plz in zone_map:
        return zone_map[plz]
    # 3-digit prefix (handles AT "330-337" override)
    if len(plz) >= 3 and plz[:3] in zone_map:
        return zone_map[plz[:3]]
    # 2-digit prefix (main path for IT/AT/FR)
    if len(plz) >= 2 and plz[:2] in zone_map:
        return zone_map[plz[:2]]
    raise LookupError(f"No Bitzer zone found for PLZ {plz!r}")


def _calc_price(
    zone: int,
    billing_kg: int,
    bands: list[_Band],
    minimum: dict[int, Decimal],
) -> tuple[Decimal, bool]:
    """
    Look up rate for (zone, billing_kg) and apply minimum.

    Returns (price, per_sendung) where per_sendung=True means the price is a
    flat EUR/Sendung rate (FTL), not derived from per-100-kg multiplication.
    """
    for band in bands:
        if band.weight_limit >= billing_kg:
            if zone not in band.rates:
                raise LookupError(f"Zone {zone} has no rate in band bis {band.weight_limit}")
            rate = band.rates[zone]
            if band.per_sendung:
                return rate, True
            price = rate * Decimal(str(billing_kg)) / Decimal("100")
            min_price = minimum.get(zone, Decimal("0"))
            return max(price, min_price), False
    raise LookupError(f"No weight band covers billing_kg={billing_kg}")


# ---------------------------------------------------------------------------
# Lazy-loaded per-country tariff cache
# ---------------------------------------------------------------------------

class _CountryTariff(NamedTuple):
    bands: list[_Band]
    zone_map: dict[str, int]
    minimum: dict[int, Decimal]
    dlv_name: str


def _find_dlv(dlv_dir: Path, glob: str) -> Path:
    # Allow upload-path matches when dlv_dir itself is the upload directory.
    allow_upload = "upload" in str(dlv_dir).lower()
    matches = [p for p in dlv_dir.glob(glob)
               if allow_upload or "upload" not in str(p).lower()]
    if not matches:
        raise FileNotFoundError(f"No file matching {glob!r} in {dlv_dir}")
    return sorted(matches)[0]


# ---------------------------------------------------------------------------
# Calculator
# ---------------------------------------------------------------------------

class BitzCalculator(TariffCalculator):
    """
    Bitzer Kühlmaschinenbau GmbH — multi-country, multi-origin tariff.

    Supported countries: IT (up to 24 t via Upload-extended DLV), AT, FR
    (zone tariff only — FR-77380 and FR-13400 use separate DLVs not yet implemented).

    Usage:
        calc = BitzCalculator()
        result = calc.calculate(
            empf_plz="40013",
            empf_land="IT",
            tonnage_kg=617.6,       # Tonnage (eff.) or (frpfl.) as appropriate
            origin_plz="71126",     # Versender PLZ
        )
    """

    customer_name = "Bitzer Kühlmaschinenbau GmbH"
    pricing_basis = "kg"

    def __init__(self) -> None:
        self._cache: dict[str, _CountryTariff] = {}

    def _get_special_dest(self, plz5: str) -> _CountryTariff:
        key = f"FR_special_{plz5}"
        if key in self._cache:
            return self._cache[key]
        path = _FR_SPECIAL_PATHS[plz5]
        bands, min_val = _load_single_dest_dlv(path)
        ct = _CountryTariff(
            bands=bands,
            zone_map={plz5: 1},   # exact 5-digit match → zone 1
            minimum={1: min_val},  # zone 1 minimum
            dlv_name=path.name,
        )
        self._cache[key] = ct
        return ct

    def _get_country(self, empf_land: str, origin_plz: str) -> _CountryTariff:
        key = empf_land.upper()
        if key in self._cache:
            return self._cache[key]

        entry = _COUNTRY_DLV.get(key)
        if entry is None:
            raise LookupError(
                f"Bitzer tariff not implemented for country {empf_land!r}. "
                f"Implemented: {sorted(_COUNTRY_DLV)}"
            )

        dlv_dir, glob = entry
        path = _find_dlv(dlv_dir, glob)
        bands, zone_map, minimum = _load_dlv(path)
        ct = _CountryTariff(
            bands=bands,
            zone_map=zone_map,
            minimum=minimum,
            dlv_name=path.name,
        )
        self._cache[key] = ct
        return ct

    def calculate(
        self,
        empf_plz: str,
        empf_land: str,
        *,
        lademeter: float | None = None,
        stellplaetze: int | None = None,
        tonnage_kg: float | None = None,
        ldm: float | None = None,
        origin_plz: str = "71126",
    ) -> TariffResult:
        if tonnage_kg is None or tonnage_kg <= 0:
            raise ValueError("tonnage_kg must be provided and > 0")

        empf_land_up = empf_land.strip().upper()

        plz5 = str(empf_plz).strip().zfill(5)
        plant = _PLANT_MAP.get(str(origin_plz).strip(), "unknown")
        billing_kg = max(100, math.ceil(tonnage_kg / 100) * 100)

        # FR special destinations use their own single-destination DLVs
        if empf_land_up == "FR" and plz5 in _FR_SPECIAL:
            ct = self._get_special_dest(plz5)
            dest_name = _FR_SPECIAL[plz5]
            basispreis, is_per_sendung = _calc_price(1, billing_kg, ct.bands, ct.minimum)
            notes = [
                f"plant={plant} (origin_plz={origin_plz})",
                f"empf_land=FR",
                f"zone=special:{dest_name}",
                f"billing_kg={billing_kg}",
            ]
            if is_per_sendung:
                notes.append("pricing=per_sendung")
            return TariffResult(
                basispreis=basispreis,
                diesel_surcharge=None,
                maut_surcharge=None,
                currency="EUR",
                tariff_file=ct.dlv_name,
                tariff_valid_from=_VALID_FROM_2025,
                tariff_valid_to=_VALID_TO_2025,
                notes=notes,
                tarifgruppe=f"bitzer_fr_special_{plz5}_{plant.lower()}",
                tariff_file_used=ct.dlv_name,
                tariff_year_used=_VALID_FROM_2025.year,
            )

        ct = self._get_country(empf_land_up, origin_plz)
        zone = _lookup_zone(empf_plz, ct.zone_map)
        basispreis, is_per_sendung = _calc_price(zone, billing_kg, ct.bands, ct.minimum)

        notes = [
            f"plant={plant} (origin_plz={origin_plz})",
            f"empf_land={empf_land_up}",
            f"zone={zone}",
            f"billing_kg={billing_kg}",
        ]
        if is_per_sendung:
            notes.append("pricing=per_sendung_ftl")

        return TariffResult(
            basispreis=basispreis,
            diesel_surcharge=None,   # separate Dieselfloater, not in DLV base
            maut_surcharge=None,     # DE+AT Maut both included in base rate
            currency="EUR",
            tariff_file=ct.dlv_name,
            tariff_valid_from=_VALID_FROM_2025,
            tariff_valid_to=_VALID_TO_2025,
            notes=notes,
            tarifgruppe=f"bitzer_{empf_land_up.lower()}_zone{zone}_{plant.lower()}",
            tariff_file_used=ct.dlv_name,
            tariff_year_used=_VALID_FROM_2025.year,
        )
