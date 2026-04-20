"""
CHT Germany GmbH tariff calculator — Spain.

DLV: "Ex- u. Import Spanien" sheet; weight-based, 6 mainland zones + Zone 7 (Mallorca):

Mainland Spain (Zones 1–6):
  - All weight bands: per 100 kg
  - Komplett LKW: per-zone flat rate (ceiling — if per-100-kg > komplett → cap)
  - Zone assignment: 2-digit PLZ prefix, table rows 31–37 in DLV sheet

Mallorca (Zone 7): mixed per-Sendung (≤600 kg) / per-100-kg (>600 kg);
  very heavy (>7000 kg) reverts to per-Sendung flat; komplett LKW flat.

Billing weight: max(100, ceil(actual_kg / 100) * 100).
Band lookup uses actual (raw) weight to select band.

Maut: DE-Maut only = 0.39 EUR / 100 kg on billing weight.
      ES-Maut included in DLV rates ("Inklusive").
Diesel: not_contracted; quarterly Sonder-Dieselfloater billed separately by CHT.
        NOTE: Erlöse_Diesel observed as 0 for all ES rows in BI data (9c.2b).
        Not computed here.

AX-Raten-Präzision: 2dp — empirisch geprüft §6c v1.7.2
  DLV nativ: e.g. bis-4000 Zone 1 = 10.29996  →  AX gespeichert: 10.30
  §8-Hinweis: "AX speichert ES-Raten mit 2dp. Calculator folgt AX-Praxis."

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
_DLV_FILE = _DLV_DIR / "20260112_CHT_Export & Import Spanien, Mallorca.xlsx"
_SHEET    = "Ex- u. Import Spanien"

_VALID_FROM = date(2026, 1, 1)
_VALID_TO   = date(2026, 12, 31)

_MAUT_PER_100KG = Decimal("0.39")  # DE-Maut only; ES-Maut included in rates

_N_MAINLAND_ZONES = 6
_ZONE7_PREFIX     = "07"


class _MainlandBand(NamedTuple):
    weight_limit: int             # upper bound kg
    rates: tuple                  # len=6; rates[z-1] = rate for zone z (per 100 kg)


class _Zone7Band(NamedTuple):
    weight_limit: int
    rate: Decimal
    unit: str   # "per Sendung" | "per 100 kg"


def _parse_es(path: Path) -> tuple[
    list[_MainlandBand],
    dict[int, Decimal],    # mainland komplett per zone (1..6)
    dict[str, int],        # 2-digit plz prefix → zone (1..7)
    list[_Zone7Band],
    Decimal,               # zone-7 komplett
]:
    df = pd.read_excel(path, sheet_name=_SHEET, header=None)
    n_rows = len(df)

    mainland_bands: list[_MainlandBand] = []
    mainland_komplett: dict[int, Decimal] = {}
    plz_to_zone: dict[str, int] = {}
    zone7_bands: list[_Zone7Band] = []
    zone7_komplett: Decimal = Decimal("0")

    # --- locate mainland header (has "Zone 1" ... "Zone 6") ---
    header_row: int | None = None
    zone_cols: list[int] = []
    for ri in range(n_rows):
        row = df.iloc[ri]
        vals = [str(v).strip() for v in row.values]
        if "Zone 1" in vals and "Zone 2" in vals:
            header_row = ri
            zone_cols = [i for i, v in enumerate(vals) if re.match(r"Zone [1-6]$", v)]
            break
    if header_row is None or len(zone_cols) < _N_MAINLAND_ZONES:
        raise ValueError("Could not find mainland zone header in ES DLV")

    # --- parse mainland bands (rows after header until zone table or blank marker) ---
    in_mainland = False
    for ri in range(header_row + 1, n_rows):
        row = df.iloc[ri]
        col0 = str(row.iloc[0]).strip().lower()
        col1 = str(row.iloc[1]).strip()

        if col0 == "bis":
            try:
                wlim = int(float(re.sub(r"[^\d.]", "", col1)))
            except (ValueError, TypeError):
                continue
            rates_raw = []
            ok = True
            for ci in zone_cols:
                try:
                    rates_raw.append(Decimal(str(round(float(row.iloc[ci]), 2))))
                except (ValueError, TypeError, IndexError):
                    ok = False; break
            if ok:
                mainland_bands.append(_MainlandBand(wlim, tuple(rates_raw)))
                in_mainland = True

        elif "kompl" in col1.lower() and in_mainland:
            # Mainland komplett: one value per zone column
            for zi, ci in enumerate(zone_cols, start=1):
                try:
                    mainland_komplett[zi] = Decimal(str(round(float(row.iloc[ci]), 2)))
                except (ValueError, TypeError, IndexError):
                    pass
            in_mainland = False

        elif "zoneneinteilung" in col0 or ("zone 1" in col0 and not in_mainland):
            in_mainland = False

    mainland_bands.sort(key=lambda b: b.weight_limit)

    # --- parse PLZ → zone table (rows with "Zone N" as col[0]) ---
    for ri in range(n_rows):
        row = df.iloc[ri]
        col0 = str(row.iloc[0]).strip()
        m = re.match(r"Zone\s+(\d+)$", col0)
        if not m:
            continue
        zone_num = int(m.group(1))
        for ci in range(1, len(row.values)):
            v = str(row.iloc[ci]).strip()
            if re.match(r"^\d{2}$", v):
                plz_to_zone[v] = zone_num

    # --- parse Mallorca / Zone 7 section ---
    in_zone7 = False
    for ri in range(n_rows):
        row = df.iloc[ri]
        vals = [str(v).strip() for v in row.values[:5]]
        if "Zone 7" in vals[:3]:
            in_zone7 = True
            continue
        if not in_zone7:
            continue

        col0 = str(row.iloc[0]).strip().lower()
        col1 = str(row.iloc[1]).strip()
        col2_raw = row.iloc[2] if len(row.values) > 2 else None
        col3 = str(row.iloc[3]).strip().lower() if len(row.values) > 3 else ""

        if col0 == "bis":
            try:
                wlim = int(float(re.sub(r"[^\d.]", "", col1)))
                rate = Decimal(str(round(float(col2_raw), 2)))
            except (ValueError, TypeError):
                continue
            unit = "per Sendung" if "sendung" in col3 else "per 100 kg"
            zone7_bands.append(_Zone7Band(wlim, rate, unit))

        elif "kompl" in col1.lower() and in_zone7:
            try:
                zone7_komplett = Decimal(str(round(float(col2_raw), 2)))
            except (ValueError, TypeError):
                pass

    zone7_bands.sort(key=lambda b: b.weight_limit)
    return mainland_bands, mainland_komplett, plz_to_zone, zone7_bands, zone7_komplett


class CHTSpainCalculator(TariffCalculator):
    """
    CHT Germany GmbH — Spain tariff (DE-72072 Tübingen origin).
    6 mainland zones by 2-digit PLZ prefix; Zone 7 = Mallorca (PLZ 07-prefix).
    Raises LookupError for non-ES destinations or unknown PLZ prefix.
    """

    customer_name = "CHT Germany GmbH"
    pricing_basis = "kg"

    def __init__(self, dlv_file: Path = _DLV_FILE) -> None:
        self._dlv_file = dlv_file
        self._loaded   = False

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            (self._mainland_bands,
             self._mainland_komplett,
             self._plz_to_zone,
             self._zone7_bands,
             self._zone7_komplett) = _parse_es(self._dlv_file)
            self._loaded = True

    def _lookup_mainland(self, zone: int, actual_kg: float) -> Decimal:
        billing_kg = max(100, math.ceil(actual_kg / 100) * 100)
        for band in self._mainland_bands:
            if band.weight_limit >= actual_kg:
                rate = band.rates[zone - 1]
                soll = rate * Decimal(str(billing_kg)) / Decimal("100")
                komplett = self._mainland_komplett.get(zone)
                if komplett is not None and soll > komplett:
                    soll = komplett
                return soll
        # fall through to komplett cap if nothing matches
        komplett = self._mainland_komplett.get(zone)
        if komplett is not None:
            return komplett
        raise LookupError(f"No ES band covers zone={zone} actual_kg={actual_kg:.1f}")

    def _lookup_zone7(self, actual_kg: float) -> Decimal:
        billing_kg = max(100, math.ceil(actual_kg / 100) * 100)
        for band in self._zone7_bands:
            if band.weight_limit >= actual_kg:
                if band.unit == "per Sendung":
                    return band.rate
                else:
                    soll = band.rate * Decimal(str(billing_kg)) / Decimal("100")
                    if self._zone7_komplett and soll > self._zone7_komplett:
                        soll = self._zone7_komplett
                    return soll
        if self._zone7_komplett:
            return self._zone7_komplett
        raise LookupError(f"No ES Zone-7 band covers actual_kg={actual_kg:.1f}")

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

        if empf_land.strip().upper() != "ES":
            raise LookupError(
                f"CHTSpainCalculator only covers ES; got empf_land={empf_land!r}"
            )
        if tonnage_kg is None or tonnage_kg <= 0:
            raise ValueError("tonnage_kg must be provided and > 0")

        plz_s   = str(empf_plz).strip()
        prefix2 = plz_s[:2].zfill(2)

        zone = self._plz_to_zone.get(prefix2)
        if zone is None:
            raise LookupError(
                f"No ES zone found for PLZ={plz_s!r} (prefix={prefix2!r})"
            )

        actual_kg  = tonnage_kg
        billing_kg = max(100, math.ceil(actual_kg / 100) * 100)

        if zone == 7:
            basispreis = self._lookup_zone7(actual_kg)
        else:
            basispreis = self._lookup_mainland(zone, actual_kg)

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
                f"zone={zone}",
                f"plz={plz_s}",
            ],
            tarifgruppe=f"cht_es_zone{zone}",
            tariff_file_used=str(self._dlv_file.name),
            tariff_year_used=_VALID_FROM.year,
        )
