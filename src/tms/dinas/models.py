from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal


@dataclass
class Charge:
    label: str
    amount: Decimal
    currency: str = "EUR"
    detail: str | None = None  # e.g. diesel base price "1038"


@dataclass
class ShipmentRecord:
    # ── Invoice header (repeated for every entry in the invoice) ──────────
    pdf_path: str
    rechnung_nr: str
    erka_kundennr: str | None       # ERKA internal customer ID (e.g. "14466")
    rechnung_date: date | None
    buchungs_date: date | None

    # ── Shipment entry ────────────────────────────────────────────────────
    eintrag_nr: int                 # 1-based position within invoice
    sendungsnummer: str | None      # 8-digit Dinas key, primary join field
    leistung_date: date | None
    frankatur: str | None

    # ── Sender ───────────────────────────────────────────────────────────
    abs_name: str | None
    abs_plz: str | None
    abs_city: str | None
    abs_land: str | None

    # ── Recipient ────────────────────────────────────────────────────────
    empf_name: str | None
    empf_plz: str | None
    empf_city: str | None
    empf_land: str | None

    # ── Cargo ─────────────────────────────────────────────────────────────
    stp: float | None = None
    gewicht_kg: float | None = None
    lm: float | None = None
    bordero_nr: str | None = None
    anz_vp: int | None = None
    inhalt: str | None = None

    # ── Charges ───────────────────────────────────────────────────────────
    fracht: Decimal | None = None
    fracht_currency: str = "EUR"
    maut: Decimal | None = None
    diesel: Decimal | None = None
    sonstige: list[Charge] = field(default_factory=list)
    sendungssumme: Decimal | None = None

    # ── Meta ──────────────────────────────────────────────────────────────
    template: str = "erka_standard"
