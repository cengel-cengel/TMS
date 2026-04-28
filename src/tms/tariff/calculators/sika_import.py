"""
Sika Supply Center AG (KNR 511241) — Import-Flow Calculator.
Route: ES-28108 (Alcobendas) or IT-28065 (Cerano) → DE-70499 (Stuttgart)

Pricing modes:
  ES-28108 : per-Stellplatz table (1–34 pallets, EUR/Sendung)
  IT-28065 : Komplett-LKW flat-rate only (LKW 1 ≤33 Stellpl., LKW 2 >33)

DE-Maut   : separate "DE-Maut ab 202312" sheet (same Anlage as export DLV)
             ES-origin → fr_es_pt group; IT-origin → at_it group
AT-Maut   : inkludiert in IT flat rates (not billed separately)

Year dispatch: 2025 DLV for 2025 shipments; 2026 DLV for 2026 shipments.
Origin passed via calculate() keyword args: vers_plz / vers_land.
"""
from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from pathlib import Path

import pandas as pd

from tms.tariff.base import TariffCalculator, TariffResult

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DLV_DIR = Path(
    "/home/user/TMS/data/extracted/v1/Noerpel AI/SIka/DLV"
    "/SIKA Deutschland GmbH Stuttgart"
)
_SHEET_OFFERTE = "Offerte"
_SHEET_MAUT    = "DE-Maut ab 202312"

# Max Stellplätze for one complete truck (LKW 1 threshold)
_LKW1_MAX_STP = 33

# DE-Maut group by origin country
_MAUT_GROUP: dict[str, str] = {
    "ES": "fr_es_pt",
    "IT": "at_it",
}

# Cache: year → (es_rates, it_rates, de_maut, valid_from, valid_to, filename)
_DLV_CACHE: dict[int, tuple] = {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cell(v) -> str:
    s = str(v).strip() if v is not None else ""
    return "" if s in ("nan", "NaT", "None") else s


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def _parse_offerte(df: pd.DataFrame) -> tuple[dict[int, Decimal], dict[int, Decimal]]:
    """
    Parse the Offerte sheet.

    Returns:
        es_rates : {stpl_int: price_EUR}   (rows 16-49, col 2, 1-indexed n_pallets)
        it_rates : {lkw_tier: price_EUR}   {1: LKW1_price, 2: LKW2_price}
    """
    es_rates: dict[int, Decimal] = {}
    it_rates: dict[int, Decimal] = {}

    # Data rows start at Excel row 16 (0-based index 15 after header rows)
    # Layout (0-based col):
    #   col 0 = Anzahl Paletten (ES) or "LKW 1"/"LKW 2" label (IT)
    #   col 2 = ES EUR/Sendung
    #   col 5 = IT label ("LKW 1", "LKW 2")
    #   col 6 = IT EUR/Sendung

    for _, row in df.iterrows():
        v0 = _cell(row.iloc[0]) if len(row) > 0 else ""
        v2 = _cell(row.iloc[2]) if len(row) > 2 else ""
        v5 = _cell(row.iloc[5]) if len(row) > 5 else ""
        v6 = _cell(row.iloc[6]) if len(row) > 6 else ""

        # ES: numeric pallet count in col 0, price in col 2
        if v0 and v2:
            try:
                n_pal = int(float(v0))
                price = Decimal(str(round(float(v2), 4)))
                if 1 <= n_pal <= 34:
                    es_rates[n_pal] = price
            except (ValueError, TypeError):
                pass

        # IT: "LKW 1" / "LKW 2" in col 5, price in col 6
        if v5 and v6:
            try:
                lkw_num = int(re.search(r"(\d+)", v5).group(1))
                price   = Decimal(str(round(float(v6), 4)))
                it_rates[lkw_num] = price
            except (AttributeError, ValueError, TypeError):
                pass

    return es_rates, it_rates


def _parse_de_maut(df: pd.DataFrame) -> dict[int, dict[str, Decimal]]:
    """Return {n_pal: {'fr_es_pt': D, 'at_it': D, 'gb_ie': D}}."""
    maut: dict[int, dict[str, Decimal]] = {}

    for _, row in df.iterrows():
        if len(row) < 7:
            continue
        v3 = _cell(row.iloc[3])
        if not v3:
            continue

        m_rng = re.match(r"^(\d+)\s*[-–]\s*(\d+)", v3)
        if m_rng:
            n_pals = list(range(int(m_rng.group(1)), int(m_rng.group(2)) + 1))
        else:
            try:
                n_pals = [int(float(v3))]
            except (ValueError, TypeError):
                continue

        try:
            fr_es_pt = Decimal(str(round(float(_cell(row.iloc[4])), 4)))
            at_it    = Decimal(str(round(float(_cell(row.iloc[5])), 4)))
            gb_ie    = Decimal(str(round(float(_cell(row.iloc[6])), 4)))
        except (ValueError, TypeError):
            continue

        for n in n_pals:
            maut[n] = {"fr_es_pt": fr_es_pt, "at_it": at_it, "gb_ie": gb_ie}

    return maut


# ---------------------------------------------------------------------------
# DLV loader (year-aware, cached)
# ---------------------------------------------------------------------------

def _get_dlv(shipment_date: date) -> tuple:
    """Return (es_rates, it_rates, de_maut, valid_from, valid_to, filename)."""
    year = max(2025, min(2026, shipment_date.year))
    if year in _DLV_CACHE:
        return _DLV_CACHE[year]

    year_dir = _DLV_DIR / str(year)
    files = sorted(year_dir.glob("*Import*.xlsx"))
    if not files:
        raise FileNotFoundError(f"No Sika Import xlsx in {year_dir}")
    path = files[-1]

    df_off  = pd.read_excel(path, sheet_name=_SHEET_OFFERTE, header=None)
    df_maut = pd.read_excel(path, sheet_name=_SHEET_MAUT,    header=None)

    es_rates, it_rates = _parse_offerte(df_off)
    de_maut            = _parse_de_maut(df_maut)

    valid_from = date(year, 1, 1)
    valid_to   = date(year, 12, 31)
    # Extract validity from the Offerte sheet if present
    for _, row in df_off.iterrows():
        v0 = _cell(row.iloc[0]) if len(row) > 0 else ""
        if "ltigkeit" in v0:
            combined = " ".join(_cell(row.iloc[j]) for j in range(min(len(row), 4)))
            dates = re.findall(r"(\d{2})\.(\d{2})\.(\d{4})", combined)
            if len(dates) >= 2:
                valid_from = date(int(dates[0][2]), int(dates[0][1]), int(dates[0][0]))
                valid_to   = date(int(dates[1][2]), int(dates[1][1]), int(dates[1][0]))
            break

    entry = (es_rates, it_rates, de_maut, valid_from, valid_to, path.name)
    _DLV_CACHE[year] = entry
    return entry


# ---------------------------------------------------------------------------
# Rate lookups
# ---------------------------------------------------------------------------

def _lookup_es(es_rates: dict[int, Decimal], stp_int: int) -> Decimal:
    if stp_int in es_rates:
        return es_rates[stp_int]
    max_stp = max(es_rates) if es_rates else 34
    if stp_int > max_stp:
        return es_rates[max_stp]
    raise LookupError(f"SikaImport: no ES rate for stp_int={stp_int}")


def _lookup_it(it_rates: dict[int, Decimal], stp_int: int) -> Decimal:
    tier = 1 if stp_int <= _LKW1_MAX_STP else 2
    price = it_rates.get(tier)
    if price is None:
        raise LookupError(f"SikaImport: no IT LKW{tier} rate in DLV")
    return price


def _lookup_maut(de_maut: dict, vers_land: str, stp_int: int) -> Decimal:
    group = _MAUT_GROUP.get(vers_land.upper())
    if not group or not de_maut:
        return Decimal("0")
    n     = min(stp_int, max(de_maut))
    entry = de_maut.get(n)
    return entry[group] if entry else Decimal("0")


# ---------------------------------------------------------------------------
# Calculator
# ---------------------------------------------------------------------------

class SikaImportCalculator(TariffCalculator):
    """
    Import-Flow Calculator for KNR 511241 (SIKA Supply Center AG).
    Origin: ES-28108 (Alcobendas) or IT-28065 (Cerano).
    Destination: DE-70499 Stuttgart (constant).

    Extra kwargs accepted by calculate():
        vers_plz  : str  — Versender PLZ  (e.g. "28108", "28065")
        vers_land : str  — Versender Land (e.g. "ES", "IT")
    """
    customer_name  = "SIKA Supply Center AG (Import)"
    pricing_basis  = "stellplaetze"
    _tarifgruppe   = "sika_import_stellplatz"

    def calculate(
        self,
        empf_plz: str,
        empf_land: str,
        *,
        stellplaetze: float | None = None,
        shipment_date: date | None = None,
        vers_plz: str | None = None,
        vers_land: str | None = None,
        **_kwargs,
    ) -> TariffResult:
        if stellplaetze is None or stellplaetze < 0:
            raise ValueError("stellplaetze required and must be >= 0")
        if not vers_land:
            raise ValueError("vers_land required (ES or IT)")

        import math
        stp_int  = max(1, math.ceil(float(stellplaetze)))
        vl       = vers_land.strip().upper()
        use_date = shipment_date or date.today()
        year     = max(2025, min(2026, use_date.year))

        es_rates, it_rates, de_maut, valid_from, valid_to, dlv_file = _get_dlv(use_date)

        if vl == "ES":
            base     = _lookup_es(es_rates, stp_int)
            pricing  = f"ES-per-stpl stp={stp_int}"
        elif vl == "IT":
            base     = _lookup_it(it_rates, stp_int)
            tier     = 1 if stp_int <= _LKW1_MAX_STP else 2
            pricing  = f"IT-LKW{tier} stp={stp_int}"
        else:
            raise LookupError(
                f"SikaImport: unsupported vers_land={vl!r}. "
                f"Only ES and IT are in DLV."
            )

        maut = _lookup_maut(de_maut, vl, stp_int)

        return TariffResult(
            basispreis=base.quantize(Decimal("0.01")),
            diesel_surcharge=None,
            maut_surcharge=maut.quantize(Decimal("0.01")),
            other_surcharges={},
            currency="EUR",
            tariff_file=dlv_file,
            tariff_valid_from=valid_from,
            tariff_valid_to=valid_to,
            notes=[
                pricing,
                f"vers_plz={vers_plz}",
                f"vers_land={vl}",
                f"de_maut={maut}",
                f"dlv={dlv_file}",
            ],
            tarifgruppe=self._tarifgruppe,
            tariff_file_used=dlv_file,
            tariff_year_used=year,
        )
