"""
GEZE GmbH tariff calculator — Export rates from Leonberg.

DLV: "Exporttarife" sheet; per-100-kg rates with minimum floor, country blocks.
Formula: billing_kg = max(100, ceil(t/100)*100)
         soll = max(minimum, rate_per_100kg × billing_kg / 100)

Countries: PT, GB, IE, IT, FR, AT, ES, CH.

Maut: INCLUDED in rates (Erlöse Maut = 0 in BI). maut_surcharge=None.
Diesel: Excluded (Dieselfloater separate in BI). diesel_surcharge=None.
CHF floater: Applied for CH only when chf_eur_rate is provided.

Origin: PLZ 71229 Leonberg.
Validity: 2025-01-01 – 2025-12-31 (no 2026 DLV; 2025 mandatory fallback).
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

_DLV_DIR = Path("/home/user/TMS/data/extracted/v1/Noerpel AI/GEZE/DLV/2025")
_DLV_FILE = next(_DLV_DIR.glob("*DUBLIN*"))

_VALID_FROM = date(2025, 1, 1)
_VALID_TO = date(2025, 12, 31)


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

class _Band(NamedTuple):
    weight_limit: int  # upper bound (kg), inclusive
    rate: Decimal      # EUR per 100 kg


class _ZoneRates(NamedTuple):
    zone: int
    minimum: Decimal
    bands: list[_Band]


# ---------------------------------------------------------------------------
# Zone lookup maps  (hardcoded from DLV Exporttarife)
# ---------------------------------------------------------------------------

def _parse_plz_spec(spec: str) -> list[tuple[str, str]]:
    """Extract (lo, hi) string pairs from a PLZ spec like '10-19, 26-29, 238'."""
    result: list[tuple[str, str]] = []
    for part in re.split(r"[,;]", spec):
        part = part.strip()
        m = re.match(r"^(\d{2,3})\s*[-\u2013]\s*(\d{2,3})$", part)
        if m:
            result.append((m.group(1), m.group(2)))
        elif re.match(r"^\d{2,3}$", part):
            result.append((part, part))
    return result


def _build_zone_lookup(zone_specs: dict[int, str]):
    """PLZ→zone callable; 3-digit overrides checked before 2-digit ranges."""
    three: list[tuple[str, str, int]] = []
    two: list[tuple[str, str, int]] = []
    for zone, spec in zone_specs.items():
        for lo, hi in _parse_plz_spec(spec):
            (three if len(lo) == 3 else two).append((lo, hi, zone))

    def lookup(plz: str) -> int | None:
        digits = re.sub(r"[^0-9]", "", str(plz))
        if not digits:
            return None
        p3 = digits[:3]
        for lo, hi, z in three:
            if lo <= p3 <= hi:
                return z
        p2 = digits[:2]
        for lo, hi, z in two:
            if lo <= p2 <= hi:
                return z
        return None

    return lookup


_PT_LOOKUP = _build_zone_lookup({
    1: "10-19, 26-29, 40-44",
    2: "20-23, 37-39, 45-49",
    3: "24-25, 30-36",
    4: "50-69, 70-89",
})

_IT_LOOKUP = _build_zone_lookup({
    1: "39",
    2: "20-22, 238, 239, 24, 25, 29, 30-38",
    3: "10-19, 26-28, 40-47, 50-59",
    4: "00-06, 230-237, 48, 61",
    5: "60, 62-66, 70, 71, 80-84",
    6: "07-09, 72-75, 85, 87-89, 90-98",
})

_FR_ZONE7_PLZ = frozenset({"77127", "77160", "77170", "77390"})
_FR_BASE_LOOKUP = _build_zone_lookup({
    1: "67",
    2: "38, 42, 69, 74, 75, 77, 78, 91-95",
    3: "27, 57, 60, 68, 76",
    4: "10, 14, 21, 28, 45, 52, 59, 70, 72, 89",
    5: "01-03, 06-08, 12, 13, 15, 19, 23, 25, 26, 37, 39, 41, 43, 44, 46-49, 51, 54, 55, 62, 63, 71, 79, 80, 85, 87, 88, 90",
    6: "04, 05, 09, 11, 16-18, 22, 24, 29-36, 40, 50, 53, 56, 58, 61, 64-66, 73, 81-84, 86",
})


def _fr_lookup(plz: str) -> int | None:
    digits = re.sub(r"[^0-9]", "", str(plz))
    if len(digits) >= 5 and digits[:5] in _FR_ZONE7_PLZ:
        return 7
    return _FR_BASE_LOOKUP(plz)


_AT_LOOKUP = _build_zone_lookup({
    1: "67-69",
    2: "60-66",
    3: "10-28",
    4: "30-39, 70-73",
    5: "50-57",
    6: "40-49",
    7: "74-76, 80-89",
    8: "90-99",
})

_ES_LOOKUP = _build_zone_lookup({
    1: "08",
    2: "28",
    3: "01, 17, 20, 25, 26, 31, 43, 48, 50",
    4: "02, 03, 05, 09, 13, 24, 33, 34, 39, 46",
    5: "04, 06, 10-16, 18, 19, 21-23, 27, 29, 30, 32, 36, 37, 41, 42, 44, 45, 47, 49",
    6: "07",
    7: "35, 38",
})

_CH_LOOKUP = _build_zone_lookup({
    1: "40-44, 80-81, 83-84",
    2: "27-28, 45-49, 50-57, 82, 85-86, 89, 92, 95",
    3: "25-26, 29, 33-34, 60-63, 87-88, 90-91, 93, 96",
    4: "23, 30-32, 35, 94",
    5: "17, 20, 22, 24, 36, 64, 73",
    6: "15, 21, 38, 70",
    7: "10, 13-14, 16, 67, 71-72",
    8: "11-12, 18, 37, 65-66, 69, 76",
    9: "19",
})

# GB postcode area (leading letters) → zone; derived from DLV sample postcodes
_GB_AREA_ZONES: dict[str, int] = {
    # Zone 1 — Midlands (GEZE UK HQ: WS13 Lichfield area)
    "WS": 1, "B": 1, "CV": 1, "DE": 1, "LE": 1, "NN": 1, "WV": 1, "ST": 1,
    # Zone 2 — South/East England further from Midlands
    "MK": 2, "LU": 2, "AL": 2, "SG": 2, "PE": 2, "CB": 2, "IP": 2,
    "CM": 2, "CO": 2, "SS": 2, "RM": 2, "E": 2, "N": 2, "NW": 2,
    "W": 2, "SW": 2, "SE": 2, "EC": 2, "WC": 2,
    # Zone 3 — Scotland
    "G": 3, "PA": 3, "FK": 3, "KA": 3, "EH": 3, "ML": 3, "KY": 3,
    "DD": 3, "PH": 3, "AB": 3, "IV": 3,
    # Zone 4 — Northern Ireland
    "BT": 4,
}


def _gb_lookup(plz: str) -> int | None:
    plz = str(plz).strip().upper()
    area_m = re.match(r"^([A-Z]+)", plz)
    if not area_m:
        return None
    code = area_m.group(1)
    for length in range(len(code), 0, -1):
        z = _GB_AREA_ZONES.get(code[:length])
        if z is not None:
            return z
    return 1  # default Zone 1 for unknown GB areas


_COUNTRY_LOOKUP: dict[str, object] = {
    "PT": _PT_LOOKUP,
    "GB": _gb_lookup,
    "IE": lambda plz: 1,
    "IT": _IT_LOOKUP,
    "FR": _fr_lookup,
    "AT": _AT_LOOKUP,
    "ES": _ES_LOOKUP,
    "CH": _CH_LOOKUP,
}


# ---------------------------------------------------------------------------
# DLV parsers
# ---------------------------------------------------------------------------

def _parse_band_limit(s: str) -> int | None:
    m = re.search(r"[\d.,]+", str(s).strip())
    if not m:
        return None
    try:
        return int(m.group().replace(".", "").replace(",", ""))
    except ValueError:
        return None


_COUNTRY_MARKERS: dict[str, str] = {
    "Portugal": "PT",
    "Großbritanien": "GB",
    "Irland": "IE",
    "Italien": "IT",
    "Frankreich Zone 7": "FR7",   # must be before "Frankreich"
    "Frankreich": "FR",
    "Österreich": "AT",
    "Spanien": "ES",
    "Schweiz": "CH",
}


def _parse_export_tarife(path: Path) -> dict[str, list[_ZoneRates]]:
    df = pd.read_excel(path, sheet_name="Exporttarife", header=None)
    result: dict[str, list[_ZoneRates]] = {}
    current_iso: str | None = None
    current_bands: list[int] = []

    for i, row in df.iterrows():
        v0 = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ""

        # Country / section header
        for marker, iso in _COUNTRY_MARKERS.items():
            if v0 == marker or v0.startswith(marker):
                current_iso = iso
                current_bands = []
                target = "FR" if iso == "FR7" else iso
                if target not in result:
                    result[target] = []
                break
        else:
            if v0.startswith("ab Werk"):
                # Column header row — extract weight band limits
                current_bands = []
                for j in range(3, len(row)):
                    v = row.iloc[j]
                    if pd.isna(v) or str(v).strip() in ("", "nan"):
                        break
                    lim = _parse_band_limit(str(v))
                    if lim:
                        current_bands.append(lim)

            elif v0.startswith("Zone") and current_iso and current_bands:
                zm = re.search(r"\d+", v0)
                if not zm:
                    continue
                zone_num = int(zm.group())
                v2 = row.iloc[2]
                if pd.isna(v2):
                    continue
                try:
                    minimum = Decimal(str(round(float(v2), 4)))
                except (ValueError, TypeError):
                    continue

                bands: list[_Band] = []
                for k, lim in enumerate(current_bands):
                    j = 3 + k
                    if j >= len(row):
                        break
                    v = row.iloc[j]
                    if pd.isna(v) or str(v).strip() in ("", "nan"):
                        break
                    try:
                        bands.append(_Band(weight_limit=lim, rate=Decimal(str(round(float(v), 4)))))
                    except (ValueError, TypeError):
                        break

                if not bands:
                    continue
                target = "FR" if current_iso == "FR7" else current_iso
                if target not in result:
                    result[target] = []
                result[target].append(_ZoneRates(zone=zone_num, minimum=minimum, bands=bands))

    return result


def _parse_chf_floater(path: Path) -> list[tuple[float, float, Decimal, Decimal]]:
    """Return [(rate_lo, rate_hi, stueckgut_frac, komplett_frac), ...]."""
    df = pd.read_excel(path, sheet_name="CH-Währungsfloater", header=None)
    out: list[tuple[float, float, Decimal, Decimal]] = []
    last_komplett = Decimal("0")
    for i, row in df.iterrows():
        if i < 21:
            continue
        # Data starts in col 2 (von CHF), col 3 (bis CHF), col 4 (Stückgut), col 5 (Komplett)
        v0, v1, v2, v3 = row.iloc[2], row.iloc[3], row.iloc[4], row.iloc[5]
        if pd.isna(v0) or str(v0) in ("nan", "NaT", ""):
            break
        try:
            lo = float(min(v0, v1))
            hi = float(max(v0, v1))
            sg = Decimal(str(round(float(v2), 6))) if pd.notna(v2) else Decimal("0")
            if pd.notna(v3) and str(v3) not in ("nan", "NaT", ""):
                ko = Decimal(str(round(float(v3), 6)))
                last_komplett = ko
            else:
                ko = last_komplett
            out.append((lo, hi, sg, ko))
        except (ValueError, TypeError):
            break
    return out


# ---------------------------------------------------------------------------
# Module-level lazy-loaded cache
# ---------------------------------------------------------------------------

_RATES: dict[str, list[_ZoneRates]] | None = None
_CHF_TABLE: list[tuple[float, float, Decimal, Decimal]] | None = None


def _get_rates() -> dict[str, list[_ZoneRates]]:
    global _RATES
    if _RATES is None:
        _RATES = _parse_export_tarife(_DLV_FILE)
    return _RATES


def _get_chf_table() -> list[tuple[float, float, Decimal, Decimal]]:
    global _CHF_TABLE
    if _CHF_TABLE is None:
        _CHF_TABLE = _parse_chf_floater(_DLV_FILE)
    return _CHF_TABLE


# ---------------------------------------------------------------------------
# Rate lookup helpers
# ---------------------------------------------------------------------------

def _find_zone_rates(empf_land: str, empf_plz: str) -> _ZoneRates | None:
    lookup_fn = _COUNTRY_LOOKUP.get(empf_land.upper())
    if lookup_fn is None:
        return None
    zone = lookup_fn(empf_plz)
    if zone is None:
        return None
    for zr in _get_rates().get(empf_land.upper(), []):
        if zr.zone == zone:
            return zr
    return None


def _compute_soll(zr: _ZoneRates, billing_kg: int) -> Decimal:
    for band in zr.bands:
        if billing_kg <= band.weight_limit:
            return max(zr.minimum, band.rate * Decimal(str(billing_kg)) / Decimal("100"))
    # Extrapolate with last band rate if billing_kg exceeds all bands
    last = zr.bands[-1]
    return max(zr.minimum, last.rate * Decimal(str(billing_kg)) / Decimal("100"))


def _chf_surcharge_frac(billing_kg: int, chf_eur_rate: float) -> Decimal:
    for lo, hi, sg_frac, ko_frac in _get_chf_table():
        if lo <= chf_eur_rate <= hi:
            return sg_frac if billing_kg <= 3000 else ko_frac
    return Decimal("0")


# ---------------------------------------------------------------------------
# Calculator
# ---------------------------------------------------------------------------

class GEZECalculator(TariffCalculator):
    customer_name = "GEZE GmbH"
    pricing_basis = "kg"

    def calculate(
        self,
        empf_plz: str,
        empf_land: str,
        *,
        lademeter: float | None = None,
        stellplaetze: int | None = None,
        tonnage_kg: float | None = None,
        ldm: float | None = None,
        chf_eur_rate: float | None = None,
    ) -> TariffResult:
        if tonnage_kg is None or tonnage_kg < 0:
            raise ValueError("tonnage_kg required and must be >= 0")

        billing_kg = max(100, math.ceil(tonnage_kg / 100) * 100)

        zr = _find_zone_rates(empf_land, empf_plz)
        if zr is None:
            raise LookupError(
                f"No GEZE rate found: land={empf_land!r} plz={empf_plz!r}"
            )

        basispreis = _compute_soll(zr, billing_kg).quantize(Decimal("0.01"))

        chf_amount = Decimal("0")
        if empf_land.upper() == "CH" and chf_eur_rate is not None:
            frac = _chf_surcharge_frac(billing_kg, chf_eur_rate)
            chf_amount = (basispreis * frac).quantize(Decimal("0.01"))

        notes = [
            f"zone={zr.zone}",
            f"billing_kg={billing_kg}",
            f"minimum={zr.minimum}",
        ]
        if empf_land.upper() == "CH" and chf_eur_rate is not None:
            notes.append(f"chf_eur_rate={chf_eur_rate}")

        return TariffResult(
            basispreis=basispreis,
            diesel_surcharge=None,
            maut_surcharge=None,
            other_surcharges={"chf_floater": chf_amount} if chf_amount else {},
            currency="EUR",
            tariff_file=_DLV_FILE.name,
            tariff_valid_from=_VALID_FROM,
            tariff_valid_to=_VALID_TO,
            notes=notes,
            tarifgruppe=f"geze_{empf_land.upper().lower()}_zone{zr.zone}",
            tariff_file_used=_DLV_FILE.name,
            tariff_year_used=_VALID_FROM.year,
        )
