"""SCHRITT 2: Pilot-Extraktion — nur B2M_1 1.pdf.

Renders pages as JPEG (300 DPI), sends each to Claude Vision, validates.
Caching: pages already in raw_pages.jsonl are not re-called (failed pages are).
2nd-pass: flagged RECHNUNG pages get one more Vision call to catch missed positions.

Run from project root:
    ANTHROPIC_AUTH_TOKEN=<token> python -m src.b2m.run_pilot
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.b2m.render import render_pdf
from src.b2m.vision import extract_page
from src.b2m.validate import validate_rechnung_page, validate_abrechnung
from src.b2m.schema import PageResult

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
    vr = validate_rechnung_page(result)   # always re-validates (clears old flags)
    flag_marker = " ✗" if result.flags else ""
    print(f"  [{seite:3d}/{total}] {label}Vision ... {result.seiten_typ:20s}  {elapsed:.1f}s{flag_marker}")
    for f in result.flags:
        print(f"    → {f}")
    return result


def run() -> list[PageResult]:
    if not PDF_IN.exists():
        sys.exit(f"PDF not found: {PDF_IN}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Render: JPEG preferred; fall back to re-rendering PNG cache
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

    # Also count PNG pages that have no JPEG counterpart
    png_only = [p for p in png_pages if not (CACHE_DIR / (p.stem + ".jpg")).exists()]
    total = max(total, len(png_pages))

    # Load existing Vision results
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
                validate_rechnung_page(result)   # re-validate with current logic
                jf.write(json.dumps(raw | {
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
            jf.write(json.dumps(result.raw | {
                "_seite": seite,
                "_seiten_typ": result.seiten_typ,
                "_flags": result.flags,
            }) + "\n")

    pages = [pages_by_seite[s] for s in sorted(pages_by_seite)]

    # ── Second pass: re-extract flagged RECHNUNG pages ──────────
    flagged = [p for p in pages if p.seiten_typ == "rechnung" and p.flags]
    if flagged:
        print(f"\n  2nd-pass: {len(flagged)} flagged RECHNUNG pages")
        for result in flagged:
            img = _find_page_img(result.seite)
            if img is None:
                continue
            new_result = _call_vision(img, result.seite, total, label="2nd ")
            # Accept 2nd pass if it reduces flags (or has fewer missing positions)
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

    # ── Save final JSONL (with 2nd-pass results) ─────────────────
    with open(JSON_CACHE, "w") as jf:
        for p in pages:
            jf.write(json.dumps(p.raw | {
                "_seite": p.seite,
                "_seiten_typ": p.seiten_typ,
                "_flags": p.flags,
            }) + "\n")

    # ── Cross-page validation (Stufe 3+4) ────────────────────────
    cross_flags = validate_abrechnung(pages)

    # ── Report ───────────────────────────────────────────────────
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
    if cross_flags:
        print(f"  Cross-page Flags :")
        for f in cross_flags:
            print(f"    ✗ {f}")
    else:
        print(f"  Cross-page (Stufe 3+4): ✓")
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
