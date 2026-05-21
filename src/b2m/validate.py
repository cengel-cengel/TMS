"""3-Stufen-Validierung für B2M invoice extraction results.

Stufe 1 (Position):  ust ≈ netto × 0.19  (±1 Cent)
Stufe 2 (Rechnung):  Σ positionen.netto = rechnung_netto  (±2 Cent for rounding)
                     rechnung_netto + rechnung_ust = rechnung_brutto  (±2 Cent)
Stufe 3 (Abrechnung): Σ rechnung_brutto = gesamtbetrag  (±5 Cent across pages)
Stufe 4 (Gegenprobe): zusammenstellung.rechnung_* = Σ rechnung pages  (±5 Cent)
"""
from __future__ import annotations
from decimal import Decimal
from dataclasses import dataclass, field
from typing import Optional

from .schema import PageResult, Position, cents

_UST_RATE = Decimal("0.19")
_TOL_POSITION = 1    # ±1 cent
_TOL_RECHNUNG = 2    # ±2 cent
_TOL_GESAMT   = 5    # ±5 cent


@dataclass
class ValidationResult:
    ok: bool
    flags: list[str] = field(default_factory=list)

    def fail(self, msg: str) -> "ValidationResult":
        self.ok = False
        self.flags.append(msg)
        return self


def _near(a: Optional[int], b: Optional[int], tol: int) -> bool:
    if a is None or b is None:
        return True  # can't check — skip rather than flag
    return abs(a - b) <= tol


def validate_position(pos: Position) -> ValidationResult:
    vr = ValidationResult(ok=True)
    if pos.netto is None or pos.ust is None:
        return vr  # missing data — skip
    expected_ust = cents(pos.netto * _UST_RATE)
    actual_ust = cents(pos.ust)
    if not _near(actual_ust, expected_ust, _TOL_POSITION):
        vr.fail(
            f"Stufe1 USt mismatch {pos.kennzeichen}/{pos.artikel}: "
            f"ist={pos.ust} erwartet≈{pos.netto}×0.19={pos.netto * _UST_RATE:.2f} "
            f"(Δ={abs(actual_ust - expected_ust)} Cent)"
        )
    return vr


def validate_rechnung_page(page: PageResult) -> ValidationResult:
    vr = ValidationResult(ok=True)
    if page.seiten_typ != "rechnung":
        return vr

    # Stufe 1: each position
    for pos in page.positionen:
        pv = validate_position(pos)
        if not pv.ok:
            page.flags.extend(pv.flags)
            vr.fail(f"Stufe1 in pg{page.seite}")

    # Stufe 2a: Σ netto
    if page.rechnung_netto is not None and page.positionen:
        sum_netto = cents(sum(p.netto for p in page.positionen if p.netto))
        if not _near(sum_netto, cents(page.rechnung_netto), _TOL_RECHNUNG):
            msg = (
                f"Stufe2a Σnetto mismatch pg{page.seite}: "
                f"Σpos={sum_netto} rn_netto={cents(page.rechnung_netto)} "
                f"(Δ={abs(sum_netto - cents(page.rechnung_netto))} Cent)"
            )
            page.flags.append(msg)
            vr.fail(msg)

    # Stufe 2b: netto + ust = brutto
    if all(x is not None for x in [page.rechnung_netto, page.rechnung_ust, page.rechnung_brutto]):
        expected = cents(page.rechnung_netto) + cents(page.rechnung_ust)
        actual = cents(page.rechnung_brutto)
        if not _near(expected, actual, _TOL_RECHNUNG):
            msg = (
                f"Stufe2b netto+ust≠brutto pg{page.seite}: "
                f"{cents(page.rechnung_netto)}+{cents(page.rechnung_ust)}"
                f"={expected} vs brutto={actual} "
                f"(Δ={abs(expected - actual)} Cent)"
            )
            page.flags.append(msg)
            vr.fail(msg)

    return vr


def validate_abrechnung(pages: list[PageResult]) -> list[str]:
    """Stufe 3 + 4: cross-page totals against Abrechnungsbrief and Zusammenstellung."""
    flags = []

    cover = next((p for p in pages if p.seiten_typ == "abrechnungsbrief"), None)
    summary = next((p for p in pages if p.seiten_typ == "zusammenstellung"), None)
    rechnungen = [p for p in pages if p.seiten_typ == "rechnung"]

    if not rechnungen:
        return flags

    sum_brutto = sum(cents(p.rechnung_brutto) for p in rechnungen if p.rechnung_brutto)
    sum_netto  = sum(cents(p.rechnung_netto)  for p in rechnungen if p.rechnung_netto)
    sum_ust    = sum(cents(p.rechnung_ust)    for p in rechnungen if p.rechnung_ust)

    # Stufe 3: Σ Rechnungen = Abrechnungsbrief Gesamtbetrag
    if cover and cover.gesamtbetrag:
        if not _near(sum_brutto, cents(cover.gesamtbetrag), _TOL_GESAMT):
            flags.append(
                f"Stufe3 Σbrutto≠Gesamtbetrag: "
                f"Σ={sum_brutto/100:.2f} vs {cover.gesamtbetrag} "
                f"(Δ={abs(sum_brutto - cents(cover.gesamtbetrag))} Cent)"
            )

    # Stufe 4: Zusammenstellung GESAMT = Σ Rechnungen
    if summary:
        if summary.rechnung_netto and not _near(sum_netto, cents(summary.rechnung_netto), _TOL_GESAMT):
            flags.append(
                f"Stufe4 Σnetto≠Zusammenstellung: "
                f"Σ={sum_netto/100:.2f} vs {summary.rechnung_netto}"
            )
        if summary.rechnung_brutto and not _near(sum_brutto, cents(summary.rechnung_brutto), _TOL_GESAMT):
            flags.append(
                f"Stufe4 Σbrutto≠Zusammenstellung: "
                f"Σ={sum_brutto/100:.2f} vs {summary.rechnung_brutto}"
            )

    return flags
