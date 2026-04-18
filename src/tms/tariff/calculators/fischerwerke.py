"""
Fischerwerke GmbH & Co. KG tariff calculator — per-route, Stellplatz-based.

DLV structure: one Excel file per lane (origin × destination).
All rates: flat EUR per Sendung, keyed by integer Stellplätze count.
Diesel & Maut: INCLUDED in all 2025 DLV rates (maut_surcharge=None,
               diesel_surcharge=None for 2025 files). Some 2026 files
               list a diesel% separately; stored in TariffResult.notes.

Billing rule: stellplaetze_int = max(1, ceil(stellplaetze))

Origin (fixed): DE-72178 Waldachtal (Klaus-Fischer-Str. 1).
DLV directory:  data/extracted/v2/Fischer/DLV/{2025,2026}/
Year fallback:  by shipment_date → validity window of each DLV.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Sequence

import pandas as pd

from tms.tariff.base import TariffCalculator, TariffResult

_DLV_ROOT = Path("/home/user/TMS/data/extracted/v2/Fischer/DLV")
_SKIP_DIRS = frozenset({"durch neue offerten ersetzt", "nicht mehr relevant", "upload"})


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class _RouteDLV:
    dest_country: str       # e.g. "IT", "DK", "GB"
    dest_plz_key: str       # e.g. "35127", "4600", "OX", "Dublin"
    prices: dict[int, Decimal]   # Stellplätze (int) → EUR per Sendung
    valid_from: date
    valid_to: date
    tariff_file: str
    diesel_included: bool = True
    diesel_pct: Decimal = Decimal("0")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cell(v) -> str:
    s = str(v).strip() if v is not None else ""
    return "" if s in ("nan", "NaT", "None") else s


def _parse_stpl(s: str) -> list[int] | None:
    """'5' → [5];  '30-33' → [30,31,32,33]; else → None."""
    s = s.strip()
    m = re.match(r"^(\d+)\s*[-\u2013]\s*(\d+)$", s)
    if m:
        return list(range(int(m.group(1)), int(m.group(2)) + 1))
    try:
        return [int(float(s))]
    except (ValueError, TypeError):
        return None


def _parse_date(s: str) -> date | None:
    m = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", s)
    if not m:
        return None
    return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))


# ---------------------------------------------------------------------------
# DLV file parser
# ---------------------------------------------------------------------------

def _parse_dlv_file(path: Path) -> _RouteDLV | None:
    """
    Parse one Fischerwerke per-route DLV file.

    Supports both single-column (IT, ES, IE, GR) and two-column (BE, DK, NL, GB)
    price table layouts.  Only files with origin DE-72... are loaded (filters out
    return / import routes like IT-35127 nach DE-72).
    """
    try:
        df = pd.read_excel(path, header=None)
    except Exception:
        return None

    origin_de72 = False
    dest_country: str | None = None
    dest_plz_key: str | None = None
    valid_from: date | None = None
    valid_to: date | None = None
    diesel_included = True
    diesel_pct = Decimal("0")
    prices: dict[int, Decimal] = {}
    in_table = False

    for i, row in df.iterrows():
        v0 = _cell(row.iloc[0])

        # ── "Ab frei geladen" row ──────────────────────────────────────────
        if v0.startswith("Ab frei geladen"):
            # Require origin to be DE-72...
            if re.search(r"DE-72\d*", v0):
                origin_de72 = True
            else:
                return None   # import or non-Waldachtal route
            # Extract primary destination (last CC-PLZ before ":")
            # Use the pattern after "bis frei Haus" if present
            after = re.split(r"bis frei Haus", v0, maxsplit=1)[-1]
            m = re.search(r"([A-Z]{2})-([A-Z0-9]+)", after)
            if m:
                dest_country = m.group(1)
                dest_plz_key = m.group(2)
            continue

        # ── Validity ─────────────────────────────────────────────────────
        if "ltigkeit" in v0:   # catches Gültigkeit / Gultigkeit
            # Dates may live in any column (often col 3 for IT/DK files)
            combined = " ".join(_cell(row.iloc[j]) for j in range(len(row)))
            dates = re.findall(r"(\d{2})\.(\d{2})\.(\d{4})", combined)
            if len(dates) >= 2:
                valid_from = date(int(dates[0][2]), int(dates[0][1]), int(dates[0][0]))
                valid_to = date(int(dates[1][2]), int(dates[1][1]), int(dates[1][0]))
            continue

        # ── Diesel row ────────────────────────────────────────────────────
        if "Dieselzuschlag" in v0 and not in_table:
            v1 = _cell(row.iloc[1] if len(row) > 1 else "")
            if v1.lower() == "inklusive":
                diesel_included = True
            else:
                try:
                    diesel_pct = Decimal(str(round(float(v1), 4)))
                    diesel_included = False
                except (ValueError, TypeError):
                    diesel_included = True
            continue

        # ── Table header detection ────────────────────────────────────────
        if not in_table:
            v1 = _cell(row.iloc[1]) if len(row) > 1 else ""

            # Two-column header: "Palletten" or "Stellplätze" in col 0
            if v0 in ("Palletten", "Stellpl\u00e4tze", "Stellplatze", "Stellpl."):
                cm = re.search(r"([A-Z]{2})-([A-Z0-9]+)", v1)
                if cm:
                    dest_country = cm.group(1)
                    dest_plz_key = cm.group(2)
                in_table = True
                continue

            # Single-column header: col 0 empty, col 1 has "CC-NNNNN" dest label
            if not v0 and v1:
                cc_m = re.match(r"([A-Z]{2})-([A-Z0-9]+)", v1)
                if cc_m:
                    dest_country = cc_m.group(1)
                    dest_plz_key = cc_m.group(2)
                    in_table = True
                    continue

        # ── Price table rows ──────────────────────────────────────────────
        if in_table:
            stpl_list = _parse_stpl(v0)
            if stpl_list is None:
                # Check if it's genuinely a non-price row (keywords)
                if prices and v0:
                    in_table = False
                continue

            # Left column pair
            v1 = _cell(row.iloc[1] if len(row) > 1 else "")
            try:
                p1 = Decimal(str(round(float(v1), 4)))
                for s in stpl_list:
                    prices[s] = p1
            except (ValueError, TypeError):
                pass

            # Right column pair (two-column layout); gap column may exist between
            # left triplet (col 0-2) and right triplet (col 3-5 or 4-6).
            for rc in range(3, len(row) - 1):
                vs = _cell(row.iloc[rc])
                vp = _cell(row.iloc[rc + 1])
                stpl_list2 = _parse_stpl(vs) if vs else None
                if stpl_list2 and vp:
                    try:
                        p2 = Decimal(str(round(float(vp), 4)))
                        for s in stpl_list2:
                            prices[s] = p2
                    except (ValueError, TypeError):
                        pass
                    break  # only one right-column pair per row

    if not origin_de72 or not dest_country or not prices:
        return None

    # Fallback validity if not found
    if valid_from is None:
        valid_from = date(2025, 1, 1)
    if valid_to is None:
        valid_to = date(2026, 12, 31)

    return _RouteDLV(
        dest_country=dest_country,
        dest_plz_key=dest_plz_key or "",
        prices=prices,
        valid_from=valid_from,
        valid_to=valid_to,
        tariff_file=path.name,
        diesel_included=diesel_included,
        diesel_pct=diesel_pct,
    )


# ---------------------------------------------------------------------------
# Route registry (loaded once, cached)
# ---------------------------------------------------------------------------

_ROUTES: list[_RouteDLV] | None = None


def _load_routes() -> list[_RouteDLV]:
    global _ROUTES
    if _ROUTES is not None:
        return _ROUTES

    routes: list[_RouteDLV] = []
    for p in sorted(_DLV_ROOT.rglob("*.xlsx")):
        # Skip superseded / upload directories
        if any(part.lower() in _SKIP_DIRS for part in p.parts):
            continue
        r = _parse_dlv_file(p)
        if r is not None:
            routes.append(r)

    _ROUTES = routes
    return routes


# ---------------------------------------------------------------------------
# Route lookup
# ---------------------------------------------------------------------------

def _plz_score(dest_plz_key: str, empf_plz: str) -> int:
    """
    Return match score (higher = better) or -1 for definitive mismatch.

    Score 0  = country-only (city-name keys like 'Dublin', 'Athen').
    Score N  = N chars of PLZ matched.
    Score -1 = key present but PLZ conflicts (different IT sub-route etc.).
    """
    key = dest_plz_key.upper()
    # Normalize empf_plz: strip spaces and non-alnum
    plz = re.sub(r"\s+", "", str(empf_plz)).upper()

    if not key:
        return 0

    if key.isalpha():
        if len(key) <= 3:
            # UK area code or short alpha key: check prefix
            return len(key) if plz.startswith(key) else -1
        # City name (Dublin, Athen, etc.): country-only match
        return 0

    if key.isdigit():
        digits = re.sub(r"[^0-9]", "", plz)
        n = min(len(key), len(digits))
        if n == 0:
            return 0
        common = sum(1 for a, b in zip(key, digits) if a == b)
        if common < n and key[:common] != digits[:common]:
            return -1 if common == 0 else common
        return common

    # Alphanumeric (shouldn't occur in practice)
    return len(key) if plz.startswith(key) else 0


def _find_route(dest_country: str, dest_plz: str, shipment_date: date) -> _RouteDLV | None:
    routes = _load_routes()
    iso = dest_country.upper()

    # Filter by country + validity
    candidates = [
        r for r in routes
        if r.dest_country == iso
        and r.valid_from <= shipment_date <= r.valid_to
    ]
    if not candidates:
        return None

    # Score by PLZ match; keep best
    best: _RouteDLV | None = None
    best_score = -2
    for r in candidates:
        score = _plz_score(r.dest_plz_key, dest_plz)
        if score > best_score:
            best_score = score
            best = r

    return best


# ---------------------------------------------------------------------------
# Calculator
# ---------------------------------------------------------------------------

class FischerwerkeCalculator(TariffCalculator):
    customer_name = "Fischerwerke GmbH & Co. KG"
    pricing_basis = "stellplaetze"

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

        route = _find_route(empf_land, empf_plz, use_date)
        if route is None:
            raise LookupError(
                f"No Fischerwerke DLV for land={empf_land!r} plz={empf_plz!r}"
                f" date={use_date}"
            )

        price = route.prices.get(stpl_int)
        if price is None:
            # Use highest available Stellplätze price (table cap)
            max_stpl = max(route.prices)
            if stpl_int > max_stpl:
                price = route.prices[max_stpl]
            else:
                raise LookupError(
                    f"No price for {stpl_int} Stellplätze in {route.tariff_file}"
                )

        notes = [
            f"stpl_int={stpl_int}",
            f"stpl_raw={stellplaetze}",
            f"route={route.dest_country}-{route.dest_plz_key}",
            f"dlv={route.tariff_file}",
        ]
        if not route.diesel_included:
            notes.append(f"diesel_pct={route.diesel_pct} (NOT in basispreis)")

        return TariffResult(
            basispreis=price.quantize(Decimal("0.01")),
            diesel_surcharge=None,
            maut_surcharge=None,
            other_surcharges={},
            currency="EUR",
            tariff_file=route.tariff_file,
            tariff_valid_from=route.valid_from,
            tariff_valid_to=route.valid_to,
            notes=notes,
            tarifgruppe=f"fischerwerke_{route.dest_country.lower()}_{route.dest_plz_key.lower()}",
            tariff_file_used=route.tariff_file,
            tariff_year_used=route.valid_from.year,
        )
