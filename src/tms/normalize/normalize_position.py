"""Position-label taxonomy routing for Dinas and AX billing data.

Etappe 9a.1.F.2a: Maps raw cost-position labels from the Dinas PDF parser
(stored in the `sonstige` column of dinas_pdfs.parquet) and from AX BI columns
(bi_top20_data.pkl) into a shared 11-category taxonomy:

    fracht | diesel | maut | transportversicherung | verzollung |
    lademittel | gefahrgut | gb_safety_ssd | avisgebuehr |
    langgutzuschlag | sonstige_nebengeb

Public API
----------
route_dinas_label(label_str)         -> str
decompose_dinas_sonstige(raw)        -> dict[str, float]
build_dinas_taxonomy_row(row)        -> dict[str, float]
build_ax_taxonomy_row(row)           -> dict[str, float]
"""
from __future__ import annotations

import ast
import logging
import math
from typing import Any

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Taxonomy constants
# ---------------------------------------------------------------------------

ALL_TAXONOMY_KEYS: tuple[str, ...] = (
    "fracht",
    "diesel",
    "maut",
    "transportversicherung",
    "verzollung",
    "lademittel",
    "gefahrgut",
    "gb_safety_ssd",
    "avisgebuehr",
    "langgutzuschlag",
    "sonstige_nebengeb",
)

# Keys that decompose_dinas_sonstige can produce (subset of taxonomy)
_SONSTIGE_KEYS: frozenset[str] = frozenset({
    "maut",
    "gefahrgut",
    "gb_safety_ssd",
    "avisgebuehr",
    "langgutzuschlag",
    "lademittel",
    "sonstige_nebengeb",
})

_ZERO_TAXONOMY: dict[str, float] = {k: 0.0 for k in ALL_TAXONOMY_KEYS}
_ZERO_SONSTIGE: dict[str, float] = {k: 0.0 for k in _SONSTIGE_KEYS}


# ---------------------------------------------------------------------------
# FUNKTION 1 — route_dinas_label
# ---------------------------------------------------------------------------

def route_dinas_label(label_str: str) -> str:
    """Route a single Dinas position label to a taxonomy category.

    Match order is intentional:

    1. "NEBENKOSTENPAUSCHALE" is checked **before** "MAUT" because labels like
       "NEBENKOSTENPAUSCHALE MAUT AT 2025" contain the word "MAUT" but represent
       a bundled surcharge, not a pure toll entry.  Routing them to "maut" would
       double-count toll against the dedicated `maut` column.

    2. "GEFAHRGUT" is checked before the generic fallback but after MAUT, since
       "GEFAHRGUTZUSCHLAG ADR FÄHRKOSTEN" does NOT contain "MAUT" and must not
       accidentally reach the maut branch.

    3. "SSD F. GB" (Safety & Security surcharge for UK shipments) is its own
       category so it stays separable from ordinary Nebengebühren in GB analysis.

    4. "AVIS" catches all AVISGEBÜHR variants (AVISGEBÜHR, AVIS GEBÜHR, etc.)
       via substring match.

    5. Everything else falls through to "sonstige_nebengeb".
    """
    u = str(label_str).upper()

    # --- bundled-surcharge labels that contain substrings of other categories ---
    # Both must be checked BEFORE "MAUT" because they contain that substring:
    #   "NEBENKOSTENPAUSCHALE MAUT AT 2025" → sonstige_nebengeb (not maut)
    #   "SSD F. GB / MAUT 2025 …"           → gb_safety_ssd     (not maut)
    if "NEBENKOSTENPAUSCHALE" in u:
        return "sonstige_nebengeb"

    if "SSD F. GB" in u or "SAFETY+SECURITY" in u or "SAFETY + SECURITY" in u:
        return "gb_safety_ssd"

    # --- dedicated categories ---
    if "MAUT" in u or "D-MAUT" in u:
        return "maut"

    if "GEFAHRGUT" in u:
        return "gefahrgut"

    if "AVIS" in u:
        return "avisgebuehr"

    if "LANGGUT" in u:
        return "langgutzuschlag"

    if "TAUSCH" in u or "EUROPAL" in u or "GITTERBOX" in u:
        return "lademittel"

    if "THERMOZUSCHLAG" in u:
        return "sonstige_nebengeb"

    if "TERMINZUSCHLAG" in u:
        return "sonstige_nebengeb"

    if "MEHRKOSTEN F. EXPRESS" in u or ("MEHRKOSTEN" in u and "EXPRESS" in u):
        return "sonstige_nebengeb"

    if "EXPRESS" in u:
        return "sonstige_nebengeb"

    if "SONSTIGE NEBENGEBÜHR" in u or "SONSTIGE NEBENGEBUEHR" in u:
        return "sonstige_nebengeb"

    return "sonstige_nebengeb"


# ---------------------------------------------------------------------------
# FUNKTION 2 — decompose_dinas_sonstige
# ---------------------------------------------------------------------------

def _safe_float(v: Any) -> float:
    """Convert v to float; return 0.0 on any failure."""
    try:
        f = float(v)
        return 0.0 if math.isnan(f) else f
    except (TypeError, ValueError):
        return 0.0


def _extract_label_amount(item: Any) -> tuple[str, float]:
    """Extract (label, amount) from one sonstige item regardless of structure."""
    if isinstance(item, dict):
        label = str(item.get("label") or item.get("l") or "")
        amount = _safe_float(item.get("amount") or item.get("a") or 0)
    elif isinstance(item, (list, tuple)) and len(item) >= 2:
        label = str(item[0])
        amount = _safe_float(item[1])
    elif isinstance(item, (list, tuple)) and len(item) == 1:
        label = str(item[0])
        amount = 0.0
    else:
        label = str(item)
        amount = 0.0
    return label, amount


def decompose_dinas_sonstige(sonstige_raw: Any) -> dict[str, float]:
    """Parse a Dinas `sonstige` cell and return per-category cumulative amounts.

    Parameters
    ----------
    sonstige_raw:
        The raw value from the `sonstige` column of dinas_pdfs.parquet.
        Typically a stringified Python list of dicts, e.g.:
            "[{'label': 'D-MAUT STANDARD', 'amount': '2.00', ...}]"
        Also accepts an already-parsed list (for tests / in-memory use).

    Returns
    -------
    dict with keys from _SONSTIGE_KEYS, all present and ≥ 0.0.
    Returns all-zero dict on any parse error without raising.
    """
    result: dict[str, float] = dict(_ZERO_SONSTIGE)

    if sonstige_raw is None:
        return result
    if isinstance(sonstige_raw, float) and math.isnan(sonstige_raw):
        return result

    # Already a list — use directly
    if isinstance(sonstige_raw, list):
        items = sonstige_raw
    else:
        raw_str = str(sonstige_raw).strip()
        if not raw_str or raw_str in ("[]", "nan", "None"):
            return result
        try:
            items = ast.literal_eval(raw_str)
        except Exception:
            log.warning("decompose_dinas_sonstige: could not parse %r", raw_str[:120])
            return result

    if not isinstance(items, list):
        return result

    for item in items:
        try:
            label, amount = _extract_label_amount(item)
            category = route_dinas_label(label)
            if category in result:
                result[category] += amount
        except Exception:
            continue

    return result


# ---------------------------------------------------------------------------
# FUNKTION 3 — build_dinas_taxonomy_row
# ---------------------------------------------------------------------------

def build_dinas_taxonomy_row(parquet_row: Any) -> dict[str, float]:
    """Build a complete 11-category taxonomy dict from one dinas_pdfs.parquet row.

    Parameters
    ----------
    parquet_row:
        A pandas Series or dict-like with keys: fracht, diesel, maut,
        sonstige, sendungssumme.

    Returns
    -------
    dict with all ALL_TAXONOMY_KEYS present. All NaN / None → 0.0.
    GESAMT key added as row['sendungssumme'].
    """
    def _get(key: str) -> float:
        v = parquet_row[key] if hasattr(parquet_row, "__getitem__") else getattr(parquet_row, key, None)
        return _safe_float(v)

    decomp = decompose_dinas_sonstige(
        parquet_row["sonstige"] if hasattr(parquet_row, "__getitem__") else getattr(parquet_row, "sonstige", None)
    )

    return {
        "fracht":                 _get("fracht"),
        "diesel":                 _get("diesel"),
        "maut":                   _get("maut") + decomp["maut"],
        "transportversicherung":  0.0,
        "verzollung":             0.0,
        "lademittel":             decomp["lademittel"],
        "gefahrgut":              decomp["gefahrgut"],
        "gb_safety_ssd":          decomp["gb_safety_ssd"],
        "avisgebuehr":            decomp["avisgebuehr"],
        "langgutzuschlag":        decomp["langgutzuschlag"],
        "sonstige_nebengeb":      decomp["sonstige_nebengeb"],
        "GESAMT":                 _get("sendungssumme"),
    }


# ---------------------------------------------------------------------------
# FUNKTION 4 — build_ax_taxonomy_row
# ---------------------------------------------------------------------------

def build_ax_taxonomy_row(bi_top20_row: Any) -> dict[str, float]:
    """Build a complete 11-category taxonomy dict from one bi_top20_data POST row.

    Parameters
    ----------
    bi_top20_row:
        A pandas Series or dict-like with AX Erlöse columns.

    Returns
    -------
    dict with all ALL_TAXONOMY_KEYS present. All NaN / None → 0.0.
    GESAMT key added as row['Erloese'].

    Notes
    -----
    Vorlageprovision is indistinguishable from other Nebengebühren in bi_top20
    (no position-label column available).  It therefore flows into
    `sonstige_nebengeb` together with `Erlöse Peak`.
    `gefahrgut`, `gb_safety_ssd`, `avisgebuehr`, `langgutzuschlag` are always
    0.0 because AX aggregates these into Nebengebühr without labelling.
    """
    def _get(key: str) -> float:
        try:
            v = bi_top20_row[key] if hasattr(bi_top20_row, "__getitem__") else getattr(bi_top20_row, key, None)
        except (KeyError, AttributeError):
            return 0.0
        return _safe_float(v)

    return {
        "fracht":                 _get("Erlöse Fracht"),
        "diesel":                 _get("Erlöse Diesel"),
        "maut":                   _get("Erlöse Maut"),
        "transportversicherung":  _get("Erlöse Transportversicherung"),
        "verzollung":             _get("Erlöse EUST Zoll"),
        "lademittel":             _get("Erlöse Lademittel"),
        "gefahrgut":              0.0,
        "gb_safety_ssd":          0.0,
        "avisgebuehr":            0.0,
        "langgutzuschlag":        0.0,
        "sonstige_nebengeb":      _get("Erlöse Nebengebühr") + _get("Erlöse Peak"),
        "GESAMT":                 _get("Erloese"),
    }
