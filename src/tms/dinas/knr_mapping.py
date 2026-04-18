"""
ERKA-Kundennummer → Dinas-KNR Mapping mit Entitäts-Kontext.

Methode: Entity-Matching (PDF-Rechnungsempfängername, Versenderort, Routenprofil)
gegen AX Abrechnungsstrecken (Sika.xlsx). Direkter Auftragsnummer-Join nicht möglich
(kein Zeitraum-Overlap zwischen Dinas-PDFs 2024-10 bis 2025-08 und
AX-Abrechnungsstrecken ab 2025-09-29).

Quellen:
  Etappe 6b: PDF-Extraktion → data/parsed/_erka_to_empfaenger_mapping.md
  Etappe 6c: Cross-Check AX-Abrechnungsstrecken (Sika.xlsx)
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

# Stichtag AX-Umstellung (Dinas → AX go-live)
AX_UMSTELLUNG = date(2025, 9, 27)


@dataclass(frozen=True)
class AeraKnrMapping:
    """Ein Dinas-KNR gültig für eine bestimmte Ära."""
    dinas_knr: str
    gueltig_ab: Optional[date] = None   # None = seit Anbeginn
    gueltig_bis: Optional[date] = None  # None = noch aktiv
    note: Optional[str] = None


@dataclass(frozen=True)
class RechnungsempfaengerMapping:
    """Vollständiges Mapping ERKA-Kundennummer → Dinas-KNR mit Entitäts-Kontext."""
    erka_kundennr: str
    fibu_konto: str
    gesellschaft: str                  # Vollständiger Name inkl. Rechtsform (bereinigt)
    gesellschaft_ax: Optional[str]     # Name wie in AX-Abrechnungsstrecken, falls abweichend
    kurzform: str                      # Intern-Label für Reports
    plz: str
    stadt: str
    land: str                          # ISO-2
    ust_id: Optional[str]
    knr_history: list[AeraKnrMapping]  # Meist 1 Eintrag, bei 18894: 2
    konfidenz: float                   # 0.0–1.0 aus Cross-Check
    matching_method: str               # Methode aus Konfidenz-Matrix


ERKA_TO_KNR: dict[str, RechnungsempfaengerMapping] = {

    # ── SIKA SUPPLY CENTER AG (6 erka_knr, alle Fibu-Konto 13890) ─────────
    "14466": RechnungsempfaengerMapping(
        erka_kundennr="14466",
        fibu_konto="13890",
        gesellschaft="Sika Supply Center AG",
        gesellschaft_ax="SIKA SUPPLY CENTER AG",
        kurzform="SSC",
        plz="6060",
        stadt="Sarnen",
        land="CH",
        ust_id=None,
        knr_history=[AeraKnrMapping(dinas_knr="511241")],
        konfidenz=1.00,
        matching_method="Bestätigt (FIBU 13890 + früherer Cross-Check)",
    ),
    "14464": RechnungsempfaengerMapping(
        erka_kundennr="14464",
        fibu_konto="13890",
        gesellschaft="Sika Supply Center AG",
        gesellschaft_ax="SIKA SUPPLY CENTER AG",
        kurzform="SSC (ältere ERKA-Nr)",
        plz="6060",
        stadt="Sarnen",
        land="CH",
        ust_id=None,
        knr_history=[AeraKnrMapping(dinas_knr="511241")],
        konfidenz=1.00,
        matching_method="Bestätigt (FIBU 13890 + früherer Cross-Check)",
    ),
    "14465": RechnungsempfaengerMapping(
        erka_kundennr="14465",
        fibu_konto="13890",
        gesellschaft="Sika Supply Center AG",
        gesellschaft_ax="SIKA SUPPLY CENTER AG",
        kurzform="SSC (Randnummer)",
        plz="6060",
        stadt="Sarnen",
        land="CH",
        ust_id=None,
        knr_history=[AeraKnrMapping(dinas_knr="511241")],
        konfidenz=0.99,
        matching_method="Name + Fibu-Konto",
    ),
    "14468": RechnungsempfaengerMapping(
        erka_kundennr="14468",
        fibu_konto="13890",
        gesellschaft="Sika Supply Center AG",
        gesellschaft_ax="SIKA SUPPLY CENTER AG",
        kurzform="SSC (minor, 3 Records)",
        plz="6060",
        stadt="Sarnen",
        land="CH",
        ust_id=None,
        knr_history=[AeraKnrMapping(dinas_knr="511241")],
        konfidenz=0.99,
        matching_method="Name + Fibu-Konto",
    ),
    "13890": RechnungsempfaengerMapping(
        erka_kundennr="13890",
        fibu_konto="13890",
        gesellschaft="Sika Supply Center AG",
        gesellschaft_ax="SIKA SUPPLY CENTER AG",
        kurzform="SSC (Fibu-Nr als ERKA-Nr)",
        plz="6060",
        stadt="Sarnen",
        land="CH",
        ust_id=None,
        knr_history=[AeraKnrMapping(dinas_knr="511241")],
        konfidenz=0.99,
        matching_method="Name + Fibu-Konto (erka_knr = Fibu-Konto, neuere Rechnungen)",
    ),
    "15550": RechnungsempfaengerMapping(
        erka_kundennr="15550",
        fibu_konto="13890",
        gesellschaft="Sika Supply Center AG",
        gesellschaft_ax="SIKA SUPPLY CENTER AG",
        kurzform="SSC Import (IT/ES→DE Inbound)",
        plz="6060",
        stadt="Sarnen",
        land="CH",
        ust_id=None,
        knr_history=[AeraKnrMapping(dinas_knr="511241")],
        konfidenz=0.99,
        # Physischer Versender: Sika Polyurethane Cerano IT + Sika S.A.U. Alcobendas ES
        # Rechnungsempfänger bleibt SSC. Frühere Annahme "Sika Polyurethane IT" bezog sich
        # auf den Absender, nicht den Rechnungsempfänger.
        matching_method="Inbound-Route IT/ES→DE, SSC als Rechnungsempfänger bestätigt",
    ),

    # ── SIKA DEUTSCHLAND GMBH & CO. KG (Stuttgart) ────────────────────────
    "25607": RechnungsempfaengerMapping(
        erka_kundennr="25607",
        fibu_konto="15607",
        gesellschaft="Sika Deutschland GmbH & Co. KG",
        gesellschaft_ax="Sika Deutschland CH AG & Co KG",  # AX-Schreibweise abweichend
        kurzform="Sika DE Stuttgart",
        plz="70439",
        stadt="Stuttgart",
        land="DE",
        ust_id="DE326812378",
        knr_history=[
            AeraKnrMapping(
                dinas_knr="491063",
                note="Handover hatte fälschlich 493163 — Zahlendreher, korrigiert Etappe 6c",
            ),
        ],
        konfidenz=0.99,
        matching_method="Direkter Namens-Match in AX (Name='Sika Deutschland CH AG & Co KG') + Route Stuttgart→IT/ES/GB/IE/PT",
    ),

    # ── SIKA AUTOMOTIVE AG (Romanshorn CH) ────────────────────────────────
    "18748": RechnungsempfaengerMapping(
        erka_kundennr="18748",
        fibu_konto="18748",
        gesellschaft="Sika Automotive AG",
        gesellschaft_ax="Sika Automotive AG",
        kurzform="Sika ATM CH",
        plz="8590",
        stadt="Romanshorn",
        land="CH",
        ust_id="CHE116323165",
        knr_history=[AeraKnrMapping(dinas_knr="527406")],
        konfidenz=0.99,
        matching_method="Direkter Namens-Match in AX (Name='Sika Automotive AG') + Route Stuttgart→IT/GB/ES/RS/PT",
    ),

    # ── SIKA AUTOMOTIVE DEUTSCHLAND GMBH (Hamburg) — Dual-Ära-Mapping ─────
    "18894": RechnungsempfaengerMapping(
        erka_kundennr="18894",
        fibu_konto="1077344",
        gesellschaft="Sika Automotive Deutschland GmbH",
        gesellschaft_ax="Sika Automotive Deutschland GmbH",
        kurzform="Sika ATM DE Hamburg",
        plz="22525",
        stadt="Hamburg",
        land="DE",
        ust_id="DE812164982",
        knr_history=[
            AeraKnrMapping(
                dinas_knr="413276",
                gueltig_bis=date(2025, 9, 26),
                note="Historischer Dinas-KNR. In AX als Null-Konto geführt (89 Zeilen, Betrag=0).",
            ),
            AeraKnrMapping(
                dinas_knr="ARA1802357",
                gueltig_ab=AX_UMSTELLUNG,
                note="AX-Konstrukt ohne Dinas-Entsprechung. 514 Zeilen, 107.114 EUR Umsatz in AX-Ära.",
            ),
        ],
        konfidenz=0.85,
        matching_method="Namens-Match, Dual-Mapping wegen AX-Kontonummern-Ambiguität (413276=Null-Konto in AX)",
    ),
}


# ── Lookup-Funktionen ─────────────────────────────────────────────────────

def get_mapping(erka_kundennr: str) -> Optional[RechnungsempfaengerMapping]:
    """Gesamtes Mapping für eine ERKA-Kundennummer."""
    return ERKA_TO_KNR.get(str(erka_kundennr))


def get_dinas_knr(
    erka_kundennr: str,
    leistungs_date: Optional[date] = None,
) -> Optional[str]:
    """
    Löst ERKA-Kundennr + Leistungsdatum → Dinas-KNR auf.

    Wenn kein Datum gegeben: gibt den aktuell gültigen KNR zurück
    (kein gueltig_bis gesetzt). Falls kein unbefristeter Eintrag, ersten Eintrag.
    """
    mapping = get_mapping(erka_kundennr)
    if not mapping:
        return None

    if leistungs_date is None:
        for hist in mapping.knr_history:
            if hist.gueltig_bis is None:
                return hist.dinas_knr
        return mapping.knr_history[0].dinas_knr

    for hist in mapping.knr_history:
        ab_ok = hist.gueltig_ab is None or leistungs_date >= hist.gueltig_ab
        bis_ok = hist.gueltig_bis is None or leistungs_date <= hist.gueltig_bis
        if ab_ok and bis_ok:
            return hist.dinas_knr
    return None


def get_all_erka_for_dinas_knr(dinas_knr: str) -> list[str]:
    """Inverse Lookup: alle ERKA-Kundennrn, die auf eine Dinas-KNR zeigen."""
    return [
        erka
        for erka, mapping in ERKA_TO_KNR.items()
        if any(h.dinas_knr == dinas_knr for h in mapping.knr_history)
    ]


def enrich_knr(df, leistungs_date_col: str = "leistung_date") -> None:
    """
    Fügt 'knr'-Spalte zu df in-place hinzu (ära-bewusst).
    Zeilen mit unbekannter erka_kundennr erhalten knr=None.
    """
    import pandas as pd

    def _resolve(row):
        ld = row.get(leistungs_date_col)
        if pd.notna(ld) and hasattr(ld, "date"):
            ld = ld.date()
        elif pd.notna(ld) and isinstance(ld, date):
            pass
        else:
            ld = None
        return get_dinas_knr(str(row["erka_kundennr"]), ld)

    df["knr"] = df.apply(_resolve, axis=1)


# ── Bekannte Nicht-Sika-ERKA (Dokumentation, kein Mapping) ───────────────

NON_SIKA_ERKA: dict[str, str] = {
    "97501": "NOERPEL SE intern (Heidenheim)",
    "97505": "NOERPEL SE intern (Villingen-Schwenningen)",
    "97502": "NOERPEL SE intern (Hilden)",
    "25052": "Fischerwerke GmbH & Co. KG (eigenes Modul)",
    "95322": "Transnatur Norte S.L. (Partner Carrier ES-Nord, nur erka_correction)",
    "95329": "Transnatur S.A. (Partner Carrier ES, Coslada)",
    "95309": "Transnatur S.A. (Partner Carrier ES, ZALII)",
    "95347": "Transnatur S.A. (Partner Carrier ES)",
    "15607": "Sika Deutschland GmbH Chem. Fabrik (ALT, ignoriert — 3 Records, VAT DE813561973)",
}
