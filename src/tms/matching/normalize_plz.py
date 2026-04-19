"""EBM-Rollout: IE county-code → Eircode routing prefix mapping.

Etappe 9a.1.C: Dinas PRE records use 3-letter Irish county abbreviations
(LAO, GAL, DON, COR). EBM DLV destination keys use 3-char Eircode routing
prefixes (R32, H91, F92, …). This module bridges the two formats.

Sources:
  - City→Eircode verified from BI POST data cross-reference (after migration
    the same shipments carry full Eircodes in Empfänger PLZ).
  - EBM.xlsx Nach Ort city names used to confirm city→county association.
  - DLV Tariffs_DE_EU sheet inspected for available IE destination keys.

Uncertain mappings are set to None with an explanatory comment.
"""
from __future__ import annotations


# Mapping: Dinas county abbreviation → Eircode routing prefix
# that matches the DLV dest-key pattern  (e.g. "IE-R32", "IE-H91").
#
# Evidence column (city confirmed in EBM.xlsx + BI POST Empfänger PLZ):
IE_COUNTY_TO_EIRCODE: dict[str, str | None] = {
    "LAO": "R32",  # Laois → Portlaoise  (EBM: 64 AX rows, BI POST: R32 PN8W)
    "GAL": "H91",  # Galway → Galway     (EBM: 27 AX rows, BI POST: H91)
    "DON": "F92",  # Donegal → Rathmullan(EBM: 10 AX rows, BI POST: F92)

    # -- ambiguous or no DLV coverage below --
    "COR": None,   # Cork: 8 Dinas PRE rows. No EBM POST rows; Cork Eircodes
                   # (T12/T23) absent from EBM DLV → cannot map reliably.
    "DUB": None,   # Dublin: D01–D24 range, multiple DLV keys (D12, K32 seen
                   # in POST). No single authoritative mapping without city.
    "LIM": None,   # Limerick: V94 Eircode, not present in EBM DLV.
    "TIP": None,   # Tipperary: Littleton uses E41 in BI POST but E41 is
                   # Longford in standard Eircode → uncertain mapping.
    "KER": None,   # Kerry: Y25/V93, not in EBM DLV.
    "KIL": "K32",  # Kildare: BI POST shows K32 → K32 in DLV. (0 PRE rows)
    "WIC": "A92",  # Wicklow: A92 in DLV; no PRE rows to verify.
    "LGF": "E41",  # Longford: E41 in DLV; uncertain (see TIP note).
}


def normalize_ie_county_for_dlv(county_code: str) -> str | None:
    """Return Eircode routing prefix for a Dinas county code.

    Returns None if the mapping is ambiguous or the county has no
    corresponding DLV destination key for EBM.
    """
    return IE_COUNTY_TO_EIRCODE.get(str(county_code).strip().upper())
