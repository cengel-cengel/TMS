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

    cross_flags = validate_abrechnung(pages)
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
