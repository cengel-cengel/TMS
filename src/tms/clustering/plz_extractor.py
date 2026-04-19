"""PLZ normalization and extraction for AX cluster building.

Etappe 8h: Fixes PLZ-code mismatches between Tagesbericht (TB) and Dinas
for Irish, Spanish, British, and Luxembourgish destinations.

Root causes addressed:
  1. Irish Eircodes in TB ("D11", "D24") yield 2-char prefix "D1"/"D2" but
     Dinas records Dublin as "DUB" → "DU".  Normalize Dublin codes → "DU".
  2. (Fallback) Sika.xlsx Nach Ort field sometimes contains city+PLZ text
     (e.g. "Dublin 17", "LU-1471 Luxembourg") when no explicit PLZ field
     is populated.  extract_plz_from_nach_ort() parses these patterns.
"""
from __future__ import annotations

import re
from typing import Optional


# ---------------------------------------------------------------------------
# IE: Eircode → 2-char matching code
# ---------------------------------------------------------------------------
# Dinas recorded all Dublin routes as "DUB" → plz2 = "DU".
# TB records Eircodes like "D11", "D12", "D22", "D24" (Dublin city),
# "DUB" (legacy), "COR" (Cork), "LIM" (Limerick), "GAL" (Galway), etc.

_IE_PLZ2: dict[str, str] = {
    # Dublin city/county — all map to "DU" to match Dinas convention
    "DUB": "DU",
    "D1":  "DU",  # D1x Eircodes
    "D2":  "DU",  # D2x Eircodes
    "D3":  "DU",
    "D4":  "DU",
    "D5":  "DU",
    "D6":  "DU",
    "D7":  "DU",
    "D8":  "DU",
    "D9":  "DU",
    # Cork
    "COR": "CO",
    "CO":  "CO",
    # Limerick
    "LIM": "LI",
    "LI":  "LI",
    # Galway
    "GAL": "GA",
    "GA":  "GA",
    # Waterford
    "WAT": "WA",
    # Tipperary
    "TIP": "TI",
    # Kerry
    "KER": "KE",
    # Kilkenny
    "KID": "KI",
    # Wexford
    "WEM": "WE",
    # Donegal
    "DON": "DO",
    # Offaly
    "OFF": "OF",
    # Laois
    "LAO": "LA",
}


def _normalize_ie_plz(plz: str) -> str:
    """Map an Irish PLZ/Eircode to its 2-char matching code.

    Dublin Eircodes (D11, D12, DUB, …) all map to "DU" to match the Dinas
    convention where every Dublin shipment was stored as "DUB".
    """
    s = str(plz).strip().upper()
    if not s or s in ("NAN", "NONE", ""):
        return ""

    # Direct lookup for known codes
    if s in _IE_PLZ2:
        return _IE_PLZ2[s]

    # "D" + digit(s): Dublin Eircode (D11, D22, D24…)
    if s.startswith("D") and len(s) > 1 and s[1].isdigit():
        return "DU"

    # Full Eircode format: "A65 B2CD" — use routing key (first 3 chars, then first 2)
    if len(s) >= 3 and s[2] in "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        return s[:2]

    return s[:2]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def normalize_empf_plz(plz: str, land: str) -> str:
    """Return the canonical 2-char PLZ prefix for family-key matching.

    For most countries: first 2 chars of the PLZ string.
    For IE: normalise via _normalize_ie_plz so Dublin variants all produce
            "DU", matching the Dinas convention.
    """
    plz_s = str(plz).strip()
    if not plz_s or plz_s.lower() in ("nan", "none"):
        return ""

    land_upper = str(land).strip().upper()
    if land_upper == "IE":
        return _normalize_ie_plz(plz_s)

    return plz_s[:2]


# ---------------------------------------------------------------------------
# Fallback: parse PLZ from Sika.xlsx "Nach Ort" text field
# ---------------------------------------------------------------------------
# Some AX rows lack a dedicated PLZ column; the destination city string
# contains embedded PLZ information:
#   IE: "Dublin 17" → "17", "Dublin IP"→ "IP"
#   ES: "Barcelona 08021" → "08"
#   LU: "LU-1471 Luxembourg" → "14"
#   AT: "Wien 1010" → "10"
#   GB: "London EC1A 1BB" → "EC"

_RE_ES_PLZ  = re.compile(r"\b(\d{5})\b")          # 5-digit Spanish PLZ
_RE_AT_PLZ  = re.compile(r"\b(\d{4})\b")           # 4-digit Austrian PLZ
_RE_LU_PLZ  = re.compile(r"\b[Ll][Uu][- ]?(\d{4})\b")  # LU-1471
_RE_GB_PLZ  = re.compile(r"\b([A-Z]{1,2}\d[A-Z\d]?)\b")  # EC1A, LS1, SW1A
_RE_IE_TEXT = re.compile(r"\bDublin\s+(\d+|[A-Z]{2,3})\b", re.IGNORECASE)


def extract_plz_from_nach_ort(nach_ort: str, land: str) -> Optional[str]:
    """Extract a 2-char PLZ prefix from a Sika.xlsx "Nach Ort" city string.

    Returns None if no PLZ pattern is recognised (caller should fall back
    to the TB Empfänger-PLZ field).

    Examples:
        extract_plz_from_nach_ort("Dublin 17", "IE")   → "17"
        extract_plz_from_nach_ort("Dublin IP", "IE")   → "IP"
        extract_plz_from_nach_ort("Barcelona 08021", "ES") → "08"
        extract_plz_from_nach_ort("LU-1471 Luxembourg", "LU") → "14"
        extract_plz_from_nach_ort("Wien 1010", "AT")   → "10"
        extract_plz_from_nach_ort("London EC1A", "GB") → "EC"
    """
    if not nach_ort:
        return None
    s = str(nach_ort).strip()
    land_upper = str(land).strip().upper()

    if land_upper == "IE":
        m = _RE_IE_TEXT.search(s)
        if m:
            code = m.group(1).upper()
            # Single/double digit → numeric Dublin district
            if code.isdigit() or (len(code) == 2 and code.isdigit()):
                return code.zfill(2) if len(code) == 1 else code
            # Alpha postcode area code (IP, LS, AL, DU …)
            return code[:2]
        return None

    if land_upper == "ES":
        m = _RE_ES_PLZ.search(s)
        return m.group(1)[:2] if m else None

    if land_upper == "LU":
        m = _RE_LU_PLZ.search(s)
        return m.group(1)[:2] if m else None

    if land_upper == "AT":
        m = _RE_AT_PLZ.search(s)
        return m.group(1)[:2] if m else None

    if land_upper == "GB":
        m = _RE_GB_PLZ.search(s)
        return m.group(1)[:2].upper() if m else None

    return None
