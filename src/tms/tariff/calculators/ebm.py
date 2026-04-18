"""
EBM-Papst Mulfingen tariff calculator.

DLV: Palletspace-based (Stückgut 1-5, LTL/FTL 6-33 Palletspaces).
     Each pallet space = 0.4 LDM.
     Origin fixed: DE-74673 Mulfingen.

Sheet layout of Tariffs_DE_EU / Toll_DE_EU:
  Row 5: pallet counts  [nan, nan, nan, 1, 2, 3, 4, 5, nan, 6, 7, …, 33]
  Row 7: "Pick up Location | To EU-Location | Leadtime | price_col…"
  Rows 9+: data rows

Column index mapping (0-based):
  0 = origin
  1 = destination key  (e.g. "IE-H91", "PL-59-241", "EE-75301 | EE-75306")
  2 = leadtime Stückgut
  3..7 = pallets 1-5  (col_idx = pallet + 2)
  8 = leadtime LTL
  9..36 = pallets 6-33  (col_idx = pallet + 3)
  "-" entries mean on-request / not offered.
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
    "/home/user/TMS/data/extracted/v1/Noerpel AI/EBM/DLV"
)
_DLV_FILE = (
    _DLV_DIR
    / "20260227_ebm-papst Mulfingen GmbH  Co. KG 74673 Hollenbach_Export Europa.xlsx"
)
_VALID_FROM = date(2026, 3, 1)
_VALID_TO   = date(2026, 12, 31)

# Fallback 2025 DLV (covers 2025-10 – 2026-02)
_DLV_2025_FILE = (
    _DLV_DIR
    / "durch neue Offerten ersetzt"
    / "20251010_ebm-papst Mulfingen GmbH  Co. KG 74673 Hollenbach_Export SI SK PL HR EE IE.xlsx"
)
_VALID_2025_FROM = date(2025, 10, 10)
_VALID_2025_TO   = date(2026, 2, 28)

# Earlier 2025 DLV for PL + IE (pre-October)
_DLV_2025_PL_IE_FILE = (
    _DLV_DIR
    / "durch neue Offerten ersetzt"
    / "20250512_ebm-papst Mulfingen GmbH  Co. KG, 74673 Hollenbach_Export PL, IE.xlsx"
)


def _col_for_pallets(n: int) -> int:
    """0-based column index for n pallet spaces in the DLV sheet."""
    if n <= 5:
        return n + 2      # pallet 1→col3, 2→col4, …, 5→col7
    else:
        return n + 3      # pallet 6→col9, 7→col10, …, 33→col36


def _parse_dest_keys(raw: str) -> list[str]:
    """Split combined keys like 'EE-75301 | EE-75306' → ['EE-75301', 'EE-75306']."""
    return [k.strip() for k in str(raw).split("|")]


def _extract_dest_prefix(key: str) -> tuple[str, str]:
    """'IE-H91' → ('IE', 'H91').  'PL-59-241' → ('PL', '59-241')."""
    parts = key.split("-", 1)
    if len(parts) == 2:
        return parts[0].upper(), parts[1].strip()
    return "", key.strip()


class _RateRow(NamedTuple):
    land: str
    plz_prefix: str
    prices: dict[int, Decimal]   # n_pallets → price


def _load_sheet(path: Path, sheet: str) -> list[_RateRow]:
    """Parse a Tariffs_DE_EU or Toll_DE_EU sheet into _RateRow list."""
    df = pd.read_excel(path, sheet_name=sheet, header=None)

    # Row 5 carries pallet count headers
    pallet_row = df.iloc[5]
    # Build col → pallet_count map (skip NaN / non-int entries)
    col_to_pallet: dict[int, int] = {}
    for col_idx, val in enumerate(pallet_row):
        try:
            pallet = int(float(val))
            col_to_pallet[col_idx] = pallet
        except (ValueError, TypeError):
            pass

    rows: list[_RateRow] = []
    for _, row in df.iloc[9:].iterrows():
        dest_raw = row.iloc[1]
        if pd.isna(dest_raw) or str(dest_raw).strip() in ("", "nan"):
            continue
        for key in _parse_dest_keys(str(dest_raw)):
            land, plz_pfx = _extract_dest_prefix(key)
            if not land:
                continue
            prices: dict[int, Decimal] = {}
            for col_idx, n_pallet in col_to_pallet.items():
                val = row.iloc[col_idx]
                try:
                    f = float(val)
                    if not math.isnan(f) and f > 0:
                        prices[n_pallet] = Decimal(str(round(f, 4)))
                except (ValueError, TypeError):
                    pass
            if prices:
                rows.append(_RateRow(land=land, plz_prefix=plz_pfx, prices=prices))
    return rows


def _normalize_plz(plz: str) -> str:
    return str(plz).strip().upper()


def _match_plz(empf_plz_norm: str, plz_prefix: str) -> bool:
    """True if normalized empf_plz starts with the DLV prefix.

    Handles:
    - IE Eircodes:  prefix "H91"  matches "H91", "H91 X123", etc.
    - PL/EE:        prefix "59-241" matches plz "59-220" via first 2 chars before "-"
    - SK:           prefix "913 11" matches plz "913 11", "913 04" etc.
    - SI/HR:        prefix "1370"  matches plz "1370"
    """
    p = plz_prefix.upper()
    plz = empf_plz_norm

    # Exact or startswith
    if plz == p or plz.startswith(p):
        return True

    # PL/EE: match on the segment before the first dash or space
    if "-" in p:
        prefix_seg = p.split("-")[0]
        plz_seg = plz.split("-")[0].split(" ")[0]
        if plz_seg == prefix_seg:
            return True

    # SK: numeric space-separated, match first 3 digits
    if " " in p:
        prefix_digits = re.sub(r"\D", "", p)[:3]
        plz_digits = re.sub(r"\D", "", plz)[:3]
        if prefix_digits and plz_digits and prefix_digits == plz_digits:
            return True

    # IE: first 3 chars of routing key
    if len(p) >= 3 and len(plz) >= 3:
        if plz[:3] == p[:3]:
            return True

    return False


class EBMCalculator(TariffCalculator):
    """
    Tariff calculator for EBM-Papst Mulfingen.
    Uses the 2026 DLV (01.03.2026–31.12.2026).
    """

    customer_name = "EBM-Papst Mulfingen GmbH & Co. KG"
    pricing_basis = "stellplaetze"

    def __init__(self, dlv_file: Path = _DLV_FILE) -> None:
        self._dlv_file = dlv_file
        self._tariff_rows: list[_RateRow] | None = None
        self._toll_rows: list[_RateRow] | None = None

    def _ensure_loaded(self) -> None:
        if self._tariff_rows is None:
            self._tariff_rows = _load_sheet(self._dlv_file, "Tariffs_DE_EU")
            self._toll_rows = _load_sheet(self._dlv_file, "Toll_DE_EU")

    def _lookup(
        self, rows: list[_RateRow], empf_land: str, empf_plz: str, n_pallets: int
    ) -> Decimal | None:
        plz_norm = _normalize_plz(empf_plz)
        land_upper = empf_land.strip().upper()
        for rate_row in rows:
            if rate_row.land != land_upper:
                continue
            if not _match_plz(plz_norm, rate_row.plz_prefix):
                continue
            prices = rate_row.prices
            if not prices:
                continue
            max_pallet = max(prices)
            n = min(n_pallets, max_pallet)
            # Walk down to find a price (some cols may be absent for very high counts)
            while n >= 1:
                if n in prices:
                    return prices[n]
                n -= 1
        return None

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

        # Resolve n_pallets from lademeter (primary) or stellplaetze
        ldm_val = lademeter if lademeter is not None else ldm
        if ldm_val is not None and ldm_val > 0:
            n_pallets = max(1, math.ceil(ldm_val / 0.4))
        elif stellplaetze is not None and stellplaetze > 0:
            n_pallets = int(stellplaetze)
        else:
            raise ValueError("Either lademeter or stellplaetze must be provided and > 0")

        basispreis = self._lookup(self._tariff_rows, empf_land, empf_plz, n_pallets)
        if basispreis is None:
            raise LookupError(
                f"No EBM tariff rate for land={empf_land!r} PLZ={empf_plz!r} "
                f"n_pallets={n_pallets}"
            )

        toll = self._lookup(self._toll_rows, empf_land, empf_plz, n_pallets)

        return TariffResult(
            basispreis=basispreis,
            diesel_surcharge=None,
            maut_surcharge=toll,
            currency="EUR",
            tariff_file=str(self._dlv_file.name),
            tariff_valid_from=_VALID_FROM,
            tariff_valid_to=_VALID_TO,
            notes=[f"n_pallets={n_pallets} (from ldm={ldm_val})"],
            tarifgruppe="ebm_papst_stellplaetze",
            tariff_file_used=str(self._dlv_file.name),
            tariff_year_used=_VALID_FROM.year,
        )
