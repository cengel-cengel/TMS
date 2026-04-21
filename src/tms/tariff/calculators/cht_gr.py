"""
CHT Germany GmbH tariff calculator — Greece.

DLV: "Export Österreich" sheet (sheet name mislabeled; content is Greece —
     §8 DLV-QA-Finding, Klärungsfrage an Operations).
File: 20260112_CHT_Export Griechenland.xlsx

Two-stage billing (billing_scope = "rn"):
  Hauptlauf (HL): DE-Tübingen → GR depot (Athens / Thessaloniki)
    - Single HL charge per RN based on total RN tonnage
    - Rate per 100 kg (band lookup by actual tonnage); minimum 46.63 EUR; maximum 3809.48 EUR
    - Prorated to individual positions by actual_kg / rn_total_kg
  Nachlauf (NL): GR depot → final delivery address
    - One NL charge per Empfänger-Gruppe = (RN, Empfänger_Name)
    - Rate per 100 kg (band lookup by group tonnage); zone-based minimum
    - Prorated to positions within the group by actual_kg / group_total_kg
  Maut: DE-Maut only = 0.56 EUR / 100 kg on RN billing_kg
        Prorated to positions by actual_kg / rn_total_kg
  Diesel: contracted; quarterly Sonder-Dieselfloater.
          Not computed here.

Zone lookup (2-digit PLZ prefix → zone):
  Zone 1: default ("bis 50 km" from Athens/Thessaloniki depot) — all prefixes not in 2-4
  Zone 2: explicit PLZs → 2-digit prefixes: 21 32 35 41 52 58 60 61 67 69
  Zone 3: explicit PLZs + range 46000-46999 → prefixes: 20 27 46
  Zone 4: explicit PLZs → prefixes: 29 68 73 84
  NL Zones 3/4 only available up to 5000 kg ("auf Anfrage" above).

AX-Raten-Präzision: 2dp (empirisch geprüft §6c 9c.2c — |Δ| < 0.001 EUR)
  DLV nativ: e.g. HL bis-1000 = 20.592249...  →  AX gespeichert: 20.59
  §8-Hinweis: "AX speichert GR-Raten mit 2dp. Calculator folgt AX-Praxis."

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

from tms.tariff.base import RNLevelCalculator, RNPosition, TariffResult

_DLV_DIR = Path(
    "/home/user/TMS/data/extracted/v1/Noerpel AI/CHT/DLV/CHT/2026"
)
_DLV_FILE  = _DLV_DIR / "20260112_CHT_Export Griechenland.xlsx"
_SHEET     = "Export Österreich"   # mislabeled; content is Greece

_VALID_FROM = date(2026, 1, 1)
_VALID_TO   = date(2026, 12, 31)

_MAUT_PER_100KG = Decimal("0.56")  # DE-Maut only


def _billing_kg(actual_kg: float) -> int:
    return max(100, math.ceil(actual_kg / 100) * 100)


class _HLBand(NamedTuple):
    weight_limit: int   # upper bound kg (999999 = catch-all for "ab X" row)
    rate: Decimal       # EUR per 100 kg, 2dp


class _NLBand(NamedTuple):
    weight_limit: int
    rate: Decimal       # EUR per 100 kg, 2dp


def _parse_gr(path: Path) -> tuple[
    list[_HLBand],
    Decimal,              # hl_min
    Decimal,              # hl_max
    dict[int, list[_NLBand]],   # zone → NL bands
    dict[int, Decimal],  # zone → NL minimum
    dict[str, int],      # 2-digit PLZ prefix → zone (1..4)
]:
    df = pd.read_excel(path, sheet_name=_SHEET, header=None)
    n  = len(df)

    hl_bands:    list[_HLBand]              = []
    hl_min:      Decimal                    = Decimal("0")
    hl_max:      Decimal                    = Decimal("999999")
    nl_bands:    dict[int, list[_NLBand]]   = {1: [], 2: [], 3: [], 4: []}
    nl_mins:     dict[int, Decimal]         = {}
    nl_zone_cols: list[int]                 = []  # col indices for zones 1-4 in NL table
    plz_to_zone: dict[str, int]             = {}

    in_hl = False
    in_nl = False

    for ri in range(n):
        row  = df.iloc[ri]
        vals = [str(v).strip() for v in row.values]
        col0 = vals[0].lower()
        col1 = vals[1] if len(vals) > 1 else ""
        col1_lower = col1.lower()

        # ── NL section header: row containing 'Zone 1' and 'Zone 2' ──────────
        if "Zone 1" in vals and "Zone 2" in vals and not in_nl:
            nl_zone_cols = [i for i, v in enumerate(vals) if re.match(r"Zone [1-4]$", v)]
            in_nl = True
            in_hl = False
            continue

        # ── HL section: Minimum row (before NL header) ────────────────────────
        if not in_nl and col0 in ("nan", "") and "minimum" in col1_lower:
            try:
                hl_min  = Decimal(str(round(float(row.iloc[2]), 2)))
                in_hl   = True
            except (ValueError, TypeError):
                pass
            continue

        # ── HL Maximum ────────────────────────────────────────────────────────
        if not in_nl and col0 in ("nan", "") and "maximum" in col1_lower:
            try:
                hl_max = Decimal(str(round(float(row.iloc[2]), 2)))
            except (ValueError, TypeError):
                pass
            continue

        # ── HL bands (bis / ab rows, before NL section) ───────────────────────
        if in_hl and not in_nl and col0 in ("bis", "ab"):
            try:
                digits = re.sub(r"[^\d]", "", col1)
                wlim   = 999999 if (col0 == "ab" or not digits) else int(float(digits))
                rate   = Decimal(str(round(float(row.iloc[2]), 2)))
                hl_bands.append(_HLBand(wlim, rate))
            except (ValueError, TypeError):
                pass
            continue

        # ── NL Minimum row ────────────────────────────────────────────────────
        if in_nl and nl_zone_cols and col0 in ("nan", "") and "minimum" in col1_lower:
            for zi, ci in enumerate(nl_zone_cols, start=1):
                try:
                    nl_mins[zi] = Decimal(str(round(float(row.iloc[ci]), 2)))
                except (ValueError, TypeError):
                    pass
            continue

        # ── NL bands (bis / ab rows, after NL header) ─────────────────────────
        if in_nl and nl_zone_cols and col0 in ("bis", "ab"):
            try:
                digits = re.sub(r"[^\d]", "", col1)
                wlim   = 999999 if (col0 == "ab" or not digits) else int(float(digits))
            except (ValueError, TypeError):
                continue
            for zi, ci in enumerate(nl_zone_cols, start=1):
                try:
                    cell = str(row.iloc[ci]).strip().lower()
                    if cell in ("nan", "auf anfrage", "auf anfrage", ""):
                        continue
                    rate = Decimal(str(round(float(row.iloc[ci]), 2)))
                    nl_bands[zi].append(_NLBand(wlim, rate))
                except (ValueError, TypeError):
                    pass
            continue

        # ── Zone PLZ table (rows: "Zone 2" / "Zone 3" / "Zone 4" in col 0) ───
        m = re.match(r"zone\s+([2-4])$", col0.strip())
        if m:
            zone_num = int(m.group(1))
            for ci in range(1, len(vals)):
                v = vals[ci]
                if v in ("nan", ""):
                    continue
                # Range like "46000 - 46999" → take prefix of lower bound
                range_m = re.match(r"(\d+)\s*[-–]\s*\d+", v)
                if range_m:
                    plz_to_zone[range_m.group(1)[:2].zfill(2)] = zone_num
                elif re.match(r"^\d{4,5}(?:\.\d+)?$", v):
                    plz_to_zone[str(int(float(v))).zfill(5)[:2]] = zone_num
            # Continuation rows (col0 = 'nan') parsed in next iterations via
            # the else-clause below.
            continue

        # ── Continuation row for zone table (col0 = 'nan', in zone-scan area) ─
        if in_nl and col0 in ("nan", "") and not nl_zone_cols:
            pass  # pre-NL nan rows; skip
        # Zone continuation rows (additional PLZ values for previously declared zone):
        # We detect them by checking if we're past the zone-table header row 40.
        # Simplest: just re-check if any zone row was the previous row.
        # (handled by parsing Zone 2 row + next nan-row for continuation)
        # Rather, scan for any 4-5 digit PLZ in nan-rows after Zone 4 declaration.

    # Post-process: handle zone continuation rows that start with nan
    # Re-scan rows 40+ for 'nan' rows that are continuation of zone table
    in_zone_scan = False
    current_zone = None
    for ri in range(n):
        row  = df.iloc[ri]
        vals = [str(v).strip() for v in row.values]
        col0 = vals[0].lower()

        m = re.match(r"zone\s+([2-4])$", col0.strip())
        if m:
            current_zone = int(m.group(1))
            in_zone_scan = True
        elif in_zone_scan and col0 in ("nan", "") and current_zone is not None:
            for v in vals[1:]:
                if v in ("nan", ""):
                    continue
                range_m = re.match(r"(\d+)\s*[-–]\s*\d+", v)
                if range_m:
                    plz_to_zone[range_m.group(1)[:2].zfill(2)] = current_zone
                elif re.match(r"^\d{4,5}(?:\.\d+)?$", v):
                    plz_to_zone[str(int(float(v))).zfill(5)[:2]] = current_zone
        elif in_zone_scan and col0 not in ("nan", ""):
            # New non-zone row → stop zone scan (unless it's another Zone row)
            if not re.match(r"zone\s+[2-4]$", col0.strip()):
                in_zone_scan = False
                current_zone = None

    hl_bands.sort(key=lambda b: b.weight_limit)
    for z in nl_bands:
        nl_bands[z].sort(key=lambda b: b.weight_limit)

    return hl_bands, hl_min, hl_max, nl_bands, nl_mins, plz_to_zone


class CHTGreeceCalculator(RNLevelCalculator):
    """
    CHT Germany GmbH — Greece tariff (DE-72072 Tübingen origin).
    billing_scope = "rn": HL once per RN, NL per Empfänger-Gruppe,
    all amounts prorated by actual_kg.
    Raises LookupError for non-GR destinations or missing NL rate.
    """

    customer_name = "CHT Germany GmbH"
    pricing_basis = "kg"
    billing_scope = "rn"

    def __init__(self, dlv_file: Path = _DLV_FILE) -> None:
        self._dlv_file = dlv_file
        self._loaded   = False

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            (self._hl_bands,
             self._hl_min,
             self._hl_max,
             self._nl_bands,
             self._nl_mins,
             self._plz_to_zone) = _parse_gr(self._dlv_file)
            self._loaded = True

    def _get_zone(self, plz5: str) -> int:
        prefix = plz5[:2].zfill(2)
        return self._plz_to_zone.get(prefix, 1)  # Zone 1 = default

    def _hl_charge(self, total_kg: float) -> Decimal:
        bk = _billing_kg(total_kg)
        for band in self._hl_bands:
            if band.weight_limit >= total_kg:
                charge = band.rate * Decimal(str(bk)) / Decimal("100")
                return min(self._hl_max, max(self._hl_min, charge))
        # fallback: last band (catch-all "ab X" entry)
        if self._hl_bands:
            charge = self._hl_bands[-1].rate * Decimal(str(bk)) / Decimal("100")
            return min(self._hl_max, max(self._hl_min, charge))
        raise LookupError(f"No HL band for total_kg={total_kg:.1f}")

    def _nl_charge(self, group_kg: float, zone: int) -> Decimal:
        bk    = _billing_kg(group_kg)
        bands = self._nl_bands.get(zone, [])
        nl_min = self._nl_mins.get(zone, Decimal("0"))
        for band in bands:
            if band.weight_limit >= group_kg:
                return max(nl_min, band.rate * Decimal(str(bk)) / Decimal("100"))
        # fallback: last band (catch-all "ab X" entry for zones 1/2)
        if bands:
            return max(nl_min, bands[-1].rate * Decimal(str(bk)) / Decimal("100"))
        raise LookupError(
            f"No NL band for zone={zone} group_kg={group_kg:.1f} "
            f"(auf Anfrage — not covered in DLV)"
        )

    def calc_rn(
        self,
        positions: list[RNPosition],
    ) -> dict[int | str, TariffResult]:
        if not positions:
            raise ValueError("positions list must not be empty")
        self._ensure_loaded()

        for p in positions:
            if p.empf_land.strip().upper() != "GR":
                raise LookupError(
                    f"CHTGreeceCalculator only covers GR; got empf_land={p.empf_land!r}"
                )
            if p.actual_kg <= 0:
                raise ValueError(f"actual_kg must be > 0; got {p.actual_kg} for position_id={p.position_id}")

        # ── 1. RN-level HL + Maut ─────────────────────────────────────────────
        total_kg  = sum(p.actual_kg for p in positions)
        bk_total  = _billing_kg(total_kg)
        rn_hl     = self._hl_charge(total_kg)
        rn_maut   = _MAUT_PER_100KG * Decimal(str(bk_total)) / Decimal("100")

        # ── 2. NL per Empfänger-Gruppe ────────────────────────────────────────
        groups: dict[str, list[RNPosition]] = {}
        for p in positions:
            groups.setdefault(p.empfaenger_name, []).append(p)

        group_nl:    dict[str, Decimal] = {}
        group_zone:  dict[str, int]     = {}
        group_total: dict[str, float]   = {}
        for name, grp in groups.items():
            grp_kg            = sum(p.actual_kg for p in grp)
            zone              = self._get_zone(grp[0].empf_plz)
            group_nl[name]    = self._nl_charge(grp_kg, zone)
            group_zone[name]  = zone
            group_total[name] = grp_kg

        # ── 3. Prorating per position ─────────────────────────────────────────
        results: dict[int | str, TariffResult] = {}
        d_total_kg = Decimal(str(total_kg))

        for p in positions:
            d_kg       = Decimal(str(p.actual_kg))
            d_grp_kg   = Decimal(str(group_total[p.empfaenger_name]))

            hl_share   = rn_hl    * d_kg / d_total_kg
            maut_share = rn_maut  * d_kg / d_total_kg
            nl_share   = group_nl[p.empfaenger_name] * d_kg / d_grp_kg
            basispreis = hl_share + nl_share

            results[p.position_id] = TariffResult(
                basispreis=basispreis,
                diesel_surcharge=None,
                maut_surcharge=maut_share,
                currency="EUR",
                tariff_file=str(self._dlv_file.name),
                tariff_valid_from=_VALID_FROM,
                tariff_valid_to=_VALID_TO,
                notes=[
                    f"total_kg={total_kg:.2f}",
                    f"billing_kg_hl={bk_total}",
                    f"rn_hl={float(rn_hl):.4f}",
                    f"zone={group_zone[p.empfaenger_name]}",
                    f"group_nl={float(group_nl[p.empfaenger_name]):.4f}",
                    f"plz={p.empf_plz}",
                ],
                tarifgruppe=f"cht_gr_zone{group_zone[p.empfaenger_name]}",
                tariff_file_used=str(self._dlv_file.name),
                tariff_year_used=_VALID_FROM.year,
            )

        return results
