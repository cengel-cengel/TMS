"""3-Stufen-Validierung für B2M invoice extraction results.

Stufe 1 (Position):  netto + ust = brutto  (±2 Cent)
                     Note: VAT rate is NOT fixed — B2M uses 0%/7%/19%/20%
Stufe 2 (Rechnung):  Σ positionen.netto = rechnung_netto  (±2 Cent for rounding)
                     rechnung_netto + rechnung_ust = rechnung_brutto  (±2 Cent)
Stufe 3 (Abrechnung): Σ invoice totals = ABRECHNUNGSBRIEF.gesamtbetrag  (±10 Cent)
Stufe 4 (Gegenprobe): Σ positions per invoice block = ZUSAMMENSTELLUNG  (±10 Cent)
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

from .schema import PageResult, Position, cents

_TOL_RECHNUNG = 2    # ±2 cent per page
_TOL_GESAMT   = 10   # ±10 cent for cross-invoice aggregates


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
    """Stufe1: netto + ust = brutto (±2 Cent).

    B2M invoices use multiple VAT rates (0%/7%/19%/20%) — do NOT check rate.
    The additive consistency (netto + ust = brutto) is the invariant.
    """
    vr = ValidationResult(ok=True)
    if pos.netto is None or pos.ust is None or pos.brutto is None:
        return vr  # can't check without all three — skip
    expected_brutto = cents(pos.netto) + cents(pos.ust)
    actual_brutto = cents(pos.brutto)
    if not _near(expected_brutto, actual_brutto, _TOL_RECHNUNG):
        vr.fail(
            f"Stufe1 netto+ust≠brutto {pos.kennzeichen}/{pos.artikel}: "
            f"{pos.netto}+{pos.ust}={expected_brutto/100:.2f} vs brutto={pos.brutto} "
            f"(Δ={abs(expected_brutto - actual_brutto)} Cent)"
        )
    return vr


def validate_rechnung_page(page: PageResult) -> ValidationResult:
    """Clear and re-validate a RECHNUNG page. Always clears flags first."""
    page.flags = []   # reset — always re-validate with current logic
    vr = ValidationResult(ok=True)
    if page.seiten_typ != "rechnung":
        return vr

    # Stufe 1: each position
    for pos in page.positionen:
        pv = validate_position(pos)
        if not pv.ok:
            page.flags.extend(pv.flags)
            vr.ok = False

    # Stufe 2a: Σ netto matches page-level total (only if total is present)
    if page.rechnung_netto is not None and page.positionen:
        sum_netto = cents(sum(p.netto for p in page.positionen if p.netto))
        if not _near(sum_netto, cents(page.rechnung_netto), _TOL_RECHNUNG):
            msg = (
                f"Stufe2a Σnetto mismatch pg{page.seite}: "
                f"Σpos={sum_netto} rn_netto={cents(page.rechnung_netto)} "
                f"(Δ={abs(sum_netto - cents(page.rechnung_netto))} Cent)"
            )
            page.flags.append(msg)
            vr.ok = False

    # Stufe 2b: netto + ust = brutto at page level
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
            vr.ok = False

    return vr


def deduplicate_split_blocks(pages: list[PageResult]) -> int:
    """Remove intermediate-subtotal false extras from split-block Karte entries.

    When a Karte block spans two pages, Vision sometimes reads the
    "Summe Kraftstoffe" sub-total row on the first page as the Karte total.
    The true SUMME KARTE/KFZ is on the next page, producing a duplicate entry
    for the same Kennzeichen on consecutive pages (different, smaller value on
    the first page).

    Rule: if Kennzeichen X appears on page N with value V1 AND on page N+1
    with value V2, and V1 < V2 (the classic subtotal-vs-total pattern), then
    null out the page-N entry. Identical values (possible genuine twin billing)
    are left untouched.

    Returns: number of positions nulled out.
    """
    from .schema import cents as _cents
    # Group by (rechnungsnummer, kennzeichen): [(seite, position_obj)]
    from collections import defaultdict
    groups: dict[tuple, list] = defaultdict(list)
    for page in pages:
        if page.seiten_typ != "rechnung":
            continue
        for pos in page.positionen:
            key = (page.rechnungsnummer or "", pos.kennzeichen or "")
            groups[key].append((page.seite, pos))

    n_nulled = 0
    for (rn, kz), entries in groups.items():
        if len(entries) < 2:
            continue
        entries_sorted = sorted(entries, key=lambda x: x[0])
        # Check consecutive-page duplicates
        for i in range(len(entries_sorted) - 1):
            s1, pos1 = entries_sorted[i]
            s2, pos2 = entries_sorted[i + 1]
            if s2 != s1 + 1:
                continue  # not consecutive — skip
            if pos1.netto is None or pos2.netto is None:
                continue
            if pos1.netto < pos2.netto:
                # pos1 is the false intermediate subtotal — null it out
                pos1.netto = None
                pos1.ust = None
                pos1.brutto = None
                n_nulled += 1
    return n_nulled


def validate_abrechnung(pages: list[PageResult]) -> list[str]:
    """Stufe 3+4: cross-invoice validation using ZUSAMMENSTELLUNG pages.

    B2M PDFs contain multiple invoice blocks. Each ZUSAMMENSTELLUNG page
    covers the invoice block that precedes it (identified by shared RN).
    Stufe 3: Σ ZUSAMMENSTELLUNG bruttos = ABRECHNUNGSBRIEF.gesamtbetrag.
    Stufe 4: Σ positions in a block = that block's ZUSAMMENSTELLUNG total.
    """
    flags = []

    cover = next((p for p in pages if p.seiten_typ == "abrechnungsbrief"), None)
    summaries = [p for p in pages if p.seiten_typ == "zusammenstellung"]
    rechnungen = [p for p in pages if p.seiten_typ == "rechnung"]

    if not rechnungen:
        return flags

    # Stufe 3: last ZUSAMMENSTELLUNG.brutto = Gesamtbetrag
    # Use ONLY the last ZUSAMMENSTELLUNG — it covers all blocks (grand total).
    # Summing multiple ZUSAMMENSTELLUNG pages would double-count earlier blocks.
    if cover and cover.gesamtbetrag and summaries:
        last_summary = summaries[-1]
        if last_summary.rechnung_brutto and not _near(
            cents(last_summary.rechnung_brutto), cents(cover.gesamtbetrag), _TOL_GESAMT
        ):
            flags.append(
                f"Stufe3 letzte-Zusammenstellung≠Gesamtbetrag: "
                f"{last_summary.rechnung_brutto} vs {cover.gesamtbetrag} "
                f"(Δ={abs(cents(last_summary.rechnung_brutto) - cents(cover.gesamtbetrag))} Cent)"
            )

    # Stufe 4: for each ZUSAMMENSTELLUNG, find preceding RECHNUNG pages (same RN)
    #          and compare Σ positions against the ZUSAMMENSTELLUNG total
    for summary in summaries:
        rn = summary.rechnungsnummer
        if not rn:
            continue
        block_pages = [p for p in rechnungen if p.rechnungsnummer == rn]
        if not block_pages:
            continue
        sum_pos_netto = sum(
            cents(pos.netto)
            for p in block_pages
            for pos in p.positionen
            if pos.netto
        )
        if summary.rechnung_netto and not _near(
            sum_pos_netto, cents(summary.rechnung_netto), _TOL_GESAMT
        ):
            flags.append(
                f"Stufe4 rn={rn} Σpos.netto≠Zusammenstellung: "
                f"Σ={sum_pos_netto/100:.2f} vs {summary.rechnung_netto} "
                f"(Δ={abs(sum_pos_netto - cents(summary.rechnung_netto))} Cent)"
            )

    return flags
