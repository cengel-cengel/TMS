"""Validierung für B2M invoice extraction results.

Stufe 0 (Manifest):    extracted RN count == manifest RN count
Stufe 1 (Position):    netto + ust = brutto  (±2 Cent)
                       Note: VAT rate is NOT fixed — B2M uses 0%/7%/19%/20%/21%/22%
Stufe 2 (Rechnung):    Σ positionen.netto = rechnung_netto  (±2 Cent for rounding)
                       rechnung_netto + rechnung_ust = rechnung_brutto  (±2 Cent)
Stufe 3 (Abrechnung):  Σ invoice brutto = manifest.betrag_eur per RN  (±10 Cent)
                       Fallback: Σ ZUSAMMENSTELLUNG bruttos = ABRECHNUNGSBRIEF.gesamtbetrag
Stufe 4 (Gegenprobe):  Σ positions per invoice block = ZUSAMMENSTELLUNG  (±10 Cent)
Kontrolle 1 (KZ):      Σ pos.netto per KZ == kz_summen[kz].netto  (de-aral, ±2 Cent)
                       Flags recovery errors and Gebühren blind-spots per KZ.
Kontrolle 2 (RN):      Σ kz_summen[kz].netto per RN == ZUSAMMENSTELLUNG.netto (±10 Cent)
                       Cross-check: kz_summen totals must equal invoice-level total.
"""
from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from .schema import PageResult, Position, ManifestEntry, KzSumme, cents

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
        return True
    return abs(a - b) <= tol


def validate_position(pos: Position) -> ValidationResult:
    """Stufe1: netto + ust = brutto (±2 Cent).

    Multiple VAT rates used (0%/7%/19%/20%/21%/22%) — do NOT check rate.
    Negative netto (Nachlass/discount) is valid.
    """
    vr = ValidationResult(ok=True)
    if pos.netto is None or pos.ust is None or pos.brutto is None:
        return vr
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
    page.flags = []
    vr = ValidationResult(ok=True)
    if page.seiten_typ != "rechnung":
        return vr

    # Stufe 1: each position
    for pos in page.positionen:
        pv = validate_position(pos)
        if not pv.ok:
            page.flags.extend(pv.flags)
            vr.ok = False

    # Stufe 2a: Σ netto matches page-level total
    if page.rechnung_netto is not None and page.positionen:
        sum_netto = cents(sum(p.netto for p in page.positionen if p.netto is not None))
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

    Rule 1 (same-page): if Kennzeichen X appears on page N with BOTH a null entry
    AND a non-null entry, and a later page N' > N also has a non-null entry, the
    non-null on page N is a sub-total within the split block — null it out.
    (Example: de-aral card with Diesel sub-total + E-charge split on same page.)

    Rule 2 (consecutive-page, kontrollgestützt):
      If Kennzeichen X appears on page N with V1 and page N+1 with V2:
      - V1 < V2: V1 is a subtotal → null V1 (original logic).
      - V1 == V2: SUMME KARTE/KFZ printed on both pages of a split block.
          Use kz_summen as control:
          · if kz_summen[X].netto == V2 → V1 is duplicate → null V1
          · if kz_summen[X].netto == V1+V2 → both needed (twin billing) → keep
          · no kz_summen available → conservative, keep both (flagged by Kontrolle 1)
    """
    # Build kz_summen index: (rn, kz) -> KzSumme from any page where visible
    kz_summen_idx: dict[tuple, KzSumme] = {}
    for page in pages:
        if page.seiten_typ != "rechnung":
            continue
        rn = page.rechnungsnummer or ""
        for kz, ks in page.kz_summen.items():
            key = (rn, kz.strip())
            if key not in kz_summen_idx and ks.netto is not None:
                kz_summen_idx[key] = ks

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

        # Rule 1: same-page null + non-null with a later non-null entry
        page_map: dict[int, list] = defaultdict(list)
        for seite, pos in entries_sorted:
            page_map[seite].append((seite, pos))
        for seite, plist in sorted(page_map.items()):
            has_null = any(pos.netto is None for _, pos in plist)
            nonnulls = [pos for _, pos in plist if pos.netto is not None]
            if has_null and nonnulls:
                later_has_value = any(
                    pos.netto is not None
                    for s, pos in entries_sorted
                    if s > seite
                )
                if later_has_value:
                    for pos in nonnulls:
                        pos.netto = None
                        pos.ust = None
                        pos.brutto = None
                        n_nulled += 1

        # Rule 2: consecutive pages (re-sort after Rule 1 may have nulled values)
        entries_sorted = sorted(entries, key=lambda x: x[0])
        ks = kz_summen_idx.get((rn, kz.strip()))
        for i in range(len(entries_sorted) - 1):
            s1, pos1 = entries_sorted[i]
            s2, pos2 = entries_sorted[i + 1]
            if s2 != s1 + 1:
                continue
            if pos1.netto is None or pos2.netto is None:
                continue
            if pos1.netto < pos2.netto:
                pos1.netto = None
                pos1.ust = None
                pos1.brutto = None
                n_nulled += 1
            elif pos1.netto == pos2.netto and ks is not None and ks.netto is not None:
                # Equal-value: use SUMME KARTE/KFZ as arbiter
                summe = cents(ks.netto)
                if summe == cents(pos2.netto):
                    # SUMME == one entry → pg N value is duplicate → null earlier
                    pos1.netto = None
                    pos1.ust = None
                    pos1.brutto = None
                    n_nulled += 1
                # elif summe == cents(pos1.netto) + cents(pos2.netto): twin billing → keep both
    return n_nulled


def validate_abrechnung(
    pages: list[PageResult],
    manifest: list[ManifestEntry] | None = None,
) -> list[str]:
    """Stufe 3+4: cross-invoice validation.

    Stufe 3a (manifest): if manifest present, compare each RN's Σbrutto against
                         manifest.betrag_eur (the ground truth from cover page).
    Stufe 3b (fallback): last ZUSAMMENSTELLUNG.brutto == ABRECHNUNGSBRIEF.gesamtbetrag.
    Stufe 4: Σ positions per RN block == that block's ZUSAMMENSTELLUNG netto.
    """
    flags = []

    cover = next((p for p in pages if p.seiten_typ == "abrechnungsbrief"), None)
    summaries = [p for p in pages if p.seiten_typ == "zusammenstellung"]
    rechnungen = [p for p in pages if p.seiten_typ == "rechnung"]

    if not rechnungen:
        return flags

    # ── Stufe 3a: per-RN manifest check ──────────────────────────────────
    if manifest:
        # Group RECHNUNG pages by RN
        from collections import defaultdict
        by_rn: dict[str, list[PageResult]] = defaultdict(list)
        for p in rechnungen:
            if p.rechnungsnummer:
                by_rn[p.rechnungsnummer].append(p)

        # Stufe 0: manifest RN count vs extracted RN count
        manifest_rns = {m.rechnungsnummer for m in manifest}
        extracted_rns = set(by_rn.keys())
        missing_rns = manifest_rns - extracted_rns
        extra_rns   = extracted_rns - manifest_rns
        if missing_rns:
            flags.append(f"Stufe0 RN im Manifest nicht extrahiert: {sorted(missing_rns)}")
        if extra_rns:
            flags.append(f"Stufe0 RN extrahiert aber nicht im Manifest: {sorted(extra_rns)}")

        # Stufe 3a: per-RN brutto sum vs manifest
        # For non-EUR invoices (CH=CHF): extracted amounts are in local currency,
        # so compare against betrag_lw; use betrag_eur for EUR-denominated invoices.
        for entry in manifest:
            rn = entry.rechnungsnummer
            block = by_rn.get(rn, [])
            if not block:
                continue
            sum_brutto = sum(
                cents(pos.brutto)
                for p in block for pos in p.positionen
                if pos.brutto is not None
            )
            if entry.waehrung != "EUR" and entry.betrag_lw is not None:
                target = cents(entry.betrag_lw)
                currency_label = entry.waehrung
            else:
                target = cents(entry.betrag_eur)
                currency_label = "EUR"
            if not _near(sum_brutto, target, _TOL_GESAMT):
                flags.append(
                    f"Stufe3 {entry.land} rn={rn} Σbrutto≠Manifest: "
                    f"Σ={sum_brutto/100:.2f} vs {target/100:.2f} {currency_label} "
                    f"(Δ={abs(sum_brutto - target)} Cent)"
                )

    # ── Stufe 3b: last ZUSAMMENSTELLUNG == gesamtbetrag (fallback) ───────
    if cover and cover.gesamtbetrag and summaries:
        last_summary = summaries[-1]
        if last_summary.rechnung_brutto and not _near(
            cents(last_summary.rechnung_brutto), cents(cover.gesamtbetrag), _TOL_GESAMT
        ):
            flags.append(
                f"Stufe3b letzte-Zusammenstellung≠Gesamtbetrag: "
                f"{last_summary.rechnung_brutto} vs {cover.gesamtbetrag} "
                f"(Δ={abs(cents(last_summary.rechnung_brutto) - cents(cover.gesamtbetrag))} Cent)"
            )

    # ── Stufe 4: Σ positions per RN == ZUSAMMENSTELLUNG netto ────────────
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
            if pos.netto is not None
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


def validate_kontrolle1(pages: list[PageResult]) -> list[str]:
    """Kontrolle 1: Σ pos.netto per (RN, KZ) == kz_summen[kz].netto (de-aral only, ±2 Cent).

    Catches recovery over/under-counts and Gebühren blind-spots per KZ.
    Only runs when kz_summen is populated (requires re-run with updated prompt).
    """
    flags: list[str] = []
    rechnungen = [p for p in pages if p.seiten_typ == "rechnung" and p.format == "de-aral"]
    if not rechnungen:
        return flags

    # Build: (rn, kz) -> kz_summen (first non-null across all pages)
    kz_summen_idx: dict[tuple, KzSumme] = {}
    for page in rechnungen:
        rn = page.rechnungsnummer or ""
        for kz, ks in page.kz_summen.items():
            key = (rn, kz.strip())
            if key not in kz_summen_idx and ks.netto is not None:
                kz_summen_idx[key] = ks

    if not kz_summen_idx:
        return flags  # kz_summen not yet populated (old JSONL, pre-re-run)

    # Build: (rn, kz) -> Σ pos.netto
    pos_sums: dict[tuple, int] = defaultdict(int)
    for page in rechnungen:
        rn = page.rechnungsnummer or ""
        for pos in page.positionen:
            if pos.netto is None:
                continue
            key = (rn, (pos.kennzeichen or "").strip())
            pos_sums[key] += cents(pos.netto)

    for key, ks in kz_summen_idx.items():
        rn, kz = key
        sigma = pos_sums.get(key, 0)
        expected = cents(ks.netto)
        if not _near(sigma, expected, _TOL_RECHNUNG):
            flags.append(
                f"Kontrolle1 rn={rn} kz={kz}: "
                f"Σpos={sigma/100:.2f} vs SUMME={expected/100:.2f} "
                f"(Δ={sigma - expected:+d} Cent)"
            )
    return flags


def validate_kontrolle2(pages: list[PageResult]) -> list[str]:
    """Kontrolle 2: Σ kz_summen[kz].netto per RN == ZUSAMMENSTELLUNG.netto (±10 Cent).

    Cross-checks that the sum of all SUMME KARTE/KFZ values matches the invoice total.
    Only runs when kz_summen is populated (de-aral, requires updated Vision prompt).
    """
    flags: list[str] = []
    rechnungen = [p for p in pages if p.seiten_typ == "rechnung" and p.format == "de-aral"]
    summaries  = [p for p in pages if p.seiten_typ == "zusammenstellung"]
    if not rechnungen or not summaries:
        return flags

    # Σ kz_summen per RN (deduplicated: only first occurrence per (rn, kz))
    seen: set[tuple] = set()
    rn_kzsum: dict[str, int] = defaultdict(int)
    for page in rechnungen:
        rn = page.rechnungsnummer or ""
        for kz, ks in page.kz_summen.items():
            key = (rn, kz.strip())
            if key in seen or ks.netto is None:
                continue
            seen.add(key)
            rn_kzsum[rn] += cents(ks.netto)

    if not rn_kzsum:
        return flags  # kz_summen not yet populated

    for summary in summaries:
        rn = summary.rechnungsnummer
        if not rn or rn not in rn_kzsum:
            continue
        if summary.rechnung_netto is None:
            continue
        sigma = rn_kzsum[rn]
        expected = cents(summary.rechnung_netto)
        if not _near(sigma, expected, _TOL_GESAMT):
            flags.append(
                f"Kontrolle2 rn={rn}: "
                f"Σkz_summen={sigma/100:.2f} vs Zusammenstellung={summary.rechnung_netto} "
                f"(Δ={sigma - expected:+d} Cent)"
            )
    return flags
