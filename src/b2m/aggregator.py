"""B2M Aggregation: (RN, KZ, WG) rows + Kontrolle 1+2.

Produces structured rows for Excel output. Works with or without
kz_summen (K1 = '?' before re-run, '✓'/'✗' after).
"""
from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from .schema import PageResult, ManifestEntry, KzSumme, cents

_TWO = Decimal("0.01")


def _d2(d: Optional[Decimal]) -> Optional[Decimal]:
    if d is None:
        return None
    return d.quantize(_TWO, rounding=ROUND_HALF_UP)


@dataclass
class AggRow:
    rn: str
    land: str
    waehrung: str
    kz: str
    wg: str                           # warengruppe or artikel-label
    artikel: str                       # dominant artikel text
    sum_netto: Decimal
    sum_ust: Decimal
    sum_brutto: Decimal
    ust_pct: Optional[Decimal]
    n: int
    kz_gesamt_netto: Optional[Decimal]   # from kz_summen (None pre-re-run)
    kz_gesamt_brutto: Optional[Decimal]
    k1: Optional[bool]                    # True=✓ False=✗ None=?


@dataclass
class KontrolleRow:
    rn: str
    land: str
    waehrung: str
    sigma_kz_netto: Optional[Decimal]   # Σ kz_summen per RN
    sigma_kz_brutto: Optional[Decimal]
    zusammenstellung_netto: Optional[Decimal]
    zusammenstellung_brutto: Optional[Decimal]
    k2: Optional[bool]                  # Kontrolle 2
    manifest_brutto: Optional[Decimal]
    delta_cent: Optional[int]           # Ist - Soll


def _wg_key(warengruppe: Optional[str], artikel: str) -> str:
    """Aggregation key: warengruppe if set, else artikel (first 30 chars)."""
    if warengruppe:
        return warengruppe.strip()
    return artikel.strip()[:30]


def aggregate(
    pages: list[PageResult],
    manifest: Optional[list[ManifestEntry]] = None,
) -> tuple[list[AggRow], list[KontrolleRow]]:
    """Aggregate all rechnung positions into (RN, KZ, WG) rows.

    Returns:
        agg_rows:     one row per (RN, KZ, WG) — sorted by (RN, KZ, WG)
        kontrolle_rows: one row per RN for Kontrolle 2 sheet
    """
    manifest_idx: dict[str, ManifestEntry] = {}
    if manifest:
        manifest_idx = {m.rechnungsnummer: m for m in manifest}

    # ── Step 1: group positions by (rn, kz, wg) ────────────────────
    # acc: (rn, kz, wg) -> {sum_netto, sum_ust, sum_brutto, n, artikel, land, waehrung}
    acc: dict[tuple, dict] = {}
    rn_order: list[str] = []
    seen_rn: set[str] = set()

    for page in pages:
        if page.seiten_typ != "rechnung":
            continue
        rn = page.rechnungsnummer or ""
        if rn not in seen_rn:
            rn_order.append(rn)
            seen_rn.add(rn)

        m = manifest_idx.get(rn)
        land    = m.land     if m else ""
        waehrung = m.waehrung if m else "EUR"

        for pos in page.positionen:
            if pos.netto is None and pos.brutto is None:
                continue
            kz  = (pos.kennzeichen or "").strip()
            wg  = _wg_key(pos.warengruppe, pos.artikel or "")
            art = (pos.artikel or "").strip()
            key = (rn, kz, wg)
            if key not in acc:
                acc[key] = {
                    "sum_netto": Decimal(0),
                    "sum_ust":   Decimal(0),
                    "sum_brutto":Decimal(0),
                    "n": 0,
                    "artikel":   art,
                    "land":      land,
                    "waehrung":  waehrung,
                }
            row = acc[key]
            row["sum_netto"]  += pos.netto  or Decimal(0)
            row["sum_ust"]    += pos.ust    or Decimal(0)
            row["sum_brutto"] += pos.brutto or Decimal(0)
            row["n"]          += 1
            if art and not row["artikel"]:
                row["artikel"] = art

    # ── Step 2: kz_summen accumulator (rn, kz) -> Σ netto/brutto ────
    # A card may appear in multiple cost-centre blocks in one invoice,
    # each ending with its own SUMME KARTE/KFZ row. Accumulate all.
    kz_sum_n: dict[tuple, Decimal] = defaultdict(Decimal)
    kz_sum_b: dict[tuple, Decimal] = defaultdict(Decimal)
    kz_sum_seen: set[tuple] = set()  # (rn, kz) pairs that have any entry
    for page in pages:
        if page.seiten_typ != "rechnung":
            continue
        rn = page.rechnungsnummer or ""
        for kz, ks in page.kz_summen.items():
            key = (rn, kz.strip())
            if ks.netto is not None:
                kz_sum_n[key] += ks.netto
                kz_sum_b[key] += ks.brutto or Decimal(0)
                kz_sum_seen.add(key)

    # ── Step 3: compute Σ netto per (rn, kz) for K1 ─────────────────
    kz_sigma: dict[tuple, Decimal] = defaultdict(Decimal)
    for (rn, kz, wg), row in acc.items():
        kz_sigma[(rn, kz)] += row["sum_netto"]

    # ── Step 4: build AggRow list ────────────────────────────────────
    agg_rows: list[AggRow] = []
    for rn in rn_order:
        rn_keys = [(rn, kz, wg) for (r, kz, wg) in acc if r == rn]
        for key in sorted(rn_keys, key=lambda k: (k[1], k[2])):
            _, kz, wg = key
            row = acc[key]
            kz_key = (rn, kz)
            has_ks = kz_key in kz_sum_seen

            kz_g_netto  = _d2(kz_sum_n[kz_key])  if has_ks else None
            kz_g_brutto = _d2(kz_sum_b[kz_key])  if has_ks else None

            # K1: Σ all WG-nettos for this KZ vs Σ kz_summen blocks
            if has_ks:
                sigma = kz_sigma[(rn, kz)]
                k1 = abs(cents(sigma) - cents(kz_sum_n[kz_key])) <= 2
            else:
                k1 = None

            # USt% from this WG row
            sn = row["sum_netto"]
            su = row["sum_ust"]
            ust_pct: Optional[Decimal] = None
            if sn and sn != 0:
                try:
                    ust_pct = _d2((su / sn * 100).quantize(_TWO))
                except Exception:
                    pass

            agg_rows.append(AggRow(
                rn=rn,
                land=row["land"],
                waehrung=row["waehrung"],
                kz=kz,
                wg=wg,
                artikel=row["artikel"],
                sum_netto=_d2(row["sum_netto"]),
                sum_ust=_d2(row["sum_ust"]),
                sum_brutto=_d2(row["sum_brutto"]),
                ust_pct=ust_pct,
                n=row["n"],
                kz_gesamt_netto=kz_g_netto,
                kz_gesamt_brutto=kz_g_brutto,
                k1=k1,
            ))

    # ── Step 5: Kontrolle 2 rows ─────────────────────────────────────
    summaries = [p for p in pages if p.seiten_typ == "zusammenstellung"]
    zusammen_idx: dict[str, PageResult] = {}
    for s in summaries:
        if s.rechnungsnummer:
            zusammen_idx[s.rechnungsnummer] = s

    # Σ kz_summen per RN — reuse the already-accumulated kz_sum_n/b
    rn_kzsum_netto: dict[str, Decimal]  = defaultdict(Decimal)
    rn_kzsum_brutto: dict[str, Decimal] = defaultdict(Decimal)
    for (rn, _kz), val in kz_sum_n.items():
        rn_kzsum_netto[rn]  += val
    for (rn, _kz), val in kz_sum_b.items():
        rn_kzsum_brutto[rn] += val

    # Σ pos.brutto per RN (for manifest comparison — always available)
    rn_pos_brutto: dict[str, Decimal] = defaultdict(Decimal)
    for page in pages:
        if page.seiten_typ != "rechnung":
            continue
        rn = page.rechnungsnummer or ""
        for pos in page.positionen:
            rn_pos_brutto[rn] += pos.brutto or Decimal(0)

    kontrolle_rows: list[KontrolleRow] = []
    for rn in rn_order:
        m = manifest_idx.get(rn)
        zus = zusammen_idx.get(rn)
        has_kzsum = rn in rn_kzsum_netto

        sigma_netto  = _d2(rn_kzsum_netto[rn])  if has_kzsum else None
        sigma_brutto = _d2(rn_kzsum_brutto[rn]) if has_kzsum else None
        zus_netto  = zus.rechnung_netto   if zus else None
        zus_brutto = zus.rechnung_brutto  if zus else None

        # K2: Σ kz_summen.netto vs Zusammenstellung.netto
        if has_kzsum and zus_netto is not None:
            k2 = abs(cents(_d2(rn_kzsum_netto[rn])) - cents(zus_netto)) <= 10
        else:
            k2 = None

        # Δ vs manifest (uses pos.brutto sum — available always)
        ist_brutto = rn_pos_brutto[rn]
        if m:
            soll = m.betrag_lw if m.betrag_lw is not None else m.betrag_eur
            delta_ct = cents(ist_brutto) - cents(soll)
            manifest_brutto = soll
        else:
            delta_ct = None
            manifest_brutto = None

        kontrolle_rows.append(KontrolleRow(
            rn=rn,
            land=m.land    if m else "",
            waehrung=m.waehrung if m else "EUR",
            sigma_kz_netto=sigma_netto,
            sigma_kz_brutto=sigma_brutto,
            zusammenstellung_netto=zus_netto,
            zusammenstellung_brutto=zus_brutto,
            k2=k2,
            manifest_brutto=manifest_brutto,
            delta_cent=delta_ct,
        ))

    return agg_rows, kontrolle_rows
