"""
CHT Germany GmbH tariff calculator — Belgium.

DLV: "Export Belgien" sheet; weight-based, single zone:
  - Actual weight ≤ 100 kg → "per Sendung" (flat €40.5511)
  - Actual weight > 100 kg → "per 100 kg" (rate × billing_kg/100, band table)
  - komplett LKW → flat €935.034 (Sonderfall, never triggered in normal range)

Billing weight: max(100, ceil(actual_kg / 100) * 100).
Band lookup uses actual (raw) weight to select the correct band.

Maut: DE-Maut only = 0.58 EUR / 100 kg on billing weight.
      BE-Maut is already included in the DLV rates ("inklusive").
Diesel: contracted via quarterly Sonder-Dieselfloater (~8.62% base + quarterly adj).
        Not computed here; tracked separately as diesel_delta in integration tests.

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
_DLV_FILE = _DLV_DIR / "20260112_CHT_Export Belgien.xlsx"
_SHEET    = "Export Belgien"

_VALID_FROM = date(2026, 1, 1)
_VALID_TO   = date(2026, 12, 31)

_MAUT_PER_100KG = Decimal("0.58")  # DE-Maut only; BE-Maut included in rates


class _Band(NamedTuple):
    weight_limit: int    # upper bound (kg); 999999 = komplett LKW catch-all
    rate: Decimal        # per-Sendung flat or per-100-kg rate
    unit: str            # "per Sendung" | "per 100 kg"


def _parse_bands(path: Path) -> list[_Band]:
    df = pd.read_excel(path, sheet_name=_SHEET, header=None)
    bands: list[_Band] = []
    for ri in range(len(df)):
        row = df.iloc[ri]
        col0 = str(row.iloc[0]).strip().lower()
        col1 = str(row.iloc[1]).strip()
        col2 = row.iloc[2]
        col3 = str(row.iloc[3]).strip() if len(row) > 3 else ""

        if col0 == "bis":
            # weight_limit may be "500 kg" or plain int
            try:
                wlim = int(float(re.sub(r"[^\d.]", "", col1)))
            except (ValueError, TypeError):
                continue
            try:
                rate = Decimal(str(round(float(col2), 2)))
            except (ValueError, TypeError):
                continue
            unit = "per Sendung" if "sendung" in col3.lower() else "per 100 kg"
            bands.append(_Band(weight_limit=wlim, rate=rate, unit=unit))

        elif "kompl" in col1.lower() or "kompl" in col0.lower():
            # komplett LKW — flat per Sendung, catch-all for very heavy
            try:
                rate = Decimal(str(round(float(col2), 2)))
                bands.append(_Band(weight_limit=999999, rate=rate, unit="per Sendung"))
            except (ValueError, TypeError):
                pass

    return sorted(bands, key=lambda b: b.weight_limit)


class CHTBelgiumCalculator(TariffCalculator):
    """
    CHT Germany GmbH — Belgium tariff (DE-72072 Tübingen origin).
    Single zone; no PLZ lookup required.
    Raises LookupError for non-BE destinations.
    """

    customer_name = "CHT Germany GmbH"
    pricing_basis = "kg"

    def __init__(self, dlv_file: Path = _DLV_FILE) -> None:
        self._dlv_file = dlv_file
        self._bands: list[_Band] | None = None

    def _ensure_loaded(self) -> None:
        if self._bands is None:
            self._bands = _parse_bands(self._dlv_file)

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
        assert self._bands is not None

        if empf_land.strip().upper() != "BE":
            raise LookupError(
                f"CHTBelgiumCalculator only covers BE; got empf_land={empf_land!r}"
            )
        if tonnage_kg is None or tonnage_kg <= 0:
            raise ValueError("tonnage_kg must be provided and > 0")

        actual_kg  = tonnage_kg
        billing_kg = max(100, math.ceil(actual_kg / 100) * 100)

        basispreis: Decimal | None = None
        for band in self._bands:
            if band.weight_limit >= actual_kg:
                if band.unit == "per Sendung":
                    basispreis = band.rate
                else:
                    basispreis = band.rate * Decimal(str(billing_kg)) / Decimal("100")
                break

        if basispreis is None:
            raise LookupError(
                f"No CHT Belgium band covers actual_kg={actual_kg:.1f}"
            )

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
                f"plz={str(empf_plz).strip()}",
            ],
            tarifgruppe="cht_be_main",
            tariff_file_used=str(self._dlv_file.name),
            tariff_year_used=_VALID_FROM.year,
        )
