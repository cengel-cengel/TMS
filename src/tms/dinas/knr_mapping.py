"""
ERKA internal customer number → Dinas KNR mapping.

Applied POST-HOC in enrichment steps, not in the parser itself.
Extend this dict as new ERKA customer numbers are identified from
parsed data.

Sources:
  14466 → 511241 (SIKA SUPPLY CENTER AG, confirmed: invoice headers +
                   Abrechnungsstrecken KNR 511241, FIBU-Konto 13890)
  14464 → 511241 (SIKA SUPPLY CENTER AG, older variant — same entity)
  15550 → unknown (seen in correction invoices, Sika Polyurethane Italy)
"""

ERKA_KNR: dict[str, str] = {
    "14466": "511241",   # SIKA SUPPLY CENTER AG
    "14464": "511241",   # SIKA SUPPLY CENTER AG (older)
    # Sika ATM entities — erka_kundennr TBD after full parse run
    # "XXXXX": "413276",  # Sika ATM DE
    # "XXXXX": "493163",  # Sika ATM DE 2nd
    # "XXXXX": "527406",  # Sika ATM CH
}


def enrich_knr(df) -> None:
    """
    Add 'knr' column to df in-place using ERKA_KNR mapping.
    Rows with unknown erka_kundennr get knr=None.
    """
    df["knr"] = df["erka_kundennr"].map(ERKA_KNR)
