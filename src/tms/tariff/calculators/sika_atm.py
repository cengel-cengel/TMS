"""
Sika ATM tariff calculator — weight-band (flat EUR/Sendung) for all
Sika Automotive routes from DE-70499 Stuttgart (LSU M7 plant).

DLV: 'Anlage 1' KORRIGIERT, valid 2024-07-01 – 2026-06-30.
     One sheet per destination country, 60 weight bands per zone.

Rate formula:
  zone_key = country-specific PLZ → zone label (see _zone_key)
  band     = first band whose upper_limit >= tonnage_kg
  rate     = flat EUR/Sendung (not per kg, not per 100 kg)

Zone key format: '{CC}-{2-digit-PLZ-prefix}' for numeric countries;
                 'GB-{area}' for GB postcodes.

Maut:   included in contracted rates; maut_surcharge = None.
Diesel: external Dieselfloater (±1.25% per 5 Ct/L step from 165-190 Ct/L
        baseline); diesel_surcharge = None.
CH/DE:  ERKA not nominated; raises LookupError.

KNR usage:
  SikaATMChCalculator  → KNR 527406 (Sika Automotive AG, Romanshorn CH)
  SikaATMDeCalculator  → KNR 413276 (Sika Automotive Deutschland, Hamburg)
Both KNRs share the same Anlage 1 — identical rates.
"""
from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import NamedTuple

import pandas as pd

from tms.tariff.base import TariffCalculator, TariffResult

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DLV_PATH = Path(
    "/home/user/TMS/data/extracted/v1/Noerpel AI/SIka/DLV"
    "/SIKA Automotive/2025"
    "/20250728_Anlage 1_Sika ATM_ERKA_Sonderleistungen_Tarifblätter_HH_u."
    " Roman. ex. LSU M7_01.07.2024 bis 30.06.2026_KORRIGIERT.xlsx"
)
_VALID_FROM = date(2024, 7, 1)
_VALID_TO   = date(2026, 6, 30)

# Map ISO-2 → sheet name (trailing spaces are literal in the file)
_SHEET_MAP: dict[str, str] = {
    "DE": "Tarif DE ex. Sika LSU M7",
    "FR": "Tarif F ex. Sika LSU M7",
    "GB": "Tarif GB ex. Sika LSU M7",
    "IT": "Tarif IT ex. Sika LSU M7 ",
    "PL": "Tarif PL ex. Sika LSU M7",
    "CZ": "Tarif CZ ex. Sika LSU M7",
    "ES": "Tarif ES ex. Sika LSU M7",
    "PT": "Tarif PT ex. Sika LSU M7 ",
    "SK": "Tarif SK ex. Sika LSU M7 ",
    "RO": "Tarif RO ex. Sika LSU M7 ",
    "HU": "Tarif HU ex. Sika LSU M7 ",
    "RS": "Tarif Serb ex. Sika LSU M7 ",
    "BE": "Tarif BE ex. Sika LSU M7 ",
    "DK": "Tarif DK ex. Sika LSU M7 ",
    "NL": "Tarif NL ex. Sika LSU M7 ",
    "SE": "Tarif SE ex. Sika LSU M7 ",
    "AT": "Tarif A ex. Sika LSU M7  ",
    "SI": "Tarif SI ex. Sika LSU M7",
    "LU": "Tarif LUX ex. Sika LSU M7",
}

# Countries where all rates are 0 — ERKA not nominated
_NOT_NOMINATED = frozenset({"CH", "DE"})


# ---------------------------------------------------------------------------
# Data type
# ---------------------------------------------------------------------------

class _SheetData(NamedTuple):
    upper_bounds: list[float]         # 60 upper weight limits (kg), ascending
    zones: dict[str, list[float]]     # zone_key → 60 flat rates (EUR/Sendung)


# ---------------------------------------------------------------------------
# Sheet parser
# ---------------------------------------------------------------------------

def _parse_sheet(sheet_name: str) -> _SheetData:
    """
    Parse one tariff sheet from Anlage 1 KORRIGIERT.

    The 'PLZ / ab kg' header row (found dynamically, typically row 10 or 12)
    carries upper weight bounds in cols 1+.  Zone rows follow immediately.
    Zone rows with label containing 'xx' or all-zero rates are skipped.
    """
    df = pd.read_excel(_DLV_PATH, sheet_name=sheet_name, header=None)

    # Find header row ('PLZ / ab kg' in col 0)
    header_row: int | None = None
    for i in range(8, min(16, len(df))):
        if "PLZ" in str(df.iloc[i, 0]).upper():
            header_row = i
            break
    if header_row is None:
        raise ValueError(f"Cannot find 'PLZ / ab kg' header in sheet {sheet_name!r}")

    # Extract upper weight bounds from header row (cols 1+)
    upper_bounds: list[float] = []
    for j in range(1, len(df.columns)):
        v = df.iloc[header_row, j]
        if pd.isna(v):
            break
        try:
            upper_bounds.append(float(v))
        except (ValueError, TypeError):
            break

    if not upper_bounds:
        raise ValueError(f"No weight bounds found in sheet {sheet_name!r}")

    # Parse zone rows (rows after header)
    zones: dict[str, list[float]] = {}
    for i in range(header_row + 1, len(df)):
        raw_label = df.iloc[i, 0]
        if pd.isna(raw_label):
            break
        label = str(raw_label).strip()
        if not label or label == "nan":
            break
        # Skip placeholder rows
        if "xx" in label.lower():
            continue

        rates: list[float] = []
        for j in range(1, 1 + len(upper_bounds)):
            if j >= len(df.columns):
                rates.append(0.0)
                continue
            v = df.iloc[i, j]
            try:
                rates.append(float(v) if not pd.isna(v) else 0.0)
            except (ValueError, TypeError):
                rates.append(0.0)

        # Skip all-zero rows (not nominiert placeholders)
        if any(r > 0 for r in rates):
            zones[label] = rates

    return _SheetData(upper_bounds=upper_bounds, zones=zones)


# ---------------------------------------------------------------------------
# Module-level lazy cache: cc → _SheetData
# ---------------------------------------------------------------------------

_CACHE: dict[str, _SheetData] = {}


def _get_sheet(cc: str) -> _SheetData:
    if cc in _CACHE:
        return _CACHE[cc]
    sheet_name = _SHEET_MAP.get(cc)
    if sheet_name is None:
        raise LookupError(
            f"SikaATM: no tariff sheet configured for country {cc!r}. "
            f"Supported: {sorted(_SHEET_MAP)}"
        )
    data = _parse_sheet(sheet_name)
    _CACHE[cc] = data
    return data


# ---------------------------------------------------------------------------
# Zone key construction
# ---------------------------------------------------------------------------

def _zone_key(cc: str, plz: str) -> str:
    """
    Construct the zone label as it appears in col 0 of the tariff sheet.

    For GB: 'GB-{area}' where area = leading letters of UK postcode.
    For all other countries: '{CC}-{2-digit-PLZ-prefix}'.
    """
    plz_s = str(plz).strip().upper()

    if cc == "GB":
        m = re.match(r"([A-Z]+)", plz_s)
        area = m.group(1) if m else plz_s[:2]
        return f"GB-{area}"

    digits = re.sub(r"\D", "", plz_s)
    prefix = digits[:2].zfill(2) if len(digits) >= 2 else digits.zfill(2)
    return f"{cc}-{prefix}"


# ---------------------------------------------------------------------------
# Rate lookup
# ---------------------------------------------------------------------------

def _lookup_rate(cc: str, plz: str, tonnage_kg: float) -> Decimal:
    """
    Return flat EUR/Sendung for (country, PLZ, tonnage_kg).
    Raises LookupError if no rate found.
    """
    data = _get_sheet(cc)
    zone = _zone_key(cc, plz)

    rates = data.zones.get(zone)
    if rates is None:
        raise LookupError(
            f"SikaATM: no zone {zone!r} found for country {cc!r} "
            f"(PLZ={plz!r}). Available zones: {sorted(data.zones)[:8]}…"
        )

    # First band where upper_limit >= tonnage_kg
    for i, upper in enumerate(data.upper_bounds):
        if upper >= tonnage_kg:
            rate = rates[i]
            if rate <= 0:
                raise LookupError(
                    f"SikaATM: rate is 0 for {zone!r} band {upper:.0f} kg "
                    f"(country not nominated?)"
                )
            return Decimal(str(round(rate, 4)))

    # tonnage_kg exceeds all bands: use last band
    rate = rates[-1]
    if rate <= 0:
        raise LookupError(
            f"SikaATM: rate is 0 for {zone!r} at {tonnage_kg:.0f} kg (last band)"
        )
    return Decimal(str(round(rate, 4)))


# ---------------------------------------------------------------------------
# Base calculator
# ---------------------------------------------------------------------------

class _SikaATMBase(TariffCalculator):
    pricing_basis = "kg"
    _tarifgruppe: str = "sika_atm"

    def calculate(
        self,
        empf_plz: str,
        empf_land: str,
        *,
        lademeter: float | None = None,
        stellplaetze: int | None = None,
        tonnage_kg: float | None = None,
        ldm: float | None = None,
    ) -> TariffResult:
        if tonnage_kg is None or tonnage_kg <= 0:
            raise ValueError("tonnage_kg must be provided and > 0")

        cc = empf_land.strip().upper()

        if cc in _NOT_NOMINATED:
            raise LookupError(
                f"SikaATM: ERKA not nominated for {cc!r}. "
                f"All DLV rates = 0. No pricing available."
            )

        basispreis = _lookup_rate(cc, empf_plz, tonnage_kg)
        zone = _zone_key(cc, empf_plz)

        return TariffResult(
            basispreis=basispreis.quantize(Decimal("0.01")),
            diesel_surcharge=None,
            maut_surcharge=None,
            other_surcharges={},
            currency="EUR",
            tariff_file=_DLV_PATH.name,
            tariff_valid_from=_VALID_FROM,
            tariff_valid_to=_VALID_TO,
            notes=[
                f"zone={zone}",
                f"tonnage_kg={tonnage_kg}",
            ],
            tarifgruppe=self._tarifgruppe,
            tariff_file_used=_DLV_PATH.name,
            tariff_year_used=_VALID_FROM.year,
        )


# ---------------------------------------------------------------------------
# Concrete calculators
# ---------------------------------------------------------------------------

class SikaATMChCalculator(_SikaATMBase):
    """Sika Automotive AG (KNR 527406, ERKA-Nr 18748) — CH billing entity."""
    customer_name = "Sika Automotive AG"
    _tarifgruppe  = "sika_atm_ch"


class SikaATMDeCalculator(_SikaATMBase):
    """Sika Automotive Deutschland GmbH (KNR 413276, ERKA-Nr 18894, Dinas era)."""
    customer_name = "Sika Automotive Deutschland GmbH"
    _tarifgruppe  = "sika_atm_de"
