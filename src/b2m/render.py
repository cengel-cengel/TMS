"""Render B2M PDF pages to JPEG at 300 DPI.

RECHNUNG pages (all middle pages) are stored in portrait orientation but contain
landscape invoice content — they need 90° rotation. Cover (page 1, ABRECHNUNGSBRIEF)
and last page (ZUSAMMENSTELLUNG) are genuine portrait and need no rotation.

JPEG is used (not PNG) to stay under the Anthropic API 5 MB base64 image limit.
PNG at 300 DPI for dense pages can reach 4+ MB raw → ~5.4 MB base64 → over limit.
JPEG quality=90 keeps the same pages under 2 MB raw.
"""
import fitz
from pathlib import Path


def render_pdf(pdf_path: Path, out_dir: Path, dpi: int = 300) -> list[Path]:
    """Render all pages to JPEG files. Returns list of paths in page order."""
    out_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(str(pdf_path))
    n = len(doc)
    paths = []

    for i, page in enumerate(doc):
        is_portrait_page = (i == 0) or (i == n - 1)
        scale = dpi / 72
        if is_portrait_page:
            mat = fitz.Matrix(scale, scale)
        else:
            mat = fitz.Matrix(scale, scale).prerotate(90)

        pix = page.get_pixmap(matrix=mat)
        out = out_dir / f"page_{i + 1:03d}.jpg"
        pix.save(str(out), jpg_quality=90)
        paths.append(out)

    doc.close()
    return paths
