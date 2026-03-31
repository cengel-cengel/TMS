"""
run_audit.py
============
Master pipeline: runs the full TMS migration audit end-to-end.

Steps:
  1. Extract data from PDF invoices (Dinas + Cargosuite)
  2. Load and clean BI report
  3. Parse customer tariffs
  4. Run reconciliation (Soll/Ist comparison on comparable routes)
  5. Top-20 customer analysis with structural break test
  6. Generate Excel reports

Usage:
    cd /home/user/TMS
    python src/run_audit.py                    # Full run, all customers
    python src/run_audit.py --kunde herma      # Single customer
    python src/run_audit.py --skip-pdf         # Skip PDF extraction (use existing CSVs)
    python src/run_audit.py --inspect-pdfs     # Show first PDF's extracted text for debugging
"""

import subprocess
import sys
import argparse
from pathlib import Path
import os

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"
SRC_DIR = BASE_DIR / "src"


def run_step(description: str, cmd: list, cwd=None) -> bool:
    """Run a pipeline step and return success status."""
    print(f"\n{'─'*60}")
    print(f"▶  {description}")
    print(f"{'─'*60}")
    result = subprocess.run(cmd, cwd=cwd or BASE_DIR, capture_output=False)
    if result.returncode != 0:
        print(f"[ERROR] Step failed: {description}")
        return False
    return True


def detect_customers() -> list[str]:
    """Auto-detect customers from data directory structure."""
    if not DATA_DIR.exists():
        return []
    kunden = []
    for subdir in DATA_DIR.iterdir():
        if subdir.is_dir() and subdir.name not in ("bi_report",):
            has_data = any(subdir.rglob("*.pdf")) or any(subdir.rglob("*.csv"))
            if has_data:
                kunden.append(subdir.name)
    return kunden


def check_data_available() -> dict:
    """Check what data is available and report status."""
    status = {
        "bi_report": False,
        "kunden": {},
    }

    # BI report
    bi_files = list((DATA_DIR / "bi_report").glob("*")) if (DATA_DIR / "bi_report").exists() else []
    status["bi_report"] = len(bi_files) > 0

    # Customer data
    for kunde_dir in DATA_DIR.iterdir() if DATA_DIR.exists() else []:
        if not kunde_dir.is_dir() or kunde_dir.name == "bi_report":
            continue
        kunde = kunde_dir.name
        dinas_pdfs = list((kunde_dir / "rechnungen_dinas").rglob("*.pdf")) if (kunde_dir / "rechnungen_dinas").exists() else []
        cs_pdfs = list((kunde_dir / "rechnungen_cargosuite").rglob("*.pdf")) if (kunde_dir / "rechnungen_cargosuite").exists() else []
        tarif_files = list((kunde_dir / "tarife").glob("*")) if (kunde_dir / "tarife").exists() else []
        status["kunden"][kunde] = {
            "dinas_pdfs": len(dinas_pdfs),
            "cargosuite_pdfs": len(cs_pdfs),
            "tarif_files": len(tarif_files),
        }

    return status


def print_status(status: dict):
    """Print data availability status."""
    print(f"\n{'='*60}")
    print("DATEN-STATUS")
    print(f"{'='*60}")
    print(f"  BI-Report:      {'✓ vorhanden' if status['bi_report'] else '✗ FEHLT — bitte data/bi_report/ befüllen'}")

    if status["kunden"]:
        for kunde, info in status["kunden"].items():
            print(f"\n  Kunde: {kunde.upper()}")
            print(f"    Dinas-PDFs:      {info['dinas_pdfs']:3d}  {'✓' if info['dinas_pdfs'] > 0 else '✗ FEHLT'}")
            print(f"    Cargosuite-PDFs: {info['cargosuite_pdfs']:3d}  {'✓' if info['cargosuite_pdfs'] > 0 else '✗ FEHLT'}")
            print(f"    Tarifdokumente:  {info['tarif_files']:3d}  {'✓' if info['tarif_files'] > 0 else '⚠ keine (Soll-Preis-Berechnung eingeschränkt)'}")
    else:
        print("\n  ✗ Keine Kundendaten gefunden unter data/")
        print("  → Bitte Dateien ablegen:")
        print("     data/herma/rechnungen_dinas/*.pdf")
        print("     data/herma/rechnungen_cargosuite/*.pdf")
        print("     data/herma/tarife/*.xlsx  (oder .pdf)")
        print("     data/fischerwerke/...")
        print("     data/bi_report/*.csv  (oder .xlsx)")
    print()


def main():
    parser = argparse.ArgumentParser(description="TMS Migration Audit Pipeline")
    parser.add_argument("--kunde", type=str, help="Process specific customer only")
    parser.add_argument("--skip-pdf", action="store_true",
                        help="Skip PDF extraction (use existing CSV output)")
    parser.add_argument("--skip-bi", action="store_true",
                        help="Skip BI loading (use existing bi_report_clean.csv)")
    parser.add_argument("--inspect-pdfs", action="store_true",
                        help="Show extracted text from first PDF of each type (debugging)")
    parser.add_argument("--status", action="store_true",
                        help="Only show data availability status")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(exist_ok=True)
    os.chdir(BASE_DIR)

    print(f"\n{'='*60}")
    print("TMS MIGRATIONSAUDIT — NOERPEL GRUPPE")
    print("Dinas → Cargosuite (Anaxco) | Migrationsdatum: 26.09.2025")
    print(f"{'='*60}")

    # Check data
    status = check_data_available()
    print_status(status)

    if args.status:
        return

    # Determine customers to process
    kunden = [args.kunde] if args.kunde else detect_customers()
    if not kunden:
        print("[WARN] Keine Kundendaten gefunden. Warte auf Daten in data/")
        print("Bitte lege die Dateien ab und starte erneut.")
        return

    print(f"Kunden in Pipeline: {kunden}")

    # ─── Step 1: PDF Extraction ────────────────────────────────────────────────
    if not args.skip_pdf:
        for kunde in kunden:
            for system in ["dinas", "cargosuite"]:
                input_path = DATA_DIR / kunde / f"rechnungen_{system}"
                if not input_path.exists() or not list(input_path.rglob("*.pdf")):
                    print(f"  [SKIP] Keine PDFs: {input_path}")
                    continue

                extra = ["--verbose"] if args.inspect_pdfs else []
                run_step(
                    f"PDF-Extraktion: {kunde} / {system}",
                    [sys.executable, "src/01_pdf_extractor.py",
                     "--system", system,
                     "--input", str(input_path),
                     "--output", str(OUTPUT_DIR)] + extra
                )
    else:
        print("\n[SKIP] PDF-Extraktion übersprungen")

    # ─── Step 2: BI Report ────────────────────────────────────────────────────
    if not args.skip_bi:
        run_step(
            "BI-Report laden und normalisieren",
            [sys.executable, "src/02_bi_loader.py",
             "--input", str(DATA_DIR / "bi_report"),
             "--output", str(OUTPUT_DIR)]
        )
    else:
        print("\n[SKIP] BI-Laden übersprungen")

    # ─── Step 3: Tariff Parsing ───────────────────────────────────────────────
    for kunde in kunden:
        tarif_dir = DATA_DIR / kunde / "tarife"
        if tarif_dir.exists() and list(tarif_dir.glob("*")):
            run_step(
                f"Tarif-Parser: {kunde}",
                [sys.executable, "src/03_tariff_parser.py",
                 "--input", str(tarif_dir),
                 "--output", str(OUTPUT_DIR),
                 "--kunde", kunde]
            )
        else:
            print(f"\n  [SKIP] Keine Tarifdaten für {kunde} — Soll-Preis ohne Konditionsblatt")

    # ─── Step 4: Reconciliation ───────────────────────────────────────────────
    for kunde in kunden:
        run_step(
            f"Soll/Ist-Abgleich (vergleichbare Routen): {kunde}",
            [sys.executable, "src/04_reconciliation.py",
             "--kunde", kunde,
             "--output", str(OUTPUT_DIR),
             "--sample", "10"]
        )

    # ─── Step 5: Top-20 Analysis ──────────────────────────────────────────────
    bi_clean = OUTPUT_DIR / "bi_report_clean.csv"
    if bi_clean.exists():
        run_step(
            "Top-20 Kundenanalyse + Strukturbruch-Test",
            [sys.executable, "src/05_top20_analysis.py",
             "--bi", str(bi_clean),
             "--output", str(OUTPUT_DIR)]
        )
    else:
        print("\n  [SKIP] BI-Report nicht verfügbar für Top-20-Analyse")

    # ─── Step 6: Report Generation ───────────────────────────────────────────
    run_step(
        "Excel-Berichte generieren",
        [sys.executable, "src/06_report_generator.py",
         "--output", str(OUTPUT_DIR)]
    )

    # ─── Final Summary ────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print("PIPELINE ABGESCHLOSSEN")
    print(f"{'='*60}")
    print(f"Output-Verzeichnis: {OUTPUT_DIR}/")
    for f in sorted(OUTPUT_DIR.glob("*.csv")) | sorted(OUTPUT_DIR.glob("*.xlsx")):
        size_kb = f.stat().st_size // 1024
        print(f"  {f.name:50s} {size_kb:>6} KB")


if __name__ == "__main__":
    main()
