"""Data classes and decimal parsing for B2M invoice extraction."""
from __future__ import annotations
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Optional


def parse_de(val) -> Optional[Decimal]:
    """Parse German or dot-decimal string to Decimal (cent-precise). Never floats."""
    if val is None:
        return None
    s = str(val).strip()
    if s in ("", "null", "None", "-"):
        return None
    # Vision may return either "1.234,56" (DE) or "1234.56" (already converted)
    # Strategy: if comma present, treat as DE format; else treat as dot-decimal
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def cents(d: Optional[Decimal]) -> Optional[int]:
    """Convert Decimal to integer cents for sum checks."""
    if d is None:
        return None
    return int(round(d * 100))


@dataclass
class Position:
    kennzeichen: str
    artikel: str
    netto: Optional[Decimal]
    ust: Optional[Decimal]
    brutto: Optional[Decimal]

    @staticmethod
    def from_dict(d: dict) -> "Position":
        return Position(
            kennzeichen=str(d.get("kennzeichen") or "").strip(),
            artikel=str(d.get("artikel") or "").strip(),
            netto=parse_de(d.get("netto")),
            ust=parse_de(d.get("ust")),
            brutto=parse_de(d.get("brutto")),
        )


@dataclass
class PageResult:
    pdf_name: str
    seite: int
    seiten_typ: str          # 'abrechnungsbrief' | 'rechnung' | 'zusammenstellung'
    rechnungsnummer: Optional[str]
    positionen: list[Position]
    rechnung_netto: Optional[Decimal]
    rechnung_ust: Optional[Decimal]
    rechnung_brutto: Optional[Decimal]
    gesamtbetrag: Optional[Decimal]
    raw: dict = field(default_factory=dict)
    flags: list[str] = field(default_factory=list)

    @staticmethod
    def from_dict(pdf_name: str, seite: int, d: dict) -> "PageResult":
        positionen = [Position.from_dict(p) for p in (d.get("positionen") or [])]
        return PageResult(
            pdf_name=pdf_name,
            seite=seite,
            seiten_typ=str(d.get("seiten_typ") or "unbekannt").lower().strip(),
            rechnungsnummer=str(d.get("rechnungsnummer") or "").strip() or None,
            positionen=positionen,
            rechnung_netto=parse_de(d.get("rechnung_netto")),
            rechnung_ust=parse_de(d.get("rechnung_ust")),
            rechnung_brutto=parse_de(d.get("rechnung_brutto")),
            gesamtbetrag=parse_de(d.get("gesamtbetrag")),
            raw=d,
        )
