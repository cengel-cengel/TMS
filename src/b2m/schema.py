"""Data classes and decimal parsing for B2M invoice extraction."""
from __future__ import annotations
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Optional


def parse_de(val) -> Optional[Decimal]:
    """Parse German or dot-decimal string to Decimal (cent-precise). Never floats.

    Handles trailing minus: "2,82-" → Decimal("-2.82") (B2M Nachlass/discount rows).
    """
    if val is None:
        return None
    s = str(val).strip()
    if s in ("", "null", "None"):
        return None
    if s == "-":
        return None
    # Trailing minus: "2,82-" → -2.82
    negative = s.endswith("-")
    if negative:
        s = s[:-1].strip()
    if not s:
        return None
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        d = Decimal(s)
        return -d if negative else d
    except InvalidOperation:
        return None


def cents(d: Optional[Decimal]) -> Optional[int]:
    """Convert Decimal to integer cents for sum checks."""
    if d is None:
        return None
    return int(round(d * 100))


@dataclass
class Position:
    kennzeichen: str             # license plate / cardholder / Lenker name
    artikel: str                 # dominant article type
    netto: Optional[Decimal]
    ust: Optional[Decimal]
    brutto: Optional[Decimal]
    kartennummer: str = ""       # card number from "Karte:" / "CARD:" line
    warengruppe: Optional[str] = None   # product group; null for fees/Nachlass

    @staticmethod
    def from_dict(d: dict) -> "Position":
        wg = d.get("warengruppe")
        return Position(
            kennzeichen=str(d.get("kennzeichen") or "").strip(),
            artikel=str(d.get("artikel") or "").strip(),
            netto=parse_de(d.get("netto")),
            ust=parse_de(d.get("ust")),
            brutto=parse_de(d.get("brutto")),
            kartennummer=str(d.get("kartennummer") or "").strip(),
            warengruppe=str(wg).strip() if wg else None,
        )


@dataclass
class KzSumme:
    """SUMME KARTE/KFZ per Kennzeichen — explicit control value (de-aral only).

    Extracted from the 'SUMME KARTE/KFZ' row visible on the page.
    Absent when the card block continues to the next page (split block).
    Used for Kontrolle 1: Σ pos.netto per KZ == kz_summen[kz].netto
    and for kontrollgestützter Rule-2 dedup of equal-value entries.
    """
    netto: Optional[Decimal]
    ust: Optional[Decimal]
    brutto: Optional[Decimal]

    @staticmethod
    def from_dict(d: dict) -> "KzSumme":
        return KzSumme(
            netto=parse_de(d.get("netto")),
            ust=parse_de(d.get("ust")),
            brutto=parse_de(d.get("brutto")),
        )


@dataclass
class ManifestEntry:
    """One invoice line from the ABRECHNUNGSBRIEF cover-page table."""
    land: str                     # country code: DE / AT / CH / IT / BE
    rechnungsnummer: str
    datum: str
    waehrung: str                 # EUR or CHF
    betrag_lw: Optional[Decimal]  # amount in local currency (null if == EUR)
    betrag_eur: Decimal           # amount billed in EUR

    @staticmethod
    def from_dict(d: dict) -> "ManifestEntry":
        return ManifestEntry(
            land=str(d.get("land") or "").strip().upper(),
            rechnungsnummer=str(d.get("rechnungsnummer") or "").strip(),
            datum=str(d.get("datum") or "").strip(),
            waehrung=str(d.get("waehrung") or "EUR").strip().upper(),
            betrag_lw=parse_de(d.get("betrag_lw")),
            betrag_eur=parse_de(d.get("betrag_eur")) or Decimal("0"),
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
    format: str = "de-aral"             # detected invoice format
    manifest: Optional[list[ManifestEntry]] = None  # populated for abrechnungsbrief
    kz_summen: dict[str, KzSumme] = field(default_factory=dict)  # de-aral only

    @staticmethod
    def from_dict(pdf_name: str, seite: int, d: dict) -> "PageResult":
        positionen = [Position.from_dict(p) for p in (d.get("positionen") or [])]
        manifest = None
        raw_manifest = d.get("manifest")
        if raw_manifest and isinstance(raw_manifest, list):
            manifest = [ManifestEntry.from_dict(m) for m in raw_manifest]
        kz_summen: dict[str, KzSumme] = {}
        raw_kzs = d.get("kz_summen")
        if raw_kzs and isinstance(raw_kzs, dict):
            for kz, ks in raw_kzs.items():
                if isinstance(ks, dict):
                    kz_summen[kz.strip()] = KzSumme.from_dict(ks)
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
            format=str(d.get("format") or "de-aral").strip(),
            manifest=manifest,
            kz_summen=kz_summen,
        )

    def to_dict(self) -> dict:
        """Serialize current Python object state (not raw Vision dict).

        Used for JSONL persistence so dedup nulls and 3rd-pass recoveries
        are correctly reflected — p.raw stays as the original Vision output.
        """
        def _dec(d):
            return str(d) if d is not None else None

        pos_list = [
            {
                "kartennummer": pos.kartennummer,
                "kennzeichen":  pos.kennzeichen,
                "warengruppe":  pos.warengruppe,
                "artikel":      pos.artikel,
                "netto":        _dec(pos.netto),
                "ust":          _dec(pos.ust),
                "brutto":       _dec(pos.brutto),
            }
            for pos in self.positionen
        ]
        manifest_list = None
        if self.manifest is not None:
            manifest_list = [
                {
                    "land":              m.land,
                    "rechnungsnummer":   m.rechnungsnummer,
                    "datum":             m.datum,
                    "waehrung":          m.waehrung,
                    "betrag_lw":         _dec(m.betrag_lw),
                    "betrag_eur":        _dec(m.betrag_eur),
                }
                for m in self.manifest
            ]
        kz_summen_dict = {
            kz: {"netto": _dec(ks.netto), "ust": _dec(ks.ust), "brutto": _dec(ks.brutto)}
            for kz, ks in self.kz_summen.items()
        }
        return {
            "seiten_typ":      self.seiten_typ,
            "format":          self.format,
            "rechnungsnummer": self.rechnungsnummer,
            "positionen":      pos_list,
            "kz_summen":       kz_summen_dict,
            "rechnung_netto":  _dec(self.rechnung_netto),
            "rechnung_ust":    _dec(self.rechnung_ust),
            "rechnung_brutto": _dec(self.rechnung_brutto),
            "gesamtbetrag":    _dec(self.gesamtbetrag),
            "manifest":        manifest_list,
        }
