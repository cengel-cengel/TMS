"""Targeted re-extraction of AT invoice pages only.

Re-runs Vision on AT RN pages across B2M_1–4 with updated prompt
(KOSTENSTELLEN-SUMME 2 now extracted as positions).
Updates the JSONL files in-place. B2M_5 has no AT invoices.

Run:
    ANTHROPIC_AUTH_TOKEN=... python -m src.b2m.rerun_at_pages
"""
from __future__ import annotations
import json
import time
from pathlib import Path

from src.b2m.schema import PageResult
from src.b2m.vision import extract_page
from src.b2m.validate import validate_rechnung_page

FULL_DIR = Path("output/b2m/full")
IMG_BASE = Path("output/b2m/full/pages")

AT_RNS = {"3603006105", "3603014114", "3603022414", "3603030499"}

PDF_STEMS = ["B2M_1_1", "B2M_2_1", "B2M_3_1", "B2M_4_1"]


def _find_img(seite: int, stem: str) -> Path | None:
    cache_dir = IMG_BASE / stem
    for ext in (".jpg", ".png"):
        p = cache_dir / f"page_{seite:03d}{ext}"
        if p.exists():
            return p
    return None


def rerun_stem(stem: str) -> None:
    jsonl = FULL_DIR / f"{stem}_pages.jsonl"
    pdf_name = stem.removesuffix("_1") + " 1.pdf"

    lines = jsonl.read_text().splitlines()
    pages_by_seite: dict[int, dict] = {}
    for line in lines:
        line = line.strip()
        if not line:
            continue
        d = json.loads(line)
        pages_by_seite[d["_seite"]] = d

    total = max(pages_by_seite)

    # Find AT pages
    at_seiten = []
    for seite, d in pages_by_seite.items():
        raw = {k: v for k, v in d.items() if not k.startswith("_")}
        p = PageResult.from_dict(pdf_name, seite, raw)
        if p.rechnungsnummer in AT_RNS and p.seiten_typ == "rechnung":
            at_seiten.append(seite)

    if not at_seiten:
        print(f"  {stem}: no AT pages — skip")
        return

    print(f"\n  {stem}: re-extracting {len(at_seiten)} AT pages: {at_seiten}")
    changed = 0
    for seite in sorted(at_seiten):
        img = _find_img(seite, stem)
        if img is None:
            print(f"    pg{seite}: no image — skip")
            continue

        print(f"    pg{seite} ...", end=" ", flush=True)
        t0 = time.time()
        result = extract_page(img, seite, total, pdf_name)
        elapsed = time.time() - t0
        validate_rechnung_page(result)

        old_d = pages_by_seite[seite]
        old_raw = {k: v for k, v in old_d.items() if not k.startswith("_")}
        old_p = PageResult.from_dict(pdf_name, seite, old_raw)

        old_brutto = sum(pos.brutto or 0 for pos in old_p.positionen)
        new_brutto = sum(pos.brutto or 0 for pos in result.positionen)

        pages_by_seite[seite] = result.to_dict() | {
            "_seite": seite,
            "_seiten_typ": result.seiten_typ,
            "_flags": result.flags,
            "_pdf": pdf_name,
        }
        changed += 1
        flag = " ✗" if result.flags else ""
        print(f"Σbrutto: {float(old_brutto):.2f} → {float(new_brutto):.2f}  ({elapsed:.1f}s){flag}")

    if changed:
        with open(jsonl, "w") as f:
            for seite in sorted(pages_by_seite):
                f.write(json.dumps(pages_by_seite[seite]) + "\n")
        print(f"  {stem}: JSONL updated ({changed} pages rewritten)")


def run() -> None:
    for stem in PDF_STEMS:
        rerun_stem(stem)
    print("\nDone. Run: python -m src.b2m.run_aggregated")


if __name__ == "__main__":
    run()
