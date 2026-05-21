"""SCHRITT 2: Pilot-Extraktion — nur B2M_1 1.pdf.

Renders pages as JPEG (300 DPI), sends each to Claude Vision, validates.
Caching: pages already in raw_pages.jsonl are not re-called (failed pages are).
2nd-pass: flagged RECHNUNG pages get one more Vision call to catch missed positions.
3rd-pass: genuinely orphaned null-KZ positions recovered via Σ(individual rows).

Run from project root:
    ANTHROPIC_AUTH_TOKEN=<token> python -m src.b2m.run_pilot
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.b2m.render import render_pdf
from src.b2m.vision import extract_page, recover_split_kz
from src.b2m.validate import validate_rechnung_page, validate_abrechnung, deduplicate_split_blocks
from src.b2m.schema import PageResult, ManifestEntry, parse_de as _parse_de

PDF_IN = Path("/tmp/b2m/B2M_1 1.pdf")
OUT_DIR = Path("output/b2m/pilot")
CACHE_DIR = OUT_DIR / "pages"
JSON_CACHE = OUT_DIR / "raw_pages.jsonl"


def _load_jsonl_cache() -> dict[int, dict]:
    """Return {seite: raw_dict} for successfully extracted (non-fehler) pages."""
    if not JSON_CACHE.exists():
        return {}
    cache = {}
    for line in JSON_CACHE.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        d = json.loads(line)
        seite = d.get("_seite")
        if seite and d.get("_seiten_typ") != "fehler":
            cache[seite] = d
    return cache


def _find_page_img(seite: int) -> Path | None:
    """Find the rendered image for a page — prefers .jpg over .png."""
    for ext in (".jpg", ".png"):
        p = CACHE_DIR / f"page_{seite:03d}{ext}"
        if p.exists():
            return p
    return None


def _call_vision(img: Path, seite: int, total: int, label: str = "") -> PageResult:
    t0 = time.time()
    result = extract_page(img, seite, total, PDF_IN.name)
    elapsed = time.time() - t0
    validate_rechnung_page(result)
    flag_marker = " ✗" if result.flags else ""
    fmt = f" [{result.format}]" if result.format and result.format != "de-aral" else ""
    print(f"  [{seite:3d}/{total}] {label}Vision ... {result.seiten_typ:20s}{fmt}  {elapsed:.1f}s{flag_marker}")
    for f in result.flags:
        print(f"    → {f}")
    return result


def run() -> list[PageResult]:
    if not PDF_IN.exists():
        sys.exit(f"PDF not found: {PDF_IN}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Render: JPEG preferred; fall back to PNG cache
    jpg_pages = sorted(CACHE_DIR.glob("page_*.jpg")) if CACHE_DIR.exists() else []
    png_pages = sorted(CACHE_DIR.glob("page_*.png")) if CACHE_DIR.exists() else []

    if jpg_pages:
        total = len(jpg_pages)
        print(f"  {total} cached JPEG renders in {CACHE_DIR}")
    else:
        msg = "Re-rendering (PNG→JPEG) ..." if png_pages else f"Rendering {PDF_IN.name} (JPEG 300 DPI) ..."
        print(msg)
        render_pdf(PDF_IN, CACHE_DIR, dpi=300)
        jpg_pages = sorted(CACHE_DIR.glob("page_*.jpg"))
        total = len(jpg_pages)
        print(f"  {total} pages rendered")

    total = max(total, len(png_pages))

    vision_cache = _load_jsonl_cache()
    n_cached = len(vision_cache)
    if n_cached:
        print(f"  Vision cache: {n_cached}/{total} pages already extracted")

    # ── First pass ──────────────────────────────────────────────
    pages_by_seite: dict[int, PageResult] = {}

    with open(JSON_CACHE, "w") as jf:
        for seite in range(1, total + 1):
            if seite in vision_cache:
                d = vision_cache[seite]
                raw = {k: v for k, v in d.items() if not k.startswith("_")}
                result = PageResult.from_dict(PDF_IN.name, seite, raw)
                validate_rechnung_page(result)
                jf.write(json.dumps(result.to_dict() | {
                    "_seite": seite,
                    "_seiten_typ": result.seiten_typ,
                    "_flags": result.flags,
                }) + "\n")
                pages_by_seite[seite] = result
                continue

            img = _find_page_img(seite)
            if img is None:
                continue
            result = _call_vision(img, seite, total)
            pages_by_seite[seite] = result
            jf.write(json.dumps(result.to_dict() | {
                "_seite": seite,
                "_seiten_typ": result.seiten_typ,
                "_flags": result.flags,
            }) + "\n")

    pages = [pages_by_seite[s] for s in sorted(pages_by_seite)]

    # Extract manifest from cover page
    manifest: list[ManifestEntry] | None = None
    cover = next((p for p in pages if p.seiten_typ == "abrechnungsbrief"), None)
    if cover and cover.manifest:
        manifest = cover.manifest
        print(f"\n  Manifest: {len(manifest)} Rechnungen aus Coverseite")
        for m in manifest:
            print(f"    {m.land:2s}  {m.rechnungsnummer:12s}  {m.waehrung}  {m.betrag_eur:>10.2f} EUR")

    # ── Deduplicate split-block false extras ──────────────────────
    n_deduped = deduplicate_split_blocks(pages)
    if n_deduped:
        print(f"  Deduplicated {n_deduped} split-block false extras")

    # ── Second pass: re-extract flagged RECHNUNG pages ───────────
    flagged = [p for p in pages if p.seiten_typ == "rechnung" and p.flags]
    if flagged:
        print(f"\n  2nd-pass: {len(flagged)} flagged RECHNUNG pages")
        for result in flagged:
            img = _find_page_img(result.seite)
            if img is None:
                continue
            new_result = _call_vision(img, result.seite, total, label="2nd ")
            old_flag_count = len(result.flags)
            new_flag_count = len(new_result.flags)
            old_pos = len(result.positionen)
            new_pos = len(new_result.positionen)
            if new_flag_count < old_flag_count or new_pos > old_pos:
                pages_by_seite[result.seite] = new_result
                print(f"    ✓ 2nd pass better: flags {old_flag_count}→{new_flag_count}, positions {old_pos}→{new_pos}")
            else:
                print(f"    ~ 2nd pass: no improvement — keeping 1st")

    pages = [pages_by_seite[s] for s in sorted(pages_by_seite)]

    # ── Third pass: recover orphaned null-KZ via Σ(individual rows) ──
    # Runs after 2nd-pass. Only targets (rn, kz) with NO non-null value anywhere.
    _has_value: set[tuple] = {
        (p.rechnungsnummer or "", (pos.kennzeichen or "").strip())
        for p in pages if p.seiten_typ == "rechnung"
        for pos in p.positionen if pos.netto is not None
    }
    # Deduplicate: process each (rn, kz) only once — take first occurrence.
    # A vehicle spanning 3 pages would otherwise get recovered twice.
    _seen_rn_kz: set[tuple] = set()
    null_kz_entries = []
    for p in pages:
        if p.seiten_typ != "rechnung":
            continue
        for pos in p.positionen:
            if pos.netto is not None:
                continue
            kz_str = (pos.kennzeichen or "").strip()
            if not kz_str:
                continue
            key = (p.rechnungsnummer or "", kz_str)
            if key in _has_value or key in _seen_rn_kz:
                continue
            _seen_rn_kz.add(key)
            null_kz_entries.append((p, pos))
    if null_kz_entries:
        print(f"\n  3rd-pass: {len(null_kz_entries)} orphaned null-KZ positions")
        n_recovered = 0
        for page, pos in null_kz_entries:
            kz = pos.kennzeichen or "?"
            img_paths = [img for s in (page.seite, page.seite + 1)
                         if (img := _find_page_img(s)) is not None]
            if not img_paths:
                print(f"    skip pg{page.seite} {kz} — no images")
                continue
            print(f"    pg{page.seite} {kz} ({len(img_paths)} imgs) ...", end=" ", flush=True)
            recovered = recover_split_kz(img_paths, kz)
            if recovered and recovered.get("netto") is not None:
                pos.netto   = _parse_de(recovered["netto"])
                pos.ust     = _parse_de(recovered.get("ust"))
                pos.brutto  = _parse_de(recovered.get("brutto"))
                pos.artikel = recovered.get("artikel") or pos.artikel
                print(f"✓ netto={pos.netto}")
                n_recovered += 1
            else:
                print("no rows found — still null")
            validate_rechnung_page(page)
        print(f"  Recovered: {n_recovered}/{len(null_kz_entries)}")

    # ── Save final JSONL (serializes Python object state, not p.raw) ─
    with open(JSON_CACHE, "w") as jf:
        for p in pages:
            jf.write(json.dumps(p.to_dict() | {
                "_seite": p.seite,
                "_seiten_typ": p.seiten_typ,
                "_flags": p.flags,
            }) + "\n")

    # ── Cross-page validation (Stufe 0/3/4) ──────────────────────
    cross_flags = validate_abrechnung(pages, manifest=manifest)

    # ── Report ────────────────────────────────────────────────────
    n_rn = sum(1 for p in pages if p.seiten_typ == "rechnung")
    n_ok = sum(1 for p in pages if p.seiten_typ == "rechnung" and not p.flags)
    n_flag = n_rn - n_ok
    n_fehler = sum(1 for p in pages if p.seiten_typ == "fehler")

    print("\n" + "=" * 60)
    print(f"PILOT REPORT: {PDF_IN.name}")
    print(f"  Seiten gesamt    : {total}")
    print(f"  RECHNUNG-Seiten  : {n_rn}")
    print(f"  Vision-Fehler    : {n_fehler}")
    print(f"  Validiert ✓      : {n_ok}  ({100*n_ok//max(n_rn,1)}%)")
    print(f"  Geflaggt  ✗      : {n_flag}")

    # Per-RN Soll/Ist from manifest
    if manifest:
        from collections import defaultdict
        from src.b2m.schema import cents
        by_rn: dict[str, list] = defaultdict(list)
        for p in [pp for pp in pages if pp.seiten_typ == "rechnung"]:
            if p.rechnungsnummer:
                by_rn[p.rechnungsnummer].append(p)
        print(f"\n  {'RN':12s}  {'Land':4s}  {'Währ':4s}  {'Soll LW':>10s}  {'Soll EUR':>10s}  {'Ist LW':>10s}  {'Δ Cent':>8s}  Status")
        print(f"  {'-'*12}  {'-'*4}  {'-'*4}  {'-'*10}  {'-'*10}  {'-'*10}  {'-'*8}  ------")
        for m in manifest:
            block = by_rn.get(m.rechnungsnummer, [])
            ist_brutto_ct = sum(
                cents(pos.brutto)
                for p in block for pos in p.positionen
                if pos.brutto is not None
            )
            ist_brutto = ist_brutto_ct / 100
            # Compare in local currency
            soll_lw = m.betrag_lw if m.betrag_lw is not None else m.betrag_eur
            delta_ct = ist_brutto_ct - cents(soll_lw)
            status = "✓" if abs(delta_ct) <= 10 else "✗"
            soll_lw_str = f"{float(soll_lw):>10.2f}"
            print(f"  {m.rechnungsnummer:12s}  {m.land:4s}  {m.waehrung:4s}  {soll_lw_str}  {float(m.betrag_eur):>10.2f}  {ist_brutto:>10.2f}  {delta_ct:>+8d}  {status}")

    if cross_flags:
        print(f"\n  Cross-page Flags:")
        for f in cross_flags:
            print(f"    ✗ {f}")
    else:
        print(f"\n  Cross-page (Stufe 0/3/4): ✓")

    if n_flag:
        print(f"\n  Flagged pages:")
        for p in pages:
            if p.seiten_typ == "rechnung" and p.flags:
                print(f"    pg{p.seite}: {'; '.join(p.flags[:2])}")

    print(f"\n  JSON cache: {JSON_CACHE}")
    print("=" * 60)

    return pages


if __name__ == "__main__":
    run()
