"""
CHT Germany GmbH tariff calculator — Italy.

DLV: "Ex- und Import Italien" sheet; weight-based, dual-mode:
  - Actual weight ≤ 1000 kg → "per Sendung" (flat per shipment, 8-zone table)
  - Actual weight > 1000 kg → "per 100 kg" (rate × billing_kg/100, 8-zone table)
  - PLZ 20052 / 20098 → separate DLV (always per 100 kg, with minimum per Sendung)

Billing weight: max(100, ceil(actual_kg / 100) * 100).
Band lookup always uses actual (raw) weight — critical for per-Sendung mode where a
1.5 kg shipment must land in "bis 50", not "bis 100" after billing rounding.

Zone lookup: first 2 digits of IT PLZ → zone 1-8 (hardcoded from DLV rows 43-50).
Override: PLZ starting with "238" or "239" → Zone 1 (not Zone 4 for "23").

Maut: DE-Maut (0.50) + AT-Maut (0.06) = 0.56 EUR / 100 kg on billing weight.
Diesel: invoiced via separate Sonder-Dieselfloater, not included in DLV base rate;
        Erlöse Diesel is always 0 in BI data — not computed here.
Thermozuschlag: 75 EUR / Sendung for some routes; not in DLV scope, shown in Erlöse
                Nebengebühr — not computed here.

Origin fixed: DE-72072 Tübingen.
Validity: 2026-01-01 – 2026-12-31.
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

_DLV_DIR = Path(
    "/home/user/TMS/data/extracted/v1/Noerpel AI/CHT/DLV/CHT/2026"
)
_DLV_FILE_ITALY = _DLV_DIR / "20260112_CHT_Export und Import Italien.xlsx"
_DLV_FILE_SPECIAL = _DLV_DIR / "20260112_CHT_Export IT-20052 und IT-20098.xlsx"

_VALID_FROM = date(2026, 1, 1)
_VALID_TO   = date(2026, 12, 31)

_MAUT_PER_100KG = Decimal("0.56")   # DE-Maut 0.50 + AT-Maut 0.06

# PLZ prefixes that use the separate special DLV (exact 5-digit match)
_SPECIAL_PLZ = {"20052", "20098"}


class _Band(NamedTuple):
    weight_limit: int          # upper bound (kg)
    rates: dict[int, Decimal]  # zone → rate (already rounded to 2 dp)
    unit: str                  # "per Sendung" | "per 100 kg"


# ---------------------------------------------------------------------------
# Zone table (hardcoded from DLV rows 43-50; stable across 2025/2026 files)
# ---------------------------------------------------------------------------

def _build_zone_map() -> dict[str, int]:
    """
    Returns mapping: 2- or 3-digit PLZ prefix string → zone 1-8.
    3-digit entries (238, 239) take lookup priority over 2-digit "23".
    """
    zones_raw: dict[int, list[str]] = {
        1: ["10", "20-22", "238+239", "24-25", "35-41"],
        2: ["26-30", "42-43", "46-47"],
        3: ["11-15", "31-33", "44-45", "48", "50-59"],
        4: ["00", "16-18", "23", "34", "60-66"],
        5: ["01-06", "19"],
        6: ["70", "80-84"],
        7: ["67", "71-75", "85-88"],
        8: ["07-09", "89-98"],
    }

    result: dict[str, int] = {}
    for zone, specs in zones_raw.items():
        for spec in specs:
            spec = spec.strip()
            # "+" separator: two 3-digit prefixes (e.g. "238+239")
            if "+" in spec:
                for part in spec.split("+"):
                    part = part.strip()
                    result[part] = zone
            elif "-" in spec:
                # Range like "20-22" or "01-06"
                parts = spec.split("-")
                start = int(parts[0].strip())
                end   = int(parts[1].strip())
                width = len(parts[0].strip())   # preserve leading zeros
                for n in range(start, end + 1):
                    result[str(n).zfill(width)] = zone
            else:
                result[spec] = zone
    return result


_ZONE_MAP: dict[str, int] = _build_zone_map()


def _lookup_zone(plz: str) -> int:
    """Return zone 1-8 for an Italian PLZ. 3-digit override checked first."""
    p = str(plz).strip().zfill(5)
    # 3-digit override (handles 238xx / 239xx)
    if p[:3] in _ZONE_MAP:
        return _ZONE_MAP[p[:3]]
    if p[:2] in _ZONE_MAP:
        return _ZONE_MAP[p[:2]]
    raise LookupError(f"No CHT Italy zone found for PLZ {plz!r}")


# ---------------------------------------------------------------------------
# Rate-table parsers
# ---------------------------------------------------------------------------

def _parse_main_bands(path: Path) -> list[_Band]:
    """Parse the 8-zone weight band table from rows 13-37 of the main DLV."""
    df = pd.read_excel(path, sheet_name="Ex- und Import Italien", header=None)

    # Row 12: header — "Zone 1" .. "Zone 8" in cols 2-9
    header_row = df.iloc[12]
    col_to_zone: dict[int, int] = {}
    for ci, val in enumerate(header_row):
        m = re.search(r"Zone\s+(\d+)", str(val))
        if m:
            col_to_zone[ci] = int(m.group(1))

    bands: list[_Band] = []
    for ri in range(13, 38):
        row = df.iloc[ri]
        marker = str(row.iloc[0]).strip().lower()
        if marker not in ("bis", "nan", ""):
            continue  # skip "Max. / kompletter LKW" row
        try:
            wlim = int(float(str(row.iloc[1])))
        except (ValueError, TypeError):
            continue
        unit_raw = str(row.iloc[10]).strip()
        unit = "per Sendung" if "sendung" in unit_raw.lower() else "per 100 kg"

        rates: dict[int, Decimal] = {}
        for ci, zone in col_to_zone.items():
            try:
                val = round(float(row.iloc[ci]), 2)
                if val > 0:
                    rates[zone] = Decimal(str(val))
            except (ValueError, TypeError):
                pass

        if rates:
            bands.append(_Band(weight_limit=wlim, rates=rates, unit=unit))

    return sorted(bands, key=lambda b: b.weight_limit)


class _SpecialBand(NamedTuple):
    weight_limit: int
    rate: Decimal   # per 100 kg


def _parse_special_bands(path: Path) -> tuple[list[_SpecialBand], Decimal]:
    """
    Parse the IT-20052 / IT-20098 special DLV.
    Returns (bands, minimum_per_sendung).
    """
    df = pd.read_excel(path, sheet_name="Export IT-20052 + IT-20098", header=None)

    minimum = Decimal("0")
    bands: list[_SpecialBand] = []

    for ri in range(len(df)):
        row = df.iloc[ri]
        cell0 = str(row.iloc[0]).strip().lower()
        cell1 = str(row.iloc[1]).strip()
        cell2 = str(row.iloc[2]).strip()

        if cell0 == "nan" and "minimum" in cell1.lower():
            try:
                minimum = Decimal(str(round(float(cell2), 2)))
            except (ValueError, TypeError):
                pass
            continue

        if cell0 == "bis":
            try:
                # weight_limit may be "500 kg" or plain "600"
                wlim = int(float(re.sub(r"[^\d.]", "", cell1)))
                rate = Decimal(str(round(float(cell2), 2)))
                if rate > 0:
                    bands.append(_SpecialBand(weight_limit=wlim, rate=rate))
            except (ValueError, TypeError):
                pass

    return sorted(bands, key=lambda b: b.weight_limit), minimum


# ---------------------------------------------------------------------------
# Calculator
# ---------------------------------------------------------------------------

class CHTItalyCalculator(TariffCalculator):
    """
    CHT Germany GmbH — Italy-only tariff (DE-72072 Tübingen origin).
    Raises LookupError for non-IT destinations.
    """

    customer_name = "CHT Germany GmbH"
    pricing_basis = "kg"

    def __init__(
        self,
        dlv_file: Path = _DLV_FILE_ITALY,
        dlv_file_special: Path = _DLV_FILE_SPECIAL,
    ) -> None:
        self._dlv_file = dlv_file
        self._dlv_file_special = dlv_file_special
        self._main_bands: list[_Band] | None = None
        self._special_bands: list[_SpecialBand] | None = None
        self._special_minimum: Decimal = Decimal("0")

    def _ensure_loaded(self) -> None:
        if self._main_bands is None:
            self._main_bands = _parse_main_bands(self._dlv_file)
            self._special_bands, self._special_minimum = _parse_special_bands(
                self._dlv_file_special
            )

    def _calc_main(self, zone: int, actual_kg: float, billing_kg: int) -> Decimal:
        """Compute freight from the main 8-zone table."""
        assert self._main_bands is not None
        for band in self._main_bands:
            if band.weight_limit >= actual_kg:
                if zone not in band.rates:
                    raise LookupError(
                        f"Zone {zone} has no rate in band bis {band.weight_limit}"
                    )
                rate = band.rates[zone]
                if band.unit == "per Sendung":
                    return rate
                else:
                    return rate * Decimal(str(billing_kg)) / Decimal("100")
        raise LookupError(
            f"No CHT Italy band covers actual_kg={actual_kg:.1f} (zone {zone})"
        )

    def _calc_special(self, actual_kg: float, billing_kg: int) -> Decimal:
        """Compute freight from the IT-20052/20098 special table."""
        assert self._special_bands is not None
        for band in self._special_bands:
            if band.weight_limit >= actual_kg:
                price = band.rate * Decimal(str(billing_kg)) / Decimal("100")
                return max(price, self._special_minimum)
        raise LookupError(
            f"No special CHT Italy band covers actual_kg={actual_kg:.1f}"
        )

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
        self._ensure_loaded()

        if empf_land.strip().upper() != "IT":
            raise LookupError(
                f"CHTItalyCalculator only covers IT; got empf_land={empf_land!r}"
            )
        if tonnage_kg is None or tonnage_kg <= 0:
            raise ValueError("tonnage_kg must be provided and > 0")

        actual_kg = tonnage_kg
        billing_kg = max(100, math.ceil(actual_kg / 100) * 100)

        plz_norm = str(empf_plz).strip().zfill(5)

        if plz_norm in _SPECIAL_PLZ:
            basispreis = self._calc_special(actual_kg, billing_kg)
            tarifgruppe = "cht_it_special"
            file_used = str(self._dlv_file_special.name)
        else:
            zone = _lookup_zone(plz_norm)
            basispreis = self._calc_main(zone, actual_kg, billing_kg)
            tarifgruppe = f"cht_it_zone{zone}"
            file_used = str(self._dlv_file.name)

        maut = _MAUT_PER_100KG * Decimal(str(billing_kg)) / Decimal("100")

        return TariffResult(
            basispreis=basispreis,
            diesel_surcharge=None,
            maut_surcharge=maut,
            currency="EUR",
            tariff_file=str(self._dlv_file.name),
            tariff_valid_from=_VALID_FROM,
            tariff_valid_to=_VALID_TO,
            notes=[
                f"actual_kg={actual_kg}",
                f"billing_kg={billing_kg}",
                f"plz={plz_norm}",
            ],
            tarifgruppe=tarifgruppe,
            tariff_file_used=file_used,
            tariff_year_used=_VALID_FROM.year,
        )
