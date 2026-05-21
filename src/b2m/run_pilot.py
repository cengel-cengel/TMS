"""SCHRITT 2: Pilot-Extraktion — nur B2M_1 1.pdf.

Renders all pages, sends each to Claude Vision, validates, prints report.
Run from project root:
    ANTHROPIC_API_KEY=sk-... python -m src.b2m.run_pilot

Output written to output/b2m/pilot/
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.b2m.render import render_pdf
from src.b2m.vision import extract_page
from src.b2m.validate import validate_rechnung_page, validate_abrechnung

PDF_IN = Path("/tmp/b2m/B2M_1 1.pdf")
OUT_DIR = Path("output/b2m/pilot")
CACHE_DIR = OUT_DIR / "pages"


def run() -> list:
    if not PDF_IN.exists():
        sys.exit(f"PDF not found: {PDF_IN}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Rendering {PDF_IN.name} at 300 DPI ...")
    png_paths = render_pdf(PDF_IN, CACHE_DIR, dpi=300)
    total = len(png_paths)
    print(f"  {total} pages rendered to {CACHE_DIR}")

    pages = []
    json_cache = OUT_DIR / "raw_pages.jsonl"
    with open(json_cache, "w") as jf:
        for i, png in enumerate(png_paths):
            seite = i + 1
            print(f"  [{seite:3d}/{total}] Vision call ...", end=" ", flush=True)
            t0 = time.time()
            result = extract_page(png, seite, total, PDF_IN.name)
            elapsed = time.time() - t0
            print(f"{result.seiten_typ:20s}  {elapsed:.1f}s")

            # Per-page validation
            vr = validate_rechnung_page(result)
            status = "✓" if vr.ok else "✗"
            if result.flags:
                print(f"    {status} flags: {result.flags}")

            pages.append(result)
            jf.write(json.dumps(result.raw | {
                "_seite": seite,
                "_seiten_typ": result.seiten_typ,
                "_flags": result.flags,
            }) + "\n")

    # Cross-page validation (Stufe 3+4)
    cross_flags = validate_abrechnung(pages)

    # Report
    n_rn = sum(1 for p in pages if p.seiten_typ == "rechnung")
    n_ok = sum(1 for p in pages if p.seiten_typ == "rechnung" and not p.flags)
    n_flag = n_rn - n_ok

    print("\n" + "=" * 60)
    print(f"PILOT REPORT: {PDF_IN.name}")
    print(f"  Seiten gesamt : {total}")
    print(f"  RECHNUNG-Seiten: {n_rn}")
    print(f"  Validiert ✓   : {n_ok}")
    print(f"  Geflaggt  ✗   : {n_flag}")
    if cross_flags:
        print(f"  Cross-page Flags:")
        for f in cross_flags:
            print(f"    ✗ {f}")
    else:
        print(f"  Cross-page (Stufe 3+4): ✓")
    print(f"\n  Raw JSON: {json_cache}")
    print("=" * 60)

    return pages


if __name__ == "__main__":
    run()
