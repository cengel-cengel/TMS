"""
Groz-Beckert KG / Groz-Beckert EU / Ferd. Schmetz tariff calculator.

Origins:
  - 72458  Albstadt (main plant)
  - 70771 / 70794  Leinfelden-Echterdingen

Pricing modes:
  1. LTL-FTL  – LDM-based absolute price for specific outbound lanes.
     Lanes (outbound only):
       70794 (Leinfelden) → CH 4528 (Zuchwil),  toll 3%
       72458 (Albstadt)   → PT 4409-516 (Porto), toll 2%
       58640 (Iserlohn)   → PT 4409-516 (Porto), toll 2%   (Stahlrump)
     LDM rounding: ceil(ldm * 2) / 2; if rounded > 12.0 → use FTL price.

  2. General Cargo – weight-band flat rate per shipment.
     Countries: BE, CH, EE, ES, FI, FR, GB, IE, IT, MA, NL.
     Billing weight: actual tonnage_kg (find first band ≥ tonnage_kg).
     Toll: separate maut_surcharge = base_price × toll_pct.

DLV file valid: 2025-05-01 – 2026-06-30.
Diesel surcharge: external Groz-Beckert Dieselfloater – NOT computed here.
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
# Paths / constants
# ---------------------------------------------------------------------------

_DLV_PATH = Path(
    "/home/user/TMS/data/extracted/v1/Noerpel AI/Groz Beckert/DLV/2025/"
    "20250408_Erka_Groz Beckert_Templates_LKW Ausschreibung_01.05.25 - 30.06.26.xlsx"
)

_VALID_FROM = date(2025, 5, 1)
_VALID_TO   = date(2026, 6, 30)

# Known origin PLZs and their canonical labels
_ORIGIN_MAP: dict[str, str] = {
    "72458": "Albstadt",
    "70771": "Leinfelden",
    "70794": "Leinfelden",
    "58640": "Iserlohn",
}

# GC weight bands (col indices 7-42, 36 bands)
_GC_WEIGHT_COL_START = 7
_GC_WEIGHT_COL_END   = 43   # exclusive → cols 7..42
_GC_TOLL_COL         = 43   # col index 43

# LTL-FTL column layout
_LTL_FROM_PLZ_COL    = 1
_LTL_FROM_ISO_COL    = 3
_LTL_TO_ISO_COL      = 6
_LTL_TO_PLZ_COL      = 7
_LTL_LDM_COL_START   = 10
_LTL_LDM_COL_END     = 33   # cols 10..32 → 23 LDM steps (1.0..12.0)
_LTL_FTL_COL         = 33
_LTL_TOLL_COL        = 34


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------

class _GcRow(NamedTuple):
    iso: str          # destination ISO-2
    plz_spec: str     # raw spec string (e.g. "10-29, 70-99", "Rest", "Alle")
    prices: list[Decimal]   # 36 prices indexed by band position
    toll_pct: Decimal


class _LtlRow(NamedTuple):
    from_plz: str
    from_iso: str
    to_iso: str
    to_plz: str
    ldm_prices: list[Decimal]  # 23 values for 1.0..12.0
    ftl_price: Decimal
    toll_pct: Decimal


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _to_decimal(val) -> Decimal | None:
    try:
        f = float(val)
        if math.isnan(f):
            return None
        return Decimal(str(round(f, 6)))
    except (ValueError, TypeError):
        return None


def _parse_gc(df: pd.DataFrame) -> tuple[list[float], list[_GcRow]]:
    """Parse General Cargo sheet. Returns (weight_limits, rows)."""
    # Row 1: weight limits (cols 7-42)
    weight_limits: list[float] = []
    for ci in range(_GC_WEIGHT_COL_START, _GC_WEIGHT_COL_END):
        v = _to_decimal(df.iloc[1, ci])
        if v is not None:
            weight_limits.append(float(v))

    rows: list[_GcRow] = []
    for ri in range(3, len(df)):
        row = df.iloc[ri]
        iso = str(row.iloc[5]).strip().upper()
        if iso in ("NAN", ""):
            break
        plz_spec = str(row.iloc[6]).strip()
        prices: list[Decimal] = []
        for ci in range(_GC_WEIGHT_COL_START, _GC_WEIGHT_COL_END):
            p = _to_decimal(row.iloc[ci])
            prices.append(p if p is not None else Decimal("0"))
        toll = _to_decimal(row.iloc[_GC_TOLL_COL]) or Decimal("0")
        rows.append(_GcRow(iso=iso, plz_spec=plz_spec, prices=prices, toll_pct=toll))

    return weight_limits, rows


def _parse_ltl(df: pd.DataFrame) -> tuple[list[float], list[_LtlRow]]:
    """Parse LTL-FTL sheet. Returns (ldm_steps, rows)."""
    # Row 1: LDM steps (cols 10-32)
    ldm_steps: list[float] = []
    for ci in range(_LTL_LDM_COL_START, _LTL_LDM_COL_END + 1):
        v = _to_decimal(df.iloc[1, ci])
        if v is not None:
            ldm_steps.append(float(v))

    rows: list[_LtlRow] = []
    for ri in range(3, len(df)):
        row = df.iloc[ri]
        from_iso_raw = str(row.iloc[_LTL_FROM_ISO_COL]).strip().upper()
        if from_iso_raw in ("NAN", ""):
            break
        from_plz = str(row.iloc[_LTL_FROM_PLZ_COL]).strip()
        to_iso   = str(row.iloc[_LTL_TO_ISO_COL]).strip().upper()
        to_plz   = str(row.iloc[_LTL_TO_PLZ_COL]).strip()

        ldm_prices: list[Decimal] = []
        for ci in range(_LTL_LDM_COL_START, _LTL_LDM_COL_END + 1):
            p = _to_decimal(row.iloc[ci])
            ldm_prices.append(p if p is not None else Decimal("0"))

        ftl = _to_decimal(row.iloc[_LTL_FTL_COL]) or Decimal("0")
        toll = _to_decimal(row.iloc[_LTL_TOLL_COL]) or Decimal("0")

        rows.append(_LtlRow(
            from_plz=from_plz,
            from_iso=from_iso_raw,
            to_iso=to_iso,
            to_plz=to_plz,
            ldm_prices=ldm_prices,
            ftl_price=ftl,
            toll_pct=toll,
        ))

    return ldm_steps, rows


# ---------------------------------------------------------------------------
# PLZ zone matching for General Cargo
# ---------------------------------------------------------------------------

def _expand_numeric_ranges(spec: str) -> list[tuple[int, int]]:
    """
    Parse a comma-separated spec of 2-digit numeric ranges/values.

    "10-29, 70-99"  → [(10,29), (70,99)]
    "50, 59"        → [(50,50), (59,59)]
    "Alle"          → [] (caller checks separately)
    """
    ranges: list[tuple[int, int]] = []
    for part in re.split(r"[,;]+", spec):
        part = part.strip()
        if not part:
            continue
        m = re.match(r"^(\d+)\s*-\s*(\d+)$", part)
        if m:
            ranges.append((int(m.group(1)), int(m.group(2))))
        elif re.match(r"^\d+$", part):
            v = int(part)
            ranges.append((v, v))
    return ranges


def _plz_matches_numeric_spec(plz: str, spec: str) -> bool:
    """
    Match the first 2 digits of a numeric PLZ against a spec string.
    Handles "Alle", "Rest" (never called for those — caller checks).
    """
    spec_stripped = spec.strip()
    if spec_stripped.lower() in ("alle", "all"):
        return True
    plz_digits = re.sub(r"[^0-9]", "", plz)
    if len(plz_digits) < 2:
        return False
    prefix = int(plz_digits[:2])
    for lo, hi in _expand_numeric_ranges(spec_stripped):
        if lo <= prefix <= hi:
            return True
    return False


def _extract_gb_area_code(plz: str) -> str:
    """
    Extract the alphabetic area code from a UK postcode.
    "B12 3AB" → "B", "CM1 2AB" → "CM", "SW1A 1AA" → "SW"
    Handles no-space variants too.
    """
    m = re.match(r"^([A-Za-z]{1,2})", plz.strip())
    return m.group(1).upper() if m else ""


def _plz_matches_gb_spec(plz: str, spec: str) -> bool:
    """Match GB area code against comma-separated list like 'B, CM, CV, ...'"""
    area = _extract_gb_area_code(plz)
    if not area:
        return False
    codes = [c.strip().upper() for c in re.split(r"[,;]+", spec) if c.strip()]
    return area in codes


def _find_gc_row(
    plz: str,
    iso: str,
    dest_city: str | None,
    gc_rows: list[_GcRow],
) -> _GcRow:
    """
    Find the matching General Cargo row for (plz, iso).

    Priority: specific spec match > "Rest"/"Alle" fallback.
    For MA: match by city name.
    For GB: match by area code.
    For numeric countries: match 2-digit prefix.
    """
    iso_up = iso.strip().upper()
    candidates = [r for r in gc_rows if r.iso == iso_up]
    if not candidates:
        raise LookupError(f"No GC tariff row for ISO={iso_up!r}")

    # For countries with a single "Alle" zone
    if len(candidates) == 1 and candidates[0].plz_spec.strip().lower() in ("alle", "all"):
        return candidates[0]

    # MA: match by city name
    if iso_up == "MA":
        city_lower = (dest_city or plz).strip().lower()
        for row in candidates:
            spec_lower = row.plz_spec.strip().lower()
            if spec_lower in city_lower or city_lower in spec_lower:
                return row
        # fallback
        for row in candidates:
            if row.plz_spec.strip().lower() in ("rest", "alle"):
                return row
        return candidates[0]

    # GB: alphabetic area code
    if iso_up == "GB":
        rest_row: _GcRow | None = None
        for row in candidates:
            spec = row.plz_spec.strip().lower()
            if spec == "rest":
                rest_row = row
            elif _plz_matches_gb_spec(plz, row.plz_spec):
                return row
        if rest_row:
            return rest_row
        return candidates[0]

    # Numeric countries (IT, BE, CH, ES, FR, NL, FI, EE, IE)
    rest_row = None
    alle_row = None
    for row in candidates:
        spec = row.plz_spec.strip().lower()
        if spec in ("rest",):
            rest_row = row
        elif spec in ("alle", "all"):
            alle_row = row
        elif _plz_matches_numeric_spec(plz, row.plz_spec):
            return row

    if alle_row:
        return alle_row
    if rest_row:
        return rest_row
    raise LookupError(f"No GC zone match for PLZ={plz!r}, ISO={iso_up!r}")


# ---------------------------------------------------------------------------
# LTL-FTL lane matching
# ---------------------------------------------------------------------------

def _round_ldm(ldm: float) -> float:
    """Round LDM up to nearest 0.5 step."""
    return math.ceil(ldm * 2) / 2


def _ltl_price(ldm_rounded: float, row: _LtlRow, ldm_steps: list[float]) -> Decimal:
    """Return absolute price for a rounded LDM value from an LTL-FTL lane row."""
    if ldm_rounded > 12.0:
        return row.ftl_price
    for idx, step in enumerate(ldm_steps):
        if abs(step - ldm_rounded) < 1e-6:
            return row.ldm_prices[idx]
    # Fallback: find first step >= ldm_rounded
    for idx, step in enumerate(ldm_steps):
        if step >= ldm_rounded - 1e-6:
            return row.ldm_prices[idx]
    return row.ftl_price


def _find_ltl_lane(
    origin_plz: str,
    dest_iso: str,
    ltl_rows: list[_LtlRow],
) -> _LtlRow | None:
    """
    Return the outbound LTL-FTL lane matching (origin_plz, dest_iso), or None.
    Leinfelden: accept both 70771 and 70794 as equivalent to lane from_plz=70794.
    """
    origin_norm = str(origin_plz).strip()
    # Normalise Leinfelden variants
    if origin_norm == "70771":
        origin_norm = "70794"
    dest_iso_up = dest_iso.strip().upper()
    for row in ltl_rows:
        # Skip inbound lanes (from_iso != DE is an outbound indicator, but
        # more reliably: skip rows where from_iso is not DE)
        if row.from_iso != "DE":
            continue
        if row.from_plz == origin_norm and row.to_iso == dest_iso_up:
            return row
    return None


# ---------------------------------------------------------------------------
# Lazy-loaded data cache
# ---------------------------------------------------------------------------

class _GBData(NamedTuple):
    weight_limits: list[float]
    gc_rows: list[_GcRow]
    ldm_steps: list[float]
    ltl_rows: list[_LtlRow]


_DATA_CACHE: _GBData | None = None


def _load_data() -> _GBData:
    global _DATA_CACHE
    if _DATA_CACHE is not None:
        return _DATA_CACHE

    gc_df  = pd.read_excel(_DLV_PATH, sheet_name="General Cargo", header=None)
    ltl_df = pd.read_excel(_DLV_PATH, sheet_name="LTL-FTL",       header=None)

    weight_limits, gc_rows = _parse_gc(gc_df)
    ldm_steps, ltl_rows    = _parse_ltl(ltl_df)

    _DATA_CACHE = _GBData(
        weight_limits=weight_limits,
        gc_rows=gc_rows,
        ldm_steps=ldm_steps,
        ltl_rows=ltl_rows,
    )
    return _DATA_CACHE


# ---------------------------------------------------------------------------
# Calculator
# ---------------------------------------------------------------------------

class GrozBeckertCalculator(TariffCalculator):
    """
    Groz-Beckert KG / Groz-Beckert EU / Ferd. Schmetz tariff calculator.

    Pricing modes:
      - LTL-FTL (LDM-based absolute) for specific lanes when lademeter is given
      - General Cargo (weight-band flat rate) for all other shipments

    Usage::

        calc = GrozBeckertCalculator()
        result = calc.calculate(
            empf_plz="4409-516",
            empf_land="PT",
            tonnage_kg=1524.0,
            lademeter=2.5,
            origin_plz="72458",
        )
    """

    customer_name = "Groz-Beckert KG"
    pricing_basis = "lademeter"

    def __init__(self) -> None:
        pass  # data loaded lazily on first calculate()

    def calculate(
        self,
        empf_plz: str,
        empf_land: str,
        *,
        lademeter: float | None = None,
        stellplaetze: int | None = None,
        tonnage_kg: float | None = None,
        ldm: float | None = None,
        origin_plz: str = "72458",
        dest_city: str | None = None,
        **kwargs,
    ) -> TariffResult:
        """
        Calculate tariff for a Groz-Beckert shipment.

        Parameters
        ----------
        empf_plz    : destination postal code
        empf_land   : destination ISO-2 country code
        lademeter   : loading meters (for LTL-FTL lane lookup); also accept ldm=
        tonnage_kg  : actual weight in kg (for General Cargo band lookup)
        origin_plz  : sender PLZ (default 72458 Albstadt)
        dest_city   : destination city (used for MA zone lookup)
        """
        # Accept ldm= as alias for lademeter=
        effective_ldm = lademeter if lademeter is not None else ldm

        data = _load_data()
        notes: list[str] = []

        origin_norm = str(origin_plz).strip()
        origin_label = _ORIGIN_MAP.get(origin_norm, f"unknown ({origin_norm})")
        if origin_label.startswith("unknown"):
            notes.append(f"warning=origin_plz {origin_norm!r} not in known list; using GC rates")

        empf_land_up = empf_land.strip().upper()
        empf_plz_s   = str(empf_plz).strip()

        # 1. Try LTL-FTL lane if lademeter provided
        ltl_lane = None
        if effective_ldm is not None and effective_ldm > 0:
            ltl_lane = _find_ltl_lane(origin_norm, empf_land_up, data.ltl_rows)

        if ltl_lane is not None:
            # LTL-FTL pricing
            ldm_rounded = _round_ldm(effective_ldm)
            base_price  = _ltl_price(ldm_rounded, ltl_lane, data.ldm_steps)
            toll_pct    = ltl_lane.toll_pct
            maut        = (base_price * toll_pct).quantize(Decimal("0.01"))

            notes += [
                f"mode=LTL-FTL",
                f"origin={origin_label} ({origin_norm})",
                f"lane={ltl_lane.from_plz}→{ltl_lane.to_iso} {ltl_lane.to_plz}",
                f"billing_ldm={ldm_rounded:.1f} (raw={effective_ldm})",
                f"toll_pct={float(toll_pct)*100:.1f}%",
            ]
            if tonnage_kg is not None:
                notes.append(f"tonnage_kg={tonnage_kg}")

            return TariffResult(
                basispreis=base_price,
                maut_surcharge=maut,
                diesel_surcharge=None,
                currency="EUR",
                tariff_file=_DLV_PATH.name,
                tariff_valid_from=_VALID_FROM,
                tariff_valid_to=_VALID_TO,
                notes=notes,
                tarifgruppe=f"groz_beckert_lane_{ltl_lane.from_plz}_{ltl_lane.to_iso.lower()}",
                tariff_file_used=_DLV_PATH.name,
                tariff_year_used=_VALID_FROM.year,
            )

        # 2. General Cargo pricing
        if tonnage_kg is None or tonnage_kg <= 0:
            raise ValueError(
                "tonnage_kg must be provided and > 0 for General Cargo pricing "
                "(or supply lademeter for LTL-FTL lanes)"
            )

        gc_row = _find_gc_row(empf_plz_s, empf_land_up, dest_city, data.gc_rows)

        # Find first weight band where band_limit >= tonnage_kg
        band_idx: int | None = None
        for i, wlim in enumerate(data.weight_limits):
            if wlim >= tonnage_kg:
                band_idx = i
                break

        if band_idx is None:
            # Weight exceeds all bands – use last band
            band_idx = len(data.weight_limits) - 1
            notes.append(
                f"warning=tonnage_kg {tonnage_kg} exceeds max band "
                f"{data.weight_limits[-1]}; using last band"
            )

        base_price = gc_row.prices[band_idx]
        toll_pct   = gc_row.toll_pct
        maut       = (base_price * toll_pct).quantize(Decimal("0.01"))

        # Determine zone description for notes
        zone_label = gc_row.plz_spec

        notes += [
            f"mode=GC",
            f"origin={origin_label} ({origin_norm})",
            f"dest_zone={zone_label}",
            f"billing_kg={tonnage_kg}",
            f"band_limit={data.weight_limits[band_idx]}",
            f"toll_pct={float(toll_pct)*100:.1f}%",
        ]

        return TariffResult(
            basispreis=base_price,
            maut_surcharge=maut,
            diesel_surcharge=None,
            currency="EUR",
            tariff_file=_DLV_PATH.name,
            tariff_valid_from=_VALID_FROM,
            tariff_valid_to=_VALID_TO,
            notes=notes,
            tarifgruppe=f"groz_beckert_gc_{empf_land_up.lower()}",
            tariff_file_used=_DLV_PATH.name,
            tariff_year_used=_VALID_FROM.year,
        )
