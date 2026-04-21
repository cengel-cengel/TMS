"""
CHT Germany GmbH tariff calculator — Austria.

DLV: "Export Österreich" sheet.
File: 20260112_CHT_Export Österreich.xlsx

Single-stage billing (billing_scope = "position"):
  Fracht: flat per-band rate; actual_kg used directly for band lookup (NOT rounded)
  Maut:   DE-Maut 0.56 EUR / 100 kg on ceil(actual_kg / 100) * 100
  AT-Maut: inclusive in Fracht rate ("inklusive")
  Diesel: not_contracted (Sonder-Dieselfloater per CHT quarterly; None here)

kg_rounding_rule (§2c v1.8.1):
  Fracht: "actual_kg_fracht_only" — actual_kg used directly against band thresholds
           (bis 50, bis 100, bis 150, …) — NO rounding to 100 before lookup.
           e.g. 32.10 kg → bis-50 band → 40.15 EUR flat; 89.72 kg → bis-100 → 51.70 EUR flat
  Maut:   ceil(actual_kg / 100) * 100, minimum 100 kg

Zone lookup (2-digit AT PLZ prefix → zone 1–6):
  Zone 1: 67–69
  Zone 2: 48–49, 50–54
  Zone 3: 40–47, 55–57, 60–66
  Zone 4: 10–19, 22–25
  Zone 5: 20–21, 26–28
  Zone 6: 30–39, 70–75, 80–89, 90–99
  Unknown prefix: raises LookupError (no default zone; §8 if encountered)

AX-Raten-Präzision: 2dp (empirisch geprüft §6c 9c.2d — all |Δ_pos| < 0.004 EUR)
  DLV nativ: e.g. Zone 6 bis-100 = 51.7038 → AX gespeichert: 51.70
  §8-Hinweis: "AX speichert AT-Raten mit 2dp. Calculator folgt AX-Praxis."

Origin: DE-72072 Tübingen (// DE-72144 Dußlingen).
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

_DLV_FILE = Path("/home/user/TMS/CHT/2026/20260112_CHT_Export Österreich.xlsx")
_SHEET    = "Export Österreich"

_VALID_FROM     = date(2026, 1, 1)
_VALID_TO       = date(2026, 12, 31)
_MAUT_PER_100KG = Decimal("0.56")   # DE-Maut only; AT-Maut inclusive in Fracht rate


class _ATBand(NamedTuple):
    weight_limit: int          # upper bound kg (inclusive, "bis X")
    rates: list[Decimal]       # [zone1, zone2, zone3, zone4, zone5, zone6], 2dp


def _parse_at(path: Path) -> tuple[list[_ATBand], dict[int, list[tuple[int, int]]]]:
    """Parse AT DLV Excel.

    Returns:
        bands      : sorted list of _ATBand (weight_limit ascending)
        zone_ranges: {zone_n: [(lo_prefix, hi_prefix), ...]}
    """
    df = pd.read_excel(path, sheet_name=_SHEET, header=None)
    n  = len(df)

    zone_cols:   list[int]                          = []  # col indices for zones 1-6
    bands:       list[_ATBand]                      = []
    zone_ranges: dict[int, list[tuple[int, int]]]   = {}

    for ri in range(n):
        row  = df.iloc[ri]
        vals = [str(v).strip() for v in row.values]
        col0 = vals[0]

        # ── Zone header row: 'Zone 1' … 'Zone 6' ─────────────────────────────
        if "Zone 1" in vals and "Zone 6" in vals and not zone_cols:
            for zone_n in range(1, 7):
                label = f"Zone {zone_n}"
                for ci, v in enumerate(vals):
                    if v == label:
                        zone_cols.append(ci)
                        break
            continue

        # ── Rate rows: col0 = 'bis', col1 = weight limit ──────────────────────
        if zone_cols and col0.lower() == "bis":
            try:
                bis_kg = int(float(re.sub(r"[^\d.]", "", str(row.iloc[1]))))
            except (ValueError, TypeError):
                continue
            rates: list[Decimal] = []
            for ci in zone_cols:
                try:
                    rates.append(Decimal(str(round(float(row.iloc[ci]), 2))))
                except (ValueError, TypeError):
                    rates.append(Decimal("0"))
            if len(rates) == 6:
                bands.append(_ATBand(weight_limit=bis_kg, rates=rates))
            continue

        # ── Zone definition rows: col0 = 'Zone N' ─────────────────────────────
        m = re.match(r"^Zone\s+([1-6])$", col0)
        if m:
            zone_n = int(m.group(1))
            zone_ranges.setdefault(zone_n, [])
            for v in vals[1:]:
                if v in ("nan", ""):
                    continue
                rm = re.match(r"(\d+)\s*[-–]\s*(\d+)", v)
                if rm:
                    zone_ranges[zone_n].append((int(rm.group(1)), int(rm.group(2))))
            continue

    bands.sort(key=lambda b: b.weight_limit)
    return bands, zone_ranges


def _plz_to_zone(plz: str, zone_ranges: dict[int, list[tuple[int, int]]]) -> int:
    """Return zone number (1–6) for a 4-digit AT PLZ string, or raise LookupError."""
    try:
        prefix = int(plz[:2])
    except (ValueError, TypeError) as exc:
        raise LookupError(f"Cannot parse PLZ prefix from {plz!r}") from exc
    for zone_n, ranges in zone_ranges.items():
        for lo, hi in ranges:
            if lo <= prefix <= hi:
                return zone_n
    raise LookupError(
        f"No AT zone for PLZ {plz!r} (2-digit prefix {plz[:2]!r} not in DLV zone table). "
        "Add §8-Eintrag and investigate with Operations."
    )


class CHTAustriaCalculator(TariffCalculator):
    """
    CHT Germany GmbH — Austria tariff (DE-72072 Tübingen origin).
    billing_scope = "position": each shipment priced independently.
    Raises LookupError for non-AT destinations, unknown PLZ zones, or
    tonnage exceeding DLV maximum (20 000 kg).
    """

    customer_name = "CHT Germany GmbH"
    pricing_basis = "kg"
    billing_scope = "position"

    def __init__(self, dlv_file: Path = _DLV_FILE) -> None:
        self._dlv_file   = dlv_file
        self._bands:       list[_ATBand] | None                 = None
        self._zone_ranges: dict[int, list[tuple[int, int]]] | None = None

    def _ensure_loaded(self) -> None:
        if self._bands is None:
            self._bands, self._zone_ranges = _parse_at(self._dlv_file)

    def _get_rate(self, actual_kg: float, zone: int) -> Decimal:
        """Find the flat Fracht rate for actual_kg in zone (1–6)."""
        assert self._bands is not None
        col = zone - 1
        for band in self._bands:
            if actual_kg <= band.weight_limit:
                return band.rates[col]
        raise LookupError(
            f"actual_kg={actual_kg:.2f} exceeds maximum DLV band "
            f"({self._bands[-1].weight_limit} kg) for AT zone {zone}."
        )

    def calculate(
        self,
        empf_plz: str,
        empf_land: str,
        *,
        lademeter:   float | None = None,
        stellplaetze: int  | None = None,
        tonnage_kg:  float | None = None,
        ldm:         float | None = None,
    ) -> TariffResult:
        self._ensure_loaded()
        assert self._bands is not None and self._zone_ranges is not None

        if empf_land.strip().upper() != "AT":
            raise LookupError(
                f"CHTAustriaCalculator only covers AT; got empf_land={empf_land!r}"
            )
        if tonnage_kg is None or tonnage_kg <= 0:
            raise ValueError("tonnage_kg must be provided and > 0")

        actual_kg = tonnage_kg
        zone      = _plz_to_zone(str(empf_plz).strip(), self._zone_ranges)

        # Fracht: flat rate from band, using actual_kg directly (no rounding)
        basispreis = self._get_rate(actual_kg, zone)

        # DE-Maut: ceil to 100 kg, minimum 100 kg
        maut_kg = max(100, math.ceil(actual_kg / 100) * 100)
        maut    = _MAUT_PER_100KG * Decimal(str(maut_kg)) / Decimal("100")

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
                f"maut_kg={maut_kg}",
                f"zone={zone}",
                f"plz={empf_plz}",
            ],
            tarifgruppe=f"cht_at_zone{zone}",
            tariff_file_used=str(self._dlv_file.name),
            tariff_year_used=_VALID_FROM.year,
        )
