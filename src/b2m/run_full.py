"""SCHRITT 3: Vollständige Extraktion aller 5 B2M PDFs.

Only run after successful pilot (run_pilot.py) validates clean.

Run:
    ANTHROPIC_API_KEY=sk-... python -m src.b2m.run_full

Output: output/b2m/full/
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.b2m.render import render_pdf
from src.b2m.vision import extract_page
from src.b2m.validate import validate_rechnung_page, validate_abrechnung

PDF_DIR = Path("/tmp/b2m")
PDFS = [PDF_DIR / f"B2M_{i} 1.pdf" for i in range(1, 6)]
OUT_DIR = Path("output/b2m/full")


def _find_img(seite: int, cache_dir: Path) -> Path | None:
    for ext in (".jpg", ".png"):
        p = cache_dir / f"page_{seite:03d}{ext}"
        if p.exists():
            return p
    return None


def run_pdf(pdf_path: Path) -> list:
    cache_dir = OUT_DIR / "pages" / pdf_path.stem.replace(" ", "_")
    json_cache = OUT_DIR / f"{pdf_path.stem.replace(' ', '_')}_pages.jsonl"

    print(f"\n{'='*60}")
    print(f"Processing: {pdf_path.name}")
    print(f"{'='*60}")

    png_paths = render_pdf(pdf_path, cache_dir, dpi=300)
    total = len(png_paths)
    print(f"  Rendered: {total} pages")

    pages = []
    with open(json_cache, "w") as jf:
        for i, png in enumerate(png_paths):
            seite = i + 1
            print(f"  [{seite:3d}/{total}] Vision ...", end=" ", flush=True)
            t0 = time.time()
            result = extract_page(png, seite, total, pdf_path.name)
            elapsed = time.time() - t0
            flag_marker = " ✗" if result.flags else ""
            print(f"{result.seiten_typ:20s} {elapsed:.1f}s{flag_marker}")

            validate_rechnung_page(result)
            pages.append(result)
            jf.write(json.dumps(result.raw | {
                "_pdf": pdf_path.name,
                "_seite": seite,
                "_seiten_typ": result.seiten_typ,
                "_flags": result.flags,
            }) + "\n")

    from src.b2m.validate import deduplicate_split_blocks
    n_deduped = deduplicate_split_blocks(pages)
    if n_deduped:
        print(f"  Deduplicated: {n_deduped} split-block false extras")

    # ── Third pass: recover null-KZ positions via Σ(individual rows) ──
    # Only recover if (rn, kz) has NO non-null netto elsewhere in the block.
    from src.b2m.vision import recover_split_kz
    from src.b2m.schema import parse_de as _parse_de

    _has_value: set[tuple] = {
        (p.rechnungsnummer or "", (pos.kennzeichen or "").strip())
        for p in pages if p.seiten_typ == "rechnung"
        for pos in p.positionen if pos.netto is not None
    }
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
        print(f"  3rd-pass: {len(null_kz_entries)} null-KZ positions")
        n_recovered = 0
        for page, pos in null_kz_entries:
            kz = pos.kennzeichen or "?"
            img_paths = [img for s in (page.seite, page.seite + 1)
                         if (img := _find_img(s, cache_dir)) is not None]
            if not img_paths:
                continue
            print(f"    pg{page.seite} {kz} ...", end=" ", flush=True)
            recovered = recover_split_kz(img_paths, kz)
            if recovered and recovered.get("netto") is not None:
                pos.netto   = _parse_de(recovered["netto"])
                pos.ust     = _parse_de(recovered.get("ust"))
                pos.brutto  = _parse_de(recovered.get("brutto"))
                pos.artikel = recovered.get("artikel") or pos.artikel
                for raw_pos in (page.raw.get("positionen") or []):
                    if (raw_pos.get("kennzeichen") or "").strip() == kz:
                        raw_pos["netto"]   = str(pos.netto)
                        raw_pos["ust"]     = str(pos.ust)
                        raw_pos["brutto"]  = str(pos.brutto)
                        raw_pos["artikel"] = pos.artikel
                        break
                print(f"✓ netto={pos.netto}")
                n_recovered += 1
            else:
                print("no rows found")
            validate_rechnung_page(page)
        if n_recovered:
            print(f"  Recovered: {n_recovered}/{len(null_kz_entries)}")

    cover = next((p for p in pages if p.seiten_typ == "abrechnungsbrief"), None)
    manifest = cover.manifest if cover else None
    cross_flags = validate_abrechnung(pages, manifest=manifest)
    if cross_flags:
        for f in cross_flags:
            print(f"  ✗ {f}")

    return pages


def run() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    all_pages = []
    for pdf in PDFS:
        if not pdf.exists():
            print(f"SKIP (not found): {pdf}")
            continue
        all_pages.extend(run_pdf(pdf))

    # Summary
    rechnungen = [p for p in all_pages if p.seiten_typ == "rechnung"]
    n_ok = sum(1 for p in rechnungen if not p.flags)
    n_flag = len(rechnungen) - n_ok

    print(f"\n{'='*60}")
    print(f"FULL EXTRACTION COMPLETE")
    print(f"  Total pages    : {len(all_pages)}")
    print(f"  RECHNUNG pages : {len(rechnungen)}")
    print(f"  Validated ✓    : {n_ok}")
    print(f"  Flagged   ✗    : {n_flag}")
    print(f"{'='*60}")
    print(f"Next: python -m src.b2m.run_report")


if __name__ == "__main__":
    run()
