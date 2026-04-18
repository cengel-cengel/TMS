"""
Hornschuch AG (KNR 490085) — per-kg tariff calculator.

DLV: ContiTech MegaTrans Deutschland 2024 Round 3
  Carrier:  ERKA GmbH Stuttgart
  Sheet:    CT-SSL-WEI-P001  (origin DE-74 = Weissbach am Kocher)
  Valid:    2024-11-01 – 2026-10-31

Rate formula:
  tonnage_kg < 50.01  → flat minimum price (EUR)
  tonnage_kg ≥ 50.01  → rate_per_kg(zone, band) × tonnage_kg

Zone mapping (PLZ prefix → ContiTech tender zone code):
  IT / ES / FR → first 2 digits of PLZ  (e.g. "45010" → "45")
  PT           → first digit of PLZ      (e.g. "4710"  → "4")
  AT/BE/CH/GR  → first 2 digits of PLZ  (ERKA has rates but not in BI scope)

Maut:   included in base rates (no separate surcharge).
Diesel: applied externally by ContiTech; diesel_surcharge = None.

PL:     ERKA was not nominated for PL from Weissbach.
        Returns TariffResult(basispreis=None) — caller must check before .total.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import openpyxl

from tms.tariff.base import TariffCalculator, TariffResult

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DLV_PATH = Path(
    "/home/user/TMS/data/extracted/v1/Noerpel AI/Hornschuch/DLV/2025/"
    "20250129_Erka_ContiTech Megatrans Deutsc.xlsx"
)
_SHEET      = "CT-SSL-WEI-P001"
_VALID_FROM = date(2024, 11, 1)
_VALID_TO   = date(2026, 10, 31)
_TARIFF_FILE = "20250129_Erka_ContiTech Megatrans Deutsc.xlsx"
_DLV_NOTE    = "ContiTech MegaTrans DE 2024 Round 3, CT-SSL-WEI-P001"

# Upper bounds of the 24 weight bands (exclusive).
# Rates tuple layout: rates[0]=minimum(<50.01), rates[1]=50–75, …, rates[24]=24000+
_BAND_UPPERS = (
    50.01, 75, 100, 125, 150, 175, 200, 250, 300, 350, 400, 500, 750,
    1000, 1500, 2000, 2500, 4000, 6000, 8000, 10000, 12500, 15000, 24000,
)

# Module-level rate cache: (cc, zone) → tuple of 25 float|None values
_CACHE: dict[tuple[str, str], tuple] = {}
_LOADED = False


# ---------------------------------------------------------------------------
# Cache loader
# ---------------------------------------------------------------------------

def _load() -> None:
    global _LOADED
    if _LOADED:
        return
    wb = openpyxl.load_workbook(_DLV_PATH, read_only=True, data_only=True)
    ws = wb[_SHEET]
    for row in ws.iter_rows(min_row=9, values_only=True):
        if len(row) < 37:
            continue
        if row[11] != "Outbound":
            continue
        if row[5] != "DE" or str(row[6]) != "74":
            continue
        min_price = row[12]
        if min_price is None or min_price == "":
            continue
        cc   = str(row[9])
        zone = str(row[10])
        _CACHE[(cc, zone)] = (min_price,) + tuple(row[13:37])
    wb.close()
    _LOADED = True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _zone(cc: str, plz: str) -> str | None:
    """Return ContiTech zone code string for a country + PLZ."""
    p = plz.strip()
    if not p:
        return None
    if cc == "PT":
        # Portuguese zone = first digit; "9 (islands)" covers PLZ prefix 9
        d = p[0]
        if not d.isdigit():
            return None
        if (cc, d) not in _CACHE and (cc, d + " (islands)") in _CACHE:
            return d + " (islands)"
        return d
    # IT, ES, FR, AT, BE, CH, GR, DE → 2-digit prefix
    prefix = p[:2]
    return prefix if len(prefix) == 2 else None


def _rate_for(tonnage: float, rates: tuple) -> float | None:
    """Return EUR/kg rate (or flat minimum) for tonnage."""
    if tonnage < 50.01:
        return rates[0]
    for j, upper in enumerate(_BAND_UPPERS[1:], 1):
        if tonnage < upper:
            return rates[j]
    return rates[-1]


# ---------------------------------------------------------------------------
# Calculator
# ---------------------------------------------------------------------------

class HornschuchCalculator(TariffCalculator):
    customer_name = "Hornschuch AG"
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
    ) -> TariffResult:
        """
        Return TariffResult for a Hornschuch shipment.

        For PL: returns TariffResult(basispreis=None) — ERKA not nominated.
        For unknown zone or missing rate: raises LookupError.
        """
        _load()

        cc = empf_land.strip().upper()

        if cc == "PL":
            return TariffResult(
                basispreis=None,
                diesel_surcharge=None,
                maut_surcharge=None,
                tariff_file=_TARIFF_FILE,
                tariff_valid_from=_VALID_FROM,
                tariff_valid_to=_VALID_TO,
                notes=[_DLV_NOTE, "ERKA not nominated for PL from Weissbach"],
            )

        t = float(tonnage_kg) if tonnage_kg is not None else 0.0
        if t <= 0:
            raise LookupError(
                f"Hornschuch: tonnage_kg must be > 0, got {tonnage_kg!r}"
            )

        zone = _zone(cc, empf_plz)
        if zone is None:
            raise LookupError(
                f"Hornschuch: cannot determine zone for {cc} PLZ={empf_plz!r}"
            )

        rates = _CACHE.get((cc, zone))
        if rates is None:
            raise LookupError(
                f"Hornschuch: no rate for {cc} zone {zone!r} (PLZ={empf_plz!r})"
            )

        rate = _rate_for(t, rates)
        if rate is None:
            raise LookupError(
                f"Hornschuch: rate is None for {cc} zone {zone!r} at {t} kg"
            )

        if t < 50.01:
            basispreis = Decimal(str(round(float(rate), 4))).quantize(Decimal("0.0001"))
            band_note = f"zone={cc}-{zone}, minimum(<50.01kg), flat={rate}€"
        else:
            basispreis = Decimal(str(round(rate * t, 4))).quantize(Decimal("0.0001"))
            band_note = f"zone={cc}-{zone}, {t}kg, rate={rate}€/kg"

        return TariffResult(
            basispreis=basispreis,
            diesel_surcharge=None,
            maut_surcharge=None,
            tariff_file=_TARIFF_FILE,
            tariff_valid_from=_VALID_FROM,
            tariff_valid_to=_VALID_TO,
            notes=[_DLV_NOTE, band_note],
        )
