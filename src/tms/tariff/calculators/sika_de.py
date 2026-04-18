"""
Sika Deutschland GmbH (KNR 491063) & SIKA Supply Center AG (KNR 511241) —
Stellplatz-based tariff calculator.

Shared DLV:  'SIKA DE & SSC Export div. LKZ_Stellplatzofferte[_2026].xlsx'
  Sheet 'Sika Export Rates 2025':  flat EUR/Sendung keyed by Stellplätze × destination
  Sheet 'DE-Maut ab 202312':       additional maut per Stellplätze by country group

Billing rule:    stpl_int = max(1, ceil(stellplaetze)), capped at 33 (DLV max)
Origin:          DE-70439 Stuttgart (Sika GmbH, Kornwestheimer Strasse)
DE-Maut groups:  FR/ES/PT = 201-300 km; AT/IT = 301-400 km; GB/IE = 401-500 km
Year selection:  2025 DLV for 2025 shipments; 2026 DLV for 2026 shipments.
"""
from __future__ import annotations

import math
import re
from datetime import date
from decimal import Decimal
from pathlib import Path

import pandas as pd

from tms.tariff.base import TariffCalculator, TariffResult

_DLV_DIR = Path(
    "/home/user/TMS/data/extracted/v1/Noerpel AI/SIka/DLV"
    "/SIKA Deutschland GmbH Stuttgart"
)
_SHEET_RATES = "Sika Export Rates 2025"
_SHEET_MAUT  = "DE-Maut ab 202312"

_MAUT_GROUP: dict[str, str] = {
    "FR": "fr_es_pt", "ES": "fr_es_pt", "PT": "fr_es_pt",
    "AT": "at_it",    "IT": "at_it",
    "GB": "gb_ie",    "IE": "gb_ie",
}

# Cache: year → (rates, de_maut, valid_from, valid_to, filename)
_DLV_CACHE: dict[int, tuple] = {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cell(v) -> str:
    s = str(v).strip() if v is not None else ""
    return "" if s in ("nan", "NaT", "None") else s


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

def _parse_rates_sheet(
    df: pd.DataFrame,
) -> dict[tuple[str, str], dict[int, Decimal]]:
    """Return {(country, zip_key): {stpl_int: price}} from first section only."""
    stpl_cols: dict[int, int] = {}
    header_row_idx = -1

    for i, row in df.iterrows():
        if len(row) < 5:
            continue
        if _cell(row.iloc[3]) == "1":
            for c in range(3, len(row)):
                v = _cell(row.iloc[c])
                if not v:
                    continue
                try:
                    stpl_cols[int(float(v))] = c
                except (ValueError, TypeError):
                    pass
            if stpl_cols:
                header_row_idx = int(i)
                break

    rates: dict[tuple[str, str], dict[int, Decimal]] = {}
    for i, row in df.iterrows():
        if int(i) <= header_row_idx:
            continue
        v0 = _cell(row.iloc[0])
        v1 = _cell(row.iloc[1]) if len(row) > 1 else ""

        if "Pallet Place" in v0 or "pallet place" in v0.lower():
            break

        if v0 not in ("ES", "GB", "PT", "IT", "IE", "FR", "AT") or not v1:
            continue

        prices: dict[int, Decimal] = {}
        for stpl, col in stpl_cols.items():
            if col >= len(row):
                continue
            v = _cell(row.iloc[col])
            if v in ("", "auf Anfrage"):
                continue
            try:
                prices[stpl] = Decimal(str(round(float(v), 4)))
            except (ValueError, TypeError):
                pass

        if prices:
            rates[(v0, v1)] = prices

    return rates


def _parse_de_maut_sheet(
    df: pd.DataFrame,
) -> dict[int, dict[str, Decimal]]:
    """Return {n_pal: {'fr_es_pt': D, 'at_it': D, 'gb_ie': D}}."""
    maut: dict[int, dict[str, Decimal]] = {}

    for _, row in df.iterrows():
        if len(row) < 7:
            continue
        v3 = _cell(row.iloc[3])
        if not v3:
            continue

        m_rng = re.match(r"^(\d+)\s*[-\u2013]\s*(\d+)", v3)
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
    year = max(2025, min(2026, shipment_date.year))
    if year in _DLV_CACHE:
        return _DLV_CACHE[year]

    year_dir = _DLV_DIR / str(year)
    # Prefer files with "Stellplatzofferte" in the name (export rate file)
    files = sorted(year_dir.glob("*Stellplatz*.xlsx"))
    if not files:
        files = sorted(f for f in year_dir.glob("*.xlsx") if "Upload" not in str(f))
    if not files:
        raise FileNotFoundError(f"No Sika Stellplatzofferte xlsx in {year_dir}")
    path = files[-1]

    df_rates = pd.read_excel(path, sheet_name=_SHEET_RATES, header=None)
    df_maut  = pd.read_excel(path, sheet_name=_SHEET_MAUT,  header=None)

    rates   = _parse_rates_sheet(df_rates)
    de_maut = _parse_de_maut_sheet(df_maut)

    valid_from = date(year, 1, 1)
    valid_to   = date(year, 12, 31)
    for _, row in df_rates.iterrows():
        v0 = _cell(row.iloc[0])
        if "ltigkeit" in v0:
            combined = " ".join(_cell(row.iloc[j]) for j in range(min(len(row), 8)))
            dates = re.findall(r"(\d{2})\.(\d{2})\.(\d{4})", combined)
            if len(dates) >= 2:
                valid_from = date(int(dates[0][2]), int(dates[0][1]), int(dates[0][0]))
                valid_to   = date(int(dates[1][2]), int(dates[1][1]), int(dates[1][0]))
            break

    entry = (rates, de_maut, valid_from, valid_to, path.name)
    _DLV_CACHE[year] = entry
    return entry


# ---------------------------------------------------------------------------
# Destination matching
# ---------------------------------------------------------------------------

def _find_zip_key(
    country: str,
    plz: str,
    rates: dict[tuple[str, str], dict],
) -> str | None:
    cc = country.upper()
    plz_clean = re.sub(r"\s+", "", str(plz)).upper()
    keys = [k for (c, k) in rates if c == cc]
    if not keys:
        return None

    if cc == "ES":
        plz2 = plz_clean[:2]
        for key in keys:
            ku = key.upper()
            if re.search(r"XXX", ku):
                prefix = re.sub(r"XXX.*", "", ku).strip()
                if plz_clean.startswith(prefix):
                    return key
            else:
                if plz2 in [c.strip() for c in key.split(",")]:
                    return key

    elif cc == "GB":
        m = re.match(r"^([A-Z]+)", plz_clean)
        area = m.group(1) if m else ""
        for key in keys:
            parts = re.sub(r"^GB-?", "", key).split("-")
            if area in parts:
                return key

    elif cc == "IT":
        plz2 = plz_clean[:2]
        for key in keys:
            codes = re.sub(r"^IT-?", "", key, flags=re.IGNORECASE)
            code_list = [c for c in re.split(r"[+\s]", codes) if c.isdigit()]
            if plz2 in code_list:
                return key

    elif cc == "PT":
        plz1 = plz_clean[0] if plz_clean else ""
        for key in keys:
            key_n = re.sub(r"^PT-?", "", key, flags=re.IGNORECASE)
            if plz1 == key_n:
                return key

    elif cc == "IE":
        for key in keys:
            area = re.sub(r"^IE-?", "", key, flags=re.IGNORECASE)
            if plz_clean.startswith(area):
                return key

    return None


# ---------------------------------------------------------------------------
# Rate and maut lookups
# ---------------------------------------------------------------------------

def _lookup_rate(
    rates: dict,
    country: str,
    plz: str,
    stpl_int: int,
) -> Decimal | None:
    zip_key = _find_zip_key(country, plz, rates)
    if zip_key is None:
        return None
    prices = rates.get((country.upper(), zip_key))
    if prices is None:
        return None
    if stpl_int in prices:
        return prices[stpl_int]
    max_stpl = max(prices)
    if stpl_int > max_stpl:
        return prices[max_stpl]
    return None


def _lookup_maut(
    de_maut: dict[int, dict],
    country: str,
    stpl_int: int,
) -> Decimal:
    group = _MAUT_GROUP.get(country.upper())
    if group is None or not de_maut:
        return Decimal("0")
    n = min(stpl_int, max(de_maut))
    entry = de_maut.get(n)
    return entry[group] if entry else Decimal("0")


# ---------------------------------------------------------------------------
# Shared base calculator
# ---------------------------------------------------------------------------

class _SikaBase(TariffCalculator):
    pricing_basis = "stellplaetze"
    _tarifgruppe: str = "sika_stellplatz"

    def calculate(
        self,
        empf_plz: str,
        empf_land: str,
        *,
        lademeter: float | None = None,
        stellplaetze: float | None = None,
        tonnage_kg: float | None = None,
        ldm: float | None = None,
        shipment_date: date | None = None,
    ) -> TariffResult:
        if stellplaetze is None or stellplaetze < 0:
            raise ValueError("stellplaetze required and must be >= 0")

        stpl_int = max(1, math.ceil(stellplaetze))
        use_date = shipment_date or date.today()
        year = max(2025, min(2026, use_date.year))

        rates, de_maut, valid_from, valid_to, dlv_file = _get_dlv(use_date)

        base = _lookup_rate(rates, empf_land, empf_plz, stpl_int)
        if base is None:
            raise LookupError(
                f"No Sika DLV rate for land={empf_land!r} plz={empf_plz!r}"
                f" stpl={stpl_int}"
            )

        maut     = _lookup_maut(de_maut, empf_land, stpl_int)
        zip_key  = _find_zip_key(empf_land, empf_plz, rates)

        notes = [
            f"stpl_int={stpl_int}",
            f"stpl_raw={stellplaetze}",
            f"zip_key={empf_land}-{zip_key}",
            f"dlv={dlv_file}",
            f"de_maut={maut}",
        ]

        return TariffResult(
            basispreis=base.quantize(Decimal("0.01")),
            diesel_surcharge=None,
            maut_surcharge=maut.quantize(Decimal("0.01")),
            other_surcharges={},
            currency="EUR",
            tariff_file=dlv_file,
            tariff_valid_from=valid_from,
            tariff_valid_to=valid_to,
            notes=notes,
            tarifgruppe=self._tarifgruppe,
            tariff_file_used=dlv_file,
            tariff_year_used=year,
        )


# ---------------------------------------------------------------------------
# Concrete calculators
# ---------------------------------------------------------------------------

class SikaDeCalculator(_SikaBase):
    customer_name = "Sika Deutschland GmbH"
    _tarifgruppe = "sika_de_stellplatz"


class SSCCalculator(_SikaBase):
    customer_name = "SIKA Supply Center AG"
    _tarifgruppe = "ssc_stellplatz"
