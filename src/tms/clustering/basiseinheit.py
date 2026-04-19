"""
Basiseinheit-Dispatcher für Cluster-Matching.

Mappt tarifgruppe → (basiseinheit_name, basiseinheit_wert) so dass
EUR/Einheit-Vergleiche zwischen Dinas (PRE) und AX (POST) normalisiert sind.

Basiseinheiten per Spec:
  Sika DE, SSC, Sika ATM, Fischer, EBM: Stellplätze
  CHT, Bitzer, Groz, GEZE, HELU:        100-kg-Einheit
  HERMA:                                  billing_weight (kg)
  Hornschuch:                             Gewichtsband pro Zone (opaque label)
"""
from __future__ import annotations

from typing import Optional

# Exact or prefix → (basiseinheit_name, aggregat_field_hint)
# aggregat_field_hint is used for documentation; actual extraction in get_basiseinheit_wert()
_EXACT: dict[str, str] = {
    "sika_de_stellplatz":     "stellplaetze",
    "ssc_stellplatz":         "stellplaetze",
    "sika_atm_ch":            "stellplaetze",
    "sika_atm_de":            "stellplaetze",
    "ebm_papst_stellplaetze": "stellplaetze",
    "herma_mit_vl":           "billing_kg",
    "herma_ohne_vl":          "billing_kg",
}

# Prefix matches (checked in order, first wins)
_PREFIX: list[tuple[str, str]] = [
    ("fischerwerke_", "stellplaetze"),
    ("cht_",          "100kg"),
    ("bitzer_",       "100kg"),
    ("groz_beckert_", "100kg"),
    ("geze_",         "100kg"),
    ("helu_",         "100kg"),
    ("hornschuch_",   "gewichtsband"),
]


def get_basiseinheit_name(tarifgruppe: str) -> str:
    """Return basiseinheit name for a tarifgruppe string."""
    if tarifgruppe in _EXACT:
        return _EXACT[tarifgruppe]
    for prefix, name in _PREFIX:
        if tarifgruppe.startswith(prefix):
            return name
    return "unbekannt"


def get_basiseinheit_wert(
    tarifgruppe: str,
    aggregat_gewicht_kg: float | None,
    aggregat_stp: float | None,
    aggregat_ldm: float | None,
) -> Optional[float]:
    """
    Compute the scalar basiseinheit_wert for a cluster.

    Returns None when the required dimension is missing/zero.
    """
    name = get_basiseinheit_name(tarifgruppe)
    if name == "stellplaetze":
        return float(aggregat_stp) if aggregat_stp and aggregat_stp > 0 else None
    if name == "100kg":
        return float(aggregat_gewicht_kg) / 100.0 if aggregat_gewicht_kg and aggregat_gewicht_kg > 0 else None
    if name == "billing_kg":
        return float(aggregat_gewicht_kg) if aggregat_gewicht_kg and aggregat_gewicht_kg > 0 else None
    if name == "gewichtsband":
        # Hornschuch: no meaningful numeric basiseinheit, leave as tonnage/100
        return float(aggregat_gewicht_kg) / 100.0 if aggregat_gewicht_kg and aggregat_gewicht_kg > 0 else None
    return None
