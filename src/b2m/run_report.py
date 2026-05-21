"""SCHRITT 4: Flag-Report + Roh-CSV aus allen extrahierten Seiten.

Reads all *.jsonl files from output/b2m/full/, produces:
  output/b2m/b2m_positionen.csv   — one row per (PDF, Seite, Kennzeichen)
  output/b2m/b2m_flag_report.txt  — summary of all validation flags

Run:
    python -m src.b2m.run_report
"""
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.b2m.schema import PageResult
from src.b2m.validate import validate_rechnung_page, validate_abrechnung

FULL_DIR = Path("output/b2m/full")
CSV_OUT = Path("output/b2m/b2m_positionen.csv")
REPORT_OUT = Path("output/b2m/b2m_flag_report.txt")

CSV_FIELDS = [
    "pdf", "seite", "seiten_typ", "rechnungsnummer",
    "kennzeichen", "artikel",
    "netto", "ust", "brutto",
    "validierung_status",
]


def load_all_pages() -> dict[str, list[PageResult]]:
    """Load all .jsonl files; return dict pdf_name → [PageResult]."""
    by_pdf: dict[str, list[PageResult]] = {}
    for jf in sorted(FULL_DIR.glob("*.jsonl")):
        pages = []
        for line in jf.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            pdf_name = d.get("_pdf", jf.stem)
            seite = d.get("_seite", 0)
            flags_stored = d.get("_flags", [])
            # Strip internal keys before parsing
            raw = {k: v for k, v in d.items() if not k.startswith("_")}
            pr = PageResult.from_dict(pdf_name, seite, raw)
            pr.flags = list(flags_stored)
            pages.append(pr)
        if pages:
            pdf_name = pages[0].pdf_name
            by_pdf.setdefault(pdf_name, []).extend(pages)
    return by_pdf


def run() -> None:
    if not FULL_DIR.exists():
        sys.exit(f"No data at {FULL_DIR} — run run_full.py first")

    by_pdf = load_all_pages()
    if not by_pdf:
        sys.exit("No .jsonl files found in output/b2m/full/")

    Path("output/b2m").mkdir(parents=True, exist_ok=True)

    rows = []
    flag_lines = []
    total_rn = 0
    total_ok = 0

    for pdf_name, pages in sorted(by_pdf.items()):
        cross_flags = validate_abrechnung(pages)
        rechnungen = [p for p in pages if p.seiten_typ == "rechnung"]
        total_rn += len(rechnungen)

        for page in pages:
            # Re-run per-page validation to ensure flags are current
            if page.seiten_typ == "rechnung":
                validate_rechnung_page(page)

            status = "✗" if page.flags else "✓"
            if page.seiten_typ == "rechnung":
                if not page.flags:
                    total_ok += 1

            if page.flags:
                for f in page.flags:
                    flag_lines.append(f"[{pdf_name} pg{page.seite}] {f}")

            for pos in page.positionen:
                rows.append({
                    "pdf": pdf_name,
                    "seite": page.seite,
                    "seiten_typ": page.seiten_typ,
                    "rechnungsnummer": page.rechnungsnummer or "",
                    "kennzeichen": pos.kennzeichen,
                    "artikel": pos.artikel,
                    "netto":   str(pos.netto)   if pos.netto   is not None else "",
                    "ust":     str(pos.ust)      if pos.ust     is not None else "",
                    "brutto":  str(pos.brutto)   if pos.brutto  is not None else "",
                    "validierung_status": status,
                })

        if cross_flags:
            for f in cross_flags:
                flag_lines.append(f"[{pdf_name} CROSS] {f}")

    # Write CSV
    with open(CSV_OUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    # Write flag report
    n_flag = total_rn - total_ok
    with open(REPORT_OUT, "w", encoding="utf-8") as f:
        f.write(f"B2M EXTRAKTION FLAG-REPORT\n")
        f.write(f"{'='*60}\n")
        f.write(f"RECHNUNG-Seiten gesamt : {total_rn}\n")
        f.write(f"Validiert ✓            : {total_ok}\n")
        f.write(f"Geflaggt  ✗            : {n_flag}\n")
        f.write(f"Positionen (CSV-Zeilen): {len(rows)}\n")
        f.write(f"{'='*60}\n")
        if flag_lines:
            f.write("\nFLAGS:\n")
            for fl in flag_lines:
                f.write(f"  ✗ {fl}\n")
        else:
            f.write("\nAlle Kreuzsummen aufgegangen ✓\n")

    print(f"CSV:    {CSV_OUT}  ({len(rows)} Zeilen)")
    print(f"Report: {REPORT_OUT}")
    print(f"  {total_ok}/{total_rn} Rechnungen validiert ✓, {n_flag} geflaggt ✗")

    if flag_lines:
        print(f"\nFlags ({len(flag_lines)}):")
        for fl in flag_lines[:20]:
            print(f"  ✗ {fl}")
        if len(flag_lines) > 20:
            print(f"  ... +{len(flag_lines)-20} weitere — siehe {REPORT_OUT}")


if __name__ == "__main__":
    run()
